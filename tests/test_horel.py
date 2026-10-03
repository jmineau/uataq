"""
Tests for the horel group space.
"""

from uataq.filesystem.groupspaces import horel


def test_column_names_do_not_depend_on_level():
    """Raw (h5) and CSV codes for the same quantity map to one name (#17)."""
    for instrument, mapping in horel.column_mapping.items():
        for name in mapping.values():
            assert "_hpa" not in name, f"{instrument}: {name} should be hPa"
