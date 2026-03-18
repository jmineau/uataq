"""
Tests for custom exception classes.
"""

import pytest

from uataq import errors


class TestCustomExceptions:
    """Test that all custom exceptions are defined correctly."""

    def test_data_file_initialization_error_exists(self):
        """Test DataFileInitializationError exists and is an Exception."""
        assert issubclass(errors.DataFileInitializationError, Exception)
        with pytest.raises(errors.DataFileInitializationError):
            raise errors.DataFileInitializationError("test message")

    def test_parser_error_exists(self):
        """Test ParserError exists and is an Exception."""
        assert issubclass(errors.ParserError, Exception)
        with pytest.raises(errors.ParserError):
            raise errors.ParserError("test message")

    def test_reader_error_exists(self):
        """Test ReaderError exists and is an Exception."""
        assert issubclass(errors.ReaderError, Exception)
        with pytest.raises(errors.ReaderError):
            raise errors.ReaderError("test message")


class TestInactiveInstrumentError:
    """Test InactiveInstrumentError with custom message."""

    def test_inactive_instrument_error_is_reader_error(self):
        """Test that InactiveInstrumentError is a ReaderError."""
        assert issubclass(errors.InactiveInstrumentError, errors.ReaderError)

    def test_inactive_instrument_error_message(self):
        """Test InactiveInstrumentError generates correct message."""
        instrument = "CRDS"
        err = errors.InactiveInstrumentError(instrument)
        assert "CRDS" in str(err)
        assert "inactive" in str(err)

    def test_inactive_instrument_error_raised(self):
        """Test raising InactiveInstrumentError."""
        with pytest.raises(errors.InactiveInstrumentError) as exc_info:
            raise errors.InactiveInstrumentError("CRDS")
        assert "CRDS" in str(exc_info.value)


class TestInvalidGroupError:
    """Test InvalidGroupError."""

    def test_invalid_group_error_is_reader_error(self):
        """Test that InvalidGroupError is a ReaderError."""
        assert issubclass(errors.InvalidGroupError, errors.ReaderError)

    def test_invalid_group_error_raised(self):
        """Test raising InvalidGroupError."""
        with pytest.raises(errors.InvalidGroupError):
            raise errors.InvalidGroupError("invalid group")


class TestInstrumentNotFoundError:
    """Test InstrumentNotFoundError with custom message."""

    def test_instrument_not_found_error_message(self):
        """Test InstrumentNotFoundError generates correct message."""
        instrument = "CRDS"
        ensemble = "TestEnsemble"
        err = errors.InstrumentNotFoundError(instrument, ensemble)
        assert instrument in str(err)
        assert ensemble in str(err)

    def test_instrument_not_found_error_raised(self):
        """Test raising InstrumentNotFoundError."""
        with pytest.raises(errors.InstrumentNotFoundError) as exc_info:
            raise errors.InstrumentNotFoundError("CRDS", "TestEnsemble")
        assert "CRDS" in str(exc_info.value)
        assert "TestEnsemble" in str(exc_info.value)


class TestPollutantNotMeasuredError:
    """Test PollutantNotMeasured with custom message."""

    def test_pollutant_not_measured_message(self):
        """Test PollutantNotMeasured generates correct message."""
        sid = "WBB"
        pollutant = "CO2"
        err = errors.PollutantNotMeasured(sid, pollutant)
        assert sid in str(err)
        assert pollutant in str(err)

    def test_pollutant_not_measured_raised(self):
        """Test raising PollutantNotMeasured."""
        with pytest.raises(errors.PollutantNotMeasured) as exc_info:
            raise errors.PollutantNotMeasured("WBB", "CO2")
        assert "WBB" in str(exc_info.value)
        assert "CO2" in str(exc_info.value)


class TestErrorHierarchy:
    """Test exception hierarchy relationships."""

    def test_inactive_instrument_error_is_exception(self):
        """Test full hierarchy: InactiveInstrumentError -> ReaderError -> Exception."""
        err = errors.InactiveInstrumentError("test")
        assert isinstance(err, errors.ReaderError)
        assert isinstance(err, Exception)

    def test_invalid_group_error_is_exception(self):
        """Test InvalidGroupError is properly inherited."""
        err = errors.InvalidGroupError("test")
        assert isinstance(err, errors.ReaderError)
        assert isinstance(err, Exception)

    def test_can_catch_as_reader_error(self):
        """Test that InactiveInstrumentError can be caught as ReaderError."""
        with pytest.raises(errors.ReaderError):
            raise errors.InactiveInstrumentError("test")

    def test_can_catch_multiple_reader_errors(self):
        """Test catching multiple types of ReaderErrors."""
        errors_to_test = [
            errors.InactiveInstrumentError("CRDS"),
            errors.InvalidGroupError("test"),
        ]

        for err in errors_to_test:
            with pytest.raises(errors.ReaderError):
                raise err
