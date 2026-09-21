"""
SODAR wind profiles from the Horel group MesoWest archive.

Reads SODAR (SOnic Detection And Ranging) wind-profile data that the Horel
group archives as monthly HDF5 files under
``horel-group/oper/mesowest/sodar_data/hdf5archive``::

    {SID}_full_metadata_log.h5    station metadata + variable scale factors
    {SID}_{YYYY}_{MM}_sodar.h5    one month of profiles

The archive is located through the Horel group space
(:data:`uataq.filesystem.groupspaces.horel.MESOWEST_DIR`); pass
``mesowest_dir=...`` to read a copy elsewhere.

SODAR stations are MesoWest stations, not UATAQ sites, so they are not part of
the :doc:`configuration <config>` and are read directly with :class:`Sodar`
rather than through :func:`uataq.read_data`. Profiles are returned as an
:class:`xarray.Dataset` with dimensions ``(Time_UTC, level)``.

Examples
--------
>>> from uataq.sodar import Sodar
>>> sodar = Sodar("USDR1")
>>> data = sodar.read_data(time_range=["2019-01-01", "2019-01-31"])
>>> winds = Sodar.get_winds_at_height(data, height=100)
"""

import datetime as dt
import logging
import multiprocessing
import os
import re
from typing import Literal

import numpy as np
import pandas as pd
import tables
import xarray as xr

from uataq import errors
from uataq.filesystem.groupspaces import horel
from uataq.timerange import TimeRange, TimeRangeTypes

_logger = logging.getLogger(__name__)

#: Horel group NoData value in the SODAR archive.
NODATA: int = -9999

#: Metadata log file name suffix (``{SID}_full_metadata_log.h5``).
_METAFILE_SUFFIX = "_full_metadata_log.h5"


def _archive_dir(mesowest_dir: str | None = None) -> str:
    """Return the SODAR HDF5 archive directory below ``mesowest_dir``."""
    mesowest_dir = mesowest_dir or horel.MESOWEST_DIR
    return os.path.join(mesowest_dir, "sodar_data", "hdf5archive")


def list_stations(mesowest_dir: str | None = None) -> list[str]:
    """
    List the SODAR station IDs available in the archive.

    A station is available if it has a ``{SID}_full_metadata_log.h5`` file.

    Parameters
    ----------
    mesowest_dir : str, optional
        MesoWest data directory. Defaults to
        :data:`uataq.filesystem.groupspaces.horel.MESOWEST_DIR`.

    Returns
    -------
    list[str]
        Sorted station IDs.
    """
    archive_dir = _archive_dir(mesowest_dir)
    return sorted(
        f[: -len(_METAFILE_SUFFIX)]
        for f in os.listdir(archive_dir)
        if f.endswith(_METAFILE_SUFFIX)
    )


def _num_processes(num_processes: int | Literal["max"], n_files: int) -> int:
    """Number of worker processes to use: capped by CPUs and number of files."""
    cpu_count = multiprocessing.cpu_count()
    requested = cpu_count if num_processes == "max" else int(num_processes)
    if requested < 1:
        raise ValueError(f"num_processes must be >= 1 or 'max', got {num_processes!r}")
    return min(requested, cpu_count, n_files)


def _slice_time(data: xr.Dataset, time_range: TimeRange) -> xr.Dataset:
    """Subset to ``start <= Time_UTC < stop`` (uataq's half-open time range)."""
    times = data.indexes["Time_UTC"]
    keep = np.ones(len(times), dtype=bool)
    if time_range.start is not None:
        keep &= np.asarray(times >= pd.Timestamp(time_range.start))
    if time_range.stop is not None:
        keep &= np.asarray(times < pd.Timestamp(time_range.stop))
    return data.isel(Time_UTC=keep)


class Sodar:
    """
    Horel group SODAR wind profiler.

    Parameters
    ----------
    SID : str
        Station identifier, e.g. ``"USDR1"`` (case-insensitive).
    mesowest_dir : str, optional
        MesoWest data directory containing ``sodar_data/hdf5archive``.
        Defaults to :data:`uataq.filesystem.groupspaces.horel.MESOWEST_DIR`.

    Attributes
    ----------
    SID : str
        Upper-case station identifier.
    sodar_dir : str
        ``{mesowest_dir}/sodar_data``.
    archive_dir : str
        ``{mesowest_dir}/sodar_data/hdf5archive``.
    metafile : str
        Path to the station's metadata log.
    meta : pandas.DataFrame
        Station metadata log (location, name, changes).
    variables : pandas.DataFrame
        Variable metadata indexed by ``SHORTNAME``; the ``MULT`` column holds
        the integer scale factor applied in :meth:`parse`.

    Raises
    ------
    FileNotFoundError
        If the archive directory or the station's metadata log does not exist.
    """

    model = "sodar"
    species_measured = ("wind",)

    def __init__(self, SID: str, mesowest_dir: str | None = None):
        """Initialize the Sodar and read the station's metadata log."""
        self.SID = SID.upper()

        mesowest_dir = mesowest_dir or horel.MESOWEST_DIR
        self.archive_dir = _archive_dir(mesowest_dir)
        self.sodar_dir = os.path.dirname(self.archive_dir)
        if not os.path.isdir(self.archive_dir):
            raise FileNotFoundError(
                f"SODAR archive not found: {self.archive_dir}. "
                "Pass mesowest_dir=... to read a copy elsewhere."
            )

        self.metafile = os.path.join(self.archive_dir, f"{self.SID}{_METAFILE_SUFFIX}")
        if not os.path.isfile(self.metafile):
            raise FileNotFoundError(
                f"No SODAR metadata log for station '{self.SID}' ({self.metafile}). "
                f"Available stations: {list_stations(mesowest_dir)}"
            )
        self.meta = pd.read_hdf(self.metafile, key="metagroup/metadata")
        variables = pd.read_hdf(self.metafile, key="metagroup/variables")
        assert isinstance(variables, pd.DataFrame)
        self.variables = variables.set_index("SHORTNAME")

        # Monthly files are named {SID}_{YYYY}_{MM}_sodar.h5 (exact SID match)
        self._file_pattern = re.compile(
            rf"^{re.escape(self.SID)}_(?P<year>\d{{4}})_(?P<month>0[1-9]|1[0-2])_sodar\.h5$"
        )

    def __repr__(self) -> str:
        return f"Sodar('{self.SID}')"

    @staticmethod
    def _check_lvl(lvl: str) -> None:
        """Only raw SODAR data is archived."""
        if lvl != "raw":
            raise ValueError(
                f"Invalid SODAR data level '{lvl}'. Only 'raw' is available."
            )

    def get_files(
        self, lvl: str = "raw", time_range: TimeRange | TimeRangeTypes = None
    ) -> list[str]:
        """
        List archived SODAR HDF5 files for this station within a time range.

        Parameters
        ----------
        lvl : str, optional
            Processing level. Only ``'raw'`` is available.
        time_range : TimeRange | TimeRangeTypes, optional
            Keep files whose month overlaps ``[start, stop)``. Default is None
            which lists all files.

        Returns
        -------
        list[str]
            Matching file paths, sorted by month.
        """
        self._check_lvl(lvl)
        time_range = TimeRange(time_range)
        start, stop = time_range.start, time_range.stop

        files = []
        for name in sorted(os.listdir(self.archive_dir)):
            match = self._file_pattern.match(name)
            if match is None:
                # Other stations, metadata logs, partial files (e.g. *_sodar_p1.h5)
                continue
            year, month = int(match["year"]), int(match["month"])
            month_start = dt.datetime(year, month, 1)
            month_stop = dt.datetime(year + month // 12, month % 12 + 1, 1)
            # Keep months overlapping [start, stop)
            if start is not None and month_stop <= start:
                continue
            if stop is not None and month_start >= stop:
                continue
            files.append(os.path.join(self.archive_dir, name))
        return files

    @staticmethod
    def parse(file: str, variables: pd.DataFrame) -> xr.Dataset:
        """
        Parse a single SODAR HDF5 file into an xarray Dataset.

        NoData (``-9999``) becomes NaN and each variable listed in
        ``variables`` is divided by its ``MULT`` scale factor.

        Parameters
        ----------
        file : str
            Path to a ``{SID}_{YYYY}_{MM}_sodar.h5`` file.
        variables : pandas.DataFrame
            Variable metadata indexed by ``SHORTNAME`` with a ``MULT`` column
            (:attr:`Sodar.variables`).

        Returns
        -------
        xarray.Dataset
            ``STATION_ID`` on ``Time_UTC`` and one ``(Time_UTC, level)``
            variable per profile field (e.g. ``HEIGHT``, ``WD``, ``WS``).
        """
        _logger.debug(f"Parsing {file}")
        h5 = tables.open_file(file, mode="r")
        try:
            table = h5.get_node("/obsdata/observations")
            if not isinstance(table, tables.Table):
                raise errors.ParserError(
                    f"{file}: /obsdata/observations is not a table"
                )
            data = table.read()
        finally:
            h5.close()

        time = pd.to_datetime(data["DATTIM"], unit="s").as_unit("ns")
        profile_vars = [
            name
            for name in data.dtype.names or ()
            if name not in ("DATTIM", "STATION_ID")
        ]
        n_levels = data[profile_vars[0]].shape[1] if profile_vars else 0

        ds = xr.Dataset(
            data_vars={
                "STATION_ID": (["Time_UTC"], data["STATION_ID"]),
                **{var: (["Time_UTC", "level"], data[var]) for var in profile_vars},
            },
            coords={"Time_UTC": time, "level": np.arange(n_levels)},
        )

        ds = ds.where(ds != NODATA)

        for var in variables.index:
            # Variables added to the log later are absent from older files
            if var in ds:
                ds[var] = ds[var] / variables.loc[var, "MULT"]

        return ds

    def read_data(
        self,
        lvl: str = "raw",
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
    ) -> xr.Dataset:
        """
        Read and combine SODAR profiles over a time range.

        Parameters
        ----------
        lvl : str, optional
            Processing level. Only ``'raw'`` is available.
        time_range : TimeRange | TimeRangeTypes, optional
            Time range to read, ``start <= Time_UTC < stop`` (see
            :class:`uataq.timerange.TimeRange`). A date string as the stop
            includes that whole day. Default is None which reads all data.
        num_processes : int | 'max', optional
            Number of processes used to parse files. Default is 1.

        Returns
        -------
        xarray.Dataset
            Profiles with dimensions ``(Time_UTC, level)``, sorted by time.

        Raises
        ------
        FileNotFoundError
            If no files overlap ``time_range``.
        """
        time_range = TimeRange(time_range)
        files = self.get_files(lvl, time_range)
        if not files:
            raise FileNotFoundError(
                f"No {lvl} SODAR files for {self.SID} in {self.archive_dir} "
                f"overlapping {time_range}"
            )

        processes = _num_processes(num_processes, len(files))
        if processes > 1:
            _logger.debug(f"Parsing {len(files)} files with {processes} processes...")
            with multiprocessing.Pool(processes=processes) as pool:
                datasets = pool.starmap(
                    Sodar.parse, [(file, self.variables) for file in files]
                )
        else:
            datasets = [Sodar.parse(file, self.variables) for file in files]

        data = xr.concat(
            datasets,
            dim="Time_UTC",
            data_vars="all",
            coords="different",
            compat="equals",
            join="outer",  # pads with NaN if the number of levels changes
        ).sortby("Time_UTC")

        return _slice_time(data, time_range)

    @staticmethod
    def get_winds_at_height(data: xr.Dataset, height: float) -> pd.DataFrame:
        """
        Extract wind direction and speed at a given height.

        The level is matched against ``HEIGHT`` at every timestamp, so the
        result is correct even if the range gates change within ``data``.
        Timestamps without a level at ``height`` are dropped.

        Parameters
        ----------
        data : xarray.Dataset
            SODAR profiles from :meth:`read_data` or :meth:`parse`.
        height : float
            Height of the range gate, in the units of ``HEIGHT`` (m AGL).

        Returns
        -------
        pandas.DataFrame
            ``direction`` and ``speed`` columns indexed by ``Time_UTC``.

        Raises
        ------
        ValueError
            If no level is at ``height`` anywhere in ``data``.
        """
        is_height = data["HEIGHT"] == height
        has_height = is_height.any("level")
        if not bool(has_height.any()):
            heights = data["HEIGHT"].values
            available = np.unique(heights[np.isfinite(heights)]).tolist()
            raise ValueError(
                f"No SODAR level at height {height}. Available heights: {available}"
            )

        level = is_height.argmax("level")  # matching level at each time
        winds = (
            data[["WD", "WS"]]
            .isel(level=level)
            .where(has_height)
            .drop_vars("level", errors="ignore")
            .to_dataframe()
        )

        winds = winds.rename(columns={"WD": "direction", "WS": "speed"})
        return winds.dropna(how="all")
