"""Tests for air-trend files, in their own file to stay clear of test_lin.py."""

from unittest.mock import patch

import pandas as pd
import pytest

from uataq.errors import ParserError
from uataq.filesystem.groupspaces import lin

CONFIG = {
    "teledyne_t500u": {
        "air_trend": {"col_names": ["time", "no2_ppb", "box_t_c"], "col_types": "Tdd"}
    }
}
ROWS = [
    "2024-09-05T10:58:29.986555,XXXX,20.9",
    "2024-09-05T10:58:32.165402,12.5,21.0",
    "2024-09-05T10:58:34.300000,12.6,21.0",
]


def parse(tmp_path, text):
    path = tmp_path / "trx02" / "teledyne_t500u" / "raw" / "2024-09-05.csv"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    with patch.object(lin, "DATA_CONFIG", CONFIG):
        return lin.AirTrendFile(str(path)).parse()


def test_file_with_a_header_loses_no_row(tmp_path):
    """The header line is skipped and every row after it is kept."""
    data = parse(tmp_path, "time,no2_ppb,box_t_c\n" + "\n".join(ROWS) + "\n")
    assert len(data) == 3
    assert data["Time_UTC"].iloc[0] == pd.Timestamp("2024-09-05 10:58:29.986555")


@pytest.mark.parametrize("fraction", [True, False], ids=["fraction", "whole-second"])
def test_file_without_a_header_keeps_its_first_row(tmp_path, fraction):
    """
    A file that opens with a data row keeps that row (#184).

    Some Pi files have no header line, and ``header=0`` read the first row
    as one and dropped it.
    """
    rows = ROWS if fraction else ["2024-09-05T10:58:29,XXXX,20.9", *ROWS[1:]]
    data = parse(tmp_path, "\n".join(rows) + "\n")
    assert len(data) == 3
    assert data["Time_UTC"].iloc[0] == pd.Timestamp(rows[0].split(",")[0])
    assert list(data.columns) == ["Time_UTC", "no2_ppb", "box_t_c"]
    assert data["box_t_c"].tolist() == [20.9, 21.0, 21.0]


def test_file_whose_first_line_is_text_but_not_a_time_is_skipped(tmp_path):
    """
    Text that is not a time is still taken for a header.

    As in TRX02's T500U file of 2023-07-21, a tar archive whose first line is
    the tar block run into the CSV's header.
    """
    first = "2023-07-26.csv\x00\x000000644\x00ustar\x00time,no2_ppb,box_t_c"
    data = parse(tmp_path, first + "\n" + "\n".join(ROWS) + "\n")
    assert len(data) == 3


@pytest.mark.parametrize("header", [True, False], ids=["header", "no-header"])
def test_a_column_the_config_lacks_names_the_file(tmp_path, header):
    """
    One field more than the config put every name one off (#209).

    pandas took the time for the row label, so every Time_UTC was NaT and the
    read dropped the whole day without a word.
    """
    rows = [row.replace(",", ",999,", 1) for row in ROWS]
    text = ("time,new,no2_ppb,box_t_c\n" if header else "") + "\n".join(rows) + "\n"
    with pytest.raises(ParserError, match="4 fields, but the pipeline config lists 3"):
        parse(tmp_path, text)


def test_a_missing_column_names_the_file(tmp_path):
    rows = [row.rsplit(",", 1)[0] for row in ROWS]
    with pytest.raises(ParserError, match="2 fields"):
        parse(tmp_path, "time,no2_ppb\n" + "\n".join(rows) + "\n")


def test_an_empty_file_has_no_rows(tmp_path):
    """A file the logger has just opened is not an error."""
    assert parse(tmp_path, "").empty
