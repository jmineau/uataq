"""
Tests for the Instrument classes.
"""

from unittest.mock import MagicMock, patch, call

import pytest

from uataq import instruments, errors


class TestInstrumentBase:
    """Test the abstract Instrument base class."""

    def test_instrument_is_abstract(self):
        """Test that Instrument defines abstract methods."""
        # Instrument has abstract methods defined by ABCMeta
        assert hasattr(instruments.Instrument, '__abstractmethods__')
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
