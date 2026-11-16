"""
Tests for the Google Street View cars' reader (uataq.gsv).

A few synthetic rows are written under ``tmp_path`` in the merged table's two
formats: the Lin group's ``3_primary_keys.csv`` (times with a UTC offset, empty
cells, rows out of time order) and the published ``GSV_SLC.csv`` (times without
an offset, ``NA``, quoted text), each with the Picarro's own table beside it. The
test against the real table is marked ``chpc``.
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


def picarro_co(qc=0):
    """Return the CO cells of a row of the Picarro; its CH4 is in a table of its own."""
    return {
        "co_ppb": 95.0,
        "co_ppb_ex": 5.0,
        "co_ppb_base": 90.0,
        "qc_picarro_g2401": qc,
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
    # the Picarro on star: good, manually removed, and parked (its CH4 is below)
    row("2019-08-15 16:00:00", "star", **picarro_co()),
    row("2019-08-15 16:00:01", "star", **picarro_co(qc=-1)),
    row("2019-08-15 16:00:02", "star", qc_gps=11, polygon=np.nan, **picarro_co()),
]

# The Picarro's own table: the CH4 the merged table lacks, and other columns
PICARRO = pd.DataFrame(
    {
        "time": [
            "2019-08-15 16:00:01+00:00",
            "2019-08-15 16:00:00+00:00",
            "2019-08-15 16:00:02+00:00",
        ],
        "system_id": "star",
        "ch4d_ppb": [1990.0, 1922.0, 1930.0],
        "h2o_pct": 0.5,
        "co_ppb": 95.0,
        "qc": [-1, 0, 0],
        "ch4d_ppb_base": 1900.0,
        "ch4d_ppb_ex": [90.0, 22.0, 30.0],
    }
)


def write_chpc(folder):
    """Write ROWS as the Lin group's ``3_primary_keys.csv`` and return the folder."""
    table = pd.DataFrame(ROWS, columns=HEADER)
    table["time"] = table["time"] + "+00:00"
    table.to_csv(folder / gsv.TABLE, index=False)
    PICARRO.to_csv(folder / gsv.TABLE_PICARRO, index=False)
    return folder


def write_zenodo(folder):
    """Write ROWS as the published ``GSV_SLC.csv``, in time order, and return the file."""
    table = pd.DataFrame(ROWS, columns=HEADER).sort_values(["time", "system_id"])
    table["polygon"] = table["polygon"].fillna("")
    file = folder / "GSV_SLC.csv"
    table.to_csv(file, index=False, na_rep="NA", quoting=csv.QUOTE_NONNUMERIC)
    PICARRO.to_csv(folder / gsv.TABLE_PICARRO, index=False)
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
        "CH4d_ppb", "CH4d_ppb_ex", "CH4d_ppb_base", "qc_picarro_g2401",
    ]  # fmt: skip
    # the six rows with the LGR's CH4 and the three with the Picarro's, by time
    assert obs.index.is_monotonic_increasing
    assert len(obs) == 9
    assert obs["CH4d_ppm"].dropna().to_list() == [1.93, 2.50, 1.95, 1.92, 1.91, 2.10]
    assert obs.index[0] == pd.Timestamp("2019-07-16 18:00:00")
    assert obs.loc["2019-08-20", "polygon"].to_list() == ["UofU"]
    assert obs["CH4d_ppm_ex"].iloc[0] == pytest.approx(0.03)
    # the Picarro's, joined on the second and the car, never on the same row as the LGR's
    assert obs["CH4d_ppb"].dropna().to_list() == [1922.0, 1990.0, 1930.0]
    assert obs["CH4d_ppb_ex"].dropna().to_list() == [22.0, 90.0, 30.0]
    assert obs["CH4d_ppb_base"].dropna().to_list() == [1900.0] * 3
    assert obs["CH4d_ppb"].iloc[5:8].notna().all()
    assert obs["CH4d_ppm"].iloc[5:8].isna().all()
    # flags are kept (the Picarro's is the merged table's), and a row without a fix
    # has no position
    assert obs["qc_lgr_mgga"].to_list() == pytest.approx(
        [0, -2, 0, 0, 0, np.nan, np.nan, np.nan, 0], nan_ok=True
    )
    assert obs["qc_picarro_g2401"].dropna().to_list() == [0, -1, 0]
    assert obs["qc_gps"].iloc[3] == 11
    assert np.isnan(obs["Latitude_deg"].iloc[4])
    assert pd.isna(obs["polygon"].iloc[3])


def test_column_names_follow_uataq(table):
    obs = gsv.get_obs(path=table)

    for pollutant in gsv.POLLUTANTS:
        columns = concentration_columns(pollutant, obs.columns)
        # CH4 has two analyzers, the LGR's in ppm and the Picarro's in ppb
        assert columns == (["CH4d_ppm", "CH4d_ppb"] if pollutant == "CH4" else columns)
        assert len(columns) == (2 if pollutant == "CH4" else 1)
        for column in columns:
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
        "CH4d_ppb", "CH4d_ppb_ex", "CH4d_ppb_base", "qc_picarro_g2401",
        "CO2d_ppm", "CO2d_ppm_ex", "CO2d_ppm_base", "qc_licor_7000",
    ]  # fmt: skip
    assert np.isnan(obs["CH4d_ppm"].iloc[0])  # lone had no CH4 that second


def test_cars(table):
    lone = gsv.get_obs("CH4", cars="LONE", path=table)
    assert lone["system_id"].to_list() == ["lone"]

    both = gsv.get_obs("CH4", cars=["star", "lone"], path=table)
    assert len(both) == 9

    # the Picarro rode on star only
    assert gsv.get_obs("CH4", cars="lone", path=table)["CH4d_ppb"].isna().all()


def test_time_range_is_half_open(table):
    day = gsv.get_obs("CH4", time_range="2019-07-16", path=table)
    assert day["CH4d_ppm"].to_list() == [1.93, 2.50, 1.95, 1.92]

    # a row exactly at the stop is left out
    stop = dt.datetime(2019, 7, 17)
    pair = gsv.get_obs("CH4", time_range=("2019-07-16 18:00:01", stop), path=table)
    assert pair["CH4d_ppm"].to_list() == [2.50, 1.95, 1.92]

    later = gsv.get_obs("CH4", time_range=("2019-07-17", None), path=table)
    assert later["CH4d_ppm"].dropna().to_list() == [1.91, 2.10]

    # the Picarro's rows follow the range too
    picarro = gsv.get_obs("CH4", time_range=("2019-08-15 16:00:01", None), path=table)
    assert picarro["CH4d_ppb"].dropna().to_list() == [1990.0, 1930.0]


def test_good_only_one_pollutant(table):
    obs = gsv.get_obs("CH4", good_only=True, path=table)

    # drops the calibration, the parked car and the row without a fix, and the
    # Picarro's CH4 that is flagged or parked
    assert obs["CH4d_ppm"].to_list() == pytest.approx(
        [1.93, 1.95, np.nan, 2.10], nan_ok=True
    )
    assert obs["CH4d_ppb"].to_list() == pytest.approx(
        [np.nan, np.nan, 1922.0, np.nan], nan_ok=True
    )
    assert (obs["qc_lgr_mgga"].dropna() == 0).all()
    assert (obs["qc_picarro_g2401"].dropna() == 0).all()
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
    assert len(obs) == 6  # the Picarro's good CH4 is the sixth


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

    assert len(gsv.get_obs("CH4")) == 9


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
    (tmp_path / gsv.TABLE_PICARRO).write_text(",".join(PICARRO.columns) + "\n")

    with pytest.warns(errors.EmptyResultWarning):
        obs = gsv.get_obs("CH4", path=file)
    assert obs.empty


def test_picarro_and_co_share_the_flag(table):
    obs = gsv.get_obs(["CO", "CH4"], good_only=True, path=table)

    assert obs.columns.to_list().count("qc_picarro_g2401") == 1
    good = obs[obs["CH4d_ppb"].notna()]
    assert good["CH4d_ppb"].to_list() == [1922.0]
    assert good["CO_ppb"].to_list() == [95.0]
    # the manually removed second loses its CH4 and its CO together
    assert len(obs[obs["CO_ppb"].notna()]) == 1


def test_picarro_table_missing_warns(table):
    folder = table if table.is_dir() else table.parent
    (folder / gsv.TABLE_PICARRO).unlink()

    with pytest.warns(errors.DroppedPollutantWarning, match="2_picarro_g2401.csv"):
        obs = gsv.get_obs("CH4", path=table)

    assert obs["CH4d_ppm"].to_list() == [1.93, 2.50, 1.95, 1.92, 1.91, 2.10]
    assert not any(col.startswith("CH4d_ppb") for col in obs)
    # another pollutant needs no Picarro table
    assert len(gsv.get_obs("CO2", path=table)) == 5


def test_picarro_table_beside_a_folder_path(tmp_path):
    write_chpc(tmp_path)

    assert gsv.get_obs("CH4", path=tmp_path)["CH4d_ppb"].notna().sum() == 3


def test_not_the_picarro_table(tmp_path):
    write_chpc(tmp_path)
    (tmp_path / gsv.TABLE_PICARRO).write_text("time,system_id,co_ppb\n")

    with pytest.raises(errors.ParserError, match="no ch4d_ppb"):
        gsv.get_obs("CH4", path=tmp_path)


def test_qc_flags_cover_the_synthetic_rows():
    flags = {r[c] for r in ROWS for c in HEADER if c.startswith("qc_")}
    assert {int(f) for f in flags if not pd.isna(f)} <= set(gsv.QC_FLAGS)


@pytest.mark.chpc
def test_real_table_ch4():
    """The Lin group's table: the cars' good CH4, LGR's and Picarro's (counted 2026-11-16)."""
    obs = gsv.get_obs("CH4", good_only=True)

    assert obs.index.is_monotonic_increasing
    assert obs.index[0] == pd.Timestamp("2019-06-06 18:22:10")
    assert obs.index[-1] == pd.Timestamp("2019-10-21 18:57:04")
    assert set(obs["system_id"]) == {"lone", "star"}
    # the LGR's rows are the ones of 2026-11-13, the Picarro's are others, on star
    lgr, picarro = obs["CH4d_ppm"].notna(), obs["CH4d_ppb"].notna()
    assert lgr.sum() == 2_068_033
    assert picarro.sum() == 237_689
    assert not (lgr & picarro).any()
    assert set(obs.loc[picarro, "system_id"]) == {"star"}
    assert obs.loc[picarro].index[0] == pd.Timestamp("2019-08-14 18:02:27")
    assert obs.loc[picarro, "CH4d_ppb"].median() == pytest.approx(1921.6, abs=0.1)
