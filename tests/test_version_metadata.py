import assemblymcp


def test_package_version_matches_metadata():
    assert assemblymcp.__version__ == assemblymcp._load_package_version()
    assert assemblymcp.__version__ != "0.0.0"
