"""
John Lin group - UUCON, TRAX, etc.

This module contains classes and functions for working with the Lin group data in the CHPC UATAQ filesystem.
"""

import datetime as dt
import io
import json
import logging
import os
import re
from copy import deepcopy

import numpy as np
import pandas as pd

import uataq.filesystem.core as filesystem
from uataq.errors import DataFileInitializationError, ParserError, ReaderError
from uataq.timerange import TimeRange

_logger = logging.getLogger(__name__)

# TODO: check for reprocessing

# The Lin group's measurements root. ``LINGROUP_MEASUREMENTS_DIR`` overrides the
# default, and is read each time a path is needed (not at import), so setting it
# after ``import uataq`` works. MEASUREMENTS_DIR, CONFIG_DIR and DATA_DIR are
# module attributes computed by ``__getattr__`` below, so they follow the
# variable; the annotations keep their documentation.
_MEASUREMENTS_ENV: str = "LINGROUP_MEASUREMENTS_DIR"
_DEFAULT_MEASUREMENTS_DIR: str = os.path.join(
    filesystem.HOME, "lin-group25", "measurements"
)


def _measurements_dir() -> str:
    """
    Return the measurements root: ``LINGROUP_MEASUREMENTS_DIR`` if set, else the default.

    Raise FileNotFoundError, naming the variable, when it is set to a path that is
    not a directory. The default is not checked: off-cluster it does not exist, and
    the readers say so when they need it.
    """
    path = os.environ.get(_MEASUREMENTS_ENV)
    if not path:
        return _DEFAULT_MEASUREMENTS_DIR
    if not os.path.isdir(path):
        raise FileNotFoundError(
            f"{_MEASUREMENTS_ENV} is set to '{path}', which is not a directory."
        )
    return path


def _config_dir() -> str:
    """Return the pipeline configuration directory under the measurements root."""
    return os.path.join(_measurements_dir(), "pipeline", "config")


def _data_dir() -> str:
    """Return the data directory under the measurements root."""
    return os.path.join(_measurements_dir(), "data")


MEASUREMENTS_DIR: str  #: Directory for Lin group measurements: ``LINGROUP_MEASUREMENTS_DIR`` if set, else the dedicated space.
CONFIG_DIR: str  #: Directory for Lin group pipeline configuration, ``pipeline/config`` under ``MEASUREMENTS_DIR``.
DATA_DIR: str  #: Directory for Lin group data, ``data`` under ``MEASUREMENTS_DIR``.

_DIRS = {
    "MEASUREMENTS_DIR": _measurements_dir,
    "CONFIG_DIR": _config_dir,
    "DATA_DIR": _data_dir,
}


def __getattr__(name: str) -> str:
    if name in _DIRS:
        return _DIRS[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *_DIRS])


#: Where the pipeline configuration is fetched from off-cluster.
CONFIG_URL: str = "https://raw.githubusercontent.com/uataq/data-pipeline/main/config"
#: Seconds to wait for each off-cluster fetch before giving up.
CONFIG_FETCH_TIMEOUT: float = 10


def _read_config(name: str) -> io.StringIO:
    """
    Read a pipeline config file from the config directory, or fetch it off-cluster.

    The fetch has a timeout, so a slow or missing network fails the import
    with a clear message instead of hanging it.
    """
    path = os.path.join(_config_dir(), name)
    if os.path.exists(path):
        with open(path) as f:
            return io.StringIO(f.read())

    import urllib.error
    import urllib.request

    url = f"{CONFIG_URL}/{name}"
    try:
        with urllib.request.urlopen(url, timeout=CONFIG_FETCH_TIMEOUT) as response:
            return io.StringIO(response.read().decode())
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(
            f"Could not read the lin pipeline config '{name}': it is not at "
            f"{path} (not on CHPC?) and fetching {url} failed: {e}"
        ) from e


#: Data configuration.
DATA_CONFIG: dict = json.load(_read_config("data_config.json"))
DATA_CONFIG["lgr_ugga_manual_cal"] = DATA_CONFIG[
    "lgr_ugga"
]  # manual cal has same format

#: Site configuration.
SITE_CONFIG = pd.read_csv(
    _read_config("site_config.csv"), skipinitialspace=True, index_col="stid"
)

#: Lin to UATAQ column mapping
column_mapping: dict[str, dict[str, str]] = {
    "2b_205": {
        "o3_ppb": "O3_ppb",
        "t_c": "Internal_T_C",
        "Cavity_T_C": "Internal_T_C",
        "p_hpa": "Internal_P_hPa",
        "Cavity_P_hPa": "Internal_P_hPa",
        "flow_ccpm": "Flow_mLpm",
        "Flow_CCmin": "Flow_mLpm",
    },
    "gps": {
        "inst_date": "Instrument_Date",
        "inst_time": "Instrument_Time",
        "fix_quality": "Fix_Quality",
        "n_sat": "N_Satellites",
        "N_Sat": "N_Satellites",
        "altitude_amsl": "Altitude_msl",
        "speed_kt": "Speed_kt",
        "true_course": "Course_deg",
        "status": "Status",
    },
    "licor_6262": {
        "RECORD": "Record",
        "batt_volt_Min": "Battery_Voltage_V",
        "PTemp_Avg": "Logger_T_C",
        "Panel_T_C": "Logger_T_C",
        "Room_T_Avg": "Ambient_T_C",
        "IRGA_T_Avg": "Instrument_T_C",
        "Cavity_T_C_IRGA": "Instrument_T_C",
        "IRGA_P_Avg": "Internal_P_kPa",
        "Cavity_P_kPa_IRGA": "Internal_P_kPa",
        "MF_Controller_mLmin_Avg": "Flow_mLpm",
        "Flow_mLmin": "Flow_mLpm",
        "PressureVolt_Avg": "Internal_P_mV",
        "Cavity_P_mV": "Internal_P_mV",
        "RH_voltage_Avg": "Internal_RH_mV",
        "Cavity_RH_mV": "Internal_RH_mV",
        "Gas_T_Avg": "Internal_T_C",
        "Cavity_T_C": "Internal_T_C",
        "rawCO2_Voltage_Avg": "Analog_CO2_ppm",
        "CO2_Analog_ppm": "Analog_CO2_ppm",
        "rawCO2_Avg": "CO2_ppm",
        "rawH2O_Avg": "Analog_H2O_ppth",
        "H2O_ppth_IRGA": "Analog_H2O_ppth",
        "Cavity_RH_pct": "Internal_RH_pct",
        "Cavity_P_Pa": "Analog_Internal_P_Pa",
    },
    "lgr_no2": {
        "inst_time": "Instrument_Time",
        "Pressure_torr": "Internal_P_torr",
        "Cavity_P_torr": "Internal_P_torr",
        # do i want to drop the -1
    },
    "lgr_ugga": {
        "GasP_torr": "Internal_P_torr",
        "Cavity_P_torr": "Internal_P_torr",
        "GasP_torr_sd": "Internal_P_torr_sd",
        "Cavity_P_torr_sd": "Internal_P_torr_sd",
        "GasT_C": "Internal_T_C",
        "Cavity_T_C": "Internal_T_C",
        "GasT_C_sd": "Internal_T_C_sd",
        "Cavity_T_C_sd": "Internal_T_C_sd",
        "AmbT_C": "Ambient_T_C",  # FIXME should this actually be called ambient??
        "AmbT_C_sd": "Ambient_T_C_sd",
        "RD0_us": "RingDown0_us",
        "RD0_us_sd": "RingDown0_us_sd",
        "RD1_us": "RingDown1_us",
        "RD1_us_sd": "RingDown1_us_sd",
    },
    "magee_ae33": {
        "bc1_ngm3": "BC1_ngm3",
        "bc2_ngm3": "BC2_ngm3",
        "bc3_ngm3": "BC3_ngm3",
        "bc4_ngm3": "BC4_ngm3",
        "bc5_ngm3": "BC5_ngm3",
        "bc6_ngm3": "BC6_ngm3",
        "bc7_ngm3": "BC7_ngm3",
        "flow_lpm": "Flow_Lpm",
        "Flow_Lmin": "Flow_Lpm",
    },
    "metone_es642": {
        "RECORD": "Record",
        "batt_volt_Min": "Battery_Voltage_V",
        "PTemp_Avg": "Logger_T_C",
        "PM_25_Avg": "PM2.5_ugm3",
        "pm25_mgm3": "PM2.5_mgm3",
        "Flow_Avg": "Flow_Lpm",
        "flow_lpm": "Flow_Lpm",
        "Flow_Lmin": "Flow_Lpm",
        "Temp_Avg": "Ambient_T_C",
        "t_c": "Ambient_T_C",
        "RH_Avg": "Internal_RH_pct",
        "rh_pct": "Internal_RH_pct",
        "Cavity_RH_pct": "Internal_RH_pct",
        "BP_Avg": "Ambient_P_hPa",
        "pres_hpa": "Ambient_P_hPa",
        "status": "Status",
        "checksum": "Checksum",
    },
    "teledyne_t200": {
        "nox_std_ppb": "NOx_ppb_std",
        "flow_ccm": "Flow_mLpm",
        "Flow_CCmin": "Flow_mLpm",
        "o3_flow_ccm": "O3_Flow_mLpm",
        "O3_Flow_CCmin": "O3_Flow_mLpm",
        "pmt_mv": "PMT_mV",
        "pmt_norm_mv": "PMT_Norm_mV",
        "azero_mv": "Azero_mV",
        "hvps_v": "HVPS_V",
        "rcell_t_c": "RCell_T_C",
        "RCel_T_C": "RCell_T_C",
        "box_t_c": "Instrument_T_C",
        "Box_T_C": "Instrument_T_C",
        "pmt_t_c": "PMT_T_C",
        "moly_t_c": "Moly_T_C",
        "rcel_pres_inhga": "RCell_P_inHgA",
        "RCel_Pres_inHgA": "RCell_P_inHgA",
        "samp_pres_inhga": "Internal_P_inHgA",
        "Samp_Pres_inHgA": "Internal_P_inHgA",
        "nox_slope": "NOx_Slope",
        "nox_offset_mv": "NOx_Offset_mV",
        "no_slope": "NO_Slope",
        "no_offset_mv": "NO_Offset_mV",
        "no2_ppb": "NO2_ppb",
        "nox_ppb": "NOx_ppb",
        "no_ppb": "NO_ppb",
        "test_mv": "Test_mV",
    },
    "teledyne_t300": {
        "co_std_ppb": "CO_ppb_std",
        "CO_std_ppb": "CO_ppb_std",
        "co_meas_mv": "CO_Meas_mV",
        "co_ref_mv": "CO_Ref_mV",
        "mr_ratio": "MR_Ratio",
        "samp_pres_inhga": "Internal_P_inHgA",
        "Samp_Pres_inHgA": "Internal_P_inHgA",
        "flow_ccm": "Flow_mLpm",
        "Flow_CCmin": "Flow_mLpm",
        "samp_t_c": "Internal_T_C",
        "Samp_T_C": "Internal_T_C",
        "bench_t_c": "Bench_T_C",
        "wheel_t_c": "Wheel_T_C",
        "pht_drive_mv": "PHT_Drive_mV",
        "slope": "Slope",
        "slope1": "Slope1",
        "slope2": "Slope2",
        "offset": "Offset",
        "offset1": "Offset1",
        "offset2": "Offset2",
        "co_ppb": "CO_ppb",
        "test_mv": "Test_mV",
    },
    "teledyne_t400": {
        "o3_std_ppb": "O3_ppb_std",
        "O3_std_ppb": "O3_ppb_std",
        "o3_meas_mv": "O3_Meas_mV",
        "o3_ref_mv": "O3_Ref_mV",
        "o3_gen_mv": "O3_Gen_mV",
        "o3_drive_mv": "O3_Drive_mV",
        "photo_power_mv": "Photo_Power_mV",
        "samp_pres_inhga": "Internal_P_inHgA",
        "Samp_Pres_inHgA": "Internal_P_inHgA",
        "flow_ccm": "Flow_mLpm",
        "Flow_CCmin": "Flow_mLpm",
        "samp_t_c": "Internal_T_C",
        "Samp_T_C": "Internal_T_C",
        "photo_lamp_t_c": "Photo_Lamp_T_C",
        "o3_scrub_t_c": "O3_Scrub_T_C",
        "o3_gen_t_c": "O3_Gen_T_C",
        "box_t_c": "Instrument_T_C",
        "Box_T_C": "Instrument_T_C",
        "slope": "Slope",
        "offset": "Offset",
        "o3_ppb": "O3_ppb",
        "test_mv": "Test_mV",
    },
    "teledyne_t500u": {
        "phase_t_c": "Phase_T_C",
        "bench_phase_s": "Bench_Phase_s",
        "meas_l_mm": "Measure_Loss_Mm",
        "Meas_L_mm": "Measure_Loss_Mm",
        "aref_l_mm": "ARef_Loss_Mm",
        "ARef_L_mm": "ARef_Loss_Mm",
        "samp_pres_inhga": "Internal_P_inHgA",
        "Samp_Pres_inHgA": "Internal_P_inHgA",
        "samp_temp_c": "Internal_T_C",
        "Samp_Temp_C": "Internal_T_C",
        "bench_t_c": "Bench_T_C",
        "box_t_c": "Instrument_T_C",
        "Box_T_C": "Instrument_T_C",
        "no2_slope": "NO2_Slope",
        "no2_offset_mv": "NO2_Offset_mV",
        "no2_ppb": "NO2_ppb",
        "no2_std_ppb": "NO2_ppb_std",
        "NO2_std_ppb": "NO2_ppb_std",
        "test_mv": "Test_mV",
    },
    "teom_1400ab": {
        "pm25_ugm3": "PM2.5_ugm3",
        "pm25_ugm3_30min": "PM2.5_ugm3_30min",
        "pm25_ugm3_1hr": "PM2.5_ugm3_1hr",
    },
}
column_mapping["licor_7000"] = column_mapping["licor_6262"]


def _read_lines(path: str, first: int = 0, last: bool = False) -> list[str]:
    """
    Read the first ``first`` lines of a file and, if ``last``, its final line.

    Replaces shelling out to ``head``/``tail``, which spawned a process per
    file and broke on paths with spaces. Line endings are stripped.
    """
    with open(path, "rb") as f:
        lines = [f.readline() for _ in range(first)]
        if last:
            # Read back from the end until the chunk holds a whole final line
            end = f.seek(0, os.SEEK_END)
            size = 4096
            while True:
                f.seek(max(end - size, 0))
                tail = f.read()
                # a trailing newline ends the last line, it doesn't start one
                body = tail[:-1] if tail.endswith(b"\n") else tail
                if b"\n" in body or size >= end:
                    lines.append(body.rsplit(b"\n", 1)[-1])
                    break
                size *= 4
    return [line.decode(errors="replace").rstrip("\r\n") for line in lines]


class LinDatFile(filesystem.DataFile):
    """
    A class for parsing Lin data files.

    Attributes
    ----------
    path : str
        The file path.
    period : pd.Period
        The period of the data file.
    logger : str
        The logger name.
    date_slicer : slice
        A slice object for extracting the date from the file name.
    file_freq : str
        The file frequency.
    ext : str
        The file extension.
    instrument : str
        The instrument name, read from the file path.
    lvl : str
        The data level, read from the file path.

    Methods
    -------
    parse()
        Parse the data file.
    """

    logger = "campbellsci"
    date_slicer = slice(7)
    file_freq = "M"
    ext = "dat"

    def __init__(self, path: str):
        super().__init__(path)

        # Get instrument name and lvl from file path
        self.instrument = self.get_instrument_name()
        self.lvl = self.get_lvl()

    def get_instrument_name(self) -> str:
        """
        Get the instrument name from the file path.

        Returns
        -------
        str
            The instrument name.
        """
        # Instrument name is the name of the directory two levels up from the file path
        return os.path.basename(os.path.dirname(os.path.dirname(self.path)))

    def get_lvl(self) -> str:
        """
        Get the data level from the file path.

        Returns
        -------
        str
            The data level.
        """
        # Data level is the name of the directory one level up from the file path
        return os.path.basename(os.path.dirname(self.path))

    def parse(self) -> pd.DataFrame:
        """
        Parse a Lin data file.

        Returns
        -------
        pd.DataFrame
            The parsed data.
        """
        _logger.debug(f"Parsing {filesystem._relpath(self.path, _data_dir())}")

        first_field = _read_lines(self.path, first=1)[0].split(",")[0]

        if first_field == "TIMESTAMP":
            # campbellsci files with their own header
            data = pd.read_csv(self.path, on_bad_lines="skip")
        else:
            # The pipeline's files have a header (Time_UTC, ...) and old
            # logger files none; either way the config names the columns.
            # Skip a header line instead of reading it in as a row, which
            # left every column object dtype.
            config = DATA_CONFIG[self.instrument][self.lvl]
            col_names = config["col_names"]
            has_header = pd.isna(pd.to_datetime(first_field, errors="coerce"))
            data = pd.read_csv(
                self.path,
                header=None,
                skiprows=1 if has_header else 0,
                on_bad_lines="skip",
            )
            data.columns = col_names
            # A stray text row would still leave a column object dtype
            numeric = [
                col
                for col, dtype in zip(col_names, config["col_types"], strict=False)
                if dtype == "d"
            ]
            data[numeric] = data[numeric].apply(pd.to_numeric, errors="coerce")

        # Format time col
        data = data.rename(columns={"TIMESTAMP": "Time_UTC"})
        data["Time_UTC"] = pd.to_datetime(
            data.Time_UTC, errors="coerce", format="ISO8601"
        )

        return data


def _day_in_range(day: dt.datetime, time_range: TimeRange) -> bool:
    """
    Return whether the day, given as its midnight, overlaps the time range.

    The range is ``[start, stop)`` with either end open: a day that ends at or
    before the start, or begins at or after the stop, does not overlap it.
    """
    start, stop = time_range.start, time_range.stop
    return not (
        (start is not None and day + dt.timedelta(days=1) <= start)
        or (stop is not None and day >= stop)
    )


class LGR_UGGA_File(filesystem.DataFile):
    """
    A class for parsing LGR UGGA data files.

    Attributes
    ----------
    path : str
        The file path.
    period : pd.Period
        The period of the data file.
    logger : str
        The logger name.
    serial : str
        The analyzer's serial number (``SN`` in the header).
    version : str
        The analyzer's software version (``VC`` in the header).
    meta : dict[str, str]
        The header's values by key: ``VC``, ``BD`` and ``SN``.
    file_freq : str
        The file frequency.
    ext : str
        The file extension.

    Methods
    -------
    get_meta(path)
        Get meta data from UGGA file.
    get_serial(path)
        Get serial number of UGGA from file.
    get_files(SID, instrument='lgr_ugga', lvl='raw', time_range=None)
        Get list of UGGA files for a given site.
    parse()
        Parse files transferred directly from LGR software.
    """

    logger = "lgr_ugga"
    file_freq = "D"
    ext = "txt"

    #: The two ways the LGR software has named its files, matched on the name
    #: itself rather than looked up by software version, so a new version that
    #: keeps either style needs no change: ``gga01Apr2014_f0000.txt`` (904M,
    #: WBB 2014-2016) and ``gga_2015-11-17_f0000.txt`` (2f90039, cf32204).
    name_date_formats = (
        (re.compile(r"^gga(\d{2}[A-Za-z]{3}\d{4})_"), "%d%b%Y"),
        (re.compile(r"^gga_(\d{4}-\d{2}-\d{2})_"), "%Y-%m-%d"),
    )

    def __init__(self, path: str):
        self.path = path
        self.meta = self.get_meta(path)
        self.serial = self.meta["SN"]
        self.version = self.meta["VC"]

        period = self._name_period(path)
        if period is None:
            raise DataFileInitializationError(
                f"No date in LGR file name {os.path.basename(path)} "
                f"(software {self.version})"
            )
        self.period = period

    @classmethod
    def _name_period(cls, path: str) -> pd.Period | None:
        """
        Return the day the file's name gives, or None if it gives none.

        It reads the name only, not the file, so files can be picked by date
        before their headers are read. A name whose date does not exist (a
        31 February) raises ``ValueError``.
        """
        fname = os.path.basename(path)
        for pattern, date_format in cls.name_date_formats:
            match = pattern.match(fname)
            if match:
                date = dt.datetime.strptime(match.group(1), date_format)
                return pd.Period(date, freq=cls.file_freq)
        return None

    @classmethod
    def _folder_day(cls, name: str) -> dt.datetime | None:
        """
        Return the midnight of the day a folder is named for, or None.

        The pipeline keeps each day's files in a folder named for the day, in
        the same two date styles as the file names (``01Apr2016`` and
        ``2017-05-09``). A name that does not read back exactly as written
        (``1Apr2016``) is not taken for a day's folder.
        """
        for _, date_format in cls.name_date_formats:
            try:
                day = dt.datetime.strptime(name, date_format)
            except ValueError:
                continue
            if day.strftime(date_format) == name:
                return day
        return None

    @staticmethod
    def get_meta(path) -> dict[str, str]:
        """
        Get meta data from UGGA file

        Parameters
        ----------
        path : str
            The path to the UGGA file.

        Returns
        -------
        dict[str, str]
            A dictionary containing the meta data.
        """
        pattern = (
            r"VC:(?P<VC>\w+)\s"
            r"BD:(?P<BD>[a-zA-Z]{3}\s\d{2}\s\d{4})\s"
            r"SN:(?P<SN>.+)"
        )

        header = _read_lines(path, first=1)[0]
        try:
            # no match -> AttributeError, caught below
            # pyrefly: ignore[missing-attribute]
            meta = re.match(pattern, header).groupdict()
        except AttributeError as e:
            raise DataFileInitializationError(
                f"Failed to read meta data from {path}"
            ) from e
        return meta

    @staticmethod
    def get_serial(path) -> str:
        """
        Get serial number of UGGA from file.

        Parameters
        ----------
        path : str
            The path to the UGGA file.

        Returns
        -------
        str
            The serial number.
        """
        return LGR_UGGA_File.get_meta(path)["SN"]

    @staticmethod
    def get_files(
        SID: str,
        instrument: str = "lgr_ugga",
        lvl: str = "raw",
        time_range: TimeRange | None = None,
    ) -> list[str]:
        """
        Get list of UGGA files for a given site.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name. Defaults to 'lgr_ugga'.
        lvl : str
            The data level. Defaults to 'raw'.
        time_range : TimeRange, optional
            Skip the folders of days that do not overlap this range. The
            pipeline keeps each day's files in a folder named for the day, so a
            read of one day lists a few of the thousands of folders a site has.
            A folder that is not named for a day is always listed. Defaults to
            None, which lists every folder.

        Returns
        -------
        list[str]
            A list of file paths.

        Raises
        ------
        ValueError
            If ``lvl`` is not ``"raw"``.
        """
        if lvl != "raw":
            raise ValueError("Only raw data is stored in UGGA files")
        data_path = LinGroup.data_path(SID, instrument, lvl)
        pattern = "*f????.txt"
        if time_range is None:
            return filesystem.list_files(
                data_path, pattern=pattern, full_names=True, recursive=True
            )

        # The files in the raw folder itself, then those in each folder that is
        # not the folder of a day outside the range. The name is read before
        # asking whether the entry is a folder: on the archive that is a stat
        # call per entry, thousands of them.
        files = filesystem.list_files(data_path, pattern=pattern, full_names=True)
        with os.scandir(data_path) as entries:
            for entry in entries:
                day = LGR_UGGA_File._folder_day(entry.name)
                if day is not None and not _day_in_range(day, time_range):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    files += filesystem.list_files(
                        entry.path, pattern=pattern, full_names=True, recursive=True
                    )
        return files

    def parse(self):
        """
        Parse files transferred directly from LGR software.

        Returns
        -------
        pd.DataFrame
            The parsed data.
        """
        _logger.debug(f"Parsing {filesystem._relpath(self.path, _data_dir())}")

        # Adapt column names depending on LGR software version.
        #  2013-2014 version has 23 columns
        #  2014+ version has 24 columns (MIU split into valve and description)
        #  77 columns when the software also wrote its fit diagnostics (ROO and
        #  HPL, 2015-11), between RD1_us_sd and Fit_Flag

        data_config = deepcopy(DATA_CONFIG["lgr_ugga"]["raw"])

        r2py_types = {"c": str, "d": float, "T": str}

        col_names = data_config["col_names"]
        col_types = data_config["col_types"]
        col_types = {
            name: r2py_types[t] for name, t in zip(col_names, col_types, strict=False)
        }

        _, cols, last_line = _read_lines(self.path, first=2, last=True)
        ndelim = cols.count(",")

        usecols = None  # every column
        if ndelim == 0:
            raise ParserError("No deliminators in header!")
        elif ndelim == 23:
            # col_names config has 23 columns, temporarily add fill column
            col_names.insert(22, "fillvalue")
            col_types["fillvalue"] = float
        elif ndelim != 22:
            # Another layout: the 21 measurement columns come first, Fit_Flag
            # is found by name, and the MIU description is last. Read with the
            # 23 names alone, pandas would take the extra leading fields for
            # an index and give the names to the wrong fields.
            header = [name.strip() for name in cols.split(",")]
            if "Fit_Flag" not in header:
                raise ParserError(f"Unknown LGR column layout ({ndelim + 1} columns)")
            usecols = [*range(21), header.index("Fit_Flag"), ndelim]

        # Leave out the last line when it is no complete row (an end-of-file
        # mark, or a row cut off by a power cut): it can end mid-number, which
        # would fail the float columns.
        source: str | io.BytesIO = self.path
        if last_line.count(",") < 22:
            with open(self.path, "rb") as f:
                text = f.read()
            body = text[:-1] if text.endswith(b"\n") else text
            source = io.BytesIO(text[: body.rfind(b"\n") + 1])

        # Read file assigning cols and dtypes
        data = pd.read_csv(
            source,
            header=1,
            names=col_names,
            usecols=usecols,
            dtype=col_types,
            on_bad_lines="skip",
            na_values=["TO", ""],
            skipinitialspace=True,
        )

        # Update columns now that data has been read in
        ncols = len(data.columns)
        if (ncols < 23) | (ncols > 24):
            raise ParserError("Too few or too many columns!")
        elif ncols == 24:
            #  drop the valve (fill) column, by position: the header does not
            #  name it consistently
            data = data.iloc[:, [i for i in range(ncols) if i != 22]]

        # Format time
        data.Time_UTC = pd.to_datetime(
            data.Time_UTC.str.strip(), format="%m/%d/%Y %H:%M:%S.%f", errors="coerce"
        )

        return data


# The start of an air-trend time, which the logger writes with isoformat()
_ISO_TIME_START = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


class AirTrendFile(filesystem.DataFile):
    """
    A class for parsing AirTrend data files.

    Attributes
    ----------
    path : str
        The file path.
    period : pd.Period
        The period of the data file.
    logger : str
        The logger name.
    date_slicer : slice
        A slice object for extracting the date from the file name.
    file_freq : str
        The file frequency.
    ext : str
        The file extension.
    config : dict
        The data configuration.

    Methods
    -------
    parse()
        Parse the data file.
    """

    logger = "air-trend"
    date_slicer = slice(10)
    file_freq = "D"
    ext = "csv"

    def __init__(self, path: str):
        # Store data config labels
        self.config = {}

        # instrument name is the name of the directory two levels up
        instrument_name = os.path.basename(os.path.dirname(os.path.dirname(path)))

        # Some instruments have special configurations indicated by their name
        # but use the same column structure as the default configuration
        # Example: lgr_ugga_manual_cal for trx01
        # Take the longest config name the directory starts with: the first
        # one in config order gave metone_es642 the layout of "met".
        matches = [key for key in DATA_CONFIG if instrument_name.startswith(key)]
        if not matches:
            raise DataFileInitializationError(
                f"Unknown instrument '{instrument_name}' for {path}"
            )
        self.config["instrument"] = max(matches, key=len)

        # Extract filename extension from custom air trend file handlers
        # This is necessary for instruments like the gps which have different types of files
        ext_match = re.match(
            r"\d{4}-\d{2}-\d{2}_?([^\s]+)?\.csv", os.path.basename(path)
        )
        if ext_match is None:
            raise DataFileInitializationError(
                f"Unexpected air-trend file name: {os.path.basename(path)}"
            )
        air_trend_ext = ext_match.group(1)
        self.config["lvl"] = (
            "air_trend" if air_trend_ext is None else f"air_trend_{air_trend_ext}"
        )

        super().__init__(path)

    def parse(self) -> pd.DataFrame:
        """
        Parse an AirTrend file.

        Returns
        -------
        pd.DataFrame
            The parsed data.
        """
        _logger.debug(f"Parsing {filesystem._relpath(self.path, _data_dir())}")

        data_config = DATA_CONFIG[self.config["instrument"]][self.config["lvl"]]

        col_names = data_config["col_names"]
        col_types = data_config["col_types"]

        # A few files have no header line and open with a data row; skipping
        # the first line would drop that row. The pipeline keeps every line
        # that holds a time, so it keeps the row.
        with open(self.path, "rb") as f:
            first_line = f.readline()
        has_header = _ISO_TIME_START.match(first_line) is None

        data = pd.read_csv(
            self.path,
            names=col_names,
            header=0 if has_header else None,
            na_values=["XXXX"],
            on_bad_lines="skip",
            low_memory=False,
        )

        # Format time. The logger writes isoformat(), which leaves out the
        # fraction when the microseconds are 0; without a format pandas infers
        # one from the first row, and a row of the other shape becomes NaT.
        data["time"] = pd.to_datetime(data.time, errors="coerce", format="ISO8601")
        data = data.rename(columns={"time": "Time_UTC"})

        # Coerce numeric columns
        numeric_cols = [
            col
            for col, dtype in zip(col_names, col_types, strict=False)
            if dtype == "d"
        ]
        data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric, errors="coerce")

        return data


class LinGroup(filesystem.GroupSpace):
    """
    A class representing the Lin group space in the CHPC UATAQ filesystem.

    Attributes
    ----------
    name : str
        The group name.
    datafiles : dict[str, Type[DataFile]]
        A dictionary mapping datafile keys to DataFile classes.
    data_config : dict
        The data configuration.

    Methods
    -------
    get_lvls(SID, instrument)
        Get the levels of data for a given site and instrument.
    get_highest_lvl(SID, instrument)
        Get the highest level of data for a given site and instrument.
    data_path(SID, instrument, lvl)
        Get the path to the data directory for a given site, instrument, and level.
    get_files(SID, instrument, lvl, logger)
        Get list of file paths for a given site, instrument, and level.
    get_datafile_key(instrument, lvl, logger)
        Get the datafile key based on the instrument, level, and logger.
    get_datafiles(SID, instrument, lvl, logger, time_range, pattern)
        Get list of data files for a given level and time range.
    """

    name = "lin"

    datafiles = {
        "data-pipeline": LinDatFile,
        "campbellsci": LinDatFile,
        "air-trend": AirTrendFile,
        "lgr_ugga": LGR_UGGA_File,
    }

    data_config = deepcopy(DATA_CONFIG)

    @property
    def data_dir(self) -> str:
        """The Lin group data directory, under ``LINGROUP_MEASUREMENTS_DIR`` when it is set."""
        return _data_dir()

    @staticmethod
    def get_lvls(SID: str, instrument: str) -> list[str]:
        """Return the levels with a folder on disk for the instrument, lowest first."""
        path = os.path.join(_data_dir(), SID.lower(), instrument)
        inst_lvls = [d for d in os.listdir(path) if d in filesystem.lvls]
        return sorted(inst_lvls, key=filesystem.lvls.__getitem__)

    @staticmethod
    def data_path(SID, instrument, lvl) -> str:
        """
        Get the path to the data directory for a given site, instrument, and level.

        Parameters
        ----------
        SID : str
            The site ID.
        instrument : str
            The instrument name.
        lvl : str
            The data level.

        Returns
        -------
        str
            The path to the data directory.
        """
        return os.path.join(_data_dir(), SID.lower(), instrument, lvl)

    def get_files(
        self, SID: str, instrument: str, lvl: str, logger: str = "campbellsci"
    ) -> list[str]:
        """
        List lin files for the instrument and level.

        See :meth:`~uataq.filesystem.core.GroupSpace.get_files`. Raw ``lgr_ugga`` files need their own
        handling because they sit in subdirectories alongside other files.
        """
        # Raw lgr_ugga files are stored subdirectories with other files
        if lvl == "raw" and logger == "lgr_ugga":
            return LGR_UGGA_File.get_files(SID, instrument, lvl)

        data_path = LinGroup.data_path(SID, instrument, lvl)
        return filesystem.list_files(data_path, full_names=True)

    def get_datafile_key(self, instrument: str, lvl: str, logger: str) -> str:
        """
        Return the data file key.

        The logger for raw files, otherwise the data pipeline's own format.
        """
        key = logger if lvl == "raw" else "data-pipeline"
        return key

    def get_datafiles(
        self,
        SID: str,
        instrument: str,
        lvl: str,
        logger: str,
        time_range: TimeRange,
        pattern: str | None = None,
    ) -> list[filesystem.DataFile]:
        """
        Return the lin data files overlapping the time range.

        See :meth:`~uataq.filesystem.core.GroupSpace.get_datafiles`. Raw files need extra handling:
        ``lgr_ugga`` file names do not line up with their contents, so the
        range is widened by a day on each side, only the day folders that
        overlap it are listed, and only the files whose name falls in it have
        their header read. GPS defaults to the ``gpgga`` sentence files.
        """
        # Custom handling for raw Lin files
        if lvl == "raw":
            if SID.startswith("TRX"):
                _logger.warning(
                    f"Time_UTC may not be accurate in raw lin data for mobile site {SID}."
                )
            if logger == "lgr_ugga":
                _logger.debug(
                    "Adding a day on either side of time range to ensure all data is included."
                )
                # Raw lgr_ugga files names dont necessarily match the period
                # Add a day on either side to ensure we get all the data
                # Construct new TimeRange to avoid modifing original range
                one_day = pd.Timedelta(days=1)
                start = time_range.start - one_day if time_range.start else None
                stop = time_range.stop + one_day if time_range.stop else None
                time_range = TimeRange(start=start, stop=stop)
                try:
                    return self._get_lgr_datafiles(SID, instrument, time_range, pattern)
                except ReaderError:
                    # No file in the range. The full listing below raises the
                    # same error, with the periods of every readable file in
                    # its message.
                    pass
            elif instrument == "gps":
                # Set default file pattern for raw lin gps data
                pattern = pattern or "gpgga"

        return super().get_datafiles(SID, instrument, lvl, logger, time_range, pattern)

    def _get_lgr_datafiles(
        self,
        SID: str,
        instrument: str,
        time_range: TimeRange,
        pattern: str | None = None,
    ) -> list[filesystem.DataFile]:
        """
        Return the raw LGR files in the time range, reading few headers.

        Initializing an :class:`LGR_UGGA_File` reads its header, and a site has
        a file a day for years: reading every header took minutes on a cold
        cache, and walking every day folder to list them took up to half a
        minute.
        So only the day folders that overlap the range are listed, the files
        are then picked by the day in their name, and only those are
        initialized. The same filter as the base class's runs on them, so the
        files kept are the ones it keeps. A file whose name has no valid date
        is initialized anyway, so it is handled as before.
        """
        datafiles: list[filesystem.DataFile] = []
        for path in LGR_UGGA_File.get_files(SID, instrument, "raw", time_range):
            try:
                day = LGR_UGGA_File._name_period(path)
            except ValueError:
                day = None
            if day is not None and not _day_in_range(day.start_time, time_range):
                continue
            try:
                datafiles.append(LGR_UGGA_File(path))
            except DataFileInitializationError as e:
                _logger.warning(f"Unable to initialize LGR_UGGA_File from {path}: {e}")

        return filesystem.filter_datafiles(datafiles, time_range, pattern)

    @staticmethod
    def standardize_data(instrument: str, data: pd.DataFrame) -> pd.DataFrame:
        """
        Rename lin columns to UATAQ names and apply per-instrument fixes.

        The fixes: GPS degree-minute coordinates, status flags, unit
        conversions. See :meth:`~uataq.filesystem.core.GroupSpace.standardize_data`.
        """
        mapping = column_mapping.get(instrument, {})

        ### Column specific manipulations ###
        # Drops and renames below edit the caller's `data` itself (`del`,
        # assigning `columns`), so a caller holding it sees the new names.

        if instrument == "gps":
            if "latitude_dm" in data.columns:
                # NMEA ddmm.mmmm to decimal degrees, vectorized: a row-wise
                # conversion took minutes on a month of 1 Hz data
                for dm, deg in [
                    ("latitude_dm", "Latitude_deg"),
                    ("longitude_dm", "Longitude_deg"),
                ]:
                    values = np.asarray(
                        pd.to_numeric(data[dm], errors="coerce"), dtype=float
                    )
                    data[deg] = values // 100 + (values % 100) / 60
                data["Latitude_deg"] *= np.where(data.n_s == "S", -1, 1)
                data["Longitude_deg"] *= np.where(data.e_w == "W", -1, 1)
                for col in ["latitude_dm", "longitude_dm", "n_s", "e_w"]:
                    del data[col]
            for status in ["status", "Status"]:
                # Map status to binary
                if status in data.columns:
                    data[status] = data[status].map({"A": 1, "V": 0})

        elif instrument == "2b_205":
            for flow in ["flow_ccpm", "Flow_CCmin"]:
                if flow in data.columns:
                    data[flow] = data[flow] / 1000
                    data.columns = [
                        "Flow_Lpm" if c == flow else c for c in data.columns
                    ]

        if "pm25_mgm3" in data.columns:
            data["pm25_mgm3"] = data.pm25_mgm3 * 1000
            data.columns = [
                "PM2.5_ugm3" if c == "pm25_mgm3" else c for c in data.columns
            ]

        return data.rename(columns=mapping)


filesystem.groups["lin"] = LinGroup()
