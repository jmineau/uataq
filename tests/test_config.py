"""
Tests of the dates in the packaged config.json.

A ``removal_date`` is an instant and reads are half-open, so a removal date on
a day that still has data hides that day's rows. Each removal date is the
midnight after the instrument's last sample (the evidence is in its
``notes``), except where an earlier date is kept on purpose, and at a MetOne
swap, where it is the replacement's first raw row.
"""

import pandas as pd
import pytest

import uataq
from uataq import errors, filesystem

#: Instruments whose removal date is the midnight after their last sample
#: (raw or qaqc, whichever is later), with that last sample
LAST_SAMPLES = {
    ("ASB", "licor_6262"): "2015-08-05 14:30:00",
    ("BUS01", "2b_405"): "2022-05-09 17:42:50",
    ("BUS03", "2b_405"): "2024-05-14 17:56:15",
    ("DBK", "licor_6262"): "2022-05-13 15:32:10",
    ("IMC", "licor_6262"): "2020-09-15 23:19:20",
    ("LDF", "lgr_ugga"): "2023-09-28 20:16:39.61",
    ("LG2", "licor_6262"): "2022-05-11 16:16:00",
    ("LGN", "licor_6262"): "2020-03-15 07:31:40",
    ("MSA", "licor_6262"): "2016-07-26 16:15:00",
    ("MUR", "licor_6262"): "2013-08-02 17:05:00",
    ("ROO", "lgr_ugga"): "2019-07-16 16:11:50.693",
    ("SUG", "licor_6262"): "2022-02-11 18:07:50",
    ("SUG", "metone_es642"): "2020-04-23 23:12:10",
    ("SUN", "licor_6262"): "2019-11-07 18:28:10",
    ("TRX01", "lgr_ugga"): "2024-08-27 17:44:49",
    ("TRX02", "lgr_no2"): "2017-06-20 05:28:52.377158",
    ("WBB", "magee_ae33"): "2024-06-19 17:41:53.764569",
    ("WBB", "metone_es642"): "2022-06-07 17:15:50.7",
    ("WBB", "teom_1400ab"): "2017-03-01 20:03:06.85",
}

#: Instruments replaced at the same site by one measuring the same thing:
#: (site, removed, replacement). The two must not be active at once.
SWAPS = [
    ("BUS02", "metone_es642", "metone_es405"),
    ("BUS03", "metone_es642", "metone_es405"),
    ("TRX01", "metone_es642", "metone_es405"),
    ("TRX02", "metone_es642", "metone_es405"),
    ("TRX03", "metone_es642", "metone_es405"),
    ("DBK", "licor_6262", "licor_7000"),
    ("HEB", "licor_6262", "licor_7000"),
    ("RPK", "licor_6262", "licor_7000"),
    ("SUG", "licor_6262", "licor_7000"),
]


def instrument(SID, name):
    return uataq.get_site(SID).instruments[name]


class LastDayFile(filesystem.DataFile):
    """A daily file holding the first and the last row of an instrument's last day."""

    date_slicer = slice(10)
    file_freq = "D"
    ext = "dat"
    rows: list[pd.Timestamp] = []

    def parse(self):
        return pd.DataFrame({"Time_UTC": self.rows, "x": range(len(self.rows))})


@pytest.mark.parametrize(("SID", "name"), sorted(LAST_SAMPLES))
class TestLastDayIsRead:
    """The last day of data is inside the installed window, at every level."""

    def test_removal_is_the_midnight_after_the_last_sample(self, SID, name):
        last = pd.Timestamp(LAST_SAMPLES[SID, name])
        stop = instrument(SID, name).active_range.stop
        assert stop == last.normalize() + pd.Timedelta(days=1)

    def test_last_day_is_not_clipped(self, SID, name):
        inst = instrument(SID, name)
        day = pd.Timestamp(LAST_SAMPLES[SID, name]).normalize()
        clipped = inst.clip_to_active(f"{day:%Y-%m-%d}")
        assert (clipped.start, clipped.stop) == (day, day + pd.Timedelta(days=1))

    def test_last_day_rows_come_back(self, SID, name):
        """The row slice that read_data applies keeps the whole last day."""
        inst = instrument(SID, name)
        last = pd.Timestamp(LAST_SAMPLES[SID, name])
        day = last.normalize()
        LastDayFile.rows = [day, last]
        datafile = LastDayFile(f"/archive/{day:%Y-%m-%d}.dat")
        data = filesystem.parse_datafiles(
            [datafile], inst.clip_to_active(f"{day:%Y-%m-%d}")
        )
        assert data.index.tolist() == [day, last]

    def test_request_starting_on_the_removal_date_raises(self, SID, name):
        inst = instrument(SID, name)
        removal = inst.active_range.stop
        with pytest.raises(errors.InactiveInstrumentError):
            inst.clip_to_active(f"{removal:%Y-%m-%d}")


@pytest.mark.parametrize(("SID", "removed", "replacement"), SWAPS)
def test_swapped_instruments_do_not_overlap(SID, removed, replacement):
    old = instrument(SID, removed).active_range
    new = instrument(SID, replacement).active_range
    assert old.stop <= new.start


#: The MetOne swaps, from horel's raw files: the ES642's last sample (in the
#: month's ``esampler.h5_prior405upgrade``) and the ES405's first row (in the
#: month's plain ``esampler.h5``)
METONE_SWAPS = {
    "BUS02": ("2025-03-13 00:37:10", "2025-03-13 02:38:00"),
    "BUS03": ("2024-12-05 05:47:35", "2024-12-05 06:09:00"),
    "TRX01": ("2025-01-06 18:10:28", "2025-01-06 19:30:00"),
    "TRX02": ("2025-01-06 20:15:50", "2025-01-07 01:03:00"),
    "TRX03": ("2025-01-03 17:15:42", "2025-01-03 20:16:00"),
}


@pytest.mark.parametrize("SID", sorted(METONE_SWAPS))
def test_metone_swap_is_the_es405s_first_row(SID):
    """One instant removes the ES642 and installs the ES405: no gap, no overlap."""
    last, first = (pd.Timestamp(t) for t in METONE_SWAPS[SID])
    es642 = instrument(SID, "metone_es642")
    es405 = instrument(SID, "metone_es405")
    assert es642.active_range.stop == es405.active_range.start == first
    # A read of the ES642's last day keeps its last sample
    assert last < es642.clip_to_active(f"{last:%Y-%m-%d}").stop


def test_every_removal_after_installation():
    for SID in uataq.laboratory.sites:
        for inst in uataq.get_site(SID).instruments:
            start, stop = inst.active_range
            if stop is not None:
                assert start < stop, inst
