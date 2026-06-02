# ruff: noqa: T201
"""
Integration test fixtures for NexusLIMS.

This module provides pytest fixtures for managing Docker services, test data,
and integration test environments. Fixtures manage the lifecycle of NEMO and
CDCS services, database setup, and cleanup operations.
"""

import contextlib
import fcntl
import os
import subprocess
import tempfile
import time
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import requests
from sqlmodel import Session as DBSession

from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog

if TYPE_CHECKING:
    # Import statements or code that should only be evaluated during type checking
    # This code will be ignored at runtime
    from nexusLIMS.harvesters.nemo.connector import NemoConnector
    from nexusLIMS.utils.elabftw import ELabFTWClient


# Docker compose directory
DOCKER_DIR = Path(__file__).parent / "docker"

# Service URLs (base URLs without /api/)
# These use the Caddy reverse proxy on port 40080
NEMO_BASE_URL = "http://nemo.localhost:40080"
NEMO2_BASE_URL = (
    "http://nemo2.localhost:40080"  # Second NEMO instance for multi-instance testing
)
CDCS_URL = "http://cdcs.localhost:40080"
FILESERVER_URL = "http://fileserver.localhost:40080"
MAILPIT_URL = "http://mailpit.localhost:40080"
MAILPIT_SMTP_HOST = "localhost"
MAILPIT_SMTP_PORT = 41025
MAILPIT_SMTP_USER = "test"
MAILPIT_SMTP_PASS = "testpass"

# eLabFTW service (accessed through Caddy reverse proxy)
ELABFTW_URL = "http://elabftw.localhost:40080"
# eLabFTW API key format: "1-" + 84 characters (minimum for validation)
ELABFTW_API_KEY = "1-" + "a" * 84

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
# xdist Coordination Helpers
# ============================================================================
# When running integration tests with pytest-xdist, multiple worker processes
# share a single Docker stack.  These helpers serialize startup/teardown so
# only the first worker starts Docker (and cleans data dirs) and only the last
# worker tears it down.

_COORD_LOCK_FILE = Path(tempfile.gettempdir()) / "nexuslims-integ-coord.lock"
_COORD_COUNT_FILE = Path(tempfile.gettempdir()) / "nexuslims-integ-coord.count"
_FILESERVER_PID_FILE = Path(tempfile.gettempdir()) / "nexuslims-integ-fileserver.pid"


@contextlib.contextmanager
def _coord_lock():
    """Acquire an exclusive OS-level file lock for worker coordination."""
    lock_fd = _COORD_LOCK_FILE.open("w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()


def _register_worker_and_setup(setup_fn) -> bool:
    """Register worker; if first, call setup_fn() under lock. Return True if first.

    The count is written BEFORE calling setup_fn so that if setup_fn raises, other
    workers see count > 0 and skip the retry rather than all attempting a failing
    setup command in a cascade.
    """
    with _coord_lock():
        count = int(_COORD_COUNT_FILE.read_text()) if _COORD_COUNT_FILE.exists() else 0
        is_first = count == 0
        _COORD_COUNT_FILE.write_text(str(count + 1))
        if is_first:
            setup_fn()
        return is_first


def _deregister_worker() -> bool:
    """Deregister this worker. Returns True if this is the last active worker."""
    with _coord_lock():
        count = int(_COORD_COUNT_FILE.read_text()) if _COORD_COUNT_FILE.exists() else 1
        remaining = max(0, count - 1)
        if remaining == 0:
            _COORD_COUNT_FILE.unlink(missing_ok=True)
            _COORD_LOCK_FILE.unlink(missing_ok=True)
        else:
            _COORD_COUNT_FILE.write_text(str(remaining))
        return remaining == 0


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.

    CRITICAL: This hook must set up the required environment variables
    BEFORE any nexusLIMS modules are imported. The Settings class validates
    path variables at import time, so we must ensure they're set here.

    We use the integration test directories and set up minimal required
    environment variables to allow imports to succeed.

    IMPORTANT: NX_TEST_MODE is already set in tests/conftest.py, which
    disables .env file loading in nexusLIMS.config to prevent test
    contamination from local environment files.
    """
    import os

    # Verify NX_TEST_MODE is set (should be set by tests/conftest.py)
    if os.environ.get("NX_TEST_MODE", "").lower() not in ("true", "1", "yes"):
        msg = (
            "CRITICAL: NX_TEST_MODE must be set before running integration tests. "
            "This should be set in tests/conftest.py."
        )
        raise RuntimeError(msg)

    # Clean up stale coordinator files from a previous crashed run.
    # Only the controller process (or a non-xdist session) does this;
    # workers have config.workerinput set.
    if not hasattr(config, "workerinput"):
        _COORD_LOCK_FILE.unlink(missing_ok=True)
        _COORD_COUNT_FILE.unlink(missing_ok=True)
        _stop_fileserver_subprocess()  # kill any lingering fileserver from previous run

    # Create test directories (for actual test execution)
    test_dirs = [
        TEST_INSTRUMENT_DATA_DIR,
        TEST_DATA_DIR,
    ]

    # Ensure all directories exist
    for dir_path in test_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Set up environment variables BEFORE any nexusLIMS imports
    # These are the minimum required for Settings validation.
    #
    # When running the full test suite with -n auto (xdist), the unit conftest's
    # module-level code already set per-worker isolated paths (e.g.,
    # /tmp/nexuslims-gw0-XXXX/InstrumentData).  Don't override those: unit tests
    # need their own isolated paths, and integration tests get the correct
    # TEST_INSTRUMENT_DATA_DIR via monkeypatch inside fresh_test_db.
    _xdist_worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    _current_instr = os.environ.get("NX_INSTRUMENT_DATA_PATH", "")
    _current_data = os.environ.get("NX_DATA_PATH", "")
    _worker_owns_paths = _xdist_worker and _xdist_worker in _current_instr

    if not _worker_owns_paths:
        os.environ["NX_INSTRUMENT_DATA_PATH"] = str(TEST_INSTRUMENT_DATA_DIR)
        os.environ["NX_DATA_PATH"] = str(TEST_DATA_DIR)

    # Set NX_DB_PATH to a placeholder path so Settings validation passes.
    # The actual per-test DB is created by the db_template + fresh_test_db
    # fixtures at test time. The placeholder file does not need to exist.
    db_suffix = f"_{_xdist_worker}" if _xdist_worker else ""
    db_placeholder = TEST_DATA_DIR / f"integration_test{db_suffix}.db"
    os.environ["NX_DB_PATH"] = str(db_placeholder)

    # Set required CDCS environment variables to dummy values
    # (actual values will be set per-test via fixtures)
    os.environ["NX_CDCS_URL"] = "https://cdcs.example.com"
    os.environ["NX_CDCS_TOKEN"] = "test-api-token"
    os.environ["NX_CERT_BUNDLE"] = (
        "-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----"
    )


def pytest_sessionfinish(session, exitstatus):
    """Stop the host fileserver when the test session finishes.

    In xdist runs this is called once per worker AND once on the controller
    after all workers finish.  We only stop the fileserver on the controller
    (or in a non-xdist single-process run) so the subprocess stays alive for
    the entire test session regardless of which workers use it.
    """
    if not hasattr(session.config, "workerinput"):
        _stop_fileserver_subprocess()


# ============================================================================
# Test Isolation Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_caches_between_tests():
    """
    Reset singletons after integration tests to prevent pollution.

    Integration tests use a persistent session-scoped database (expensive to
    recreate), but we still need to clear caches to prevent pollution between
    tests. This fixture runs automatically after each test to reset caches
    while keeping the database intact.

    The database engine itself is NOT reset because it's session-scoped and
    shared across all integration tests for performance reasons.

    Notes
    -----
    We reset AFTER tests rather than BEFORE because session-scoped fixtures
    (like populated_test_database) need to run once at the start. Resetting
    before tests would interfere with these fixtures.

    What gets reset:
    - Instrument cache (forces reload from database)
    - Settings cache (forces reload from environment)
    - EMG graph cache (forces reload of glossary)

    What does NOT get reset:
    - Database engine (session-scoped for performance)
    - Database contents (managed by per-test fixtures as needed)
    """
    from tests.fixtures.core import SingletonResetter

    yield  # Test runs first

    # AFTER test: reset caches so next test starts clean
    SingletonResetter.reset_instrument_cache()
    SingletonResetter.reset_settings()
    SingletonResetter.reset_emg_cache()
    # Don't reset engine/database - those are session-scoped


# ============================================================================
# Docker Service Management
# ============================================================================


def _start_fileserver_subprocess() -> int:
    """Start fileserver as a detached subprocess; return its PID.

    The subprocess runs independently of any pytest worker process, so it
    survives when the worker that started it finishes.  The last worker's
    docker_services teardown is responsible for stopping it.
    """
    import select as _select
    import sys as _sys

    server_code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer\n"
        "from urllib.parse import unquote, urlparse\n"
        "\n"
        "INSTR = Path('/tmp/nexuslims-test-instrument-data')\n"
        "DATA  = Path('/tmp/nexuslims-test-data')\n"
        "\n"
        "class H(SimpleHTTPRequestHandler):\n"
        "    def translate_path(self, path):\n"
        "        path = unquote(urlparse(path).path).lstrip('/')\n"
        "        if path.startswith('instrument-data/'):\n"
        "            return str(INSTR / path[len('instrument-data/'):])\n"
        "        if path.startswith('data/'):\n"
        "            return str(DATA / path[len('data/'):])\n"
        "        return '/dev/null/nonexistent'\n"
        "    def end_headers(self):\n"
        "        self.send_header('Access-Control-Allow-Origin', '*')\n"
        "        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')\n"
        "        self.send_header('Access-Control-Allow-Headers', '*')\n"
        "        cc = ('no-store, no-cache, must-revalidate,'\n"
        "              ' proxy-revalidate, max-age=0')\n"
        "        self.send_header('Cache-Control', cc)\n"
        "        self.send_header('Pragma', 'no-cache')\n"
        "        self.send_header('Expires', '0')\n"
        "        super().end_headers()\n"
        "    def log_message(self, *a): pass\n"
        "\n"
        "srv = ThreadingHTTPServer(('', 48081), H)\n"
        "sys.stdout.write('ready\\n'); sys.stdout.flush()\n"
        "srv.serve_forever()\n"
    )
    proc = subprocess.Popen(
        [_sys.executable, "-c", server_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    rlist, _, _ = _select.select([proc.stdout], [], [], 10.0)
    if rlist:
        proc.stdout.readline()  # consume "ready\n"
    else:
        print("[!] Fileserver subprocess did not signal ready within 10 s")
    _FILESERVER_PID_FILE.write_text(str(proc.pid))
    print(f"[+] Host fileserver subprocess started (PID={proc.pid}) on port 48081")
    print(f"[+] Serving instrument data from: {TEST_INSTRUMENT_DATA_DIR}")
    print(f"[+] Serving NexusLIMS data from: {TEST_DATA_DIR}")
    return proc.pid


def _stop_fileserver_subprocess() -> None:
    """Stop the fileserver subprocess identified by _FILESERVER_PID_FILE."""
    import signal as _signal

    if not _FILESERVER_PID_FILE.exists():
        return
    try:
        pid = int(_FILESERVER_PID_FILE.read_text().strip())
    except (ValueError, OSError):
        _FILESERVER_PID_FILE.unlink(missing_ok=True)
        return
    try:
        os.kill(pid, _signal.SIGTERM)
        print(f"[+] Host fileserver subprocess stopped (PID={pid})")
    except ProcessLookupError:
        print(f"[*] Fileserver process {pid} already gone")
    _FILESERVER_PID_FILE.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def host_fileserver():
    """
    Pytest fixture for host-based fileserver.

    When running under pytest-xdist, multiple workers share a single
    fileserver subprocess.  The first worker starts it as a detached
    subprocess (via _start_fileserver_subprocess) so it outlives any
    individual worker process.  The subprocess is stopped by the controller
    in pytest_sessionfinish after all workers have completed, ensuring it
    remains alive for all tests regardless of which workers use it.

    Returns
    -------
    None
        Fileserver is running when the fixture completes setup
    """
    with _coord_lock():
        if not _FILESERVER_PID_FILE.exists():
            _start_fileserver_subprocess()
        else:
            print("[*] Host fileserver already running (started by another worker)")


@pytest.fixture(scope="session")
def docker_services(request, host_fileserver):  # noqa: PLR0912, PLR0915
    """
    Start Docker services once per test session.

    This fixture manages the lifecycle of all Docker services defined in
    docker-compose.yml including NEMO, CDCS, PostgreSQL, Redis, and Mailpit.
    Note that the fileserver now runs on the host machine (via host_fileserver fixture)
    to avoid Docker volume mount issues on macOS.

    When running under pytest-xdist, multiple workers share a single Docker
    stack.  The first worker to reach this fixture cleans data directories and
    starts Docker; subsequent workers wait for services to become healthy.
    Only the last active worker tears Docker down.

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
    - Set NX_TESTS_KEEP_DOCKER_RUNNING=1 env var to skip teardown for debugging
    """
    import os
    import shutil

    keep_running = os.environ.get("NX_TESTS_KEEP_DOCKER_RUNNING", "0") == "1"

    # ------------------------------------------------------------------
    # First-worker setup: clean data dirs + start Docker (under lock so
    # only one worker does it; others wait and then proceed to health checks)
    # ------------------------------------------------------------------
    def _first_worker_setup():
        print("\n[*] Checking test data directories...")
        for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
            if test_dir.exists():
                print(f"[!] Removing existing test data directory: {test_dir}")
                shutil.rmtree(test_dir)
            test_dir.mkdir(parents=True, exist_ok=True)
            print(f"[+] Created {test_dir}")

        # Check if Docker services are already running before trying to start
        already_running = False
        try:
            nemo_ok = (
                requests.get(NEMO_HEALTH_URL, timeout=2).status_code == HTTPStatus.OK
            )
            cdcs_ok = (
                requests.get(CDCS_HEALTH_URL, timeout=2).status_code == HTTPStatus.OK
            )
            mailpit_ok = (
                requests.get(MAILPIT_HEALTH_URL, timeout=2).status_code == HTTPStatus.OK
            )
            already_running = nemo_ok and cdcs_ok and mailpit_ok
        except (requests.ConnectionError, requests.Timeout):
            pass

        if already_running:
            print("[+] Docker services already running — skipping startup")
            return

        print("[*] Docker services not running — starting them now...")
        compose_cmd = ["docker", "compose", "-f", "docker-compose.yml"]
        ci_override = DOCKER_DIR / "docker-compose.ci.yml"
        in_ci = any(os.environ.get(v) for v in ["CI", "GITHUB_ACTIONS", "GITLAB_CI"])
        if ci_override.exists() and in_ci:
            print(
                "[*] Detected CI environment, using CI override with pre-built images"
            )
            compose_cmd.extend(["-f", "docker-compose.ci.yml"])
        elif not in_ci:
            print("[*] Running locally, using base docker-compose.yml to build images")
        compose_cmd.append("up")
        compose_cmd.append("-d")

        result = subprocess.run(
            compose_cmd, check=False, cwd=DOCKER_DIR, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[!] docker compose up failed (exit {result.returncode})")
            if result.stdout:
                print(f"[!] stdout:\n{result.stdout}")
            if result.stderr:
                print(f"[!] stderr:\n{result.stderr}")
            result.check_returncode()

    _register_worker_and_setup(_first_worker_setup)

    # ------------------------------------------------------------------
    # All workers wait for services to be healthy
    # ------------------------------------------------------------------
    max_wait = 180
    start_time = time.time()
    nemo_ready = cdcs_ready = mailpit_ready = False

    print("[*] Waiting for Docker services to be healthy...")
    while time.time() - start_time < max_wait:
        try:
            if not nemo_ready:
                nemo_ready = (
                    requests.get(NEMO_HEALTH_URL, timeout=2).status_code
                    == HTTPStatus.OK
                )
                if nemo_ready:
                    print("[+] NEMO service is ready")
            if not cdcs_ready:
                cdcs_ready = (
                    requests.get(CDCS_HEALTH_URL, timeout=2).status_code
                    == HTTPStatus.OK
                )
                if cdcs_ready:
                    print("[+] CDCS service is ready")
            if not mailpit_ready:
                mailpit_ready = (
                    requests.get(MAILPIT_HEALTH_URL, timeout=2).status_code
                    == HTTPStatus.OK
                )
                if mailpit_ready:
                    print("[+] Mailpit service is ready")
            if nemo_ready and cdcs_ready and mailpit_ready:
                print("[+] All services are ready!")
                break
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2)
    else:
        print("[-] Service health checks timed out")
        subprocess.run(["docker", "compose", "logs"], check=False, cwd=DOCKER_DIR)
        msg = (
            f"Services failed to start within {max_wait} seconds. "
            "Check Docker logs above for details."
        )
        raise RuntimeError(msg)

    yield

    # ------------------------------------------------------------------
    # Last-worker teardown: only the final worker cleans up
    # ------------------------------------------------------------------
    is_last = _deregister_worker()

    if keep_running:
        if is_last:
            print(
                "\n[*] NX_TESTS_KEEP_DOCKER_RUNNING=1: Keeping Docker services running"
            )
            print("[!] Remember to manually clean up with: docker compose down -v")
        return

    if not is_last:
        return

    print("\n[*] Last worker — cleaning up Docker services...")
    subprocess.run(
        ["docker", "compose", "down", "-v"],
        check=False,
        cwd=DOCKER_DIR,
        capture_output=True,
    )
    print("[+] Docker services cleaned up")

    print("[*] Cleaning test data directories...")
    cleanup_errors = []
    for test_dir in [TEST_INSTRUMENT_DATA_DIR, TEST_DATA_DIR]:
        if test_dir.exists():
            try:
                shutil.rmtree(test_dir)
                print(f"[+] Removed {test_dir}")
            except Exception as exc:
                msg = f"Failed to remove {test_dir}: {exc}"
                print(f"[!] {msg}")
                cleanup_errors.append(msg)

    if cleanup_errors:
        print("\n[!] WARNING: Some cleanup operations failed:")
        for err in cleanup_errors:
            print(f"    - {err}")
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
    return {
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
            # Mailpit API: msg.Subject, msg.To, msg.From (not nested in Content.Headers)
            # Check subject
            if subject is not None:
                msg_subject = msg.get("Subject", "")
                if subject.lower() not in msg_subject.lower():
                    continue

            # Check recipient
            if to is not None:
                msg_to_list = msg.get("To", [])
                # msg_to_list is a list of {"Address": email, "Name": ...} dicts
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
def nemo_connector(nemo_client, fresh_test_db, monkeypatch) -> "NemoConnector":
    """
    Provide a NemoConnector instance for integration tests.

    This fixture creates a NemoConnector instance using the configured
    NEMO client settings, avoiding repeated connector creation in tests.
    It patches the instrument_db to use the test database.

    Parameters
    ----------
    nemo_client : dict
        NEMO connection configuration from nemo_client fixture
    fresh_test_db : Path
        Per-test isolated database copy with instruments populated
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
    test_instrument_db = instruments._get_instrument_db(db_path=fresh_test_db)

    # Patch the instrument_db in both the instruments module and the connector module
    # This is necessary because the connector imports instrument_db at module level
    monkeypatch.setattr(connector, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments, "_instrument_db_initialized", True)

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
        Dictionary with 'token' key containing the API token
    """
    # Use the same fixed dev token defined in NexusLIMS-CDCS's
    # NX_DEV_API_TOKEN setting in config/settings/dev_settings.py
    return {
        "token": "nexuslims-dev-token-not-for-production",
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
    ...         NX_CDCS_TOKEN="invalid-token",
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


def delete_all_cdcs_records():
    """
    Delete all records from the CDCS instance.

    This helper function fetches all records from CDCS and deletes them.
    Useful for cleanup after tests to ensure a clean state.

    Returns
    -------
    int
        Number of records deleted
    """
    from nexusLIMS.utils import cdcs

    deleted_count = 0
    print("\n[*] Cleaning up CDCS records...")
    try:
        all_records = cdcs.search_records()
        if all_records:
            for record in all_records:
                try:
                    cdcs.delete_record(record["id"])
                    print(f"    Deleted record: {record.get('title', record['id'])}")
                    deleted_count += 1
                except Exception as e:
                    print(f"[!] Failed to delete record {record['id']}: {e}")
            print(f"[+] Deleted {deleted_count} records from CDCS")
        else:
            print("[+] No records to delete from CDCS")
    except Exception as e:
        print(f"[!] Failed to fetch records for cleanup: {e}")

    return deleted_count


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
        Authentication credentials with 'token' key

    Returns
    -------
    None
        Environment variables are set as a side effect
    """
    import os

    os.environ["NX_CDCS_URL"] = cdcs_url
    os.environ["NX_CDCS_TOKEN"] = cdcs_credentials["token"]

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
    monkeypatch.setenv("NX_CDCS_TOKEN", cdcs_credentials["token"])

    # Ensure the database file exists (Settings validation requires it)
    # Get the current NX_DB_PATH from environment
    import os

    db_path = Path(
        os.environ.get("NX_DB_PATH", "/tmp/nexuslims-test-data/nexuslims_test.db")
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch(exist_ok=True)

    refresh_settings()

    # Track created records and users for cleanup
    created_records = []
    created_user_ids = []

    def register_record(record_id: str):
        """Register a record ID for cleanup after test."""
        created_records.append(record_id)

    def register_user(user_id: int):
        """Register a user ID for cleanup after test."""
        created_user_ids.append(user_id)

    yield {
        "url": cdcs_url,
        "token": cdcs_credentials["token"],
        "register_record": register_record,
        "register_user": register_user,
        "created_records": created_records,
        "created_user_ids": created_user_ids,
    }

    # Cleanup: Delete all records and users created during the test
    if os.environ.get("NX_TESTS_SKIP_CDCS_CLEANUP", "0") == "1":
        print(
            f"\n[*] NX_TESTS_SKIP_CDCS_CLEANUP=1: Leaving {len(created_records)} "
            f"record(s) in CDCS: {created_records}"
        )
        print(
            f"[*] NX_TESTS_SKIP_CDCS_CLEANUP=1: Leaving {len(created_user_ids)} "
            f"user(s) in CDCS: {created_user_ids}"
        )
        return

    from urllib.parse import urljoin

    from nexusLIMS.utils import cdcs
    from nexusLIMS.utils.network import nexus_req

    for record_id in created_records:
        try:
            cdcs.delete_record(record_id)
        except Exception as e:
            print(f"[!] Failed to cleanup record {record_id}: {e}")

    for user_id in created_user_ids:
        try:
            endpoint = urljoin(cdcs_url, f"rest/user/{user_id}/")
            r = nexus_req(endpoint, "DELETE", token_auth=cdcs_credentials["token"])
            if r.status_code not in (204, 200):
                print(f"[!] Failed to cleanup user {user_id}: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[!] Failed to cleanup user {user_id}: {e}")


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
    # Make titles unique per xdist worker to prevent CDCS search collisions
    # when multiple workers run in parallel and each uploads their own copy.
    _worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    _worker_suffix = f" [{_worker}]"

    # First record: STEM imaging with EDS spectrum
    test_record_1_title = f"NexusLIMS Integration Test Record - STEM{_worker_suffix}"
    test_record_1_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Experiment xmlns="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <title>{test_record_1_title}</title>
    <summary>
        <instrument pid="TEST-INSTRUMENT-001">Test STEM for Integration Tests
        </instrument>
        <reservationStart>2024-12-01T09:00:00-07:00</reservationStart>
        <reservationEnd>2024-12-01T17:00:00-07:00</reservationEnd>
        <motivation>Integration test seed record for search and download</motivation>
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
    test_record_2_title = f"NexusLIMS Integration Test Record - SEM{_worker_suffix}"
    test_record_2_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Experiment xmlns="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <title>{test_record_2_title}</title>
    <summary>
        <instrument pid="TEST-INSTRUMENT-002">Test SEM for Integration Tests
        </instrument>
        <reservationStart>2024-12-02T08:00:00-07:00</reservationStart>
        <reservationEnd>2024-12-02T16:00:00-07:00</reservationEnd>
        <motivation>Second test record with different instrument for search/filter
        </motivation>
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

    from nexusLIMS.utils import cdcs

    # Upload all test records
    created_records = []
    for test_record_title, test_record_xml in cdcs_test_record_xml:
        response, record_id = cdcs.upload_record_content(
            test_record_xml, test_record_title
        )

        if response.status_code != 201:
            # Cleanup any previously created records before raising
            for record in created_records:
                with contextlib.suppress(Exception):
                    cdcs.delete_record(record["record_id"])
            msg = (
                f"Failed to create test record '{test_record_title}': "
                f"{response.status_code} - {response.text}"
            )
            raise RuntimeError(msg)

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
            cdcs.delete_record(record["record_id"])
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
    NexusLIMS database schema using SQLModel. The database is isolated for
    each test and automatically cleaned up after the test completes.

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
    from sqlmodel import SQLModel

    from nexusLIMS.config import refresh_settings
    from nexusLIMS.db.engine import create_transient_sqlite_engine

    # Import all models to register them with SQLModel metadata
    from nexusLIMS.db.models import (  # noqa: F401
        Instrument,
        SessionLog,
        UploadLog,
    )

    # Create database in temporary directory
    db_path = tmp_path / "test_integration.db"

    # Create engine and tables using SQLModel
    engine = create_transient_sqlite_engine(db_path)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    # Now that the database file exists, update the config
    monkeypatch.setenv("NX_DB_PATH", str(db_path))
    refresh_settings()

    return db_path


@pytest.fixture(scope="session")
def db_template(docker_services, mock_tools_data, tmp_path_factory):
    """
    Create a populated, read-only SQLite DB template once per worker.

    Lives in pytest's own tmp space (``tmp_path_factory``), which is never
    wiped by ``_first_worker_setup``.  ``fresh_test_db`` copies this file for
    every test that needs an isolated, writable DB.

    Parameters
    ----------
    docker_services : None
        Ensures Docker services are running before the DB is created.
    mock_tools_data : list[dict]
        Mock NEMO tool records (shared with unit tests).
    tmp_path_factory : pytest.TempPathFactory
        Session-scoped factory for temporary directories.

    Returns
    -------
    Path
        Path to the read-only template database file.
    """
    import sqlite3

    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    from nexusLIMS.db.engine import create_transient_sqlite_engine
    from tests.conftest import create_test_database
    from tests.fixtures.test_data import INSTRUMENTS

    template_dir = tmp_path_factory.mktemp("db_template")
    db_path = template_dir / "template.db"

    # Create schema
    create_test_database(db_path)

    # Seed alembic_version so _check_alembic_migration passes.
    _alembic_ini = Path(__file__).parents[2] / "alembic.ini"
    _cfg = AlembicConfig(str(_alembic_ini))
    _cfg.set_main_option(
        "script_location",
        str(_alembic_ini.parent / "nexusLIMS" / "db" / "migrations"),
    )
    _head = ScriptDirectory.from_config(_cfg).get_current_head()
    if _head:
        _engine = create_transient_sqlite_engine(db_path)
        with _engine.connect() as _conn:
            _conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS alembic_version "
                    "(version_num VARCHAR(32) NOT NULL)"
                )
            )
            _conn.execute(text("DELETE FROM alembic_version"))
            _conn.execute(text(f"INSERT INTO alembic_version VALUES ('{_head}')"))
            _conn.commit()
        _engine.dispose()

    # Map mock tool IDs to instrument PIDs from unified test data.
    tool_id_to_pid = {
        1: "FEI-Titan-STEM",
        3: "FEI-Titan-TEM",
        10: "test-tool-10",
    }

    instruments = []
    for tool in mock_tools_data:
        if tool["id"] in tool_id_to_pid:
            instrument_pid = tool_id_to_pid[tool["id"]]
            cfg = INSTRUMENTS[instrument_pid]
            instruments.append(
                {
                    "instrument_pid": cfg["instrument_pid"],
                    "api_url": f"{NEMO_URL}tools/?id={tool['id']}",
                    "calendar_url": cfg["calendar_url"],
                    "location": cfg["location"],
                    "display_name": tool["name"],
                    "property_tag": cfg["property_tag"],
                    "filestore_path": cfg["filestore_path"],
                    "harvester": cfg["harvester"],
                    "timezone": cfg["timezone"],
                }
            )

    # TEST-TOOL for multi-signal integration testing (tool ID 999)
    test_tool_cfg = INSTRUMENTS["TEST-TOOL"]
    instruments.append(
        {
            "instrument_pid": test_tool_cfg["instrument_pid"],
            "api_url": f"{NEMO_URL}tools/?id=999",
            "calendar_url": test_tool_cfg["calendar_url"],
            "location": test_tool_cfg["location"],
            "display_name": "Test Tool (Multi-signal)",
            "property_tag": test_tool_cfg["property_tag"],
            "filestore_path": test_tool_cfg["filestore_path"],
            "harvester": "nemo",
            "timezone": test_tool_cfg["timezone"],
        }
    )

    # Tofwerk-pFIB-TOFSIMS (dummy tool ID 7)
    tofwerk_cfg = INSTRUMENTS["Tofwerk-pFIB-TOFSIMS"]
    instruments.append(
        {
            "instrument_pid": tofwerk_cfg["instrument_pid"],
            "api_url": f"{NEMO_URL}tools/?id=7",
            "calendar_url": tofwerk_cfg["calendar_url"],
            "location": tofwerk_cfg["location"],
            "display_name": tofwerk_cfg["display_name"],
            "property_tag": tofwerk_cfg["property_tag"],
            "filestore_path": tofwerk_cfg["filestore_path"],
            "harvester": tofwerk_cfg["harvester"],
            "timezone": tofwerk_cfg["timezone"],
        }
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM instruments")
    for inst in instruments:
        cursor.execute(
            """
            INSERT INTO instruments (
                instrument_pid, api_url, calendar_url,
                location, display_name, property_tag, filestore_path,
                harvester, timezone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inst["instrument_pid"],
                inst["api_url"],
                inst["calendar_url"],
                inst["location"],
                inst["display_name"],
                inst["property_tag"],
                inst["filestore_path"],
                inst["harvester"],
                inst["timezone"],
            ),
        )
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def fresh_test_db(db_template, tmp_path, monkeypatch):
    """
    Provide a per-test copy of the instrument-populated DB template.

    Copies the read-only template created by ``db_template`` into the
    test's ``tmp_path``, patches ``NX_DB_PATH``, the SQLAlchemy engine
    singleton, and the ``instrument_db`` cache for the duration of one test,
    then restores them on teardown.

    Parameters
    ----------
    db_template : Path
        Path to the populated template DB (session-scoped).
    tmp_path : Path
        Per-test temporary directory provided by pytest.
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture; restores ``NX_DB_PATH`` automatically.

    Yields
    ------
    Path
        Path to the writable per-test copy of the database.
    """
    import shutil

    from nexusLIMS import instruments as instruments_module
    from nexusLIMS.config import refresh_settings
    from nexusLIMS.db import engine as engine_module
    from nexusLIMS.db.engine import create_transient_sqlite_engine

    test_db = tmp_path / "test.db"
    shutil.copy(str(db_template), str(test_db))

    monkeypatch.setenv("NX_DB_PATH", str(test_db))
    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(TEST_INSTRUMENT_DATA_DIR))
    monkeypatch.setenv("NX_DATA_PATH", str(TEST_DATA_DIR))

    old_engine = engine_module._engine
    new_engine = create_transient_sqlite_engine(test_db)
    engine_module._engine = new_engine

    instruments_module.instrument_db.clear()
    instruments_module.instrument_db.update(
        instruments_module._get_instrument_db(db_path=test_db)
    )
    instruments_module._instrument_db_initialized = True
    refresh_settings()

    yield test_db

    new_engine.dispose()
    engine_module._engine = old_engine


# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_instrument_db(fresh_test_db):
    """
    Provide instrument database loaded from the test database.

    This fixture loads the instrument database from the per-test isolated
    database, making it easy for tests to access the instruments that were
    created by the fresh_test_db fixture.

    Parameters
    ----------
    fresh_test_db : Path
        Path to the per-test isolated database copy from fresh_test_db fixture

    Returns
    -------
    dict
        Dictionary of Instrument objects loaded from the test database
    """
    from nexusLIMS.instruments import _get_instrument_db

    # Load instrument database from the test database path
    return _get_instrument_db(db_path=fresh_test_db)


# ============================================================================
# Test Data Fixtures
# ==================================================================================
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

    return {
        "instrument_data": instrument_data_dir,
        "nexuslims_data": nexuslims_data_dir,
    }

    # Note: The directories persist across individual tests within the session,
    # but are cleaned at the start and end of each test session by the
    # docker_services fixture to ensure a clean slate for each test run


@pytest.fixture
def sample_microscopy_files(extracted_test_files):
    """
    Provide paths to sample microscopy data files for testing.

    These files are managed by the session-scoped ``extracted_test_files``
    fixture; this fixture just returns the already-extracted paths without
    re-extracting or cleaning up.  Cleanup happens at session teardown via
    ``extracted_test_files``.

    Parameters
    ----------
    extracted_test_files : dict
        Session-scoped fixture that extracts and owns the test archive.

    Yields
    ------
    list[Path]
        List of existing file paths from the test archive.
    """
    import tarfile

    archive_path = Path(__file__).parents[1] / "unit/files/test_record_files.tar.gz"
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()

    instrument_data_dir = TEST_INSTRUMENT_DATA_DIR
    return [
        instrument_data_dir / n for n in names if (instrument_data_dir / n).exists()
    ]


@pytest.fixture(scope="session")
def extracted_test_files():
    """Extract test files archive once per worker session (session-scoped).

    All workflow tests run on the same worker (via ``xdist_group("workflow")``),
    so extracting once is safe. Per-test generated metadata is cleaned up by
    ``test_environment_setup``; this fixture only cleans up the source files on
    session teardown.

    Yields
    ------
    dict
        - 'base_dir': ``TEST_INSTRUMENT_DATA_DIR``
        - 'titan_date': ``datetime(2018, 11, 13, tzinfo=America/Denver)``
        - 'jeol_date': ``datetime(2019, 7, 24, tzinfo=America/Denver)``
        - 'extracted_dirs': list of top-level directory names extracted
        - 'orion_files': dict with 'zeiss' and 'fibics' Paths (if present)
        - 'tescan_files': dict with 'tif' and 'hdr' Paths (if present)
    """
    import tarfile
    import zoneinfo
    from datetime import datetime

    archive_path = Path(__file__).parents[1] / "unit/files/test_record_files.tar.gz"
    instrument_data_dir = TEST_INSTRUMENT_DATA_DIR

    print(f"\n[*] Extracting test files to {instrument_data_dir}")
    extracted_top_level_dirs = []

    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isdir():
                top_level = member.name.split("/")[0]
                if top_level not in extracted_top_level_dirs:
                    extracted_top_level_dirs.append(top_level)
        tar.extractall(instrument_data_dir, filter="data")

    print(f"[+] Top-level directories extracted: {extracted_top_level_dirs}")

    denver_tz = zoneinfo.ZoneInfo("America/Denver")
    titan_date = datetime(2018, 11, 13, tzinfo=denver_tz)
    jeol_date = datetime(2019, 7, 24, tzinfo=denver_tz)

    orion_files = {}
    tescan_files = {}
    if "Titan_TEM" in extracted_top_level_dirs:
        titan_dir = (
            instrument_data_dir / "Titan_TEM/researcher_a/project_alpha/20181113"
        )
        zeiss_file = titan_dir / "orion-zeiss_dataZeroed.tif"
        fibics_file = titan_dir / "orion-fibics_dataZeroed.tif"
        if zeiss_file.exists():
            orion_files["zeiss"] = zeiss_file
        if fibics_file.exists():
            orion_files["fibics"] = fibics_file
        tescan_tif = titan_dir / "tescan-pfib_dataZeroed.tif"
        tescan_hdr = titan_dir / "tescan-pfib_dataZeroed.hdr"
        if tescan_tif.exists():
            tescan_files["tif"] = tescan_tif
        if tescan_hdr.exists():
            tescan_files["hdr"] = tescan_hdr

    return {
        "base_dir": instrument_data_dir,
        "titan_date": titan_date,
        "jeol_date": jeol_date,
        "extracted_dirs": extracted_top_level_dirs,
        "orion_files": orion_files,
        "tescan_files": tescan_files,
    }
    # Source files are cleaned up by docker_services teardown on the last
    # worker, which removes TEST_INSTRUMENT_DATA_DIR entirely.  Doing it here
    # would race with other workers that are still running workflow tests.


@pytest.fixture
def test_environment_setup(  # noqa: PLR0913
    docker_services_running,
    nemo_connector,
    fresh_test_db,
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
        Configured NEMO connector from fixture (mocked for test usage events)
    fresh_test_db : Path
        Per-test isolated database copy with instruments populated and empty
        session/upload log tables
    extracted_test_files : dict
        Extracted test files information
    cdcs_client : dict
        CDCS client configuration for record uploads
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Yields
    ------
    dict
        Test environment information:
        - 'instrument_pid': Instrument PID to use for testing
        - 'dt_from': Expected session start datetime
        - 'dt_to': Expected session end datetime
        - 'user': Expected username
        - 'instrument_db': Test instrument database
        - 'cdcs_client': CDCS client configuration

    Notes
    -----
    After the test completes, all records are deleted from the CDCS instance
    to ensure a clean state for subsequent tests.
    """
    from datetime import timedelta

    from nexusLIMS import instruments

    # Patch the instrument_db to use test database
    test_instrument_db = instruments._get_instrument_db(db_path=fresh_test_db)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments, "_instrument_db_initialized", True)

    # Configure eLabFTW export destination
    monkeypatch.setenv("NX_ELABFTW_URL", ELABFTW_URL)
    monkeypatch.setenv("NX_ELABFTW_API_KEY", ELABFTW_API_KEY)

    from nexusLIMS.config import refresh_settings

    refresh_settings()

    # Get Titan instrument from test database (should be FEI-Titan-TEM)
    instrument = test_instrument_db["FEI-Titan-TEM"]

    # Create expected session timespan that covers the test files
    # Files are dated 2018-11-13, so expect a session around that time
    # (the nemo_connector fixture should already be configured to return this)
    session_start = extracted_test_files["titan_date"].replace(
        hour=4, minute=0, second=0
    )
    session_end = session_start + timedelta(hours=12)

    print("\n[+] Test environment configured")
    print(f"    Instrument: {instrument.name}")
    print(f"    Expected session time: {session_start} to {session_end}")
    print("    Expected user: captain")

    from nexusLIMS.utils import cdcs as cdcs_utils

    # Snapshot CDCS record IDs before test runs
    before_cdcs_ids = {r["id"] for r in cdcs_utils.search_records() or []}

    # Snapshot TEST_DATA_DIR subdirectories before test runs
    before_data_dirs = (
        {p.name for p in TEST_DATA_DIR.iterdir() if p.is_dir()}
        if TEST_DATA_DIR.exists()
        else set()
    )

    yield {
        "instrument_pid": instrument.name,  # instrument.name is the PID
        "dt_from": session_start,
        "dt_to": session_end,
        "user": "captain",
        "instrument_db": test_instrument_db,
        "cdcs_client": cdcs_client,
    }

    # Cleanup: Delete only CDCS records created during this test
    import shutil

    after_records = cdcs_utils.search_records() or []
    for r in after_records:
        if r["id"] not in before_cdcs_ids:
            try:
                cdcs_utils.delete_record(r["id"])
            except Exception as e:
                print(f"[!] Failed to cleanup record {r['id']}: {e}")

    # Cleanup: Remove TEST_DATA_DIR subdirectories created during this test.
    # Skip "logs/" — it is shared across xdist workers (CLI tests write logs
    # here while workflow tests may be tearing down concurrently).  Deleting
    # it here would race with the CLI worker's runner.invoke() which holds a
    # FileHandler into that directory.  The docker_services teardown removes
    # TEST_DATA_DIR entirely at the end of the session.
    _worker_shared_dirs = {"logs"}
    if TEST_DATA_DIR.exists():
        for subdir in TEST_DATA_DIR.iterdir():
            if subdir.name in _worker_shared_dirs:
                continue
            if subdir.is_dir() and subdir.name not in before_data_dirs:
                try:
                    shutil.rmtree(subdir)
                except Exception as e:
                    print(f"[!] Failed to remove {subdir}: {e}")


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
                cmd,
                check=False,
                cwd=DOCKER_DIR,
                capture_output=True,
                text=True,
                timeout=timeout,
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
# Multi-signal Test Fixtures and Helpers
# ============================================================================


def _verify_json_metadata_accessible(metadata_url, index, total):
    """
    Verify a JSON metadata file is accessible and valid.

    Helper function used by multi-signal fileserver tests.

    Parameters
    ----------
    metadata_url : str
        URL to the JSON metadata file
    index : int
        Current file index (for logging)
    total : int
        Total number of files (for logging)

    Raises
    ------
    AssertionError
        If the metadata file is not accessible or invalid
    """
    import json

    import requests

    print(f"  [{index}/{total}] {metadata_url}")
    response = requests.get(metadata_url, timeout=10)

    assert response.status_code == 200, (
        f"Failed to access metadata JSON via fileserver: {response.status_code}\n"
        f"URL: {metadata_url}"
    )
    assert len(response.content) > 0, f"Metadata file is empty: {metadata_url}"

    # Verify it's valid JSON with nx_meta key
    try:
        metadata_json = json.loads(response.content)
        assert "nx_meta" in metadata_json, "Metadata JSON missing 'nx_meta' key"
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON in metadata file {metadata_url}: {e}")


def _get_metadata_urls_for_datasets(xml_doc, namespace):
    """
    Extract metadata JSON URLs from XML datasets.

    Helper function that builds metadata URLs based on dataset locations,
    handling both single-signal and multi-signal files.

    Parameters
    ----------
    xml_doc : lxml.etree.Element
        Parsed XML document
    namespace : str
        XML namespace (e.g., "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}")

    Returns
    -------
    list[str]
        List of metadata JSON URLs
    """
    import re

    all_datasets = xml_doc.findall(f".//{namespace}dataset")

    # Build mapping of location -> dataset names
    location_to_names = {}
    for dataset in all_datasets:
        location_el = dataset.find(f"{namespace}location")
        name_el = dataset.find(f"{namespace}name")
        if location_el is not None and name_el is not None:
            location = location_el.text
            if location not in location_to_names:
                location_to_names[location] = []
            location_to_names[location].append(name_el.text)

    # Build metadata URLs
    metadata_urls = []
    for location, names in location_to_names.items():
        if len(names) == 1:
            # Single signal
            metadata_urls.append(
                f"http://fileserver.localhost:40080/data{location}.json"
            )
        else:
            # Multi-signal - extract signal indices from names
            for name in names:
                match = re.search(r"\((\d+) of \d+\)", name)
                if match:
                    signal_idx = int(match.group(1)) - 1
                    url = f"http://fileserver.localhost:40080/data{location}_signal{signal_idx}.json"
                    metadata_urls.append(url)

    return metadata_urls


def _verify_url_accessible(url, index, total, expected_type=None):
    """
    Verify a URL is accessible via HTTP GET.

    Helper function for fileserver accessibility tests.

    Parameters
    ----------
    url : str
        URL to verify
    index : int
        Current item index (for logging)
    total : int
        Total number of items (for logging)
    expected_type : str, optional
        Expected content type (e.g., "image"). If provided, validates content type.

    Raises
    ------
    AssertionError
        If the URL is not accessible or content type doesn't match
    """
    import requests

    print(f"  [{index}/{total}] {url}")
    response = requests.get(url, timeout=10)

    assert response.status_code == 200, (
        f"Failed to access URL: {response.status_code}\nURL: {url}"
    )
    assert len(response.content) > 0, f"Content is empty: {url}"

    if expected_type == "image":
        content_type = response.headers.get("Content-Type", "")
        is_image_type = "image" in content_type
        is_image_ext = url.endswith((".png", ".jpg", ".jpeg"))
        assert is_image_type or is_image_ext, (
            f"URL doesn't appear to be an image: {content_type}\nURL: {url}"
        )


@pytest.fixture
def multi_signal_integration_record(  # noqa: PLR0913, PLR0915
    docker_services_running,
    nemo_connector,
    fresh_test_db,
    cdcs_client,
    multi_signal_test_files,
    monkeypatch,
):
    """
    Create and upload a multi-signal test record for integration tests.

    This fixture sets up multi-signal test files, creates a database session,
    runs record building, and uploads to CDCS. The generated record is cleaned
    up after the test completes.

    Parameters
    ----------
    docker_services_running : dict
        Ensures Docker services are running
    nemo_connector : NemoConnector
        Configured NEMO connector
    fresh_test_db : Path
        Per-test isolated database copy with instruments populated and empty
        session/upload log tables
    cdcs_client : dict
        CDCS client configuration
    multi_signal_test_files : list[Path]
        Multi-signal test files from unit test fixtures
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Yields
    ------
    dict
        Multi-signal record information:
        - 'record_id': CDCS record ID
        - 'record_title': Record title
        - 'xml_doc': Parsed XML document (lxml.etree.Element)
        - 'xml_path': Path to the uploaded XML file
        - 'session_identifier': Database session identifier
    """
    from datetime import datetime as dt

    from lxml import etree

    from nexusLIMS import instruments
    from nexusLIMS.builder import record_builder
    from nexusLIMS.config import refresh_settings
    from nexusLIMS.db.session_handler import Session, get_sessions_to_build

    # Explicitly set integration test directories in environment
    # (unit test fixtures may have overwritten them)
    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(TEST_INSTRUMENT_DATA_DIR))
    monkeypatch.setenv("NX_DATA_PATH", str(TEST_DATA_DIR))

    # Ensure settings are using integration test directories
    refresh_settings()

    # Patch the instrument_db to use test database
    test_instrument_db = instruments._get_instrument_db(db_path=fresh_test_db)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments, "_instrument_db_initialized", True)

    # Get the test instrument from database
    instrument = test_instrument_db.get("TEST-TOOL")
    if instrument is None:
        pytest.fail("TEST-TOOL instrument not found in database")

    # Define session times matching NEMO seed data reservation 999
    session_start = dt.fromisoformat("2025-06-15T02:00:00+00:00")
    session_end = dt.fromisoformat("2025-06-16T04:00:00+00:00")

    session = Session(
        session_identifier="https://nemo.example.com/api/usage_events/?id=999",
        instrument=instrument,
        dt_range=(session_start, session_end),
        user="captain",
    )

    # Insert session into database using SQLModel
    print("\n[*] Creating database session...")
    start_log = SessionLog(
        session_identifier=session.session_identifier,
        instrument=session.instrument.name,
        timestamp=session.dt_from,
        event_type=EventType.START,
        record_status=RecordStatus.TO_BE_BUILT,
        user=session.user,
    )
    end_log = SessionLog(
        session_identifier=session.session_identifier,
        instrument=session.instrument.name,
        timestamp=session.dt_to,
        event_type=EventType.END,
        record_status=RecordStatus.TO_BE_BUILT,
        user=session.user,
    )

    from nexusLIMS.db.engine import get_engine

    with DBSession(get_engine()) as db_session:
        db_session.add(start_log)
        db_session.add(end_log)
        db_session.commit()

    print(f"  Session created: {session.session_identifier}")

    # Run record building (skip NEMO harvesting since we already created the sessions)
    print("\n[*] Running record builder...")
    xml_files, sessions_built, *_ = record_builder.build_new_session_records(
        generate_previews=True
    )

    # Export the built records using the new export framework
    if xml_files:
        print(f"\n[*] Exporting {len(xml_files)} records to configured destinations...")
        import shutil

        from nexusLIMS.config import settings
        from nexusLIMS.exporters import export_records, was_successfully_exported

        # Export to all configured destinations
        export_results = export_records(xml_files, sessions_built)

        # Update session status based on export results
        sessions_by_file = dict(zip(xml_files, sessions_built, strict=True))
        for xml_file, session_obj in sessions_by_file.items():
            if was_successfully_exported(xml_file, export_results):
                session_obj.update_session_status(RecordStatus.COMPLETED)
                print(f"  Session {session_obj.session_identifier} marked COMPLETED")
            else:
                session_obj.update_session_status(RecordStatus.BUILT_NOT_EXPORTED)
                pytest.fail(
                    f"Export failed for {xml_file.name}. "
                    f"Session marked BUILT_NOT_EXPORTED"
                )

        # Move successfully exported files to uploaded directory
        uploaded_dir = settings.records_dir_path / "uploaded"
        uploaded_dir.mkdir(parents=True, exist_ok=True)

        files_exported = [
            f for f in xml_files if was_successfully_exported(f, export_results)
        ]
        for f in files_exported:
            shutil.copy2(f, uploaded_dir)
            Path(f).unlink()

    # Verify session was completed
    sessions_remaining = get_sessions_to_build()
    if len(sessions_remaining) > 0:
        pytest.fail(
            f"Session should be completed but found "
            f"{len(sessions_remaining)} TO_BE_BUILT"
        )

    # Get the uploaded record from the uploaded directory
    from nexusLIMS.config import settings

    uploaded_dir = settings.records_dir_path / "uploaded"
    expected_record_name = f"{session_start.date()}_TEST-TOOL_999.xml"
    record_path = uploaded_dir / expected_record_name

    if not record_path.exists():
        available_files = list(uploaded_dir.glob("*.xml"))
        pytest.fail(
            f"Expected record {expected_record_name} not found in {uploaded_dir}. "
            f"Available files: {available_files}"
        )

    # Read and parse the XML
    print(f"\n[*] Reading generated record: {expected_record_name}")
    with record_path.open(encoding="utf-8") as f:
        xml_string = f.read()

    # Validate XML against schema
    schema_doc = etree.parse(str(record_builder.XSD_PATH))
    schema = etree.XMLSchema(schema_doc)
    xml_doc = etree.fromstring(xml_string.encode())

    is_valid = schema.validate(xml_doc)
    if not is_valid:
        pytest.fail(f"XML validation failed: {schema.error_log}")

    # Get record ID from CDCS (record should already be uploaded)
    from nexusLIMS.utils import cdcs

    record_title = record_path.stem
    search_results = cdcs.search_records(title=record_title)
    if not search_results:
        pytest.fail(f"Record '{record_title}' not found in CDCS after upload")

    record_id = search_results[0]["id"]
    print(f"  Record ID: {record_id}")
    print("[+] Multi-signal record fixture setup complete")

    yield {
        "record_id": record_id,
        "record_title": record_title,
        "xml_doc": xml_doc,
        "xml_path": record_path,
        "session_identifier": session.session_identifier,
    }

    # Cleanup: Delete record from CDCS
    print("\n[*] Cleaning up multi-signal test record...")
    try:
        cdcs.delete_record(record_id)
        print(f"  Deleted record from CDCS: {record_id}")
    except Exception as e:
        print(f"[!] Failed to cleanup record {record_id}: {e}")


@pytest.fixture
def tofwerk_integration_record(  # noqa: PLR0915
    docker_services_running,
    fresh_test_db,
    extracted_test_files,
    cdcs_client,
    monkeypatch,
):
    """
    Build and upload a Tofwerk pFIB-ToF-SIMS record for integration tests.

    This fixture creates session log entries directly (no NEMO harvesting),
    runs the record builder against the Tofwerk files extracted from
    test_record_files.tar.gz, exports the result to CDCS, and yields the
    record information.  The CDCS record is deleted on teardown.

    Parameters
    ----------
    docker_services_running : dict
        Ensures Docker services are running.
    fresh_test_db : Path
        Per-test isolated database copy with instruments populated and empty
        session/upload log tables (includes Tofwerk-pFIB-TOFSIMS).
    extracted_test_files : dict
        Extracts test_record_files.tar.gz, including Tofwerk_pFIB_TOFSIMS/.
    cdcs_client : dict
        CDCS client configuration for record uploads.
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Yields
    ------
    dict
        - 'record_id': CDCS record ID
        - 'record_title': Record filename stem
        - 'xml_doc': Parsed XML document (lxml.etree.Element)
        - 'xml_path': Path to the uploaded XML file
        - 'session_identifier': Database session identifier
    """
    import shutil
    from datetime import datetime as dt

    from lxml import etree

    from nexusLIMS import instruments as instruments_module
    from nexusLIMS.builder import record_builder
    from nexusLIMS.config import refresh_settings, settings
    from nexusLIMS.db.engine import get_engine
    from nexusLIMS.db.session_handler import Session, get_sessions_to_build
    from nexusLIMS.exporters import export_records, was_successfully_exported
    from nexusLIMS.harvesters.reservation_event import ReservationEvent

    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(TEST_INSTRUMENT_DATA_DIR))
    monkeypatch.setenv("NX_DATA_PATH", str(TEST_DATA_DIR))
    refresh_settings()

    test_instrument_db = instruments_module._get_instrument_db(db_path=fresh_test_db)
    monkeypatch.setattr(instruments_module, "instrument_db", test_instrument_db)
    monkeypatch.setattr(instruments_module, "_instrument_db_initialized", True)

    instrument = test_instrument_db.get("Tofwerk-pFIB-TOFSIMS")
    if instrument is None:
        pytest.fail("Tofwerk-pFIB-TOFSIMS instrument not found in database")

    # Session window that covers the 2025-12-03 files in the archive.
    # Files have mtimes of 12:00 and 12:05 ET; use a broad window.
    session_identifier = "https://nemo.example.com/api/usage_events/?id=707"
    session_start = dt.fromisoformat("2025-12-03T10:00:00-05:00")
    session_end = dt.fromisoformat("2025-12-03T15:00:00-05:00")

    session = Session(
        session_identifier=session_identifier,
        instrument=instrument,
        dt_range=(session_start, session_end),
        user="researcher_e",
    )

    # Mock NEMO reservation lookup -- the test NEMO instance has no tool 7 or
    # usage event 707, so we return a synthetic ReservationEvent directly.
    def _mock_res_event(sess):
        return ReservationEvent(
            experiment_title="pFIB-ToF-SIMS depth profiling of multilayer film",
            instrument=sess.instrument,
            username=sess.user,
            user_full_name="Emma Researcher",
            start_time=sess.dt_from,
            end_time=sess.dt_to,
            experiment_purpose=(
                "Characterize elemental distribution in multilayer thin film"
            ),
            reservation_type="User session",
            sample_details=["Multilayer thin film on silicon substrate"],
            sample_pid=["sample-pfib-001"],
            sample_name=["Multilayer"],
            project_name=["FIB-SIMS Characterization"],
            project_id=["project-pfib-001"],
        )

    monkeypatch.setattr(
        "nexusLIMS.harvesters.nemo.res_event_from_session",
        _mock_res_event,
    )

    print("\n[*] Creating Tofwerk session log entries...")
    start_log = SessionLog(
        session_identifier=session.session_identifier,
        instrument=session.instrument.name,
        timestamp=session.dt_from,
        event_type=EventType.START,
        record_status=RecordStatus.TO_BE_BUILT,
        user=session.user,
    )
    end_log = SessionLog(
        session_identifier=session.session_identifier,
        instrument=session.instrument.name,
        timestamp=session.dt_to,
        event_type=EventType.END,
        record_status=RecordStatus.TO_BE_BUILT,
        user=session.user,
    )

    with DBSession(get_engine()) as db_session:
        db_session.add(start_log)
        db_session.add(end_log)
        db_session.commit()

    print(f"  Session created: {session.session_identifier}")

    print("\n[*] Running record builder for Tofwerk session...")
    xml_files, sessions_built, *_ = record_builder.build_new_session_records(
        generate_previews=True
    )

    if not xml_files:
        pytest.fail("Record builder produced no XML files for Tofwerk session")

    export_results = export_records(xml_files, sessions_built)

    sessions_by_file = dict(zip(xml_files, sessions_built, strict=True))
    for xml_file, session_obj in sessions_by_file.items():
        if was_successfully_exported(xml_file, export_results):
            session_obj.update_session_status(RecordStatus.COMPLETED)
        else:
            session_obj.update_session_status(RecordStatus.BUILT_NOT_EXPORTED)
            pytest.fail(f"Export failed for {xml_file.name}")

    uploaded_dir = settings.records_dir_path / "uploaded"
    uploaded_dir.mkdir(parents=True, exist_ok=True)
    files_exported = [
        f for f in xml_files if was_successfully_exported(f, export_results)
    ]
    for f in files_exported:
        shutil.copy2(f, uploaded_dir)
        f.unlink()

    remaining = get_sessions_to_build()
    if remaining:
        pytest.fail(
            f"Expected no TO_BE_BUILT sessions remaining, found {len(remaining)}"
        )

    expected_record_name = "2025-12-03_Tofwerk-pFIB-TOFSIMS_707.xml"
    record_path = uploaded_dir / expected_record_name
    if not record_path.exists():
        available = list(uploaded_dir.glob("*.xml"))
        pytest.fail(
            f"Expected record {expected_record_name} not found. Available: {available}"
        )

    print(f"\n[*] Reading generated record: {expected_record_name}")
    xml_doc = etree.fromstring(record_path.read_bytes())

    schema_doc = etree.parse(str(record_builder.XSD_PATH))
    schema = etree.XMLSchema(schema_doc)
    if not schema.validate(xml_doc):
        pytest.fail(f"XML validation failed: {schema.error_log}")

    from nexusLIMS.utils import cdcs

    record_title = record_path.stem
    search_results = cdcs.search_records(title=record_title)
    if not search_results:
        pytest.fail(f"Record '{record_title}' not found in CDCS after upload")

    record_id = search_results[0]["id"]
    print(f"  Record ID in CDCS: {record_id}")
    print("[+] Tofwerk integration record fixture setup complete")

    yield {
        "record_id": record_id,
        "record_title": record_title,
        "xml_doc": xml_doc,
        "xml_path": record_path,
        "session_identifier": session.session_identifier,
    }

    print("\n[*] Cleaning up Tofwerk integration record...")
    try:
        cdcs.delete_record(record_id)
        print(f"  Deleted record from CDCS: {record_id}")
    except Exception as e:
        print(f"[!] Failed to cleanup record {record_id}: {e}")


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

    # Skip docker logs for xfail/xpass tests — failures there are expected
    if item.get_closest_marker("xfail"):
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
                check=False,
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


# ============================================================================
# eLabFTW Integration Fixtures
# ============================================================================


@pytest.fixture
def elabftw_client(docker_services) -> "ELabFTWClient":
    """Create eLabFTW client for integration tests.

    Parameters
    ----------
    docker_services : None
        Ensures Docker services (including eLabFTW) are running

    Returns
    -------
    ELabFTWClient
        Configured eLabFTW client instance
    """
    from nexusLIMS.utils.elabftw import ELabFTWClient

    return ELabFTWClient(base_url=ELABFTW_URL, api_key=ELABFTW_API_KEY)


@pytest.fixture
def sample_xml_file(tmp_path):
    """Create sample XML record for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory

    Returns
    -------
    Path
        Path to created sample XML file
    """
    xml_file = tmp_path / "integration_test_record.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<nx:Experiment
    xmlns:nx="https://data.nist.gov/od/dm/nexus/experiment/v1.0"
    pid="test-experiment-001">
    <nx:title>Integration Test TEM Session</nx:title>
    <nx:summary>
        <nx:experimenter>Test User</nx:experimenter>
        <nx:instrument pid="FEI-Titan-TEM-1">FEI Titan TEM</nx:instrument>
        <nx:reservationStart>2025-02-01T09:00:00-05:00</nx:reservationStart>
        <nx:reservationEnd>2025-02-01T12:00:00-05:00</nx:reservationEnd>
        <nx:motivation>
            Integration testing of eLabFTW export functionality
        </nx:motivation>
    </nx:summary>
    <nx:sample id="sample-001">
        <nx:name>Test Sample</nx:name>
        <nx:description>Sample used for integration testing</nx:description>
    </nx:sample>
    <nx:acquisitionActivity seqno="1">
        <nx:startTime>2025-02-01T09:15:00-05:00</nx:startTime>
        <nx:sampleID>sample-001</nx:sampleID>
        <nx:setup>
            <nx:param name="Acceleration Voltage" unit="kV">200</nx:param>
            <nx:param name="Magnification">50000</nx:param>
            <nx:param name="Microscope Mode">TEM</nx:param>
        </nx:setup>
        <nx:dataset type="Image">
            <nx:name>image_001.dm3</nx:name>
            <nx:location>researcher_a/project_alpha/20181113/image_001.dm3</nx:location>
            <nx:description>TEM image for integration testing</nx:description>
            <nx:meta name="Exposure Time" unit="s">0.5</nx:meta>
            <nx:meta name="Detector">CCD Camera</nx:meta>
        </nx:dataset>
    </nx:acquisitionActivity>
</nx:Experiment>"""
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def export_context_elabftw(sample_xml_file, test_environment_setup, monkeypatch):
    """Create ExportContext for eLabFTW export tests.

    Parameters
    ----------
    sample_xml_file : Path
        Path to sample XML file for testing
    test_environment_setup : dict
        Test environment with populated database and configuration
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    ExportContext
        Configured export context for eLabFTW testing
    """
    from nexusLIMS.config import refresh_settings
    from nexusLIMS.exporters.base import ExportContext

    # Configure eLabFTW settings
    monkeypatch.setenv("NX_ELABFTW_URL", ELABFTW_URL)
    monkeypatch.setenv("NX_ELABFTW_API_KEY", ELABFTW_API_KEY)

    # Refresh settings to pick up environment variables
    refresh_settings()

    # Create export context using test environment data
    return ExportContext(
        xml_file_path=sample_xml_file,
        session_identifier="integration-test-2025-01-27",
        instrument_pid=test_environment_setup["instrument_pid"],
        dt_from=test_environment_setup["dt_from"],
        dt_to=test_environment_setup["dt_to"],
        user=test_environment_setup["user"],
    )
