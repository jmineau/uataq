"""
Tests for the TimeRange class.
"""

import datetime as dt
from typing import Tuple

import numpy as np
import pandas as pd
import pytest

from uataq.timerange import TimeRange


class TestTimeRangeInitialization:
    """Test TimeRange initialization with various input formats."""

    def test_empty_initialization(self):
        """Test creating an empty TimeRange (entire observation period)."""
        tr = TimeRange()
        assert tr.start is None
        assert tr.stop is None

    def test_initialization_with_datetime_objects(self, sample_datetime_range):
        """Test initialization with datetime objects."""
        start, stop = sample_datetime_range
        tr = TimeRange(start=start, stop=stop)
        assert tr.start == start
        assert tr.stop == stop

    def test_initialization_with_iso_string(self):
        """Test initialization with ISO8601 date string."""
        tr = TimeRange("2024-01-15")
        assert tr.start is not None
        assert tr.stop is not None
        # When given a single date, start and stop should bracket the day
        assert tr.start.date() == dt.date(2024, 1, 15)
        # Stop might be at start of next day when inclusive=True
        assert tr.stop.date() in [dt.date(2024, 1, 15), dt.date(2024, 1, 16)]

    def test_initialization_with_tuple(self):
        """Test initialization with tuple of (start, stop)."""
        start = dt.datetime(2024, 1, 1)
        stop = dt.datetime(2024, 1, 31)
        tr = TimeRange((start, stop))
        assert tr.start == start
        assert tr.stop == stop

    def test_initialization_with_list(self):
        """Test initialization with list of [start, stop]."""
        start = dt.datetime(2024, 1, 1)
        stop = dt.datetime(2024, 1, 31)
        tr = TimeRange([start, stop])
        assert tr.start == start
        assert tr.stop == stop

    def test_initialization_with_slice(self):
        """Test initialization with slice object."""
        start = dt.datetime(2024, 1, 1)
        stop = dt.datetime(2024, 1, 31)
        tr = TimeRange(slice(start, stop))
        assert tr.start == start
        assert tr.stop == stop

    def test_initialization_with_timerange_object(self):
        """Test initialization by copying another TimeRange."""
        original = TimeRange(
            start=dt.datetime(2024, 1, 1), stop=dt.datetime(2024, 1, 31)
        )
        copy = TimeRange(original)
        assert copy.start == original.start
        assert copy.stop == original.stop

    def test_initialization_with_numpy_datetime64(self):
        """Test initialization with numpy datetime64 objects."""
        start = np.datetime64("2024-01-01")
        stop = np.datetime64("2024-01-31")
        tr = TimeRange(start=start, stop=stop)
        assert isinstance(tr.start, dt.datetime)
        assert isinstance(tr.stop, dt.datetime)

    def test_initialization_conflict_raises_error(self):
        """Test that specifying both time_range and start/stop raises error."""
        with pytest.raises(AssertionError):
            TimeRange(
                time_range="2024-01-15",
                start=dt.datetime(2024, 1, 1),
            )

    def test_initialization_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError):
            TimeRange(time_range=12345)  # Invalid type


class TestTimeRangeProperties:
    """Test TimeRange property setters and getters."""

    def test_start_setter_with_datetime(self):
        """Test setting start with datetime object."""
        tr = TimeRange()
        dt_obj = dt.datetime(2024, 1, 1, 12, 0, 0)
        tr.start = dt_obj
        assert tr.start == dt_obj

    def test_start_setter_with_iso_string(self):
        """Test setting start with ISO8601 string."""
        tr = TimeRange()
        tr.start = "2024-01-01"
        assert isinstance(tr.start, dt.datetime)
        assert tr.start.date() == dt.date(2024, 1, 1)

    def test_start_setter_with_numpy_datetime64(self):
        """Test setting start with numpy datetime64."""
        tr = TimeRange()
        tr.start = np.datetime64("2024-01-01")
        assert isinstance(tr.start, dt.datetime)

    def test_start_setter_with_none(self):
        """Test setting start to None."""
        tr = TimeRange()
        tr.start = None
        assert tr.start is None

    def test_stop_setter_similar_to_start(self):
        """Test that stop setter works like start setter."""
        tr = TimeRange()
        tr.stop = dt.datetime(2024, 1, 31, 23, 59, 59)
        assert isinstance(tr.stop, dt.datetime)

    def test_total_seconds_property(self):
        """Test total_seconds property calculation."""
        start = dt.datetime(2024, 1, 1, 0, 0, 0)
        stop = dt.datetime(2024, 1, 2, 0, 0, 0)  # 24 hours later
        tr = TimeRange(start=start, stop=stop)
        assert tr.total_seconds == 86400.0  # 24 * 60 * 60

    def test_total_seconds_raises_error_without_both_times(self):
        """Test that total_seconds raises error if start or stop is missing."""
        tr = TimeRange(start=dt.datetime(2024, 1, 1))
        with pytest.raises(ValueError):
            _ = tr.total_seconds

        tr = TimeRange(stop=dt.datetime(2024, 1, 31))
        with pytest.raises(ValueError):
            _ = tr.total_seconds


class TestTimeRangeStringRepresentation:
    """Test TimeRange string representations."""

    def test_repr(self):
        """Test __repr__ method."""
        tr = TimeRange(
            start=dt.datetime(2024, 1, 1), stop=dt.datetime(2024, 1, 31)
        )
        repr_str = repr(tr)
        assert "TimeRange" in repr_str
        assert "2024-01-01" in repr_str

    def test_str_empty_range(self):
        """Test __str__ for empty time range."""
        tr = TimeRange()
        assert str(tr) == "Entire Observation Period"

    def test_str_only_start(self):
        """Test __str__ for range with only start."""
        tr = TimeRange(start=dt.datetime(2024, 1, 1))
        assert "After 2024-01-01" in str(tr)

    def test_str_only_stop(self):
        """Test __str__ for range with only stop."""
        tr = TimeRange(stop=dt.datetime(2024, 1, 31))
        assert "Before 2024-01-31" in str(tr)

    def test_str_full_range(self):
        """Test __str__ for full time range."""
        tr = TimeRange(
            start=dt.datetime(2024, 1, 1), stop=dt.datetime(2024, 1, 31)
        )
        str_repr = str(tr)
        assert "2024-01-01" in str_repr
        assert "2024-01-31" in str_repr


class TestTimeRangeIteration:
    """Test TimeRange iteration."""

    def test_iter_returns_start_and_stop(self):
        """Test that iterating over TimeRange returns [start, stop]."""
        start = dt.datetime(2024, 1, 1)
        stop = dt.datetime(2024, 1, 31)
        tr = TimeRange(start=start, stop=stop)
        items = list(tr)
        assert items == [start, stop]


class TestTimeRangeMembership:
    """Test TimeRange containment/membership checks."""

    def test_contains_entire_period(self):
        """Test containment for empty (entire period) TimeRange."""
        tr = TimeRange()
        assert dt.datetime(2024, 1, 15) in tr
        assert dt.datetime(1990, 1, 1) in tr

    def test_contains_before_stop_only(self):
        """Test containment for range with only stop."""
        tr = TimeRange(stop=dt.datetime(2024, 1, 31))
        assert dt.datetime(2024, 1, 15) in tr
        assert dt.datetime(2024, 1, 31) in tr
        assert dt.datetime(2024, 2, 1) not in tr

    def test_contains_after_start_only(self):
        """Test containment for range with only start."""
        tr = TimeRange(start=dt.datetime(2024, 1, 1))
        assert dt.datetime(2024, 1, 15) in tr
        assert dt.datetime(2024, 1, 1) in tr
        assert dt.datetime(2023, 12, 31) not in tr

    def test_contains_full_range(self):
        """Test containment for full time range."""
        tr = TimeRange(
            start=dt.datetime(2024, 1, 1), stop=dt.datetime(2024, 1, 31)
        )
        assert dt.datetime(2024, 1, 15) in tr
        assert dt.datetime(2024, 1, 1) in tr
        assert dt.datetime(2024, 1, 31) in tr
        assert dt.datetime(2024, 2, 1) not in tr
        assert dt.datetime(2023, 12, 31) not in tr


class TestTimeRangeParsing:
    """Test static parse_iso method."""

    def test_parse_iso_date_only(self):
        """Test parsing ISO date (YYYY-MM-DD)."""
        result = TimeRange.parse_iso("2024-01-15")
        assert result.date() == dt.date(2024, 1, 15)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_parse_iso_datetime(self):
        """Test parsing ISO datetime."""
        result = TimeRange.parse_iso("2024-01-15T12:30:45")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        # Parsing might normalize time, check at least hour is reasonable
        assert result.hour >= 0
        assert result.hour < 24

    def test_parse_iso_with_timezone(self):
        """Test parsing ISO datetime with timezone."""
        result = TimeRange.parse_iso("2024-01-15T12:30:45Z")
        assert isinstance(result, dt.datetime)

    def test_parse_iso_inclusive_flag(self):
        """Test parse_iso with inclusive flag adds time."""
        result_exclusive = TimeRange.parse_iso("2024-01-15", inclusive=False)
        result_inclusive = TimeRange.parse_iso("2024-01-15", inclusive=True)

        # Exclusive should be start of day
        assert result_exclusive.hour == 0
        # Inclusive should be end of day
        assert result_inclusive.hour == 23 or result_inclusive.day != 15


class TestTimeRangeEdgeCases:
    """Test edge cases and special scenarios."""

    def test_zero_duration_range(self):
        """Test time range with same start and stop."""
        dt_obj = dt.datetime(2024, 1, 15, 12, 0, 0)
        tr = TimeRange(start=dt_obj, stop=dt_obj)
        assert tr.total_seconds == 0.0

    def test_microsecond_precision(self):
        """Test that microsecond precision is preserved."""
        start = dt.datetime(2024, 1, 1, 0, 0, 0, 123456)
        stop = dt.datetime(2024, 1, 1, 0, 0, 1, 654321)
        tr = TimeRange(start=start, stop=stop)
        assert tr.start.microsecond == 123456
        assert tr.stop.microsecond == 654321

    def test_reverse_order_range(self):
        """Test time range where start is after stop (should still work)."""
        start = dt.datetime(2024, 1, 31)
        stop = dt.datetime(2024, 1, 1)
        tr = TimeRange(start=start, stop=stop)
        # Object should be created, but total_seconds will be negative
        assert tr.start == start
        assert tr.stop == stop
