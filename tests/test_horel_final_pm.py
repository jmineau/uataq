"""Tests for the horel final level, in their own file to stay clear of test_horel.py."""

import pandas as pd

from uataq.filesystem.groupspaces import horel

from .test_horel import TRX_HEADER, TRX_UNITS, write_csv_gz

PM = 5  # index of ES642_PM2.5_Concentration in a TRX row


def es642_final(tmp_path, pm_values):
    """Read the ES642's final level from three unflagged rows with these PM2.5 values."""
    rows = [
        ["2024-06-01T00:00:00", 40.76, -111.86, 1325.4, 13.1, pm_values[0], 29.3, 47.2, 1.9, 825.3, 0, 0],
        ["2024-06-01T00:00:02", 40.76, -111.86, 1325.7, 13.1, pm_values[1], 29.4, 50.3, 1.9, 825.3, 0, 0],
        ["2024-06-01T00:00:04", 40.76, -111.86, 1325.9, 13.1, pm_values[2], 29.5, 51.0, 1.9, 825.3, 0, 0],
    ]  # fmt: skip
    path = write_csv_gz(tmp_path / "TRX01_2024_06.csv.gz", TRX_HEADER, TRX_UNITS, rows)
    return horel.HorelCSVFinalizedFile(path, "metone_es642").parse()


def test_es642_final_drops_rows_with_no_pm25(tmp_path):
    """
    A row with a temperature and no PM2.5 is not a final row (#186).

    ``Ambient_T_C`` is the sampler's own temperature, which the ES642 reports
    when it has no concentration, so it does not make a row an observation.
    """
    data = es642_final(tmp_path, [2.0, -9999.0, 3.0])

    assert data["Time_UTC"].tolist() == [
        pd.Timestamp("2024-06-01 00:00:00"),
        pd.Timestamp("2024-06-01 00:00:04"),
    ]
    assert data["PM2.5_ugm3"].tolist() == [2.0, 3.0]
    # the ambient columns stay on the rows that are kept
    assert data["Ambient_T_C"].tolist() == [29.3, 29.5]


def test_es642_final_without_any_pm25_is_empty(tmp_path):
    """No concentration at all, no rows (the temperature alone keeps none)."""
    assert es642_final(tmp_path, [-9999.0] * 3).empty
