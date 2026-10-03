"""
Tests for the horel group space.
"""

import os
from unittest.mock import patch

from uataq.filesystem.groupspaces import horel


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
