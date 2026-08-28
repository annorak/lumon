from pathlib import Path

import pytest


@pytest.fixture
def graphs_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "graphs"
