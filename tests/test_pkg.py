"""
Basic package tests for uataq.

This module contains foundational tests for the package.
Additional organized tests are in:
- test_timerange.py: TimeRange class tests
- test_errors.py: Custom exception tests
- test_filesystem.py: Filesystem utilities tests
- test_instruments.py: Instrument class tests
- test_sites.py: Site class tests
- test_integration.py: Integration and API tests
"""

import uataq


class TestPackageMetadata:
    """Test basic package metadata."""

    def test_version(self):
        """Test that version is defined."""
        assert hasattr(uataq, "__version__")
        assert isinstance(uataq.__version__, str)
        assert len(uataq.__version__) > 0

    def test_author(self):
        """Test that author is defined."""
        assert hasattr(uataq, "__author__")
        assert isinstance(uataq.__author__, str)
        assert len(uataq.__author__) > 0

    def test_email(self):
        """Test that email is defined."""
        assert hasattr(uataq, "__email__")
        assert isinstance(uataq.__email__, str)
        assert "@" in uataq.__email__

    def test_version_format(self):
        """Test that version follows expected format."""
        version = uataq.__version__
        # Should be semantic versioning like "2025.11.0"
        parts = version.split(".")
        assert len(parts) >= 2
        # Each part should be numeric or at least start with a digit
        for part in parts[:2]:  # At least year and month/feature
            assert part[0].isdigit()


class TestPackageStructure:
    """Test that package has expected structure."""

    def test_has_filesystem_module(self):
        """Test filesystem module is available."""
        assert hasattr(uataq, "filesystem")

    def test_has_instruments_module(self):
        """Test instruments module is available."""
        assert hasattr(uataq, "instruments")

    def test_has_sites_module(self):
        """Test sites module is available."""
        assert hasattr(uataq, "sites")

    def test_has_timerange_class(self):
        """Test TimeRange class is available."""
        assert hasattr(uataq, "TimeRange")
        assert callable(uataq.TimeRange)

    def test_has_errors_module(self):
        """Test errors module is accessible."""
        from uataq import errors

        assert hasattr(errors, "InactiveInstrumentError")


class TestPublicAPI:
    """Test public API functions."""

    def test_read_data_exists(self):
        """Test read_data function exists."""
        assert hasattr(uataq, "read_data")
        assert callable(uataq.read_data)

    def test_get_site_exists(self):
        """Test get_site function exists."""
        assert hasattr(uataq, "get_site")
        assert callable(uataq.get_site)

    def test_laboratory_exists(self):
        """Test laboratory object exists."""
        assert hasattr(uataq, "laboratory")
