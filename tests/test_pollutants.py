"""
Tests for uataq.pollutants.
"""

import pytest

from uataq import network, pollutants
from uataq.pollutants import ConcentrationColumn, parse_column


def test_pollutants_come_from_the_catalog():
    assert {"CO2", "CH4", "NOx", "PM2.5", "BC"} <= set(pollutants.POLLUTANTS)


def test_network_still_exports_concentration_columns():
    assert network.concentration_columns is pollutants.concentration_columns


@pytest.mark.parametrize(
    "column, expected",
    [
        ("O3_ppb", ConcentrationColumn("O3_ppb", "O3", "ppb")),
        (
            "CO2d_ppm_cal",
            ConcentrationColumn("CO2d_ppm_cal", "CO2", "ppm", True, "cal"),
        ),
        (
            "CH4d_ppm_raw",
            ConcentrationColumn("CH4d_ppm_raw", "CH4", "ppm", True, "raw"),
        ),
        ("NO2_ppb", ConcentrationColumn("NO2_ppb", "NO2", "ppb")),
        ("NOx_ppb", ConcentrationColumn("NOx_ppb", "NOx", "ppb")),
        ("PM10_ugm3", ConcentrationColumn("PM10_ugm3", "PM10", "ugm3")),
        ("PM2.5_ugm3", ConcentrationColumn("PM2.5_ugm3", "PM2.5", "ugm3")),
        ("BC6_ngm3", ConcentrationColumn("BC6_ngm3", "BC", "ngm3", channel=6)),
    ],
)
def test_parse_column(column, expected):
    assert parse_column(column) == expected


@pytest.mark.parametrize(
    "column", ["Time_UTC", "O3_Meas_mV", "O3_ppb_std", "CO2d_ppm_sd", "H2O_ppm"]
)
def test_parse_column_rejects_non_concentrations(column):
    assert parse_column(column) is None
