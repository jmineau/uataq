"""Tests for the lin column renaming, in their own file to stay clear of test_lin.py."""

import pandas as pd
import pytest

from uataq.filesystem.groupspaces import lin


@pytest.mark.parametrize(
    "instrument, raw_name, qaqc_name",
    [
        ("teledyne_t300", "samp_t_c", "Samp_T_C"),
        ("teledyne_t400", "samp_t_c", "Samp_T_C"),
        ("teledyne_t500u", "samp_temp_c", "Samp_T_C"),
    ],
)
def test_sample_temperature_has_one_name_at_every_level(
    instrument, raw_name, qaqc_name
):
    """
    The Teledyne analyzers' sample temperature is ``Internal_T_C`` at raw and qaqc (#185).

    The pipeline's t500u qaqc files say ``Samp_T_C`` (its raw files say
    ``samp_temp_c``); the mapping had ``Samp_Temp_C``, which no file has.
    """
    for name in (raw_name, qaqc_name):
        data = pd.DataFrame({name: [45.0, 45.1]})
        out = lin.LinGroup.standardize_data(instrument, data)
        assert list(out.columns) == ["Internal_T_C"]


MET_NAMES = [
    "Case_T_C",
    "Case_RH_pct",
    "Case_T2_C",
    "Case_P_hPa",
    "Ambient_T_C",
    "Ambient_RH_pct",
    "Box_T_C",
]


def test_met_raw_and_final_columns_have_the_same_names(tmp_path):
    """TRX02's met raw air-trend file comes out with the final files' names (#160)."""
    path = tmp_path / "trx02" / "met" / "raw" / "2016-02-04.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "time,case_t_c,case_rh_pct,case_t2_c,case_p_hpa,amb_t_c,amb_rh_pct,box_t_c\n"
        "2016-02-04T00:30:18.428737,21,14.9,20.60,880.88,20.3,18.1,21.19\n"
        "2016-02-04T00:30:20.030000,21,14.8,20.60,880.87,20.3,18.0,21.25\n"
    )
    raw = lin.AirTrendFile(str(path)).parse()
    raw = lin.LinGroup.standardize_data("met", raw)
    assert list(raw.columns) == ["Time_UTC", *MET_NAMES]
    assert raw["Case_P_hPa"].tolist() == [880.88, 880.87]

    final = lin.LinGroup.standardize_data(
        "met", pd.DataFrame({name: [1.0] for name in MET_NAMES})
    )
    assert list(final.columns) == MET_NAMES


@pytest.mark.chpc
@pytest.mark.parametrize("lvl", ["raw", "final"])
def test_trx02_met_reads_from_the_archive(lvl):
    """TRX02's met reads at both levels the pipeline wrote, with the same columns (#160)."""
    import uataq

    data = uataq.read_data("TRX02", instruments="met", lvl=lvl, time_range="2017-06-20")
    met = data["met"]
    assert set(MET_NAMES) <= set(met.columns)
    # the final files round times to hundredths of a second
    assert met.index.max().floor("s") == pd.Timestamp("2017-06-20 05:28:51")
