"""Test basic functionality of uataq."""

import uataq


def test_version():
    """Test that version is defined."""
    assert hasattr(uataq, "__version__")
    assert isinstance(uataq.__version__, str)


def test_author():
    """Test that author is defined."""
    assert hasattr(uataq, "__author__")
    assert isinstance(uataq.__author__, str)


def test_email():
    """Test that email is defined."""
    assert hasattr(uataq, "__email__")
    assert isinstance(uataq.__email__, str)
