# ruff: noqa: T201
"""Top-level pytest configuration for test discovery and plugin loading."""

import os
import tempfile
from pathlib import Path

# ============================================================================
# CRITICAL: Enable test mode BEFORE any nexusLIMS imports
# ============================================================================
# This disables Pydantic validation in nexusLIMS.config, allowing tests to
# set up the environment at runtime without validation errors during import
os.environ["NX_TEST_MODE"] = "true"

# Ensure we never create a repo-root SQLite file from relative NX_DB_PATH values
_DEFAULT_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="nexuslims-tests-"))
_DEFAULT_TEST_DB_PATH = _DEFAULT_TEST_DB_DIR / "test.db"
_DEFAULT_TEST_DB_SET = False
if "NX_DB_PATH" not in os.environ or not Path(os.environ["NX_DB_PATH"]).is_absolute():
    os.environ["NX_DB_PATH"] = str(_DEFAULT_TEST_DB_PATH)
    _DEFAULT_TEST_DB_SET = True


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Clean up the temp NX_DB_PATH used for tests."""
    if not _DEFAULT_TEST_DB_SET:
        return

    try:
        if _DEFAULT_TEST_DB_PATH.exists():
            _DEFAULT_TEST_DB_PATH.unlink()
        _DEFAULT_TEST_DB_DIR.rmdir()
    except OSError:
        # Best-effort cleanup; ignore if the DB is still open or the dir isn't empty.
        pass


# ============================================================================
# Shared Database Initialization
# ============================================================================


def create_test_database(db_path: Path) -> None:
    """
    Create a test database using SQLModel.

    This ensures the schema matches the actual model definitions and is used
    by both unit and integration tests to maintain consistency.

    Parameters
    ----------
    db_path : Path
        Path where the database should be created
    """
    from sqlmodel import SQLModel, create_engine

    # Import all models to register them with SQLModel metadata
    from nexusLIMS.db.models import (  # noqa: F401
        Instrument,
        SessionLog,
        UploadLog,
    )

    # Always recreate to ensure latest schema
    if db_path.exists():
        db_path.unlink()

    # Create engine and tables
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()


# This MUST be at the top-level conftest.py (not in subdirectories)
# Include unit test fixtures in pytest_plugins to make them available to both
# unit and integration tests. This allows fixtures like multi_signal_test_files
# to be reused across the entire test suite.
pytest_plugins = [
    "tests.unit.fixtures.cdcs_mock_data",
    "tests.unit.fixtures.nemo_mock_data_from_json",
    "tests.unit.fixtures.multi_signal_test_files",
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
            f"[DEBUG] Found {len(filtered_vars)} "
            f"NX_TESTS_* variables: {list(filtered_vars.keys())}"
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
