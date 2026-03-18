"""
Shared fixtures and configuration for UATAQ tests.
"""

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def sample_datetime():
    """Return a sample datetime for testing."""
    return dt.datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def sample_datetime_range():
    """Return a sample datetime range tuple."""
    start = dt.datetime(2024, 1, 1, 0, 0, 0)
    stop = dt.datetime(2024, 1, 31, 23, 59, 59)
    return start, stop


@pytest.fixture
def sample_dataframe():
    """Return a sample pandas DataFrame for testing."""
    return pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=24, freq="H"),
        "pollutant_ppm": [1.0 + i * 0.1 for i in range(24)],
        "temperature_c": [20.0 + i * 0.2 for i in range(24)],
        "humidity_percent": [50.0 + i * 0.5 for i in range(24)],
    })


@pytest.fixture
def mock_config():
    """Return a mock site configuration."""
    return {
        "name": "Test Site",
        "is_active": True,
        "is_mobile": False,
        "latitude": 40.7608,
        "longitude": -111.8910,
        "zagl": 10.0,
        "loggers": {
            "horel": "horel-group",
            "lin": "lin-group",
        },
        "instruments": {
            "crds": {
                "loggers": {"horel": "horel-group"},
                "installation_date": "2023-01-01",
                "removal_date": None,
            },
            "licor": {
                "loggers": {"lin": "lin-group"},
                "installation_date": "2023-06-01",
                "removal_date": None,
            },
        },
    }


@pytest.fixture
def mock_instrument():
    """Return a mock instrument object."""
    mock = MagicMock()
    mock.name = "test_instrument"
    mock.SID = "test_site"
    mock.model = "TestModel"
    mock.groups = ["horel", "lin"]
    mock.loggers = {"horel-group", "lin-group"}
    mock.pollutants = ["CO2", "CH4"]
    mock.config = {}
    return mock


@pytest.fixture
def mock_instrument_ensemble():
    """Return a mock instrument ensemble."""
    mock = MagicMock()
    mock.groups = {"horel", "lin"}
    mock.loggers = {"horel-group", "lin-group"}
    mock.pollutants = {"CO2", "CH4", "N2O"}
    mock.__iter__ = lambda self: iter([])  # Empty ensemble
    return mock


@pytest.fixture
def sample_files():
    """Return a list of sample file paths."""
    return [
        "/data/raw/2024/01/01/site_instrument_001.dat",
        "/data/raw/2024/01/02/site_instrument_001.dat",
        "/data/raw/2024/01/03/site_instrument_001.dat",
    ]


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary test directory structure."""
    raw_dir = tmp_path / "raw" / "2024" / "01"
    raw_dir.mkdir(parents=True, exist_ok=True)

    qaqc_dir = tmp_path / "qaqc" / "2024" / "01"
    qaqc_dir.mkdir(parents=True, exist_ok=True)

    # Create sample data files
    for day in range(1, 4):
        with open(raw_dir / f"site_instrument_{day:02d}.dat", "w") as f:
            f.write(f"# Sample data for day {day}\n")

    return tmp_path
