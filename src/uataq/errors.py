"""
Custom exceptions and warnings for UATAQ.
"""


class DataFileInitializationError(Exception):
    """
    Raised when a data file cannot be set up.

    Its header or file name, for example, does not carry the metadata the
    reader needs.
    """


class ParserError(Exception):
    """Raised when a data file's contents cannot be parsed."""


class ReaderError(Exception):
    """
    Base class for failures to read data.

    Caught per instrument by :meth:`uataq.sites.Site.read_data`, which warns
    and moves on.

    Attributes
    ----------
    detail : str
        When a read found no data at a site, the part of the message that says
        what became of each instrument (``Site.get_obs`` puts it behind the
        pollutants it was asked for). Empty for every other error.
    """

    detail: str = ""


class InactiveInstrumentError(ReaderError):
    """
    Raised when the requested time range misses the instrument's installation.

    The range lies entirely outside the window in which the instrument was
    installed at the site.
    """

    def __init__(self, instrument):
        msg = f"{instrument} is inactive in given time_range"
        super().__init__(msg)


class InvalidGroupError(ReaderError):
    """
    Raised when a research group cannot read the instrument.

    The group does not operate the instrument, or is not a registered
    groupspace.
    """


class InstrumentNotFoundError(Exception):
    """Raised when a site does not have the requested instrument."""

    def __init__(self, instrument, ensemble):
        msg = f"{instrument} not found in {ensemble}"
        super().__init__(msg)


class EmptyResultWarning(UserWarning):
    """
    Warned when a read finds files for the range but no data in them.

    ``get_obs`` and ``get_recent_obs`` issue it for a table with no rows, and
    so does ``Network.get_obs``. The read did not fail: the archive has files
    for the range, and nothing in them falls inside it. At a mobile site,
    ``get_obs`` also issues it when the files hold rows but none of them found
    a GPS fix. Silence it with
    ``warnings.filterwarnings("ignore", category=uataq.errors.EmptyResultWarning)``.
    """


class DroppedPollutantWarning(UserWarning):
    """
    Warned when a read of several pollutants leaves one out for want of data.

    ``get_obs`` and ``get_recent_obs`` issue it when none of the instruments
    that measure a pollutant you asked for gave data (no files for the range,
    or not installed then), so the table has no column for it. The read did not
    fail: the other pollutants are returned. ``uataq.gsv.get_obs`` issues it when
    the Picarro's CH4 table is missing. Silence it with
    ``warnings.filterwarnings("ignore", category=uataq.errors.DroppedPollutantWarning)``.
    """


class DataFileWarning(UserWarning):
    """
    Warned when a data file is not what the reader expects and a read went on.

    The read did not fail, but part of the archive did not make it into the
    result: a file that could not be parsed is skipped, rows whose time cannot
    be read are dropped, or two rows of the files read share a time (the files
    may overlap, or repeat rows). The message names the file. Silence it with
    ``warnings.filterwarnings("ignore", category=uataq.errors.DataFileWarning)``.
    """
