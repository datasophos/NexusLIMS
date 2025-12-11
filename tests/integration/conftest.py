"""
Integration test fixtures for NexusLIMS.

This module provides pytest fixtures for managing Docker services, test data,
and integration test environments. Fixtures manage the lifecycle of NEMO and
CDCS services, database setup, and cleanup operations.
"""

import subprocess
import time
from pathlib import Path

import pytest
import requests

# Docker compose directory
DOCKER_DIR = Path(__file__).parent / "docker"

# Service URLs
NEMO_URL = "http://localhost:8000"
CDCS_URL = "http://localhost:8080"
FILESERVER_URL = "http://localhost:8081"

# Service health check endpoints
NEMO_HEALTH_URL = f"{NEMO_URL}/"
CDCS_HEALTH_URL = f"{CDCS_URL}/"

# Test data directories (these should match docker-compose volume mounts)
TEST_INSTRUMENT_DATA_DIR = Path("/tmp/nexuslims-test-instrument-data")
TEST_DATA_DIR = Path("/tmp/nexuslims-test-data")


# ============================================================================
# Docker Service Management
# ============================================================================


@pytest.fixture(scope="session")
def docker_services():
    """
    Start Docker services once per test session.

    This fixture manages the lifecycle of all Docker services defined in
    docker-compose.yml including NEMO, CDCS, MongoDB, PostgreSQL, Redis,
    and the fileserver.

    Yields
    ------
    None
        Services are running when fixture yields control to tests

    Notes
    -----
    - Services are started with `docker compose up -d`
    - Health checks wait up to 180 seconds for all services to be ready
    - Services are torn down with `docker compose down -v` after all tests
    - Volumes are removed to ensure clean state for next test run
    - Test data directories are cleaned before starting to ensure clean slate
    """
    import shutil

    # Check test data directories before starting Docker services
    # Fail if they exist to catch cleanup failures from previous runs
    print("\n[*] Checking test data directories...")
    for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
        if test_dir.exists():
            msg = (
                f"\n{'='*70}\n"
                f"ERROR: Test data directory already exists: {test_dir}\n"
                f"\n"
                f"This indicates a previous test run did not clean up properly.\n"
                f"Or there were pre-existing files in the temporary directory.\n"
                f"This could cause test isolation issues and unreliable results.\n"
                f"\n"
                f"To fix this, manually remove the directory:\n"
                f"  rm -rf {test_dir}\n"
                f"\n"
                f"Or remove all test directories:\n"
                f"  rm -rf /tmp/nexuslims-test-*\n"
                f"{'='*70}"
            )
            raise RuntimeError(msg)
        test_dir.mkdir(parents=True, exist_ok=True)
        print(f"[+] Created {test_dir}")

    # Start services
    print("[*] Starting Docker services...")

    # Build docker compose command - use CI override if available
    compose_cmd = ["docker", "compose"]

    # Always use base docker-compose.yml
    compose_cmd.extend(["-f", "docker-compose.yml"])

    # Add CI override if it exists (for pre-built images in CI)
    ci_override = DOCKER_DIR / "docker-compose.ci.yml"
    if ci_override.exists():
        print("[*] Using CI override with pre-built images")
        compose_cmd.extend(["-f", "docker-compose.ci.yml"])

    compose_cmd.extend(["up", "-d"])

    subprocess.run(
        compose_cmd,
        cwd=DOCKER_DIR,
        check=True,
        capture_output=True,
    )

    # Wait for health checks
    max_wait = 180  # 3 minutes
    start_time = time.time()
    nemo_ready = False
    cdcs_ready = False

    print("[*] Waiting for services to be healthy...")

    while time.time() - start_time < max_wait:
        try:
            # Check NEMO
            if not nemo_ready:
                nemo_response = requests.get(NEMO_HEALTH_URL, timeout=2)
                nemo_ready = nemo_response.status_code == 200
                if nemo_ready:
                    print("[+] NEMO service is ready")

            # Check CDCS
            if not cdcs_ready:
                cdcs_response = requests.get(CDCS_HEALTH_URL, timeout=2)
                cdcs_ready = cdcs_response.status_code == 200
                if cdcs_ready:
                    print("[+] CDCS service is ready")

            # All services ready
            if nemo_ready and cdcs_ready:
                print("[+] All services are ready!")
                break

        except (requests.ConnectionError, requests.Timeout):
            pass

        time.sleep(2)
    else:
        # Timeout - collect logs for debugging
        print("[-] Service health checks timed out")
        subprocess.run(
            ["docker", "compose", "logs"],
            cwd=DOCKER_DIR,
        )
        raise RuntimeError(
            f"Services failed to start within {max_wait} seconds. "
            "Check Docker logs above for details."
        )

    yield

    # Cleanup - tear down services and remove volumes
    print("\n[*] Cleaning up Docker services...")
    subprocess.run(
        ["docker", "compose", "down", "-v"],
        cwd=DOCKER_DIR,
        capture_output=True,
    )
    print("[+] Docker services cleaned up")

    # Clean test data directories after stopping Docker services
    # Use try/except to ensure we attempt all cleanups even if one fails
    print("[*] Cleaning test data directories...")
    cleanup_errors = []
    for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
        if test_dir.exists():
            try:
                shutil.rmtree(test_dir)
                print(f"[+] Removed {test_dir}")
            except Exception as e:
                error_msg = f"Failed to remove {test_dir}: {e}"
                print(f"[!] {error_msg}")
                cleanup_errors.append(error_msg)

    if cleanup_errors:
        print("\n[!] WARNING: Some cleanup operations failed:")
        for error in cleanup_errors:
            print(f"    - {error}")
        print("\nYou may need to manually remove directories:")
        print("  rm -rf /tmp/nexuslims-test-*")
    else:
        print("[+] Test environment cleanup complete")


@pytest.fixture(scope="session")
def docker_services_running(docker_services):
    """
    Verify Docker services are running and accessible.

    This is a convenience fixture that depends on docker_services and
    can be used to ensure services are ready before running tests.

    Parameters
    ----------
    docker_services : None
        Depends on docker_services fixture

    Yields
    ------
    dict
        Service URLs and status information
    """
    yield {
        "nemo_url": NEMO_URL,
        "cdcs_url": CDCS_URL,
        "fileserver_url": FILESERVER_URL,
        "status": "ready",
    }


# ============================================================================
# NEMO Integration Fixtures
# ============================================================================


@pytest.fixture
def nemo_url(docker_services) -> str:
    """
    Provide NEMO service URL.

    Parameters
    ----------
    docker_services : None
        Ensures Docker services are running

    Returns
    -------
    str
        Base URL for NEMO API (e.g., "http://localhost:8000")
    """
    return NEMO_URL


@pytest.fixture
def nemo_api_url(nemo_url) -> str:
    """
    Provide NEMO API base URL.

    Parameters
    ----------
    nemo_url : str
        Base NEMO URL

    Returns
    -------
    str
        Full API base URL (e.g., "http://localhost:8000/api/")
    """
    return f"{nemo_url}/api/"


@pytest.fixture
def nemo_client(nemo_api_url, monkeypatch):
    """
    Configure NEMO environment variables for integration tests.

    This fixture configures the NexusLIMS environment to use the test NEMO
    instance. It sets environment variables and refreshes the config.

    Parameters
    ----------
    nemo_api_url : str
        NEMO API URL
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict
        NEMO connection configuration
    """
    # Set environment variables for NEMO configuration
    token_val = "test-api-token"
    monkeypatch.setenv("NX_NEMO_ADDRESS_1", nemo_api_url)
    monkeypatch.setenv("NX_NEMO_TOKEN_1", token_val)
    monkeypatch.setenv("NX_NEMO_TZ_1", "America/Denver")

    # Refresh settings to pick up new environment variables
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    return {
        "url": nemo_api_url,
        "token": f"{token_val}_captain",
        "timezone": "America/Denver",
    }


# NEMO test data fixtures are imported from unit test fixtures
# See tests/unit/fixtures/nemo_mock_data.py for:
# - mock_users_data: User data (captain, professor, ned, commander)
# - mock_tools_data: Tool data (643 Titan, 642 FEI Titan, JEOL 3010, Test Tool, etc.)
# - mock_projects_data: Project data
# - mock_reservations_data: Reservation data with question_data
# - mock_usage_events_data: Usage event data
#
# These fixtures are automatically available via pytest_plugins in tests/conftest.py


# ============================================================================
# CDCS Integration Fixtures
# ============================================================================


@pytest.fixture
def cdcs_url(docker_services) -> str:
    """
    Provide CDCS service URL.

    Parameters
    ----------
    docker_services : None
        Ensures Docker services are running

    Returns
    -------
    str
        Base URL for CDCS (e.g., "http://localhost:8080")
    """
    return CDCS_URL


@pytest.fixture
def cdcs_credentials() -> dict[str, str]:
    """
    Provide CDCS authentication credentials.

    Returns
    -------
    dict[str, str]
        Dictionary with 'username' and 'password' keys
    """
    return {
        "username": "admin",
        "password": "admin",
    }


@pytest.fixture
def cdcs_client(cdcs_url, cdcs_credentials, monkeypatch):
    """
    Configure CDCS environment variables for integration tests.

    This fixture configures the NexusLIMS environment to use the test CDCS
    instance. It sets environment variables and refreshes the config.

    Parameters
    ----------
    cdcs_url : str
        CDCS base URL
    cdcs_credentials : dict
        Authentication credentials
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict
        CDCS connection configuration and utilities
    """
    # Set environment variables for CDCS configuration
    monkeypatch.setenv("NX_CDCS_URL", cdcs_url)
    monkeypatch.setenv("NX_CDCS_USER", cdcs_credentials["username"])
    monkeypatch.setenv("NX_CDCS_PASS", cdcs_credentials["password"])

    # Refresh settings to pick up new environment variables
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    # Track created records for cleanup
    created_records = []

    def register_record(record_id: str):
        """Register a record ID for cleanup after test."""
        created_records.append(record_id)

    yield {
        "url": cdcs_url,
        "username": cdcs_credentials["username"],
        "password": cdcs_credentials["password"],
        "register_record": register_record,
        "created_records": created_records,
    }

    # Cleanup: Delete all records created during the test
    import nexusLIMS.cdcs as cdcs_module

    for record_id in created_records:
        try:
            cdcs_module.delete_record(record_id)
        except Exception as e:
            # Log but don't fail test on cleanup error
            print(f"[!] Failed to cleanup record {record_id}: {e}")


# ============================================================================
# Test Database Fixtures
# ============================================================================


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    """
    Create fresh test database for integration tests.

    This fixture creates a temporary SQLite database and initializes the
    NexusLIMS database schema. The database is isolated for each test and
    automatically cleaned up after the test completes.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory fixture
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Yields
    ------
    Path
        Path to the test database file

    Notes
    -----
    The database is automatically cleaned up by pytest's tmp_path fixture
    """
    import sqlite3

    from nexusLIMS.config import refresh_settings

    # Create database in temporary directory
    db_path = tmp_path / "test_integration.db"

    # Initialize database schema (same approach as unit tests)
    # NOTE: Must create database BEFORE refreshing settings since NX_DB_PATH
    # validation requires the file to exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create instruments table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            instrument_pid TEXT PRIMARY KEY,
            api_url TEXT,
            calendar_name TEXT,
            calendar_url TEXT,
            location TEXT,
            schema_name TEXT,
            property_tag TEXT,
            filestore_path TEXT,
            computer_name TEXT,
            computer_ip TEXT,
            computer_mount TEXT,
            harvester TEXT,
            timezone TEXT
        )
        """
    )

    # Create session_log table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_log (
            session_identifier TEXT,
            instrument TEXT,
            timestamp TEXT,
            event_type TEXT,
            record_status TEXT,
            user TEXT,
            FOREIGN KEY(instrument) REFERENCES instruments(instrument_pid)
        )
        """
    )

    conn.commit()
    conn.close()

    # Now that the database file exists, update the config
    monkeypatch.setenv("NX_DB_PATH", str(db_path))
    refresh_settings()

    yield db_path

    # Cleanup is automatic via tmp_path


@pytest.fixture
def populated_test_database(test_database, mock_tools_data):
    """
    Create test database populated with sample instruments.

    This fixture extends test_database by adding sample instrument entries
    that match the NEMO test tools from shared mock data.

    Parameters
    ----------
    test_database : Path
        Test database from test_database fixture
    mock_tools_data : list[dict]
        Mock NEMO tools data from unit test fixtures

    Yields
    ------
    Path
        Path to the populated test database

    Notes
    -----
    Uses mock_tools_data from tests/unit/fixtures/nemo_mock_data.py to ensure
    consistency between unit and integration tests.
    """
    import sqlite3

    # Build instruments from mock tools data
    # Map tool IDs to instrument configurations
    tool_configs = {
        1: {  # 643 Titan (S)TEM
            "instrument_pid": "FEI-Titan-TEM-643",
            "property_tag": "643",
            "filestore_path": "./643_Titan",
        },
        3: {  # 642 FEI Titan
            "instrument_pid": "FEI-Titan-TEM-642",
            "property_tag": "642",
            "filestore_path": "./642_Titan",
        },
    }

    instruments = []
    for tool in mock_tools_data:
        if tool["id"] in tool_configs:
            config = tool_configs[tool["id"]]
            instruments.append({
                "instrument_pid": config["instrument_pid"],
                "api_url": f"{NEMO_URL}/api/tools/?id={tool['id']}",
                "calendar_name": tool["name"],
                "calendar_url": f"{NEMO_URL}/calendar/{config['property_tag']}-titan/",
                "location": "Building 217",
                "schema_name": tool["name"],
                "property_tag": config["property_tag"],
                "filestore_path": config["filestore_path"],
                "harvester": "nemo",
                "timezone": "America/Denver",
            })

    # Insert instruments into database
    conn = sqlite3.connect(test_database)
    cursor = conn.cursor()

    for inst in instruments:
        cursor.execute(
            """
            INSERT INTO instruments (
                instrument_pid, api_url, calendar_name, calendar_url,
                location, schema_name, property_tag, filestore_path,
                harvester, timezone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inst["instrument_pid"],
                inst["api_url"],
                inst["calendar_name"],
                inst["calendar_url"],
                inst["location"],
                inst["schema_name"],
                inst["property_tag"],
                inst["filestore_path"],
                inst["harvester"],
                inst["timezone"],
            ),
        )

    conn.commit()
    conn.close()

    yield test_database


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_data_dirs(tmp_path, monkeypatch) -> dict[str, Path]:
    """
    Create test data directories for integration tests.

    This fixture creates temporary directories for instrument data and
    NexusLIMS data that match the expected structure. These directories
    are used by the Docker fileserver service.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory fixture
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict[str, Path]
        Dictionary with keys 'instrument_data' and 'nexuslims_data' pointing
        to the created directories
    """
    from nexusLIMS.config import refresh_settings

    # Create directories
    instrument_data_dir = TEST_INSTRUMENT_DATA_DIR
    nexuslims_data_dir = TEST_DATA_DIR

    # Ensure they exist
    instrument_data_dir.mkdir(parents=True, exist_ok=True)
    nexuslims_data_dir.mkdir(parents=True, exist_ok=True)

    # Set environment variables for data paths
    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(instrument_data_dir))
    monkeypatch.setenv("NX_DATA_PATH", str(nexuslims_data_dir))

    # Refresh settings to pick up new environment variables
    refresh_settings()

    yield {
        "instrument_data": instrument_data_dir,
        "nexuslims_data": nexuslims_data_dir,
    }

    # Note: The directories persist across individual tests within the session,
    # but are cleaned at the start and end of each test session by the
    # docker_services fixture to ensure a clean slate for each test run


@pytest.fixture
def sample_microscopy_files():
    """
    Extract sample microscopy data files for testing from unit test archive.

    This fixture extracts test files from test_record_files.tar.gz (shared
    with unit tests) into the instrument data directory. These files can be
    used for testing file discovery, metadata extraction, and record building.

    Yields
    ------
    list[Path]
        List of extracted file paths

    Notes
    -----
    Uses test_record_files.tar.gz from tests/unit/files/, which contains:
    - Titan_TEM/researcher_a/project_alpha/20181113/ (8 .dm3, 2 .ser, 1 .emi)
    - JEOL_TEM/researcher_b/project_beta/20190724/ (multiple .dm3 files)
    - Nexus_Test_Instrument/test_files/ (sample .dm3 files)

    Files are extracted to NX_INSTRUMENT_DATA_PATH and cleaned up after test.
    """
    # Import extraction utilities from unit tests
    from tests.unit.utils import delete_files, extract_files

    # Extract test record files (same as used in unit tests)
    files = extract_files("TEST_RECORD_FILES")

    yield files

    # Cleanup after test
    delete_files("TEST_RECORD_FILES")


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def wait_for_service():
    """
    Provide utility function to wait for service availability.

    Returns
    -------
    callable
        Function that takes (url, timeout) and waits for service to respond
    """

    def _wait(url: str, timeout: int = 30) -> bool:
        """Wait for a service to become available."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    return True
            except (requests.ConnectionError, requests.Timeout):
                pass
            time.sleep(1)
        return False

    return _wait


@pytest.fixture
def integration_test_marker(request):
    """
    Verify test is marked as integration test.

    This fixture can be used to ensure tests are properly marked and to
    provide integration-test-specific setup/teardown.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request fixture

    Raises
    ------
    ValueError
        If test is not marked as integration test
    """
    if "integration" not in [mark.name for mark in request.node.iter_markers()]:
        msg = (
            f"Test {request.node.name} uses integration fixtures but is not "
            "marked with @pytest.mark.integration"
        )
        raise ValueError(msg)
