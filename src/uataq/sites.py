"""
Classes and functions for working with UATAQ sites.
"""

import datetime as dt
import json
import logging
import warnings
from collections import defaultdict
from collections.abc import Mapping
from typing import Literal

import geopandas as gpd
import numpy as np
import pandas as pd

from uataq import errors, instruments
from uataq.filesystem.core import _parse_once
from uataq.pollutants import POLLUTANTS
from uataq.timerange import TimeRange, TimeRangeTypes

_logger = logging.getLogger(__name__)

_all_or_mult_strs = Literal["all"] | str | list[str] | tuple[str, ...] | set[str]

# How far past its rows' range lin's GPS is read. lin rows are joined to lin's
# GPS on the Pi's clock, but a read selects the fixes by their GPS time, and
# the Pi's clock has been days off: up to 5 days on TRX01 in 2022-11, 4.5 days
# in 2018-08, hours in 2016 (#94).
_PI_CLOCK_MARGIN = dt.timedelta(days=7)


def _describe_plan(plan: instruments.ReadPlan) -> str:
    """Name the groupspace(s) a read plan reads from, with dates when split."""
    if len(plan) == 1:
        return f"{plan[0][0]} groupspace"
    return " and ".join(f"{group} groupspace ({portion})" for group, portion in plan)


def _no_data(asked: str, lvl: str | None, SID: str, detail: str) -> errors.ReaderError:
    """
    Build the error for a read at a site that found no data.

    ``asked`` is what the caller asked for: the instruments of a ``read_data``,
    the pollutants of a ``get_obs``. ``detail`` says what became of each
    instrument, and ``lvl`` is the level that was read, if one was named.
    """
    level = f"{lvl.lower()} " if lvl else ""
    error = errors.ReaderError(f"No {level}data found for {asked} at {SID}: {detail}.")
    error.detail = detail
    return error


def _reject_level(kwargs: Mapping[str, object]) -> None:
    """Raise TypeError if ``get_obs`` was given a level, which it never takes."""
    for name in ("lvl", "level"):
        if name in kwargs:
            raise TypeError(
                f"get_obs() got an unexpected keyword argument '{name}'. get_obs "
                "always reads the final level; to read another, call "
                f"read_data(..., lvl={kwargs[name]!r})."
            )


def _read_plan(
    instrument: instruments.Instrument,
    plan: instruments.ReadPlan,
    lvl: str | None,
    num_processes: int | Literal["max"],
    file_pattern: str | None,
) -> pd.DataFrame:
    """
    Read each ``(group, portion)`` of a plan and concatenate them in time.

    A portion that raises ReaderError is logged and skipped, so the others
    are still returned.

    Raises
    ------
    ReaderError
        If every portion fails. A single-portion plan re-raises its own error.
    """
    if len(plan) == 1:
        group, portion = plan[0]
        return instrument.read_data(group, lvl, portion, num_processes, file_pattern)

    frames = []
    failures = []
    for group, portion in plan:
        try:
            frames.append(
                instrument.read_data(group, lvl, portion, num_processes, file_pattern)
            )
        except errors.ReaderError as e:
            _logger.warning(f"No {instrument} data from {group} for {portion}: {e}")
            failures.append(f"{group} ({portion}): {e}")
    if not frames:
        raise errors.ReaderError(
            f"No {instrument} data from any group: " + "; ".join(failures)
        )
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames).sort_index(kind="stable")


def _split_by_plan(
    frame: pd.DataFrame, plan: instruments.ReadPlan
) -> list[pd.DataFrame]:
    """
    Cut an instrument's frame back into the rows each portion of its plan read.

    Returns one frame per ``(group, portion)`` of ``plan``, in the same order.
    Reads slice rows to their portion, so a row belongs to the last portion
    starting at or before it; cutting at the starts alone keeps every row.
    """
    if len(plan) == 1:
        return [frame]
    times = pd.DatetimeIndex(frame.index)
    pieces = []
    for i, (_, portion) in enumerate(plan):
        keep = np.ones(len(frame), dtype=bool)
        if i > 0 and portion.start is not None:
            keep &= times >= pd.Timestamp(portion.start)
        next_start = plan[i + 1][1].start if i + 1 < len(plan) else None
        if next_start is not None:
            keep &= times < pd.Timestamp(next_start)
        pieces.append(frame[keep])
    return pieces


def _span(portions: list[TimeRange]) -> TimeRange:
    """Return the smallest range covering every portion; a None bound is unbounded."""
    starts = [p.start for p in portions if p.start is not None]
    stops = [p.stop for p in portions if p.stop is not None]
    start = min(starts) if len(starts) == len(portions) else None
    stop = max(stops) if len(stops) == len(portions) else None
    return TimeRange(start=start, stop=stop)


def _widen(span: TimeRange, margin: dt.timedelta) -> TimeRange:
    """Return ``span`` reaching ``margin`` further on each bounded side."""
    start = None if span.start is None else span.start - margin
    stop = None if span.stop is None else span.stop + margin
    return TimeRange(start=start, stop=stop)


def _reshape_obs(
    df: pd.DataFrame, pattern: str, format: Literal["wide", "long"]
) -> pd.DataFrame:
    """Keep one instrument's ``pattern`` columns, wide or melted long."""
    if format == "wide":
        return pd.DataFrame(df.filter(regex=pattern).dropna(how="all"))
    melted = df.reset_index().melt(
        id_vars="Time_UTC",
        value_vars=list(df.columns),
        var_name="pollutant",
        value_name="value",
    )
    melted = pd.DataFrame(melted[melted["pollutant"].str.contains(pattern)])
    melted = melted.dropna(subset=["value"])
    return melted.set_index("Time_UTC")


class Site:
    """
    A class representing a site where atmospheric measurements are taken.

    Attributes
    ----------
    SID : str
        The site identifier.
    config : dict
        A dictionary containing configuration information for the site.
    instruments : InstrumentEnsemble
        An instance of the InstrumentEnsemble class representing the instruments at the site.
    groups : set of str
        The research groups that collect data at the site.
    loggers : set of str
        The loggers used by research groups that record data at a site.
    pollutants : set of str
        The pollutants measured at the site, in upper case (``'NOX'`` for NOx).
        ``get_obs`` takes them in any case.
    pollutant_instruments : dict[str, list[Instrument]]
        The instruments that measure each pollutant, keyed by the pollutant's
        upper-case name, as in ``pollutants``.

    Methods
    -------
    read_data(instruments='all', group=None, lvl=None, time_range=None, num_processes=1, file_pattern=None)
        Read data for each instrument for specified level.
    get_obs(pollutants='all', format='wide', group=None, time_range=None, num_processes=1)
        Get observations for each pollutant, combining instruments by pollutants.
    get_recent_obs(recent=dt.timedelta(days=10), pollutants='all', format='wide', group=None)
        Get recent observations from site instruments.
    """

    def __init__(
        self, SID: str, config: dict, instruments: instruments.InstrumentEnsemble
    ):
        """
        Initialize a Site object with the given site ID.

        Parameters
        ----------
        SID : str
            The site identifier.
        config : dict
            A dictionary containing configuration information for the site:

            .. code-block:: python

                {
                    name: str,
                    is_active: bool,
                    is_mobile: bool,
                    latitude: float,
                    longitude: float,
                    zagl: float,
                    loggers: dict,
                    instruments: {
                        instrument: {
                            loggers: dict
                            installation_date: str,
                            removal_date: str,
                        }
                    }
                }

        instruments : InstrumentEnsemble
            An instance of the InstrumentEnsemble class representing the instruments at the site.
        """
        self.SID = SID
        self.config = config
        self.instruments = instruments
        self.groups = instruments.groups
        self.loggers = instruments.loggers
        self.pollutants = instruments.pollutants

        # Build pollutant: instruments lookup table, keyed by the uppercase
        # name like self.pollutants. Column names keep the declared case
        # ("NOx_ppb"), so remember it for filtering columns.
        self.pollutant_instruments = defaultdict(list)
        self._declared_pollutants: dict[str, str] = {}
        for instrument in self.instruments:
            # duck-typed: only SensorMixin subclasses declare pollutants
            for pollutant in getattr(instrument, "pollutants", ()) or ():
                self.pollutant_instruments[pollutant.upper()].append(instrument)
                self._declared_pollutants[pollutant.upper()] = pollutant

    def __repr__(self):
        cls = self.__class__.__name__
        config = json.dumps(self.config, indent=4)
        instruments = repr(self.instruments)
        return f'{cls}(SID="{self.SID}", config={config}, instruments={instruments})'

    def __str__(self):
        return f"{self.__class__.__name__}: {self.SID}"

    def read_data(
        self,
        instruments: _all_or_mult_strs = "all",
        group: instruments.GroupSelection = None,
        lvl: str | None = None,
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
        file_pattern: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Read data for the specified instruments and level.

        Parameters
        ----------
        instruments : str or list of str or 'all'
            The instrument(s) to read data from. If 'all', read data from all instruments.
            Default is 'all'.
        group : str | Mapping[str, str] | None
            The research group to read data from. A name applies to every
            instrument; a mapping of instrument name to group name sets it per
            instrument. Default None selects each instrument's group
            automatically, by time when the groups' archives cover different
            periods: a range crossing a ``group_dates`` boundary is read from
            each group in turn and concatenated (see
            :meth:`~uataq.instruments.Instrument.plan_reads`).
        lvl : str, optional
            The data level to read: ``'raw'``, ``'qaqc'``, ``'calibrated'`` or
            ``'final'``. ``'final'`` is the ready-to-share level, with the
            pipeline's default flags applied; the lower levels are for finer
            control. Which to use depends on how clean the data need to be for
            what you are doing, and on how much control you want over the
            QAQC. Default is None which reads the highest level available (per
            group, when the read is split across groups).
        time_range : TimeRange | TimeRangeTypes
            The time range to read data. Default is None which reads all available data.
        num_processes : int or 'max'
            The number of processes to use for reading data. Default is 1.
        file_pattern : str, optional
            The file pattern to use for filtering files. Default is None.

        Returns
        -------
        dict[str, pandas.DataFrame]
            A dictionary containing the data for each instrument.

        Raises
        ------
        uataq.errors.ReaderError
            If no data is found for the specified instruments. The message
            says, for each, why it gave none: the files it looked for, and the
            first and last period it has files for, or the levels it has when
            it has none at ``lvl``.
        """
        # Format instruments
        if instruments == "all":
            instruments = self.instruments.names
        elif isinstance(instruments, str):
            instruments = [instruments.lower()]
        else:  # list, tuple or set
            instruments = [i.lower() for i in instruments]

        # Read data for each instrument and store in dictionary
        data = {}
        notes = []  # what became of each instrument that gave no data
        # Several instruments can read the same file (horel's finalized CSVs
        # hold a whole platform): parse each once in this call
        with _parse_once():
            for name in instruments:
                if name not in self.instruments:
                    raise errors.InstrumentNotFoundError(name, self.instruments)

                instrument = self.instruments[name]

                # Each instrument plans its own reads: the site's instruments are
                # not all operated by the same research group, and one group's
                # archive may cover only part of the range (config group_dates).
                try:
                    plan = instrument.plan_reads(group, time_range)
                except errors.InvalidGroupError:
                    raise
                except errors.ReaderError as e:
                    # Inactive in the range, or no group's archive covers it
                    _logger.warning(f"Not reading {instrument}: {e}")
                    notes.append(f"{name} not read: {str(e).rstrip('.')}")
                    continue

                try:
                    data[name] = _read_plan(
                        instrument, plan, lvl, num_processes, file_pattern
                    )
                except errors.ReaderError as e:
                    _logger.warning(
                        f"Error reading {instrument} data from {_describe_plan(plan)}: {e}"
                    )
                    notes.append(
                        f"{name} in {_describe_plan(plan)}: {str(e).rstrip('.')}"
                    )

        if not data:
            raise _no_data(f"{instruments}", lvl, self.SID, "; ".join(notes))

        return data

    def get_obs(
        self,
        pollutants: _all_or_mult_strs = "all",
        format: Literal["wide"] | Literal["long"] = "wide",
        group: instruments.GroupSelection = None,
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Get observations for each pollutant, combining instruments by pollutants.

        Parameters
        ----------
        pollutants : str or list of str, optional
            pollutants to read. If 'all', read all pollutants. Default is 'all'.
        format : str, optional
            Format of the data to return. Default is 'wide'.
        group : str | Mapping[str, str] | None
            The research group to read data from. A name applies to every
            instrument; a mapping of instrument name to group name sets it per
            instrument. Default None selects each instrument's group
            automatically (see :meth:`~uataq.instruments.Instrument.resolve_group`).
        time_range : TimeRange | TimeRangeTypes
            The time range to read data. Default is None which reads all available data.
        num_processes : int, optional
            Number of processes to use for reading data. Default is 1.

        Returns
        -------
        pandas.DataFrame
            One dataframe indexed by ``Time_UTC``, with the final-level rows of every
            instrument that measures the requested pollutants, sorted by time.
            The ``wide`` format has a column for each of their measurement columns
            (``CO2d_ppm_cal``, ``O3_ppb`` and so on); the ``long`` format has a
            ``pollutant`` column (those names) and a ``value`` column.
            The wide columns come instrument by instrument, in the order the
            ``pollutants`` were asked for (a set is sorted; ``'all'`` follows
            the site's config), and the same on every call. Rows on one
            timestamp come in that order too.

        Raises
        ------
        ValueError
            If a pollutant is not measured at the site. The message says
            which pollutants the site does measure, and tells a pollutant
            uataq reads at other sites (``Not measured at ...``) from a name
            it does not know (``Invalid pollutant(s)``).
        TypeError
            If you pass ``lvl`` or ``level``: ``get_obs`` always reads the
            ``final`` level. Use :func:`uataq.read_data` to read another.

        Warns
        -----
        EmptyResultWarning
            If the instruments have files for the range but no data in it, so
            the table has no rows. A range with no files raises
            :class:`~uataq.errors.ReaderError` instead.
        DroppedPollutantWarning
            If you name several pollutants and none of the instruments that
            measure one of them gave data (no files for the range, or not
            installed then), so the table leaves it out. It names the
            pollutants and the instruments. ``pollutants='all'`` does not warn,
            and when none of the pollutants has data the read raises
            :class:`~uataq.errors.ReaderError` instead.
        """
        _reject_level(kwargs)
        frames = self._read_obs(pollutants, format, group, time_range, num_processes)
        return pd.DataFrame(pd.concat(frames.values()).sort_index(kind="stable"))

    def _not_measured(self, asked: list[str]) -> ValueError:
        """
        Build the error for upper-case pollutant names this site does not measure.

        A name that no instrument model measures is invalid (a misspelling);
        one that some model measures, but not at this site, is not measured
        here. Either way the error says what the site does measure.
        """
        known = {p.upper(): p for p in POLLUTANTS}
        invalid = [p for p in asked if p not in known]
        absent = [known[p] for p in asked if p in known]
        measured = ", ".join(
            self._declared_pollutants.get(p, p) for p in sorted(self.pollutants)
        )
        sentences = []
        if invalid:
            sentences.append(f"Invalid pollutant(s): {', '.join(invalid)}")
        if absent:
            sentences.append(f"Not measured at {self.SID}: {', '.join(absent)}")
        sentences.append(f"{self.SID} measures {measured}")
        return ValueError(". ".join(sentences) + ".")

    def _read_obs(
        self,
        pollutants: _all_or_mult_strs,
        format: Literal["wide"] | Literal["long"],
        group: instruments.GroupSelection,
        time_range: TimeRange | TimeRangeTypes,
        num_processes: int | Literal["max"],
    ) -> dict[str, pd.DataFrame]:
        """
        Read the instruments measuring ``pollutants`` at the final level.

        Reshape each one's frame to ``format`` (see :meth:`get_obs`).
        Instruments are kept apart, keyed by name, so a caller can still tell
        which instrument (and so which group's clock) each row came from.
        """
        lvl = "final"

        if format not in ("wide", "long"):
            raise ValueError(f"Invalid format '{format}'. Must be 'wide' or 'long'.")

        everything = pollutants == "all"
        if everything:
            # In the config's order (self.pollutants is a set); the lookup is a
            # defaultdict, so skip a key that only a miss left behind
            pollutants = [p for p, found in self.pollutant_instruments.items() if found]
        elif isinstance(pollutants, str):
            pollutants = [pollutants.upper()]
        elif isinstance(pollutants, set):  # no order of its own: sort it
            pollutants = sorted(p.upper() for p in pollutants)
        else:  # list or tuple: keep the order asked for
            pollutants = [p.upper() for p in pollutants]

        unmeasured = [p for p in dict.fromkeys(pollutants) if p not in self.pollutants]
        if unmeasured:
            raise self._not_measured(unmeasured)

        # Get instruments for each pollutant: in the order the pollutants were
        # asked for, and each pollutant's in the config's. A list, not a set:
        # get_obs joins the instruments' columns in this order, and a set's
        # order changes with PYTHONHASHSEED (#74).
        instruments_to_read = list(
            dict.fromkeys(
                instrument.name
                for pollutant in pollutants
                for instrument in self.pollutant_instruments[pollutant]
            )
        )

        # Columns carry the declared case ("NOx_ppb"), not the uppercase request
        declared = [self._declared_pollutants.get(p, p) for p in pollutants]
        # Say which pollutants were asked for, not the instruments that measure them
        asked = "all pollutants" if everything else ", ".join(declared)

        # Read data
        try:
            data = self.read_data(
                instruments_to_read, group, lvl, time_range, num_processes
            )
        except errors.ReaderError as e:
            if not e.detail:  # not a read that found nothing
                raise
            raise _no_data(asked, lvl, self.SID, e.detail) from None

        # read_data logged each instrument it could not read and went on: a
        # pollutant with none of its instruments in data is left out of the table
        left_out = {  # the pollutant as declared: the names of its instruments
            name: [i.name for i in self.pollutant_instruments[pollutant]]
            for pollutant, name in zip(pollutants, declared, strict=True)
            if not any(i.name in data for i in self.pollutant_instruments[pollutant])
        }
        # Only for pollutants that were named: 'all' covers every pollutant the
        # site ever measured, and an instrument not installed in the range is
        # expected to give none
        if left_out and not everything:
            gave_none = dict.fromkeys(n for names in left_out.values() for n in names)
            warnings.warn(
                f"No {lvl} data found for {', '.join(left_out)} at {self.SID} "
                f"({TimeRange(time_range)}): {', '.join(gave_none)} gave none, "
                f"so the table leaves out {', '.join(left_out)}.",
                errors.DroppedPollutantWarning,
                stacklevel=3,  # the caller of get_obs
            )

        pattern = "|".join(declared)

        _logger.info("Combining data by pollutant...")
        frames = {name: _reshape_obs(df, pattern, format) for name, df in data.items()}

        if not any(len(frame) for frame in frames.values()):
            # An instrument with no files is not in data (read_data logged it
            # and went on), so each one here has files, and none has data in
            # the range
            warnings.warn(
                f"No {lvl} data found for {asked} at {self.SID} "
                f"({TimeRange(time_range)}): the files for {', '.join(data)} exist "
                "but hold no data in that range.",
                errors.EmptyResultWarning,
                stacklevel=3,  # the caller of get_obs
            )
        return frames

    def get_recent_obs(
        self,
        recent: str | dt.timedelta = dt.timedelta(days=10),
        pollutants: _all_or_mult_strs = "all",
        format: Literal["wide"] | Literal["long"] = "wide",
        group: instruments.GroupSelection = None,
    ) -> pd.DataFrame:
        """
        Get recent observations from site instruments.

        Parameters
        ----------
        recent : str or datetime.timedelta, optional
            Time range to get recent observations. Default is 10 days.
        pollutants : str or list of str, optional
            Pollutants to read. If 'all', read all pollutants. Default is 'all'.
        format : str, optional
            Format of the data to return. Default is 'wide'.
        group : str, optional
            Research group to read data from. Defaults to None which uses the default group.

        Returns
        -------
        pandas.DataFrame
            A dataframe containing recent observations from site instruments.

        Warns
        -----
        EmptyResultWarning
            If nothing in the files falls in the range, so the table has no
            rows (see :meth:`get_obs`).
        DroppedPollutantWarning
            If you name several pollutants and one of them has no data in the
            range (see :meth:`get_obs`).
        """
        if isinstance(recent, str):
            recent = pd.to_timedelta(recent)
        start_time = dt.datetime.now(dt.UTC).replace(tzinfo=None) - recent
        return self.get_obs(pollutants, format, group, [start_time, None])


class MobileSite(Site):
    """
    A class representing a mobile site where atmospheric measurements are taken.

    Parameters
    ----------
    SID : str
        The site identifier.
    config : dict
        A dictionary containing configuration information for the site:

        .. code-block:: python

            {
                ...
                is_mobile: True,
                instruments: {
                    instrument: {...}
                }
                ...
            }
    """

    _pilot_sites = ["trx01", "trx02"]

    @staticmethod
    def merge_gps(
        obs: pd.DataFrame,
        gps: pd.DataFrame,
        on: str | None = None,
        obs_on: str | None = None,
        gps_on: str | None = None,
    ) -> pd.DataFrame:
        """
        Merge observation data with location data from GPS.

        Parameters
        ----------
        obs (pd.DataFrame): The observation data.
        gps (pd.DataFrame): The GPS location data.
        on (str, optional): The column name to merge on. Defaults to 'Time_UTC'.
        obs_on (str, optional): The column name in the observation data to merge on. If not specified, it will use the value of 'on'.
        gps_on (str, optional): The column name in the GPS data to merge on. If not specified, it will use the value of 'on'.

        Returns
        -------
        pd.DataFrame: The merged data with added location information.

        Notes
        -----
        Both times are floored to whole seconds and the rows joined where the
        seconds match, so an observation with no fix in its second is dropped.
        When two fixes fall in the same second, the observation keeps the one
        nearest to it in time (the first on a tie), so no observation appears
        twice.
        """

        def truncate(time):
            """Floor to whole seconds so the two records' timestamps line up."""
            return time.dt.floor("s")

        _logger.info("Merging obs data with location data from gps...")

        # Reset datetime index
        obs = obs.reset_index()
        gps = gps.reset_index()

        # Merge on Time_UTC by default unless specified
        if on is None:
            on = "Time_UTC"
        obs_on = obs_on or on
        gps_on = gps_on or on

        # Convert to datetime
        obs[obs_on] = pd.to_datetime(obs[obs_on], errors="coerce")
        gps[gps_on] = pd.to_datetime(gps[gps_on], errors="coerce")

        # Drop rows with missing obs, time, or location
        obs = obs.dropna(how="all")
        gps = gps.dropna(subset=[gps_on, "Latitude_deg", "Longitude_deg"])

        # Number the observations and keep both exact times, to choose
        # between two fixes that fall in one second
        obs["_obs_row"] = np.arange(len(obs))
        obs["_obs_time"] = obs[obs_on]
        gps["_gps_time"] = gps[gps_on]

        # Truncate time to seconds
        obs[obs_on] = truncate(obs[obs_on])
        gps[gps_on] = truncate(gps[gps_on])

        # Perform merge
        obs = obs.merge(
            gps, how="inner", left_on=obs_on, right_on=gps_on, suffixes=("", "_gps")
        )

        # Two fixes can share a second (the Pi stamps fixes with jitter), and
        # each would copy the observation: keep the fix nearest to it in time
        # (the first on a tie), so each observation appears once (#93). The
        # merge keeps the observations' order; sorting by row restores it.
        gap = (obs["_obs_time"] - obs["_gps_time"]).abs()
        obs = (
            obs.assign(_gap=gap)
            .sort_values(["_obs_row", "_gap"], kind="stable")
            .drop_duplicates("_obs_row")
            .drop(columns=["_obs_row", "_obs_time", "_gps_time", "_gap"])
        )

        # Set Time_UTC as index
        obs = obs.set_index("Time_UTC")

        # Convert to geodataframe
        obs = gpd.GeoDataFrame(
            obs,
            crs="EPSG:4326",
            geometry=gpd.points_from_xy(obs.Longitude_deg, obs.Latitude_deg),
        )

        return obs

    def get_obs(
        self,
        pollutants: _all_or_mult_strs = "all",
        format: Literal["wide"] | Literal["long"] = "wide",
        group: instruments.GroupSelection = None,
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
        include_gps: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Get mobile site observations for each pollutant.

        Combines instruments by pollutant and, optionally, merges location data
        from GPS.

        Parameters
        ----------
        pollutants : str or list of str, optional
            pollutants to read. If 'all', read all pollutants. Default is 'all'.
        format : str, optional
            Format of the data to return. Default is 'wide'.
        group : str | Mapping[str, str] | None
            The research group to read data from. A name applies to every
            instrument; a mapping of instrument name to group name sets it per
            instrument. Default None selects each instrument's group
            automatically (see :meth:`~uataq.instruments.Instrument.resolve_group`).
        time_range : TimeRange | TimeRangeTypes, optional
            Time range to read data. Default is None.
        num_processes : int, optional
            Number of processes to use for reading data. Default is 1.
        include_gps : bool, optional
            Whether to include GPS data in the returned dataframe. Default is True.

        Returns
        -------
        pandas.DataFrame
            A dataframe containing mobile site observations for each pollutant
            with location data merged (a GeoDataFrame when ``include_gps``).
            The ``instrument`` column names the instrument each row came from
            (``lgr_ugga`` or ``lgr_ugga_manual_cal`` for TRX01's CO2 and CH4,
            whose ``_cal`` and ``_raw`` columns mean different things in
            each), as in :func:`~uataq.get_network_obs`. Otherwise the columns
            are those of :meth:`Site.get_obs`, then the GPS columns.

        Raises
        ------
        ValueError
            If a pollutant is not measured at the site (see :meth:`Site.get_obs`).
        TypeError
            If you pass ``lvl`` or ``level``: ``get_obs`` always reads the
            ``final`` level (see :meth:`Site.get_obs`).

        Warns
        -----
        EmptyResultWarning
            If the instruments' files hold no data in the range (see
            :meth:`Site.get_obs`), or, with ``include_gps``, if they do but no
            row found a GPS fix (TRX01 has no lin GPS file for 2018-09 and
            2018-10, so its methane those months has no position).
        DroppedPollutantWarning
            If you name several pollutants and one of them has no data in the
            range (see :meth:`Site.get_obs`).

        Notes
        -----
        Each instrument's rows are located with the GPS logged on the same
        clock, which is the GPS of the group they were read from (see
        :meth:`locate`). With no group named, one call can read TRAX methane
        from lin and ozone from horel, so the result can mix both groups'
        GPS columns.
        """
        _reject_level(kwargs)
        frames = self._read_obs(pollutants, format, group, time_range, num_processes)
        # Name the instrument on every row, as get_network_obs does
        labeled = {
            name: frame.assign(instrument=name) for name, frame in frames.items()
        }
        if include_gps:
            obs = self.locate(labeled, group, time_range, "final", num_processes)
            read = {name: len(frame) for name, frame in frames.items() if len(frame)}
            if obs.empty and read:
                # Rows were read but none found a fix: a month without a GPS
                # file, whose neighbors' were read for the Pi clock's margin
                warnings.warn(
                    f"No final data located at {self.SID} ({TimeRange(time_range)}): "
                    + ", ".join(f"{n} rows of {name}" for name, n in read.items())
                    + " were read, but none found a GPS fix in its second. "
                    "get_obs(..., include_gps=False) returns them without a position.",
                    errors.EmptyResultWarning,
                    stacklevel=2,  # the caller of get_obs
                )
        else:
            obs = pd.DataFrame(pd.concat(labeled.values()).sort_index(kind="stable"))
        # The label goes after all the measurement columns, before the GPS ones
        measured = list(dict.fromkeys(c for frame in frames.values() for c in frame))
        rest = [c for c in obs.columns if c not in measured and c != "instrument"]
        return obs[[*measured, "instrument", *rest]]

    def locate(
        self,
        frames: Mapping[str, pd.DataFrame],
        group: instruments.GroupSelection = None,
        time_range: TimeRange | TimeRangeTypes = None,
        lvl: str | None = "final",
        num_processes: int | Literal["max"] = 1,
    ) -> gpd.GeoDataFrame:
        """
        Merge GPS locations onto instrument data, joining each row on its own clock.

        Parameters
        ----------
        frames : Mapping[str, pandas.DataFrame]
            Data per instrument name, indexed by ``Time_UTC``, as read with
            ``group`` and ``time_range`` (e.g. from
            :meth:`~uataq.sites.Site.read_data`).
        group : str | Mapping[str, str] | None
            The group selection the frames were read with. It is used to
            replay each instrument's read plan, so it must be the same one.
        time_range : TimeRange | TimeRangeTypes
            The time range the frames were read with.
        lvl : str or None, optional
            The GPS data level to read. Default 'final'; None reads the
            highest level available.
        num_processes : int or 'max', optional
            Number of processes to use for reading GPS data. Default is 1.

        Returns
        -------
        geopandas.GeoDataFrame
            The rows that found a location, indexed by ``Time_UTC`` (EPSG:4326).
            ``GPS_Group`` names the group whose GPS located each row, and so
            the clock its ``Time_UTC`` is on (lin: GPS time; horel: CR1000).

        Raises
        ------
        uataq.errors.ReaderError
            If no GPS data could be read for any of the rows.
        ValueError
            If rows would be located with another group's GPS.

        Notes
        -----
        A row is joined to the GPS of the group it was read from, since the
        two share a logger clock: lin instruments and lin's GPS are stamped
        by the Pi (joined on ``Pi_Time``), horel's by the CR1000 (joined on
        ``Time_UTC``; the instrument and GPS values share one record). The
        clocks disagree: on TRX01 the CR1000 ran 1-20 s ahead of GPS time on
        dates sampled 2019-2026, so joining horel rows to lin's GPS on the Pi
        clock placed them that many seconds along the track, and dropped rows
        with no lin GPS record at their second (uataq#42).

        The Pi's clock itself has been hours to days off GPS time (up to 5
        days on TRX01 in 2022-11), and a GPS read selects fixes by GPS time,
        so lin's GPS is read a week past the rows' range on each side: the
        fixes of rows near the ends are then read too (uataq#94). Rows are
        still selected by the Pi's clock, so a located row's ``Time_UTC`` (GPS
        time) can fall outside ``time_range`` by as much as the Pi was off.

        One group's rows are never located with another group's GPS. A GPS
        group the caller names explicitly (a mapping entry for ``gps``) that
        differs from the group some rows were read from raises ``ValueError``,
        as does a group that logs no GPS at this site.
        """
        # gps group -> [(obs group, rows, portion)]
        pieces: dict[str, list[tuple[str, pd.DataFrame, TimeRange]]] = defaultdict(list)
        for name, frame in frames.items():
            # Replay the instrument's read plan to tell which group each row
            # came from: read_data concatenates the portions.
            plan = self.instruments[name].plan_reads(group, time_range)
            for (obs_group, portion), rows in zip(
                plan, _split_by_plan(frame, plan), strict=True
            ):
                if rows.empty:
                    continue
                gps_group = self._gps_group(obs_group, group)
                pieces[gps_group].append((obs_group, rows, portion))

        located = []
        failures = []
        for gps_group, group_pieces in pieces.items():
            # Read GPS only where these rows were read, not the whole request
            span = _span([portion for _, _, portion in group_pieces])
            if gps_group == "lin":
                # The join is on the Pi's clock and the read on GPS time:
                # reach far enough for the fixes of rows near the ends
                span = _widen(span, _PI_CLOCK_MARGIN)
            try:
                gps = self.read_data("gps", gps_group, lvl, span, num_processes)["gps"]
            except errors.ReaderError as e:
                n_rows = sum(len(rows) for _, rows, _ in group_pieces)
                _logger.warning(
                    f"No {gps_group} GPS for {self.SID} ({span}); "
                    f"{n_rows} rows go unlocated: {e}"
                )
                failures.append(f"{gps_group}: {e}")
                continue
            for _, rows, _ in group_pieces:
                located.append(MobileSite._merge_on_clock(rows, gps, gps_group))

        if failures and not located:
            raise errors.ReaderError(
                f"No GPS data for {self.SID}: " + "; ".join(failures)
            )
        if not located:  # every frame was empty: nothing to locate
            empty = pd.concat(list(frames.values())) if frames else pd.DataFrame()
            return gpd.GeoDataFrame(
                empty, geometry=gpd.points_from_xy([], []), crs="EPSG:4326"
            )
        obs = located[0] if len(located) == 1 else pd.concat(located)
        # Instrument columns first, then GPS, whichever piece came first
        firsts = list(dict.fromkeys(c for f in frames.values() for c in f.columns))
        firsts = [c for c in firsts if c in obs.columns]
        obs = obs[firsts + [c for c in obs.columns if c not in firsts]]
        return gpd.GeoDataFrame(obs.sort_index(kind="stable"))

    def _gps_group(self, obs_group: str, group: instruments.GroupSelection) -> str:
        """
        Return the group whose GPS locates rows read from ``obs_group``.

        It is always that group itself, since only its GPS shares its logger
        clock.

        Raises
        ------
        ValueError
            If the caller named another group's GPS for these rows, or
            ``obs_group`` logs no GPS at this site. One group's rows are never
            located with another group's GPS.
        """
        gps = self.instruments["gps"]
        named = gps._named_group(group)
        if named is not None and named != obs_group:
            raise ValueError(
                f"group names {named} GPS for {self.SID}, but some rows were read "
                f"from {obs_group}. Each group's rows are located only with that "
                "group's own GPS, since their logger clocks differ: drop the "
                f"'gps' entry, or read those instruments from {named}."
            )
        if obs_group not in gps.groups:
            raise ValueError(
                f"{obs_group} logs no GPS at {self.SID}, so its rows can't be "
                "located: one group's rows are never located with another "
                "group's GPS."
            )
        return obs_group

    @staticmethod
    def _merge_on_clock(
        obs: pd.DataFrame, gps: pd.DataFrame, gps_group: str
    ) -> gpd.GeoDataFrame:
        """Merge one group's rows with that group's GPS on its logger's clock."""
        if gps_group == "lin":
            # Can't always trust the Pi's clock for lin mobile data, but lin's
            # instruments and GPS are both stamped by it, so Pi_Time connects
            # them; the GPS supplies Time_UTC.
            merged = MobileSite.merge_gps(obs.rename_axis("Pi_Time"), gps, on="Pi_Time")
            merged = merged.drop(columns=["Pi_Time"])
        elif gps_group == "horel":
            # horel's instruments and GPS are stamped by the same CR1000
            merged = MobileSite.merge_gps(
                obs.rename_axis("Time_UTC"), gps, on="Time_UTC"
            )
        else:
            raise ValueError(f"Invalid group '{gps_group}'. Must be 'lin' or 'horel'.")
        # Which GPS located the row, and so which clock its Time_UTC is on:
        # lin's GPS time, or horel's CR1000 clock (1-20 s ahead of GPS time)
        merged["GPS_Group"] = gps_group
        return gpd.GeoDataFrame(merged)

    @staticmethod
    def plot(obs, ax=None):
        """
        Plot mobile observations on a map.

        Requires the optional cartopy and matplotlib dependencies.

        .. warning::
           Incomplete -- it returns an axis without drawing the observations.
        """
        import cartopy.crs as ccrs  # optional plotting extra
        import matplotlib.pyplot as plt  # optional plotting extra

        # FIXME is this the best way to do this?
        obs["lon"] = obs.Longitude_deg.round(3)
        obs["lat"] = obs.Latitude_deg.round(3)

        # keep only most recent for each lat/lon

        if ax is None:
            fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})

        # ax.set_extent([SLV_bounds[0], SLV_bounds[2],
        #                SLV_bounds[1], SLV_bounds[3]], crs=ccrs.PlateCarree())

        return ax
