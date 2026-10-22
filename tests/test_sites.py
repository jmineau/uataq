"""
Tests for the Site class and related functionality.
"""

import logging
import os
import subprocess
import sys
import textwrap
import warnings
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from uataq import errors, instruments, sites
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

        # lin's GPS reaches a margin further, for the Pi's clock (#94)
        margin = sites._PI_CLOCK_MARGIN
        spans = {group: (tr.start, tr.stop) for group, tr in calls}
        assert spans == {
            "lin": (self.SPAN[0] - margin, self.LIN_STOP + margin),
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


class TestLocateWithPiClockOff:
    """
    lin rows are located when the Pi's clock is off GPS time (#94).

    The join is on the Pi's clock, but a GPS read selects fixes by GPS time.
    On 2016-11-09 TRX01's Pi ran about 4,110 s behind GPS time, so the fixes
    of the rows in the last 4,110 s of a range have a GPS time past its end.
    """

    SPAN = (datetime(2016, 11, 9, 0), datetime(2016, 11, 9, 6))
    OFFSET = pd.Timedelta(seconds=4110)

    def gps(self):
        pi = pd.date_range("2016-11-08 22:00", "2016-11-09 08:00", freq="10min")
        return pd.DataFrame(
            {
                "Pi_Time": pi.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "Latitude_deg": 40.7,
                "Longitude_deg": -111.9,
            },
            index=pd.DatetimeIndex(pi + self.OFFSET, name="Time_UTC"),
        )

    def locate(self, calls):
        import uataq

        site = uataq.get_site("TRX01")
        gps = self.gps()

        def read_data(instruments, group=None, lvl=None, time_range=None, *a, **k):
            # Select fixes by GPS time, half-open, as a real read does
            start, stop = TimeRange(time_range)
            calls.append((start, stop))
            index = pd.DatetimeIndex(gps.index)
            return {"gps": gps[(index >= start) & (index < stop)]}

        # Rows on the Pi's clock, one every 10 minutes across the range
        pi = pd.date_range(*self.SPAN, freq="10min", inclusive="left")
        rows = pd.DataFrame(
            {"CH4d_ppm_cal": 2.0}, index=pd.DatetimeIndex(pi, name="Time_UTC")
        )
        with patch.object(site, "read_data", read_data):
            return rows, site.locate({"lgr_ugga": rows}, time_range=self.SPAN)

    def test_rows_near_the_end_are_located(self):
        rows, located = self.locate([])
        # 36 rows; the last 6 (Pi 05:00 on) have fixes past 06:00 GPS time
        assert len(located) == len(rows) == 36
        assert located.index.max() == pd.Timestamp("2016-11-09 06:58:30")

    def test_gps_read_reaches_the_margin(self):
        calls = []
        self.locate(calls)
        margin = sites._PI_CLOCK_MARGIN
        assert calls == [(self.SPAN[0] - margin, self.SPAN[1] + margin)]


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

        assert read_data.call_args.args[0] == ["2b_405"]
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
        # The config's order: BUS01 lists 2b_205, 2b_405, then metone_es642
        assert read.call_args.args[0] == ["2b_205", "2b_405", "metone_es642"]
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


class TestGetObsColumnOrder:
    """get_obs gives its columns in the same order in every session (#74)."""

    times = pd.DatetimeIndex(["2024-06-01 00:00", "2024-06-01 00:01"], name="Time_UTC")
    columns = {
        "2b_205": {"O3_ppb": [40.0, 41.0]},
        "2b_405": {"NO_ppb": [1.0, 2.0], "NO2_ppb": [3.0, 4.0]},
        "metone_es642": {"PM2.5_ugm3": [5.0, 6.0]},
    }

    @pytest.fixture
    def site(self):
        import uataq

        return uataq.get_site("BUS01")

    def read_data(self, instruments, group, lvl, time_range, num_processes):
        """Return a frame per instrument in the order asked, as Site.read_data does."""
        return {
            name: pd.DataFrame(self.columns[name], self.times) for name in instruments
        }

    @pytest.mark.parametrize(
        ("pollutants", "instruments"),
        [
            (["O3", "NO2"], ["2b_205", "2b_405"]),
            (["NO2", "O3"], ["2b_405", "2b_205"]),
            (("PM2.5", "NO", "O3"), ["metone_es642", "2b_405", "2b_205"]),
            # an instrument measuring two of them is read once, where it first appears
            (["NO", "O3", "NO2"], ["2b_405", "2b_205"]),
            (["no2", "o3"], ["2b_405", "2b_205"]),
            ("all", ["2b_205", "2b_405", "metone_es642"]),
            # a set has no order of its own, so it is sorted
            ({"O3", "NO2", "PM2.5"}, ["2b_405", "2b_205", "metone_es642"]),
        ],
    )
    def test_instruments_are_read_in_a_fixed_order(self, site, pollutants, instruments):
        with patch.object(
            sites.Site, "read_data", side_effect=self.read_data
        ) as read_data:
            obs = sites.Site.get_obs(site, pollutants)

        assert read_data.call_args.args[0] == instruments
        # The columns follow, instrument by instrument (those the pollutants match)
        expected = [c for name in instruments for c in self.columns[name]]
        assert list(obs.columns) == [c for c in expected if c in obs.columns]
        assert len(obs.columns) > 0

    def test_all_skips_a_pollutant_that_was_only_looked_up(self, site):
        """pollutant_instruments is a defaultdict: a miss leaves an empty key."""
        fresh = sites.Site(site.SID, site.config, site.instruments)
        assert fresh.pollutant_instruments["CO2"] == []  # BUS01 measures no CO2
        with patch.object(
            sites.Site, "read_data", side_effect=self.read_data
        ) as read_data:
            sites.Site.get_obs(fresh, "all")
        assert read_data.call_args.args[0] == ["2b_205", "2b_405", "metone_es642"]

    def test_order_does_not_depend_on_the_hash_seed(self):
        """Columns and rows on one timestamp are the same under four hash seeds."""
        code = textwrap.dedent(
            """
            from unittest.mock import patch

            import pandas as pd

            import uataq
            from uataq import sites

            site = uataq.get_site("WBB")
            times = pd.DatetimeIndex(["2024-06-01"], name="Time_UTC")


            def read_data(instruments, group, lvl, time_range, num_processes):
                # a column per instrument and pollutant, so the order shows
                return {
                    name: pd.DataFrame(
                        {
                            f"{name}_{p}_ppb": [1.0]
                            for p in site.instruments[name].pollutants
                        },
                        times,
                    )
                    for name in instruments
                }


            with patch.object(sites.Site, "read_data", side_effect=read_data):
                obs = sites.Site.get_obs(site, "all")
            print(*obs.columns)
            print(*obs.notna().idxmax(axis=1))  # each row's first filled column
            """
        )
        orders = set()
        for seed in range(4):
            result = subprocess.run(
                [sys.executable, "-c", code],
                env={**os.environ, "PYTHONHASHSEED": str(seed)},
                capture_output=True,
                text=True,
                check=True,
            )
            orders.add(result.stdout.strip())

        assert len(orders) == 1, orders
        assert "lgr_ugga_CO2_ppb" in orders.pop().split()


FILES_RUN = "No files found within the specified time range (files run from 2021-09 to 2026-07, with gaps)."


class TestNoDataMessage:
    """A read that finds nothing says what was asked for, and what exists (#63)."""

    @pytest.fixture
    def site(self):
        import uataq

        return uataq.get_site("BUS01")  # horel only; 2b_205 measures O3

    @staticmethod
    def no_files(site, *names, message=FILES_RUN):
        """Make these instruments find no file in the range."""
        return [
            patch.object(
                site.instruments[name],
                "read_data",
                side_effect=errors.ReaderError(message),
            )
            for name in names
        ]

    def test_get_obs_names_the_pollutant_level_site_and_dates(self, site):
        with self.no_files(site, "2b_205")[0], pytest.raises(errors.ReaderError) as e:
            site.get_obs("O3", time_range="2023-01")

        assert str(e.value) == (
            f"No final data found for O3 at BUS01: 2b_205 in horel groupspace: {FILES_RUN[:-1]}."
        )
        assert "['2b_205']" not in str(e.value)  # not the instrument list

    def test_get_obs_names_the_pollutant_in_the_case_it_is_declared(self, site):
        """``nox`` asks for NOx; 2b_405 declares it so."""
        with self.no_files(site, "2b_405")[0], pytest.raises(errors.ReaderError) as e:
            site.get_obs("nox", time_range="2022-01")

        assert "No final data found for NOx at BUS01" in str(e.value)

    def test_get_obs_with_several_pollutants_names_each(self, site):
        patches = self.no_files(site, "2b_205", "2b_405")
        with patches[0], patches[1], pytest.raises(errors.ReaderError) as e:
            site.get_obs(["O3", "NO2"], format="long", time_range="2022-01")

        assert "No final data found for O3, NO2 at BUS01" in str(e.value)
        assert "2b_205 in horel groupspace" in str(e.value)
        assert "2b_405 in horel groupspace" in str(e.value)

    def test_get_obs_of_everything(self, site):
        patches = self.no_files(site, "2b_205", "2b_405", "metone_es642")
        with patches[0], patches[1], patches[2], pytest.raises(errors.ReaderError) as e:
            site.get_obs(time_range="2022-01")

        assert "No final data found for all pollutants at BUS01" in str(e.value)

    def test_an_inactive_instrument_is_named_with_its_reason(self, site):
        """BUS01's 2b_405 was removed on 2022-05-10."""
        with pytest.raises(errors.ReaderError) as e:
            site.get_obs("NO2", time_range="2023-01")

        assert str(e.value) == (
            "No final data found for NO2 at BUS01: "
            "2b_405 not read: 2b_405@BUS01 is inactive in given time_range."
        )

    def test_read_data_names_the_instruments_and_the_level_asked_for(self, site):
        with self.no_files(site, "2b_205")[0], pytest.raises(errors.ReaderError) as e:
            site.read_data("2b_205", lvl="Final", time_range="2023-01")

        assert str(e.value).startswith(
            "No final data found for ['2b_205'] at BUS01: 2b_205 in horel groupspace: "
        )

    def test_read_data_without_a_level_does_not_name_one(self, site):
        with self.no_files(site, "2b_205")[0], pytest.raises(errors.ReaderError) as e:
            site.read_data("2b_205", time_range="2023-01")

        assert str(e.value).startswith("No data found for ['2b_205'] at BUS01: ")

    def test_reasons_are_kept_for_the_caller(self, site):
        with self.no_files(site, "2b_205")[0], pytest.raises(errors.ReaderError) as e:
            site.read_data("2b_205", time_range="2023-01")

        assert e.value.detail == f"2b_205 in horel groupspace: {FILES_RUN[:-1]}"

    def test_a_group_that_does_not_operate_the_instrument_is_the_reason(self, site):
        with pytest.raises(errors.ReaderError) as e:
            site.get_obs("O3", group="lin", time_range="2023-01")

        assert str(e.value) == (
            "No final data found for O3 at BUS01: "
            "2b_205 in lin groupspace: lin group invalid for 2b_205@BUS01."
        )

    def test_other_reader_errors_pass_through_get_obs(self, site):
        """An error that is not a read finding nothing keeps its own message."""
        with (
            patch.object(
                site.instruments["2b_205"],
                "plan_reads",
                side_effect=errors.InvalidGroupError("no group reads it"),
            ),
            pytest.raises(errors.InvalidGroupError) as e,
        ):
            site.get_obs("O3", time_range="2023-01")

        assert str(e.value) == "no group reads it"
        assert e.value.detail == ""

    def test_each_group_of_a_split_read_is_named(self):
        """TRX01 ozone is lin's before 2017-10-28 and horel's after."""
        import uataq

        trx = uataq.get_site("TRX01")
        with (
            self.no_files(trx, "2b_205", message="no files")[0],
            pytest.raises(errors.ReaderError) as e,
        ):
            trx.get_obs("O3", time_range=["2017-10-01", "2017-12-01"])

        assert "No final data found for O3 at TRX01: 2b_205 in lin groupspace" in str(
            e.value
        )
        assert "horel groupspace" in str(e.value)

    def test_through_the_files_on_disk(self, tmp_path, monkeypatch):
        """No file in the month: the real message, built from file names alone."""
        import uataq
        from uataq.filesystem.groupspaces import lin

        monkeypatch.setattr(lin, "DATA_DIR", str(tmp_path))
        final = tmp_path / "wbb" / "lgr_ugga" / "final"
        final.mkdir(parents=True)
        for month in ["2021_07", "2021_09", "2021_10"]:
            (final / f"{month}_final.dat").touch()

        with pytest.raises(errors.ReaderError) as e:
            uataq.get_site("WBB").get_obs("CO2", time_range="2021-08")

        assert str(e.value) == (
            "No final data found for CO2 at WBB: lgr_ugga in lin groupspace: "
            "No files found within the specified time range "
            "(files run from 2021-07 to 2021-10, with gaps)."
        )


def no_rows(*args, **kwargs):
    """Stand in for Instrument.read_data when the files hold nothing in the range."""
    return pd.DataFrame(
        {"O3_ppb": pd.Series(dtype=float)}, index=pd.DatetimeIndex([], name="Time_UTC")
    )


def two_rows(*args, **kwargs):
    """Stand in for Instrument.read_data when the files hold two rows in the range."""
    index = pd.DatetimeIndex(["2024-03-04 00:00", "2024-03-04 00:01"], name="Time_UTC")
    return pd.DataFrame({"O3_ppb": [41.0, 42.0]}, index=index)


class TestEmptyResultWarning:
    """A range with files but no rows warns, and says what was asked (#63)."""

    @pytest.fixture
    def wbb(self):
        import uataq

        return uataq.get_site("WBB")  # lin only; teledyne_t400 measures O3

    @staticmethod
    def read(instrument, read_data):
        """Make ``instrument`` read ``read_data`` instead of the archive."""
        return patch.object(instrument, "read_data", read_data)

    def test_get_obs_warns_and_returns_no_rows(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], no_rows),
            pytest.warns(errors.EmptyResultWarning) as caught,
        ):
            obs = wbb.get_obs("O3", time_range="2024-03-04")

        assert len(obs) == 0
        assert [str(w.message) for w in caught] == [
            "No final data found for O3 at WBB "
            "(2024-03-04 00:00:00 to 2024-03-05 00:00:00): "
            "the files for teledyne_t400 exist but hold no data in that range."
        ]

    def test_the_warning_points_at_the_line_that_called_get_obs(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], no_rows),
            pytest.warns(errors.EmptyResultWarning) as caught,
        ):
            wbb.get_obs("O3", time_range="2024-03-04")

        assert caught[0].filename == __file__

    def test_the_long_format_warns_too(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], no_rows),
            pytest.warns(errors.EmptyResultWarning, match="No final data found"),
        ):
            obs = wbb.get_obs("O3", format="long", time_range="2024-03-04")

        assert len(obs) == 0

    def test_every_pollutant_asked_for_is_named(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], no_rows),
            self.read(wbb.instruments["lgr_ugga"], no_rows),
            pytest.warns(errors.EmptyResultWarning) as caught,
        ):
            wbb.get_obs(["O3", "CO2"], time_range="2024-03-04")

        message = str(caught[0].message)
        assert message.startswith("No final data found for O3, CO2 at WBB")
        assert "the files for teledyne_t400, lgr_ugga exist" in message

    def test_all_pollutants_is_said_so(self, wbb):
        # the instruments installed on 2024-03-04; the rest are inactive then
        with (
            patch.object(instruments.Instrument, "read_data", no_rows),
            pytest.warns(errors.EmptyResultWarning, match="for all pollutants at WBB"),
        ):
            wbb.get_obs(time_range="2024-03-04")

    def test_rows_with_no_value_for_the_pollutant_warn(self, wbb):
        """Rows that are all NaN in the columns asked for are dropped: nothing left."""

        def nan_rows(*args, **kwargs):
            return two_rows().assign(O3_ppb=float("nan"))

        with (
            self.read(wbb.instruments["teledyne_t400"], nan_rows),
            pytest.warns(errors.EmptyResultWarning, match="No final data found for O3"),
        ):
            obs = wbb.get_obs("O3", time_range="2024-03-04")

        assert len(obs) == 0

    def test_its_own_category_silences_it(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], no_rows),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            warnings.filterwarnings("ignore", category=errors.EmptyResultWarning)
            obs = wbb.get_obs("O3", time_range="2024-03-04")

        assert len(obs) == 0
        assert caught == []

    def test_a_range_with_rows_does_not_warn(self, wbb):
        with (
            self.read(wbb.instruments["teledyne_t400"], two_rows),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs("O3", time_range="2024-03-04")

        assert len(obs) == 2
        assert caught == []

    def test_one_instrument_without_rows_does_not_warn(self, wbb):
        """Only a table with no rows at all warns: the other instrument has data."""
        with (
            self.read(wbb.instruments["teledyne_t400"], two_rows),
            self.read(wbb.instruments["lgr_ugga"], no_rows),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs(["O3", "CO2"], time_range="2024-03-04")

        assert len(obs) == 2
        assert caught == []

    def test_get_recent_obs_warns(self, wbb):
        with (
            self.read(wbb.instruments["lgr_ugga"], no_rows),
            pytest.warns(
                errors.EmptyResultWarning,
                match=r"No final data found for CO2 at WBB \(After 20\d\d-",
            ),
        ):
            obs = wbb.get_recent_obs("1h", "CO2")

        assert len(obs) == 0

    @pytest.mark.parametrize("include_gps", [True, False])
    def test_a_mobile_site_warns_with_and_without_gps(self, include_gps):
        import uataq

        trx = uataq.get_site("TRX01")
        with (
            self.read(trx.instruments["2b_205"], no_rows),
            pytest.warns(errors.EmptyResultWarning, match="O3 at TRX01") as caught,
        ):
            obs = trx.get_obs("O3", include_gps=include_gps, time_range="2024-06-04")

        assert len(obs) == 0
        assert len(caught) == 1

    def test_an_empty_portion_of_a_split_read_does_not_warn(self):
        """A range cut at a group_dates edge may be empty on one side only."""
        import uataq

        def read_data(group, lvl=None, time_range=None, *args, **kwargs):
            # TRX01 ozone: lin's portion (before 2017-10-28) is empty, horel's is not
            if group == "lin":
                return no_rows()
            start = TimeRange(time_range).start
            index = pd.DatetimeIndex([start, start + pd.Timedelta(hours=1)])
            return pd.DataFrame({"O3_ppb": [2.0, 2.0]}, index=index.rename("Time_UTC"))

        trx = uataq.get_site("TRX01")
        span = (datetime(2017, 10, 20), datetime(2017, 10, 30))
        with (
            self.read(trx.instruments["2b_205"], read_data),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = trx.get_obs("O3", include_gps=False, time_range=span)

        assert obs["O3_ppb"].tolist() == [2.0, 2.0]
        assert caught == []

    def test_through_the_files_on_disk(self, tmp_path, monkeypatch):
        """A month's file with rows on other days: the real read, slice and warning."""
        import uataq
        from uataq.filesystem.groupspaces import lin

        monkeypatch.setattr(lin, "DATA_DIR", str(tmp_path))
        final = tmp_path / "wbb" / "teledyne_t400" / "final"
        final.mkdir(parents=True)
        (final / "2024_06_final.dat").write_text(
            "Time_UTC,O3_ppb\n2024-06-01 00:00:01,47.2\n2024-06-01 00:00:03,47.1\n"
        )
        wbb = uataq.get_site("WBB")
        config = {"final": {"col_names": ["Time_UTC", "O3_ppb"], "col_types": "Td"}}

        with (
            patch.dict(lin.DATA_CONFIG, {"teledyne_t400": config}),
            pytest.warns(errors.EmptyResultWarning) as caught,
        ):
            empty = wbb.get_obs("O3", time_range="2024-06-04")
        assert len(empty) == 0
        assert [str(w.message) for w in caught] == [
            "No final data found for O3 at WBB "
            "(2024-06-04 00:00:00 to 2024-06-05 00:00:00): "
            "the files for teledyne_t400 exist but hold no data in that range."
        ]

        with (
            patch.dict(lin.DATA_CONFIG, {"teledyne_t400": config}),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs("O3", time_range="2024-06-01")
        assert obs["O3_ppb"].tolist() == [47.2, 47.1]
        assert caught == []


class TestLevelTheInstrumentLacks:
    """A read at a level an instrument does not have names the levels it has (#63)."""

    COLUMNS = {
        "col_names": ["Time_UTC", "O3_ppb"],
        "col_types": "Td",
    }

    @pytest.fixture
    def archive(self, tmp_path, monkeypatch):
        """WBB ozone with a calibrated month; the NO monitor has no such folder."""
        from uataq.filesystem.groupspaces import lin

        monkeypatch.setattr(lin, "DATA_DIR", str(tmp_path))
        for inst, lvls in [
            ("teledyne_t400", ["raw", "qaqc", "calibrated", "final"]),
            ("teledyne_t200", ["raw", "qaqc", "final"]),
        ]:
            for lvl in lvls:
                (tmp_path / "wbb" / inst / lvl).mkdir(parents=True)
        (
            tmp_path / "wbb" / "teledyne_t400" / "calibrated" / "2024_06_cal.dat"
        ).write_text(
            "Time_UTC,O3_ppb\n2024-06-01 00:00:01,47.2\n2024-06-01 00:00:03,47.1\n"
        )
        config = {"calibrated": self.COLUMNS}
        with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": config}):
            yield tmp_path

    @pytest.fixture
    def wbb(self):
        import uataq

        return uataq.get_site("WBB")

    def test_the_error_names_the_levels_it_has(self, archive, wbb):
        with pytest.raises(errors.ReaderError) as e:
            wbb.read_data("teledyne_t200", lvl="calibrated", time_range="2024-06")

        assert str(e.value) == (
            "No calibrated data found for ['teledyne_t200'] at WBB: "
            "teledyne_t200 in lin groupspace: "
            "teledyne_t200@WBB has no calibrated level (it has raw, qaqc and final)."
        )

    def test_the_log_says_it_too(self, archive, wbb, caplog):
        with (
            caplog.at_level(logging.WARNING, logger="uataq"),
            pytest.raises(errors.ReaderError),
        ):
            wbb.read_data("teledyne_t200", lvl="calibrated", time_range="2024-06")

        assert (
            "Error reading teledyne_t200@WBB data from lin groupspace: "
            "teledyne_t200@WBB has no calibrated level (it has raw, qaqc and final)."
        ) in caplog.text

    def test_an_instrument_that_has_the_level_is_still_read(self, archive, wbb):
        """One instrument lacking the level no longer ends the read of the others."""
        data = wbb.read_data(
            ["teledyne_t200", "teledyne_t400"], lvl="calibrated", time_range="2024-06"
        )

        assert list(data) == ["teledyne_t400"]
        assert data["teledyne_t400"]["O3_ppb"].tolist() == [47.2, 47.1]

    def test_the_level_is_read_whatever_its_case(self, archive, wbb):
        data = wbb.read_data("teledyne_t400", lvl="Calibrated", time_range="2024-06")

        assert len(data["teledyne_t400"]) == 2

    def test_the_top_level_function_raises_the_same_error(self, archive):
        import uataq

        with pytest.raises(errors.ReaderError, match="has no calibrated level"):
            uataq.read_data(
                "WBB", "teledyne_t200", lvl="calibrated", time_range="2024-06"
            )

    def test_each_group_of_a_split_read_is_named(self):
        """TRX01 ozone is lin's before 2017-10-28 and horel's after; neither has it."""
        import uataq

        trx = uataq.get_site("TRX01")
        levels = ["raw", "qaqc", "final"]
        with (
            patch(
                "uataq.filesystem.groupspaces.lin.LinGroup.get_lvls",
                return_value=levels,
            ),
            patch(
                "uataq.filesystem.groupspaces.horel.HorelGroup.get_lvls",
                return_value=levels,
            ),
            pytest.raises(errors.ReaderError) as e,
        ):
            trx.read_data(
                "2b_205", lvl="calibrated", time_range=["2017-10-01", "2017-12-01"]
            )

        message = str(e.value)
        assert message.startswith("No calibrated data found for ['2b_205'] at TRX01: ")
        assert "lin (" in message and "horel (" in message
        assert message.count("2b_205@TRX01 has no calibrated level") == 2
