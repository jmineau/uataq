"""UATAQ

Read UATAQ data
"""

__version__ = "2025.11.0"
__author__ = "James Mineau"
__email__ = "jameskmineau@gmail.com"

import datetime as dt
import logging
from typing import Literal

import pandas as pd

# Best-practice for libraries: don't emit output unless the caller opts in.
logging.getLogger(__name__).addHandler(logging.NullHandler())

from . import filesystem, instruments, sites
from ._laboratory import Laboratory, get_site, laboratory
from .filesystem import DEFAULT_GROUP
from .network import Network
from .timerange import TimeRange, TimeRangeTypes

_all_or_mult_strs = Literal["all"] | str | list[str] | tuple[str, ...] | set[str]

#: UATAQ Laboratory object.
#:
#: Built from :doc:`UATAQ configuration <config>`.
laboratory: Laboratory


# sites = {SID: laboratory.get_site(SID)  # name conflict
#          for SID in laboratory.sites}  # how much time does this take?


def read_data(
    SID: str,
    instruments: _all_or_mult_strs = "all",
    group: str | None = None,
    lvl: str | None = None,
    time_range: TimeRange | TimeRangeTypes = None,
    num_processes: int | Literal["max"] = 1,
    file_pattern: str | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Read data from an instrument at a site.

    Parameters
    ----------
    SID : str
        The site ID.
    instruments : str | list[str] | tuple[str] | set[str] | 'all'
        The instrument(s) to read data from.
    group : str | None
        The group name.
    lvl : str | None
        The data level.
    time_range : str | list[Union[str, dt.datetime, None]] | tuple[Union[str, dt.datetime, None], Union[str, dt.datetime, None]] | slice | None
        The time range to read data. Default is None which reads all available data.
    num_processes : int | 'max'
        The number of processes to use. Default is 1.
    file_pattern : str | None
        A string pattern to filter the file paths.

    Returns
    -------
    dict[str, pd.DataFrame]
        The data.
    """
    site = get_site(SID)
    data = site.read_data(
        instruments, group, lvl, time_range, num_processes, file_pattern
    )

    return data


def get_obs(
    SID: str,
    pollutants: _all_or_mult_strs = "all",
    format: Literal["wide"] | Literal["long"] = "wide",
    group: str | None = None,
    time_range: TimeRange | TimeRangeTypes = None,
    num_processes: int | Literal["max"] = 1,
    **kwargs,
) -> pd.DataFrame:
    """
    Get observations from a site.

    Parameters
    ----------
    SID : str
        The site ID.
    pollutants : str | list[str] | tuple[str] | set[str] | 'all'
        The pollutant(s) to get observations for.
    format : 'wide' | 'long'
        The format of the data. Default is 'wide'.
    group : str | None
        The group name.
    time_range : str | list[Union[str, dt.datetime, None]] | tuple[Union[str, dt.datetime, None], Union[str, dt.datetime, None]] | slice | None
        The time range to get observations. Default is None which gets all available data.
    num_processes : int | 'max'
        The number of processes to use. Default is 1.
    kwargs
        Additional keyword arguments to pass to the site's `get_obs` method.

    Returns
    -------
    pd.DataFrame
        The observations.
    """
    site = get_site(SID)
    obs = site.get_obs(pollutants, format, group, time_range, num_processes, **kwargs)

    return obs


def get_recent_obs(
    SID,
    recent: str | dt.timedelta = dt.timedelta(days=10),
    pollutants: _all_or_mult_strs = "all",
    format: Literal["wide"] | Literal["long"] = "wide",
    group: str | None = None,
) -> pd.DataFrame:
    """
    Get recent observations from a site.

    Parameters
    ----------
    SID : str
        The site ID.
    recent : str | dt.timedelta
        The recent time range. Default is 10 days.
    pollutants : str | list[str] | tuple[str] | set[str] | 'all'
        The pollutant(s) to get observations for.
    format : 'wide' | 'long'
        The format of the data. Default is 'wide'.
    group : str | None
        The group name.

    Returns
    -------
    pd.DataFrame
        The recent observations.
    """
    site = get_site(SID)
    obs = site.get_recent_obs(recent, pollutants, format, group)

    return obs


def get_network_obs(
    sites: list[str] | tuple[str, ...],
    pollutant: str,
    time_range: TimeRange | TimeRangeTypes = None,
    group: str | None = None,
    num_processes: int | Literal["max"] = 1,
):
    """
    Get observations for a network of sites for a single pollutant.

    Convenience wrapper around Network.get_obs() that combines measurements
    from multiple sites (stationary and/or mobile) into a single GeoDataFrame.

    Parameters
    ----------
    sites : list[str] | tuple[str, ...]
        List of site identifiers to include in the network.
    pollutant : str
        The pollutant to retrieve observations for (e.g., 'CO2', 'O3', 'NO2').
    time_range : TimeRange | TimeRangeTypes, optional
        The time range to retrieve data for. Can be a TimeRange object,
        string, list, or None (all data). Default is None.
    group : str | None, optional
        The research group to read data from. If None, uses the default group.
        Default is None.
    num_processes : int | Literal["max"], optional
        Number of processes to use for parallel data reading. Default is 1.

    Returns
    -------
    geopandas.GeoDataFrame
        A GeoDataFrame with the following structure:
        - Index: Time_UTC (datetime)
        - Columns: SID, [pollutant columns], Latitude_deg, Longitude_deg, zagl, geometry
        - CRS: EPSG:4326

    Examples
    --------
    >>> # Get CO2 from multiple sites for January 2024
    >>> obs = uataq.get_network_obs(
    ...     sites=['WBB', 'SUG', 'RPK'],
    ...     pollutant='CO2',
    ...     time_range='2024-01'
    ... )
    >>> print(obs)

    >>> # Get O3 from mobile sites for a time range
    >>> obs = uataq.get_network_obs(
    ...     sites=['TRX01', 'TRX02'],
    ...     pollutant='O3',
    ...     time_range=['2024-01-01', '2024-01-31']
    ... )
    """
    net = Network(sites=sites, pollutant=pollutant, group=group)
    return net.get_obs(time_range=time_range, num_processes=num_processes)


__all__ = [
    "sites",
    "instruments",
    "laboratory",
    "filesystem",
    "DEFAULT_GROUP",
    "get_site",
    "read_data",
    "get_obs",
    "get_recent_obs",
    "Network",
    "get_network_obs",
]
