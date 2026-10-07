"""
Tests for the lin group space.

Archive files are mimicked with a few synthetic lines in ``tmp_path``, laid
out like ``measurements/data/{sid}/{instrument}/{lvl}/``: pipeline
``YYYY_MM_{lvl}.dat`` files, air-trend ``YYYY-MM-DD[_sentence].csv`` files and
LGR software ``gga*_f0000.txt`` files. The pipeline config entries the parsers
read are patched with small stand-ins, so the tests don't depend on its
current contents.
"""

import logging
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from uataq import errors
from uataq.filesystem.groupspaces import lin
from uataq.timerange import TimeRange

# The LGR software's 23 columns, as the pipeline config names them
UGGA_NAMES = [
    "Time_UTC", "CH4_ppm", "CH4_ppm_sd", "H2O_ppm", "H2O_ppm_sd", "CO2_ppm",
    "CO2_ppm_sd", "CH4d_ppm", "CH4d_ppm_sd", "CO2d_ppm", "CO2d_ppm_sd",
    "GasP_torr", "GasP_torr_sd", "GasT_C", "GasT_C_sd", "AmbT_C", "AmbT_C_sd",
    "RD0_us", "RD0_us_sd", "RD1_us", "RD1_us_sd", "Fit_Flag", "ID",
]  # fmt: skip
UGGA_CONFIG = {"raw": {"col_names": UGGA_NAMES, "col_types": "c" + "d" * 21 + "c"}}

GPS_CONFIG = {
    "air_trend_gpgga": {
        "col_names": ["time", "inst_time", "latitude_dm", "n_s", "longitude_dm",
                      "e_w", "fix_quality", "n_sat", "altitude_amsl"],
        "col_types": "Tcdcdcddd",
    },
    "air_trend_gprmc": {
        "col_names": ["time", "inst_time", "status", "latitude_dm", "n_s",
                      "longitude_dm", "e_w", "speed_kt", "true_course", "inst_date"],
        "col_types": "Tccdcdcddc",
    },
}  # fmt: skip

T400_CONFIG = {
    "final": {"col_names": ["Time_UTC", "O3_ppb"], "col_types": "Td"},
    "raw": {
        "col_names": ["TIMESTAMP", "RECORD", "MM", "SS", "O3_ppb"],
        "col_types": "Tdddd",
    },
}


def test_gps_degree_minutes_to_decimal_degrees():
    """NMEA ddmm.mmmm -> signed decimal degrees, NaN for unparseable values."""
    data = pd.DataFrame(
        {
            "latitude_dm": [4039.165, 3330.0, "bad"],
            "n_s": ["N", "S", "N"],
            "longitude_dm": [11155.9945, 1500.6, np.nan],
            "e_w": ["W", "E", "W"],
        }
    )
    out = lin.LinGroup.standardize_data("gps", data)

    assert out["Latitude_deg"].iloc[:2].tolist() == pytest.approx([40.65275, -33.5])
    assert out["Longitude_deg"].iloc[:2].tolist() == pytest.approx(
        [-111.933241667, 15.01]
    )
    assert out[["Latitude_deg", "Longitude_deg"]].iloc[2].isna().all()
    assert not {"latitude_dm", "longitude_dm", "n_s", "e_w"} & set(out.columns)


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"a\nb\nc\nlast\n", ["a", "b", "last"]),
        (b"a\nb\nc\npartial", ["a", "b", "partial"]),  # cut off mid-row
        (b"a\r\nb\r\nlast\r\n", ["a", "b", "last"]),
        (b"a\nb\n" + b"x" * 10000 + b"\n", ["a", "b", "x" * 10000]),
        (b"only\n", ["only", "", "only"]),
    ],
)
def test_read_lines_matches_head_and_tail(tmp_path, content, expected):
    """_read_lines(first=2, last=True) gives head -n 2 and tail -n 1."""
    path = tmp_path / "gga_2024-01-02_f0000.txt"
    path.write_bytes(content)
    assert lin._read_lines(str(path), first=2, last=True) == expected


class TestReadConfig:
    """Off-cluster config fetches fail fast with a clear message."""

    def test_local_file_is_read(self, tmp_path, monkeypatch):
        (tmp_path / "x.json").write_text('{"a": 1}')
        monkeypatch.setattr(lin, "CONFIG_DIR", str(tmp_path))
        assert lin._read_config("x.json").read() == '{"a": 1}'

    def test_fetch_failure_names_path_and_url(self, tmp_path, monkeypatch):
        import urllib.error
        import urllib.request

        def fail(url, timeout):
            assert timeout == lin.CONFIG_FETCH_TIMEOUT
            raise urllib.error.URLError("timed out")

        monkeypatch.setattr(lin, "CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(urllib.request, "urlopen", fail)
        with pytest.raises(RuntimeError, match="not on CHPC") as err:
            lin._read_config("site_config.csv")
        assert lin.CONFIG_URL in str(err.value)


def ugga_row(time: str, sep: str = ",", n_numeric: int = 20, tail=("3",)) -> str:
    """One LGR software data row: padded time, numbers, then text fields."""
    values = [f"{1.9 + i:15.6e}" for i in range(n_numeric)]
    return sep.join([f"  {time}", *values, *[f"{t:>15}" for t in tail]])


def write_ugga(path, version: str, rows: list[str], header_cols: int = 23) -> str:
    """Write an LGR software file: meta line, column header, data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = f"VC:{version} BD:Jan 16 2014 SN:LGR-13-0221"
    header = ",".join(f"col{i}" for i in range(header_cols))
    path.write_text("\n".join([meta, header, *rows]) + "\n")
    return str(path)


class TestDms2dd:
    def test_converts(self):
        assert lin.dms2dd(40, 30, 36) == pytest.approx(40.51)

    def test_unparseable_is_nan(self):
        assert np.isnan(lin.dms2dd("forty", 30))


class TestLinDatFile:
    """Pipeline ``.dat`` files: instrument and level come from the path."""

    def test_instrument_level_and_period_from_path(self, tmp_path):
        path = tmp_path / "wbb" / "teledyne_t400" / "final" / "2024_06_final.dat"
        path.parent.mkdir(parents=True)
        path.touch()
        datafile = lin.LinDatFile(str(path))
        assert datafile.instrument == "teledyne_t400"
        assert datafile.lvl == "final"
        assert datafile.period == pd.Period("2024-06", freq="M")

    def test_pipeline_header_gets_config_names(self, tmp_path):
        """
        A Time_UTC header is not TIMESTAMP, so the config names apply.

        The header line is skipped, not read in as a row that made every column
        text (uataq.get_obs returned object-dtype concentrations).
        """
        path = tmp_path / "wbb" / "teledyne_t400" / "final" / "2024_06_final.dat"
        path.parent.mkdir(parents=True)
        path.write_text(
            "Time_UTC,O3_ppb\n"
            "2024-06-01 00:00:01.270,47.2\n"
            "2024-06-01 00:00:03.310,47.1\n"
        )
        with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": T400_CONFIG}):
            data = lin.LinDatFile(str(path)).parse()

        assert list(data.columns) == ["Time_UTC", "O3_ppb"]
        assert data["Time_UTC"].tolist() == list(
            pd.to_datetime(["2024-06-01 00:00:01.270", "2024-06-01 00:00:03.310"])
        )
        assert data["O3_ppb"].dtype == float
        assert data["O3_ppb"].tolist() == [47.2, 47.1]

    def test_stray_text_in_a_numeric_column(self, tmp_path):
        """A config numeric column stays numeric; text in it becomes NaN."""
        path = tmp_path / "wbb" / "teledyne_t400" / "final" / "2024_06_final.dat"
        path.parent.mkdir(parents=True)
        path.write_text(
            "Time_UTC,O3_ppb\n2024-06-01 00:00:01,47.2\n2024-06-01 00:00:03,ERR\n"
        )
        with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": T400_CONFIG}):
            data = lin.LinDatFile(str(path)).parse()
        assert data["O3_ppb"].dtype == float
        assert data["O3_ppb"].isna().tolist() == [False, True]

    def test_headerless_file_keeps_its_first_row(self, tmp_path):
        """
        Old raw logger files have no header: the first line is data.

        Its values are kept as written (not de-duplicated like column names,
        which turned a second "0" into "0.1").
        """
        path = tmp_path / "wbb" / "teledyne_t400" / "raw" / "2016_01_raw.dat"
        path.parent.mkdir(parents=True)
        path.write_text(
            "2016-01-01 00:00:00,805612,0,0,40.1\n"
            "2016-01-01 00:00:10,805613,0,10,40.2\n"
        )
        with patch.dict(lin.DATA_CONFIG, {"teledyne_t400": T400_CONFIG}):
            data = lin.LinDatFile(str(path)).parse()

        assert list(data.columns) == ["Time_UTC", "RECORD", "MM", "SS", "O3_ppb"]
        assert data["Time_UTC"].tolist() == list(
            pd.to_datetime(["2016-01-01 00:00:00", "2016-01-01 00:00:10"])
        )
        assert data["SS"].tolist() == [0, 10]
        assert data["O3_ppb"].tolist() == [40.1, 40.2]

    def test_timestamp_header_keeps_the_files_names(self, tmp_path):
        """Campbell files with a TIMESTAMP header use their own column names."""
        path = tmp_path / "dbk" / "licor_6262" / "raw" / "2022_05_raw.dat"
        path.parent.mkdir(parents=True)
        path.write_text(
            "TIMESTAMP,RECORD,PTemp_Avg\n"
            "2022-05-01 00:00:00.00,2816242,25.8\n"
            "2022-05-01 00:00:10.00,2816243,25.79\n"
        )
        data = lin.LinDatFile(str(path)).parse()

        assert list(data.columns) == ["Time_UTC", "RECORD", "PTemp_Avg"]
        assert data["Time_UTC"].notna().all()
        assert data["PTemp_Avg"].tolist() == [25.8, 25.79]


class TestLGRUGGAFile:
    """Files written by the LGR software (raw lgr_ugga)."""

    @pytest.fixture(autouse=True)
    def config(self):
        with patch.dict(lin.DATA_CONFIG, {"lgr_ugga": UGGA_CONFIG}):
            yield

    def test_meta_and_period_old_software(self, tmp_path):
        path = write_ugga(
            tmp_path / "gga01Apr2016_f0000.txt",
            "904M",
            [ugga_row("04/01/2016 21:18:56.498", tail=("3", "V:1 Atmosphere"))],
        )
        datafile = lin.LGR_UGGA_File(path)
        assert datafile.version == "904M"
        assert datafile.serial == "LGR-13-0221"
        assert lin.LGR_UGGA_File.get_serial(path) == "LGR-13-0221"
        assert datafile.period == pd.Period("2016-04-01", freq="D")

    def test_period_new_software(self, tmp_path):
        path = write_ugga(
            tmp_path / "gga_2017-05-09_f0000.txt",
            "2f90039",
            [ugga_row("05/09/2017 22:06:07.927", tail=("3", "3", "~flush~flush"))],
            header_cols=24,
        )
        assert lin.LGR_UGGA_File(path).period == pd.Period("2017-05-09", freq="D")

    def test_parse_23_columns(self, tmp_path):
        """2013-14 software: the MIU valve and description share one field."""
        rows = [
            ugga_row("04/01/2016 21:18:56.498", tail=("3", "V:1 Atmosphere")),
            ugga_row("04/01/2016 21:19:06.512", tail=("3", "V:1 Atmosphere")),
        ]
        path = write_ugga(tmp_path / "gga01Apr2016_f0000.txt", "904M", rows)
        data = lin.LGR_UGGA_File(path).parse()

        assert list(data.columns) == UGGA_NAMES
        assert data["Time_UTC"].tolist() == list(
            pd.to_datetime(["2016-04-01 21:18:56.498", "2016-04-01 21:19:06.512"])
        )
        assert data["CH4_ppm"].dtype == float
        assert data["CH4_ppm"].tolist() == pytest.approx([1.9, 1.9])
        assert data["ID"].tolist() == ["V:1 Atmosphere"] * 2

    def test_parse_24_columns_drops_the_valve(self, tmp_path):
        """
        2014+ software splits the MIU field.

        The valve number is dropped and the description becomes ID.
        """
        rows = [
            ugga_row("05/09/2017 22:06:07.927", tail=("3", "3", "~flush~flush")),
            ugga_row("05/09/2017 22:06:17.927", tail=("3", "4", "atmosphere")),
        ]
        path = write_ugga(
            tmp_path / "gga_2017-05-09_f0000.txt", "2f90039", rows, header_cols=24
        )
        data = lin.LGR_UGGA_File(path).parse()

        assert list(data.columns) == UGGA_NAMES
        assert data["Fit_Flag"].tolist() == [3.0, 3.0]
        assert data["ID"].tolist() == ["~flush~flush", "atmosphere"]

    def test_incomplete_last_row_is_dropped(self, tmp_path):
        """A row cut off mid-write (a power cut) is skipped, not misread."""
        rows = [
            ugga_row("04/01/2016 21:18:56.498", tail=("3", "V:1 Atmosphere")),
            "  04/01/2016 21:19:06.512,   1.9e+00,   1.0e-03",
        ]
        path = write_ugga(tmp_path / "gga01Apr2016_f0000.txt", "904M", rows)
        data = lin.LGR_UGGA_File(path).parse()
        assert len(data) == 1

    def test_header_without_delimiters(self, tmp_path):
        path = tmp_path / "gga01Apr2016_f0000.txt"
        path.write_text("VC:904M BD:May 23 2013 SN:LGR-13-0221\nno delimiters\nrow\n")
        with pytest.raises(errors.ParserError, match="No deliminators"):
            lin.LGR_UGGA_File(str(path)).parse()

    def test_unreadable_meta(self, tmp_path):
        path = tmp_path / "gga01Apr2016_f0000.txt"
        path.write_text("-----BEGIN PGP MESSAGE-----\n")
        with pytest.raises(errors.DataFileInitializationError, match="meta data"):
            lin.LGR_UGGA_File(str(path))

    @pytest.mark.parametrize(
        "name", ["gga_2026-10-01_f0000.txt", "gga01Oct2026_f0000.txt"]
    )
    def test_unknown_software_version_is_dated_from_the_name(self, tmp_path, name):
        # The date comes from the file-name style, not a per-version table
        path = write_ugga(
            tmp_path / name,
            "abc1234",
            [ugga_row("10/01/2026 00:00:00.000", tail=("3", "3", "atmosphere"))],
            header_cols=24,
        )
        f = lin.LGR_UGGA_File(path)
        assert f.version == "abc1234"
        assert f.period == pd.Period("2026-10-01", freq="D")

    def test_name_without_a_date_is_skipped(self, tmp_path):
        path = write_ugga(
            tmp_path / "gga_latest_f0000.txt",
            "2f90039",
            [ugga_row("10/01/2026 00:00:00.000", tail=("3", "3", "atmosphere"))],
            header_cols=24,
        )
        with pytest.raises(errors.DataFileInitializationError, match="No date"):
            lin.LGR_UGGA_File(path)

    def test_get_files_finds_f_files_in_day_dirs(self, tmp_path, monkeypatch):
        raw = tmp_path / "wbb" / "lgr_ugga" / "raw"
        for name in [
            "01Apr2016/gga01Apr2016_f0000.txt",
            "01Apr2016/gga01Apr2016_b0000.txt",
            "01Apr2016/gga01Apr2016_l0000.txt",
            "2017-05-09/gga_2017-05-09_f0000.txt",
            "2017-05-09/gga_2017-05-09_f0000.txt.zip",
        ]:
            (raw / name).parent.mkdir(parents=True, exist_ok=True)
            (raw / name).touch()
        monkeypatch.setattr(lin, "DATA_DIR", str(tmp_path))

        files = lin.LinGroup().get_files("WBB", "lgr_ugga", "raw", logger="lgr_ugga")

        assert sorted(os.path.basename(f) for f in files) == [
            "gga01Apr2016_f0000.txt",
            "gga_2017-05-09_f0000.txt",
        ]


class TestAirTrendFile:
    """Files written by the air-trend logger on the Pis."""

    def write(self, tmp_path, instrument, name, text):
        path = tmp_path / "trx01" / instrument / "raw" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)

    def test_gps_sentence_files(self, tmp_path):
        """The sentence in the file name picks the column layout."""
        path = self.write(
            tmp_path,
            "gps",
            "2026-10-03_gpgga.csv",
            "time,inst_time,latitude_dm,n_s,longitude_dm,e_w,fix_quality,n_sat,altitude_amsl\n"
            "2026-10-03T00:00:00.278624,000000.000,4043.3583,N,11155.1757,W,0,00,1376.7\n"
            "2026-10-03T00:00:01.278836,000001.000,XXXX,N,11155.1757,W,0,00,bad\n",
        )
        with patch.dict(lin.DATA_CONFIG, {"gps": GPS_CONFIG}):
            datafile = lin.AirTrendFile(path)
            data = datafile.parse()

        assert datafile.config == {"instrument": "gps", "lvl": "air_trend_gpgga"}
        assert datafile.period == pd.Period("2026-10-03", freq="D")
        assert list(data.columns) == [
            "Time_UTC",
            *GPS_CONFIG["air_trend_gpgga"]["col_names"][1:],
        ]
        assert data["Time_UTC"].iloc[0] == pd.Timestamp("2026-10-03 00:00:00.278624")
        # XXXX and other text in numeric columns become NaN
        assert data["latitude_dm"].tolist()[0] == 4043.3583
        assert np.isnan(data["latitude_dm"].iloc[1])
        assert np.isnan(data["altitude_amsl"].iloc[1])
        # character columns stay text
        assert data["n_s"].tolist() == ["N", "N"]

    def test_variant_instrument_uses_its_base_config(self, tmp_path):
        """lgr_ugga_manual_cal files have the lgr_ugga layout."""
        path = self.write(tmp_path, "lgr_ugga_manual_cal", "2024-08-27.csv", "")
        config = lin.AirTrendFile(path).config
        assert config["lvl"] == "air_trend"
        assert lin.DATA_CONFIG[config["instrument"]] is lin.DATA_CONFIG["lgr_ugga"]

    def test_instrument_is_not_matched_by_a_shorter_name(self, tmp_path):
        """
        metone_es642 is not read with the met sensors' layout.

        Its name starts with "met" (the met sensors), which comes first in the
        pipeline config, so its PM files were read with the met layout.
        """
        metone = {"air_trend": {"col_names": ["time", "pm25_mgm3"], "col_types": "Td"}}
        met = {"air_trend": {"col_names": ["time", "case_t_c"], "col_types": "Td"}}
        path = self.write(
            tmp_path,
            "metone_es642",
            "2022-06-07.csv",
            "time,pm25_mgm3\n2022-06-07T00:00:00.769465,000.012\n",
        )
        config = {"met": met, "metone_es642": metone}
        with patch.object(lin, "DATA_CONFIG", config):
            datafile = lin.AirTrendFile(path)
            data = datafile.parse()

        assert datafile.config["instrument"] == "metone_es642"
        assert data["pm25_mgm3"].tolist() == [0.012]

    def test_unknown_instrument(self, tmp_path):
        path = self.write(tmp_path, "img", "2024-08-27.csv", "")
        with pytest.raises(
            errors.DataFileInitializationError, match="Unknown instrument"
        ):
            lin.AirTrendFile(path)

    def test_unexpected_file_name(self, tmp_path):
        path = self.write(tmp_path, "gps", "notes.csv", "")
        with pytest.raises(errors.DataFileInitializationError, match="file name"):
            lin.AirTrendFile(path)


class TestLinGroup:
    """File discovery over a synthetic data tree."""

    @pytest.fixture
    def data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lin, "DATA_DIR", str(tmp_path))
        return tmp_path

    def test_highest_level_ignores_other_dirs(self, data_dir):
        for d in ["raw", "qaqc", "final", "raw_frozen_multiLGRproblem_230202"]:
            (data_dir / "wbb" / "lgr_ugga" / d).mkdir(parents=True)
        for d in ["raw", "qaqc"]:
            (data_dir / "trx01" / "2b_205" / d).mkdir(parents=True)

        assert lin.LinGroup.get_highest_lvl("WBB", "lgr_ugga") == "final"
        assert lin.LinGroup.get_highest_lvl("TRX01", "2b_205") == "qaqc"

    def test_data_path_lowercases_the_site(self, data_dir):
        assert lin.LinGroup.data_path("WBB", "lgr_ugga", "final") == str(
            data_dir / "wbb" / "lgr_ugga" / "final"
        )

    def test_datafile_key(self):
        group = lin.LinGroup()
        assert group.get_datafile_key("lgr_ugga", "raw", "air-trend") == "air-trend"
        assert (
            group.get_datafile_key("lgr_ugga", "qaqc", "air-trend") == "data-pipeline"
        )
        assert group.get_datafile_class("gps", "raw", "air-trend") is lin.AirTrendFile
        assert group.get_datafile_class("gps", "final", "x") is lin.LinDatFile

    def test_unknown_logger(self):
        with pytest.raises(ValueError, match="DataFile class not found"):
            lin.LinGroup().get_datafile_class("gps", "raw", "no-such-logger")

    def test_raw_gps_defaults_to_gga_sentences(self, data_dir):
        """The fix sentences, not RMC, unless a pattern says otherwise."""
        raw = data_dir / "trx01" / "gps" / "raw"
        raw.mkdir(parents=True)
        for name in ["2024-06-01_gpgga.csv", "2024-06-01_gprmc.csv"]:
            (raw / name).touch()

        datafiles = lin.LinGroup().get_datafiles(
            "TRX01", "gps", "raw", "air-trend", TimeRange("2024-06-01")
        )
        assert [os.path.basename(d.path) for d in datafiles] == ["2024-06-01_gpgga.csv"]

        datafiles = lin.LinGroup().get_datafiles(
            "TRX01", "gps", "raw", "air-trend", TimeRange("2024-06-01"), "gprmc"
        )
        assert [os.path.basename(d.path) for d in datafiles] == ["2024-06-01_gprmc.csv"]

    def test_raw_ugga_range_is_widened_a_day(self, data_dir):
        """
        LGR file names need not match their contents.

        So the day before and after are read too.
        """
        raw = data_dir / "wbb" / "lgr_ugga" / "raw"
        for day in [
            "2024-06-01",
            "2024-06-02",
            "2024-06-03",
            "2024-06-04",
            "2024-06-05",
        ]:
            write_ugga(
                raw / day / f"gga_{day}_f0000.txt",
                "2f90039",
                [ugga_row("06/01/2024 00:00:00.000", tail=("3", "3", "atmosphere"))],
                header_cols=24,
            )

        datafiles = lin.LinGroup().get_datafiles(
            "WBB", "lgr_ugga", "raw", "lgr_ugga", TimeRange("2024-06-03")
        )
        assert sorted(str(d.period) for d in datafiles) == [
            "2024-06-02",
            "2024-06-03",
            "2024-06-04",
        ]

    def test_bad_file_is_skipped_with_a_warning(self, data_dir, caplog):
        """One unreadable file name doesn't stop the read."""
        raw = data_dir / "trx01" / "2b_205" / "raw"
        raw.mkdir(parents=True)
        (raw / "2024-06-01.csv").touch()
        (raw / "backup.csv").touch()

        with caplog.at_level(logging.WARNING, logger="uataq"):
            datafiles = lin.LinGroup().get_datafiles(
                "TRX01", "2b_205", "raw", "air-trend", TimeRange("2024-06")
            )
        assert [os.path.basename(d.path) for d in datafiles] == ["2024-06-01.csv"]
        assert "backup.csv" in caplog.text


class TestStandardizeData:
    """Per-instrument unit fixes on top of the column renames."""

    def test_2b_flow_cc_per_minute_to_liters(self):
        for flow in ["flow_ccpm", "Flow_CCmin"]:
            data = pd.DataFrame({flow: [1500.0], "o3_ppb": [40.0]})
            out = lin.LinGroup.standardize_data("2b_205", data)
            assert out["Flow_Lpm"].tolist() == [1.5]
            assert out["O3_ppb"].tolist() == [40.0]

    def test_pm_mg_to_ug(self):
        data = pd.DataFrame({"pm25_mgm3": [0.012]})
        out = lin.LinGroup.standardize_data("metone_es642", data)
        assert list(out.columns) == ["PM2.5_ugm3"]
        assert out["PM2.5_ugm3"].tolist() == pytest.approx([12.0])

    def test_gps_status_is_binary(self):
        data = pd.DataFrame({"status": ["A", "V", "A"], "true_course": [1.0, 2.0, 3.0]})
        out = lin.LinGroup.standardize_data("gps", data)
        assert out["Status"].tolist() == [1, 0, 1]
        assert "Course_deg" in out.columns

    def test_shared_layouts(self):
        """licor_7000 files use the licor_6262 names."""
        data = pd.DataFrame(columns=["rawCO2_Avg", "IRGA_P_Avg"])
        out = lin.LinGroup.standardize_data("licor_7000", data)
        assert list(out.columns) == ["CO2_ppm", "Internal_P_kPa"]

    def test_unknown_instrument_is_unchanged(self):
        data = pd.DataFrame({"x": [1.0]})
        assert lin.LinGroup.standardize_data("no_such_instrument", data).equals(data)
