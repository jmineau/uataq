"""
This module implements UATAQ instruments as classes.

Each instrument class is a subclass of the `Instrument` abstract base class and
implements methods for reading and parsing data files.

The `Instrument` class provides a common interface for all instrument classes
and defines abstract methods that must be implemented by each subclass.
"""

import json
import logging
from abc import ABCMeta
from collections.abc import Iterator, Mapping
from typing import Literal

import numpy as np
import pandas as pd

from uataq import errors, filesystem, gps
from uataq.timerange import TimeRange, TimeRangeTypes

#: How a caller picks a research group: a name, a per-instrument mapping, or
#: None for automatic selection. See :meth:`Instrument.resolve_group`.
GroupSelection = str | Mapping[str, str] | None

_logger = logging.getLogger(__name__)

# TODO
# TRX01 aeth & no2 from horel-group


class Instrument(metaclass=ABCMeta):
    """
    Abstract base class for instrument objects.

    Attributes
    ----------
    model : str
        Model of the instrument.
    SID : str
        Site ID where the instrument is installed.
    name : str
        Name of the instrument.
    groups : list[str]
        Research groups that operate the instrument.
    loggers : set[str]
        Loggers used by the research groups to record data.
    config : dict
        Configuration settings for the instrument.

    Methods
    -------
    get_files(group: str, lvl: str) -> list[str]
        Get list of file paths for a given level.
    read_data(group: str, lvl: str, time_range: TimeRange, num_processes: int, file_pattern: str) -> pd.DataFrame
        Read and parse group data files for the given level and time range using multiple processes.
    """

    model: str

    def __init__(self, SID: str, name: str, loggers: dict, config: dict):
        """
        Initialize the Instrument object.

        Parameters
        ----------
        SID : str
            Site ID where the instrument is installed.
        name : str
            Name of the instrument.
        loggers : dict
            Dictionary of loggers used by different research groups.
        config : dict
            Configuration settings for the instrument.
        """
        self.SID = SID
        self.name = name
        self._loggers = loggers
        self.config = config

        self.groups = list(loggers.keys())
        self.loggers = set(loggers.values())

    def __str__(self):
        return f"{self.name}@{self.SID}"

    def __repr__(self):
        name = f", name='{self.name}" if self.name != self.model else ""
        config = json.dumps(self.config, indent=4)
        return (
            f"{self.__class__.__name__}({self.SID}"
            f"{name}, loggers={self._loggers}, config={config})"
        )

    def resolve_group(self, group: GroupSelection = None) -> str:
        """
        Pick which research group's data to read this instrument from.

        Parameters
        ----------
        group : str | Mapping[str, str] | None
            A group name, used as given; a mapping of instrument name to group
            name, from which this instrument's entry is used (instruments the
            mapping does not name fall back to automatic selection); or None to
            select automatically.

        Returns
        -------
        str
            The group name.

        Raises
        ------
        InvalidGroupError
            If no registered groupspace operates this instrument.

        Notes
        -----
        Automatic selection reads the configured operators of *this*
        instrument: the default group when it is one of them, otherwise the
        sole operator, otherwise the first configured. It is a configuration
        lookup, not a search of the archive -- it does not check whether that
        group actually holds data for a given time range.
        """
        if isinstance(group, Mapping):
            group = group.get(self.name, group.get(self.name.lower()))
        if isinstance(group, str):
            return filesystem.get_group(group)

        candidates = [g for g in self.groups if g in filesystem.groups]
        if not candidates:
            raise errors.InvalidGroupError(
                f"No registered groupspace operates {self}. "
                f"Configured: {self.groups or 'none'}."
            )
        if filesystem.DEFAULT_GROUP in candidates:
            return filesystem.DEFAULT_GROUP
        selected: str = candidates[0]
        if len(candidates) > 1:
            _logger.info(
                f"{self} is operated by {candidates} and not by the default "
                f"group '{filesystem.DEFAULT_GROUP}'; reading from '{selected}'."
            )
        else:
            _logger.debug(f"{self} is operated by '{selected}'; reading from it.")
        return selected

    def _get_groupspace(self, group: str) -> filesystem.GroupSpace:
        """
        Get the groupspace object for the given group.

        Parameters
        ----------
        group : str
            The research group whose groupspace to retrieve.

        Returns
        -------
        GroupSpace
            The groupspace object.
        """
        if group not in filesystem.groups:
            raise errors.InvalidGroupError(
                f"{group} groupspace not found in filesystem"
            )
        elif group not in self.groups:
            raise errors.InvalidGroupError(f"{group} group invalid for {self}")
        return filesystem.groups[group]

    def get_highest_lvl(self, group: str) -> str:
        """
        Get the highest data level for the instrument.

        Parameters
        ----------
        group : str
            The research group whose data to retrieve.

        Returns
        -------
        str
            The highest data level.
        """
        _logger.info("No level specified. Determining highest level...")
        groupspace = self._get_groupspace(group)
        return groupspace.get_highest_lvl(self.SID, self.name)

    def get_files(self, group: str, lvl: str) -> list[str]:
        """
        Get list of file paths for a given level.

        Parameters
        ----------
        group : str
            The research group whose data to retrieve.
        lvl : str
            The level of the data to retrieve.

        Returns
        -------
        list[str]
            A list of file paths.
        """
        groupspace = self._get_groupspace(group)
        logger = self._loggers[group]
        return groupspace.get_files(self.SID, self.name, lvl, logger)

    def get_datafiles(
        self,
        group: str,
        lvl: str,
        time_range: TimeRange | TimeRangeTypes,
        pattern: str | None = None,
    ) -> list[filesystem.DataFile]:
        """
        Get data files for the given level and time range from the groupspace.

        Parameters
        ----------
        group : str
            The research group whose data to retrieve.
        lvl : str
            The level of the data to retrieve.
        time_range : TimeRange | TimeRangeTypes
            The time range of the data to retrieve.
        pattern : str
            A string pattern to filter the file paths.

        Returns
        -------
        list[DataFile]
            A list of data files.
        """
        time_range = self.clip_to_active(time_range)

        groupspace = self._get_groupspace(group)
        logger = self._loggers[group]
        return groupspace.get_datafiles(
            self.SID, self.name, lvl, logger, time_range, pattern
        )

    @property
    def active_range(self) -> TimeRange:
        """
        When this instrument was installed at the site and when it was removed.

        An instrument still installed has no stop. Built from the site
        configuration's ``installation_date`` / ``removal_date``.
        """
        removal_date = self.config.get("removal_date")
        return TimeRange(
            start=pd.to_datetime(self.config["installation_date"]),
            stop=pd.to_datetime(removal_date) if removal_date else None,
        )

    def clip_to_active(self, time_range: TimeRange | TimeRangeTypes) -> TimeRange:
        """
        Narrow a requested time range to when this instrument was installed.

        Parameters
        ----------
        time_range : TimeRange | TimeRangeTypes
            The requested time range.

        Returns
        -------
        TimeRange
            The requested range intersected with :attr:`active_range`. Never
            wider than what was asked for.

        Raises
        ------
        InactiveInstrumentError
            If the requested range does not overlap the active range at all.

        Notes
        -----
        Without this, a request that reaches past a swap reads the replacement
        instrument's files as though they were this one's: research groups
        reuse a file name across an instrument change (the horel group calls
        both MetOne models ``esampler``), so the file name cannot distinguish
        them, but the installation and removal dates can.
        """
        time_range = TimeRange(time_range)
        start, stop = time_range
        active_start, active_stop = self.active_range

        if (stop and active_start and stop < active_start) or (
            start and active_stop and start > active_stop
        ):
            raise errors.InactiveInstrumentError(self)

        clipped = TimeRange(
            start=max(start, active_start)
            if start and active_start
            else (start or active_start),
            stop=min(stop, active_stop)
            if stop and active_stop
            else (stop or active_stop),
        )
        if (clipped.start, clipped.stop) != (start, stop):
            _logger.debug(
                f"Clipped {time_range} to {clipped} -- when {self} was installed."
            )
        return clipped

    def standardize_data(self, group: str, data: pd.DataFrame) -> pd.DataFrame:
        """
        Manipulate the data to a standard format between research groups,
        renaming columns, converting units, mapping values, etc. as needed.

        Parameters
        ----------
        group : str
            The research group whose data to standardize.
        data : pandas.DataFrame
            The data to standardize.

        Returns
        -------
        pandas.DataFrame
            The standardized data.
        """
        groupspace = self._get_groupspace(group)
        return groupspace.standardize_data(self.model, data)

    def read_data(
        self,
        group: str,
        lvl: str | None = None,
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
        file_pattern: str | None = None,
    ) -> pd.DataFrame:
        """
        Read and parse data files for the given level and time range,
        using multiple processes if specified.

        Parameters
        ----------
        group : str
            The research group whose data to read.
        lvl : str
            The level of the data to read.
        time_range : TimeRange | TimeRangeTypes
            The time range to read data. Default is None which reads all available data.
        num_processes : int | 'max'
            The number of processes to use for parallelization.
        file_pattern : str
            A string pattern to filter the file paths.

        Returns
        -------
        pandas.DataFrame
            A concatenated DataFrame containing the parsed data from files.
        """
        _logger.info(f"Reading data for {self} from the {group} groupspace...")

        # Format lvl & time_range
        lvl = lvl.lower() if lvl else self.get_highest_lvl(group)
        assert lvl in filesystem.lvls, (
            f"Invalid data level '{lvl}'. Must be one of {filesystem.lvls}."
        )
        # Clip once, and use the clipped range for both file selection and the
        # row slice, so data logged after a swap cannot be read as this
        # instrument's (see clip_to_active).
        time_range = self.clip_to_active(time_range)

        _logger.info(f"Getting {lvl} files...")
        datafiles = self.get_datafiles(group, lvl, time_range, file_pattern)
        data = filesystem.parse_datafiles(datafiles, time_range, num_processes)
        _logger.info("Mapping columns to UATAQ names...")
        data = self.standardize_data(group, data)
        _logger.info("done.")
        return data


def configure_instrument(
    SID: str, name: str, config: dict, loggers: dict | None = None
) -> Instrument:
    """
    Configure an instrument object based on the given configuration settings.

    Parameters
    ----------
    SID : str
        Site ID where the instrument is installed.
    name : str
        Name of the instrument.
    config : dict
        Configuration settings for the instrument.
    loggers : dict, optional
        Dictionary of loggers used by different research groups.

    Returns
    -------
    Instrument
        An instrument object configured with the given settings.

    Raises
    ------
    ValueError
        If the instrument model is not found in the catalog.
    ValueError
        If no loggers are found for the instrument at the site.
    """
    model = config.get("model", name)

    loggers = config.get("loggers") or loggers
    if not loggers:
        raise ValueError(f"No loggers found for instrument {name} at site {SID}.")

    InstrumentClass = catalog.get(model)
    if not InstrumentClass:
        raise ValueError(f"Model '{model}' not found in the instrument catalog.")

    return InstrumentClass(SID, name, loggers, config)


class InstrumentEnsemble:
    """
    Container for an ensemble of instruments at a site.

    Attributes
    ----------
    SID : str
        Site ID of the ensemble.
    configs : dict[str, dict]
        Dictionary of configuration settings for each instrument.
    names : list[str]
        List of instrument names in the ensemble.
    loggers : set[str]
        Set of loggers used by the research groups.
    groups : set[str]
        Set of research groups that operate the instruments.
    pollutants : set[str]
        Set of pollutants measured by the instruments.
    """

    def __init__(self, SID: str, configs: dict, loggers: dict | None = None):
        """
        Initialize the InstrumentEnsemble object.

        Parameters
        ----------
        SID : str
            Site ID of the ensemble.
        configs : dict[instrument, config]
            Dictionary of configuration settings for each instrument.
        loggers : dict[group, logger], optional
            Dictionary of loggers used by different research groups.
        """
        self.SID = SID
        self.configs = configs
        self._loggers = loggers

        self.names = list(configs.keys())

        # Configure instruments
        self._instruments = {
            name: configure_instrument(SID, name, config, loggers)
            for name, config in configs.items()
        }

        # Gather ensemble attributes
        self.loggers = set()
        self.groups = set()
        self.pollutants = set()
        for instrument in self._instruments.values():
            self.loggers.update(instrument.loggers)
            self.groups.update(instrument.groups)

            # duck-typed: only SensorMixin subclasses declare pollutants
            pollutants = getattr(instrument, "pollutants", None)
            if pollutants:
                self.pollutants.update(p.upper() for p in pollutants)

    def __repr__(self):
        configs = json.dumps(self.configs, indent=4)
        loggers = f", loggers={self._loggers}" if self._loggers else ""
        return f'InstrumentEnsemble("{self.SID}", configs={configs}{loggers})'

    def __str__(self):
        return f"InstrumentEnsemble({self.SID}, instruments={self.names})"

    def __getattr__(self, name: str) -> Instrument:
        return self._instruments[name]

    def __getitem__(self, name: str) -> Instrument:
        return self._instruments[name]

    def __contains__(self, name: str) -> bool:
        return name in self.names

    def __iter__(self) -> Iterator[Instrument]:
        return iter(self._instruments.values())


class SensorMixin:
    """
    Mixin for instrument objects that measure a pollutant.

    Attributes:
        pollutants (tuple): Tuple of pollutants measured by the instrument.
    """

    pollutants: tuple[str, ...]


class BB_205(Instrument, SensorMixin):
    """2B Technologies Model 205 ozone monitor (UV absorption)."""

    model = "2b_205"
    pollutants = ("O3",)


class BB_405(Instrument, SensorMixin):
    """2B Technologies Model 405 nm NO/NO2/NOx monitor."""

    model = "2b_405"
    pollutants = ("NO", "NO2", "NOx")


class CR1000(Instrument):
    """Campbell Scientific CR1000 datalogger. Not a sensor itself: it
    records housekeeping such as battery voltage and enclosure temperature."""

    model = "cr1000"


class GPS(Instrument):
    """GPS receiver providing position, and speed/course where the receiver
    logs them.

    Recorded speed is converted from knots to ``Speed_m_s``. Receivers logging
    only ``GPGGA`` sentences record neither speed nor course; both are then
    estimated from the positions (:func:`uataq.gps.estimate_speed_course`) and
    flagged in ``Speed_Estimated`` / ``Course_Estimated``.
    """

    model = "gps"

    #: Samples on each side of the centered difference used to estimate speed
    #: and course from positions. See :func:`uataq.gps.estimate_speed_course`.
    estimate_window: int = 1

    #: Longest interval between consecutive fixes that an estimate may span.
    estimate_max_gap: str = "60s"

    def read_data(
        self,
        group: str,
        lvl: str | None = None,
        time_range: TimeRange | TimeRangeTypes = None,
        num_processes: int | Literal["max"] = 1,
        file_pattern: str | None = None,
        estimate_motion: bool = True,
    ) -> pd.DataFrame:
        """
        Read GPS data, with speed in m/s and course in degrees.

        Extends :meth:`Instrument.read_data`. Recorded speed (knots in the
        files) is converted to m/s as ``Speed_m_s``, and course is
        ``Course_deg``.

        Receivers logging only ``GPGGA`` sentences record neither, in which
        case both are estimated from the positions (see
        :func:`uataq.gps.estimate_speed_course`) and the boolean columns
        ``Speed_Estimated`` / ``Course_Estimated`` mark every value that came
        from positions rather than from the receiver. Recorded values are
        never overwritten.

        Parameters
        ----------
        estimate_motion : bool
            Fill missing speed and course from the positions. Default True.
            Only reachable through the instrument object --
            :func:`uataq.read_data` does not forward it.

        See :meth:`Instrument.read_data` for the other parameters.
        """
        # Read GPS data
        data = super().read_data(group, lvl, time_range, num_processes, file_pattern)

        if "Speed_kt" in data.columns:
            # convert knots to m/s
            data["Speed_kt"] = data.Speed_kt * 0.514444
            data.rename(columns={"Speed_kt": "Speed_m_s"}, inplace=True)

        if estimate_motion:
            data = self.estimate_motion(data)

        return data

    @classmethod
    def estimate_motion(cls, data: pd.DataFrame) -> pd.DataFrame:
        """
        Fill missing ``Speed_m_s`` / ``Course_deg`` from the positions.

        Adds ``Speed_Estimated`` and ``Course_Estimated``, which are True
        exactly where the value was derived from positions rather than
        recorded by the receiver. Returns ``data`` unchanged if it has no
        positions or no DatetimeIndex to difference against.
        """
        if not {"Latitude_deg", "Longitude_deg"}.issubset(data.columns) or not (
            isinstance(data.index, pd.DatetimeIndex) and len(data)
        ):
            return data

        estimated = gps.estimate_speed_course(
            data.Latitude_deg,
            data.Longitude_deg,
            time=data.index,
            window=cls.estimate_window,
            max_gap=cls.estimate_max_gap,
        )
        for col in ("Speed_m_s", "Course_deg"):
            if col not in data.columns:
                data[col] = np.nan
            elif not pd.api.types.is_numeric_dtype(data[col]):
                # An all-NA column can come back as strings (the GPGGA-only
                # years), which cannot hold the fill values.
                coerced = pd.to_numeric(data[col].astype(object), errors="coerce")
                data[col] = np.asarray(coerced, dtype=float)
            # Positions only fill gaps; a recorded value always wins.
            missing = data[col].isna().to_numpy()
            values = estimated[col].to_numpy()
            data.loc[missing, col] = values[missing]
            data[f"{col.split('_')[0]}_Estimated"] = missing & ~np.isnan(values)
        return data


class LGR_NO2(Instrument, SensorMixin):
    """Los Gatos Research NO2 analyzer (cavity-enhanced absorption)."""

    model = "lgr_no2"
    pollutants = ("NO2",)


class LGR_UGGA(Instrument, SensorMixin):
    """Los Gatos Research Ultraportable Greenhouse Gas Analyzer,
    measuring CO2 and CH4 by off-axis ICOS."""

    model = "lgr_ugga"
    pollutants = ("CO2", "CH4")


class Licor_6262(Instrument, SensorMixin):
    """LI-COR LI-6262 infrared CO2/H2O gas analyzer."""

    model = "licor_6262"
    pollutants = ("CO2",)


class Licor_7000(Licor_6262):
    """LI-COR LI-7000 infrared CO2/H2O gas analyzer. Parsed like the
    LI-6262."""

    model = "licor_7000"


class Magee_AE33(Instrument, SensorMixin):
    """Magee Scientific AE33 aethalometer, measuring black carbon."""

    model = "magee_ae33"
    pollutants = ("BC",)


class MetOne_ES405(Instrument, SensorMixin):
    """Met One E-Sampler ES-405, reporting PM1, PM2.5, PM4 and PM10.

    Replaced the ES-642 at several sites. The horel group names both models
    ``esampler`` on disk, so only the configured installation and removal
    dates separate them -- see :meth:`Instrument.clip_to_active`."""

    model = "metone_es405"
    pollutants = ("PM1", "PM2.5", "PM4", "PM10")


class MetOne_ES642(Instrument, SensorMixin):
    """Met One E-Sampler ES-642, reporting PM2.5 only.

    Superseded by the ES-405 at several sites; see :class:`MetOne_ES405`."""

    model = "metone_es642"
    pollutants = ("PM2.5",)


class Teledyne_T200(Instrument, SensorMixin):
    """Teledyne API T200 chemiluminescence NO/NO2/NOx analyzer."""

    model = "teledyne_t200"
    pollutants = ("NO", "NO2", "NOx")


class Teledyne_T300(Instrument, SensorMixin):
    """Teledyne API T300 gas-filter-correlation CO analyzer."""

    model = "teledyne_t300"
    pollutants = ("CO",)


class Teledyne_T400(Instrument, SensorMixin):
    """Teledyne API T400 UV-absorption ozone analyzer."""

    model = "teledyne_t400"
    pollutants = ("O3",)


class Teledyne_T500u(Instrument, SensorMixin):
    """Teledyne API T500U CAPS NO2 analyzer."""

    model = "teledyne_t500u"
    pollutants = ("NO2",)


class Teom_1400ab(Instrument, SensorMixin):
    """Thermo/R&P TEOM 1400ab tapered-element oscillating microbalance,
    measuring PM2.5 mass."""

    model = "teom_1400ab"
    pollutants = ("PM2.5",)


#: Instrument catalog
catalog: dict[str, type[Instrument]] = {
    "2b_205": BB_205,
    "2b_405": BB_405,
    "cr1000": CR1000,
    "gps": GPS,
    "lgr_no2": LGR_NO2,
    "lgr_ugga": LGR_UGGA,
    "licor_6262": Licor_6262,
    "licor_7000": Licor_7000,
    "magee_ae33": Magee_AE33,
    "metone_es405": MetOne_ES405,
    "metone_es642": MetOne_ES642,
    "teledyne_t200": Teledyne_T200,
    "teledyne_t300": Teledyne_T300,
    "teledyne_t400": Teledyne_T400,
    "teledyne_t500u": Teledyne_T500u,
    "teom_1400ab": Teom_1400ab,
}
