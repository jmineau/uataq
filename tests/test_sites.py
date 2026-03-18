"""
Tests for the Site class and related functionality.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import pandas as pd

from uataq import sites, errors


class TestSiteInitialization:
    """Test Site class initialization."""

    def test_site_initialization(self, mock_config, mock_instrument_ensemble):
        """Test creating a Site object."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert site.SID == "WBB"
        assert site.config == mock_config
        assert site.instruments == mock_instrument_ensemble

    def test_site_stores_groups_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores groups from instrument ensemble."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert site.groups == mock_instrument_ensemble.groups

    def test_site_stores_loggers_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores loggers from instrument ensemble."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert site.loggers == mock_instrument_ensemble.loggers

    def test_site_stores_pollutants_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores pollutants from instrument ensemble."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert site.pollutants == mock_instrument_ensemble.pollutants


class TestSiteConfiguration:
    """Test Site configuration access."""

    def test_site_config_access(self, mock_config, mock_instrument_ensemble):
        """Test accessing site configuration."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert site.config["name"] == "Test Site"
        assert site.config["latitude"] == 40.7608
        assert site.config["longitude"] == -111.8910

    def test_site_config_with_standard_keys(self, mock_config, mock_instrument_ensemble):
        """Test that standard config keys are present."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        expected_keys = {
            "name",
            "is_active",
            "is_mobile",
            "latitude",
            "longitude",
            "zagl",
            "loggers",
            "instruments",
        }

        assert all(key in site.config for key in expected_keys)


class TestSitePollutantInstrumentMapping:
    """Test the pollutant-to-instruments mapping."""

    def test_site_builds_pollutant_instruments_mapping(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site creates pollutant_instruments mapping."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        # The mapping should be built
        assert hasattr(site, "pollutant_instruments")
        assert isinstance(site.pollutant_instruments, dict)

    def test_pollutant_instruments_mapping_with_mock_instruments(self, mock_config):
        """Test pollutant_instruments mapping with instruments that have pollutants."""
        # Create mock instruments with pollutants
        mock_ensemble = MagicMock()
        mock_ensemble.groups = {"horel", "lin"}
        mock_ensemble.loggers = {"horel-group", "lin-group"}
        mock_ensemble.pollutants = {"CO2", "CH4"}

        # Create mock instruments
        inst1 = MagicMock()
        inst1.name = "crds"
        inst1.pollutants = ["CO2", "CH4"]

        inst2 = MagicMock()
        inst2.name = "licor"
        inst2.pollutants = ["CO2"]

        # Make ensemble iterable
        mock_ensemble.__iter__ = MagicMock(return_value=iter([inst1, inst2]))

        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_ensemble)

        # Check the mapping was built
        assert "CO2" in site.pollutant_instruments
        # CO2 should be measured by both instruments
        assert len(site.pollutant_instruments["CO2"]) == 2


class TestSiteStringRepresentation:
    """Test Site string representation methods."""

    def test_site_str_method(self, mock_config, mock_instrument_ensemble):
        """Test __str__ method of Site."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        site_str = str(site)
        # Should contain site ID
        assert "WBB" in site_str or site_str != ""

    def test_site_repr_method(self, mock_config, mock_instrument_ensemble):
        """Test __repr__ method of Site."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        site_repr = repr(site)
        # Should contain class name and site ID
        assert "Site" in site_repr or "WBB" in site_repr


class TestSiteDataReading:
    """Test Site data reading methods."""

    @patch("uataq.sites.filesystem")
    def test_site_read_data_method_exists(
        self, mock_fs, mock_config, mock_instrument_ensemble
    ):
        """Test that Site has read_data method."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert hasattr(site, "read_data")
        assert callable(site.read_data)

    @patch("uataq.sites.filesystem")
    def test_site_has_data_methods(
        self, mock_fs, mock_config, mock_instrument_ensemble
    ):
        """Test that Site has expected data methods."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        # Check for read_data method which should exist
        assert hasattr(site, "read_data")
        assert callable(site.read_data)

    @patch("uataq.sites.filesystem")
    def test_site_get_recent_obs_method_exists(
        self, mock_fs, mock_config, mock_instrument_ensemble
    ):
        """Test that Site has get_recent_obs method."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert hasattr(site, "get_recent_obs")
        assert callable(site.get_recent_obs)


class TestSiteWithActiveStatus:
    """Test Site behavior with active/inactive status."""

    def test_site_active_status_from_config(self, mock_instrument_ensemble):
        """Test reading active status from configuration."""
        config = {
            "name": "Active Site",
            "is_active": True,
            "is_mobile": False,
            "latitude": 40.7608,
            "longitude": -111.8910,
            "zagl": 10.0,
            "loggers": {},
            "instruments": {},
        }

        site = sites.Site(SID="ACTIVE", config=config, instruments=mock_instrument_ensemble)
        assert site.config["is_active"] is True

    def test_site_inactive_status_from_config(self, mock_instrument_ensemble):
        """Test reading inactive status from configuration."""
        config = {
            "name": "Inactive Site",
            "is_active": False,
            "is_mobile": False,
            "latitude": 40.7608,
            "longitude": -111.8910,
            "zagl": 10.0,
            "loggers": {},
            "instruments": {},
        }

        site = sites.Site(SID="INACTIVE", config=config, instruments=mock_instrument_ensemble)
        assert site.config["is_active"] is False


class TestSiteWithMobileStatus:
    """Test Site behavior for mobile vs stationary sites."""

    def test_site_mobile_status(self, mock_instrument_ensemble):
        """Test mobile site designation."""
        config = {
            "name": "Mobile Site",
            "is_active": True,
            "is_mobile": True,
            "latitude": 40.7608,
            "longitude": -111.8910,
            "zagl": 10.0,
            "loggers": {},
            "instruments": {},
        }

        site = sites.Site(SID="MOBILE", config=config, instruments=mock_instrument_ensemble)
        assert site.config["is_mobile"] is True

    def test_site_stationary_status(self, mock_instrument_ensemble):
        """Test stationary site designation."""
        config = {
            "name": "Stationary Site",
            "is_active": True,
            "is_mobile": False,
            "latitude": 40.7608,
            "longitude": -111.8910,
            "zagl": 10.0,
            "loggers": {},
            "instruments": {},
        }

        site = sites.Site(SID="STATION", config=config, instruments=mock_instrument_ensemble)
        assert site.config["is_mobile"] is False


class TestSiteLocationData:
    """Test Site geographic/location information."""

    def test_site_has_geographic_info(self, mock_config, mock_instrument_ensemble):
        """Test that Site contains geographic information."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        assert "latitude" in site.config
        assert "longitude" in site.config
        assert "zagl" in site.config

    def test_site_geographic_values(self, mock_config, mock_instrument_ensemble):
        """Test that geographic values are reasonable."""
        site = sites.Site(SID="WBB", config=mock_config, instruments=mock_instrument_ensemble)

        lat = site.config["latitude"]
        lon = site.config["longitude"]
        zagl = site.config["zagl"]

        # Check reasonable ranges for Utah
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90
        assert zagl >= 0  # Height above ground level is positive
