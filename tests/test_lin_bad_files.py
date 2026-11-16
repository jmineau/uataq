"""
A lin ``.dat`` file that is not what the reader expects is named, not misread (#199).

Each case was a read that returned wrong data with no error, or failed with a
bare pandas traceback that did not say which file. The archives here are small
synthetic ones in the documented layout under ``tmp_path``.
"""

import warnings
from unittest.mock import patch

import pandas as pd
import pytest

import uataq
from uataq import errors
from uataq.filesystem.groupspaces import lin

CONFIG = {
    "final": {
        "col_names": ["Time_UTC", "O3_ppb", "Flow_ccm"],
        "col_types": "Tdd",
    }
}


def table(day="2024-06-01", hours=24, **columns):
    """Hourly rows of a T400 final file (the pipeline's columns, in its order)."""
    times = pd.date_range(day, periods=hours, freq="h").strftime("%Y-%m-%d %H:%M:%S")
    frame = pd.DataFrame(
        {
            "Time_UTC": times,
            "O3_ppb": [40.0 + h for h in range(hours)],
            "Flow_ccm": 500.0,
        }
    )
    return frame.assign(**columns)


@pytest.fixture(autouse=True)
def config():
    with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": CONFIG}):
        yield


@pytest.fixture
def final(lin_data_dir):
    """The WBB T400 final folder of a synthetic archive."""
    folder = lin_data_dir / "wbb" / "teledyne_t400" / "final"
    folder.mkdir(parents=True)
    return folder


def write(folder, name, frame, header=True):
    path = folder / name
    frame.to_csv(path, index=False, header=header)
    return path


def read(time_range="2024-06"):
    return uataq.read_data("WBB", "teledyne_t400", time_range=time_range)[
        "teledyne_t400"
    ]


class TestHeader:
    """The file's header is checked against the pipeline's config."""

    def test_a_header_in_another_order_reads_by_name(self, final):
        write(final, "2024_06_final.dat", table()[["Time_UTC", "Flow_ccm", "O3_ppb"]])
        data = read()
        assert data["O3_ppb"].tolist() == [40.0 + h for h in range(24)]
        assert (data["Flow_ccm"] == 500.0).all()
        assert sorted(data.columns) == ["Flow_ccm", "O3_ppb"]

    def test_a_renamed_column_names_the_file(self, final):
        path = write(
            final, "2024_06_final.dat", table().rename(columns={"O3_ppb": "O3_ppt"})
        )
        with pytest.raises(errors.ReaderError, match="2024_06_final.dat") as e:
            read()
        assert str(path) in str(e.value)
        assert "O3_ppt" in str(e.value)
        assert "lacks O3_ppb" in str(e.value)

    def test_an_extra_column_names_the_file(self, final):
        write(final, "2024_06_final.dat", table().assign(N2O_ppb=330.0))
        with pytest.raises(errors.ReaderError, match="2024_06_final.dat.*N2O_ppb"):
            read()

    def test_a_missing_column_names_the_file(self, final):
        write(final, "2024_06_final.dat", table().drop(columns="Flow_ccm"))
        with pytest.raises(errors.ReaderError, match="lacks Flow_ccm"):
            read()

    def test_the_other_months_still_read_when_one_is_wrong(self, final):
        write(final, "2024_06_final.dat", table())
        write(final, "2024_07_final.dat", table("2024-07-01").drop(columns="Flow_ccm"))
        with pytest.warns(errors.DataFileWarning, match="2024_07_final.dat"):
            data = read(["2024-06", "2024-07"])
        assert len(data) == 24

    def test_a_headerless_file_with_the_wrong_column_count(self, lin_data_dir):
        folder = lin_data_dir / "wbb" / "teledyne_t400" / "final"
        folder.mkdir(parents=True)
        write(folder, "2024_06_final.dat", table().assign(extra=1.0), header=False)
        with pytest.raises(errors.ReaderError, match="4 columns.*config lists 3"):
            read()

    def test_a_headerless_file_of_the_right_width_still_reads(self, final):
        write(final, "2024_06_final.dat", table(), header=False)
        assert len(read()) == 24


class TestUnparsedTimes:
    def test_rows_with_times_that_do_not_parse_are_warned_with_the_count(self, final):
        frame = table(hours=6)
        frame.loc[::2, "Time_UTC"] = "06/01/2024 01:00"
        path = write(final, "2024_06_final.dat", frame)
        with pytest.warns(errors.DataFileWarning, match="3 of 6 rows") as w:
            data = read()
        assert str(path) in str(w[0].message)
        assert "06/01/2024 01:00" in str(w[0].message)
        assert len(data) == 3

    def test_clean_times_do_not_warn(self, final):
        write(final, "2024_06_final.dat", table())
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert len(read()) == 24


class TestFileNames:
    """Only YYYY_MM_<level>.dat in the level's folder is one of the pipeline's files."""

    def test_a_copy_kept_beside_the_file_is_not_read(self, final):
        write(final, "2024_06_final.dat", table())
        write(final, "2024_06_final_old.dat", table())
        with warnings.catch_warnings():
            warnings.simplefilter("error", errors.DataFileWarning)
            assert len(read()) == 24

    @pytest.mark.parametrize(
        "name", ["README.dat", "2024_06.dat", "2024_6_final.dat", "final.dat"]
    )
    def test_a_file_that_is_not_a_period_is_skipped(self, final, name):
        write(final, "2024_06_final.dat", table())
        (final / name).write_text("notes\n")
        assert len(read()) == 24

    def test_the_level_in_the_name_is_the_folders(self, final):
        write(final, "2024_06_qaqc.dat", table())
        with pytest.raises(errors.ReaderError, match="No files found"):
            read()

    def test_the_initializer_says_why(self, final):
        with pytest.raises(errors.DataFileInitializationError, match="README.dat"):
            lin.LinDatFile(str(final / "README.dat"))


class TestEmptyFiles:
    def test_an_empty_file_has_no_rows_and_does_not_fail_the_read(self, final):
        write(final, "2024_06_final.dat", table())
        (final / "2024_07_final.dat").write_text("")
        data = read(["2024-06", "2024-07"])
        assert len(data) == 24

    def test_a_header_only_file_has_no_rows(self, final):
        (final / "2024_06_final.dat").write_text("Time_UTC,O3_ppb,Flow_ccm\n")
        with pytest.warns(errors.EmptyResultWarning):
            data = uataq.get_obs("WBB", "O3", time_range="2024-06")
        assert data.empty

    def test_the_parse_of_an_empty_file_has_the_columns(self, final):
        path = final / "2024_06_final.dat"
        path.write_text("")
        data = lin.LinDatFile(str(path)).parse()
        assert list(data.columns) == CONFIG["final"]["col_names"]
        assert data.empty


class TestRepeatedTimes:
    """Rows that share a time are returned as read, with a warning that names the files."""

    def test_two_files_that_overlap(self, final):
        write(final, "2024_06_final.dat", table("2024-06-01", 48))
        write(final, "2024_07_final.dat", table("2024-06-02", 24))
        with pytest.warns(errors.DataFileWarning, match="24 rows repeat") as w:
            data = read(["2024-06", "2024-07"])
        assert "2024_06_final.dat" in str(w[0].message)
        assert "2024_07_final.dat" in str(w[0].message)
        assert len(data) == 72  # unchanged: the data are returned as read

    def test_rows_repeated_in_one_file(self, final):
        frame = table()
        write(final, "2024_06_final.dat", pd.concat([frame, frame.iloc[:5]]))
        with pytest.warns(errors.DataFileWarning, match="5 rows repeat"):
            data = read()
        assert len(data) == 29

    def test_repeats_outside_the_range_do_not_warn(self, final):
        frame = table("2024-06-01", 48)
        write(final, "2024_06_final.dat", pd.concat([frame, frame.iloc[:5]]))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert len(read("2024-06-02")) == 24

    def test_distinct_times_do_not_warn(self, final):
        write(final, "2024_06_final.dat", table("2024-06-01", 48))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            read()


class TestMissingInstrumentFolder:
    """An instrument in the config with no folder on disk is a ReaderError, not FileNotFoundError."""

    def test_read_data_skips_to_a_reader_error(self, lin_data_dir):
        (lin_data_dir / "wbb").mkdir()
        with pytest.raises(errors.ReaderError, match="teledyne_t400"):
            uataq.read_data("WBB", "teledyne_t400", time_range="2024-06")

    def test_the_other_instruments_of_the_site_still_read(self, final):
        write(final, "2024_06_final.dat", table())
        # the site's other instruments have no folder here
        data = uataq.read_data("WBB", "all", time_range="2024-06")
        assert list(data) == ["teledyne_t400"]

    def test_a_network_skips_the_site(self, final):
        write(final, "2024_06_final.dat", table())
        net = uataq.Network(["WBB", "SUG"], "O3")
        obs = net.get_obs(time_range="2024-06")
        assert set(obs.SID) == {"WBB"}
