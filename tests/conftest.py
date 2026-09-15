from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

settings.register_profile(
    "demo",
    max_examples=200,
    deadline=None,
    derandomize=False,
    database=DirectoryBasedExampleDatabase(
        Path(__file__).resolve().parents[1] / ".hypothesis" / "examples"
    ),
)
settings.register_profile("demo-deep", parent=settings.get_profile("demo"), max_examples=1000)
settings.load_profile("demo")


@pytest.fixture
def graphs_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "graphs"
