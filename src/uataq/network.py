"""
This module provides classes for combining and analyzing data across multiple sites.
"""

import logging
import multiprocessing
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal

import geopandas as gpd
import pandas as pd

from uataq import _laboratory, errors, filesystem, sites
from uataq.instruments import Instrument
from uataq.timerange import TimeRange, TimeRangeTypes

_logger = logging.getLogger(__name__)

#: Colors for each data level in :meth:`Network.plot_availability`. Levels are
#: ordered, so they share one hue, from light (raw) to dark (final).
LEVEL_COLORS: dict[str, str] = {
    "raw": "#86b6ef",
    "qaqc": "#3987e5",
    "calibrated": "#1c5cab",
    "final": "#0d366b",
}


def concentration_columns(pollutant: str, columns: Iterable[str]) -> list[str]:
    """
    Pick the columns holding a pollutant's measured concentration.

    Matches ``{pollutant}_{unit}`` with a concentration unit, e.g. ``O3_ppb``,
    ``CO2d_ppm`` (dry mole fraction), ``CH4d_ppm_cal`` (calibrated),
    ``PM2.5_ugm3`` or ``BC6_ngm3`` (an aethalometer channel). Instrument
    diagnostics that share the prefix, like ``O3_Meas_mV`` or ``NO2_Slope``,
    and spreads like ``O3_ppb_std`` are not matches.

    Parameters
    ----------
    pollutant : str
        The pollutant, matched case-insensitively.
    columns : Iterable[str]
        Column names to search.

    Returns
    -------
    list[str]
        The matching columns, in their original order.
    """
    # BC is reported per wavelength channel (BC1..BC7); everything else may
    # carry a "d" for dry mole fraction. Kept apart so PM1 can't match PM10.
    infix = r"\d" if pollutant.upper() == "BC" else "d?"
    pattern = re.compile(
        rf"^{re.escape(pollutant)}{infix}_(ppm|ppb|ugm3|ngm3)(_cal)?$", re.IGNORECASE
    )
    return [col for col in columns if pattern.match(col)]


def _datafile_coverage(
    task: tuple[str, Instrument, str, str, filesystem.DataFile, str, str, TimeRange],
) -> tuple[str, str, pd.PeriodIndex | None]:
    """
    Find the time bins in which one data file has the pollutant.

    Module-level so :class:`multiprocessing.Pool` can pickle it.

    Parameters
    ----------
    task : tuple
        ``(SID, instrument, group, lvl, datafile, pollutant, freq, time_range)``.
        ``time_range`` is already clipped to when the instrument was installed.

    Returns
    -------
    tuple[str, str, pd.PeriodIndex | None]
        ``(SID, lvl, bins)``: the bins holding at least one non-null
        concentration, or None if the file could not be read.
    """
    SID, instrument, group, lvl, datafile, pollutant, freq, time_range = task
    try:
        data = datafile.parse()
        # Stray header rows inside a file parse to NaT; drop them before
        # standardizing, as parse_datafiles does, or unit conversions see text.
        data = data.dropna(subset="Time_UTC")
        data = instrument.standardize_data(group, data)
    except Exception as e:
        # A survey of thousands of files should report a bad one, not stop on it.
        _logger.warning(f"Skipping {datafile} ({type(e).__name__}: {e})")
        return SID, lvl, None

    columns = concentration_columns(pollutant, data.columns)
    values = data[columns].apply(pd.to_numeric, errors="coerce")
    times = data.loc[values.notna().any(axis=1), "Time_UTC"]

    start, stop = time_range
    if start is not None:
        times = times[times >= start]
    # An instrument still installed has no stop; cap at now so a corrupt
    # timestamp (seen: year ~178 billion) can't become a bin in the far future.
    now = pd.Timestamp.now("UTC").tz_localize(None)
    if future := int((times > now).sum()):
        _logger.warning(f"{datafile}: dropping {future} rows stamped after now")
    stop = now if stop is None else min(stop, now)
    times = times[times < stop]

    return SID, lvl, pd.PeriodIndex(times.dt.to_period(freq).unique())


def _coverage_to_segments(SID: str, coverage: dict[str, set[pd.Period]]) -> list[dict]:
    """
    Collapse per-level time bins into runs of the best available level.

    Parameters
    ----------
    SID : str
        The site ID, copied onto every segment.
    coverage : dict[str, set[pd.Period]]
        For each data level, the bins in which it has data.

    Returns
    -------
    list[dict]
        Segments with keys ``SID``, ``lvl``, ``start``, ``stop``. Each bin
        takes the highest level that covers it; consecutive bins sharing a
        level merge into one half-open ``[start, stop)`` segment.
    """
    best: dict[pd.Period, str] = {}
    for lvl, bins in coverage.items():
        for b in bins:
            if b not in best or filesystem.lvls[lvl] > filesystem.lvls[best[b]]:
                best[b] = lvl

    runs: list[list] = []  # [lvl, first bin, last bin]
    for b in sorted(best, key=lambda b: b.ordinal):
        lvl = best[b]
        if runs and runs[-1][0] == lvl and runs[-1][2] + 1 == b:
            runs[-1][2] = b
        else:
            runs.append([lvl, b, b])

    return [
        {
            "SID": SID,
            "lvl": lvl,
            "start": first.start_time,
            "stop": (last + 1).start_time,
        }
        for lvl, first, last in runs
    ]


class Network:
    """
    Container for combining and analyzing data across multiple sites for a single pollutant.

    This class aggregates measurements from multiple sites (stationary and/or mobile)
    for a single pollutant, handling spatial coordinates appropriately for each site type.

    Attributes
    ----------
    sites : list[str]
        List of site identifiers.
    pollutant : str
        The pollutant to retrieve data for (uppercase).
    site_objects : list[sites.Site]
        List of Site or MobileSite objects that measure the specified pollutant.
    group : str | None
        The research group to read data from.

    Methods
    -------
    get_obs(time_range=None, num_processes=1)
        Get observations for the network across all sites.
    get_availability(time_range=None, freq='D', lvls=None, num_processes=1)
        When each site has data for the pollutant, and at what level.
    plot_availability(availability=None, ax=None, **kwargs)
        Plot data availability per site, colored by level.
    """

    def __init__(
        self,
        sites: list[str] | tuple[str, ...] | Literal["all"],
        pollutant: str,
        group: str | None = None,
    ):
        """
        Initialize a Network object.

        Parameters
        ----------
        sites : list[str] | tuple[str, ...] | 'all'
            List of site identifiers to include in the network, or 'all' for
            every configured site (those not measuring the pollutant drop out).
        pollutant : str
            The pollutant to measure. Will be converted to uppercase.
            Examples: 'CO2', 'O3', 'NO2', 'PM2.5', 'BC'
        group : str, optional
            The research group to read data from. If None, uses the default group.

        Raises
        ------
        ValueError
            If sites is empty or if no sites measure the specified pollutant.
        """
        if not sites:
            raise ValueError("sites cannot be empty.")
        if sites == "all":
            sites = _laboratory.laboratory.sites

        self.sites = [s.upper() for s in sites]
        self.pollutant = pollutant.upper()
        self.group = group

        # Validate and filter sites
        self.site_objects = self._validate_sites()

        if not self.site_objects:
            raise ValueError(
                f"No sites found that measure pollutant '{self.pollutant}'. "
                f"Valid sites: {self.sites}"
            )

        _logger.info(
            f"Network initialized for {self.pollutant} at {len(self.site_objects)} sites: "
            f"{[site.SID for site in self.site_objects]}"
        )

    def __repr__(self) -> str:
        site_ids = [site.SID for site in self.site_objects]
        return f"Network(sites={site_ids}, pollutant='{self.pollutant}')"

    def __str__(self) -> str:
        site_ids = [site.SID for site in self.site_objects]
        return f"Network: {self.pollutant} at {site_ids}"

    def _validate_sites(self) -> list[sites.Site]:
        """
        Validate that all sites exist and measure the requested pollutant.

        Returns
        -------
        list[sites.Site]
            List of Site or MobileSite objects that measure the pollutant.
            Sites that don't measure the pollutant are silently excluded.

        Raises
        ------
        ValueError
            If a site ID is not found in the configuration.
        """
        valid_sites = []

        for sid in self.sites:
            try:
                site = _laboratory.get_site(sid)
            except ValueError as e:
                _logger.warning(f"Site '{sid}' not found: {e}")
                continue

            # Check if site measures the requested pollutant
            if self.pollutant in site.pollutants:
                valid_sites.append(site)
            else:
                _logger.debug(
                    f"Site '{sid}' does not measure pollutant '{self.pollutant}'. "
                    f"Available: {site.pollutants}"
                )

        return valid_sites

    def get_obs(
        self,
        time_range: TimeRange | TimeRangeTypes | None = None,
        num_processes: int | Literal["max"] = 1,
    ) -> gpd.GeoDataFrame:
        """
        Get observations for the network across all sites.

        Combines data from all sites into a single GeoDataFrame with spatial coordinates,
        always using the highest available data level (consistent with Site.get_obs()).
        For stationary sites, coordinates are repeated for each timestamp.
        For mobile sites, coordinates vary with GPS data.

        This method is optimized for the common case of combining data from multiple sites
        for one pollutant at the final data level. For complex custom filtering (e.g., reading
        from multiple instruments at different levels, applying custom QAQC flags), use the
        lower-level Site.read_data() API directly.

        Parameters
        ----------
        time_range : TimeRange | TimeRangeTypes, optional
            The time range to retrieve data for. Can be a TimeRange object,
            string, list, or None (all data). Default is None.
        num_processes : int | Literal["max"], optional
            Number of processes to use for parallel data reading. Default is 1.

        Returns
        -------
        geopandas.GeoDataFrame
            A GeoDataFrame with the following structure:
            - Index: Time_UTC (datetime)
            - Columns: SID, [pollutant columns], Latitude_deg, Longitude_deg, zagl, geometry
            - CRS: EPSG:4326

        Raises
        ------
        ReaderError
            If no data is found for any site.
        """
        _logger.info(
            f"Reading {self.pollutant} data from {len(self.site_objects)} sites..."
        )

        dataframes = []
        for site in self.site_objects:
            try:
                site_data = self._read_site_data(site, time_range, num_processes)
                dataframes.append(site_data)
            except errors.ReaderError as e:
                _logger.warning(f"Error reading data from {site.SID}: {e}")

        if not dataframes:
            raise errors.ReaderError(f"No data found for {self.pollutant} in any site.")

        # Concatenate all site dataframes
        _logger.info("Concatenating data from all sites...")
        combined = pd.concat(dataframes, axis=0, sort=False)

        # Convert to GeoDataFrame
        _logger.info("Creating GeoDataFrame with spatial geometry...")
        gdf = gpd.GeoDataFrame(
            combined,
            geometry=gpd.points_from_xy(
                combined["Longitude_deg"], combined["Latitude_deg"]
            ),
            crs="EPSG:4326",
        )

        return gpd.GeoDataFrame(gdf.sort_index())

    def _pollutant_instruments(self, site: sites.Site) -> list[Instrument]:
        """Instruments at a site measuring this network's pollutant."""
        # Instruments declare mixed case ("NOx"); the network stores uppercase.
        return [
            instrument
            for instrument in site.instruments
            if self.pollutant
            in {p.upper() for p in getattr(instrument, "pollutants", ())}
        ]

    def get_availability(
        self,
        time_range: TimeRange | TimeRangeTypes | None = None,
        freq: str = "D",
        lvls: list[str] | None = None,
        num_processes: int | Literal["max"] = 1,
    ) -> pd.DataFrame:
        """
        Find when each site has data for the pollutant, and at what level.

        Every data file is parsed, so this reflects real measurements rather
        than which files exist: a time bin counts for a level when any row in
        it has a non-null concentration (see :func:`concentration_columns`).
        Each bin is labeled with the highest level that covers it, so a bin
        measured but dropped from final data shows as qaqc.

        Parameters
        ----------
        time_range : TimeRange | TimeRangeTypes, optional
            The time range to check. Default is None (all data).
        freq : str, optional
            The size of a time bin, as a pandas period alias: 'h', 'D', 'W',
            'M', ... Default is 'D'.
        lvls : list[str], optional
            The data levels to check. Default is None, every level in
            :data:`uataq.filesystem.lvls`. Checking fewer is faster.
        num_processes : int | 'max', optional
            Number of processes used to parse files. Default is 1. A whole
            network is thousands of files; use a compute node.

        Returns
        -------
        pandas.DataFrame
            One row per segment, with columns ``SID``, ``lvl``, ``start`` and
            ``stop``. Segments are half-open ``[start, stop)``. Sites with no
            data have no rows.

        Notes
        -----
        If the network was built without a group, every group that operates
        an instrument is checked (TRX01 ozone, for instance, is in both the
        lin and horel archives), not only the one ``get_obs`` would read.
        """
        lvls = lvls or list(filesystem.lvls)
        if invalid := set(lvls) - set(filesystem.lvls):
            raise ValueError(
                f"Invalid level(s) {invalid}. Must be in {list(filesystem.lvls)}."
            )
        time_range = TimeRange(time_range)

        # One task per data file, across the whole network, so a single pool
        # stays busy instead of one pool per site.
        tasks = []
        for site in self.site_objects:
            for instrument in self._pollutant_instruments(site):
                if self.group:
                    groups = [instrument.resolve_group(self.group)]
                else:
                    groups = [g for g in instrument.groups if g in filesystem.groups]
                for group in groups:
                    for lvl in lvls:
                        try:
                            clipped = instrument.clip_to_active(time_range)
                            datafiles = instrument.get_datafiles(group, lvl, clipped)
                        except (errors.ReaderError, FileNotFoundError, ValueError) as e:
                            # This group doesn't keep this level, or has no files
                            # in range.
                            _logger.debug(
                                f"No {lvl} files for {instrument} in {group}: {e}"
                            )
                            continue
                        tasks.extend(
                            (
                                site.SID,
                                instrument,
                                group,
                                lvl,
                                datafile,
                                self.pollutant,
                                freq,
                                clipped,
                            )
                            for datafile in datafiles
                        )

        _logger.info(
            f"Checking {len(tasks)} files for {self.pollutant} "
            f"at {len(self.site_objects)} sites..."
        )
        processes = filesystem.cpu_count() if num_processes == "max" else num_processes
        processes = max(1, min(processes, len(tasks)))
        if processes == 1:
            results = [_datafile_coverage(task) for task in tasks]
        else:
            with multiprocessing.Pool(processes) as pool:
                results = pool.map(_datafile_coverage, tasks, chunksize=4)

        coverage: dict[str, dict[str, set[pd.Period]]] = defaultdict(
            lambda: defaultdict(set)
        )
        skipped = 0
        for SID, lvl, bins in results:
            if bins is None:
                skipped += 1
            else:
                coverage[SID][lvl].update(bins)
        if skipped:
            _logger.warning(f"{skipped} of {len(tasks)} files could not be read.")

        segments = [
            segment
            for site in self.site_objects
            for segment in _coverage_to_segments(site.SID, coverage[site.SID])
        ]
        return pd.DataFrame(segments, columns=pd.Index(["SID", "lvl", "start", "stop"]))

    def plot_availability(
        self,
        availability: pd.DataFrame | None = None,
        ax=None,
        **kwargs,
    ):
        """
        Plot when each site has data for the pollutant, colored by level.

        Time runs along x and each site gets a row, with a bar wherever it has
        data, shaded light (raw) to dark (final) by :data:`LEVEL_COLORS`.
        Requires the optional matplotlib dependency.

        Parameters
        ----------
        availability : pandas.DataFrame, optional
            The output of :meth:`get_availability`. If None, it is computed,
            passing ``kwargs`` along. Compute it once and pass it in to restyle
            the plot without re-reading the archive.
        ax : matplotlib.axes.Axes, optional
            Axes to draw on. Default is None, which makes a new figure.
        **kwargs
            Passed to :meth:`get_availability` when ``availability`` is None.

        Returns
        -------
        matplotlib.axes.Axes
            The axes drawn on.
        """
        import matplotlib.dates as mdates  # pyright: ignore[reportMissingImports]  # optional plotting extra
        import matplotlib.patches as mpatches  # pyright: ignore[reportMissingImports]  # optional plotting extra
        import matplotlib.pyplot as plt  # pyright: ignore[reportMissingImports]  # optional plotting extra

        if availability is None:
            availability = self.get_availability(**kwargs)

        # Every site in the network gets a row, top to bottom in network
        # order, so a site with no data shows up as an empty row.
        SIDs = [site.SID for site in self.site_objects]
        if ax is None:
            _, ax = plt.subplots(figsize=(10, 0.35 * len(SIDs) + 1.5))

        height = 0.6
        for row, SID in enumerate(SIDs):
            site_segments = availability[availability["SID"] == SID]
            for lvl, segments in site_segments.groupby("lvl"):
                start = mdates.date2num(segments["start"])
                stop = mdates.date2num(segments["stop"])
                ax.broken_barh(
                    list(zip(start, stop - start, strict=True)),
                    (row - height / 2, height),
                    facecolors=LEVEL_COLORS[str(lvl)],
                    linewidth=0,
                )

        ax.set_yticks(range(len(SIDs)), SIDs)
        ax.set_ylim(len(SIDs) - 0.5, -0.5)  # first site on top
        ax.xaxis_date()
        ax.grid(axis="x", color="0.9", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)

        present = [lvl for lvl in filesystem.lvls if lvl in set(availability["lvl"])]
        ax.legend(
            handles=[
                mpatches.Patch(color=LEVEL_COLORS[lvl], label=lvl) for lvl in present
            ],
            loc="lower left",
            bbox_to_anchor=(0, 1),
            ncols=len(present) or 1,
            frameon=False,
        )
        ax.set_title(f"{self.pollutant} data availability", loc="left", pad=28)
        return ax

    def _read_site_data(
        self,
        site: sites.Site,
        time_range: TimeRange | TimeRangeTypes | None = None,
        num_processes: int | Literal["max"] = 1,
    ) -> pd.DataFrame:
        """
        Read and prepare data for a single site.

        Parameters
        ----------
        site : sites.Site
            The site object to read data from.
        time_range : TimeRange | TimeRangeTypes | None
            Time range to filter data.
        num_processes : int | Literal["max"]
            Number of processes for parallel reading.

        Returns
        -------
        pd.DataFrame
            DataFrame with SID, coordinates, and pollutant data.

        Raises
        ------
        ReaderError
            If no data is found for the site.
        """
        from uataq import filesystem as fs

        # Find instruments that measure this pollutant
        instruments_to_read = [
            instr.name
            for instr in site.instruments
            if hasattr(instr, "pollutants") and self.pollutant in instr.pollutants  # type: ignore
        ]

        if not instruments_to_read:
            raise errors.ReaderError(
                f"No instruments at {site.SID} measure {self.pollutant}"
            )

        # Determine group if not specified
        group = self.group or fs.get_group(None)

        # Read raw instrument data at the highest/final level
        data_dict = site.read_data(
            instruments=instruments_to_read,
            group=group,
            lvl=None,  # Gets highest available level
            time_range=time_range,
            num_processes=num_processes,
        )

        # Extract pollutant columns from all instruments
        dataframes = []
        for instrument_name, df in data_dict.items():
            if instrument_name == "gps":
                continue  # Skip GPS; we'll handle separately

            # Filter columns to only include those matching the pollutant
            pollutant_columns = [
                col
                for col in df.columns
                if self.pollutant in col.upper() or col.upper() == self.pollutant
            ]

            if pollutant_columns:
                df_filtered = df[pollutant_columns].copy()
                dataframes.append(df_filtered)

        if not dataframes:
            raise errors.ReaderError(
                f"No data columns found for {self.pollutant} at {site.SID}"
            )

        # Combine instrument data for this site
        site_data = pd.concat(dataframes, axis=1)
        site_data["SID"] = site.SID

        # Handle coordinate information
        if isinstance(site, sites.MobileSite):
            # Mobile site: use GPS data with group-specific merging
            try:
                gps_data = site.read_data(
                    instruments="gps",
                    group=group,
                    lvl=None,  # GPS typically only has final level
                    time_range=time_range,
                    num_processes=num_processes,
                )["gps"]

                # Use MobileSite.merge_gps() to handle group-specific logic
                # Set index to Time_UTC for wide format
                site_data.index.name = "Time_UTC"

                # Determine merge column based on group
                if group == "lin":
                    merge_on = "Pi_Time"
                    site_data.index.name = "Pi_Time"
                elif group == "horel":
                    merge_on = "Time_UTC"
                else:
                    merge_on = "Time_UTC"

                # Use the static merge_gps method from MobileSite
                site_data = sites.MobileSite.merge_gps(site_data, gps_data, on=merge_on)

                # Clean up Pi_Time column if it was used for merging
                if merge_on == "Pi_Time" and "Pi_Time" in site_data.columns:
                    site_data = site_data.drop(columns=["Pi_Time"])

            except (errors.ReaderError, KeyError) as e:
                _logger.warning(
                    f"Could not read GPS data for mobile site {site.SID}: {e}"
                )
                raise
        else:
            # Stationary site: use fixed coordinates from config
            latitude = site.config.get("latitude")
            longitude = site.config.get("longitude")

            if latitude is None or longitude is None:
                raise ValueError(
                    f"Site {site.SID} is missing latitude or longitude in config"
                )

            site_data["Latitude_deg"] = latitude
            site_data["Longitude_deg"] = longitude

        # Add height above ground level
        zagl = site.config.get("zagl")
        site_data["zagl"] = zagl if zagl is not None else None

        return site_data
