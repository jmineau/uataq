"""
Tests for Network data availability (get_availability / plot_availability).
"""

import pandas as pd
import pytest

from uataq import Network, instruments
from uataq.network import _coverage_to_segments, concentration_columns


class TestConcentrationColumns:
    """Pick the measured concentration, not diagnostics sharing the prefix."""

    def test_skips_diagnostics_and_spreads(self):
        cols = ["Time_UTC", "O3_ppb", "O3_Meas_mV", "O3_std_ppb", "O3_ppb_std"]
        assert concentration_columns("O3", cols) == ["O3_ppb"]

    def test_dry_and_calibrated(self):
        cols = ["CO2d_ppm_cal", "CO2d_ppm_raw", "CO2d_ppm", "CO2d_m", "CO_ppb"]
        assert concentration_columns("CO2", cols) == ["CO2d_ppm_cal", "CO2d_ppm"]

    def test_prefix_does_not_leak(self):
        """CO must not match CO2, NO must not match NO2, PM1 must not match PM10."""
        assert concentration_columns("CO", ["CO2_ppm", "CO_ppb"]) == ["CO_ppb"]
        assert concentration_columns("NO", ["NO2_ppb", "NOx_ppb", "NO_ppb"]) == [
            "NO_ppb"
        ]
        assert concentration_columns("PM1", ["PM10_ugm3", "PM1_ugm3"]) == ["PM1_ugm3"]

    def test_case_and_special_characters(self):
        assert concentration_columns("NOX", ["NOx_ppb"]) == ["NOx_ppb"]
        assert concentration_columns("PM2.5", ["PM2.5_ugm3", "PM205_ugm3"]) == [
            "PM2.5_ugm3"
        ]

    def test_raw_is_opt_in(self):
        cols = ["CO2d_ppm_cal", "CO2d_ppm_raw", "CO2d_ppm_raw_sd"]
        assert concentration_columns("CO2", cols, raw=True) == [
            "CO2d_ppm_cal",
            "CO2d_ppm_raw",
        ]

    def test_black_carbon_channels(self):
        cols = ["BC1_ngm3", "BC6_ngm3", "BC_Flag"]
        assert concentration_columns("BC", cols) == ["BC1_ngm3", "BC6_ngm3"]


def day(s: str) -> pd.Period:
    return pd.Period(s, freq="D")


class TestCoverageToSegments:
    """Bins take their best level, then consecutive bins merge."""

    def test_highest_level_wins_and_runs_merge(self):
        coverage = {
            "raw": {day("2024-01-01"), day("2024-01-02"), day("2024-01-03")},
            "final": {day("2024-01-02"), day("2024-01-03")},
        }
        segments = _coverage_to_segments("WBB", coverage)
        assert [(s["lvl"], s["start"], s["stop"]) for s in segments] == [
            ("raw", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")),
            ("final", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-04")),
        ]
        assert all(s["SID"] == "WBB" for s in segments)

    def test_gap_splits_a_run(self):
        coverage = {"qaqc": {day("2024-01-01"), day("2024-01-03")}}
        segments = _coverage_to_segments("WBB", coverage)
        assert [(s["start"], s["stop"]) for s in segments] == [
            (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")),
            (pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-04")),
        ]

    def test_monthly_bins(self):
        coverage = {"final": {pd.Period("2024-01", "M"), pd.Period("2024-02", "M")}}
        (segment,) = _coverage_to_segments("WBB", coverage)
        assert segment["start"] == pd.Timestamp("2024-01-01")
        assert segment["stop"] == pd.Timestamp("2024-03-01")

    def test_empty(self):
        assert _coverage_to_segments("WBB", {}) == []


class FakeDataFile:
    """Stands in for a DataFile: parses to a fixed frame."""

    def __init__(self, data: pd.DataFrame):
        self.data = data

    def parse(self) -> pd.DataFrame:
        return self.data.copy()


class BrokenDataFile:
    """A DataFile whose parse fails."""

    def parse(self) -> pd.DataFrame:
        raise OSError("corrupt")


@pytest.fixture
def fake_archive(monkeypatch):
    """Serve WBB ozone from memory: raw for two days, final for the second."""
    times = pd.to_datetime(["2024-01-01 12:00", "2024-01-02 12:00"])
    files = {
        "raw": [
            FakeDataFile(pd.DataFrame({"Time_UTC": times, "O3_ppb": [30.0, 31.0]})),
            BrokenDataFile(),
        ],
        # A stray header row (NaT time, text values) must not break anything,
        # and an all-NaN concentration must not count as data.
        "final": [
            FakeDataFile(
                pd.DataFrame(
                    {
                        "Time_UTC": [pd.NaT, times[0], times[1]],
                        "O3_ppb": ["O3_ppb", None, "31.0"],
                    }
                )
            )
        ],
    }

    def get_datafiles(self, group, lvl, time_range, pattern=None):
        if lvl not in files:
            raise FileNotFoundError(lvl)
        return files[lvl]

    monkeypatch.setattr(instruments.Instrument, "get_datafiles", get_datafiles)
    monkeypatch.setattr(
        instruments.Instrument, "standardize_data", lambda self, group, data: data
    )


class TestGetAvailability:
    """End-to-end over an in-memory archive."""

    def test_segments(self, fake_archive):
        net = Network(["WBB"], "O3")
        availability = net.get_availability(["2024-01-01", "2024-01-05"])
        assert list(availability.columns) == ["SID", "lvl", "start", "stop"]
        assert [(r.lvl, r.start, r.stop) for r in availability.itertuples()] == [
            ("raw", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")),
            ("final", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")),
        ]

    def test_time_range_clips_rows(self, fake_archive):
        net = Network(["WBB"], "O3")
        availability = net.get_availability(["2024-01-02", "2024-01-05"])
        assert list(availability["lvl"]) == ["final"]

    def test_level_subset(self, fake_archive):
        net = Network(["WBB"], "O3")
        availability = net.get_availability(lvls=["raw"])
        assert set(availability["lvl"]) == {"raw"}

    def test_invalid_level(self):
        with pytest.raises(ValueError, match="Invalid level"):
            Network(["WBB"], "O3").get_availability(lvls=["gold"])

    def test_plot(self, fake_archive):
        pytest.importorskip("matplotlib")
        import matplotlib

        matplotlib.use("Agg")
        net = Network(["WBB"], "O3")
        ax = net.plot_availability(net.get_availability())
        assert [t.get_text() for t in ax.get_yticklabels()] == ["WBB"]
        assert {t.get_text() for t in ax.get_legend().get_texts()} == {"raw", "final"}


def test_network_all_sites():
    """'all' keeps every configured site that measures the pollutant."""
    net = Network("all", "O3")
    assert "WBB" in {site.SID for site in net.site_objects}
    assert all("O3" in site.pollutants for site in net.site_objects)


@pytest.mark.chpc
def test_availability_real_archive():
    """WBB ozone over two days of the real archive."""
    net = Network(["WBB"], "O3")
    availability = net.get_availability(["2023-07-01", "2023-07-03"])
    assert not availability.empty
    assert set(availability["lvl"]) <= {"raw", "qaqc", "calibrated", "final"}
