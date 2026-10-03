"""
Tests for the lin group space.
"""

import numpy as np
import pandas as pd
import pytest

from uataq.filesystem.groupspaces import lin


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
