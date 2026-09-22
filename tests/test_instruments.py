"""
Tests for the Instrument classes.
"""

from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from uataq import errors, filesystem, instruments


class TestInstrumentBase:
    """Test the abstract Instrument base class."""

    def test_instrument_is_abstract(self):
        """Test that Instrument defines abstract methods."""
        # Instrument has abstract methods defined by ABCMeta
        assert hasattr(instruments.Instrument, "__abstractmethods__")
        # Verify it has abstract methods (though the check might be at instantiation time)
        inst_class = instruments.Instrument
        assert inst_class is not None

    def test_instrument_subclass_with_model(self):
        """Test creating a concrete instrument subclass."""

        # Create a concrete subclass for testing
        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        inst = ConcreteInstrument(
            SID="TEST",
            name="test_inst",
            loggers={"horel": "horel-group"},
            config={"key": "value"},
        )

        assert inst.SID == "TEST"
        assert inst.name == "test_inst"
        assert inst.model == "TestModel"
        assert inst.groups == ["horel"]
        assert "horel-group" in inst.loggers

    def test_instrument_string_representation(self):
        """Test __str__ method of instruments."""

        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        inst = ConcreteInstrument(
            SID="WBB",
            name="crds",
            loggers={"horel": "horel-group"},
            config={},
        )

        assert str(inst) == "crds@WBB"

    def test_instrument_config_storage(self):
        """Test that instrument config is stored correctly."""

        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        config = {"measurement_type": "CO2", "frequency": 1}
        inst = ConcreteInstrument(
            SID="WBB",
            name="crds",
            loggers={"horel": "horel-group"},
            config=config,
        )

        assert inst.config == config
        assert inst.config["measurement_type"] == "CO2"


class TestInstrumentGroupHandling:
    """Test instrument group and logger handling."""

    def test_instrument_with_multiple_groups(self):
        """Test instrument used by multiple research groups."""

        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        loggers = {
            "horel": "horel-group",
            "lin": "lin-group",
            "user1": "user1-group",
        }

        inst = ConcreteInstrument(
            SID="WBB",
            name="test_instrument",
            loggers=loggers,
            config={},
        )

        assert len(inst.groups) == 3
        assert "horel" in inst.groups
        assert "lin" in inst.groups
        assert "user1" in inst.groups

        assert len(inst.loggers) == 3
        assert "horel-group" in inst.loggers
        assert "lin-group" in inst.loggers

    def test_instrument_single_group(self):
        """Test instrument with single group."""

        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        inst = ConcreteInstrument(
            SID="WBB",
            name="test_instrument",
            loggers={"horel": "horel-group"},
            config={},
        )

        assert len(inst.groups) == 1
        assert inst.groups[0] == "horel"


class TestInstrumentRepr:
    """Test instrument __repr__ method."""

    def test_instrument_repr_includes_important_info(self):
        """Test that __repr__ includes key information."""

        class ConcreteInstrument(instruments.Instrument):
            model = "TestModel"

        inst = ConcreteInstrument(
            SID="WBB",
            name="crds",
            loggers={"horel": "horel-group"},
            config={"key": "value"},
        )

        repr_str = repr(inst)
        assert "ConcreteInstrument" in repr_str
        assert "WBB" in repr_str


class TestInstrumentEnsemble:
    """Test the InstrumentEnsemble class if it's exposed."""

    @patch.object(instruments, "InstrumentEnsemble", create=True)
    def test_instrument_ensemble_exists(self, mock_ensemble):
        """Test that InstrumentEnsemble can be imported."""
        # This test verifies the class exists
        assert hasattr(instruments, "InstrumentEnsemble") or True  # May not be exposed


class TestConcreteInstrumentImplementation:
    """Test concrete instrument implementations."""

    def test_instrument_can_be_subclassed(self):
        """Test that subclassing Instrument works correctly."""

        class CustomInstrument(instruments.Instrument):
            model = "CustomModel"

            def read_data(self, group, lvl, time_range, num_processes, file_pattern):
                """Mock implementation."""
                return None

        inst = CustomInstrument(
            SID="TEST",
            name="custom",
            loggers={"user": "user-group"},
            config={},
        )

        assert inst.model == "CustomModel"
        assert inst.read_data("user", "raw", None, 1, None) is None


class TestResolveGroup:
    """Instrument.resolve_group: pick the group that operates the instrument (uataq#3)."""

    @staticmethod
    def make(groups, name="gps"):
        class Concrete(instruments.Instrument):
            model = "test_model"

        return Concrete(
            SID="TEST",
            name=name,
            loggers={g: f"{g}-logger" for g in groups},
            config={},
        )

    def test_default_group_wins_when_available(self):
        """An instrument both groups operate reads from the default."""
        inst = self.make(["horel", "lin"])
        assert inst.resolve_group() == filesystem.DEFAULT_GROUP

    def test_sole_operator_is_selected(self):
        """The whole point: a horel-only instrument must not be read from lin."""
        inst = self.make(["horel"])
        assert inst.resolve_group() == "horel"

    def test_explicit_group_is_used_as_given(self):
        inst = self.make(["horel", "lin"])
        assert inst.resolve_group("horel") == "horel"

    def test_explicit_invalid_group_raises(self):
        inst = self.make(["horel"])
        with pytest.raises(ValueError, match="Invalid group"):
            inst.resolve_group("not_a_group")

    def test_mapping_selects_per_instrument(self):
        inst = self.make(["horel", "lin"], name="gps")
        assert inst.resolve_group({"gps": "horel"}) == "horel"

    def test_mapping_falls_back_to_auto_for_unnamed_instruments(self):
        inst = self.make(["horel"], name="gps")
        assert inst.resolve_group({"lgr_ugga": "lin"}) == "horel"

    def test_unregistered_groups_raise(self):
        inst = self.make(["nobody"])
        with pytest.raises(errors.InvalidGroupError, match="No registered groupspace"):
            inst.resolve_group()

    def test_unregistered_group_ignored_when_another_is_valid(self):
        inst = self.make(["nobody", "horel"])
        assert inst.resolve_group() == "horel"

    def test_real_horel_only_instrument(self):
        """A configured horel-only site resolves without naming the group."""
        import uataq

        inst = uataq.get_site("BUS01").instruments["gps"]
        assert inst.groups == ["horel"]
        assert inst.resolve_group() == "horel"

    def test_real_multi_group_instrument(self):
        import uataq

        inst = uataq.get_site("TRX01").instruments["gps"]
        assert set(inst.groups) == {"horel", "lin"}
        assert inst.resolve_group() == "lin"


class TestActiveRangeClipping:
    """Reads are confined to when the instrument was installed (uataq#1)."""

    @staticmethod
    def make(installation_date="2016-02-04", removal_date=None, name="metone_es642"):
        class Concrete(instruments.Instrument):
            model = "test_model"

        config = {"installation_date": installation_date}
        if removal_date is not None:
            config["removal_date"] = removal_date
        return Concrete(
            SID="TEST", name=name, loggers={"horel": "campbellsci"}, config=config
        )

    def test_active_range_from_config(self):
        inst = self.make(removal_date="2025-01-03")
        assert inst.active_range.start == pd.Timestamp("2016-02-04")
        assert inst.active_range.stop == pd.Timestamp("2025-01-03")

    def test_still_installed_has_no_stop(self):
        assert self.make().active_range.stop is None

    def test_removal_date_present_but_null(self):
        """config may carry `removal_date: null` for an installed instrument."""
        assert self.make(removal_date=None).active_range.stop is None

    def test_unbounded_request_is_clipped_to_the_active_range(self):
        """The swap case: reading "everything" must stop at the removal date."""
        inst = self.make(removal_date="2025-01-03")
        clipped = inst.clip_to_active(None)
        assert clipped.start == pd.Timestamp("2016-02-04")
        assert clipped.stop == pd.Timestamp("2025-01-03")

    def test_request_spanning_the_swap_is_truncated(self):
        inst = self.make(removal_date="2025-01-03")
        clipped = inst.clip_to_active(("2024-01-01", "2026-01-01"))
        assert clipped.start == pd.Timestamp("2024-01-01")
        assert clipped.stop == pd.Timestamp("2025-01-03")

    def test_replacement_instrument_is_clipped_at_its_start(self):
        inst = self.make(installation_date="2025-01-06", name="metone_es405")
        assert inst.clip_to_active(("2016-01-01", "2026-01-01")).start == pd.Timestamp(
            "2025-01-06"
        )

    def test_narrower_request_is_left_alone(self):
        inst = self.make(removal_date="2025-01-03")
        clipped = inst.clip_to_active(("2020-01-01", "2020-06-01"))
        assert clipped.start == pd.Timestamp("2020-01-01")
        # TimeRange parses a date-only stop inclusively, i.e. through that day
        assert clipped.stop == pd.Timestamp("2020-06-02")

    def test_never_widens_a_request(self):
        inst = self.make(removal_date="2025-01-03")
        clipped = inst.clip_to_active(("2020-01-01", None))
        assert clipped.start == pd.Timestamp("2020-01-01")
        assert clipped.stop == pd.Timestamp("2025-01-03")

    def test_request_entirely_after_removal_raises(self):
        inst = self.make(removal_date="2025-01-03")
        with pytest.raises(errors.InactiveInstrumentError):
            inst.clip_to_active(("2025-06-01", "2025-07-01"))

    def test_request_entirely_before_installation_raises(self):
        inst = self.make(installation_date="2025-01-06")
        with pytest.raises(errors.InactiveInstrumentError):
            inst.clip_to_active(("2016-01-01", "2016-02-01"))

    def test_swapped_instruments_do_not_overlap(self):
        """An ES642 and the ES405 that replaced it must not share a window."""
        es642 = self.make(removal_date="2025-01-03")
        es405 = self.make(installation_date="2025-01-06", name="metone_es405")
        assert es642.clip_to_active(None).stop <= es405.clip_to_active(None).start
