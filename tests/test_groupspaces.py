"""
Tests for the group space adapters.
"""

import logging
from unittest.mock import patch

from uataq.filesystem import core, groups
from uataq.timerange import TimeRange


class TestNoticesUseLogging:
    """Notices go through logging, not stdout, so callers can silence them."""

    def test_horel_pilot_phase_notice(self, capsys, caplog):
        horel = groups["horel"]
        with (
            patch.object(horel, "get_files", return_value=[]),
            patch.object(core, "filter_datafiles", return_value=[]),
            caplog.at_level(logging.INFO, logger="uataq"),
        ):
            horel.get_datafiles("TRX01", "2b_205", "final", "", TimeRange())

        assert capsys.readouterr().out == ""
        assert "pilot phase" in caplog.text

    def test_lin_mobile_raw_notice(self, capsys, caplog):
        lin = groups["lin"]
        with (
            patch.object(core.GroupSpace, "get_datafiles", return_value=[]),
            caplog.at_level(logging.WARNING, logger="uataq"),
        ):
            lin.get_datafiles("TRX01", "2b_205", "raw", "campbellsci", TimeRange())

        assert capsys.readouterr().out == ""
        assert "may not be accurate" in caplog.text
