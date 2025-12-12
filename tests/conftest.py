"""Top-level pytest configuration for test discovery and plugin loading."""

import os
from pathlib import Path

# This MUST be at the top-level conftest.py (not in subdirectories)
pytest_plugins = [
    "tests.unit.fixtures.cdcs_mock_data",
    "tests.unit.fixtures.nemo_mock_data_from_json",
]

# Load environment variables from .env file if it exists
try:
    from dotenv import dotenv_values

    def load_and_filter_env_vars(env_path, source_name):
        """Load and filter environment variables from a given path."""
        print(f"[DEBUG] Loading environment variables from {source_name}")
        env_vars = dotenv_values(env_path)
        filtered_vars = {k: v for k, v in env_vars.items() if k.startswith("NX_TESTS_")}
        print(
            f"[DEBUG] Found {len(filtered_vars)} NX_TESTS_* variables: {list(filtered_vars.keys())}"
        )
        # Only set environment variables if they are not already set
        for k, v in filtered_vars.items():
            if k not in os.environ:
                os.environ[k] = v
            else:
                print(f"[DEBUG] Variable {k} already set in environment, skipping")
        return len(filtered_vars) > 0

    # First check for .env.test in the tests directory (takes precedence)
    test_env_path = Path(__file__).parent / ".env.test"
    if test_env_path.exists():
        load_and_filter_env_vars(test_env_path, str(test_env_path))
    else:
        # Fall back to .env file in the project root
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_and_filter_env_vars(env_path, str(env_path))
        else:
            print("[DEBUG] No .env or .env.test file found")
except ImportError:
    # dotenv not installed, continue without it
    print("[DEBUG] dotenv library not available, skipping environment variable loading")
    pass
