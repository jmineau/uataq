"""
Tests for the Network class.
"""

import geopandas as gpd
import pandas as pd
import pytest

from uataq import Network


class TestNetworkInitialization:
    """Test Network initialization and validation."""

    def test_network_single_stationary_site(self):
        """Test creating a Network with a single stationary site."""
        net = Network(sites=["WBB"], pollutant="CO2")
        assert net.pollutant == "CO2"
        assert len(net.site_objects) == 1
        assert net.site_objects[0].SID == "WBB"

    def test_network_multiple_sites(self):
        """Test creating a Network with multiple sites."""
        net = Network(sites=["WBB", "SUG", "RPK"], pollutant="CO2")
        assert net.pollutant == "CO2"
        assert len(net.site_objects) == 3
        site_sids = {site.SID for site in net.site_objects}
        assert site_sids == {"WBB", "SUG", "RPK"}

    def test_network_case_insensitive(self):
        """Test that site and pollutant names are case-insensitive."""
        net = Network(sites=["wbb", "sug"], pollutant="co2")
        assert net.pollutant == "CO2"
        assert net.sites == ["WBB", "SUG"]

    def test_network_empty_sites_list(self):
        """Test that empty sites list raises ValueError."""
        with pytest.raises(ValueError, match="sites cannot be empty"):
            Network(sites=[], pollutant="CO2")

    def test_network_site_not_found(self):
        """Test that non-existent site is skipped with warning."""
        net = Network(sites=["NONEXISTENT", "WBB"], pollutant="CO2")
        # Should only have WBB in the valid sites
        assert len(net.site_objects) == 1
        assert net.site_objects[0].SID == "WBB"

    def test_network_pollutant_not_measured(self):
        """Test that sites not measuring the pollutant are excluded."""
        # ASB measures different pollutants than CO2
        net = Network(sites=["ASB", "WBB"], pollutant="CO2")
        # Only WBB should be included
        assert len(net.site_objects) >= 1
        assert any(site.SID == "WBB" for site in net.site_objects)

    def test_network_no_valid_sites(self):
        """Test that error is raised if no sites measure the pollutant."""
        with pytest.raises(ValueError, match="No sites found"):
            Network(sites=["NONEXISTENT"], pollutant="CO2")


class TestNetworkDataRetrieval:
    """Test Network data retrieval."""

    def test_get_obs_returns_geodataframe(self):
        """Test that get_obs returns a GeoDataFrame."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        assert isinstance(obs, gpd.GeoDataFrame)

    def test_geodataframe_has_required_columns(self):
        """Test that returned GeoDataFrame has required columns."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        
        required_columns = {"SID", "Latitude_deg", "Longitude_deg", "zagl", "geometry"}
        assert required_columns.issubset(set(obs.columns))

    def test_geodataframe_has_correct_crs(self):
        """Test that GeoDataFrame has correct CRS."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        assert obs.crs == "EPSG:4326"

    def test_time_index(self):
        """Test that returned DataFrame has Time_UTC as index."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        assert obs.index.name == "Time_UTC"
        assert pd.api.types.is_datetime64_any_dtype(obs.index)

    def test_stationary_site_constant_coordinates(self):
        """Test that stationary site has constant coordinates."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        
        # WBB is stationary, so all rows should have the same coordinates
        assert obs["Latitude_deg"].nunique() == 1
        assert obs["Longitude_deg"].nunique() == 1

    def test_sid_column_present(self):
        """Test that SID column distinguishes sites."""
        net = Network(sites=["WBB", "SUG"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        
        assert "SID" in obs.columns
        site_ids = obs["SID"].unique()
        assert len(site_ids) == 2

    def test_pollutant_column_present(self):
        """Test that pollutant columns are present in result."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range="2024-01-01")
        
        # At least one column should contain CO2
        co2_cols = [col for col in obs.columns if "CO2" in col.upper()]
        assert len(co2_cols) > 0

    def test_time_range_filtering(self):
        """Test that time_range parameter filters data correctly."""
        net = Network(sites=["WBB"], pollutant="CO2")
        obs = net.get_obs(time_range=["2024-01-01", "2024-01-02"])
        
        # Check that all timestamps are within range
        assert obs.index.min() >= pd.Timestamp("2024-01-01")
        # The end of the day on 2024-01-02 is included (23:59:58)
        assert obs.index.max() < pd.Timestamp("2024-01-03")

    def test_num_processes_parameter(self):
        """Test that num_processes parameter is accepted."""
        net = Network(sites=["WBB"], pollutant="CO2")
        # Just test that it doesn't error
        obs = net.get_obs(time_range="2024-01-01", num_processes=2)
        assert isinstance(obs, gpd.GeoDataFrame)


class TestNetworkReprAndStr:
    """Test Network string representations."""

    def test_repr(self):
        """Test __repr__ method."""
        net = Network(sites=["WBB"], pollutant="CO2")
        repr_str = repr(net)
        assert "Network" in repr_str
        assert "CO2" in repr_str
        assert "WBB" in repr_str

    def test_str(self):
        """Test __str__ method."""
        net = Network(sites=["WBB"], pollutant="CO2")
        str_str = str(net)
        assert "Network" in str_str
        assert "CO2" in str_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
