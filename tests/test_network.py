"""
Tests for the Network class.
"""

import logging
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
import pytest

from uataq import Network, errors, get_site, instruments, sites
from uataq.network import _datafile_coverage
from uataq.timerange import TimeRange


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


class TestNetworkGroupSelection:
    """Network reads let each instrument pick its own group (#14)."""

    times = pd.date_range("2024-06-01", periods=3, freq="s", name="Time_UTC")

    def fake_read_data(self, calls):
        """A Site.read_data stand-in that records the requested group."""

        def read_data(site, instruments, group=None, *args, **kwargs):
            instruments = [instruments] if isinstance(instruments, str) else instruments
            calls.append((site.SID, tuple(instruments), group))
            data = {}
            for name in instruments:
                if name == "gps":
                    data[name] = pd.DataFrame(
                        {"Latitude_deg": 40.7, "Longitude_deg": -111.9},
                        index=self.times,
                    )
                else:
                    data[name] = pd.DataFrame(
                        {"O3_ppb": 40.0, "NOx_ppb": 10.0}, index=self.times
                    )
            return data

        return read_data

    def test_horel_only_site_is_read(self):
        """BUS01 is horel-only; forcing the default group (lin) dropped it."""
        calls = []
        with patch.object(sites.Site, "read_data", self.fake_read_data(calls)):
            obs = Network(["BUS01"], "O3").get_obs(time_range="2024-06-01")

        assert len(obs) == len(self.times)
        assert set(obs["SID"]) == {"BUS01"}
        # None reaches Site.read_data, so each instrument resolves its own group
        assert all(group is None for _, _, group in calls)

    def test_explicit_group_is_passed_through(self):
        calls = []
        with patch.object(sites.Site, "read_data", self.fake_read_data(calls)):
            Network(["BUS01"], "O3", group="horel").get_obs()

        assert {group for _, _, group in calls} == {"horel"}

    def test_mixed_case_pollutant_finds_instruments(self):
        """Instruments declare "NOx"; the network stores "NOX" (#13)."""
        calls = []
        with patch.object(sites.Site, "read_data", self.fake_read_data(calls)):
            obs = Network(["BUS01"], "NOx").get_obs()

        assert ("BUS01", ("2b_405",), None) in calls
        assert "NOx_ppb" in obs.columns


class TestNetworkColumns:
    """Network obs keep concentrations only, one column per name (#13)."""

    times = pd.date_range("2024-06-01", periods=2, freq="s", name="Time_UTC")

    def test_two_instruments_stack_without_duplicate_columns(self):
        """TRX01's lgr_ugga and lgr_ugga_manual_cal both write CO2d_ppm_cal."""
        frame = {
            "CO2d_ppm_cal": [420.0, None],
            "CO2d_ppm_raw": [410.0, 421.0],
            "Cavity_P_torr": [140.0, 140.0],
        }
        data = {
            "lgr_ugga": pd.DataFrame(frame, index=self.times),
            "lgr_ugga_manual_cal": pd.DataFrame(frame, index=self.times),
        }
        net = Network(["WBB"], "CO2")
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = net._read_site_data(net.site_objects[0])

        assert obs.columns.is_unique
        assert {"CO2d_ppm_cal", "CO2d_ppm_raw", "instrument"} <= set(obs.columns)
        assert "Cavity_P_torr" not in obs.columns
        assert sorted(obs["instrument"].unique()) == ["lgr_ugga", "lgr_ugga_manual_cal"]
        assert len(obs) == 4

    def test_no_does_not_pick_up_no2(self):
        data = {
            "teledyne_t200": pd.DataFrame(
                {"NO_ppb": 1.0, "NO2_ppb": 2.0, "NOx_ppb": 3.0, "NO_Slope": 1.0},
                index=self.times,
            )
        }
        net = Network(["WBB"], "NO")
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = net._read_site_data(net.site_objects[0])

        assert [c for c in obs.columns if c.startswith("NO")] == ["NO_ppb"]


@pytest.mark.chpc
class TestNetworkDataRetrieval:
    """Test Network data retrieval.

    These read real observations through the lin groupspace, so they need the
    CHPC filesystem. Excluded from CI by ``-m "not chpc"``.
    """

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


class TestNetworkGetObsErrors:
    """A site that can't be read is skipped; no readable site is an error."""

    @staticmethod
    def frame(value):
        times = pd.date_range("2024-06-01", periods=2, freq="h", name="Time_UTC")
        return pd.DataFrame(
            {"CO2d_ppm_cal": value, "Latitude_deg": 40.7, "Longitude_deg": -111.8},
            index=times,
        )

    def test_unreadable_site_is_skipped(self, caplog):
        def read(self, site, time_range=None, num_processes=1):
            if site.SID == "SUG":
                raise errors.ReaderError("no files")
            return TestNetworkGetObsErrors.frame(420.0).assign(SID=site.SID)

        net = Network(["WBB", "SUG"], "CO2")
        with (
            patch.object(Network, "_read_site_data", read),
            caplog.at_level(logging.WARNING, logger="uataq"),
        ):
            obs = net.get_obs()

        assert set(obs["SID"]) == {"WBB"}
        assert "SUG" in caplog.text

    def test_no_readable_site(self):
        net = Network(["WBB", "SUG"], "CO2")
        with (
            patch.object(
                Network, "_read_site_data", side_effect=errors.ReaderError("none")
            ),
            pytest.raises(errors.ReaderError, match="No data found for CO2"),
        ):
            net.get_obs()


class TestReadSiteData:
    """One site's rows: concentrations, coordinates and height."""

    times = pd.date_range("2024-06-01", periods=2, freq="h", name="Time_UTC")

    def test_stationary_site_gets_its_configured_location(self):
        net = Network(["WBB"], "CO2")
        site = net.site_objects[0]
        data = {"lgr_ugga": pd.DataFrame({"CO2d_ppm_cal": [420.0, 421.0]}, self.times)}
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = net._read_site_data(site)

        assert (obs["Latitude_deg"] == site.config["latitude"]).all()
        assert (obs["Longitude_deg"] == site.config["longitude"]).all()
        assert (obs["zagl"] == site.config["zagl"]).all()
        assert (obs["SID"] == "WBB").all()
        assert obs["CO2d_ppm_cal"].tolist() == [420.0, 421.0]

    def test_site_without_the_pollutant(self):
        """BUS01 measures no CO2."""
        net = Network(["WBB"], "CO2")
        with pytest.raises(errors.ReaderError, match="No instruments at BUS01"):
            net._read_site_data(get_site("BUS01"))

    def test_instrument_data_without_concentrations(self):
        net = Network(["WBB"], "CO2")
        data = {"lgr_ugga": pd.DataFrame({"Cavity_P_torr": [140.0, 140.0]}, self.times)}
        with (
            patch.object(sites.Site, "read_data", return_value=data),
            pytest.raises(errors.ReaderError, match="No data columns found"),
        ):
            net._read_site_data(net.site_objects[0])

    def test_stationary_site_without_coordinates(self):
        net = Network(["WBB"], "CO2")
        site = net.site_objects[0]
        del site.config["latitude"]  # get_site hands out its own copy
        data = {"lgr_ugga": pd.DataFrame({"CO2d_ppm_cal": [420.0, 421.0]}, self.times)}
        with (
            patch.object(sites.Site, "read_data", return_value=data),
            pytest.raises(ValueError, match="missing latitude or longitude"),
        ):
            net._read_site_data(site)


class TestAvailabilityGroups:
    """Which archives get_availability looks in."""

    def groups_checked(self, monkeypatch, **network_kwargs) -> set[str]:
        calls = []

        def get_datafiles(self, group, lvl, time_range, pattern=None):
            calls.append(group)
            return []

        monkeypatch.setattr(instruments.Instrument, "get_datafiles", get_datafiles)
        Network(["TRX01"], "O3", **network_kwargs).get_availability(
            ["2016-01-01", "2016-01-02"], lvls=["raw"]
        )
        return set(calls)

    def test_every_operating_group_without_a_group(self, monkeypatch):
        """TRX01 ozone is in both the lin and horel archives."""
        assert self.groups_checked(monkeypatch) == {"lin", "horel"}

    def test_only_the_named_group(self, monkeypatch):
        assert self.groups_checked(monkeypatch, group="horel") == {"horel"}


def test_coverage_drops_rows_stamped_in_the_future(caplog):
    """A corrupt timestamp in the far future must not become a bin."""
    future = pd.Timestamp.now() + pd.Timedelta(days=400)
    data = pd.DataFrame(
        {
            "Time_UTC": [pd.Timestamp("2024-06-01 12:00"), future],
            "O3_ppb": [40.0, 41.0],
        }
    )
    datafile = MagicMock()
    datafile.parse.return_value = data
    instrument = MagicMock()
    instrument.standardize_data.side_effect = lambda group, data: data
    task = ("WBB", instrument, "lin", "raw", datafile, "O3", "D", TimeRange())

    with caplog.at_level(logging.WARNING, logger="uataq"):
        SID, lvl, bins = _datafile_coverage(task)

    assert (SID, lvl) == ("WBB", "raw")
    assert list(bins) == [pd.Period("2024-06-01", freq="D")]
    assert "after now" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
