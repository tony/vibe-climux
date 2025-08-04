"""Basic tests for climux."""

from app import __version__


def test_version() -> None:
    """Test that version is accessible."""
    assert __version__ == "0.1.0"