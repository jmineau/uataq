"""
This module provides custom exceptions for UATAQ.
"""


class DataFileInitializationError(Exception):
    """Raised when a data file cannot be set up, e.g. its header or file name
    does not carry the metadata the reader needs."""


class ParserError(Exception):
    """Raised when a data file's contents cannot be parsed."""


class ReaderError(Exception):
    """Base class for failures to read data. Caught per instrument by
    :meth:`uataq.sites.Site.read_data`, which warns and moves on."""


class InactiveInstrumentError(ReaderError):
    """Raised when the requested time range lies entirely outside the window
    in which the instrument was installed at the site."""

    def __init__(self, instrument):
        msg = f"{instrument} is inactive in given time_range"
        super().__init__(msg)


class InvalidGroupError(ReaderError):
    """Raised when a research group does not operate the instrument, or is not
    a registered groupspace."""


class InstrumentNotFoundError(Exception):
    """Raised when a site does not have the requested instrument."""

    def __init__(self, instrument, ensemble):
        msg = f"{instrument} not found in {ensemble}"
        super().__init__(msg)


class PollutantNotMeasured(Exception):
    """Raised when a site measures none of the requested pollutants."""

    def __init__(self, SID, pollutant):
        msg = f"{pollutant} not measured at {SID}"
        super().__init__(msg)
