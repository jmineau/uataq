"""
Classes and functions for working in the CHPC UATAQ filesystem.
"""

import logging
import multiprocessing
import os
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

import pandas as pd

import uataq.errors as errors
from uataq.timerange import TimeRange

_logger = logging.getLogger(__name__)

HOME: str = "/uufs/chpc.utah.edu/common/home"


lvls: dict = {"raw": 1, "qaqc": 2, "calibrated": 3, "final": 4}


def cpu_count() -> int:
    """
    Return the number of CPUs this process may run on.

    Unlike :func:`multiprocessing.cpu_count`, which reports every core on the
    machine, this respects the CPU affinity a scheduler sets: a SLURM job
    given 16 cores on a 64-core node gets 16, not 64.

    Returns
    -------
    int
        The usable CPU count.
    """
    if hasattr(os, "sched_getaffinity"):  # Linux
        return len(os.sched_getaffinity(0))
    return multiprocessing.cpu_count()


def _relpath(path: str, start: str) -> str:
    """
    Return ``path`` relative to ``start``, for log messages.

    Return ``path`` itself when there is no relative path (on Windows, when the
    two are on different drives).
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


def list_files(
    path: str | Path = ".",
    pattern: str | None = None,
    ignore_case: bool = False,
    all_files: bool = False,
    full_names: bool = False,
    recursive: bool = False,
    followlinks: bool = False,
) -> list[str]:
    """
    Return a list of files in the specified directory that match the specified pattern.

    Parameters
    ----------
    path : str, optional
        The directory to search for files. Defaults to the current directory.
    pattern : str, optional
        The glob-style pattern to match against file names. Defaults to None, which matches all files.
    ignore_case : bool, optional
        Whether to ignore case when matching file names. Defaults to False.
    all_files : bool, optional
        Whether to include hidden files (files that start with a dot). Defaults to False.
    full_names : bool, optional
        Whether to return the full path of each file. Defaults to False.
    recursive : bool, optional
        Whether to search for files recursively in subdirectories. Defaults to False.
    followlinks : bool, optional
        Whether to follow symbolic links. Defaults to False.

    Returns
    -------
    List[str]
        A list of file names or full paths that match the specified pattern.
    """
    import fnmatch

    result = []
    if recursive:
        walk = os.walk(path, followlinks=followlinks)
    else:
        # Files only, as os.walk lists them: a folder named like a data file
        # (2024_02_final.dat/) is not one (#206). A missing path raises
        # FileNotFoundError, which callers rely on.
        with os.scandir(path) as entries:
            walk = [(path, None, [e.name for e in entries if e.is_file()])]

    if ignore_case and pattern is not None:
        pattern = pattern.lower()

    for root, _, files in walk:
        for file in files:
            if all_files or not file.startswith("."):
                fn = file.lower() if ignore_case else file
                if pattern is None or fnmatch.fnmatch(fn, pattern):
                    if full_names:
                        result.append(os.path.abspath(os.path.join(root, file)))
                    else:
                        result.append(file)
    return result


class DataFile(metaclass=ABCMeta):
    """
    Abstract base class for data files.

    Attributes
    ----------
    path : str
        The file path.
    period : pd.Period
        The period of the data file.
    logger : str
        The logger name.
    date_slicer : slice
        A slice object to extract the date from the file name.
    file_freq : str
        The file frequency.
    ext : str
        The file extension.

    Methods
    -------
    parse()
        Parse the data file.
    """

    logger: str
    date_slicer: slice
    file_freq: str
    ext: str

    def __init__(self, path: str):
        """
        Initialize the DataFile object.

        Determines the period of the data file from the file name.

        Parameters
        ----------
        path : str
            The file path.
        """
        self.path = path

        # Get date from file name
        fname = os.path.basename(path)
        date_str = fname[self.date_slicer].replace("_", "-")
        self.period = pd.Period(date_str, freq=self.file_freq)

    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.path})"

    @abstractmethod
    def parse(self) -> pd.DataFrame:
        """
        Parse the data file. Must be implemented by subclasses.
        """
        raise NotImplementedError


def _describe_periods(files: list[DataFile]) -> str:
    """
    Say which periods the files cover, for an error message.

    The first and last period, and "with gaps" when a period between them has
    no file. It reads each file's period, which the file name already gave.
    """
    periods = sorted({file.period for file in files})
    if not periods:
        return "there are no files"
    first, last = periods[0], periods[-1]
    if first == last:
        return f"the only file is from {first}"
    covered = f"files run from {first} to {last}"
    if len(periods) < last.ordinal - first.ordinal + 1:
        covered += ", with gaps"
    return covered


def filter_datafiles(
    files: list[DataFile], time_range: TimeRange, pattern: str | None = None
) -> list[DataFile]:
    """
    Filter a list of files by a given time range.

    Parameters
    ----------
    files : list
        A list of DataFile objects.
    time_range : TimeRange
        A TimeRange object representing the time range to filter by.
    pattern : str, optional
        A string pattern to filter the file paths. Defaults to None.

    Returns
    -------
    list[DataFile]
        A list of DataFile objects that match the given time range.

    Raises
    ------
    ReaderError
        If no file is in the time range. The message gives the first and last
        period the files cover.
    """
    _logger.info(f"Filtering files to time range: {time_range}")

    # Filter by pattern
    if pattern:
        files = [file for file in files if pattern in file.path]

    df = pd.DataFrame(
        {
            "file": files,
            "period": [file.period for file in files],
        }
    )
    df = df.set_index("period").sort_index(kind="stable")

    # Filter by time range
    filtered_files = df.loc[time_range.start : time_range.stop, "file"].tolist()

    # Drop the files that start at the end of the time range, which is
    # exclusive. A period can have more than one file (horel's
    # prior405upgrade files), so drop each, not only the last.
    filtered_files = [
        file for file in filtered_files if file.period.start_time != time_range.stop
    ]

    if len(filtered_files) == 0:
        raise errors.ReaderError(
            "No files found within the specified time range "
            f"({_describe_periods(files)})."
        )

    return filtered_files


#: The files parsed so far in the current ``Site.read_data`` call, by path;
#: None outside one (see :func:`_parse_once`).
_parsed_files: ContextVar[dict[str, pd.DataFrame] | None] = ContextVar(
    "_parsed_files", default=None
)


@contextmanager
def _parse_once() -> Iterator[None]:
    """
    Share the files parsed inside the block, by path.

    Several instruments can read the same file (each of horel's finalized
    CSVs holds a whole platform). Inside the block, a ``DataFile`` that reads
    such a file keeps its parse in :data:`_parsed_files` for the next
    instrument. The dict is dropped when the block ends, so nothing outlives
    the read. ``Site.read_data`` wraps its loop over instruments in it.
    """
    token = _parsed_files.set({})
    try:
        yield
    finally:
        _parsed_files.reset(token)


def _forget_parsed_files() -> None:
    """
    Turn :data:`_parsed_files` off in a pool worker.

    A forked worker inherits a copy of the parent's dict, but what it adds
    never reaches the parent, so it would only hold memory until the pool
    closes.
    """
    _parsed_files.set(None)


def _parse_datafile(
    datafile: DataFile,
) -> tuple[pd.DataFrame | None, str | None, list[tuple[type[Warning], str]]]:
    """
    Private function to parse a single data file.

    Parameters
    ----------
    datafile : DataFile
        A DataFile object.

    Returns
    -------
    tuple
        The parsed DataFrame (None when the file could not be parsed), the
        reason it could not be (else None), and the warnings the parse raised
        as ``(category, message)`` pairs. A pool worker's warnings never reach
        the caller's filters, so the caller issues them again.
    """
    reason = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            data = datafile.parse()
        except (errors.ParserError, OSError, EOFError) as e:
            # OSError and EOFError: a file that cannot be opened or was cut off
            # mid-write (a .csv.gz being rewritten) is skipped too (#206)
            _logger.warning(f"Error parsing {datafile}: {e}")
            data = None
            reason = f"{datafile}: {e}"
    return data, reason, [(w.category, str(w.message)) for w in caught]


def _warn_repeated_times(
    files: list[DataFile], datasets: list[pd.DataFrame | None], data: pd.DataFrame
) -> None:
    """
    Warn when rows of the result share a time, and name the files that hold them.

    Two monthly files that overlap, or rows repeated inside one file, put each
    such row in the table twice. The data are not changed.
    """
    repeated = data.index[data.index.duplicated()]
    if repeated.empty:
        return
    times = repeated.unique()
    holding = [
        str(file)
        for file, frame in zip(files, datasets, strict=True)
        if frame is not None and frame["Time_UTC"].isin(times).any()
    ]
    named = ", ".join(holding[:3]) + (
        f" and {len(holding) - 3} more" if len(holding) > 3 else ""
    )
    warnings.warn(
        f"{len(repeated)} rows repeat the Time_UTC of an earlier row (the first "
        f"is {times[0]}), so they appear more than once in the table. They are "
        f"in: {named}. The files may overlap or repeat rows; the data are "
        "returned as read.",
        errors.DataFileWarning,
        stacklevel=2,
    )


def parse_datafiles(
    files: list[DataFile],
    time_range: TimeRange,
    num_processes: int | Literal["max"] = 1,
    driver: Literal["pandas"] | Literal["xarray"] = "pandas",
):
    """
    Read and parse data files, in parallel, using multiple processes.

    Parameters
    ----------
    files : list
        A list of DataFile objects.
    time_range : TimeRange
        A TimeRange object representing the time range to filter by.
    num_processes : int, optional
        The number of processes to use. Defaults to 1.
    driver : str, optional
        The data driver to use. Defaults to 'pandas'.

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing the parsed data.

    Raises
    ------
    ReaderError
        If none of the files could be parsed.
    """
    # Determine the number of processes to use
    cpus = cpu_count()
    if num_processes == "max":
        processes = cpus
    elif num_processes > cpus:
        _logger.debug(
            f"{num_processes} processes requested, "
            f"but there are only {cpus} CPU(s) available."
        )
        processes = cpus
    else:
        processes = num_processes

    if processes > len(files):
        _logger.debug(
            f"{num_processes} processes requested, "
            f"but there are only {len(files)} files to parse."
        )
        processes = len(files)

    # If only one process is requested, execute the function sequentially
    if processes == 1:
        _logger.debug("Parsing files sequentially...")
        results = [_parse_datafile(f) for f in files]
    else:
        _logger.debug(f"Parsing files in parallel with {processes} processes...")

        # The with block shuts the pool down even if a worker raises
        with multiprocessing.Pool(
            processes=processes, initializer=_forget_parsed_files
        ) as pool:
            results = pool.map(func=_parse_datafile, iterable=files)

    datasets = [data for data, _, _ in results]
    reasons = [reason for _, reason, _ in results if reason is not None]
    if driver == "pandas" and all(data is None for data in datasets):
        # ReaderError, not pd.concat's ValueError, so Site.read_data skips
        # this instrument instead of abandoning the whole site
        why = f": {reasons[0]}" if reasons else ""
        more = f" (and {len(reasons) - 1} more)" if len(reasons) > 1 else ""
        raise errors.ReaderError(
            f"None of the {len(files)} data file(s) could be parsed{why}{more}"
        )
    # Say what the parses said, and which files were skipped, in this process
    for _, reason, notes in results:
        for category, message in notes:
            warnings.warn(message, category, stacklevel=2)
        if reason is not None:
            warnings.warn(f"Skipped {reason}", errors.DataFileWarning, stacklevel=2)

    # Concatenate the datasets
    _logger.info("Concatenating datasets and reducing rows to time range...")
    if driver == "pandas":
        # a datafile that failed to parse contributes None
        data = pd.concat([d for d in datasets if d is not None])

        # Set time as index and filter to time_range
        data = (
            data.dropna(subset="Time_UTC")
            .set_index("Time_UTC")
            .sort_index(kind="stable")
        )
        data = data.loc[time_range.start : time_range.stop]
        if time_range.stop is not None:
            # .loc is inclusive, but time ranges are half-open [start, stop):
            # a sample exactly at stop belongs to the next range (#9)
            data = data[data.index < time_range.stop]
        _warn_repeated_times(files, datasets, data)
    elif driver == "xarray":
        # TODO
        raise NotImplementedError("xarray driver not implemented yet.")
    else:
        raise ValueError(f"Invalid driver: {driver}")

    return data


class GroupSpace(metaclass=ABCMeta):
    """
    Abstract base class for group spaces.

    Attributes
    ----------
    name : str
        The group name.
    datafiles : dict[str, Type[DataFile]]
        A dictionary of datafile keys and DataFile classes.

    Methods
    -------
    get_lvls(SID, instrument)
        Get the data levels a given site and instrument has.
    get_highest_lvl(SID, instrument)
        Get the highest data level for a given site and instrument.
    get_files(SID, instrument, lvl, logger)
        Get list of file paths for a given site, instrument, and level.
    get_datafile_key(instrument, lvl, logger)
        Get the datafile key based on the instrument, level, and logger.
    get_datafile_class(instrument, lvl, logger)
        Get the DataFile class based on the instrument, level, and logger.
    get_datafiles(SID, instrument, lvl, logger, time_range, pattern)
        Return a list of data files for a given level and time range.
    """

    name: str  # group name
    datafiles: dict[str, type[DataFile]]  # datafile key: DataFile class

    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def __str__(self):
        return f"{self.name.capitalize()} GroupSpace"

    @staticmethod
    @abstractmethod
    def get_lvls(SID: str, instrument: str) -> list[str]:
        """
        Get the data levels the group has for a given site and instrument.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name.

        Returns
        -------
        list[str]
            The levels, lowest first (the order of :data:`~uataq.filesystem.lvls`).
        """
        raise NotImplementedError

    @classmethod
    def get_highest_lvl(cls, SID: str, instrument: str) -> str:
        """
        Get the highest data level for a given site and instrument.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name.

        Returns
        -------
        str
            The highest data level.
        """
        return cls.get_lvls(SID, instrument)[-1]

    @abstractmethod
    def get_files(self, SID: str, instrument: str, lvl: str, logger: str) -> list[str]:
        """
        Get list of file paths for a given site, instrument, and level.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name.
        lvl : str
            The data level.
        logger : str
            The logger name.

        Returns
        -------
        list[str]
            A list of file paths.
        """
        raise NotImplementedError

    @abstractmethod
    def get_datafile_key(self, instrument: str, lvl: str, logger: str) -> str:
        """
        Get the datafile key based on the instrument, level, and logger.

        Parameters
        ----------
        instrument : str
            The instrument name.
        lvl : str
            The data level.
        logger : str
            The logger name.

        Returns
        -------
        str
            The datafile key.
        """
        raise NotImplementedError

    def get_datafile_class(
        self, instrument: str, lvl: str, logger: str
    ) -> type[DataFile]:
        """
        Get the DataFile class based on the instrument, level, and logger.

        Parameters
        ----------
        instrument : str
            The instrument name.
        lvl : str
            The data level.
        logger : str
            The logger name.

        Returns
        -------
        Type[DataFile]
            The DataFile class.
        """
        key = self.get_datafile_key(instrument, lvl, logger)
        DataFileClass = self.datafiles.get(key)
        if DataFileClass is None:
            raise ValueError(
                f"DataFile class not found for key: {key} in {self.name} group."
            )
        return DataFileClass

    def get_datafiles(
        self,
        SID: str,
        instrument: str,
        lvl: str,
        logger: str,
        time_range: TimeRange,
        pattern: str | None = None,
    ) -> list[DataFile]:
        """
        Return a list of data files for a given level and time range.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name.
        lvl : str
            The data level.
        logger : str
            The logger name.
        time_range : TimeRange
            The time range to filter by.
        pattern : str, optional
            A string pattern to filter the file paths. Defaults to None.

        Returns
        -------
        list[DataFile]
            A list of DataFile objects.
        """
        DataFileClass = self.get_datafile_class(instrument, lvl, logger)

        file_paths = self.get_files(SID, instrument, lvl, logger)

        # Initialize DataFile objects from file paths
        datafiles = []
        for path in file_paths:
            if path.endswith(DataFileClass.ext):
                try:
                    datafiles.append(DataFileClass(path))
                except errors.DataFileInitializationError as e:
                    _logger.warning(
                        f"Unable to initialize {DataFileClass.__name__} from {path}: {e}"
                    )
            continue

        return filter_datafiles(datafiles, time_range, pattern)

    @staticmethod
    @abstractmethod
    def standardize_data(instrument: str, data: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize the data across research groups.

        Rename columns, convert units, map values, etc. as needed.

        Parameters
        ----------
        instrument : str
            The instrument model.
        data : pd.DataFrame
            The data to standardize.

        Returns
        -------
        pd.DataFrame
            The standardized data.
        """
        raise NotImplementedError


groups: dict = {}
