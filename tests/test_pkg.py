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

import importlib.metadata
import json
from unittest.mock import MagicMock, patch

import pytest

import uataq
from uataq import sites
from uataq._laboratory import Laboratory


class TestPackageMetadata:
    """Test basic package metadata."""

    def test_version(self):
        """Test that version is defined."""
        assert hasattr(uataq, "__version__")
        assert isinstance(uataq.__version__, str)
        assert len(uataq.__version__) > 0
        # the installed distribution's version (setuptools-scm, from git tags)
        assert uataq.__version__ == importlib.metadata.version("uataq")

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


class TestTopLevelHelpers:
    """The module-level functions hand every argument to the right place."""

    @pytest.fixture
    def site(self):
        site = MagicMock()
        with patch.object(uataq, "get_site", return_value=site) as get_site:
            yield site
            get_site.assert_called_once_with("WBB")

    def test_read_data(self, site):
        out = uataq.read_data(
            "WBB",
            instruments="lgr_ugga",
            group="lin",
            lvl="final",
            time_range="2024-06",
            num_processes=2,
            file_pattern="2024_06",
        )
        site.read_data.assert_called_once_with(
            "lgr_ugga", "lin", "final", "2024-06", 2, "2024_06"
        )
        assert out is site.read_data.return_value

    def test_get_obs(self, site):
        out = uataq.get_obs(
            "WBB",
            pollutants=["CO2"],
            format="long",
            group="lin",
            time_range="2024-06",
            num_processes=3,
            include_gps=False,
        )
        site.get_obs.assert_called_once_with(
            ["CO2"], "long", "lin", "2024-06", 3, include_gps=False
        )
        assert out is site.get_obs.return_value

    def test_get_recent_obs(self, site):
        out = uataq.get_recent_obs(
            "WBB", recent="2D", pollutants="CO2", format="long", group="lin"
        )
        site.get_recent_obs.assert_called_once_with("2D", "CO2", "long", "lin")
        assert out is site.get_recent_obs.return_value

    def test_get_network_obs(self):
        with patch.object(uataq.Network, "get_obs") as get_obs:
            out = uataq.get_network_obs(
                ["wbb"], "co2", time_range="2024-06", group="lin", num_processes=4
            )
        get_obs.assert_called_once_with(time_range="2024-06", num_processes=4)
        assert out is get_obs.return_value

    def test_get_network_obs_builds_the_network(self):
        built = []

        def get_obs(self, time_range=None, num_processes=1):
            built.append(self)

        with patch.object(uataq.Network, "get_obs", get_obs):
            uataq.get_network_obs(["wbb"], "co2", group="lin")
        (net,) = built
        assert (net.sites, net.pollutant, net.group) == (["WBB"], "CO2", "lin")


class TestLaboratory:
    """Building sites from a configuration."""

    config = {
        "TST": {
            "name": "Test",
            "latitude": 40.0,
            "longitude": -111.0,
            "loggers": {"lin": "campbellsci"},
            "instruments": {"lgr_ugga": {"installation_date": "2020-01-01"}},
        },
        "MOB": {
            "is_mobile": True,
            "instruments": {"gps": {"loggers": {"horel": "campbellsci"}}},
        },
        "NONE": {"name": "No instruments"},
    }

    def test_from_a_file(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps(self.config))
        lab = Laboratory(str(path))
        assert lab.config == self.config
        assert lab.sites == ["TST", "MOB", "NONE"]
        assert sorted(lab.instruments) == ["gps", "lgr_ugga"]

    def test_invalid_config(self):
        with pytest.raises(ValueError, match="file path or dictionary"):
            Laboratory(["TST"])  # pyrefly: ignore[bad-argument-type]

    def test_site_class_and_config(self):
        lab = Laboratory(self.config)
        site = lab.get_site("tst")
        assert type(site) is sites.Site
        assert site.SID == "TST"
        # loggers and instruments move into the ensemble
        assert "instruments" not in site.config and "loggers" not in site.config
        assert site.instruments["lgr_ugga"].groups == ["lin"]
        assert isinstance(lab.get_site("MOB"), sites.MobileSite)

    def test_get_site_does_not_change_the_config(self):
        lab = Laboratory(self.config)
        lab.get_site("TST")
        assert lab.config["TST"]["instruments"] == self.config["TST"]["instruments"]

    def test_unknown_site(self):
        with pytest.raises(ValueError, match="'XYZ' not found"):
            Laboratory(self.config).get_site("xyz")

    def test_site_without_instruments(self):
        with pytest.raises(ValueError, match="No instruments found for site 'NONE'"):
            Laboratory(self.config).get_site("NONE")

    def test_str(self):
        assert str(Laboratory(self.config)) == "UATAQ Laboratory"
