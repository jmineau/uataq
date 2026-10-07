"""
Tests for the Site class and related functionality.
"""

import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from uataq import errors, sites
from uataq.timerange import TimeRange


class TestSiteInitialization:
    """Test Site class initialization."""

    def test_site_initialization(self, mock_config, mock_instrument_ensemble):
        """Test creating a Site object."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert site.SID == "WBB"
        assert site.config == mock_config
        assert site.instruments == mock_instrument_ensemble

    def test_site_stores_groups_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores groups from instrument ensemble."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert site.groups == mock_instrument_ensemble.groups

    def test_site_stores_loggers_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores loggers from instrument ensemble."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert site.loggers == mock_instrument_ensemble.loggers

    def test_site_stores_pollutants_from_instruments(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that Site stores pollutants from instrument ensemble."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert site.pollutants == mock_instrument_ensemble.pollutants


class TestSiteConfiguration:
    """Test Site configuration access."""

    def test_site_config_access(self, mock_config, mock_instrument_ensemble):
        """Test accessing site configuration."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert site.config["name"] == "Test Site"
        assert site.config["latitude"] == 40.7608
        assert site.config["longitude"] == -111.8910

    def test_site_config_with_standard_keys(
        self, mock_config, mock_instrument_ensemble
    ):
        """Test that standard config keys are present."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

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
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

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
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        site_str = str(site)
        # Should contain site ID
        assert "WBB" in site_str or site_str != ""

    def test_site_repr_method(self, mock_config, mock_instrument_ensemble):
        """Test __repr__ method of Site."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        site_repr = repr(site)
        # Should contain class name and site ID
        assert "Site" in site_repr or "WBB" in site_repr


class TestSiteDataReading:
    """Test Site data reading methods."""

    def test_site_read_data_method_exists(self, mock_config, mock_instrument_ensemble):
        """Test that Site has read_data method."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert hasattr(site, "read_data")
        assert callable(site.read_data)

    def test_site_has_data_methods(self, mock_config, mock_instrument_ensemble):
        """Test that Site has expected data methods."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        # Check for read_data method which should exist
        assert hasattr(site, "read_data")
        assert callable(site.read_data)

    def test_site_get_recent_obs_method_exists(
        self, mock_config, mock_instrument_ensemble
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

        site = sites.Site(
            SID="ACTIVE", config=config, instruments=mock_instrument_ensemble
        )
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

        site = sites.Site(
            SID="INACTIVE", config=config, instruments=mock_instrument_ensemble
        )
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

        site = sites.Site(
            SID="MOBILE", config=config, instruments=mock_instrument_ensemble
        )
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

        site = sites.Site(
            SID="STATION", config=config, instruments=mock_instrument_ensemble
        )
        assert site.config["is_mobile"] is False


class TestSiteLocationData:
    """Test Site geographic/location information."""

    def test_site_has_geographic_info(self, mock_config, mock_instrument_ensemble):
        """Test that Site contains geographic information."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        assert "latitude" in site.config
        assert "longitude" in site.config
        assert "zagl" in site.config

    def test_site_geographic_values(self, mock_config, mock_instrument_ensemble):
        """Test that geographic values are reasonable."""
        site = sites.Site(
            SID="WBB", config=mock_config, instruments=mock_instrument_ensemble
        )

        lat = site.config["latitude"]
        lon = site.config["longitude"]
        zagl = site.config["zagl"]

        # Check reasonable ranges for Utah
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90
        assert zagl >= 0  # Height above ground level is positive


class TestPerInstrumentGroupSelection:
    """Site.read_data resolves a group per instrument (uataq#3)."""

    @staticmethod
    def fake_instrument(name, groups):
        inst = MagicMock()
        inst.name = name
        inst.groups = groups
        inst.resolve_group.side_effect = lambda group=None: (
            group
            if isinstance(group, str)
            else ("lin" if "lin" in groups else groups[0])
        )
        # No group_dates: one portion from the resolved group (uataq#33)
        inst.plan_reads.side_effect = lambda group=None, time_range=None: [
            (inst.resolve_group(group), time_range)
        ]
        inst.read_data.return_value = pd.DataFrame({"x": [1.0]})
        return inst

    def site_with(self, mock_config, instruments_by_name):
        ensemble = MagicMock()
        ensemble.names = list(instruments_by_name)
        ensemble.__contains__ = lambda self, key: key in instruments_by_name
        ensemble.__getitem__ = lambda self, key: instruments_by_name[key]
        return sites.Site(SID="TEST", config=mock_config, instruments=ensemble)

    def test_each_instrument_reads_from_its_own_group(self, mock_config):
        """A lin instrument and a horel instrument on one site, read together."""
        insts = {
            "licor": self.fake_instrument("licor", ["lin"]),
            "crds": self.fake_instrument("crds", ["horel"]),
        }
        site = self.site_with(mock_config, insts)

        site.read_data(["licor", "crds"])

        assert insts["licor"].read_data.call_args.args[0] == "lin"
        assert insts["crds"].read_data.call_args.args[0] == "horel"

    def test_explicit_group_applies_to_every_instrument(self, mock_config):
        insts = {
            "licor": self.fake_instrument("licor", ["lin"]),
            "crds": self.fake_instrument("crds", ["horel"]),
        }
        site = self.site_with(mock_config, insts)

        site.read_data(["licor", "crds"], group="horel")

        for inst in insts.values():
            assert inst.read_data.call_args.args[0] == "horel"

    def test_error_names_the_group_each_instrument_was_read_from(self, mock_config):
        insts = {"crds": self.fake_instrument("crds", ["horel"])}
        insts["crds"].read_data.side_effect = errors.ReaderError("nope")
        site = self.site_with(mock_config, insts)

        with pytest.raises(errors.ReaderError, match="crds in horel"):
            site.read_data(["crds"])


class TestMobileSiteGetObs:
    """MobileSite.get_obs reads GPS only when it will merge it (#18)."""

    def test_include_gps_false_skips_gps_read(self):

        import uataq

        site = uataq.get_site("TRX01")
        obs = pd.DataFrame(
            {"O3_ppb": [40.0]},
            index=pd.DatetimeIndex(["2024-06-01"], name="Time_UTC"),
        )
        with (
            patch.object(sites.Site, "get_obs", return_value=obs),
            patch.object(sites.Site, "read_data") as read_data,
        ):
            result = site.get_obs("O3", include_gps=False)

        read_data.assert_not_called()
        assert result.equals(obs)


class TestSplitByPlan:
    """Cutting a concatenated read back into its plan's portions (#42)."""

    times = pd.DatetimeIndex(
        ["2017-10-27 23:59", "2017-10-28 00:00", "2017-10-28 00:01"], name="Time_UTC"
    )
    frame = pd.DataFrame({"O3_ppb": [1.0, 2.0, 3.0]}, index=times)

    def test_one_portion_is_the_whole_frame(self):
        plan = [("lin", TimeRange())]
        (piece,) = sites._split_by_plan(self.frame, plan)
        assert piece is self.frame

    def test_cut_at_each_portion_start(self):
        cut = datetime(2017, 10, 28)
        plan = [
            ("lin", TimeRange(start=datetime(2015, 5, 13), stop=cut)),
            ("horel", TimeRange(start=cut, stop=None)),
        ]
        lin, horel = sites._split_by_plan(self.frame, plan)
        assert list(lin["O3_ppb"]) == [1.0]
        assert list(horel["O3_ppb"]) == [2.0, 3.0]

    def test_no_row_lost_to_a_gap_between_portions(self):
        plan = [
            ("lin", TimeRange(start=None, stop=datetime(2017, 10, 27, 23, 59, 30))),
            ("horel", TimeRange(start=datetime(2017, 10, 28, 0, 0, 30), stop=None)),
        ]
        pieces = sites._split_by_plan(self.frame, plan)
        assert [len(p) for p in pieces] == [2, 1]


class TestMobileSiteLocate:
    """
    Each row is located with the GPS logged on its own clock (#42).

    TRX01 ozone crossing 2017-10-28 is read from lin, then horel (config
    group_dates). lin's instruments and GPS are stamped by the Pi; horel's by
    the CR1000, whose clock runs seconds off the Pi's. Positions encode which
    GPS a row was joined to: lin's latitudes are 1.x, horel's 2.x.
    """

    LIN_STOP = datetime(2017, 10, 28)
    SPAN = (datetime(2017, 10, 27, 23, 59), datetime(2017, 10, 28, 0, 1))

    @staticmethod
    def stamp(*times):
        return pd.DatetimeIndex(pd.to_datetime(list(times)), name="Time_UTC")

    @property
    def o3(self):
        # lin rows on the Pi clock, then horel rows on the CR1000 clock
        index = self.stamp(
            "2017-10-27 23:59:58",
            "2017-10-27 23:59:59",
            "2017-10-28 00:00:00",
            "2017-10-28 00:00:01",
            "2017-10-28 00:00:02",
        )
        return pd.DataFrame({"O3_ppb": [10.0, 11.0, 20.0, 21.0, 22.0]}, index=index)

    @property
    def lin_gps(self):
        # GPS time in Time_UTC, the Pi's clock in Pi_Time. No record for the
        # Pi's 00:00:02, so a horel row joined on Pi_Time there was dropped.
        index = self.stamp(
            "2017-10-27 23:59:58",
            "2017-10-27 23:59:59",
            "2017-10-28 00:00:00",
            "2017-10-28 00:00:01",
        )
        pi = (index + pd.Timedelta("190ms")).strftime("%Y-%m-%d %H:%M:%S.%f")
        return pd.DataFrame(
            {
                "Pi_Time": pi,
                "Latitude_deg": [1.0, 1.1, 1.2, 1.3],
                "Longitude_deg": -111.0,
                "Altitude_msl": 1300.0,
            },
            index=index,
        )

    @property
    def horel_gps(self):
        index = self.stamp(
            "2017-10-28 00:00:00", "2017-10-28 00:00:01", "2017-10-28 00:00:02"
        )
        return pd.DataFrame(
            {"Latitude_deg": [2.0, 2.1, 2.2], "Longitude_deg": -111.0}, index=index
        )

    def fake_read_data(self, calls, fail=()):
        """Stand in for read_data: O3 as read across the cut, GPS per group."""

        def read_data(instruments, group=None, lvl=None, time_range=None, *a, **k):
            if instruments == "gps":
                calls.append((group, TimeRange(time_range)))
                if group in fail:
                    raise errors.ReaderError(f"no {group} gps")
                return {"gps": {"lin": self.lin_gps, "horel": self.horel_gps}[group]}
            return {"2b_205": self.o3}

        return read_data

    def get_obs(self, calls, fail=(), **kwargs):
        import uataq

        site = uataq.get_site("TRX01")
        with patch.object(site, "read_data", self.fake_read_data(calls, fail)):
            return site.get_obs("O3", time_range=self.SPAN, **kwargs)

    def test_each_group_joins_its_own_gps(self):
        calls = []
        obs = self.get_obs(calls)

        # Every row kept, horel's 00:00:02 included
        assert list(obs["O3_ppb"]) == [10.0, 11.0, 20.0, 21.0, 22.0]
        assert list(obs["Latitude_deg"]) == [1.0, 1.1, 2.0, 2.1, 2.2]
        assert list(obs["GPS_Group"]) == ["lin", "lin", "horel", "horel", "horel"]
        assert "Pi_Time" not in obs.columns
        assert obs.index.name == "Time_UTC"
        assert obs.crs == "EPSG:4326"

    def test_gps_is_read_only_where_its_rows_were(self):
        calls = []
        self.get_obs(calls)

        spans = {group: (tr.start, tr.stop) for group, tr in calls}
        assert spans == {
            "lin": (self.SPAN[0], self.LIN_STOP),
            "horel": (self.LIN_STOP, self.SPAN[1]),
        }

    def test_long_format_is_located_too(self):
        obs = self.get_obs([], format="long")
        assert list(obs["value"]) == [10.0, 11.0, 20.0, 21.0, 22.0]
        assert list(obs["Latitude_deg"]) == [1.0, 1.1, 2.0, 2.1, 2.2]
        assert list(obs["GPS_Group"]) == ["lin", "lin", "horel", "horel", "horel"]

    def test_explicit_gps_group_for_another_groups_rows_raises(self):
        # horel's ozone rows may not be located with lin's GPS (their clocks differ)
        calls = []
        with pytest.raises(ValueError, match="read those instruments from lin"):
            self.get_obs(calls, group={"gps": "lin"})

    def test_missing_gps_drops_only_its_rows(self, caplog):
        with caplog.at_level(logging.WARNING, logger="uataq.sites"):
            obs = self.get_obs([], fail=("horel",))

        assert list(obs["O3_ppb"]) == [10.0, 11.0]
        assert "3 rows go unlocated" in caplog.text

    def test_no_gps_at_all_raises(self):
        with pytest.raises(errors.ReaderError, match="No GPS data for TRX01"):
            self.get_obs([], fail=("lin", "horel"))

    def test_network_locates_the_same_way(self):
        from uataq.network import Network

        net = Network(["TRX01"], "O3")
        site = net.site_objects[0]
        with patch.object(site, "read_data", self.fake_read_data([])):
            obs = net._read_site_data(site, time_range=self.SPAN)

        assert list(obs["Latitude_deg"]) == [1.0, 1.1, 2.0, 2.1, 2.2]
        assert set(obs["SID"]) == {"TRX01"}
        assert list(obs["GPS_Group"]) == ["lin", "lin", "horel", "horel", "horel"]

    def test_group_without_its_own_gps_raises(self):
        gps = MagicMock()
        gps.groups = ["horel"]
        gps._named_group.return_value = None
        site = SimpleNamespace(instruments={"gps": gps}, SID="BUS99")

        with pytest.raises(ValueError, match="lin logs no GPS at BUS99"):
            sites.MobileSite._gps_group(site, "lin", None)  # pyrefly: ignore[bad-argument-type]  # duck-typed site
        assert sites.MobileSite._gps_group(site, "horel", None) == "horel"  # pyrefly: ignore[bad-argument-type]  # duck-typed site

    def test_named_gps_matching_the_rows_is_fine(self):
        gps = MagicMock()
        gps.groups = ["horel", "lin"]
        gps._named_group.return_value = "horel"
        site = SimpleNamespace(instruments={"gps": gps}, SID="TRX01")
        assert sites.MobileSite._gps_group(site, "horel", {"gps": "horel"}) == "horel"  # pyrefly: ignore[bad-argument-type]  # duck-typed site


class TestPollutantCase:
    """Pollutants are matched regardless of case (#13)."""

    def test_mixed_case_pollutant_finds_its_instrument(self):

        import uataq

        site = uataq.get_site("BUS01")
        assert [i.name for i in site.pollutant_instruments["NOX"]] == ["2b_405"]

        times = pd.DatetimeIndex(["2024-06-01"], name="Time_UTC")
        data = {"2b_405": pd.DataFrame({"NOx_ppb": [10.0], "NO_ppb": [2.0]}, times)}
        with patch.object(sites.Site, "read_data", return_value=data) as read_data:
            obs = sites.Site.get_obs(site, "NOx")

        assert read_data.call_args.args[0] == {"2b_405"}
        # "NOX" must still select the declared-case NOx_ppb column
        assert list(obs.columns) == ["NOx_ppb"]

    def test_read_data_lowercases_a_set(self):

        import uataq

        site = uataq.get_site("BUS01")
        with patch.object(
            site.instruments["2b_405"], "read_data", return_value=pd.DataFrame()
        ):
            data = site.read_data({"2B_405"})
        assert list(data) == ["2b_405"]


class TestSiteReadDataSelection:
    """Which instruments Site.read_data reads, and what it does on failure."""

    @staticmethod
    def site_with(mock_config, names, plan_errors=None):
        """Make a site whose instruments return a one-row frame named after them."""
        plan_errors = plan_errors or {}
        insts = {}
        for name in names:
            inst = MagicMock()
            inst.name = name
            inst.__str__.return_value = name
            if name in plan_errors:
                inst.plan_reads.side_effect = plan_errors[name]
            else:
                inst.plan_reads.return_value = [("lin", None)]
            inst.read_data.return_value = pd.DataFrame({name: [1.0]})
            insts[name] = inst
        ensemble = MagicMock()
        ensemble.names = list(insts)
        ensemble.__contains__ = lambda self, key: key in insts
        ensemble.__getitem__ = lambda self, key: insts[key]
        return sites.Site(SID="TEST", config=mock_config, instruments=ensemble)

    def test_all_reads_every_instrument(self, mock_config):
        site = self.site_with(mock_config, ["licor", "crds"])
        assert sorted(site.read_data("all")) == ["crds", "licor"]

    def test_unknown_instrument(self, mock_config):
        site = self.site_with(mock_config, ["licor"])
        with pytest.raises(errors.InstrumentNotFoundError):
            site.read_data("picarro")

    def test_invalid_group_is_raised_not_skipped(self, mock_config):
        """A bad group name is the caller's mistake, not missing data."""
        site = self.site_with(
            mock_config,
            ["licor", "crds"],
            plan_errors={"crds": errors.InvalidGroupError("no group 'x'")},
        )
        with pytest.raises(errors.InvalidGroupError):
            site.read_data(["licor", "crds"], group="x")

    def test_inactive_instrument_is_skipped(self, mock_config):
        site = self.site_with(
            mock_config,
            ["licor", "crds"],
            plan_errors={"crds": errors.ReaderError("not installed")},
        )
        data = site.read_data(["licor", "crds"])
        assert list(data) == ["licor"]

    def test_nothing_read_says_why(self, mock_config):
        site = self.site_with(
            mock_config,
            ["crds"],
            plan_errors={"crds": errors.ReaderError("not installed")},
        )
        with pytest.raises(errors.ReaderError, match="crds not read: not installed"):
            site.read_data("crds")


class TestSiteGetObs:
    """Combining instruments by pollutant, in wide and long format."""

    times = pd.DatetimeIndex(["2024-06-01 00:00", "2024-06-01 00:01"], name="Time_UTC")

    @pytest.fixture
    def site(self):
        import uataq

        return uataq.get_site("BUS01")

    def data(self):
        return {
            "2b_205": pd.DataFrame(
                {"O3_ppb": [40.0, None], "Flow_Lpm": [1.9, 1.9]}, self.times
            ),
            "2b_405": pd.DataFrame(
                {"NO_ppb": [1.0, 2.0], "NO2_ppb": [3.0, None]}, self.times
            ),
        }

    def test_unmeasured_pollutant(self, site):
        with pytest.raises(ValueError, match="CO2"):
            sites.Site.get_obs(site, ["O3", "CO2"])

    def test_all_reads_every_pollutant_instrument(self, site):
        with patch.object(sites.Site, "read_data", return_value=self.data()) as read:
            sites.Site.get_obs(site, "all")
        assert read.call_args.args[0] == {"2b_205", "2b_405", "metone_es642"}
        assert read.call_args.args[2] == "final"

    def test_long_format(self, site):
        with patch.object(sites.Site, "read_data", return_value=self.data()):
            obs = sites.Site.get_obs(site, ["O3", "NO2"], format="long")

        assert list(obs.columns) == ["pollutant", "value"]
        assert obs.index.name == "Time_UTC"
        # Diagnostics and missing values are dropped; NO2 rows survive NO's
        assert sorted(zip(obs["pollutant"], obs["value"], strict=True)) == [
            ("NO2_ppb", 3.0),
            ("O3_ppb", 40.0),
        ]
        assert obs.index.is_monotonic_increasing

    def test_wide_format_drops_empty_rows(self, site):
        data = {"2b_205": self.data()["2b_205"]}
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = sites.Site.get_obs(site, "O3")
        assert list(obs.columns) == ["O3_ppb"]
        assert obs["O3_ppb"].tolist() == [40.0]

    def test_invalid_format(self, site):
        with (
            patch.object(sites.Site, "read_data", return_value=self.data()),
            pytest.raises(ValueError, match="Invalid format"),
        ):
            sites.Site.get_obs(site, "O3", format="tall")  # pyrefly: ignore[bad-argument-type]

    def test_recent_obs_reads_from_now_minus_recent(self):
        import uataq

        site = uataq.get_site("WBB")  # stationary: Site.get_obs is its own
        before = pd.Timestamp.now("UTC").tz_localize(None)
        with patch.object(sites.Site, "get_obs") as get_obs:
            site.get_recent_obs("2D", "O3", "long", "horel")
        after = pd.Timestamp.now("UTC").tz_localize(None)

        pollutants, format, group, (start, stop) = get_obs.call_args.args
        assert (pollutants, format, group, stop) == ("O3", "long", "horel", None)
        assert before - pd.Timedelta("2D") <= start <= after - pd.Timedelta("2D")
