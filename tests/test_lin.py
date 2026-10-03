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
