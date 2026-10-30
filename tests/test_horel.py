"""
Tests for the horel group space.

The archive files are mimicked with a few synthetic rows in ``tmp_path``,
shaped like ``horel-group/uutrax``: raw ``{SID}_{YYYY}_{MM}_{inst}.h5`` tables
at ``/obsdata/observations`` (``EPOCHTIME`` + four-letter codes), and gzipped
``csv_finalized[_ebus]/{SID}_{YYYY}_{MM}.csv.gz`` with a units row under the
header and every instrument of the platform in one file.
"""

import gzip
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import tables

from uataq import get_site
from uataq.errors import InactiveInstrumentError, ReaderError
from uataq.filesystem import core
from uataq.filesystem.groupspaces import horel
from uataq.timerange import TimeRange

JUNE = int(pd.Timestamp("2024-06-01").timestamp())


def write_h5(path, columns: dict[str, list]) -> str:
    """Write a horel raw table: ``EPOCHTIME`` (int) plus float32 columns."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    dtype = [("EPOCHTIME", "<i8")] + [(c, "<f4") for c in columns if c != "EPOCHTIME"]
    rows = np.zeros(len(columns["EPOCHTIME"]), dtype=dtype)
    for c, values in columns.items():
        rows[c] = values
    with tables.open_file(str(path), mode="w") as f:
        group = f.create_group("/", "obsdata")
        f.create_table(group, "observations", rows)
    return str(path)


def write_csv_gz(path, header: list[str], units: list[str], rows: list[list]) -> str:
    """Write a horel finalized CSV: header, units row, then data rows."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [",".join(header), ",".join(units)]
    lines += [",".join(str(v) for v in row) for row in rows]
    with gzip.open(path, "wt") as f:
        f.write("\n".join(lines) + "\n")
    return str(path)


# A TRX-like finalized file: GPS, logger, ES642 and 2B in one table.
TRX_HEADER = [
    "Timestamp",
    "Latitude",
    "Longitude",
    "Elevation",
    "Battery_Voltage",
    "ES642_PM2.5_Concentration",
    "ES642_Internal_Air_Temperature",
    "2B_Ozone_Concentration",
    "2B_Air_Flow_Rate",
    "2B_Internal_Air_Pressure",
    "PM2.5_Data_Flagged",
    "Ozone_Data_Flagged",
]
TRX_UNITS = ["UTC", "ddeg", "ddeg", "m", "volts", "ug/m3", "degC"]
TRX_UNITS += ["ppbv", "L/min", "hpa", "binary", "binary"]
TRX_ROWS = [
    ["2024-06-01T00:00:00", 40.76, -111.86, 1325.4, 13.1, 2.0, 29.3, 47.2, 1.9, 825.3, 0, 1],
    ["2024-06-01T00:00:02", 40.76, -111.86, 1325.7, 13.1, 1.0, 29.3, 50.3, 1.9, 825.3, 0, 0],
    ["2024-06-01T00:00:04", 40.76, -111.86, 1325.9, 13.1, 3.0, 29.3, -9999.00, -9999.00, -9999.00, 1, 0],
]  # fmt: skip

# A BUS-like finalized file adds GPS speed, direction, RMC validity and a
# storage flag.
BUS_HEADER = [
    "Timestamp",
    "Latitude",
    "Longitude",
    "Elevation",
    "GPS_Speed",
    "GPS_Direction",
    "GPS_RMC_Valid",
    "2B_Ozone_Concentration",
    "Ozone_Data_Flagged",
    "GPS_Data_Flagged",
]
BUS_UNITS = ["UTC", "ddeg", "ddeg", "m", "m/s", "deg", "binary", "ppbv"]
BUS_UNITS += ["binary", "binary"]
BUS_ROWS = [
    ["2024-06-01T00:00:00", 40.76, -111.90, 1301.1, 0.0, 172.2, 1, 44.6, 0, 1],
    ["2024-06-01T00:00:05", 40.76, -111.90, 1301.1, 5.5, 172.2, 1, 46.9, 0, 0],
    ["2024-06-01T00:00:10", 40.76, -111.90, 1301.1, 6.0, 172.2, 0, 46.0, 0, 1],
]


def write_trx(tmp_path) -> str:
    return write_csv_gz(
        tmp_path / "csv_finalized" / "TRX01_2024_06.csv.gz",
        TRX_HEADER,
        TRX_UNITS,
        TRX_ROWS,
    )


def write_bus(tmp_path) -> str:
    return write_csv_gz(
        tmp_path / "csv_finalized_ebus" / "BUS01_2024_06.csv.gz",
        BUS_HEADER,
        BUS_UNITS,
        BUS_ROWS,
    )


def test_column_names_do_not_depend_on_level():
    """Raw (h5) and CSV codes for the same quantity map to one name (#17)."""
    for instrument, mapping in horel.column_mapping.items():
        for name in mapping.values():
            assert "_hpa" not in name, f"{instrument}: {name} should be hPa"


def test_get_files_skips_a_missing_level_dir(tmp_path):
    """The pilot archive has no nox dir; raw reads used to crash on it (#26)."""
    pilot, main = tmp_path / "uutrax_pilot", tmp_path / "uutrax"
    (main / "nox").mkdir(parents=True)
    (main / "nox" / "BUS03_2024_04_nox.h5").touch()
    with patch.dict(horel.lvl_data_dirs, {"raw": [str(pilot), str(main)]}):
        files = horel.HorelGroup().get_files("BUS03", "2b_405", "raw")
    assert [os.path.basename(f) for f in files] == ["BUS03_2024_04_nox.h5"]


class TestHorelH5File:
    """Raw campbellsci tables."""

    def write(self, tmp_path) -> str:
        return write_h5(
            tmp_path / "2b" / "BUS01_2024_06_2b.h5",
            {
                "EPOCHTIME": [JUNE, JUNE + 5, JUNE + 10],
                "OZNE": [44.6, -9999.0, 46.0],
                "FL2B": [1.88, 1.87, 1.86],
                "PS2B": [837.1, 837.1, 837.0],
                "TC2B": [45.7, 45.7, 45.8],
                "VOLT": [13.5, 13.5, 13.5],  # a cr1000 column, not the 2B's
            },
        )

    def test_period_comes_from_the_file_name(self, tmp_path):
        datafile = horel.HorelH5File(self.write(tmp_path), "2b_205")
        assert datafile.period == pd.Period("2024-06", freq="M")
        assert datafile.instrument == "2b_205"

    def test_parse(self, tmp_path):
        data = horel.HorelH5File(self.write(tmp_path), "2b_205").parse()

        # The other instrument's column is dropped, time is renamed
        assert set(data.columns) == {"Time_UTC", "OZNE", "FL2B", "PS2B", "TC2B"}
        expected = ["2024-06-01 00:00:00", "2024-06-01 00:00:05", "2024-06-01 00:00:10"]
        assert list(data["Time_UTC"]) == list(pd.to_datetime(expected))
        # -9999 is the horel no-data value
        assert data["OZNE"].isna().tolist() == [False, True, False]
        assert data["OZNE"].iloc[0] == pytest.approx(44.6)
        assert all(pd.api.types.is_float_dtype(data[c]) for c in ["OZNE", "FL2B"])

    def test_standardized_names(self, tmp_path):
        data = horel.HorelH5File(self.write(tmp_path), "2b_205").parse()
        data = horel.HorelGroup.standardize_data("2b_205", data)
        assert set(data.columns) == {
            "Time_UTC",
            "O3_ppb",
            "Flow_Lpm",
            "Internal_P_hPa",
            "Internal_T_C",
        }


class TestHorelCSVFile:
    """qaqc: the finalized CSVs, every row kept, flags translated."""

    def test_period_comes_from_the_file_name(self, tmp_path):
        datafile = horel.HorelCSVFile(write_trx(tmp_path), "2b_205")
        assert datafile.period == pd.Period("2024-06", freq="M")

    def test_reads_only_the_instruments_columns(self, tmp_path):
        data = horel.HorelCSVFile(write_trx(tmp_path), "2b_205").parse()

        assert set(data.columns) == {
            "Time_UTC",
            "2B_Ozone_Concentration",
            "2B_Air_Flow_Rate",
            "2B_Internal_Air_Pressure",
            "QAQC_Flag",
        }
        # The units row is skipped, so every time parses
        assert data["Time_UTC"].notna().all()
        assert data["Time_UTC"].iloc[1] == pd.Timestamp("2024-06-01 00:00:02")
        assert data["2B_Ozone_Concentration"].iloc[:2].tolist() == [47.2, 50.3]
        assert np.isnan(data["2B_Ozone_Concentration"].iloc[2])  # -9999

    def test_data_flag_becomes_a_negative_qaqc_flag(self, tmp_path):
        """A data flag of 1 marks bad data, which uataq flags negative."""
        data = horel.HorelCSVFile(write_trx(tmp_path), "2b_205").parse()
        assert data["QAQC_Flag"].tolist() == [-1, 0, 0]

        pm = horel.HorelCSVFile(write_trx(tmp_path), "metone_es642").parse()
        assert pm["QAQC_Flag"].tolist() == [0, 0, -1]
        assert "PM2.5_Data_Flagged" not in pm.columns

    def test_gps_flags(self, tmp_path):
        """
        Storage is a positive GPS flag, an invalid RMC fix a negative one.

        Storage is ``GPS_Data_Flagged``; the source columns are dropped.
        """
        data = horel.HorelCSVFile(write_bus(tmp_path), "gps").parse()

        assert data["QAQC_Flag"].tolist() == [20, 0, -23]
        assert not {"GPS_Data_Flagged", "GPS_RMC_Valid"} & set(data.columns)
        assert "2B_Ozone_Concentration" not in data.columns

    def test_gps_without_flag_columns_is_unflagged(self, tmp_path):
        """TRX files carry no GPS flags: every row is flag 0."""
        data = horel.HorelCSVFile(write_trx(tmp_path), "gps").parse()
        assert data["QAQC_Flag"].tolist() == [0, 0, 0]
        assert {"Latitude", "Longitude", "Elevation"} <= set(data.columns)


class TestHorelCSVFinalizedFile:
    """final: flagged rows dropped, diagnostics dropped."""

    def test_drops_flagged_rows_and_diagnostic_columns(self, tmp_path):
        data = horel.HorelCSVFinalizedFile(write_trx(tmp_path), "2b_205").parse()

        # The flagged first row is gone; flow, pressure and the flag are too
        assert list(data.columns) == ["Time_UTC", "O3_ppb"]
        assert data["Time_UTC"].iloc[0] == pd.Timestamp("2024-06-01 00:00:02")
        assert data["O3_ppb"].iloc[0] == 50.3

    def test_keeps_ambient_and_concentration_columns(self, tmp_path):
        data = horel.HorelCSVFinalizedFile(write_trx(tmp_path), "metone_es642").parse()
        # The ES642 "internal" temperature is mapped to ambient
        assert list(data.columns) == ["Time_UTC", "PM2.5_ugm3", "Ambient_T_C"]
        assert data["PM2.5_ugm3"].tolist() == [2.0, 1.0]


class TestFinalizedRowsWithoutObs:
    """final drops a row whose measurements are all no-data."""

    def test_drops_rows_without_obs(self, tmp_path):
        data = horel.HorelCSVFinalizedFile(write_trx(tmp_path), "2b_205").parse()
        # Row 3 is unflagged, but its ozone is -9999
        assert data["O3_ppb"].notna().all()
        assert data["Time_UTC"].tolist() == [pd.Timestamp("2024-06-01 00:00:02")]

    def test_keeps_rows_with_any_obs(self, tmp_path):
        rows = [r[:7] + [-9999.0] + r[8:] for r in TRX_ROWS]  # no ozone at all
        path = write_csv_gz(
            tmp_path / "TRX01_2024_06.csv.gz", TRX_HEADER, TRX_UNITS, rows
        )
        data = horel.HorelCSVFinalizedFile(path, "gps").parse()
        assert len(data) == 3  # the positions are still there


class TestStandardizeData:
    """Per-instrument fixes applied on top of the column renames."""

    @pytest.mark.parametrize(
        "instrument, column",
        [("metone_es405", "Internal_T_C"), ("metone_es642", "Ambient_T_C")],
    )
    def test_metone_fahrenheit_becomes_celsius(self, instrument, column):
        data = pd.DataFrame({"ITMP": [32.0, 212.0], "PM25": [1.0, 2.0]})
        out = horel.HorelGroup.standardize_data(instrument, data)
        assert out[column].tolist() == pytest.approx([0.0, 100.0])
        assert "ITMP" not in out.columns
        assert "PM2.5_ugm3" in out.columns

    def test_renames_the_callers_frame(self):
        """The temperature rename edits the frame passed in, not a copy."""
        data = pd.DataFrame({"ITMP": [32.0], "PM25": [1.0]})
        horel.HorelGroup.standardize_data("metone_es405", data)
        assert "Internal_T_C" in data.columns
        assert "ITMP" not in data.columns

    def test_csv_and_h5_codes_meet(self):
        """The 2B405's raw codes and CSV names give the same columns."""
        raw = pd.DataFrame(columns=["NO1C", "NO2C", "NOXC", "FO3N"])
        csv = pd.DataFrame(
            columns=[
                "2B405_NO_Concentration",
                "2B405_NO2_Concentration",
                "2B405_NOX_Concentration",
                "2B405_Cell_O3_Flow_Rate",
            ]
        )
        names = ["NO_ppb", "NO2_ppb", "NOx_ppb", "O3_Flow_mLpm"]
        assert list(horel.HorelGroup.standardize_data("2b_405", raw).columns) == names
        assert list(horel.HorelGroup.standardize_data("2b_405", csv).columns) == names


class TestHorelGroup:
    """File discovery over a synthetic uutrax tree."""

    @pytest.fixture
    def archive(self, tmp_path, monkeypatch):
        """uutrax_pilot + uutrax, with raw, TRX and BUS finalized files."""
        pilot, main = tmp_path / "uutrax_pilot", tmp_path / "uutrax"
        for d in [
            pilot / "esampler",
            main / "esampler",
            main / "csv_finalized",
            main / "csv_finalized_ebus",
        ]:
            d.mkdir(parents=True)
        for f in [
            pilot / "esampler" / "TRX01_2016_01_esampler.h5",
            main / "esampler" / "TRX01_2024_05_esampler.h5",
            main / "esampler" / "TRX01_2024_06_esampler.h5",
            main / "esampler" / "TRX02_2024_06_esampler.h5",
            main / "esampler" / "TRX01_2024_06_esampler.csv",  # not an h5
            main / "csv_finalized" / "TRX01_2024_06.csv.gz",
            main / "csv_finalized_ebus" / "BUS01_2024_06.csv.gz",
        ]:
            f.touch()
        monkeypatch.setattr(horel, "UUTRAX_DIR", str(main))
        dirs = {
            "raw": [str(pilot), str(main)],
            "qaqc": [str(main)],
            "final": [str(main)],
        }
        with patch.dict(horel.lvl_data_dirs, dirs):
            yield tmp_path

    @staticmethod
    def names(paths) -> list[str]:
        return sorted(os.path.basename(str(p)) for p in paths)

    def test_highest_level(self, archive):
        """Final if the site has a finalized file (BUS in the ebus dir)."""
        assert horel.HorelGroup.get_highest_lvl("TRX01", "2b_205") == "final"
        assert horel.HorelGroup.get_highest_lvl("BUS01", "2b_205") == "final"
        assert horel.HorelGroup.get_highest_lvl("TRX02", "2b_205") == "raw"
        assert horel.HorelGroup.get_highest_lvl("BUS02", "2b_205") == "raw"

    def test_levels(self):
        """Horel keeps raw, qaqc and final for every instrument."""
        group = horel.HorelGroup()
        assert group.get_lvls("TRX01", "2b_205") == ["raw", "qaqc", "final"]
        assert group.get_lvls("BUS02", "metone_es642") == ["raw", "qaqc", "final"]

    def test_raw_files_span_pilot_and_main_archives(self, archive):
        """Both MetOne models live in the esampler dir."""
        files = horel.HorelGroup().get_files("TRX01", "metone_es405", "raw")
        assert self.names(files) == [
            "TRX01_2016_01_esampler.h5",
            "TRX01_2024_05_esampler.h5",
            "TRX01_2024_06_esampler.csv",
            "TRX01_2024_06_esampler.h5",
        ]

    def test_finalized_files_by_platform(self, archive):
        group = horel.HorelGroup()
        assert self.names(group.get_files("TRX01", "2b_205", "qaqc")) == [
            "TRX01_2024_06.csv.gz"
        ]
        assert self.names(group.get_files("BUS01", "2b_205", "final")) == [
            "BUS01_2024_06.csv.gz"
        ]

    def test_invalid_level(self, archive):
        with pytest.raises(ValueError, match="Invalid data level"):
            horel.HorelGroup().get_files("TRX01", "2b_205", "calibrated")

    def test_an_instrument_is_told_which_levels_horel_has(self):
        """Horel has no calibrated level, and does not look for a folder to say so."""
        bus01 = get_site("BUS01").instruments["2b_205"]
        with pytest.raises(ReaderError) as e:
            bus01.get_datafiles("horel", "calibrated", "2024-06")
        assert str(e.value) == (
            "2b_205@BUS01 has no calibrated level (it has raw, qaqc and final)."
        )

    def test_datafile_class_depends_on_level_only(self):
        group = horel.HorelGroup()
        assert group.get_datafile_class("gps", "raw", "x") is horel.HorelH5File
        assert group.get_datafile_class("gps", "qaqc", "x") is horel.HorelCSVFile
        assert (
            group.get_datafile_class("2b_205", "final", "campbellsci")
            is horel.HorelCSVFinalizedFile
        )

    def test_get_datafiles(self, archive):
        """Right extension, right months, and the instrument passed along."""
        datafiles = horel.HorelGroup().get_datafiles(
            "TRX01",
            "metone_es642",
            "raw",
            "campbellsci",
            TimeRange(["2024-06-01", "2024-06-15"]),
        )
        assert self.names(d.path for d in datafiles) == ["TRX01_2024_06_esampler.h5"]
        assert all(isinstance(d, horel.HorelH5File) for d in datafiles)
        assert all(d.instrument == "metone_es642" for d in datafiles)


class TestHorelGPSRead:
    """GPS through the Instrument, from a synthetic cr1000 table."""

    def test_recorded_speed_is_already_m_s(self, tmp_path):
        """
        Horel's RSPD is in m/s, so reading it applies no knots conversion.

        The h5 variable metadata and the CSV units row say so, and it matches
        the speed from positions. Lin's knots conversion must not apply.
        """
        main = tmp_path / "uutrax"
        write_h5(
            main / "cr1000" / "BUS01_2024_06_cr1000.h5",
            {
                "EPOCHTIME": [JUNE, JUNE + 5, JUNE + 10],
                "GLAT": [40.7639, 40.7640, 40.7641],
                "GLON": [-111.9096, -111.9096, -111.9096],
                "GELV": [1301.1, 1301.1, 1301.1],
                "RSPD": [0.0, 2.0, 10.0],
                "RDIR": [172.2, 0.0, 0.0],
                "RSTS": [1.0, 1.0, 1.0],
                "VOLT": [13.5, 13.5, 13.5],
            },
        )
        gps = get_site("BUS01").instruments["gps"]
        with patch.dict(horel.lvl_data_dirs, {"raw": [str(main)]}):
            data = gps.read_data(
                "horel", "raw", ["2024-06-01", "2024-06-02"], estimate_motion=False
            )

        assert data["Speed_m_s"].tolist() == pytest.approx([0.0, 2.0, 10.0])
        assert data["Latitude_deg"].iloc[1] == pytest.approx(40.7640)
        assert "Battery_Voltage_V" not in data.columns  # a cr1000 column

    def test_final_csv_keeps_recorded_speed(self, tmp_path):
        """The BUS finalized CSV's GPS_Speed (m/s) survives the final filter."""
        data = horel.HorelCSVFinalizedFile(write_bus(tmp_path), "gps").parse()
        # The invalid-RMC row is dropped
        assert data["Speed_m_s"].tolist() == [0.0, 5.5]


#: The five MetOne swaps: the ES642's last raw row (in the month's
#: ``esampler.h5_prior405upgrade`` file) and the ES405's first (in the
#: month's plain ``esampler.h5``), as in horel's archive.
SWAPS = {
    "BUS02": ("2025-03-13 00:37:10", "2025-03-13 02:38:00"),
    "BUS03": ("2024-12-05 05:47:35", "2024-12-05 06:09:00"),
    "TRX01": ("2025-01-06 18:10:28", "2025-01-06 19:30:00"),
    "TRX02": ("2025-01-06 20:15:50", "2025-01-07 01:03:00"),
    "TRX03": ("2025-01-03 17:15:42", "2025-01-03 20:16:00"),
}


def epoch(*times) -> list[int]:
    return [int(pd.Timestamp(t).timestamp()) for t in times]


@pytest.mark.parametrize("SID", sorted(SWAPS))
class TestPrior405UpgradeFiles:
    """
    The month of each ES642-to-ES405 swap has two raw esampler files.

    ``{SID}_{YYYY}_{MM}_esampler.h5_prior405upgrade`` holds the ES642's rows up
    to the swap and the plain ``.h5`` the ES405's from it. The ES642 reads both
    and keeps its own rows; the ES405 reads only the plain file.
    """

    @pytest.fixture
    def swap(self, SID, tmp_path):
        """Write the swap month's two files, the month before, and stray files."""
        last, first = (pd.Timestamp(t) for t in SWAPS[SID])
        month = first.to_period("M")
        start = month.start_time
        before = (month - 1).start_time
        folder = tmp_path / "uutrax" / "esampler"
        es642 = {"PM25": [5.0, 6.0], "FLOW": [2.0, 2.0], "ITMP": [50.0, 50.0]}
        es405 = {**es642, "PM01": [1.0, 1.0], "PM04": [7.0, 7.0], "PM10": [9.0, 9.0]}
        name = f"{SID}_{month.strftime('%Y_%m')}_esampler"
        write_h5(
            folder / f"{name}.h5_prior405upgrade",
            {"EPOCHTIME": epoch(start, last), **es642},
        )
        write_h5(
            folder / f"{name}.h5",
            {"EPOCHTIME": epoch(first, first + pd.Timedelta("1min")), **es405},
        )
        write_h5(
            folder / f"{SID}_{(month - 1).strftime('%Y_%m')}_esampler.h5",
            {"EPOCHTIME": epoch(before, before + pd.Timedelta("2s")), **es642},
        )
        # Other suffixes in horel's raw folders are not data to read
        for stray in ("h5_bad", "h5_old", "h5.partial"):
            write_h5(
                folder / f"{name}.{stray}",
                {"EPOCHTIME": epoch(start + pd.Timedelta("1h")), "PM25": [99.0]},
            )
        with patch.dict(horel.lvl_data_dirs, {"raw": [str(tmp_path / "uutrax")]}):
            yield start, (month + 1).start_time, last, first

    def test_es642_reads_the_prior_file_up_to_the_swap(self, SID, swap):
        start, stop, last, _ = swap
        es642 = get_site(SID).instruments["metone_es642"]
        data = es642.read_data("horel", "raw", (start, stop))
        assert data.index.tolist() == [start, last]
        assert data["PM2.5_ugm3"].tolist() == [5.0, 6.0]
        assert "PM1_ugm3" not in data.columns

    def test_es405_reads_only_its_own_rows(self, SID, swap):
        start, stop, _, first = swap
        es405 = get_site(SID).instruments["metone_es405"]
        data = es405.read_data("horel", "raw", (start, stop))
        assert data.index.tolist() == [first, first + pd.Timedelta("1min")]
        assert data["PM1_ugm3"].tolist() == [1.0, 1.0]

    def test_only_the_es642_lists_the_prior_file(self, SID, swap):
        start, stop, _, _ = swap
        names = {}
        for model in ("metone_es642", "metone_es405"):
            datafiles = horel.HorelGroup().get_datafiles(
                SID, model, "raw", "campbellsci", TimeRange(start=start, stop=stop)
            )
            names[model] = sorted(os.path.basename(d.path) for d in datafiles)
        plain = f"{SID}_{start:%Y_%m}_esampler.h5"
        assert names["metone_es642"] == [plain, plain + "_prior405upgrade"]
        assert names["metone_es405"] == [plain]

    def test_month_without_a_prior_file_is_read_as_before(self, SID, swap):
        start, _, _, _ = swap
        before = (start.to_period("M") - 1).start_time
        es642 = get_site(SID).instruments["metone_es642"]
        data = es642.read_data("horel", "raw", (before, start))
        assert data.index.tolist() == [before, before + pd.Timedelta("2s")]


def test_prior_and_plain_gps_rows_join_in_time(tmp_path):
    """TRX01's GPS (cr1000) was split at the swap too; the two files meet in order."""
    folder = tmp_path / "uutrax" / "cr1000"
    position = {"GLAT": [40.76, 40.77], "GLON": [-111.89, -111.88]}
    write_h5(
        folder / "TRX01_2025_01_cr1000.h5_prior405upgrade",
        {"EPOCHTIME": epoch("2025-01-01", "2025-01-06 18:10:28"), **position},
    )
    write_h5(
        folder / "TRX01_2025_01_cr1000.h5",
        {"EPOCHTIME": epoch("2025-01-06 19:30:00", "2025-01-06 19:30:05"), **position},
    )
    gps = get_site("TRX01").instruments["gps"]
    with patch.dict(horel.lvl_data_dirs, {"raw": [str(tmp_path / "uutrax")]}):
        data = gps.read_data(
            "horel", "raw", ("2025-01-01", "2025-01-31"), estimate_motion=False
        )
    times = [
        "2025-01-01",
        "2025-01-06 18:10:28",
        "2025-01-06 19:30",
        "2025-01-06 19:30:05",
    ]
    assert data.index.tolist() == [pd.Timestamp(t) for t in times]


class TestPilotFileEnd:
    """
    November 2018 has a raw file in both the pilot and the main archive.

    The pilot file runs on past the end of the pilot phase with a copy of the
    main file's rows once a minute, so a read would get those rows twice.
    """

    STOP = pd.Timestamp(horel.PILOT_PHASE["TRX01"].stop)

    @pytest.fixture
    def archive(self, tmp_path, monkeypatch):
        pilot, main = tmp_path / "uutrax_pilot", tmp_path / "uutrax"
        position = {"GLAT": [40.76, 40.77], "GLON": [-111.89, -111.88]}
        before, after = (
            self.STOP - pd.Timedelta("3min"),
            self.STOP + pd.Timedelta("1min"),
        )
        # The pilot's own row, then a copy of a main-archive row
        write_h5(
            pilot / "cr1000" / "TRX01_2018_11_cr1000.h5",
            {"EPOCHTIME": epoch(before, after), **position},
        )
        write_h5(
            main / "cr1000" / "TRX01_2018_11_cr1000.h5",
            {"EPOCHTIME": epoch(after, after + pd.Timedelta("2s")), **position},
        )
        monkeypatch.setattr(horel, "UUTRAX_PILOT_DIR", str(pilot))
        with patch.dict(horel.lvl_data_dirs, {"raw": [str(pilot), str(main)]}):
            yield before, after

    def test_each_row_is_read_once(self, archive):
        before, after = archive
        gps = get_site("TRX01").instruments["gps"]
        data = gps.read_data(
            "horel", "raw", ("2018-11-19", "2018-11-21"), estimate_motion=False
        )
        assert data.index.tolist() == [before, after, after + pd.Timedelta("2s")]

    def test_main_archive_file_is_kept_whole(self, archive, tmp_path):
        _, after = archive
        path = tmp_path / "uutrax" / "cr1000" / "TRX01_2018_11_cr1000.h5"
        data = horel.HorelH5File(str(path), "gps").parse()
        assert data["Time_UTC"].tolist() == [after, after + pd.Timedelta("2s")]


class TestParseOnce:
    """
    One ``Site.read_data`` call parses each finalized CSV once.

    The file holds every instrument of the platform, and each takes its own
    columns from the one parse. The parse lives only for that call.
    """

    #: TRX01's horel instruments in June 2024 (its ES405 came in 2025-01)
    INSTRUMENTS = ["2b_205", "cr1000", "gps", "metone_es642"]

    @pytest.fixture
    def archive(self, tmp_path):
        """TRX01's 2024-05 and 2024-06 finalized files."""
        write_trx(tmp_path)
        may = [[row[0].replace("-06-", "-05-"), *row[1:]] for row in TRX_ROWS]
        write_csv_gz(
            tmp_path / "csv_finalized" / "TRX01_2024_05.csv.gz",
            TRX_HEADER,
            TRX_UNITS,
            may,
        )
        dirs = {"qaqc": [str(tmp_path)], "final": [str(tmp_path)]}
        with patch.dict(horel.lvl_data_dirs, dirs):
            yield tmp_path

    @staticmethod
    def read(lvl: str, time_range="2024-06", instruments=None, num_processes=1):
        return get_site("TRX01").read_data(
            instruments or TestParseOnce.INSTRUMENTS,
            group="horel",
            lvl=lvl,
            time_range=time_range,
            num_processes=num_processes,
        )

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_each_call_parses_the_file_once(self, archive, lvl):
        with patch.object(horel.pd, "read_csv", wraps=pd.read_csv) as read_csv:
            data = self.read(lvl)
            assert sorted(data) == sorted(self.INSTRUMENTS)
            assert read_csv.call_count == 1

            # Nothing is kept between calls: the next one parses again
            self.read(lvl)
            assert read_csv.call_count == 2
        assert core._parsed_files.get() is None

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_columns_are_those_of_a_read_on_its_own(self, archive, lvl):
        """No instrument's columns depend on what the others did to the parse."""
        together = self.read(lvl)
        for name in self.INSTRUMENTS:
            alone = self.read(lvl, instruments=[name])[name]
            pd.testing.assert_frame_equal(together[name], alone)

    def test_files_are_parsed_once_each(self, archive):
        with patch.object(horel.pd, "read_csv", wraps=pd.read_csv) as read_csv:
            self.read("final", time_range=["2024-05", "2024-07"])
        assert read_csv.call_count == 2

    def test_parallel_read_gives_the_same_frames(self, archive):
        """Pool workers parse on their own; what they return is unchanged."""
        time_range = ["2024-05", "2024-07"]
        serial = self.read("final", time_range=time_range)
        parallel = self.read("final", time_range=time_range, num_processes=2)
        for name in self.INSTRUMENTS:
            pd.testing.assert_frame_equal(parallel[name], serial[name])


#: A BUS-like finalized file whose ES405 values carry the ES642's column names
ES642_NAMED = [
    "Timestamp",
    "ES642_PM2.5_Concentration",
    "ES642_Air_Flow_Rate",
    "ES642_Internal_Air_Temperature",
    "ES642_Internal_Relative_Humidity",
    "ES642_Internal_Air_Pressure",
    "ES642_Error_Code",
    "PM2.5_Data_Flagged",
]
ES642_UNITS = ["UTC", "ug/m3", "L/min", "degC", "%", "hpa", "code", "binary"]

#: The same file with the ES405's own names (and its PM1, PM4 and PM10)
ES405_NAMED = [
    "Timestamp",
    "ES405_PM1_Concentration",
    "ES405_PM2.5_Concentration",
    "ES405_PM4_Concentration",
    "ES405_PM10_Concentration",
    "ES405_Air_Flow_Rate",
    "ES405_Internal_Air_Temperature",
    "ES405_Internal_Relative_Humidity",
    "ES405_Internal_Air_Pressure",
    "ES405_Error_Code",
    "PM2.5_Data_Flagged",
]
ES405_UNITS = ["UTC", "ug/m3", "ug/m3", "ug/m3", "ug/m3", "L/min", "degC", "%"]
ES405_UNITS += ["hpa", "code", "binary"]


def es642_named_rows(day: str, pm: list[float]) -> list[list]:
    """Rows of ``ES642_NAMED``: one a minute from ``day``, PM2.5 as given."""
    times = pd.date_range(day, periods=len(pm), freq="1min")
    return [
        [t.strftime("%Y-%m-%dT%H:%M:%S"), v, 1.9, 20.5, 31.0, 850.0, 0, 0]
        for t, v in zip(times, pm, strict=True)
    ]


class TestES405UnderES642Names:
    """
    The ES405 reads horel's ES642-named columns as its own inside a window.

    Horel's qaqc and final files name BUS01's and BUS02's ES405 values for the
    ES642 for a few months after each swap. The catalog's ``es642_column_dates``
    says when, and the ES405 reads those columns only inside that window.
    """

    @pytest.fixture
    def archive(self, tmp_path):
        """BUS01 2026-03 and 2026-04 and BUS02 2025-04 and 2025-12 qaqc files."""
        ebus = tmp_path / "csv_finalized_ebus"
        write_csv_gz(
            ebus / "BUS01_2026_03.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2026-03-02 20:21", [4.0, 5.0, 6.0]),
        )
        april = [
            ["2026-04-01T00:23:00", 1.0, 2.0, 3.0, 4.0, 1.9, 20.5, 31.0, 850.0, 0, 0],
            ["2026-04-01T00:24:00", 1.5, 2.5, 3.5, 4.5, 1.9, 20.5, 31.0, 850.0, 0, 0],
        ]  # fmt: skip
        write_csv_gz(ebus / "BUS01_2026_04.csv.gz", ES405_NAMED, ES405_UNITS, april)
        # BUS02's ES405 is installed from 2025-03-13: its files from then hold
        # its flow, temperature and the rest under the ES642's names, and an
        # empty PM2.5 (-9999) under that name until 2025-11
        write_csv_gz(
            ebus / "BUS02_2025_04.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2025-04-02 00:00", [-9999.0, -9999.0]),
        )
        # before the installation (the ES642's time) nothing is the ES405's
        write_csv_gz(
            ebus / "BUS02_2025_02.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2025-02-02 00:00", [12.0]),
        )
        write_csv_gz(
            ebus / "BUS02_2025_12.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2025-12-02 17:22", [9.0, 10.0]),
        )
        # BUS03 has no window: its ES642-named file is never the ES405's
        write_csv_gz(
            ebus / "BUS03_2025_02.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2025-02-02 00:00", [11.0]),
        )
        dirs = {"qaqc": [str(tmp_path)], "final": [str(tmp_path)]}
        with patch.dict(horel.lvl_data_dirs, dirs):
            yield tmp_path

    @staticmethod
    def read(SID: str, lvl: str, time_range):
        es405 = get_site(SID).instruments["metone_es405"]
        return es405.read_data("horel", lvl, time_range)

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_bus01_reads_the_es642_names_as_its_own(self, archive, lvl):
        data = self.read("BUS01", lvl, "2026-03")
        assert data["PM2.5_ugm3"].tolist() == [4.0, 5.0, 6.0]
        assert data.index[0] == pd.Timestamp("2026-03-02 20:21")
        assert not any(c.startswith("ES642_") for c in data.columns)

    def test_qaqc_has_every_column_of_the_es405(self, archive):
        data = self.read("BUS01", "qaqc", "2026-03")
        assert data["Flow_Lpm"].tolist() == [1.9] * 3
        assert data["Internal_T_C"].tolist() == [20.5] * 3
        assert data["Internal_RH_pct"].tolist() == [31.0] * 3
        assert data["Internal_P_hPa"].tolist() == [850.0] * 3
        assert data["QAQC_Flag"].tolist() == [0] * 3
        assert "PM1_ugm3" not in data.columns  # the ES642's files hold no PM1

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_es405_names_are_read_as_before(self, archive, lvl):
        data = self.read("BUS01", lvl, "2026-04")
        assert data["PM2.5_ugm3"].tolist() == [2.0, 2.5]
        assert data["PM1_ugm3"].tolist() == [1.0, 1.5]

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_a_read_across_the_stop_has_one_column_each(self, archive, lvl):
        """March (ES642 names) and April (ES405 names) in one read."""
        data = self.read("BUS01", lvl, ["2026-03-01", "2026-04-02"])
        assert data.columns.is_unique
        assert data["PM2.5_ugm3"].tolist() == [4.0, 5.0, 6.0, 2.0, 2.5]
        # PM1 exists only from April on
        assert data["PM1_ugm3"].isna().tolist() == [True] * 3 + [False] * 2

    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_bus02_reads_its_window(self, archive, lvl):
        data = self.read("BUS02", lvl, "2025-12")
        assert data["PM2.5_ugm3"].tolist() == [9.0, 10.0]

    def test_bus02_qaqc_has_the_diagnostics_from_the_installation(self, archive):
        """Flow, temperature and the rest under ES642 names; the PM2.5 is empty."""
        data = self.read("BUS02", "qaqc", "2025-04")
        assert data["Flow_Lpm"].tolist() == [1.9, 1.9]
        assert data["Internal_T_C"].tolist() == [20.5, 20.5]
        assert data["Internal_RH_pct"].tolist() == [31.0, 31.0]
        assert data["Internal_P_hPa"].tolist() == [850.0, 850.0]
        assert data["Status"].tolist() == [0, 0]
        assert data["PM2.5_ugm3"].isna().all()

    def test_bus02_final_has_no_rows_for_the_empty_pm25(self, archive):
        """The final level keeps the PM columns only, and they are empty."""
        data = self.read("BUS02", "final", "2025-04")
        assert list(data.columns) == ["PM2.5_ugm3"]
        assert data.empty

    @pytest.mark.parametrize(
        ("SID", "month"), [("BUS02", "2025-02"), ("BUS03", "2025-02")]
    )
    @pytest.mark.parametrize("lvl", ["qaqc", "final"])
    def test_es642_names_outside_the_window_are_not_the_es405s(
        self, archive, SID, month, lvl
    ):
        """BUS02 before its installation and BUS03, which has no window, read none."""
        try:
            data = self.read(SID, lvl, month)
        except (ReaderError, InactiveInstrumentError):
            return  # not installed yet, or no row with an observation at final
        assert "PM2.5_ugm3" not in data.columns or data["PM2.5_ugm3"].isna().all()

    def test_es642_no_longer_reads_the_es405s_months(self, archive):
        """BUS01's ES642 was removed before the ES405's values began."""
        es642 = get_site("BUS01").instruments["metone_es642"]
        with pytest.raises(InactiveInstrumentError):
            es642.read_data("horel", "qaqc", "2026-03")

    def test_get_obs_finds_pm25(self, archive, monkeypatch):
        """The case that came back empty: get_obs for BUS01 in 2026-03."""
        monkeypatch.setattr(horel, "UUTRAX_DIR", str(archive))
        obs = get_site("BUS01").get_obs(
            "PM2.5", time_range="2026-03", include_gps=False
        )
        assert obs["PM2.5_ugm3"].tolist() == [4.0, 5.0, 6.0]

    def test_final_keeps_only_the_final_columns(self, archive):
        """A file with ES642 names gives the same final columns as the ES405's own."""
        data = self.read("BUS01", "final", "2026-03")
        assert list(data.columns) == ["PM2.5_ugm3"]

    def test_window_edges_are_half_open(self, tmp_path):
        """A file that straddles the window's stop takes the rows before it."""
        path = write_csv_gz(
            tmp_path / "csv_finalized_ebus" / "BUS01_2026_03.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2026-03-31 23:59", [1.0, 2.0]),
        )
        datafile = horel.HorelCSVFile(path, "metone_es405")
        datafile.es642_column_dates = TimeRange(
            start=pd.Timestamp("2026-02-01"), stop=pd.Timestamp("2026-04-01")
        )
        data = datafile.parse()
        assert data["ES405_PM2.5_Concentration"].isna().tolist() == [False, True]
        assert not any(c.startswith("ES642_") for c in data.columns)

    def test_a_file_with_no_dates_takes_none(self, tmp_path):
        path = write_csv_gz(
            tmp_path / "csv_finalized_ebus" / "BUS01_2026_03.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2026-03-02 20:21", [4.0]),
        )
        data = horel.HorelCSVFile(path, "metone_es405").parse()
        assert list(data.columns) == ["Time_UTC", "QAQC_Flag"]

    def test_the_instrument_hands_its_dates_to_the_files(self, archive):
        es405 = get_site("BUS01").instruments["metone_es405"]
        for datafile in es405.get_datafiles("horel", "qaqc", "2026-03"):
            assert tuple(datafile.es642_column_dates) == (
                pd.Timestamp("2026-02-01"),
                pd.Timestamp("2026-04-01"),
            )
        bus03 = get_site("BUS03").instruments["metone_es405"]
        for datafile in bus03.get_datafiles("horel", "qaqc", "2025-02"):
            assert datafile.es642_column_dates is None

    def test_names_stand_for_es405_columns(self):
        """Each ES642 name read for the ES405 maps to a column the ES405 has."""
        assert horel.ES405_UNDER_ES642_NAMES
        for name in horel.ES405_UNDER_ES642_NAMES.values():
            assert name in horel.column_mapping["metone_es405"]

    def test_only_the_es405_takes_them_as_its_own(self, tmp_path):
        path = write_csv_gz(
            tmp_path / "csv_finalized_ebus" / "BUS01_2026_03.csv.gz",
            ES642_NAMED,
            ES642_UNITS,
            es642_named_rows("2026-03-02 20:21", [4.0]),
        )
        es405 = horel.HorelCSVFile(path, "metone_es405")
        es405.es642_column_dates = TimeRange(
            start=pd.Timestamp("2026-02-01"), stop=pd.Timestamp("2026-04-01")
        )
        assert "ES405_PM2.5_Concentration" in es405.parse().columns
        es642 = horel.HorelCSVFile(path, "metone_es642").parse()
        assert "ES642_PM2.5_Concentration" in es642.columns
        assert "ES405_PM2.5_Concentration" not in es642.columns
