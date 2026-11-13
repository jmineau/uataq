"""
Tests for the Google Street View cars' reader (uataq.gsv).

A few synthetic rows are written under ``tmp_path`` in the merged table's two
formats: the Lin group's ``3_primary_keys.csv`` (times with a UTC offset, empty
cells, rows out of time order) and the published ``GSV_SLC.csv`` (times without
an offset, ``NA``, quoted text). The test against the real table is marked
``chpc``.
"""

import csv
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from uataq import errors, gsv
from uataq.pollutants import concentration_columns, parse_column

# The merged table's columns, in its order
HEADER = [
    "time", "system_id", "latitude", "longitude", "polygon", "qc_gps",
    "o3_ppb", "qc_2b_205",
    "ch4d_ppm", "ch4d_ppm_ex", "ch4d_ppm_base", "qc_lgr_mgga",
    "co2d_ppm", "co2d_ppm_ex", "co2d_ppm_base", "qc_licor_7000",
    "bc_ngm3", "bc_ngm3_ex", "bc_ngm3_base", "qc_magee_ae33",
    "co_ppb", "co_ppb_ex", "co_ppb_base", "qc_picarro_g2401",
    "no_ppb", "no_ppb_ex", "no_ppb_base", "qc_teledyne_t200",
    "no2_ppb", "no2_ppb_ex", "no2_ppb_base", "qc_teledyne_t500u",
    "pm25_ugm3", "pm25_ugm3_ex", "pm25_ugm3_base", "qc_thermo_pdr_1500",
]  # fmt: skip


def row(time, car, lat=40.76, lon=-111.89, polygon="Downtown", qc_gps=0, **cells):
    """Return one row of the merged table; ``cells`` fill the pollutant columns."""
    out = dict.fromkeys(HEADER, np.nan)
    out.update(time=time, system_id=car, latitude=lat, longitude=lon)
    out.update(polygon=polygon, qc_gps=qc_gps, **cells)
    return out


def ch4(value, qc=0, base=1.9):
    """Return the four CH4 cells of a row."""
    return {
        "ch4d_ppm": value,
        "ch4d_ppm_ex": round(value - base, 5),
        "ch4d_ppm_base": base,
        "qc_lgr_mgga": qc,
    }


def co2(value, qc=0, base=410.0):
    """Return the four CO2 cells of a row."""
    return {
        "co2d_ppm": value,
        "co2d_ppm_ex": round(value - base, 5),
        "co2d_ppm_base": base,
        "qc_licor_7000": qc,
    }


# Out of time order, as the real table is. Index 0..8 for reference in the tests.
ROWS = [
    row("2019-07-16 18:00:02", "star", **ch4(1.95), **co2(420.0)),
    row("2019-07-16 18:00:00", "star", **ch4(1.93), **co2(415.0, qc=-31)),
    # both cars in the same second
    row("2019-07-16 18:00:02", "lone", **co2(430.0), o3_ppb=40.0, qc_2b_205=0),
    # a calibration: CH4 flagged, CO2 good
    row("2019-07-16 18:00:01", "star", **ch4(2.50, qc=-2), **co2(418.0)),
    # parked where the car is stored (conditional use)
    row("2019-07-16 23:59:59", "star", qc_gps=11, polygon=np.nan, **ch4(1.92)),
    # no fix: no position and no GPS flag
    row(
        "2019-07-17 00:00:00",
        "star",
        lat=np.nan,
        lon=np.nan,
        polygon=np.nan,
        qc_gps=np.nan,
        **ch4(1.91),
    ),
    # a later month, the other car
    row("2019-08-20 15:00:00", "lone", polygon="UofU", **ch4(2.10)),
    # a row with neither CH4 nor CO2
    row(
        "2019-07-16 18:00:03",
        "star",
        pm25_ugm3=5.0,
        pm25_ugm3_ex=1.0,
        pm25_ugm3_base=4.0,
        qc_thermo_pdr_1500=0,
    ),
    # a manually passed CO2 (flag 1) and a bad position
    row("2019-07-16 18:00:04", "lone", lat=403919.5, qc_gps=-12, **co2(440.0, qc=1)),
]


def write_chpc(folder):
    """Write ROWS as the Lin group's ``3_primary_keys.csv`` and return the folder."""
    table = pd.DataFrame(ROWS, columns=HEADER)
    table["time"] = table["time"] + "+00:00"
    table.to_csv(folder / gsv.TABLE, index=False)
    return folder


def write_zenodo(folder):
    """Write ROWS as the published ``GSV_SLC.csv``, in time order, and return the file."""
    table = pd.DataFrame(ROWS, columns=HEADER).sort_values(["time", "system_id"])
    table["polygon"] = table["polygon"].fillna("")
    file = folder / "GSV_SLC.csv"
    table.to_csv(file, index=False, na_rep="NA", quoting=csv.QUOTE_NONNUMERIC)
    return file


@pytest.fixture(params=["chpc", "zenodo"])
def table(request, tmp_path):
    """Return the path of a synthetic merged table, in each of its two formats."""
    return write_chpc(tmp_path) if request.param == "chpc" else write_zenodo(tmp_path)


def test_ch4_columns_and_order(table):
    obs = gsv.get_obs("CH4", path=table)

    assert obs.index.name == "Time_UTC"
    assert obs.index.tz is None
    assert obs.index.dtype == "datetime64[ns]"
    assert obs.columns.to_list() == [
        "system_id", "Latitude_deg", "Longitude_deg", "polygon", "qc_gps",
        "CH4d_ppm", "CH4d_ppm_ex", "CH4d_ppm_base", "qc_lgr_mgga",
    ]  # fmt: skip
    # the six rows with CH4, sorted by time
    assert obs.index.is_monotonic_increasing
    assert obs["CH4d_ppm"].to_list() == [1.93, 2.50, 1.95, 1.92, 1.91, 2.10]
    assert obs.index[0] == pd.Timestamp("2019-07-16 18:00:00")
    assert obs.loc["2019-08-20", "polygon"].to_list() == ["UofU"]
    assert obs["CH4d_ppm_ex"].iloc[0] == pytest.approx(0.03)
    # flags are kept, and a row without a fix has no position
    assert obs["qc_lgr_mgga"].to_list() == [0, -2, 0, 0, 0, 0]
    assert obs["qc_gps"].iloc[3] == 11
    assert np.isnan(obs["Latitude_deg"].iloc[4])
    assert pd.isna(obs["polygon"].iloc[3])


def test_column_names_follow_uataq(table):
    obs = gsv.get_obs(path=table)

    for pollutant in gsv.POLLUTANTS:
        (column,) = concentration_columns(pollutant, obs.columns)
        parsed = parse_column(column)
        assert parsed is not None and parsed.pollutant == pollutant
    assert "O3_ppb_ex" not in obs  # the table has no O3 enhancement
    assert {"BC6_ngm3", "BC6_ngm3_ex", "BC6_ngm3_base", "PM2.5_ugm3"} <= set(obs)
    assert len(obs) == len(ROWS)


def test_same_second_sorted_by_car(table):
    obs = gsv.get_obs(["co2", "CH4"], path=table, time_range="2019-07-16 18:00:02")

    assert obs["system_id"].to_list() == ["lone", "star"]
    assert obs.index.to_list() == [pd.Timestamp("2019-07-16 18:00:02")] * 2
    # the table's order, whatever order was asked: CH4 before CO2
    assert obs.columns.to_list()[5:] == [
        "CH4d_ppm", "CH4d_ppm_ex", "CH4d_ppm_base", "qc_lgr_mgga",
        "CO2d_ppm", "CO2d_ppm_ex", "CO2d_ppm_base", "qc_licor_7000",
    ]  # fmt: skip
    assert np.isnan(obs["CH4d_ppm"].iloc[0])  # lone had no CH4 that second


def test_cars(table):
    lone = gsv.get_obs("CH4", cars="LONE", path=table)
    assert lone["system_id"].to_list() == ["lone"]

    both = gsv.get_obs("CH4", cars=["star", "lone"], path=table)
    assert len(both) == 6


def test_time_range_is_half_open(table):
    day = gsv.get_obs("CH4", time_range="2019-07-16", path=table)
    assert day["CH4d_ppm"].to_list() == [1.93, 2.50, 1.95, 1.92]

    # a row exactly at the stop is left out
    stop = dt.datetime(2019, 7, 17)
    pair = gsv.get_obs("CH4", time_range=("2019-07-16 18:00:01", stop), path=table)
    assert pair["CH4d_ppm"].to_list() == [2.50, 1.95, 1.92]

    later = gsv.get_obs("CH4", time_range=("2019-07-17", None), path=table)
    assert later["CH4d_ppm"].to_list() == [1.91, 2.10]


def test_good_only_one_pollutant(table):
    obs = gsv.get_obs("CH4", good_only=True, path=table)

    # drops the calibration, the parked car and the row without a fix
    assert obs["CH4d_ppm"].to_list() == [1.93, 1.95, 2.10]
    assert (obs["qc_lgr_mgga"] == 0).all()
    assert (obs["qc_gps"] == 0).all()


def test_good_only_several_pollutants(table):
    obs = gsv.get_obs(["CH4", "CO2"], good_only=True, path=table)

    # 18:00:00 CO2 flagged -31 and 18:00:01 CH4 flagged -2: emptied, rows kept
    assert obs["CH4d_ppm"].to_list()[:4] == pytest.approx(
        [1.93, np.nan, np.nan, 1.95], nan_ok=True
    )
    assert obs["CO2d_ppm"].to_list()[:4] == pytest.approx(
        [np.nan, 418.0, 430.0, 420.0], nan_ok=True
    )
    emptied = obs.iloc[1]
    assert np.isnan(emptied["CH4d_ppm_ex"]) and np.isnan(emptied["CH4d_ppm_base"])
    assert emptied["qc_lgr_mgga"] == -2  # the flag still says why
    # the CO2 with flag 1 sat on a bad position: gone
    assert 440.0 not in obs["CO2d_ppm"].to_list()
    assert len(obs) == 5


def test_empty_result_warns(table):
    with pytest.warns(errors.EmptyResultWarning, match="No Street View rows with CH4"):
        obs = gsv.get_obs("CH4", time_range="2020-01", path=table)

    assert obs.empty
    assert obs.index.name == "Time_UTC"
    assert "CH4d_ppm" in obs


def test_unknown_pollutant_and_car(table):
    with pytest.raises(ValueError, match="Unknown pollutant 'SO2'"):
        gsv.get_obs("SO2", path=table)
    with pytest.raises(ValueError, match="Unknown car 'moon'"):
        gsv.get_obs("CH4", cars="moon", path=table)
    with pytest.raises(ValueError, match="No pollutant given"):
        gsv.get_obs([], path=table)


def test_missing_table(tmp_path, lin_data_dir):
    with pytest.raises(FileNotFoundError, match="zenodo.7605718"):
        gsv.get_obs("CH4", path=tmp_path / "nowhere.csv")
    # with no path, the table is looked for under the Lin group's data folder
    with pytest.raises(FileNotFoundError, match="3_primary_keys.csv"):
        gsv.get_obs("CH4")


def test_default_path_follows_measurements_dir(lin_data_dir):
    tables = lin_data_dir / "gsv" / "tables"
    tables.mkdir(parents=True)
    write_chpc(tables)

    assert len(gsv.get_obs("CH4")) == 6


def test_not_the_merged_table(tmp_path):
    file = tmp_path / "2_lgr_mgga.csv"
    file.write_text(
        "time,system_id,ch4d_ppm,qc\n2019-07-16 18:00:00+00:00,star,1.9,0\n"
    )

    with pytest.raises(errors.ParserError, match="has no latitude"):
        gsv.get_obs("CH4", path=file)


def test_header_only_table(tmp_path):
    file = tmp_path / gsv.TABLE
    file.write_text(",".join(HEADER) + "\n")

    with pytest.warns(errors.EmptyResultWarning):
        obs = gsv.get_obs("CH4", path=file)
    assert obs.empty


def test_qc_flags_cover_the_synthetic_rows():
    flags = {r[c] for r in ROWS for c in HEADER if c.startswith("qc_")}
    assert {int(f) for f in flags if not pd.isna(f)} <= set(gsv.QC_FLAGS)


@pytest.mark.chpc
def test_real_table_ch4():
    """The Lin group's table: the cars' good CH4 (counted 2026-11-13)."""
    obs = gsv.get_obs("CH4", good_only=True)

    assert len(obs) == 2_068_033
    assert obs.index.is_monotonic_increasing
    assert obs.index[0] == pd.Timestamp("2019-06-06 18:22:10")
    assert obs.index[-1] == pd.Timestamp("2019-10-21 18:57:04")
    assert set(obs["system_id"]) == {"lone", "star"}
