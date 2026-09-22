"""
Tests for uataq.gps and the GPS instrument's motion estimation (uataq#2).
"""

import numpy as np
import pandas as pd
import pytest

from uataq import gps, instruments

#: meters per degree of latitude on the sphere gps.py assumes
M_PER_DEG_LAT = np.pi * gps.EARTH_RADIUS_M / 180


def straight_track(speed=10.0, n=11, freq="1s", lat0=40.0, lon0=-111.0, heading="N"):
    """A constant-speed track due north or east, and its times."""
    time = pd.date_range("2024-01-01", periods=n, freq=freq)
    step = speed * (time[1] - time[0]).total_seconds() / M_PER_DEG_LAT
    offsets = np.arange(n) * step
    if heading == "N":
        return lat0 + offsets, np.full(n, lon0), time
    return np.full(n, lat0), lon0 + offsets / np.cos(np.deg2rad(lat0)), time


class TestHaversine:
    def test_one_degree_of_latitude(self):
        assert gps.haversine(40, -111, 41, -111) == pytest.approx(111194.9, abs=1)

    def test_coincident_points(self):
        assert gps.haversine(40, -111, 40, -111) == pytest.approx(0.0)

    def test_symmetric(self):
        assert gps.haversine(40, -111, 41, -110) == pytest.approx(
            gps.haversine(41, -110, 40, -111)
        )

    def test_broadcasts(self):
        d = gps.haversine(40, -111, np.array([41.0, 42.0]), -111)
        np.testing.assert_allclose(d, [111194.9, 222389.8], atol=1)

    def test_radius_argument(self):
        assert gps.haversine(40, -111, 41, -111, R=1.0) == pytest.approx(
            np.deg2rad(1.0), abs=1e-9
        )


class TestBearing:
    @pytest.mark.parametrize(
        "p2, expected",
        [((41, -111), 0.0), ((40, -110), 89.678), ((39, -111), 180.0)],
    )
    def test_cardinal_directions(self, p2, expected):
        assert gps.bearing(40, -111, *p2) == pytest.approx(expected, abs=1e-3)

    def test_in_range(self):
        b = gps.bearing(40, -111, np.array([41.0, 39.0, 40.0]), np.array([-112.0] * 3))
        assert ((b >= 0) & (b < 360)).all()

    def test_matches_pyproj_sphere(self):
        pyproj = pytest.importorskip("pyproj")
        g = pyproj.Geod(a=gps.EARTH_RADIUS_M, b=gps.EARTH_RADIUS_M)
        rng = np.random.default_rng(0)
        lat1, lat2 = rng.uniform(-80, 80, (2, 100))
        lon1, lon2 = rng.uniform(-180, 180, (2, 100))
        az12, _, dist = g.inv(lon1, lat1, lon2, lat2)
        got = gps.bearing(lat1, lon1, lat2, lon2)
        assert np.abs((got - az12 % 360 + 180) % 360 - 180).max() < 1e-6
        np.testing.assert_allclose(
            gps.haversine(lat1, lon1, lat2, lon2), dist, rtol=1e-9
        )


class TestEstimateSpeedCourse:
    def test_constant_speed_northbound(self):
        lat, lon, time = straight_track(speed=10.0)
        out = gps.estimate_speed_course(lat, lon, time)
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 10.0, atol=1e-3)
        np.testing.assert_allclose(out.Course_deg.dropna(), 0.0, atol=1e-6)

    def test_constant_speed_eastbound(self):
        lat, lon, time = straight_track(speed=25.0, heading="E")
        out = gps.estimate_speed_course(lat, lon, time)
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 25.0, rtol=1e-3)
        np.testing.assert_allclose(out.Course_deg.dropna(), 90.0, atol=0.01)

    def test_stationary_gives_zero(self):
        time = pd.date_range("2024-01-01", periods=5, freq="1s")
        out = gps.estimate_speed_course(np.full(5, 40.0), np.full(5, -111.0), time)
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 0.0, atol=1e-9)

    def test_edges_are_nan(self):
        lat, lon, time = straight_track(n=5)
        out = gps.estimate_speed_course(lat, lon, time)
        assert out.Speed_m_s.isna().to_numpy().tolist() == [
            True,
            False,
            False,
            False,
            True,
        ]

    def test_window_widens_the_nan_edges(self):
        lat, lon, time = straight_track(n=9)
        out = gps.estimate_speed_course(lat, lon, time, window=2)
        assert out.Speed_m_s.isna().to_numpy()[:2].all()
        assert out.Speed_m_s.isna().to_numpy()[-2:].all()
        np.testing.assert_allclose(out.Speed_m_s.iloc[2:-2], 10.0, atol=1e-3)

    def test_window_averages_over_a_longer_baseline(self):
        """A wider window suppresses position noise on a stationary platform."""
        rng = np.random.default_rng(1)
        n = 400
        time = pd.date_range("2024-01-01", periods=n, freq="1s")
        jitter = rng.normal(0, 3.0, (2, n)) / M_PER_DEG_LAT  # ~3 m GPS noise
        lat, lon = 40.0 + jitter[0], -111.0 + jitter[1]
        narrow = gps.estimate_speed_course(lat, lon, time, window=1).Speed_m_s
        wide = gps.estimate_speed_course(lat, lon, time, window=30).Speed_m_s
        assert narrow.mean() > 3 * wide.mean()

    def test_gap_is_not_bridged(self):
        time = pd.DatetimeIndex(
            ["2024-01-01 00:00:00", "2024-01-01 00:00:01", "2024-01-01 01:00:00"]
        )
        out = gps.estimate_speed_course([40.0, 40.001, 41.0], [-111.0] * 3, time)
        assert out.Speed_m_s.isna().all()

    def test_gap_check_can_be_disabled(self):
        time = pd.DatetimeIndex(
            ["2024-01-01 00:00:00", "2024-01-01 00:00:01", "2024-01-01 01:00:00"]
        )
        out = gps.estimate_speed_course(
            [40.0, 40.001, 41.0], [-111.0] * 3, time, max_gap=None
        )
        assert out.Speed_m_s.notna().iloc[1]

    def test_gap_only_blanks_the_affected_samples(self):
        lat, lon, time = straight_track(n=11)
        time = time.to_list()
        time[6] = time[6] + pd.Timedelta("10min")  # one late fix
        out = gps.estimate_speed_course(lat, lon, pd.DatetimeIndex(time))
        assert out.Speed_m_s.iloc[1:5].notna().all()
        assert out.Speed_m_s.iloc[5:8].isna().all()

    def test_duplicate_timestamps_are_nan_not_inf(self):
        time = pd.DatetimeIndex(["2024-01-01 00:00:00"] * 3)
        out = gps.estimate_speed_course([40.0, 40.001, 40.002], [-111.0] * 3, time)
        assert not np.isinf(out.Speed_m_s.to_numpy()).any()
        assert out.Speed_m_s.isna().all()

    def test_series_index_supplies_time(self):
        lat, lon, time = straight_track()
        out = gps.estimate_speed_course(
            pd.Series(lat, index=time), pd.Series(lon, index=time)
        )
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 10.0, atol=1e-3)
        assert out.index.name == "Time_UTC"

    def test_time_required_without_datetime_index(self):
        with pytest.raises(ValueError, match="time is required"):
            gps.estimate_speed_course([40.0, 41.0], [-111.0, -111.0])

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            gps.estimate_speed_course(
                [40.0, 41.0], [-111.0], pd.date_range("2024-01-01", periods=2, freq="s")
            )

    def test_window_must_be_positive(self):
        lat, lon, time = straight_track()
        with pytest.raises(ValueError, match="window must be"):
            gps.estimate_speed_course(lat, lon, time, window=0)

    def test_too_few_samples_returns_all_nan(self):
        time = pd.date_range("2024-01-01", periods=2, freq="1s")
        out = gps.estimate_speed_course([40.0, 40.1], [-111.0, -111.0], time, window=3)
        assert len(out) == 2 and out.Speed_m_s.isna().all()

    def test_nan_positions_propagate_without_raising(self):
        lat, lon, time = straight_track(n=7)
        lat = lat.copy()
        lat[3] = np.nan
        out = gps.estimate_speed_course(lat, lon, time)
        assert out.Speed_m_s.notna().any()


class TestGPSInstrumentMotion:
    """GPS.estimate_motion: fill what the receiver did not record."""

    @staticmethod
    def frame(n=11, **cols):
        lat, lon, time = straight_track(n=n)
        return pd.DataFrame(
            {"Latitude_deg": lat, "Longitude_deg": lon, **cols}, index=time
        )

    def test_fills_missing_columns(self):
        out = instruments.GPS.estimate_motion(self.frame())
        assert "Speed_m_s" in out and "Course_deg" in out
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 10.0, atol=1e-3)
        assert out.Speed_Estimated.iloc[1:-1].all()
        assert not out.Speed_Estimated.iloc[0]  # edge: nothing to fill with
        assert out.Course_Estimated.iloc[1:-1].all()

    def test_recorded_values_are_never_overwritten(self):
        df = self.frame(Speed_m_s=np.full(11, 3.0), Course_deg=np.full(11, 42.0))
        out = instruments.GPS.estimate_motion(df)
        assert (out.Speed_m_s == 3.0).all()
        assert (out.Course_deg == 42.0).all()
        assert not out.Speed_Estimated.any()
        assert not out.Course_Estimated.any()

    def test_fills_only_the_missing_rows(self):
        speed = np.full(11, 3.0)
        speed[5] = np.nan
        out = instruments.GPS.estimate_motion(self.frame(Speed_m_s=speed))
        assert out.Speed_m_s.iloc[5] == pytest.approx(10.0, abs=1e-3)
        assert out.Speed_Estimated.iloc[5]
        assert not out.Speed_Estimated.drop(out.index[5]).any()

    def test_all_na_string_column_is_coerced(self):
        """The GPGGA-only years hand back an all-NA Speed column typed as strings."""
        df = self.frame()
        df["Speed_m_s"] = pd.Series([None] * len(df), index=df.index, dtype="str")
        out = instruments.GPS.estimate_motion(df)
        assert pd.api.types.is_numeric_dtype(out.Speed_m_s)
        np.testing.assert_allclose(out.Speed_m_s.dropna(), 10.0, atol=1e-3)
        assert out.Speed_Estimated.iloc[1:-1].all()

    def test_no_positions_is_a_no_op(self):
        df = pd.DataFrame(
            {"Speed_m_s": [1.0, 2.0]},
            index=pd.date_range("2024-01-01", periods=2, freq="1s"),
        )
        out = instruments.GPS.estimate_motion(df)
        assert out.columns.tolist() == ["Speed_m_s"]

    def test_non_datetime_index_is_a_no_op(self):
        lat, lon, _ = straight_track(n=5)
        df = pd.DataFrame({"Latitude_deg": lat, "Longitude_deg": lon})
        assert instruments.GPS.estimate_motion(df).columns.tolist() == [
            "Latitude_deg",
            "Longitude_deg",
        ]

    def test_empty_frame_is_a_no_op(self):
        df = pd.DataFrame(
            {"Latitude_deg": [], "Longitude_deg": []}, index=pd.DatetimeIndex([])
        )
        assert instruments.GPS.estimate_motion(df).empty
