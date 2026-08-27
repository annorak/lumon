"""Fixtures shared by the test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def graphs_dir() -> Path:
    """Where the hand-written graph fixtures live."""
    return Path(__file__).parent / "fixtures" / "graphs"
