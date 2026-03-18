"""
Tests for filesystem utilities.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uataq import filesystem


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
        files_lower = filesystem.list_files(path=raw_dir, pattern="*.dat", ignore_case=False)
        files_upper = filesystem.list_files(path=raw_dir, pattern="*.DAT", ignore_case=True)

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
