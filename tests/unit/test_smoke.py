"""Smoke test: the package imports and reports a version.

Deliberately trivial. Its job is to prove the scaffold works end to end — the package
is installed, importable, and typed — not to test any behaviour, because task 01 ships
no behaviour.
"""

import lumon


def test_package_exposes_version() -> None:
    assert lumon.__version__ == "0.1.0"
