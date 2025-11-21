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
        Parse the ISO8601 formatted time string and return a datetime object.
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
        if not any([self.start, self.stop]):
            # Entire Period - True
            return True
        if not self.start:
            # Before stop - True if item <= stop
            return item <= self.stop
        if not self.stop:
            # After start - True if start <= item
            return self.start <= item
        return self.start <= item <= self.stop

    @property
    def start(self) -> dt.datetime | None:
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
        if not all([self.start, self.stop]):
            raise ValueError("Both start and stop times must be specified")
        return (self.stop - self.start).total_seconds()

    @staticmethod
    def parse_iso(string: str, inclusive: bool = False) -> dt.datetime:
        """
        Parse the ISO8601 formatted time string and return a namedtuple with the parsed components.

        Parameters
        ----------
        string : str
            The ISO8601 formatted time string.
        inclusive

        Returns
        -------
        dt.datetime
            The parsed datetime object.

        Raises
        ------
        ValueError
            If the time_str format is invalid.
        """
        # Parse time_range string using regex assuming ISO8601 format
        iso8601 = (
            r"^(?P<year>\d{4})-?(?P<month>\d{2})?-?(?P<day>\d{2})?"
            r"[T\s]?(?P<hour>\d{1,2})?:?(?:\d{2})?"
        )
        match = re.match(iso8601, string)
        if not match:
            raise ValueError("Invalid time string format")

        components = match.groupdict()
        year = int(components["year"])
        month = int(components["month"] or 1)
        day = int(components["day"] or 1)
        hour = int(components["hour"] or 0)

        start = dt.datetime(year, month, day, hour)

        # Determine the stop time based on the inclusive flag
        if inclusive:
            if components["year"] and not components["month"]:
                "YYYY"
                stop = dt.datetime(year + 1, 1, 1)
            elif components["month"] and not components["day"]:
                "YYYY-MM"
                mm = month + 1 if month < 12 else 1
                yyyy = year + 1 if month == 12 else year
                stop = dt.datetime(yyyy, mm, 1)
            elif components["day"] and not components["hour"]:
                "YYYY-MM-DD"
                stop = start + dt.timedelta(days=1)
            elif components["hour"]:
                "YYYY-MM-DDTHH"
                stop = start + dt.timedelta(hours=1)
            else:
                raise ValueError("Invalid time string format")

            return stop
        else:
            return start
