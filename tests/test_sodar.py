"""
Tests for the Horel group SODAR reader (uataq.sodar).

Synthetic archives are written with PyTables under ``tmp_path`` using the same
layout as the real Horel archive::

    {mesowest_dir}/sodar_data/hdf5archive/
        {SID}_full_metadata_log.h5   /metagroup/{metadata,variables}
        {SID}_{YYYY}_{MM}_sodar.h5   /obsdata/observations

Tests against the real CHPC archive are skipped when it is not mounted.
"""

import datetime as dt
import os

import numpy as np
import pandas as pd
import pytest
import tables
import xarray as xr

from uataq import sodar
from uataq.filesystem.groupspaces import horel
from uataq.sodar import Sodar, list_stations

MULT = 100  # archive stores WS/WD/MXWS as int(value * 100)


# -- synthetic archive helpers ------------------------------------------------


def archive_dir(mesowest_dir) -> str:
    """Return (and create) the hdf5archive dir below a mesowest dir."""
    path = os.path.join(mesowest_dir, "sodar_data", "hdf5archive")
    os.makedirs(path, exist_ok=True)
    return path


def write_metadata(mesowest_dir, SID, extra_vars=()):
    """Write a {SID}_full_metadata_log.h5 like the Horel archive."""
    meta = np.array(
        [
            (
                1,
                5,
                SID.encode(),
                SID.encode(),
                b"Test SODAR",
                40.7,
                -111.9,
                1300.0,
                b"2019-02-05",
            )
        ],
        dtype=[
            ("ID", "<u2"),
            ("STATION_ID", "<u2"),
            ("STID", "S8"),
            ("ALIAS", "S8"),
            ("NAME", "S32"),
            ("LATITUDE", "<f4"),
            ("LONGITUDE", "<f4"),
            ("ELEVATION", "<f4"),
            ("DATE_CHANGED", "S10"),
        ],
    )
    names = ["WS", "WD", "MXWS", *extra_vars]
    variables = np.array(
        [
            (i + 1, name.encode(), b"", b"", name.lower().encode(), MULT, b"")
            for i, name in enumerate(names)
        ],
        dtype=[
            ("ID", "<u2"),
            ("SHORTNAME", "S8"),
            ("LONGNAME", "S32"),
            ("UNITS", "S16"),
            ("VARALIAS", "S8"),
            ("MULT", "<i4"),
            ("DATE_ADDED", "S10"),
        ],
    )
    path = os.path.join(archive_dir(mesowest_dir), f"{SID}_full_metadata_log.h5")
    with tables.open_file(path, "w") as f:
        group = f.create_group("/", "metagroup")
        f.create_table(group, "metadata", obj=meta)
        f.create_table(group, "variables", obj=variables)
    return path


def write_month(mesowest_dir, SID, times, heights, ws, wd, name=None):
    """
    Write a monthly observation file.

    ``heights``/``ws``/``wd`` are (time, level) arrays in physical units;
    NaN is written as the -9999 NoData value.
    """
    heights, ws, wd = (np.asarray(a, dtype=float) for a in (heights, ws, wd))
    n_times, n_levels = heights.shape

    def raw(values, mult):
        out = np.where(np.isnan(values), -9999, np.round(values * mult))
        return out.astype("<i4")

    obs = np.zeros(
        n_times,
        dtype=[
            ("STATION_ID", "<u2"),
            ("DATTIM", "<i8"),
            ("HEIGHT", "<i4", (n_levels,)),
            ("MXWS", "<i4", (n_levels,)),
            ("WD", "<i4", (n_levels,)),
            ("WS", "<i4", (n_levels,)),
        ],
    )
    obs["STATION_ID"] = 5
    obs["DATTIM"] = pd.DatetimeIndex(times).as_unit("s").asi8
    obs["HEIGHT"] = raw(heights, 1)
    obs["MXWS"] = raw(ws, MULT)
    obs["WD"] = raw(wd, MULT)
    obs["WS"] = raw(ws, MULT)

    t0 = pd.Timestamp(times[0])
    name = name or f"{SID}_{t0.year:04d}_{t0.month:02d}_sodar.h5"
    path = os.path.join(archive_dir(mesowest_dir), name)
    with tables.open_file(path, "w") as f:
        group = f.create_group("/", "obsdata")
        f.create_table(group, "observations", obj=obs)
    return path


def write_hourly_month(mesowest_dir, SID, start, periods, heights=(10.0, 50.0)):
    """Hourly profiles with WS = hour-of-record and WD = 180, constant heights."""
    times = pd.date_range(start, periods=periods, freq="h")
    n_levels = len(heights)
    hs = np.tile(heights, (periods, 1))
    ws = np.tile(np.arange(periods, dtype=float)[:, None], (1, n_levels))
    wd = np.full((periods, n_levels), 180.0)
    return write_month(mesowest_dir, SID, times, hs, ws, wd)


@pytest.fixture
def mesowest(tmp_path):
    """A MesoWest dir with station USDR1 and two months (Jan 31 + Feb 1)."""
    write_metadata(tmp_path, "USDR1")
    # Jan 31 00:00 .. 23:00 and Feb 1 00:00 .. 05:00
    write_hourly_month(tmp_path, "USDR1", "2024-01-31 00:00", 24)
    write_hourly_month(tmp_path, "USDR1", "2024-02-01 00:00", 6)
    return tmp_path


def touch_files(mesowest_dir, names):
    """Create empty files in the archive dir."""
    for name in names:
        open(os.path.join(archive_dir(mesowest_dir), name), "w").close()


def names(files):
    """Basenames of file paths."""
    return [os.path.basename(f) for f in files]


# -- module -------------------------------------------------------------------


class TestModule:
    """Module-level constants and helpers."""

    def test_mesowest_dir_in_horel_groupspace(self):
        """The archive is located through the Horel group space."""
        expected = os.path.join(horel.HOREL_DIR, "oper", "mesowest")
        assert expected == horel.MESOWEST_DIR

    def test_list_stations(self, tmp_path):
        """Stations are the SIDs with a metadata log."""
        write_metadata(tmp_path, "USDR1")
        write_metadata(tmp_path, "WSLSA")
        touch_files(tmp_path, ["all_sodar_metadata.h5", "USDR1_2024_01_sodar.h5"])
        assert list_stations(str(tmp_path)) == ["USDR1", "WSLSA"]

    def test_num_processes_capped_by_files(self):
        """An empty file list gives zero processes (never Pool(0))."""
        assert sodar._num_processes(4, 0) == 0
        assert sodar._num_processes("max", 0) == 0
        assert sodar._num_processes(8, 2) <= 2
        assert sodar._num_processes(1, 5) == 1

    def test_num_processes_invalid(self):
        """Non-positive process counts are rejected."""
        with pytest.raises(ValueError, match="num_processes"):
            sodar._num_processes(0, 3)


# -- Sodar() --------------------------------------------------------------------


class TestSodarInit:
    """Constructing a Sodar reads the station metadata log."""

    def test_reads_metadata(self, tmp_path):
        """Metadata and variable scale factors are loaded; SID is upper-cased."""
        write_metadata(tmp_path, "USDR1")
        s = Sodar("usdr1", mesowest_dir=str(tmp_path))
        assert s.SID == "USDR1"
        assert s.archive_dir == archive_dir(tmp_path)
        assert s.sodar_dir == os.path.join(str(tmp_path), "sodar_data")
        assert s.meta["STID"].iloc[0] == "USDR1"
        assert list(s.variables.index) == ["WS", "WD", "MXWS"]
        assert (s.variables["MULT"] == MULT).all()

    def test_defaults_to_horel_mesowest_dir(self, tmp_path, monkeypatch):
        """Without mesowest_dir the Horel group space location is used."""
        write_metadata(tmp_path, "USDR1")
        monkeypatch.setattr(horel, "MESOWEST_DIR", str(tmp_path))
        assert Sodar("USDR1").archive_dir == archive_dir(tmp_path)

    def test_missing_archive(self, tmp_path):
        """A missing archive directory fails clearly."""
        with pytest.raises(FileNotFoundError, match="SODAR archive not found"):
            Sodar("USDR1", mesowest_dir=str(tmp_path / "nope"))

    def test_unknown_station(self, tmp_path):
        """An unknown station lists the available ones."""
        write_metadata(tmp_path, "USDR1")
        with pytest.raises(FileNotFoundError, match=r"Available stations: \['USDR1'\]"):
            Sodar("XYZ", mesowest_dir=str(tmp_path))


# -- get_files ------------------------------------------------------------------


class TestGetFiles:
    """get_files() filters by exact station id, file name, and time range."""

    def test_filters_by_sid_and_name(self, tmp_path):
        """Only {SID}_{YYYY}_{MM}_sodar.h5 for this exact SID is returned."""
        write_metadata(tmp_path, "USDR1")
        touch_files(
            tmp_path,
            [
                "USDR1_2024_01_sodar.h5",
                "USDR1_2024_06_sodar.h5",
                "USDR10_2024_01_sodar.h5",  # longer SID sharing the prefix
                "USDR2_2024_01_sodar.h5",  # different SID
                "USDR1_2024_01_notes.txt",  # wrong suffix
                "USDR1_2024_02_sodar_p1.h5",  # partial file
                "USDR1_2024_13_sodar.h5",  # not a month
            ],
        )
        files = Sodar("USDR1", mesowest_dir=str(tmp_path)).get_files()
        assert names(files) == ["USDR1_2024_01_sodar.h5", "USDR1_2024_06_sodar.h5"]
        assert all(os.path.dirname(f) == archive_dir(tmp_path) for f in files)

    @pytest.mark.parametrize("SID", ["ABC", "ABCDEF", "KSLC1X"])
    def test_sid_length_independent(self, tmp_path, SID):
        """Dates are parsed from the name for SIDs that are not 5 characters."""
        write_metadata(tmp_path, SID)
        touch_files(tmp_path, [f"{SID}_2024_03_sodar.h5", f"{SID}_2024_09_sodar.h5"])
        s = Sodar(SID, mesowest_dir=str(tmp_path))
        assert names(s.get_files(time_range="2024-03")) == [f"{SID}_2024_03_sodar.h5"]

    def test_filters_by_time_range(self, tmp_path):
        """Months overlapping [start, stop) are kept."""
        write_metadata(tmp_path, "USDR1")
        touch_files(tmp_path, [f"USDR1_2024_{m:02d}_sodar.h5" for m in (1, 4, 6, 8)])
        s = Sodar("USDR1", mesowest_dir=str(tmp_path))
        # '2024-07' as a stop means "through July" -> stop = 2024-08-01 (exclusive)
        files = s.get_files(time_range=("2024-05", "2024-07"))
        assert names(files) == ["USDR1_2024_06_sodar.h5"]

    def test_file_starting_at_stop_is_excluded(self, tmp_path):
        """A month that begins exactly at the (exclusive) stop is not listed."""
        write_metadata(tmp_path, "USDR1")
        touch_files(tmp_path, ["USDR1_2024_01_sodar.h5", "USDR1_2024_02_sodar.h5"])
        s = Sodar("USDR1", mesowest_dir=str(tmp_path))
        files = s.get_files(time_range=["2024-01-15", dt.datetime(2024, 2, 1)])
        assert names(files) == ["USDR1_2024_01_sodar.h5"]

    @pytest.mark.parametrize(
        ("time_range", "expected"),
        [
            ("2024-01", ["2024_01"]),
            ("2023-12", ["2023_12"]),
            (("2023-12-31", "2024-01-01"), ["2023_12", "2024_01"]),
            ((None, dt.datetime(2024, 1, 1)), ["2023_12"]),
        ],
    )
    def test_december_rollover(self, tmp_path, time_range, expected):
        """Month bounds roll over the year correctly."""
        write_metadata(tmp_path, "USDR1")
        touch_files(tmp_path, ["USDR1_2023_12_sodar.h5", "USDR1_2024_01_sodar.h5"])
        s = Sodar("USDR1", mesowest_dir=str(tmp_path))
        files = s.get_files(time_range=time_range)
        assert names(files) == [f"USDR1_{e}_sodar.h5" for e in expected]

    def test_invalid_lvl(self, tmp_path):
        """Only raw data is archived."""
        write_metadata(tmp_path, "USDR1")
        with pytest.raises(ValueError, match="Only 'raw'"):
            Sodar("USDR1", mesowest_dir=str(tmp_path)).get_files(lvl="qaqc")


# -- parse ----------------------------------------------------------------------


class TestParse:
    """parse() turns one HDF5 file into a (Time_UTC, level) Dataset."""

    def test_structure_and_scaling(self, tmp_path):
        """Variables are scaled by MULT, NoData becomes NaN, HEIGHT is unscaled."""
        write_metadata(tmp_path, "USDR1")
        times = pd.date_range("2024-01-01", periods=2, freq="min")
        path = write_month(
            tmp_path,
            "USDR1",
            times,
            heights=[[40, 60, 80], [40, 60, 80]],
            ws=[[5.79, 5.82, np.nan], [1.0, 2.0, 3.0]],
            wd=[[166.4, 168.2, 167.1], [90.0, np.nan, 270.0]],
        )
        variables = Sodar("USDR1", mesowest_dir=str(tmp_path)).variables
        ds = Sodar.parse(path, variables)

        assert isinstance(ds, xr.Dataset)
        assert dict(ds.sizes) == {"Time_UTC": 2, "level": 3}
        assert ds["level"].values.tolist() == [0, 1, 2]
        assert (ds.indexes["Time_UTC"] == times).all()
        assert set(ds.data_vars) == {"STATION_ID", "HEIGHT", "MXWS", "WD", "WS"}
        assert ds["STATION_ID"].dims == ("Time_UTC",)
        np.testing.assert_allclose(ds["HEIGHT"].values[0], [40, 60, 80])
        np.testing.assert_allclose(ds["WS"].values[0], [5.79, 5.82, np.nan])
        np.testing.assert_allclose(ds["WD"].values[1], [90.0, np.nan, 270.0])

    def test_logged_variable_missing_from_file(self, tmp_path):
        """Variables in the metadata log but not in an (older) file are skipped."""
        write_metadata(tmp_path, "USDR1", extra_vars=("SNR",))
        path = write_hourly_month(tmp_path, "USDR1", "2024-01-01", 2)
        variables = Sodar("USDR1", mesowest_dir=str(tmp_path)).variables
        ds = Sodar.parse(path, variables)
        assert "SNR" not in ds


# -- read_data ------------------------------------------------------------------


class TestReadData:
    """read_data() combines files and slices to [start, stop)."""

    def test_reads_all(self, mesowest):
        """All months are combined and sorted by time."""
        data = Sodar("USDR1", mesowest_dir=str(mesowest)).read_data()
        times = data.indexes["Time_UTC"]
        assert len(times) == 24 + 6
        assert times.is_monotonic_increasing
        assert times[0] == pd.Timestamp("2024-01-31 00:00")
        assert times[-1] == pd.Timestamp("2024-02-01 05:00")

    def test_single_day_excludes_next_midnight(self, mesowest):
        """A date string covers that day only - no sample at the next 00:00."""
        data = Sodar("USDR1", mesowest_dir=str(mesowest)).read_data(
            time_range="2024-01-31"
        )
        times = data.indexes["Time_UTC"]
        assert len(times) == 24
        assert times[-1] == pd.Timestamp("2024-01-31 23:00")

    def test_date_string_stop_includes_whole_day(self, mesowest):
        """A date string as stop includes that day, but not the next midnight."""
        data = Sodar("USDR1", mesowest_dir=str(mesowest)).read_data(
            time_range=("2024-01-31T12", "2024-01-31")
        )
        times = data.indexes["Time_UTC"]
        assert times[0] == pd.Timestamp("2024-01-31 12:00")
        assert times[-1] == pd.Timestamp("2024-01-31 23:00")

    def test_datetime_stop_is_exclusive(self, mesowest):
        """A datetime stop is exclusive, matching uataq.TimeRange semantics."""
        data = Sodar("USDR1", mesowest_dir=str(mesowest)).read_data(
            time_range=[dt.datetime(2024, 2, 1, 1), dt.datetime(2024, 2, 1, 3)]
        )
        assert data.indexes["Time_UTC"].tolist() == [
            pd.Timestamp("2024-02-01 01:00"),
            pd.Timestamp("2024-02-01 02:00"),
        ]

    def test_no_files(self, mesowest):
        """No overlapping files raises FileNotFoundError before any parsing."""
        s = Sodar("USDR1", mesowest_dir=str(mesowest))
        with pytest.raises(FileNotFoundError, match="No raw SODAR files for USDR1"):
            s.read_data(time_range="2023")

    def test_parallel_matches_serial(self, mesowest):
        """num_processes > 1 gives the same result as serial parsing."""
        s = Sodar("USDR1", mesowest_dir=str(mesowest))
        xr.testing.assert_identical(s.read_data(num_processes=2), s.read_data())

    def test_level_count_change_is_padded(self, tmp_path):
        """Months with a different number of range gates are padded with NaN."""
        write_metadata(tmp_path, "USDR1")
        write_hourly_month(tmp_path, "USDR1", "2024-01-31", 2, heights=(10.0, 50.0))
        write_hourly_month(
            tmp_path, "USDR1", "2024-02-01", 2, heights=(10.0, 50.0, 90.0)
        )
        data = Sodar("USDR1", mesowest_dir=str(tmp_path)).read_data()
        assert dict(data.sizes) == {"Time_UTC": 4, "level": 3}
        assert np.isnan(data["HEIGHT"].values[:2, 2]).all()
        np.testing.assert_allclose(data["HEIGHT"].values[2:, 2], 90.0)


# -- get_winds_at_height -----------------------------------------------------------


def profile(heights, wd, ws, times=None):
    """Build a small (Time_UTC, level) SODAR-like Dataset."""
    heights = np.asarray(heights, dtype=float)
    times = (
        times
        if times is not None
        else pd.date_range("2024-01-01", periods=len(heights), freq="h")
    )
    return xr.Dataset(
        {
            "HEIGHT": (("Time_UTC", "level"), heights),
            "WD": (("Time_UTC", "level"), np.asarray(wd, dtype=float)),
            "WS": (("Time_UTC", "level"), np.asarray(ws, dtype=float)),
        },
        coords={"Time_UTC": times, "level": np.arange(heights.shape[1])},
    )


class TestGetWindsAtHeight:
    """get_winds_at_height() picks the level at a height at every timestamp."""

    def test_selects_level_and_renames(self):
        """Selects the level matching a height and renames columns."""
        ds = profile(
            np.tile([10.0, 50.0], (3, 1)),
            wd=[[100, 200], [110, 210], [120, 220]],
            ws=[[1, 2], [3, 4], [5, 6]],
        )
        winds = Sodar.get_winds_at_height(ds, 50.0)
        assert list(winds.columns) == ["direction", "speed"]
        assert winds.index.name == "Time_UTC"
        assert winds["direction"].tolist() == [200.0, 210.0, 220.0]
        assert winds["speed"].tolist() == [2.0, 4.0, 6.0]

    def test_missing_height_raises_value_error(self):
        """A height with no level raises a clear ValueError, not IndexError."""
        ds = profile(
            np.tile([10.0, 50.0], (2, 1)), wd=[[1, 2], [3, 4]], ws=[[1, 2], [3, 4]]
        )
        with pytest.raises(
            ValueError, match=r"height 75.*Available heights: \[10.0, 50.0\]"
        ):
            Sodar.get_winds_at_height(ds, 75)

    def test_heights_change_over_time(self):
        """The level is found per timestamp, not from the first record."""
        ds = profile(
            [[10.0, 50.0], [50.0, 90.0], [50.0, 90.0]],
            wd=[[100, 200], [300, 310], [320, 330]],
            ws=[[1, 2], [3, 4], [5, 6]],
        )
        # 90 m is absent from the first record but present later
        winds90 = Sodar.get_winds_at_height(ds, 90)
        assert winds90.index.tolist() == list(ds.indexes["Time_UTC"][1:])
        assert winds90["speed"].tolist() == [4.0, 6.0]
        # 50 m is level 1 first, then level 0
        winds50 = Sodar.get_winds_at_height(ds, 50)
        assert winds50["speed"].tolist() == [2.0, 3.0, 5.0]
        assert winds50["direction"].tolist() == [200.0, 300.0, 320.0]

    def test_drops_all_nan_rows(self):
        """Timestamps with no valid winds at the height are dropped."""
        ds = profile(
            np.tile([10.0, 50.0], (3, 1)),
            wd=[[1, np.nan], [2, 20], [3, 30]],
            ws=[[1, np.nan], [2, 2], [3, 3]],
        )
        winds = Sodar.get_winds_at_height(ds, 50)
        assert len(winds) == 2

    def test_without_level_coordinate(self):
        """Datasets without a level coordinate (old lair output) still work."""
        ds = profile(
            np.tile([10.0, 50.0], (2, 1)), wd=[[1, 2], [3, 4]], ws=[[5, 6], [7, 8]]
        )
        winds = Sodar.get_winds_at_height(ds.drop_vars("level"), 10)
        assert winds["speed"].tolist() == [5.0, 7.0]


def test_parse_then_winds_end_to_end(mesowest):
    """read_data() output feeds get_winds_at_height()."""
    data = Sodar("USDR1", mesowest_dir=str(mesowest)).read_data(time_range="2024-02-01")
    winds = Sodar.get_winds_at_height(data, 50)
    assert winds["speed"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    assert (winds["direction"] == 180.0).all()


# -- real CHPC archive (skipped off-cluster) ---------------------------------------

REAL_ARCHIVE = os.path.join(horel.MESOWEST_DIR, "sodar_data", "hdf5archive")
requires_archive = pytest.mark.skipif(
    not os.path.isdir(REAL_ARCHIVE), reason="Horel SODAR archive not available"
)


@requires_archive
class TestRealArchive:
    """Light reads against the real Horel archive (one ~200 KB file)."""

    def test_stations(self):
        """Known stations are listed."""
        stations = list_stations()
        assert {"USDR1", "USDR2", "WSLSA"} <= set(stations)

    def test_partial_file_is_skipped(self):
        """USDR2_2018_12_sodar_p1.h5 is not treated as a monthly file."""
        files = Sodar("USDR2").get_files(time_range="2018-12")
        assert names(files) == ["USDR2_2018_12_sodar.h5"]

    def test_read_one_day(self):
        """A single day from a small file parses to sensible winds."""
        s = Sodar("WSLSA")
        assert names(s.get_files(time_range="2019-06")) == ["WSLSA_2019_06_sodar.h5"]
        data = s.read_data(time_range="2019-06-01")
        times = data.indexes["Time_UTC"]
        assert times[0] >= pd.Timestamp("2019-06-01")
        assert times[-1] < pd.Timestamp("2019-06-02")
        assert {"HEIGHT", "WD", "WS"} <= set(data.data_vars)
        assert float(data["WS"].max()) < 100  # m/s after MULT scaling
        winds = Sodar.get_winds_at_height(data, 100)
        assert not winds.empty
        assert winds["direction"].dropna().between(0, 360).all()
