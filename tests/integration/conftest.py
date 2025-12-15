"""
Integration test fixtures for NexusLIMS.

This module provides pytest fixtures for managing Docker services, test data,
and integration test environments. Fixtures manage the lifecycle of NEMO and
CDCS services, database setup, and cleanup operations.
"""

import subprocess
import time
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import requests

if TYPE_CHECKING:
    # Import statements or code that should only be evaluated during type checking
    # This code will be ignored at runtime
    from nexusLIMS.harvesters.nemo.connector import NemoConnector


# Docker compose directory
DOCKER_DIR = Path(__file__).parent / "docker"

# Service URLs (base URLs without /api/)
NEMO_BASE_URL = "http://nemo.localhost"
NEMO2_BASE_URL = (
    "http://nemo2.localhost"  # Second NEMO instance for multi-instance testing
)
CDCS_URL = "http://cdcs.localhost"
FILESERVER_URL = "http://fileserver.localhost"
MAILPIT_URL = "http://mailpit.localhost"
MAILPIT_SMTP_HOST = "localhost"
MAILPIT_SMTP_PORT = 1025
MAILPIT_SMTP_USER = "test"
MAILPIT_SMTP_PASS = "testpass"

# NEMO API URLs (base URLs + /api/)
NEMO_URL = f"{NEMO_BASE_URL}/api/"
NEMO2_URL = f"{NEMO2_BASE_URL}/api/"

# Service health check endpoints
NEMO_HEALTH_URL = f"{NEMO_BASE_URL}/"
CDCS_HEALTH_URL = f"{CDCS_URL}/"
MAILPIT_HEALTH_URL = f"{MAILPIT_URL}/"

# Test data directories (these should match docker-compose volume mounts)
TEST_INSTRUMENT_DATA_DIR = Path("/tmp/nexuslims-test-instrument-data")
TEST_DATA_DIR = Path("/tmp/nexuslims-test-data")


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.

    This hook ensures that the directories expected by the root .env file
    exist before any module imports occur. This is necessary because some
    NexusLIMS modules access settings at import time, which triggers
    Pydantic validation of directory paths.

    The root .env file typically points to /tmp/nx_instrument_data and
    /tmp/nx_data for development, but integration tests use different paths.
    We create both sets of directories to ensure tests can run regardless
    of which .env file is loaded.
    """
    from dotenv import dotenv_values

    # Read directories from root .env file (for import-time validation)
    root_env_path = Path(__file__).parents[2] / ".env"
    root_env_dirs = []

    if root_env_path.exists():
        env_vars = dotenv_values(root_env_path)
        if "NX_INSTRUMENT_DATA_PATH" in env_vars:
            root_env_dirs.append(Path(env_vars["NX_INSTRUMENT_DATA_PATH"]))
        if "NX_DATA_PATH" in env_vars:
            root_env_dirs.append(Path(env_vars["NX_DATA_PATH"]))

    # Create test directories (for actual test execution)
    test_dirs = [
        TEST_INSTRUMENT_DATA_DIR,
        TEST_DATA_DIR,
    ]

    # Ensure all directories exist
    for dir_path in root_env_dirs + test_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Docker Service Management
# ============================================================================


def start_fileserver():
    """
    Start a host-based fileserver to serve test files.

    This avoids Docker volume mount issues on macOS by running the fileserver
    directly on the host machine instead of in a Docker container.

    Returns
    -------
    ThreadingHTTPServer
        The running HTTP server instance. Call shutdown() and server_close() to stop.

    Notes
    -----
    - Fileserver runs on port 8081
    - Serves files from TEST_INSTRUMENT_DATA_DIR and TEST_DATA_DIR
    - Uses Python's built-in HTTP server with custom routing
    - Server runs in a daemon thread
    """
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import unquote, urlparse

    class TestFileHandler(SimpleHTTPRequestHandler):
        """Custom handler that serves files from test directories."""

        def __init__(self, *args, **kwargs):
            self.instrument_data_dir = TEST_INSTRUMENT_DATA_DIR
            self.nexuslims_data_dir = TEST_DATA_DIR
            super().__init__(*args, **kwargs)

        def translate_path(self, path):
            """Translate URL path to filesystem path, handling our test directories."""
            # Decode URL and normalize path
            path = unquote(path)
            path = urlparse(path).path
            path = path.lstrip("/")

            # Handle instrument-data requests
            if path.startswith("instrument-data/"):
                relative_path = path[len("instrument-data/") :]
                full_path = self.instrument_data_dir / relative_path

            # Handle data requests
            elif path.startswith("data/"):
                relative_path = path[len("data/") :]
                full_path = self.nexuslims_data_dir / relative_path

            else:
                # Reject any other paths - only serve from our two test directories
                # Return a non-existent path to trigger 404
                return "/dev/null/nonexistent"

            return str(full_path)

        def do_GET(self):
            """Handle GET requests with CORS headers."""
            # Call parent method to handle the actual file serving first
            super().do_GET()

            # Then add CORS headers to the response
            # Note: We need to override end_headers to add our custom headers

        def end_headers(self):
            """Override to add CORS and cache control headers."""
            # Add CORS headers
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")

            # Disable caching
            self.send_header(
                "Cache-Control",
                "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0",
            )
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

            # Call parent method to finalize headers
            super().end_headers()

        def log_message(self, format, *args):
            """Override to reduce logging verbosity."""
            # Only log errors, not every request
            if "404" in format or "500" in format:
                import sys

                sys.stderr.write(
                    "[%s] %s\n" % (self.log_date_time_string(), format % args)
                )

    # Create and start the server
    server_address = ("", 8081)
    httpd = ThreadingHTTPServer(server_address, TestFileHandler)

    print(f"[+] Host fileserver started successfully on port 8081")
    print(f"[+] Serving instrument data from: {TEST_INSTRUMENT_DATA_DIR}")
    print(f"[+] Serving NexusLIMS data from: {TEST_DATA_DIR}")

    # Start server in a separate thread
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    return httpd


@pytest.fixture(scope="session")
def host_fileserver():
    """
    Pytest fixture for host-based fileserver.

    Yields
    ------
    None
        Fileserver is running when fixture yields control to tests
    """
    httpd = start_fileserver()

    try:
        yield
    finally:
        # Clean up server
        print("[*] Stopping host fileserver...")
        httpd.shutdown()
        httpd.server_close()
        print("[+] Host fileserver stopped successfully")


@pytest.fixture(scope="session")
def docker_services(request, host_fileserver):
    """
    Start Docker services once per test session.

    This fixture manages the lifecycle of all Docker services defined in
    docker-compose.yml including NEMO, CDCS, MongoDB, PostgreSQL, Redis.
    Note that the fileserver now runs on the host machine (via host_fileserver fixture)
    to avoid Docker volume mount issues on macOS.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object to access configuration
    host_fileserver : None
        Dependency on host_fileserver fixture to ensure it's running

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
    - Set NX_TESTS_KEEP_DOCKER_RUNNING=1 environment variable to skip teardown for debugging
    """
    import os
    import shutil

    # Check if we should keep Docker services running for debugging
    keep_running = os.environ.get("NX_TESTS_KEEP_DOCKER_RUNNING", "0") == "1"
    # Debug: Show keep_running status before yield (during test execution)
    print(f"\n[DEBUG] keep_running status before tests: {keep_running}")

    # Always clean test data directories to ensure clean state
    print("\n[*] Checking test data directories...")
    for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
        if test_dir.exists():
            print(f"[!] WARNING: Test data directory already exists: {test_dir}")
            print(
                f"[!] This may indicate a previous test run did not clean up properly"
            )
            print(f"[!] Removing directory to ensure clean test environment...")
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True, exist_ok=True)
        print(f"[+] Created {test_dir}")

    # Check if services are already running
    max_wait = 1  # Short timeout for checking existing services
    start_time = time.time()
    nemo_ready = False
    cdcs_ready = False
    mailpit_ready = False

    print("[*] Checking if Docker services are already running...")

    while time.time() - start_time < max_wait:
        try:
            # Check NEMO
            if not nemo_ready:
                nemo_response = requests.get(NEMO_HEALTH_URL, timeout=2)
                nemo_ready = nemo_response.status_code == HTTPStatus.OK
                if nemo_ready:
                    print("[+] NEMO service is ready")

            # Check CDCS
            if not cdcs_ready:
                cdcs_response = requests.get(CDCS_HEALTH_URL, timeout=2)
                cdcs_ready = cdcs_response.status_code == HTTPStatus.OK
                if cdcs_ready:
                    print("[+] CDCS service is ready")

            # Check Mailpit
            if not mailpit_ready:
                mailpit_response = requests.get(MAILPIT_HEALTH_URL, timeout=2)
                mailpit_ready = mailpit_response.status_code == HTTPStatus.OK
                if mailpit_ready:
                    print("[+] Mailpit service is ready")

            # All services ready
            if nemo_ready and cdcs_ready and mailpit_ready:
                print("[+] All services are ready!")
                break

        except (requests.ConnectionError, requests.Timeout):
            pass

        time.sleep(1)

    # If services are not running, start them
    if not (nemo_ready and cdcs_ready and mailpit_ready):
        print("[*] Docker services not running - starting them now...")

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
        max_wait = 60  # 1 minute
        start_time = time.time()
        nemo_ready = False
        cdcs_ready = False
        mailpit_ready = False

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

                # Check Mailpit
                if not mailpit_ready:
                    mailpit_response = requests.get(MAILPIT_HEALTH_URL, timeout=2)
                    mailpit_ready = mailpit_response.status_code == 200
                    if mailpit_ready:
                        print("[+] Mailpit service is ready")

                # All services ready
                if nemo_ready and cdcs_ready and mailpit_ready:
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
    # Debug: Show keep_running status after yield (during cleanup)
    print(f"\n[DEBUG] keep_running status during cleanup: {keep_running}")

    # Cleanup logic based on keep_running flag
    if keep_running:
        print(
            "\n[*] NX_TESTS_KEEP_DOCKER_RUNNING=1: Keeping Docker services running for debugging"
        )
        print("[!] Remember to manually clean up with: docker compose down -v")
        print(
            "\n[*] NX_TESTS_KEEP_DOCKER_RUNNING=1: Keeping test data directories for debugging"
        )
        print(f"[!] Test instrument data: {TEST_INSTRUMENT_DATA_DIR}")
        print(f"[!] Test NexusLIMS data: {TEST_DATA_DIR}")
    else:
        # Always stop services (regardless of who started them)
        print("\n[*] Cleaning up Docker services...")
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=DOCKER_DIR,
            capture_output=True,
        )
        print("[+] Docker services cleaned up")

        # Clean test data directories
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
        "mailpit_url": MAILPIT_URL,
        "mailpit_smtp_host": MAILPIT_SMTP_HOST,
        "mailpit_smtp_port": MAILPIT_SMTP_PORT,
        "status": "ready",
    }


# ============================================================================
# Mailpit Integration Fixtures
# ============================================================================


@pytest.fixture
def mailpit_client(docker_services, monkeypatch):
    """
    Provide Mailpit client for email testing.

    This fixture provides utilities to interact with the Mailpit SMTP testing
    server, including checking for received emails and clearing the mailbox.
    It also configures the NX_EMAIL_* environment variables to point to the
    Mailpit SMTP server.

    Parameters
    ----------
    docker_services : None
        Ensures Docker services are running
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict
        Mailpit client configuration and utilities with keys:
        - 'smtp_host': SMTP server host
        - 'smtp_port': SMTP server port
        - 'smtp_user': SMTP username for authentication
        - 'smtp_password': SMTP password for authentication
        - 'api_url': Mailpit API base URL
        - 'web_url': Mailpit web UI URL
        - 'get_messages': Function to retrieve all messages
        - 'clear_messages': Function to delete all messages
        - 'search_messages': Function to search messages by subject/recipient

    Examples
    --------
    >>> def test_email_sending(mailpit_client):
    ...     # Clear mailbox before test
    ...     mailpit_client['clear_messages']()
    ...
    ...     # Send email via your code
    ...     send_email(to='test@example.com', subject='Test')
    ...
    ...     # Check email was received
    ...     messages = mailpit_client['get_messages']()
    ...     assert len(messages) == 1
    ...     assert messages[0]['Subject'] == 'Test'
    """
    # Configure email environment variables to use Mailpit
    monkeypatch.setenv("NX_EMAIL_SMTP_HOST", MAILPIT_SMTP_HOST)
    monkeypatch.setenv("NX_EMAIL_SMTP_PORT", str(MAILPIT_SMTP_PORT))
    monkeypatch.setenv("NX_EMAIL_SMTP_USERNAME", MAILPIT_SMTP_USER)
    monkeypatch.setenv("NX_EMAIL_SMTP_PASSWORD", MAILPIT_SMTP_PASS)
    monkeypatch.setenv("NX_EMAIL_SENDER", "nexuslims-test@localhost.net")
    monkeypatch.setenv(
        "NX_EMAIL_RECIPIENTS", "admin@localhost.net,errors@localhost.net"
    )
    monkeypatch.setenv("NX_EMAIL_USE_TLS", "false")  # Mailpit doesn't use TLS

    # Refresh settings to pick up new environment variables
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    def get_messages():
        """Get all messages from Mailpit."""
        response = requests.get(f"{MAILPIT_URL}/api/v1/messages", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("messages", [])

    def get_message(message_id):
        """
        Get a specific message by ID from Mailpit.

        Parameters
        ----------
        message_id : str
            The message ID to retrieve

        Returns
        -------
        dict
            The complete message object including headers, body, and attachments

        Raises
        ------
        requests.HTTPError
            If the message is not found (404) or other HTTP errors occur
        """
        response = requests.get(f"{MAILPIT_URL}/api/v1/message/{message_id}", timeout=5)
        response.raise_for_status()
        return response.json()

    def clear_messages():
        """Delete all messages from Mailpit."""
        requests.delete(f"{MAILPIT_URL}/api/v1/messages", timeout=5)

    def search_messages(subject=None, to=None, sender=None):
        """
        Search for messages matching criteria.

        Parameters
        ----------
        subject : str, optional
            Subject line to search for (partial match)
        to : str, optional
            Recipient email address to search for
        sender : str, optional
            Sender email address to search for

        Returns
        -------
        list
            List of matching messages
        """
        messages = get_messages()
        results = []

        for msg in messages:
            # Mailpit API structure: msg.Subject, msg.To, msg.From (not nested in Content.Headers)
            # Check subject
            if subject is not None:
                msg_subject = msg.get("Subject", "")
                if subject.lower() not in msg_subject.lower():
                    continue

            # Check recipient
            if to is not None:
                msg_to_list = msg.get("To", [])
                # msg_to_list is a list of {"Address": "email@domain.com", "Name": "..."} dicts
                if not any(
                    to.lower() in recipient.get("Address", "").lower()
                    for recipient in msg_to_list
                ):
                    continue

            # Check sender
            if sender is not None:
                msg_from = msg.get("From", {}).get("Address", "")
                if sender.lower() not in msg_from.lower():
                    continue

            results.append(msg)

        return results

    # Clear mailbox before each test
    clear_messages()

    return {
        "smtp_host": MAILPIT_SMTP_HOST,
        "smtp_port": MAILPIT_SMTP_PORT,
        "smtp_user": MAILPIT_SMTP_USER,
        "smtp_password": MAILPIT_SMTP_PASS,
        "api_url": f"{MAILPIT_URL}/api",
        "web_url": MAILPIT_URL,
        "get_messages": get_messages,
        "get_message": get_message,
        "clear_messages": clear_messages,
        "search_messages": search_messages,
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
        Base URL for NEMO (e.g., "http://nemo.localhost")
    """
    return NEMO_BASE_URL


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
        Full API base URL (e.g., "http://nemo.localhost/api/")
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
    token_val = "test-api-token_captain"
    monkeypatch.setenv("NX_NEMO_ADDRESS_1", nemo_api_url)
    monkeypatch.setenv("NX_NEMO_TOKEN_1", token_val)
    monkeypatch.setenv("NX_NEMO_TZ_1", "America/Denver")

    # Refresh settings to pick up new environment variables
    from nexusLIMS.config import refresh_settings

    refresh_settings()

    return {
        "url": nemo_api_url,
        "token": token_val,
        "timezone": "America/Denver",
    }


@pytest.fixture
def nemo_connector(
    nemo_client, populated_test_database, monkeypatch
) -> "NemoConnector":
    """
    Provide a NemoConnector instance for integration tests.

    This fixture creates a NemoConnector instance using the configured
    NEMO client settings, avoiding repeated connector creation in tests.
    It patches the instrument_db to use the test database.

    Parameters
    ----------
    nemo_client : dict
        NEMO connection configuration from nemo_client fixture
    populated_test_database : Path
        Ensures the test database is populated before creating connector
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture for patching

    Returns
    -------
    NemoConnector
        Configured NemoConnector instance with test database
    """
    from nexusLIMS import instruments
    from nexusLIMS.harvesters.nemo import connector

    # Reload instrument_db from the test database
    test_instrument_db = instruments._get_instrument_db(db_path=populated_test_database)

    # Patch the instrument_db in both the instruments module and the connector module
    # This is necessary because the connector imports instrument_db at module level
    monkeypatch.setattr(connector, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)

    return connector.NemoConnector(
        base_url=nemo_client["url"],
        token=nemo_client["token"],
    )


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


@pytest.fixture(scope="session")
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
        Base URL for CDCS (e.g., "http://cdcs.localhost")
    """
    return CDCS_URL


@pytest.fixture(scope="session")
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
def safe_refresh_settings(monkeypatch, tmp_path):
    """
    Provide a helper to safely refresh settings with valid required paths.

    This fixture is useful for tests that need to call refresh_settings() with
    custom environment variables (e.g., to test invalid credentials) but still
    need to satisfy the validation requirements for path settings.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture
    tmp_path : Path
        Pytest temporary path fixture

    Returns
    -------
    callable
        A function that accepts **env_vars keyword arguments and safely
        refreshes settings with those variables plus valid paths

    Examples
    --------
    >>> def test_invalid_credentials(safe_refresh_settings):
    ...     safe_refresh_settings(
    ...         NX_CDCS_USER="invalid",
    ...         NX_CDCS_PASS="invalid",
    ...     )
    """
    from nexusLIMS.config import refresh_settings

    def _refresh(**env_vars):
        """Refresh settings with provided env vars plus valid required paths."""
        # Create temporary database file
        db_path = tmp_path / "test.db"
        db_path.touch()

        # Create temporary directories
        instrument_data_path = tmp_path / "instrument"
        data_path = tmp_path / "data"
        instrument_data_path.mkdir(exist_ok=True)
        data_path.mkdir(exist_ok=True)

        # Set required path variables if not provided
        if "NX_DB_PATH" not in env_vars:
            monkeypatch.setenv("NX_DB_PATH", str(db_path))
        if "NX_INSTRUMENT_DATA_PATH" not in env_vars:
            monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(instrument_data_path))
        if "NX_DATA_PATH" not in env_vars:
            monkeypatch.setenv("NX_DATA_PATH", str(data_path))

        # Set all provided environment variables
        for key, value in env_vars.items():
            monkeypatch.setenv(key, str(value))

        # Refresh settings
        refresh_settings()

    return _refresh


def setup_cdcs_environment(cdcs_url, cdcs_credentials):
    """
    Set up CDCS environment variables and refresh settings.

    This is a helper function used by both cdcs_client and cdcs_test_record
    fixtures to configure the CDCS environment.

    Parameters
    ----------
    cdcs_url : str
        CDCS base URL
    cdcs_credentials : dict
        Authentication credentials with 'username' and 'password' keys

    Returns
    -------
    None
        Environment variables are set as a side effect
    """
    import os

    os.environ["NX_CDCS_URL"] = cdcs_url
    os.environ["NX_CDCS_USER"] = cdcs_credentials["username"]
    os.environ["NX_CDCS_PASS"] = cdcs_credentials["password"]

    from nexusLIMS.config import refresh_settings

    refresh_settings()


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
    from nexusLIMS.config import refresh_settings

    # Use monkeypatch for function-scoped environment setup
    monkeypatch.setenv("NX_CDCS_URL", cdcs_url)
    monkeypatch.setenv("NX_CDCS_USER", cdcs_credentials["username"])
    monkeypatch.setenv("NX_CDCS_PASS", cdcs_credentials["password"])

    # Ensure the database file exists (Settings validation requires it)
    # Get the current NX_DB_PATH from environment
    import os

    db_path = Path(
        os.environ.get("NX_DB_PATH", "/tmp/nexuslims-test-data/nexuslims_test.db")
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch(exist_ok=True)

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


@pytest.fixture(scope="session")
def cdcs_test_record_xml():
    """
    Provide test XML content for CDCS integration tests.

    This fixture returns two valid Nexus Experiment XML records with different
    characteristics to enable testing of search and filtering functionality.
    The XML is validated against the nexus-experiment.xsd schema.

    Returns
    -------
    list of tuple
        A list of (title, xml_content) tuples where:
        - title: The record title
        - xml_content: The complete XML as a string
    """
    # First record: STEM imaging with EDS spectrum
    test_record_1_title = "NexusLIMS Integration Test Record - STEM"
    test_record_1_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Experiment xmlns="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <title>{test_record_1_title}</title>
    <summary>
        <instrument pid="TEST-INSTRUMENT-001">Test STEM for Integration Tests</instrument>
        <reservationStart>2024-12-01T09:00:00-07:00</reservationStart>
        <reservationEnd>2024-12-01T17:00:00-07:00</reservationEnd>
        <motivation>Integration test seed record for testing CDCS search and download functionality</motivation>
    </summary>
    <acquisitionActivity seqno="1">
        <startTime>2024-12-01T09:30:00-07:00</startTime>
        <dataset type="Image" role="Experimental">
            <name>test_image_001.dm3</name>
            <location>/path/to/data/test_image_001.dm3</location>
            <format>Digital Micrograph DM3</format>
            <description>Test STEM image for integration testing</description>
            <meta name="magnification">50000x</meta>
            <meta name="beam_energy">200 kV</meta>
            <meta name="pixel_size">0.5 nm</meta>
        </dataset>
        <dataset type="Spectrum" role="Experimental">
            <name>test_spectrum_001.msa</name>
            <location>/path/to/data/test_spectrum_001.msa</location>
            <format>EMSA-MSA Spectrum</format>
            <description>Test EDS spectrum for integration testing</description>
            <meta name="dwell_time">10 ms</meta>
            <meta name="detector">EDS Detector</meta>
        </dataset>
    </acquisitionActivity>
    <acquisitionActivity seqno="2">
        <startTime>2024-12-01T10:15:00-07:00</startTime>
        <dataset type="Image" role="Experimental">
            <name>test_image_002.tif</name>
            <location>/path/to/data/test_image_002.tif</location>
            <format>TIFF</format>
            <description>Test TEM image for integration testing</description>
            <meta name="magnification">100000x</meta>
            <meta name="defocus">-500 nm</meta>
        </dataset>
    </acquisitionActivity>
</Experiment>
"""

    # Second record: SEM imaging with different instrument and metadata
    test_record_2_title = "NexusLIMS Integration Test Record - SEM"
    test_record_2_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Experiment xmlns="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <title>{test_record_2_title}</title>
    <summary>
        <instrument pid="TEST-INSTRUMENT-002">Test SEM for Integration Tests</instrument>
        <reservationStart>2024-12-02T08:00:00-07:00</reservationStart>
        <reservationEnd>2024-12-02T16:00:00-07:00</reservationEnd>
        <motivation>Second integration test record with different instrument and parameters for testing search/filter</motivation>
    </summary>
    <acquisitionActivity seqno="1">
        <startTime>2024-12-02T08:30:00-07:00</startTime>
        <dataset type="Image" role="Experimental">
            <name>sem_image_001.tif</name>
            <location>/path/to/data/sem_image_001.tif</location>
            <format>TIFF</format>
            <description>Test SEM image for integration testing</description>
            <meta name="magnification">10000x</meta>
            <meta name="beam_energy">15 kV</meta>
            <meta name="working_distance">10 mm</meta>
        </dataset>
    </acquisitionActivity>
    <acquisitionActivity seqno="2">
        <startTime>2024-12-02T09:45:00-07:00</startTime>
        <dataset type="Image" role="Experimental">
            <name>sem_image_002.tif</name>
            <location>/path/to/data/sem_image_002.tif</location>
            <format>TIFF</format>
            <description>High resolution SEM image</description>
            <meta name="magnification">50000x</meta>
            <meta name="beam_energy">10 kV</meta>
            <meta name="working_distance">5 mm</meta>
        </dataset>
        <dataset type="Spectrum" role="Experimental">
            <name>sem_eds_001.spc</name>
            <location>/path/to/data/sem_eds_001.spc</location>
            <format>EDAX SPC Spectrum</format>
            <description>EDS spectrum from SEM analysis</description>
            <meta name="live_time">60 s</meta>
            <meta name="detector">EDAX EDS</meta>
        </dataset>
    </acquisitionActivity>
</Experiment>
"""

    return [
        (test_record_1_title, test_record_1_xml),
        (test_record_2_title, test_record_2_xml),
    ]


@pytest.fixture(scope="session")
def cdcs_test_record(
    docker_services_running, cdcs_url, cdcs_credentials, cdcs_test_record_xml
):
    """
    Create test records in CDCS for search/download integration tests.

    This fixture uploads two test records to CDCS with different characteristics
    to enable testing of search and filtering functionality.

    Parameters
    ----------
    docker_services_running : dict
        Ensures Docker services are running
    cdcs_url : str
        CDCS base URL
    cdcs_credentials : dict
        Authentication credentials
    cdcs_test_record_xml : list of tuple
        List of test record (title, XML content) tuples from fixture

    Returns
    -------
    list of dict
        Information about the created test records, each containing:
        - title: Record title
        - record_id: CDCS record ID
        - xml_content: Original XML content
    """
    # Set up CDCS environment for session scope
    setup_cdcs_environment(cdcs_url, cdcs_credentials)

    import nexusLIMS.cdcs as cdcs_module

    # Upload all test records
    created_records = []
    for test_record_title, test_record_xml in cdcs_test_record_xml:
        response, record_id = cdcs_module.upload_record_content(
            test_record_xml, test_record_title
        )

        if response.status_code != 201:
            # Cleanup any previously created records before raising
            for record in created_records:
                try:
                    cdcs_module.delete_record(record["record_id"])
                except Exception:
                    pass
            raise RuntimeError(
                f"Failed to create test record '{test_record_title}': "
                f"{response.status_code} - {response.text}"
            )

        print(f"[+] Created test record: {test_record_title} (ID: {record_id})")
        created_records.append(
            {
                "title": test_record_title,
                "record_id": record_id,
                "xml_content": test_record_xml,
            }
        )

    yield created_records

    # Cleanup: Delete all test records
    for record in created_records:
        try:
            cdcs_module.delete_record(record["record_id"])
            print(f"[+] Deleted test record: {record['record_id']}")
        except Exception as e:
            print(f"[!] Failed to cleanup test record {record['record_id']}: {e}")


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

    # Initialize database schema using production SQL script
    # NOTE: Must create database BEFORE refreshing settings since NX_DB_PATH
    # validation requires the file to exist
    schema_script = (
        Path(__file__).parent.parent.parent
        / "nexusLIMS"
        / "db"
        / "dev"
        / "NexusLIMS_db_creation_script.sql"
    )

    conn = sqlite3.connect(db_path)
    with schema_script.open() as f:
        conn.executescript(f.read())
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
            "instrument_pid": "FEI-Titan-STEM",
            "property_tag": "STEM_3840284",
            "filestore_path": "./Titan_STEM",
        },
        3: {  # 642 FEI Titan
            "instrument_pid": "FEI-Titan-TEM",
            "property_tag": "TEM_12039485",
            "filestore_path": "./Titan_TEM",
        },
        10: {  # Test Tool
            "instrument_pid": "TEST-TOOL-010",
            "property_tag": "TEST",
            "filestore_path": "./Nexus_Test_Instrument",
        },
    }

    instruments = []
    for tool in mock_tools_data:
        if tool["id"] in tool_configs:
            config = tool_configs[tool["id"]]
            instruments.append(
                {
                    "instrument_pid": config["instrument_pid"],
                    "api_url": f"{NEMO_URL}tools/?id={tool['id']}",
                    "calendar_name": tool["name"],
                    "calendar_url": f"{NEMO_BASE_URL}/calendar/{config['property_tag']}-titan/",
                    "location": "Building 217",
                    "schema_name": tool["name"],
                    "property_tag": config["property_tag"],
                    "filestore_path": config["filestore_path"],
                    "harvester": "nemo",
                    "timezone": "America/Denver",
                }
            )

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


# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_instrument_db(populated_test_database):
    """
    Provide instrument database loaded from the test database.

    This fixture loads the instrument database from the populated test database,
    making it easy for tests to access the instruments that were created by the
    populated_test_database fixture.

    Parameters
    ----------
    populated_test_database : Path
        Path to the populated test database from populated_test_database fixture

    Returns
    -------
    dict
        Dictionary of Instrument objects loaded from the test database
    """
    from nexusLIMS.instruments import _get_instrument_db

    # Load instrument database from the test database path
    return _get_instrument_db(db_path=populated_test_database)


# ============================================================================
# Test Data Fixtures
# ========================================================================================================================================================
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


@pytest.fixture
def extracted_test_files(test_data_dirs):
    """
    Extract test_record_files.tar.gz to test instrument data directory.

    This fixture extracts the test record files archive to the temporary
    test instrument data directory with metadata about the extracted files.
    This is useful for end-to-end and error recovery tests that need to know
    the expected file dates and directory structure.

    Parameters
    ----------
    test_data_dirs : dict
        Test data directories fixture

    Yields
    ------
    dict
        Dictionary with paths and metadata:
        - 'base_dir': Base directory where files were extracted
        - 'titan_date': Expected date for Titan files (2018-11-13)
        - 'jeol_date': Expected date for JEOL files (2019-07-24)
        - 'extracted_dirs': List of top-level directories extracted
    """
    import shutil
    import tarfile
    from datetime import datetime

    from nexusLIMS.config import settings

    # Test data archive location
    archive_path = Path(__file__).parents[1] / "unit/files/test_record_files.tar.gz"

    # Get the test instrument data directory from settings
    instrument_data_dir = Path(settings.NX_INSTRUMENT_DATA_PATH)
    nx_data_dir = Path(settings.NX_DATA_PATH)

    # Extract archive to instrument data directory and track what was extracted
    print(f"\n[*] Extracting test files to {instrument_data_dir}")
    extracted_top_level_dirs = []

    with tarfile.open(archive_path, "r:gz") as tar:
        # Get list of top-level directories that will be extracted
        for member in tar.getmembers():
            if member.isdir():
                top_level = member.name.split("/")[0]
                if top_level not in extracted_top_level_dirs:
                    extracted_top_level_dirs.append(top_level)

        tar.extractall(instrument_data_dir)

    print(f"[+] Top-level directories extracted: {extracted_top_level_dirs}")

    # Dates from the archive structure (Titan: 20181113, JEOL: 20190724)
    titan_date = datetime(2018, 11, 13)
    jeol_date = datetime(2019, 7, 24)

    yield {
        "base_dir": instrument_data_dir,
        "titan_date": titan_date,
        "jeol_date": jeol_date,
        "extracted_dirs": extracted_top_level_dirs,
    }

    # Cleanup: Remove extracted directories from both instrument data and NX_DATA_PATH
    print("\n[*] Cleaning up extracted test files and generated metadata")
    for dir_name in extracted_top_level_dirs:
        # Clean up source files in instrument data directory
        source_dir = instrument_data_dir / dir_name
        if source_dir.exists():
            print(f"[*] Removing {source_dir}")
            shutil.rmtree(source_dir)

        # Clean up generated metadata in NX_DATA_PATH
        metadata_dir = nx_data_dir / dir_name
        if metadata_dir.exists():
            print(f"[*] Removing generated metadata {metadata_dir}")
            shutil.rmtree(metadata_dir)


@pytest.fixture
def test_environment_setup(
    docker_services_running,
    nemo_connector,
    populated_test_database,
    extracted_test_files,
    cdcs_client,
    monkeypatch,
):
    """
    Set up the test environment for end-to-end workflow testing.

    This fixture configures the environment so that process_new_records()
    can run naturally, including NEMO harvesting and CDCS uploads. It does NOT
    create sessions directly - that's left to the NEMO harvester to do.

    Parameters
    ----------
    docker_services_running : dict
        Ensures all Docker services (including fileserver) are running
    nemo_connector : NemoConnector
        Configured NEMO connector from fixture (already mocked to return test usage events)
    populated_test_database : Path
        Test database with instruments (also configures NX_DB_PATH)
    extracted_test_files : dict
        Extracted test files information
    cdcs_client : dict
        CDCS client configuration for record uploads
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict
        Test environment information:
        - 'instrument_pid': Instrument PID to use for testing
        - 'dt_from': Expected session start datetime
        - 'dt_to': Expected session end datetime
        - 'user': Expected username
        - 'instrument_db': Test instrument database
        - 'cdcs_client': CDCS client configuration
    """
    from datetime import timedelta

    from nexusLIMS import instruments

    # Patch the instrument_db to use test database
    test_instrument_db = instruments._get_instrument_db(db_path=populated_test_database)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)

    # Get Titan instrument from test database (should be FEI-Titan-TEM)
    instrument = test_instrument_db["FEI-Titan-TEM"]

    # Create expected session timespan that covers the test files
    # Files are dated 2018-11-13, so expect a session around that time
    # (the nemo_connector fixture should already be configured to return this)
    session_start = extracted_test_files["titan_date"].replace(
        hour=4, minute=0, second=0
    )
    session_end = session_start + timedelta(hours=12)

    print(f"\n[+] Test environment configured")
    print(f"    Instrument: {instrument.name}")
    print(f"    Expected session time: {session_start} to {session_end}")
    print(f"    Expected user: captain")

    return {
        "instrument_pid": instrument.name,  # instrument.name is the PID
        "dt_from": session_start,
        "dt_to": session_end,
        "user": "captain",
        "instrument_db": test_instrument_db,
        "cdcs_client": cdcs_client,
    }


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
def docker_logs():
    """
    Provide utility function to capture Docker service logs.

    This fixture provides a function that can be called from tests to
    capture and return Docker service logs for debugging purposes.

    Returns
    -------
    callable
        Function that takes optional service names and returns logs as string
    """

    def _get_docker_logs(services=None, timeout=30):
        """
        Capture Docker service logs.

        Parameters
        ----------
        services : list[str] | None
            List of service names to get logs for. If None, gets all services.
        timeout : int
            Maximum time to wait for logs (seconds)

        Returns
        -------
        str
            Combined stdout and stderr logs from Docker services
        """
        import subprocess

        cmd = ["docker", "compose", "logs", "--no-color"]
        if services:
            cmd.extend(services)

        try:
            result = subprocess.run(
                cmd, cwd=DOCKER_DIR, capture_output=True, text=True, timeout=timeout
            )

            logs = []
            if result.stdout:
                logs.append("[STDOUT]")
                logs.append(result.stdout)
            if result.stderr:
                logs.append("[STDERR]")
                logs.append(result.stderr)

            return "\n".join(logs) if logs else "No logs captured"

        except subprocess.TimeoutExpired:
            return f"Docker log capture timed out after {timeout} seconds"
        except Exception as e:
            return f"Failed to capture Docker logs: {e}"

    return _get_docker_logs


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


# ============================================================================
# Docker Log Capture on Test Failure
# ============================================================================


def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture Docker logs on test failure.

    This hook captures Docker service logs when integration tests fail,
    making it easier to debug issues with the CDCS, NEMO, or other services.
    """
    # Only process integration tests
    if "integration" not in [mark.name for mark in item.iter_markers()]:
        return

    # Only capture logs for failed tests
    if call.excinfo and call.excinfo.value:
        # Import here to avoid issues if Docker isn't available
        import subprocess

        print(f"\n{'=' * 70}")
        print(f"CAPTURING DOCKER LOGS FOR FAILED TEST: {item.name}")
        print(f"{'=' * 70}")

        try:
            # Capture Docker compose logs (last 100 lines only)
            result = subprocess.run(
                ["docker", "compose", "logs", "--no-color", "--tail", "100", "cdcs"],
                cwd=DOCKER_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.stdout:
                print("\n[DOCKER LOGS START]")
                print(result.stdout)
                print("[DOCKER LOGS END]\n")

            if result.stderr:
                print("\n[DOCKER ERRORS START]")
                print(result.stderr)
                print("[DOCKER ERRORS END]\n")

        except subprocess.TimeoutExpired:
            print("[!] Docker log capture timed out after 30 seconds")
        except Exception as e:
            print(f"[!] Failed to capture Docker logs: {e}")

        print(f"{'=' * 70}")
        print("END OF DOCKER LOGS")
        print(f"{'=' * 70}\n")
