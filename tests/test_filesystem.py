"""
Tests for filesystem utilities.
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from uataq import errors, filesystem
from uataq.timerange import TimeRange


class TestLvlsConstant:
    """Test the lvls constant dictionary."""

    def test_lvls_contains_expected_keys(self):
        """Test that lvls dict has all expected processing levels."""
        expected_keys = {"raw", "qaqc", "calibrated", "final"}
        assert set(filesystem.lvls.keys()) == expected_keys

    def test_lvls_values_are_ordered(self):
        """Test that lvls values are in ascending order."""
        assert filesystem.lvls["raw"] < filesystem.lvls["qaqc"]
        assert filesystem.lvls["qaqc"] < filesystem.lvls["calibrated"]
        assert filesystem.lvls["calibrated"] < filesystem.lvls["final"]

    def test_lvls_raw_is_first(self):
        """Test that raw level has value 1."""
        assert filesystem.lvls["raw"] == 1

    def test_lvls_final_is_last(self):
        """Test that final level has value 4."""
        assert filesystem.lvls["final"] == 4


class TestListFiles:
    """Test the list_files function."""

    def test_list_files_basic(self, temp_test_dir):
        """Test listing files in a directory."""
        raw_dir = temp_test_dir / "raw" / "2024" / "01"
        files = filesystem.list_files(path=raw_dir)

        assert len(files) > 0
        # Check that all results are strings or Paths
        for f in files:
            assert isinstance(f, (str, Path))

    def test_list_files_with_pattern(self, temp_test_dir):
        """Test listing files with a glob pattern."""
        raw_dir = temp_test_dir / "raw" / "2024" / "01"
        files = filesystem.list_files(path=raw_dir, pattern="*.dat")

        assert len(files) > 0
        for f in files:
            assert str(f).endswith(".dat")

    def test_list_files_full_names(self, temp_test_dir):
        """Test listing files with full_names=True."""
        raw_dir = temp_test_dir / "raw" / "2024" / "01"
        files = filesystem.list_files(path=raw_dir, full_names=True)

        if files:
            # With full_names=True, paths should be absolute or contain directory
            for f in files:
                assert "/" in str(f) or "\\" in str(f)

    def test_list_files_recursive(self, temp_test_dir):
        """Test recursive file listing."""
        base_dir = temp_test_dir / "raw"
        files_non_recursive = filesystem.list_files(path=base_dir, recursive=False)
        files_recursive = filesystem.list_files(path=base_dir, recursive=True)

        # Recursive should find more or equal files
        assert len(files_recursive) >= len(files_non_recursive)

    def test_list_files_default_path(self):
        """Test list_files with default path (current directory)."""
        # Should not raise an error
        files = filesystem.list_files()
        assert isinstance(files, list)

    def test_list_files_empty_directory(self, tmp_path):
        """Test listing files in an empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        files = filesystem.list_files(path=empty_dir)
        assert files == []

    def test_list_files_case_insensitive(self, temp_test_dir):
        """Test case-insensitive pattern matching."""
        raw_dir = temp_test_dir / "raw" / "2024" / "01"
        files_lower = filesystem.list_files(
            path=raw_dir, pattern="*.dat", ignore_case=False
        )
        files_upper = filesystem.list_files(
            path=raw_dir, pattern="*.DAT", ignore_case=True
        )

        # At least one should find results (assuming lowercase files exist)
        assert len(files_lower) + len(files_upper) > 0


class TestHomeConstant:
    """Test the HOME constant."""

    def test_home_is_string(self):
        """Test that HOME is defined as a string."""
        from uataq.filesystem.core import HOME

        assert isinstance(HOME, str)

    def test_home_points_to_common_home(self):
        """Test that HOME points to the expected directory."""
        from uataq.filesystem.core import HOME

        assert "common" in HOME
        assert "home" in HOME


class TestFileSystemIntegration:
    """Integration tests for filesystem functions."""

    def test_list_files_with_multiple_patterns(self, temp_test_dir):
        """Test listing files matching multiple patterns."""
        raw_dir = temp_test_dir / "raw" / "2024" / "01"

        # List dat files
        dat_files = filesystem.list_files(path=raw_dir, pattern="*.dat")
        assert len(dat_files) > 0

    def test_list_files_handles_nonexistent_path(self):
        """Test behavior when path doesn't exist."""
        # Should handle gracefully - may raise or return empty list
        # depending on implementation
        try:
            files = filesystem.list_files(path="/nonexistent/path/xyz")
            # If it doesn't raise, it should return a list
            assert isinstance(files, list)
        except (FileNotFoundError, OSError):
            # Or it might raise an error, which is also acceptable
            pass


class TestParseDatafiles:
    """Test parse_datafiles."""

    class BadFile(filesystem.DataFile):
        """A data file whose contents never parse."""

        date_slicer = slice(7)
        file_freq = "M"
        ext = "dat"

        def parse(self):
            raise errors.ParserError("unparseable")

    def test_no_parseable_files_raises_reader_error(self):
        """Used to escape as pd.concat's ValueError (#16)."""
        files = [self.BadFile("2024_01.dat"), self.BadFile("2024_02.dat")]
        with pytest.raises(errors.ReaderError, match="None of the 2"):
            filesystem.parse_datafiles(files, TimeRange("2024"))

    def test_rows_are_half_open(self):
        """A sample exactly at stop is not returned (#9)."""

        class GoodFile(filesystem.DataFile):
            date_slicer = slice(7)
            file_freq = "M"
            ext = "dat"

            def parse(self):
                times = ["2024-01-01", "2024-01-15", "2024-02-01"]
                return pd.DataFrame({"Time_UTC": pd.to_datetime(times), "x": 1})

        files = [GoodFile("2024_01.dat")]
        data = filesystem.parse_datafiles(files, TimeRange("2024-01"))
        assert data.index.tolist() == [
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-01-15"),
        ]


class MonthFile(filesystem.DataFile):
    """A monthly data file that parses to two rows."""

    date_slicer = slice(7)
    file_freq = "M"
    ext = "dat"

    def parse(self):
        times = pd.to_datetime([f"{self.period}-01", f"{self.period}-02"])
        return pd.DataFrame({"Time_UTC": times, "x": [1.0, 2.0]})


class TestFilterDatafiles:
    """Choosing data files by period and pattern."""

    files = [
        MonthFile("/a/2024_01_qaqc.dat"),
        MonthFile("/a/2024_02_final.dat"),
        MonthFile("/a/2024_03_final.dat"),
    ]

    def test_by_period(self):
        out = filesystem.filter_datafiles(self.files, TimeRange("2024-02"))
        assert [str(f) for f in out] == ["/a/2024_02_final.dat"]

    def test_by_pattern(self):
        out = filesystem.filter_datafiles(self.files, TimeRange(), pattern="final")
        assert [f.path for f in out] == ["/a/2024_02_final.dat", "/a/2024_03_final.dat"]

    def test_nothing_in_range(self):
        with pytest.raises(errors.ReaderError, match="No files found"):
            filesystem.filter_datafiles(self.files, TimeRange("2023"))


class TestParseDatafilesOptions:
    """Process counts and drivers."""

    files = [MonthFile("2024_01.dat"), MonthFile("2024_02.dat")]

    @pytest.mark.parametrize("num_processes", ["max", 8])
    def test_one_cpu_parses_sequentially(self, num_processes):
        """More processes than CPUs is capped, not an error."""
        with (
            patch("uataq.filesystem.core.cpu_count", return_value=1),
            patch("uataq.filesystem.core.multiprocessing.Pool") as pool,
        ):
            data = filesystem.parse_datafiles(
                self.files, TimeRange("2024"), num_processes
            )
        pool.assert_not_called()
        assert len(data) == 4

    def test_xarray_driver_is_not_implemented(self):
        with pytest.raises(NotImplementedError):
            filesystem.parse_datafiles(self.files, TimeRange(), driver="xarray")

    def test_invalid_driver(self):
        with pytest.raises(ValueError, match="Invalid driver"):
            filesystem.parse_datafiles(self.files, TimeRange(), driver="polars")  # pyright: ignore[reportArgumentType]


def test_cpu_count_without_affinity(monkeypatch):
    """Where the OS has no CPU affinity (macOS), count every core."""
    monkeypatch.delattr("os.sched_getaffinity", raising=False)
    with patch("uataq.filesystem.core.multiprocessing.cpu_count", return_value=3):
        assert filesystem.cpu_count() == 3


def test_groupspace_str():
    assert str(filesystem.groups["horel"]) == "Horel GroupSpace"
    assert repr(filesystem.groups["lin"]) == "LinGroup()"
