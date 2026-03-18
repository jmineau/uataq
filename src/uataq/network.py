"""
This module provides classes for combining and analyzing data across multiple sites.
"""

import logging
from typing import Literal

import geopandas as gpd
import pandas as pd

from uataq import _laboratory, errors, sites
from uataq.timerange import TimeRange, TimeRangeTypes

_logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        sites: list[str] | tuple[str, ...],
        pollutant: str,
        group: str | None = None,
    ):
        """
        Initialize a Network object.

        Parameters
        ----------
        sites : list[str] | tuple[str, ...]
            List of site identifiers to include in the network.
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
        _logger.info(f"Reading {self.pollutant} data from {len(self.site_objects)} sites...")

        dataframes = []
        for site in self.site_objects:
            try:
                site_data = self._read_site_data(
                    site, time_range, num_processes
                )
                dataframes.append(site_data)
            except errors.ReaderError as e:
                _logger.warning(f"Error reading data from {site.SID}: {e}")

        if not dataframes:
            raise errors.ReaderError(
                f"No data found for {self.pollutant} in any site."
            )

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

        return gdf.sort_index()

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
                site_data = sites.MobileSite.merge_gps(
                    site_data, gps_data, on=merge_on
                )
                
                # Clean up Pi_Time column if it was used for merging
                if merge_on == "Pi_Time" and "Pi_Time" in site_data.columns:
                    site_data = site_data.drop(columns=["Pi_Time"])
                    
            except (errors.ReaderError, KeyError) as e:
                _logger.warning(f"Could not read GPS data for mobile site {site.SID}: {e}")
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
