"""
Bad arguments raise an error that names the problem (#199).

Each case was a read that returned the wrong data with no error: a misspelled
keyword, a ``group`` of the wrong type or naming an instrument the site does
not have, an empty ``time_range``.
"""

import pytest

import uataq
from uataq import errors
from uataq.timerange import TimeRange

T400 = "Time_UTC,O3_ppb\n" + "".join(
    f"2024-06-{day:02d} {hour:02d}:00:00,{40 + hour}\n"
    for day in (1, 2)
    for hour in range(24)
)


@pytest.fixture
def wbb_ozone(lin_data_dir):
    """A WBB ozone archive: hourly rows on 1 and 2 June 2024."""
    final = lin_data_dir / "wbb" / "teledyne_t400" / "final"
    final.mkdir(parents=True)
    (final / "2024_06_final.dat").write_text(T400)
    return lin_data_dir


class TestGetObsKeywords:
    """A keyword get_obs does not take raises, so it cannot be silently dropped."""

    @pytest.mark.parametrize("keyword", ["time_rnge", "timerange", "start", "foo"])
    def test_a_misspelled_keyword_raises(self, wbb_ozone, keyword):
        with pytest.raises(TypeError, match=f"'{keyword}'"):
            uataq.get_obs("WBB", "O3", **{keyword: "2024-06-02"})

    def test_the_message_lists_the_keywords_it_takes(self, wbb_ozone):
        with pytest.raises(TypeError, match="time_range"):
            uataq.get_obs("WBB", "O3", timerange="2024-06-02")

    def test_a_mobile_site_raises_too(self):
        with pytest.raises(TypeError, match="'timerange'"):
            uataq.get_site("TRX01").get_obs("CO2", timerange="2024-06-02")

    def test_include_gps_is_still_taken_at_a_fixed_site(self, wbb_ozone):
        obs = uataq.get_obs("WBB", "O3", time_range="2024-06-02", include_gps=False)
        assert len(obs) == 24

    def test_a_level_keeps_its_own_message(self, wbb_ozone):
        with pytest.raises(TypeError, match="always reads the final level"):
            uataq.get_obs("WBB", "O3", lvl="qaqc")


class TestGroupArgument:
    """``group`` is a name, a mapping of instrument name to name, or None."""

    @pytest.mark.parametrize("group", [["horel"], ("horel",), 1, {"horel"}, 1.5])
    def test_a_group_of_the_wrong_type_raises(self, wbb_ozone, group):
        with pytest.raises(TypeError, match="group must be"):
            uataq.get_obs("WBB", "O3", group=group, time_range="2024-06-02")

    def test_a_mapping_value_of_the_wrong_type_raises(self, wbb_ozone):
        with pytest.raises(TypeError, match="group.*teledyne_t400"):
            uataq.get_obs(
                "WBB", "O3", group={"teledyne_t400": ["lin"]}, time_range="2024-06-02"
            )

    def test_a_key_that_is_not_an_instrument_raises(self, wbb_ozone):
        with pytest.raises(ValueError, match="'lgr-ugga'.*not an instrument at WBB"):
            uataq.get_obs(
                "WBB", "O3", group={"lgr-ugga": "horel"}, time_range="2024-06-02"
            )

    def test_the_message_lists_the_instruments_there(self, wbb_ozone):
        with pytest.raises(ValueError, match="lgr_ugga"):
            uataq.read_data("WBB", "lgr_ugga", group={"nope": "lin"})

    def test_a_key_for_an_instrument_not_being_read_is_fine(self, wbb_ozone):
        obs = uataq.get_obs(
            "WBB", "O3", group={"lgr_ugga": "horel"}, time_range="2024-06-02"
        )
        assert len(obs) == 24

    def test_a_mapping_and_none_still_read(self, wbb_ozone):
        by_name = uataq.get_obs(
            "WBB", "O3", group={"teledyne_t400": "lin"}, time_range="2024-06-02"
        )
        auto = uataq.get_obs("WBB", "O3", group=None, time_range="2024-06-02")
        assert by_name.equals(auto)

    def test_a_network_takes_a_key_from_any_of_its_sites(self):
        # lgr_ugga is at WBB, teledyne_t400 at SUG's: each site gets its own key
        net = uataq.Network(
            ["WBB", "SUG"], "CO2", group={"lgr_ugga": "lin", "teledyne_t400": "lin"}
        )
        assert net.sites == ["WBB", "SUG"]

    def test_a_network_rejects_a_key_at_none_of_its_sites(self):
        with pytest.raises(ValueError, match="'lgr-ugga'.*not at any site"):
            uataq.Network(["WBB", "SUG"], "CO2", group={"lgr-ugga": "lin"})

    def test_a_network_rejects_a_group_of_the_wrong_type(self):
        with pytest.raises(TypeError, match="group must be"):
            uataq.Network(["WBB"], "CO2", group=["lin"])


class TestTimeRangeArgument:
    """An empty or reversed time_range raises; only None means everything."""

    @pytest.mark.parametrize("empty", ["", [], (), {}, 0])
    def test_an_empty_time_range_raises(self, empty):
        with pytest.raises(ValueError, match="Invalid time"):
            TimeRange(empty)

    def test_get_obs_with_an_empty_time_range_raises(self, wbb_ozone):
        for empty in ("", []):
            with pytest.raises(ValueError, match="Invalid time"):
                uataq.get_obs("WBB", "O3", time_range=empty)

    def test_none_still_reads_everything(self, wbb_ozone):
        assert len(uataq.get_obs("WBB", "O3", time_range=None)) == 48

    def test_start_after_stop_raises(self, wbb_ozone):
        with pytest.raises(ValueError, match="is after the stop"):
            uataq.get_obs("WBB", "O3", time_range=["2024-06-03", "2024-06-01"])

    @pytest.mark.parametrize(
        "reversed_range",
        [
            ["2024-06-02T12", "2024-06-02T06"],
            ("2024-06-03", "2024-06-01"),
            slice("2024-07-02", "2024-06-01"),
        ],
    )
    def test_every_form_of_a_reversed_range_raises(self, reversed_range):
        with pytest.raises(ValueError, match="after the stop"):
            TimeRange(reversed_range)

    def test_a_start_and_stop_given_as_keywords_are_checked_too(self):
        with pytest.raises(ValueError, match="after the stop"):
            TimeRange(start="2024-06-03", stop="2024-06-01")

    def test_a_one_day_range_and_open_ends_are_fine(self):
        assert TimeRange("2024-06-01").total_seconds == 86400
        assert TimeRange(["2024-06-01", None]).stop is None
        assert TimeRange(slice(None, "2024-06-01")).start is None

    def test_a_time_range_with_start_and_stop_given_raises(self):
        with pytest.raises(ValueError, match="both time_range and start/stop"):
            TimeRange("2024-06", start="2024-06-02")


def test_the_errors_are_not_reader_errors(wbb_ozone):
    """Bad arguments are not 'no data' failures that a loop over sites swallows."""
    with pytest.raises(TypeError) as e:
        uataq.get_obs("WBB", "O3", timerange="2024-06-02")
    assert not isinstance(e.value, errors.ReaderError)
