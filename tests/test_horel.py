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
        """Storage (GPS_Data_Flagged) is a positive flag, an invalid RMC fix
        a negative one, and the source columns are dropped."""
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
        """final if the site has a finalized file (BUS in the ebus dir)."""
        assert horel.HorelGroup.get_highest_lvl("TRX01", "2b_205") == "final"
        assert horel.HorelGroup.get_highest_lvl("BUS01", "2b_205") == "final"
        assert horel.HorelGroup.get_highest_lvl("TRX02", "2b_205") == "raw"
        assert horel.HorelGroup.get_highest_lvl("BUS02", "2b_205") == "raw"

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
