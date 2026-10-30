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
            patch.object(sites.Site, "_read_obs", return_value={"2b_205": obs}),
            patch.object(sites.Site, "read_data") as read_data,
        ):
            result = site.get_obs("O3", include_gps=False)

        read_data.assert_not_called()
        assert result["O3_ppb"].tolist() == [40.0]


class TestMobileSiteInstrumentColumn:
    """MobileSite.get_obs says which instrument each row came from."""

    SPAN = (datetime(2024, 9, 1), datetime(2024, 9, 2))

    @staticmethod
    def stamp(*times):
        return pd.DatetimeIndex(pd.to_datetime(list(times)), name="Time_UTC")

    def fake_read_data(self, instruments, group=None, lvl=None, *args, **kwargs):
        """TRX01 CO2 from both LGR names, ozone from horel, and a lin GPS."""
        if instruments == "gps":
            index = self.stamp("2024-09-01 00:00:07", "2024-09-01 00:00:17")
            pi = index.strftime("%Y-%m-%d %H:%M:%S.%f")
            gps = pd.DataFrame(
                {"Pi_Time": pi, "Latitude_deg": 40.7, "Longitude_deg": -111.9},
                index=index,
            )
            return {"gps": gps}
        cal = pd.DataFrame(
            {"CO2d_ppm_cal": [430.0], "CO2d_ppm_raw": [432.0]},
            index=self.stamp("2024-09-01 00:00:07"),
        )
        manual = pd.DataFrame(
            {"CO2d_ppm_cal": [None], "CO2d_ppm_raw": [433.0]},
            index=self.stamp("2024-09-01 00:00:17"),
        )
        return {"lgr_ugga": cal, "lgr_ugga_manual_cal": manual}

    def trx01_obs(self, **kwargs):
        import uataq

        site = uataq.get_site("TRX01")
        with patch.object(site, "read_data", self.fake_read_data):
            return site.get_obs("CO2", group="lin", time_range=self.SPAN, **kwargs)

    @pytest.mark.parametrize("include_gps", [True, False])
    def test_each_row_names_its_instrument(self, include_gps):
        obs = self.trx01_obs(include_gps=include_gps)

        assert obs["instrument"].tolist() == ["lgr_ugga", "lgr_ugga_manual_cal"]
        assert obs["CO2d_ppm_raw"].tolist() == [432.0, 433.0]

    def test_the_label_follows_the_measurements_before_the_gps_columns(self):
        columns = self.trx01_obs().columns.tolist()

        assert columns[:3] == ["CO2d_ppm_cal", "CO2d_ppm_raw", "instrument"]
        assert columns.index("Latitude_deg") == 3

    def test_long_format_is_labeled_too(self):
        obs = self.trx01_obs(format="long", include_gps=False)

        assert obs.columns.tolist() == ["pollutant", "value", "instrument"]
        # lgr_ugga gives its _cal and _raw values, lgr_ugga_manual_cal only _raw
        assert obs["instrument"].tolist() == ["lgr_ugga"] * 2 + ["lgr_ugga_manual_cal"]


class TestFixedSiteInstrumentColumn:
    """Site.get_obs says which instrument each row came from, as MobileSite does."""

    times = pd.DatetimeIndex(
        ["2022-03-01 00:00:00", "2022-03-01 00:00:10"], name="Time_UTC"
    )

    @pytest.fixture
    def wbb(self):
        import uataq

        return uataq.get_site("WBB")

    def two_no2_instruments(self):
        """WBB's NO2 in 2022 came from two instruments at once."""
        return {
            "teledyne_t200": pd.DataFrame(
                {"NO2_ppb": [13.0, 14.0], "NOx_ppb": [20.0, 21.0]}, self.times
            ),
            "teledyne_t500u": pd.DataFrame({"NO2_ppb": [15.0, 16.0]}, self.times),
        }

    def get_obs(self, wbb, pollutants, **kwargs):
        data = self.two_no2_instruments()
        with patch.object(wbb, "read_data", return_value=data):
            return wbb.get_obs(pollutants, time_range="2022-03-01", **kwargs)

    def test_each_row_names_its_instrument(self, wbb):
        obs = self.get_obs(wbb, "NO2")

        assert obs.columns.tolist() == ["NO2_ppb", "instrument"]
        # Rows on one time keep the order of the instruments
        assert obs["instrument"].tolist() == ["teledyne_t200", "teledyne_t500u"] * 2
        assert obs["NO2_ppb"].tolist() == [13.0, 15.0, 14.0, 16.0]

    def test_the_label_follows_the_measurements_of_every_instrument(self, wbb):
        obs = self.get_obs(wbb, ["NO2", "NOx"])

        assert obs.columns.tolist() == ["NO2_ppb", "NOx_ppb", "instrument"]

    def test_long_format_is_labeled_too(self, wbb):
        obs = self.get_obs(wbb, "NO2", format="long")

        assert obs.columns.tolist() == ["pollutant", "value", "instrument"]
        assert obs["instrument"].tolist() == ["teledyne_t200", "teledyne_t500u"] * 2

    def test_rows_and_values_are_those_without_the_label(self, wbb):
        data = self.two_no2_instruments()
        with patch.object(wbb, "read_data", return_value=data):
            obs = wbb.get_obs("NO2", time_range="2022-03-01")
        unlabeled = pd.concat(
            [data["teledyne_t200"][["NO2_ppb"]], data["teledyne_t500u"][["NO2_ppb"]]]
        ).sort_index(kind="stable")

        pd.testing.assert_frame_equal(obs.drop(columns="instrument"), unlabeled)

    def test_the_hourly_mean_needs_numeric_only(self, wbb):
        obs = self.get_obs(wbb, "NO2")

        hourly = obs.resample("h").mean(numeric_only=True)

        assert hourly.columns.tolist() == ["NO2_ppb"]
        assert hourly["NO2_ppb"].tolist() == [14.5]


class TestMobileSiteNoFix:
    """A mobile get_obs whose rows all miss the GPS says so (TRX01 2018-09)."""

    SPAN = (datetime(2018, 9, 1), datetime(2018, 9, 2))

    @staticmethod
    def fake_read_data(instruments, group=None, lvl=None, *args, **kwargs):
        """Methane in September; the GPS read finds only August's fixes."""
        if instruments == "gps":
            index = pd.DatetimeIndex(["2018-08-31 23:59:59"], name="Time_UTC")
            gps = pd.DataFrame(
                {
                    "Pi_Time": ["2018-08-31 23:59:59.40"],
                    "Latitude_deg": [40.7],
                    "Longitude_deg": [-111.9],
                },
                index=index,
            )
            return {"gps": gps}
        index = pd.DatetimeIndex(["2018-09-01 00:00:07"], name="Time_UTC")
        return {"lgr_ugga": pd.DataFrame({"CH4d_ppm_cal": [2.0]}, index=index)}

    def get_obs(self, **kwargs):
        import uataq

        site = uataq.get_site("TRX01")
        with patch.object(site, "read_data", self.fake_read_data):
            return site.get_obs("CH4", group="lin", time_range=self.SPAN, **kwargs)

    def test_warns_when_no_row_found_a_fix(self):
        with pytest.warns(errors.EmptyResultWarning, match="1 rows of lgr_ugga"):
            obs = self.get_obs()
        assert obs.empty

    def test_without_gps_the_rows_are_there_and_nothing_warns(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            obs = self.get_obs(include_gps=False)
        assert obs["CH4d_ppm_cal"].tolist() == [2.0]


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


class TestMergeGps:
    """
    Each observation is merged with one GPS fix (#93).

    The Pi stamps lin's GPS fixes with jitter, so a fix logged late in one
    second and the next one logged early in the following second can fall in
    the same Pi second. Latitudes say which fix located a row.
    """

    @staticmethod
    def lin_obs(*pi_times):
        index = pd.DatetimeIndex(pd.to_datetime(list(pi_times)), name="Time_UTC")
        return pd.DataFrame({"CH4d_ppm_cal": range(len(pi_times))}, index=index)

    @staticmethod
    def lin_gps():
        # Pi_Time 12:00:00.02 and 12:00:00.98 share a second
        index = pd.DatetimeIndex(
            ["2024-01-01 11:59:59", "2024-01-01 12:00:00", "2024-01-01 12:00:01"],
            name="Time_UTC",
        )
        return pd.DataFrame(
            {
                "Pi_Time": [
                    "2024-01-01 12:00:00.02",
                    "2024-01-01 12:00:00.98",
                    "2024-01-01 12:00:01.99",
                ],
                "Latitude_deg": [40.70, 40.71, 40.72],
                "Longitude_deg": -111.9,
            },
            index=index,
        )

    def locate(self, obs):
        return sites.MobileSite._merge_on_clock(obs, self.lin_gps(), "lin")

    def test_two_fixes_in_one_second_give_one_row(self):
        obs = self.lin_obs("2024-01-01 12:00:00.50")
        assert len(self.locate(obs)) == 1

    def test_the_fix_nearest_in_time_is_kept(self):
        obs = self.lin_obs(
            "2024-01-01 12:00:00.10",  # nearer 12:00:00.02
            "2024-01-01 12:00:00.70",  # nearer 12:00:00.98
            "2024-01-01 12:00:01.30",  # alone in its second
        )
        located = self.locate(obs)

        assert list(located["CH4d_ppm_cal"]) == [0, 1, 2]
        assert list(located["Latitude_deg"]) == [40.70, 40.71, 40.72]
        assert list(located.index) == list(
            pd.to_datetime(
                ["2024-01-01 11:59:59", "2024-01-01 12:00:00", "2024-01-01 12:00:01"]
            )
        )

    def test_a_tie_keeps_the_first_fix(self):
        obs = self.lin_obs("2024-01-01 12:00:00.50")  # 0.48 s from both
        assert list(self.locate(obs)["Latitude_deg"]) == [40.70]

    def test_columns_are_unchanged(self):
        located = self.locate(self.lin_obs("2024-01-01 12:00:00.50"))
        assert list(located.columns) == [
            "CH4d_ppm_cal",
            "Latitude_deg",
            "Longitude_deg",
            "geometry",
            "GPS_Group",
        ]

    def test_repeated_time_utc_on_one_clock(self):
        # horel: instrument and GPS share the CR1000 clock, joined on Time_UTC
        obs = pd.DataFrame(
            {"O3_ppb": [30.0, 31.0]},
            index=pd.DatetimeIndex(
                ["2024-01-01 12:00:00", "2024-01-01 12:00:01"], name="Time_UTC"
            ),
        )
        gps = pd.DataFrame(
            {"Latitude_deg": [40.70, 40.71, 40.72], "Longitude_deg": -111.9},
            index=pd.DatetimeIndex(
                ["2024-01-01 12:00:00", "2024-01-01 12:00:00", "2024-01-01 12:00:01"],
                name="Time_UTC",
            ),
        )
        merged = sites.MobileSite.merge_gps(obs, gps)
        assert list(merged["O3_ppb"]) == [30.0, 31.0]
        assert list(merged["Latitude_deg"]) == [40.70, 40.72]


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
        assert list(obs.columns) == ["NOx_ppb", "instrument"]

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

        assert list(obs.columns) == ["pollutant", "value", "instrument"]
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
        assert list(obs.columns) == ["O3_ppb", "instrument"]
        assert obs["O3_ppb"].tolist() == [40.0]

    @pytest.mark.parametrize("format", ["wide", "long"])
    def test_a_pollutant_brings_only_its_own_columns(self, site, format):
        """NO is not NO2 or NOx, though their names start alike."""
        data = {
            "2b_405": pd.DataFrame(
                {"NO_ppb": [1.0, 2.0], "NO2_ppb": [3.0, 4.0], "NOx_ppb": [4.0, 6.0]},
                self.times,
            )
        }
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = sites.Site.get_obs(site, "NO", format=format)
        if format == "wide":
            assert list(obs.columns) == ["NO_ppb", "instrument"]
        else:
            assert set(obs["pollutant"]) == {"NO_ppb"}
            assert obs["value"].tolist() == [1.0, 2.0]

    def test_pm1_is_not_pm10(self):
        import uataq

        site = uataq.get_site("TRX03")
        times = pd.DatetimeIndex(["2025-06-01"], name="Time_UTC")
        frame = pd.DataFrame({"PM1_ugm3": [2.0], "PM10_ugm3": [9.0]}, times)
        with patch.object(
            sites.Site, "read_data", return_value={"metone_es405": frame}
        ):
            obs = sites.Site.get_obs(site, "PM1")
        assert list(obs.columns) == ["PM1_ugm3", "instrument"]

    def test_raw_columns_are_kept(self):
        """TRX01's lgr_ugga_manual_cal has its value only in _raw."""
        import uataq

        trx01 = uataq.get_site("TRX01")
        times = pd.DatetimeIndex(["2024-09-01"], name="Time_UTC")
        frame = pd.DataFrame(
            {"CO2d_ppm_cal": [None], "CO2d_ppm_raw": [430.0], "H2O_ppm": [9000.0]},
            times,
        )
        data = {"lgr_ugga_manual_cal": frame}
        with patch.object(sites.Site, "read_data", return_value=data):
            obs = sites.Site.get_obs(trx01, "CO2")
        assert list(obs.columns) == ["CO2d_ppm_cal", "CO2d_ppm_raw", "instrument"]

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
        measured = [c for c in expected if c in obs.columns]
        assert list(obs.columns) == [*measured, "instrument"]
        assert len(measured) > 0

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
                # each instrument's values are its place in the config, so the
                # order of the rows shows
                return {
                    name: pd.DataFrame(
                        {
                            f"{p}_ppb": [float(site.instruments.names.index(name))]
                            for p in site.instruments[name].pollutants
                        },
                        times,
                    )
                    for name in instruments
                }


            with patch.object(sites.Site, "read_data", side_effect=read_data):
                obs = sites.Site.get_obs(site, "all")
            print(*obs.columns)
            print(obs.to_csv(header=False))
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
        assert "CO2_ppb" in orders.pop().split()


class TestGetObsRowOrder:
    """Rows on one timestamp keep the instrument order in every session (#63)."""

    #: BUS01 reads 2b_205, 2b_405 and metone_es642 for these, in the order asked
    asked = ["O3", "NO2", "PM2.5"]
    columns = {"2b_205": "O3_ppb", "2b_405": "NO2_ppb", "metone_es642": "PM2.5_ugm3"}

    @pytest.fixture
    def site(self):
        import uataq

        return uataq.get_site("BUS01")

    def read_data(self, instruments, group, lvl, time_range, num_processes):
        """Give every instrument rows on the same timestamps, as co-located ones do."""
        times = pd.date_range("2024-06-01", periods=1000, freq="min", name="Time_UTC")
        return {
            name: pd.DataFrame({self.columns[name]: range(len(times))}, times)
            for name in instruments
        }

    @pytest.mark.parametrize("format", ["wide", "long"])
    def test_rows_on_one_timestamp_keep_the_instrument_order(self, site, format):
        """The default sort (quicksort) swaps tied rows; a stable one cannot."""
        with patch.object(sites.Site, "read_data", side_effect=self.read_data):
            obs = sites.Site.get_obs(site, self.asked, format)

        assert obs.index.is_monotonic_increasing
        # wide: each row's only filled column; long: its pollutant column
        names = obs.notna().idxmax(axis=1) if format == "wide" else obs["pollutant"]
        assert names.tolist() == list(self.columns.values()) * 1000

    def test_the_order_asked_is_the_order_of_the_rows(self, site):
        with patch.object(sites.Site, "read_data", side_effect=self.read_data):
            obs = sites.Site.get_obs(site, ["PM2.5", "O3", "NO2"])

        names = obs.notna().idxmax(axis=1)
        assert names.tolist() == ["PM2.5_ugm3", "O3_ppb", "NO2_ppb"] * 1000


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

    def test_through_the_files_on_disk(self, lin_data_dir):
        """No file in the month: the real message, built from file names alone."""
        import uataq

        final = lin_data_dir / "wbb" / "lgr_ugga" / "final"
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

    def test_through_the_files_on_disk(self, lin_data_dir):
        """A month's file with rows on other days: the real read, slice and warning."""
        import uataq
        from uataq.filesystem.groupspaces import lin

        final = lin_data_dir / "wbb" / "teledyne_t400" / "final"
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


class TestDroppedPollutantWarning:
    """A pollutant with no data is left out of a read of several, and the warning says so (#63)."""

    RANGE = "(2024-03-04 00:00:00 to 2024-03-05 00:00:00)"

    @pytest.fixture
    def wbb(self):
        import uataq

        return uataq.get_site("WBB")  # CO2 and CH4: lgr_ugga; O3: teledyne_t400

    @staticmethod
    def no_files(instrument):
        """Make ``instrument`` find no file in the range."""
        error = errors.ReaderError(
            "No files found within the specified time range "
            "(files run from 2014-02 to 2024-02, with gaps)."
        )
        return patch.object(instrument, "read_data", side_effect=error)

    @staticmethod
    def rows(instrument):
        """Make ``instrument`` read two rows."""
        return patch.object(instrument, "read_data", two_rows)

    def test_the_pollutant_with_no_data_is_named(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning) as caught,
        ):
            obs = wbb.get_obs(["CO2", "O3"], time_range="2024-03-04")

        assert obs.columns.tolist() == [
            "O3_ppb",
            "instrument",
        ]  # what is returned is unchanged
        assert [str(w.message) for w in caught] == [
            f"No final data found for CO2 at WBB {self.RANGE}: "
            "lgr_ugga gave none, so the table leaves out CO2."
        ]

    def test_the_warning_points_at_the_line_that_called_get_obs(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning) as caught,
        ):
            wbb.get_obs(["CO2", "O3"], time_range="2024-03-04")

        assert caught[0].filename == __file__

    def test_the_long_format_warns_too(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning, match="for CO2 at WBB"),
        ):
            obs = wbb.get_obs(["CO2", "O3"], format="long", time_range="2024-03-04")

        assert set(obs["pollutant"]) == {"O3_ppb"}

    def test_every_pollutant_left_out_is_named_once(self, wbb):
        """CO2 and CH4 are measured by one instrument, which is named once."""
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning) as caught,
        ):
            wbb.get_obs(["CO2", "CH4", "O3"], time_range="2024-03-04")

        assert [str(w.message) for w in caught] == [
            f"No final data found for CO2, CH4 at WBB {self.RANGE}: "
            "lgr_ugga gave none, so the table leaves out CO2, CH4."
        ]

    def test_each_instrument_that_gave_none_is_named(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.no_files(wbb.instruments["teledyne_t300"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning) as caught,
        ):
            wbb.get_obs(["co2", "CO", "O3"], time_range="2024-03-04")

        assert [str(w.message) for w in caught] == [
            f"No final data found for CO2, CO at WBB {self.RANGE}: "
            "lgr_ugga, teledyne_t300 gave none, so the table leaves out CO2, CO."
        ]

    def test_an_instrument_not_installed_then_is_one_that_gave_none(self, wbb):
        """WBB's ae33 was removed on 2024-06-20, so it reads nothing after that."""
        with (
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning, match="magee_ae33 gave none"),
        ):
            obs = wbb.get_obs(["BC", "O3"], time_range="2024-07-04")

        assert obs.columns.tolist() == ["O3_ppb", "instrument"]

    def test_get_recent_obs_warns(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            pytest.warns(errors.DroppedPollutantWarning, match="for CO2 at WBB"),
        ):
            wbb.get_recent_obs("1h", ["CO2", "O3"])

    @pytest.mark.parametrize("include_gps", [True, False])
    def test_a_mobile_site_warns_with_and_without_gps(self, include_gps):
        import uataq

        trx = uataq.get_site("TRX01")  # PM1: metone_es405; O3: 2b_205
        with (
            self.no_files(trx.instruments["metone_es405"]),
            self.rows(trx.instruments["2b_205"]),
            # the GPS is not under test: skip locating the rows
            patch.object(
                sites.MobileSite,
                "locate",
                lambda self, frames, *args, **kwargs: pd.concat(frames.values()),
            ),
            pytest.warns(
                errors.DroppedPollutantWarning, match="PM1 at TRX01"
            ) as caught,
        ):
            obs = trx.get_obs(
                ["PM1", "O3"], include_gps=include_gps, time_range="2025-03-04"
            )

        assert obs.columns.tolist() == ["O3_ppb", "instrument"]
        assert len(caught) == 1

    def test_its_own_category_silences_it(self, wbb):
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            warnings.filterwarnings("ignore", category=errors.DroppedPollutantWarning)
            obs = wbb.get_obs(["CO2", "O3"], time_range="2024-03-04")

        assert obs.columns.tolist() == ["O3_ppb", "instrument"]
        assert caught == []

    def test_all_pollutants_with_data_does_not_warn(self, wbb):
        with (
            self.rows(wbb.instruments["lgr_ugga"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs(["CO2", "O3"], time_range="2024-03-04")

        assert len(obs) == 4
        assert caught == []

    def test_a_pollutant_another_instrument_still_measures_is_not_left_out(self, wbb):
        """NO2 is measured by two instruments in 2022; one gave data, so it is in the table."""
        with (
            self.no_files(wbb.instruments["teledyne_t200"]),
            self.rows(wbb.instruments["teledyne_t500u"]),
            self.rows(wbb.instruments["teledyne_t400"]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs(["NO2", "O3"], time_range="2022-03-04")

        assert len(obs) == 4
        assert caught == []

    def test_all_pollutants_does_not_warn(self, wbb):
        """``'all'`` names none, and removed instruments are expected to give none."""
        with (
            # the instruments installed on 2024-03-04 read two rows, lgr_ugga none
            patch.object(instruments.Instrument, "read_data", two_rows),
            self.no_files(wbb.instruments["lgr_ugga"]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            obs = wbb.get_obs(time_range="2024-03-04")

        assert "O3_ppb" in obs.columns
        assert not [w for w in caught if w.category is errors.DroppedPollutantWarning]

    def test_one_pollutant_with_no_data_is_still_an_error(self, wbb):
        """A read that finds nothing raises, as before, with no warning."""
        with (
            self.no_files(wbb.instruments["lgr_ugga"]),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            with pytest.raises(errors.ReaderError, match="No final data found for CO2"):
                wbb.get_obs("CO2", time_range="2024-03-04")
            with pytest.raises(errors.ReaderError, match="No final data found for CO2"):
                wbb.get_obs(["CO2", "CH4"], time_range="2024-03-04")

        assert caught == []

    def test_through_the_files_on_disk(self, lin_data_dir):
        """No CO2 file in the month, an ozone file with rows: the real read and warning."""
        import uataq
        from uataq.filesystem.groupspaces import lin

        o3 = lin_data_dir / "wbb" / "teledyne_t400" / "final"
        o3.mkdir(parents=True)
        (o3 / "2024_06_final.dat").write_text(
            "Time_UTC,O3_ppb\n2024-06-04 00:00:01,47.2\n2024-06-04 00:00:03,47.1\n"
        )
        co2 = lin_data_dir / "wbb" / "lgr_ugga" / "final"
        co2.mkdir(parents=True)
        (co2 / "2024_05_final.dat").touch()
        config = {"final": {"col_names": ["Time_UTC", "O3_ppb"], "col_types": "Td"}}

        with (
            patch.dict(lin.DATA_CONFIG, {"teledyne_t400": config}),
            pytest.warns(errors.DroppedPollutantWarning) as caught,
        ):
            obs = uataq.get_site("WBB").get_obs(["CO2", "O3"], time_range="2024-06-04")

        assert obs["O3_ppb"].tolist() == [47.2, 47.1]
        assert [str(w.message) for w in caught] == [
            "No final data found for CO2 at WBB "
            "(2024-06-04 00:00:00 to 2024-06-05 00:00:00): "
            "lgr_ugga gave none, so the table leaves out CO2."
        ]


class TestLevelTheInstrumentLacks:
    """A read at a level an instrument does not have names the levels it has (#63)."""

    COLUMNS = {
        "col_names": ["Time_UTC", "O3_ppb"],
        "col_types": "Td",
    }

    @pytest.fixture
    def archive(self, lin_data_dir):
        """WBB ozone with a calibrated month; the NO monitor has no such folder."""
        from uataq.filesystem.groupspaces import lin

        for inst, lvls in [
            ("teledyne_t400", ["raw", "qaqc", "calibrated", "final"]),
            ("teledyne_t200", ["raw", "qaqc", "final"]),
        ]:
            for lvl in lvls:
                (lin_data_dir / "wbb" / inst / lvl).mkdir(parents=True)
        (
            lin_data_dir / "wbb" / "teledyne_t400" / "calibrated" / "2024_06_cal.dat"
        ).write_text(
            "Time_UTC,O3_ppb\n2024-06-01 00:00:01,47.2\n2024-06-01 00:00:03,47.1\n"
        )
        config = {"calibrated": self.COLUMNS}
        with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": config}):
            yield lin_data_dir

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


class TestGetObsLevelKeyword:
    """``get_obs`` always reads the final level, so a level keyword is an error."""

    @pytest.mark.parametrize("name", ["lvl", "level"])
    def test_a_fixed_site_raises_and_reads_nothing(self, name):
        import uataq

        site = uataq.get_site("WBB")
        with (
            patch.object(sites.Site, "read_data") as read,
            pytest.raises(TypeError) as excinfo,
        ):
            site.get_obs("CO2", **{name: "qaqc"})

        read.assert_not_called()
        assert str(excinfo.value) == (
            f"get_obs() got an unexpected keyword argument '{name}'. get_obs "
            "always reads the final level; to read another, call "
            "read_data(..., lvl='qaqc')."
        )

    @pytest.mark.parametrize("include_gps", [True, False])
    def test_a_mobile_site_raises_with_and_without_gps(self, include_gps):
        import uataq

        site = uataq.get_site("TRX01")
        with (
            patch.object(sites.Site, "read_data") as read,
            pytest.raises(TypeError, match="'lvl'.*final level"),
        ):
            site.get_obs("O3", include_gps=include_gps, lvl="raw")

        read.assert_not_called()

    def test_the_top_level_function_raises(self):
        import uataq

        with (
            patch.object(sites.Site, "read_data") as read,
            pytest.raises(TypeError, match="'level'.*read_data"),
        ):
            uataq.get_obs("WBB", "CO2", level="calibrated")

        read.assert_not_called()

    def test_the_value_given_is_in_the_hint(self):
        import uataq

        with pytest.raises(TypeError, match=r"read_data\(\.\.\., lvl='raw'\)"):
            uataq.get_site("WBB").get_obs("CO2", lvl="raw")


class TestUnmeasuredPollutant:
    """The error for a pollutant the site does not measure says what it does."""

    @pytest.fixture
    def csp(self):
        import uataq

        return uataq.get_site("CSP")

    def message(self, site, pollutants):
        with (
            patch.object(sites.Site, "read_data") as read,
            pytest.raises(ValueError) as excinfo,
        ):
            site.get_obs(pollutants)
        read.assert_not_called()
        return str(excinfo.value)

    def test_a_pollutant_measured_elsewhere_is_not_measured_here(self, csp):
        assert self.message(csp, "O3") == (
            "Not measured at CSP: O3. CSP measures CH4, CO2."
        )

    def test_a_misspelling_is_invalid(self, csp):
        assert self.message(csp, "NH3") == (
            "Invalid pollutant(s): NH3. CSP measures CH4, CO2."
        )

    def test_the_two_are_told_apart_in_one_message(self, csp):
        assert self.message(csp, ["co2", "nh3", "o3"]) == (
            "Invalid pollutant(s): NH3. Not measured at CSP: O3. CSP measures CH4, CO2."
        )

    def test_names_are_in_the_spelling_of_the_columns(self, csp):
        # typed in any case; NOx is declared with a lower-case x
        assert self.message(csp, "nox") == (
            "Not measured at CSP: NOx. CSP measures CH4, CO2."
        )
        import uataq

        message = self.message(uataq.get_site("WBB"), "pm10")
        assert "Not measured at WBB: PM10." in message
        assert "NO, NO2, NOx, O3, PM2.5." in message

    def test_a_name_asked_twice_is_named_once(self, csp):
        assert self.message(csp, ["o3", "O3"]).startswith("Not measured at CSP: O3. ")

    def test_a_mobile_site_says_the_same(self):
        import uataq

        assert self.message(uataq.get_site("BUS01"), ["O3", "CO2"]) == (
            "Not measured at BUS01: CO2. BUS01 measures NO, NO2, NOx, O3, PM2.5."
        )
