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
