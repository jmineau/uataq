"""
Time range handling.

:class:`TimeRange` normalizes the several ways a caller can ask for a period
(a string, a ``(start, stop)`` pair, a list, a slice, or None for everything)
into a start and a stop.
"""

import datetime as dt
import re
from typing import TypeAlias

import numpy as np
import pandas as pd

# Type Aliases for TimeRange inputs
TimeObject: TypeAlias = str | dt.datetime | np.datetime64 | None
TimeRangeTuple: TypeAlias = tuple[TimeObject, TimeObject]
TimeRangeList: TypeAlias = list[TimeObject]
TimeRangeTypes = str | TimeRangeTuple | TimeRangeList | slice | None

# Each component needs the one before it, so "2024-1-5" fails instead of
# being read as year 2024, hour 1. Only a UTC offset is accepted.
_ISO8601 = re.compile(
    r"^(?P<year>\d{4})"
    r"(?:-?(?P<month>\d{2})"
    r"(?:-?(?P<day>\d{2})"
    r"(?:[T\s](?P<hour>\d{1,2})"
    r"(?::?(?P<minute>\d{2})"
    r"(?::?(?P<second>\d{2}(?:\.\d{1,6})?))?"
    r")?)?)?)?"
    r"(?:Z|[+-]00:?00)?$"
)


class TimeRange:
    """
    TimeRange class to represent a time range with start and stop times.

    Attributes
    ----------
    start : dt.datetime | None
        The start time of the time range.
    stop : dt.datetime | None
        The stop time of the time range.
    total_seconds : float
        The total number of seconds in the time range.

    Methods
    -------
    parse_iso(string: str, inclusive: bool = False) -> dt.datetime
        Parse an ISO 8601 time string into a datetime.
    """

    def __init__(
        self,
        time_range: "TimeRange | TimeRangeTypes" = None,
        start: TimeObject = None,
        stop: TimeObject = None,
    ):
        """
        Initialize a TimeRange object with the specified time range.
        """
        assert not all([time_range, any([start, stop])]), (
            "Cannot specify both time_range and start/stop"
        )

        self._start = None
        self._stop = None

        if isinstance(time_range, TimeRange):
            start, stop = time_range.start, time_range.stop
        elif not any([time_range, start, stop]):
            start = None
            stop = None
        elif time_range:
            if isinstance(time_range, str):
                # Handle the case when time_range is a string
                start = TimeRange.parse_iso(time_range)
                stop = TimeRange.parse_iso(time_range, inclusive=True)
            elif isinstance(time_range, (list, tuple)) and len(time_range) == 2:
                # Handle the case when time_range is a list/tuple
                #   representing start and stop
                start, stop = time_range
            elif isinstance(time_range, slice):
                # Handle the case when time_range is a slice
                start, stop = time_range.start, time_range.stop
            else:
                raise ValueError("Invalid time_range format")

        self.start = start
        self.stop = stop

    def __repr__(self):
        return f"TimeRange(start={self.start}, stop={self.stop})"

    def __str__(self):
        if not any([self.start, self.stop]):
            return "Entire Observation Period"
        elif not self.start:
            return f"Before {self.stop}"
        elif not self.stop:
            return f"After {self.start}"
        else:
            return f"{self.start} to {self.stop}"

    def __iter__(self):
        return iter([self.start, self.stop])

    def __contains__(self, item):
        # Half-open [start, stop): a string range stops at the start of the
        # next period, so TimeRange("2024") does not contain 2025-01-01 00:00
        if not any([self.start, self.stop]):
            # Entire Period - True
            return True
        if not self.start:
            # Before stop - True if item < stop
            return item < self.stop
        if not self.stop:
            # After start - True if start <= item
            return self.start <= item
        return self.start <= item < self.stop

    @property
    def start(self) -> dt.datetime | None:
        """
        Start of the range, or None when unbounded.

        Assigning a string parses it; a date-only string is taken as the
        beginning of that day.
        """
        return self._start

    @start.setter
    def start(self, start):
        if start is None or isinstance(start, dt.datetime):
            self._start = start
        elif isinstance(start, str):
            self._start = TimeRange.parse_iso(start)
        elif isinstance(start, np.datetime64):
            self._start = pd.to_datetime(start).to_pydatetime()
        else:
            raise ValueError("Invalid start time format")

    @property
    def stop(self) -> dt.datetime | None:
        """
        End of the range, or None when unbounded.

        Assigning a string parses it **inclusively**: a date-only string is
        taken as the end of that day, so ``"2024-01-01"`` stops at
        ``2024-01-02 00:00``.
        """
        return self._stop

    @stop.setter
    def stop(self, stop):
        if stop is None or isinstance(stop, dt.datetime):
            self._stop = stop
        elif isinstance(stop, str):
            self._stop = TimeRange.parse_iso(stop, inclusive=True)
        elif isinstance(stop, np.datetime64):
            self._stop = pd.to_datetime(stop).to_pydatetime()
        else:
            raise ValueError("Invalid stop time format")

    @property
    def total_seconds(self) -> float:
        """
        Length of the range in seconds.

        Raises
        ------
        ValueError
            If either end is unbounded.
        """
        if self.start is None or self.stop is None:
            raise ValueError("Both start and stop times must be specified")
        return (self.stop - self.start).total_seconds()

    @staticmethod
    def parse_iso(string: str, inclusive: bool = False) -> dt.datetime:
        """
        Parse an ISO 8601 time string into a datetime.

        Accepts ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``, then a ``T`` or space
        and ``HH``, ``HH:MM``, ``HH:MM:SS`` or ``HH:MM:SS.ffffff``. Dashes and
        colons may be left out (``20240115``), and a trailing ``Z`` or
        ``+00:00`` is allowed; times are UTC.

        Parameters
        ----------
        string : str
            The ISO 8601 formatted time string.
        inclusive : bool
            If False (default), return the start of the period the string
            names. If True, return its end: one unit of the finest component
            given past the start, so ``"2024-01"`` ends at ``2024-02-01``,
            ``"2024-01-15T12:30"`` at ``12:31``, and ``"12:30:45.5"`` at
            ``12:30:45.6`` (one unit of the last fractional digit).

        Returns
        -------
        dt.datetime
            The parsed datetime.

        Raises
        ------
        ValueError
            If the string is not in one of the accepted forms, carries a
            non-UTC offset, or names an impossible date.
        """
        match = _ISO8601.match(string.strip())
        if not match:
            raise ValueError(
                f"Invalid time string '{string}'. Expected ISO 8601 in UTC, "
                "e.g. '2024', '2024-01', '2024-01-15', '2024-01-15T12:30:45'."
            )

        c = match.groupdict()
        second, _, fraction = (c["second"] or "0").partition(".")
        start = dt.datetime(
            int(c["year"]),
            int(c["month"] or 1),
            int(c["day"] or 1),
            int(c["hour"] or 0),
            int(c["minute"] or 0),
            int(second),
            int(fraction.ljust(6, "0")) if fraction else 0,
        )
        if not inclusive:
            return start

        # Widen by one unit of the finest component given
        if c["second"]:
            # e.g. 45 -> +1 s, 45.5 -> +0.1 s, 45.123456 -> +1 us
            return start + dt.timedelta(microseconds=10 ** (6 - len(fraction)))
        if c["minute"]:
            return start + dt.timedelta(minutes=1)
        if c["hour"]:
            return start + dt.timedelta(hours=1)
        if c["day"]:
            return start + dt.timedelta(days=1)
        if c["month"]:
            if start.month == 12:
                return start.replace(year=start.year + 1, month=1)
            return start.replace(month=start.month + 1)
        return start.replace(year=start.year + 1)
