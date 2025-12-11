"""Top-level pytest configuration for test discovery and plugin loading."""

# This MUST be at the top-level conftest.py (not in subdirectories)
pytest_plugins = [
    "tests.unit.fixtures.cdcs_mock_data",
    "tests.unit.fixtures.nemo_mock_data_from_json",
]
