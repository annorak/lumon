import lumon


def test_package_exposes_version() -> None:
    assert lumon.__version__ == "0.1.0"
