"""
Tests for per-group date windows (config ``group_dates``) and split reads.

See uataq#33. No CHPC data needed: reads are mocked.
"""

import logging
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from uataq import errors, filesystem, instruments, sites
from uataq.timerange import TimeRange

LIN_STOP = datetime(2017, 10, 28)
# A week either side of lin's stop. Datetimes, not strings: a stop string
# parses inclusively ("2017-10-30" would stop at 2017-10-31 00:00).
SPAN = (datetime(2017, 10, 20), datetime(2017, 10, 30))


def make(groups=("horel", "lin"), name="2b_205", **config):
    """Make an instrument operated by ``groups``, installed 2015-05-13 by default."""

    class Concrete(instruments.Instrument):
        model = "test_model"

    config.setdefault("installation_date", "2015-05-13")
    return Concrete(
        SID="TEST",
        name=name,
        loggers={g: f"{g}-logger" for g in groups},
        config=config,
    )


def trx_like(**config):
    """Like TRX01 2b_205: both groups log it, lin's archive stops in 2017."""
    return make(group_dates={"lin": ["2015-05-13", "2017-10-28"]}, **config)


def as_tuples(plan):
    """Return a plan as plain (group, start, stop) tuples, for comparison."""
    return [(group, portion.start, portion.stop) for group, portion in plan]


class TestGroupDatesConfig:
    """Parsing and validating ``group_dates``."""

    def test_parsed_as_half_open_instants(self):
        inst = trx_like()
        window = inst.group_dates["lin"]
        # an exact instant, not the end of that day like a TimeRange stop string
        assert (window.start, window.stop) == (datetime(2015, 5, 13), LIN_STOP)

    def test_absent_means_no_windows(self):
        assert make().group_dates == {}

    def test_null_end_is_unbounded(self):
        inst = make(group_dates={"horel": ["2017-10-28", None]})
        assert inst.group_dates["horel"].stop is None

    def test_group_that_does_not_operate_raises(self):
        with pytest.raises(ValueError, match="does not operate"):
            make(groups=["horel"], group_dates={"lin": ["2015", "2016"]})

    def test_not_a_pair_raises(self):
        with pytest.raises(ValueError, match=r"\[start, stop\]"):
            make(group_dates={"lin": ["2015-05-13"]})

    def test_stop_before_start_raises(self):
        with pytest.raises(ValueError, match="ends before it starts"):
            make(group_dates={"lin": ["2017-01-01", "2016-01-01"]})

    def test_real_config_parses(self):
        import uataq

        windows = {
            (SID, inst.name): inst.group_dates
            for SID in uataq.laboratory.sites
            for inst in uataq.get_site(SID).instruments
            if inst.group_dates
        }
        assert set(windows) == {
            ("TRX01", "2b_205"),
            ("TRX02", "2b_205"),
            ("TRX02", "metone_es642"),
        }
        assert windows["TRX01", "2b_205"]["lin"].stop == LIN_STOP


class TestPlanReads:
    """Instrument.plan_reads: which group reads which part of a range."""

    def test_explicit_group_reads_the_whole_range(self):
        inst = trx_like()
        plan = inst.plan_reads("horel", SPAN)
        assert as_tuples(plan) == [
            ("horel", datetime(2017, 10, 20), datetime(2017, 10, 30))
        ]

    def test_explicit_lin_is_not_cut_at_its_stop(self):
        """Naming a group is a request for its data, even outside its window."""
        plan = trx_like().plan_reads("lin", "2024-06-01")
        assert [g for g, _ in plan] == ["lin"]

    def test_mapping_naming_the_instrument_reads_the_whole_range(self):
        plan = trx_like().plan_reads({"2b_205": "lin"}, ("2017-10-20", "2017-11"))
        assert [g for g, _ in plan] == ["lin"]

    def test_mapping_without_the_instrument_splits(self):
        plan = trx_like().plan_reads({"gps": "horel"}, SPAN)
        assert [g for g, _ in plan] == ["lin", "horel"]

    def test_inside_lin_window_reads_lin_only(self):
        plan = trx_like().plan_reads(None, "2016-06")
        assert as_tuples(plan) == [
            ("lin", datetime(2016, 6, 1), datetime(2016, 7, 1)),
        ]

    def test_after_lin_window_reads_horel_only(self):
        plan = trx_like().plan_reads(None, "2024-06-01")
        assert as_tuples(plan) == [
            ("horel", datetime(2024, 6, 1), datetime(2024, 6, 2)),
        ]

    def test_spanning_lin_stop_splits_exactly_there(self):
        plan = trx_like().plan_reads(None, SPAN)
        assert as_tuples(plan) == [
            ("lin", datetime(2017, 10, 20), LIN_STOP),
            ("horel", LIN_STOP, datetime(2017, 10, 30)),
        ]

    def test_none_range_reads_lin_from_installation_then_horel(self):
        plan = trx_like().plan_reads()
        assert as_tuples(plan) == [
            ("lin", datetime(2015, 5, 13), LIN_STOP),
            ("horel", LIN_STOP, None),
        ]

    def test_open_ended_range_after_installation(self):
        """get_recent_obs asks for [start, None)."""
        plan = trx_like().plan_reads(None, [datetime(2024, 6, 1), None])
        assert as_tuples(plan) == [("horel", datetime(2024, 6, 1), None)]

    def test_horel_stops_at_removal(self):
        inst = make(
            group_dates={"lin": ["2016-02-04", "2017-06-21"]},
            installation_date="2016-02-04",
            removal_date="2025-01-03",
        )
        assert as_tuples(inst.plan_reads()) == [
            ("lin", datetime(2016, 2, 4), datetime(2017, 6, 21)),
            ("horel", datetime(2017, 6, 21), datetime(2025, 1, 3)),
        ]

    def test_portions_are_a_partition_of_the_clipped_range(self):
        inst = trx_like()
        plan = inst.plan_reads(None, ("2010", "2030"))
        clipped = inst.clip_to_active(("2010", "2030"))
        assert plan[0][1].start == clipped.start
        assert plan[-1][1].stop == clipped.stop
        for (_, a), (_, b) in zip(plan, plan[1:], strict=False):
            assert a.stop == b.start

    def test_default_group_preferred_where_windows_overlap(self):
        """Both cover 2016: lin, the default, wins although horel is listed first."""
        inst = make(
            group_dates={"lin": ["2015-05-13", "2017-01-01"], "horel": ["2016", None]}
        )
        assert filesystem.DEFAULT_GROUP == "lin"
        assert as_tuples(inst.plan_reads(None, ("2016-06", "2017-05"))) == [
            ("lin", datetime(2016, 6, 1), datetime(2017, 1, 1)),
            ("horel", datetime(2017, 1, 1), datetime(2017, 6, 1)),
        ]

    def test_configured_order_breaks_ties_without_the_default(self):
        """With the default group not an operator, the first configured wins."""
        inst = make(group_dates={"lin": ["2015-05-13", "2017-01-01"]})
        with patch.object(filesystem, "DEFAULT_GROUP", "nobody"):
            plan = inst.plan_reads(None, "2016")
        assert [g for g, _ in plan] == ["horel"]

    def test_uncovered_portion_is_skipped(self, caplog):
        inst = make(
            group_dates={"lin": ["2015-05-13", "2016-01-01"], "horel": ["2017", None]}
        )
        with caplog.at_level(logging.DEBUG, logger="uataq.instruments"):
            plan = inst.plan_reads(None, ("2015-06", "2017-05"))
        assert as_tuples(plan) == [
            ("lin", datetime(2015, 6, 1), datetime(2016, 1, 1)),
            ("horel", datetime(2017, 1, 1), datetime(2017, 6, 1)),
        ]
        assert "skipping" in caplog.text

    def test_nothing_covered_raises(self):
        inst = make(groups=["lin"], group_dates={"lin": ["2015-05-13", "2016"]})
        with pytest.raises(errors.ReaderError, match="No group's archive covers"):
            inst.plan_reads(None, "2018")

    def test_inactive_still_raises(self):
        with pytest.raises(errors.InactiveInstrumentError):
            trx_like().plan_reads(None, "2014")

    def test_without_group_dates_matches_resolve_group(self):
        inst = make()
        plan = inst.plan_reads(None, SPAN)
        assert as_tuples(plan) == [
            (inst.resolve_group(), datetime(2017, 10, 20), datetime(2017, 10, 30))
        ]

    def test_real_trx01_ozone_after_2017_reads_horel(self):
        import uataq

        inst = uataq.get_site("TRX01").instruments["2b_205"]
        assert [g for g, _ in inst.plan_reads(None, "2024-06-01")] == ["horel"]
        # resolve_group itself is unchanged: a config lookup
        assert inst.resolve_group() == "lin"

    def test_real_gps_still_reads_lin(self):
        import uataq

        inst = uataq.get_site("TRX01").instruments["gps"]
        assert [g for g, _ in inst.plan_reads(None, "2024-06-01")] == ["lin"]


def fake_read(failing=()):
    """Stand in for Instrument.read_data: two samples per portion, tagged by group."""

    def read_data(group, lvl=None, time_range=None, num_processes=1, pattern=None):
        if group in failing:
            raise errors.ReaderError(f"no {group} files")
        start = TimeRange(time_range).start
        index = pd.DatetimeIndex(
            [start, start + pd.Timedelta(hours=1)], name="Time_UTC"
        )
        value = 1.0 if group == "lin" else 2.0
        return pd.DataFrame({"O3_ppb": [value, value]}, index=index)

    return read_data


class TestSiteReadsSplitPlan:
    """Site.read_data reads each portion and concatenates them (uataq#33)."""

    @pytest.fixture
    def trx01(self):
        import uataq

        return uataq.get_site("TRX01")

    def read(self, site, failing=(), **kwargs):
        inst = site.instruments["2b_205"]
        with patch.object(inst, "read_data", side_effect=fake_read(failing)) as rd:
            data = site.read_data("2b_205", **kwargs)
        return data, rd

    def test_spanning_range_reads_both_groups_in_time_order(self, trx01):
        data, rd = self.read(trx01, time_range=SPAN)

        assert [c.args[0] for c in rd.call_args_list] == ["lin", "horel"]
        portions = [c.args[2] for c in rd.call_args_list]
        assert (portions[0].stop, portions[1].start) == (LIN_STOP, LIN_STOP)

        df = data["2b_205"]
        assert df.index.is_monotonic_increasing
        assert df["O3_ppb"].tolist() == [1.0, 1.0, 2.0, 2.0]
        assert df.index[2] == LIN_STOP

    def test_lvl_is_passed_to_every_portion(self, trx01):
        _, rd = self.read(trx01, lvl="final", time_range=("2017-10-20", "2017-11"))
        assert [c.args[1] for c in rd.call_args_list] == ["final", "final"]

    def test_explicit_group_is_one_read(self, trx01):
        _, rd = self.read(trx01, group="horel", time_range=("2017-10-20", "2017-11"))
        assert [c.args[0] for c in rd.call_args_list] == ["horel"]

    def test_failed_portion_is_skipped_and_the_rest_returned(self, trx01, caplog):
        with caplog.at_level(logging.WARNING, logger="uataq.sites"):
            data, _ = self.read(trx01, failing={"horel"}, time_range=SPAN)
        assert data["2b_205"]["O3_ppb"].tolist() == [1.0, 1.0]
        assert "no horel files" in caplog.text

    def test_every_portion_failing_raises_and_names_each_group(self, trx01):
        with pytest.raises(errors.ReaderError) as excinfo:
            self.read(
                trx01,
                failing={"lin", "horel"},
                time_range=SPAN,
            )
        message = str(excinfo.value)
        assert "2b_205 in lin groupspace" in message
        assert "horel groupspace" in message

    def test_get_obs_combines_the_portions(self, trx01):
        inst = trx01.instruments["2b_205"]
        with patch.object(inst, "read_data", side_effect=fake_read()):
            obs = sites.Site.get_obs(trx01, "O3", time_range=("2017-10-20", "2017-11"))
        assert obs["O3_ppb"].tolist() == [1.0, 1.0, 2.0, 2.0]

    def test_inactive_instrument_is_reported_not_read(self, trx01):
        """Outside its installation an instrument is skipped, as before."""
        with pytest.raises(errors.ReaderError, match="2b_205 not read"):
            trx01.read_data("2b_205", time_range="2014")
