"""Set up pytest configuration."""

# pylint: disable=unused-argument
# ruff: noqa: ARG001, SLF001

import os
import shutil
import sqlite3
from datetime import datetime as dt
from datetime import timedelta as td
from pathlib import Path

# ============================================================================
# CRITICAL: Set test environment variables BEFORE any nexusLIMS imports
# ============================================================================
# The Settings class in nexusLIMS.config is instantiated at module import time,
# so we MUST set environment variables before any nexusLIMS module is imported.

# Define paths for test database and data directories
_test_files_dir = Path(__file__).parent / "files"
_nexuslims_path = _test_files_dir / "NexusLIMS"
_instr_data_path = _test_files_dir / "InstrumentData"

# Create the directories
_nexuslims_path.mkdir(exist_ok=True)
_instr_data_path.mkdir(exist_ok=True)

# Define path for dynamically-created test database
_test_db_path = _nexuslims_path / "test_db.sqlite"

# Create empty database with tables if it doesn't exist
if not _test_db_path.exists():
    conn = sqlite3.connect(_test_db_path)
    cursor = conn.cursor()
    # Create empty tables (will be populated by fresh_test_db fixture)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            instrument_pid VARCHAR(100) NOT NULL PRIMARY KEY,
            api_url TEXT NOT NULL UNIQUE,
            calendar_name TEXT NOT NULL,
            calendar_url TEXT NOT NULL,
            location VARCHAR(100) NOT NULL,
            schema_name TEXT NOT NULL,
            property_tag VARCHAR(20) NOT NULL,
            filestore_path TEXT NOT NULL,
            computer_name TEXT UNIQUE,
            computer_ip VARCHAR(15) UNIQUE,
            computer_mount TEXT,
            harvester TEXT,
            timezone TEXT DEFAULT 'America/New_York' NOT NULL
        )
    """,
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS session_log (
            id_session_log INTEGER PRIMARY KEY AUTOINCREMENT,
            session_identifier TEXT NOT NULL,
            instrument TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            record_status TEXT DEFAULT 'TO_BE_BUILT',
            user TEXT
        )
    """,
    )
    conn.commit()
    conn.close()

# Set environment variables to use test paths
# CRITICAL: This MUST happen before importing nexusLIMS.config
os.environ["NX_DB_PATH"] = str(_test_db_path)
os.environ["NX_DATA_PATH"] = str(_nexuslims_path)
os.environ["NX_INSTRUMENT_DATA_PATH"] = str(_instr_data_path)

# Set test-specific config to override .env file
# Use JSON format for list values (pydantic-settings requirement)
os.environ["NX_IGNORE_PATTERNS"] = '["*.mib", "*.db", "*.emi"]'
os.environ["NX_FILE_STRATEGY"] = "exclusive"

# Set dummy CDCS environment variables so tests can run independent of
# the local .env file (these are not used, since only unit tests are done
# and there's no integration testing to an actual CDCS server at this moment)
os.environ["NX_CDCS_URL"] = "https://cdcs.example.com"
os.environ["NX_CDCS_USER"] = "username"
os.environ["NX_CDCS_PASS"] = "dummy_password"
os.environ["NX_CERT_BUNDLE"] = (
    "-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----"
)

# Create required directory structure
(_nexuslims_path / "test_files").mkdir(parents=True, exist_ok=True)

# ============================================================================
# NOW it's safe to import nexusLIMS modules
# ============================================================================

import pytest  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402

from nexusLIMS.config import settings  # noqa: E402
from nexusLIMS.utils import current_system_tz  # noqa: E402

from .utils import delete_files, extract_files  # noqa: E402

# Load fixtures from fixtures modules
pytest_plugins = ["tests.fixtures.cdcs_mock_data"]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """
    Clear settings cache after each test to prevent pollution.

    This ensures that any environment variable changes made during a test
    don't leak into subsequent tests. Tests that modify environment variables
    should call refresh_settings() to pick up the changes.
    """
    yield

    # Clear the settings cache so next test gets fresh settings
    from nexusLIMS.config import clear_settings

    clear_settings()


def pytest_configure(config):
    """
    Configure pytest.

    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest
    file after command line options have been parsed.

    Note: The test database extraction now happens at module level (before imports)
    to ensure it's available when nexusLIMS.instruments is imported.
    """


def pytest_unconfigure(config):
    """
    Unconfigure pytest.

    Clean up the temporary directories created for the test session.
    This includes the NexusLIMS and InstrumentData subdirectories in tests/files.
    """
    from nexusLIMS.config import settings  # pylint: disable=import-outside-toplevel

    # Paths are now subdirectories of tests/files
    nexuslims_path = Path(settings.NX_DATA_PATH)
    instr_data_path = Path(settings.NX_INSTRUMENT_DATA_PATH)
    test_files_dir = Path(__file__).parent / "files"

    # Clean up the created directories, with safety checks
    if nexuslims_path.exists() and nexuslims_path.parent == test_files_dir:
        shutil.rmtree(nexuslims_path)

    if instr_data_path.exists() and instr_data_path.parent == test_files_dir:
        shutil.rmtree(instr_data_path)

    # The old logic also removed a 'records' directory.
    # Let's see if it exists and remove it if it's inside tests/files.
    records_dir = test_files_dir / "records"
    if records_dir.exists():
        shutil.rmtree(records_dir)


@pytest.fixture(scope="session")
def monkey_session():
    """Monkeypatch a whole Pytest session."""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope="session", name="mock_nemo_env", autouse=True)
def mock_nemo_env_fixture(monkey_session):
    """
    Set up mock NEMO environment variables for testing.

    This fixture provides a basic NEMO configuration that allows
    tests to run without requiring a real NEMO instance. Auto-used
    for all tests unless NEMO environment variables are already set.
    """
    import os  # pylint: disable=import-outside-toplevel

    # Only set if not already set (allows real NEMO testing if env vars exist)
    if "NX_NEMO_ADDRESS_1" not in os.environ:
        monkey_session.setenv("NX_NEMO_ADDRESS_1", "https://nemo.example.com/api/")
        monkey_session.setenv("NX_NEMO_TOKEN_1", "test-token-12345")
        monkey_session.setenv("NX_NEMO_TZ_1", "America/Denver")


@pytest.fixture(scope="session", name="_fix_mountain_time")
# pylint: disable=redefined-outer-name
def _fix_mountain_time(monkey_session):
    """
    Fix datetimes for MT/ET difference.

    Hack to determine if we need to adjust our datetime objects for the time
    difference between Boulder and G'burg.
    """
    import nexusLIMS.utils  # pylint: disable=import-outside-toplevel

    tz_string = current_system_tz().tzname(dt.now(tz=current_system_tz()))

    # if timezone is MST or MDT, we're 2 hours behind, so we need to adjust
    # datetime objects to match file store
    if tz_string in ["MST", "MDT"]:
        # get current timezone, and adjust tz_offset as needed
        monkey_session.setattr(nexusLIMS.utils, "tz_offset", td(hours=-2))
        monkey_session.setenv("ignore_mib", "True")
        monkey_session.setenv("is_mountain_time", "True")


@pytest.fixture(name="_cleanup_session_log")
def cleanup_session_log():
    """
    Cleanup the session log after a test.

    This fixture removes the rows for the usage event added in
    test_usage_event_to_session_log, so it doesn't mess up future record building tests.
    """
    # pylint: disable=import-outside-toplevel
    yield None
    from nexusLIMS.db.session_handler import db_query

    to_remove = (
        "https://nemo.example.com/api/usage_events/?id=29",
        "https://nemo.example.com/api/usage_events/?id=30",
        "https://nemo.example.com/api/usage_events/?id=31",
        "test_session",
    )
    db_query(
        f"DELETE FROM session_log WHERE session_identifier IN "
        f"({','.join('?' * len(to_remove))})",
        to_remove,
    )


# test file fixtures


# 643 Titan files
@pytest.fixture(scope="module")
def eftem_diff():
    """Titan EFTEM example diffraction."""
    files = extract_files("TITAN_EFTEM_DIFF")
    yield files
    delete_files("TITAN_EFTEM_DIFF")


@pytest.fixture(scope="module")
def stem_stack_titan():
    """Titan example STEM stack."""
    files = extract_files("TITAN_STEM_STACK")
    yield files
    delete_files("TITAN_STEM_STACK")


@pytest.fixture(scope="module")
def survey_titan():
    """Titan example survey image."""
    files = extract_files("TITAN_SURVEY_IMAGE")
    yield files
    delete_files("TITAN_SURVEY_IMAGE")


@pytest.fixture(scope="module")
def eels_si_titan():
    """Titan STEM example EELS spectrum image."""
    files = extract_files("TITAN_EELS_SI")
    yield files
    delete_files("TITAN_EELS_SI")


@pytest.fixture(scope="module")
def eels_proc_int_bg_titan():
    """Titan example EELS SI with processing integration and background removal."""
    files = extract_files("TITAN_EELS_PROC_INT_BG")
    yield files
    delete_files("TITAN_EELS_PROC_INT_BG")


@pytest.fixture(scope="module")
def eels_proc_thick_titan():
    """Titan example EELS spectrum image with thickness calculation."""
    files = extract_files("TITAN_EELS_PROC_THICK")
    yield files
    delete_files("TITAN_EELS_PROC_THICK")


@pytest.fixture(scope="module")
def eds_si_titan():
    """Titan example EDS spectrum image."""
    files = extract_files("TITAN_EDS_SI")
    yield files
    delete_files("TITAN_EDS_SI")


@pytest.fixture(scope="module")
def eels_si_drift_titan():
    """Titan STEM example EELS spectrum image with drift correction."""
    files = extract_files("TITAN_EELS_SI_DRIFT")
    yield files
    delete_files("TITAN_EELS_SI_DRIFT")


@pytest.fixture(scope="module")
def annotations():
    """643 Titan example image with annotations."""
    files = extract_files("ANNOTATIONS")
    yield files
    delete_files("ANNOTATIONS")


@pytest.fixture(scope="module")
def four_d_stem():
    """4D STEM example."""
    files = extract_files("4D_STEM")
    yield files
    delete_files("4D_STEM")


@pytest.fixture(scope="module")
def fft():
    """FFT example."""
    files = extract_files("FFT")
    yield files
    delete_files("FFT")


@pytest.fixture(scope="module")
def corrupted_file():
    """Corrupted dm3 file example."""
    files = extract_files("CORRUPTED")
    yield files
    delete_files("CORRUPTED")


# JEOL 3010 files


@pytest.fixture(scope="module")
def jeol3010_diff():
    """JEOL 3010 example diffraction image."""
    files = extract_files("JEOL3010_DIFF")
    yield files
    delete_files("JEOL3010_DIFF")


# 642 Titan files


@pytest.fixture(scope="module")
def stem_diff():
    """Titan STEM diffraction."""
    files = extract_files("TITAN_STEM_DIFF")
    yield files
    delete_files("TITAN_STEM_DIFF")


@pytest.fixture(scope="module")
def opmode_diff():
    """STEM diffraction (in operation mode) from Titan."""
    files = extract_files("TITAN_OPMODE_DIFF")
    yield files
    delete_files("TITAN_OPMODE_DIFF")


@pytest.fixture(scope="module")
def eels_proc_1_titan():
    """EELS processing metadata from Titan."""
    files = extract_files("TITAN_EELS_PROC_1")
    yield files
    delete_files("TITAN_EELS_PROC_1")


@pytest.fixture(scope="module")
def eels_si_drift():
    """EELS SI drift correction metadata from Titan."""
    files = extract_files("EELS_SI_DRIFT")
    yield files
    delete_files("EELS_SI_DRIFT")


@pytest.fixture(scope="module")
def tecnai_mag():
    """Tecnai magnification metadata from 642 Titan."""
    files = extract_files("TECNAI_MAG")
    yield files
    delete_files("TECNAI_MAG")


# Quanta tiff files


@pytest.fixture(scope="module")
def quanta_test_file():
    """Quanta example."""
    files = extract_files("QUANTA_TIF")
    yield files
    delete_files("QUANTA_TIF")


@pytest.fixture(scope="module")
def quanta_32bit_test_file():
    """Quanta 32 bit example."""
    files = extract_files("QUANTA_32BIT")
    yield files
    delete_files("QUANTA_32BIT")


@pytest.fixture(scope="module")
def quanta_no_beam_meta():
    """Quanta example with no beam, scan, or system metadata."""
    files = extract_files("QUANTA_NO_BEAM")
    yield files
    delete_files("QUANTA_NO_BEAM")


@pytest.fixture(scope="module")
def scios_multiple_gis_meta():
    """Scios FIB example tif with duplicate metadata sections."""
    files = extract_files("SCIOS_DUPLICATE_META_TIF")
    yield files
    delete_files("SCIOS_DUPLICATE_META_TIF")


@pytest.fixture(scope="module")
def scios_xml_metadata():
    """Scios FIB example tif with XML metadata embedded at the end."""
    files = extract_files("SCIOS_XML_META_TIF")
    yield files
    delete_files("SCIOS_XML_META_TIF")


# other assorted files


@pytest.fixture(scope="module")
def parse_meta_titan():
    """642 Titan file for metadata parsing test."""
    files = extract_files("PARSE_META_TITAN")
    yield files
    delete_files("PARSE_META_TITAN")


@pytest.fixture(scope="module")
def list_signal():
    """Signal returning a signal list."""
    files = extract_files("LIST_SIGNAL")
    yield files
    delete_files("LIST_SIGNAL")


@pytest.fixture(scope="module")
def fei_ser_files():
    """FEI .ser/.emi test files."""
    files = extract_files("FEI_SER")
    yield files
    delete_files("FEI_SER")


@pytest.fixture
def fei_ser_files_function_scope():
    """FEI .ser/.emi test files."""
    files = extract_files("FEI_SER")
    yield files
    delete_files("FEI_SER")


# plain test files (not in .tar.gz archives, so do not need to delete at end)


@pytest.fixture(scope="module")
def basic_txt_file():
    """Plain txt file for basic extractor test."""
    return Path(__file__).parent / "files" / "basic_test.txt"


@pytest.fixture(scope="module")
def basic_txt_file_no_extension():
    """Plain txt file with no extension for basic extractor test."""
    return Path(__file__).parent / "files" / "basic_test_no_extension"


@pytest.fixture(scope="module")
def stem_image_dm3():
    """Small dm3 file for zeroing data test."""
    return Path(__file__).parent / "files" / "test_STEM_image.dm3"


@pytest.fixture(scope="module")
def quanta_bad_metadata():
    """Quanta tif file with bad metadata."""
    return Path(__file__).parent / "files" / "quanta_bad_metadata.tif"


@pytest.fixture(scope="module")
def quanta_just_modded_mdata():
    """Quanta tif file with modified metadata."""
    return Path(__file__).parent / "files" / "quanta_just_modded_mdata.tif"


@pytest.fixture(scope="module")
def text_paragraph_test_file():
    """Text file imitating a natural language note to self."""
    return Path(__file__).parent / "files" / "text_preview_test_paragraph.txt"


@pytest.fixture(scope="module")
def text_data_test_file():
    """Text file imitating textual data output, e.g. column data."""
    return Path(__file__).parent / "files" / "text_preview_test_data.txt"


@pytest.fixture(scope="module")
def text_ansi_test_file():
    """Text file in ansi format from JEOL SEMs."""
    return Path(__file__).parent / "files" / "text_preview_jeol_ansi.txt"


@pytest.fixture(scope="module")
def basic_image_file():
    """Image file that is not data, e.g. a screenshot."""
    extract_files("IMAGE_FILES")
    yield (
        Path(__file__).parent
        / "files"
        / str(settings.NX_INSTRUMENT_DATA_PATH)
        / "test_image_thumb_source.bmp"
    )
    delete_files("IMAGE_FILES")


@pytest.fixture(scope="module")
def image_thumb_source_gif():
    """Image file in GIF format for thumbnail testing."""
    extract_files("IMAGE_FILES")
    yield (
        Path(__file__).parent
        / "files"
        / str(settings.NX_INSTRUMENT_DATA_PATH)
        / "test_image_thumb_source.gif"
    )
    delete_files("IMAGE_FILES")


@pytest.fixture(scope="module")
def image_thumb_source_png():
    """Image file in PNG format for thumbnail testing."""
    extract_files("IMAGE_FILES")
    yield (
        Path(__file__).parent
        / "files"
        / str(settings.NX_INSTRUMENT_DATA_PATH)
        / "test_image_thumb_source.png"
    )
    delete_files("IMAGE_FILES")


@pytest.fixture(scope="module")
def image_thumb_source_tif():
    """Image file in TIF format for thumbnail testing."""
    extract_files("IMAGE_FILES")
    yield (
        Path(__file__).parent
        / "files"
        / str(settings.NX_INSTRUMENT_DATA_PATH)
        / "test_image_thumb_source.tif"
    )
    delete_files("IMAGE_FILES")


@pytest.fixture(scope="module")
def image_thumb_source_jpg():
    """Image file in JPG format for thumbnail testing."""
    extract_files("IMAGE_FILES")
    yield (
        Path(__file__).parent
        / "files"
        / str(settings.NX_INSTRUMENT_DATA_PATH)
        / "test_image_thumb_source.jpg"
    )
    delete_files("IMAGE_FILES")


@pytest.fixture(scope="module")
def unreadable_image_file():
    """File with a .jpg extension that is not readable as an image."""
    return Path(__file__).parent / "files" / "unreadable_image.jpg"


@pytest.fixture(scope="module")
def binary_text_file():
    """File with a .txt extension that is not readable as plaintext."""
    return Path(__file__).parent / "files" / "binary_text.txt"


# XML record test file


@pytest.fixture(scope="module")
def xml_record_file():
    """Test XML record."""
    files = extract_files("RECORD")
    yield files
    delete_files("RECORD")


# CDCS mocking fixtures


@pytest.fixture
def test_xml_record_file(tmp_path):
    """Create a temporary test XML record file for CDCS upload tests."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<nx:Experiment xmlns:nx="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <nx:summary>
        <nx:title>Test Record</nx:title>
        <nx:instrument pid="test-instrument">Test Instrument</nx:instrument>
        <nx:creationDate>2025-01-15T10:00:00</nx:creationDate>
    </nx:summary>
</nx:Experiment>"""

    # Create test XML file
    xml_file = tmp_path / "test_record.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    # Create figs subdirectory for no-files test
    (tmp_path / "figs").mkdir()

    return [xml_file]


@pytest.fixture
def mock_cdcs_server(monkeypatch, mock_cdcs_responses):
    """
    Mock the CDCS server by patching nexus_req to return mock responses.

    This fixture intercepts all HTTP calls to the CDCS API and returns
    appropriate mock responses based on the URL and HTTP method.
    """
    from http import HTTPStatus
    from typing import NamedTuple
    from urllib.parse import urlparse

    import nexusLIMS.cdcs

    class MockResponse(NamedTuple):
        """Mock HTTP response."""

        status_code: int
        text: str

        def json(self):
            """Return JSON response data."""
            import json

            return json.loads(self.text)

    # Track created record IDs for delete operations
    created_records = set()

    def mock_nexus_req(url, method, **kwargs):
        """Mock HTTP request handler."""
        parsed = urlparse(url)
        path = parsed.path

        # GET /rest/workspace/read_access
        if path.endswith("/rest/workspace/read_access") and method == "GET":
            import json

            return MockResponse(
                status_code=HTTPStatus.OK,
                text=json.dumps(mock_cdcs_responses["workspace"]),
            )

        # GET /rest/template-version-manager/global
        if path.endswith("/rest/template-version-manager/global") and method == "GET":
            import json

            return MockResponse(
                status_code=HTTPStatus.OK,
                text=json.dumps(mock_cdcs_responses["template"]),
            )

        # POST /rest/data/
        if path.endswith("/rest/data/") and method == "POST":
            import json
            import uuid

            # Generate a unique record ID
            record_id = f"test-record-{uuid.uuid4().hex[:12]}"
            created_records.add(record_id)

            response_data = {
                "id": record_id,
                "template": mock_cdcs_responses["template"][0]["current"],
                "title": kwargs.get("json", {}).get("title", "Test Record"),
                "xml_content": kwargs.get("json", {}).get("xml_content", ""),
            }

            return MockResponse(
                status_code=HTTPStatus.CREATED,
                text=json.dumps(response_data),
            )

        # Handle workspace assignment endpoint
        if "/rest/data/" in path and "/assign/" in path and method == "PATCH":
            return MockResponse(status_code=HTTPStatus.OK, text="{}")

        # Handle record deletion endpoint
        if "/rest/data/" in path and method == "DELETE":
            return MockResponse(status_code=HTTPStatus.NO_CONTENT, text="")

        # Return 404 for unknown endpoints
        return MockResponse(
            status_code=HTTPStatus.NOT_FOUND,
            text="Mock endpoint not found",
        )

    # Patch the nexus_req function in the cdcs module
    monkeypatch.setattr(nexusLIMS.cdcs, "nexus_req", mock_nexus_req)


@pytest.fixture(scope="module")
def test_record_files():
    """
    Test record files for file finding and record building tests.

    Extracts test files from test_record_files.tar.gz which contains:
    - Titan_TEM/researcher_a/project_alpha/20181113/
      (8 .dm3 files, 2 .ser files, 1 .emi file, 4 test files)
    - JEOL_TEM/researcher_b/project_beta/20190724/
      (3 subdirectories with .dm3 files)
    - Nexus_Test_Instrument/test_files/ (4 sample .dm3 files)

    Files have specific modification times for temporal file-finding tests.
    """
    files = extract_files("TEST_RECORD_FILES")
    yield files
    delete_files("TEST_RECORD_FILES")


@pytest.fixture(autouse=True)
def fresh_test_db():
    """
    Populate test database with test instruments and sessions.

    Populates the database with:
    - Five test instruments: FEI-Titan-STEM, FEI-Titan-TEM, FEI-Quanta-ESEM,
      JEOL-JEM-TEM, testtool-TEST-A1234567
    - Test sessions for Titan_TEM, JEOL_TEM, and Nexus_Test_Instrument matching
      test file dates

    This replaces the static test_db.sqlite.tar.gz approach with
    dynamic database construction for cleaner, more maintainable tests.

    Function-scoped and autouse=True ensures each test gets a fresh database,
    preventing test isolation issues.
    """
    # Connect to existing database (schema created during conftest initialization)
    db_path = _test_db_path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear any existing data to ensure clean state for each test
    cursor.execute("DELETE FROM session_log")
    cursor.execute("DELETE FROM instruments")

    # Insert test instruments
    # Match the tool IDs from test_instrument_factory.py and mock NEMO responses
    instruments = [
        # FEI Titan STEM (id=1)
        (
            "FEI-Titan-STEM",
            "https://nemo.example.com/api/tools/?id=1",
            "FEI Titan TEM",
            "https://nemo.example.com/calendar/titan-stem/",
            "Test Building Room 300",
            "Titan TEM",
            "TEST-STEM-001",
            "./Titan_STEM",
            None,
            None,
            None,
            "nemo",
            "America/New_York",
        ),
        # FEI Titan TEM (id=2)
        (
            "FEI-Titan-TEM",
            "https://nemo.example.com/api/tools/?id=2",
            "FEI Titan TEM",
            "https://nemo.example.com/calendar/titan/",
            "Test Building Room 301",
            "FEI Titan TEM",
            "TEST-TEM-001",
            "./Titan_TEM",
            None,
            None,
            None,
            "nemo",
            "America/New_York",
        ),
        # FEI Quanta ESEM (id=3)
        (
            "FEI-Quanta-ESEM",
            "https://nemo.example.com/api/tools/?id=3",
            "FEI Quanta 200 ESEM",
            "https://nemo.example.com/calendar/quanta/",
            "Test Building Room 302",
            "Quanta FEG 200",
            "TEST-SEM-001",
            "./Quanta",
            None,
            None,
            None,
            "nemo",
            "America/New_York",
        ),
        # JEOL TEM (id=5)
        (
            "JEOL-JEM-TEM",
            "https://nemo.example.com/api/tools/?id=5",
            "JEOL 3010 TEM",
            "https://nemo.example.com/calendar/jeol/",
            "Test Building Room 303",
            "JEOL JEM-3010",
            "TEST-JEOL-001",
            "./JEOL_TEM",
            None,
            None,
            None,
            "nemo",
            "America/Chicago",
        ),
        # Generic test tool (id=6)
        (
            "testtool-TEST-A1234567",
            "https://nemo.example.com/api/tools/?id=6",
            "Test Tool",
            "https://nemo.example.com/calendar/test-tool/",
            "Test Building Room 400",
            "Test Tool",
            "TEST-TOOL-001",
            "./Nexus_Test_Instrument",
            None,
            None,
            None,
            "nemo",
            "America/Denver",
        ),
        # Test Tool for NEMO connector tests (id=10)
        (
            "test-tool-10",
            "https://nemo.example.com/api/tools/?id=10",
            "Test Tool",
            "https://nemo.example.com/calendar/test-tool-10/",
            "Test Building Room 100",
            "Test Tool",
            "TEST-TOOL-010",
            "./Test_Tool_10",
            None,
            None,
            None,
            "nemo",
            "America/Denver",
        ),
    ]

    cursor.executemany(
        """
        INSERT INTO instruments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        instruments,
    )

    # Insert test sessions matching the test data files
    # Session identifiers use URL format with ID parameter for proper
    # filename generation
    sessions = [
        # Titan TEM session (2018-11-13) - tool_id=2
        (
            "https://nemo.example.com/api/usage_events/?id=101",
            "FEI-Titan-TEM",
            "2018-11-13T13:00:00-05:00",
            "START",
            "TO_BE_BUILT",
            "researcher_a",
        ),
        (
            "https://nemo.example.com/api/usage_events/?id=101",
            "FEI-Titan-TEM",
            "2018-11-13T16:00:00-05:00",
            "END",
            "TO_BE_BUILT",
            "researcher_a",
        ),
        # JEOL TEM session (2019-07-24) - tool_id=5
        (
            "https://nemo.example.com/api/usage_events/?id=202",
            "JEOL-JEM-TEM",
            "2019-07-24T11:00:00-04:00",
            "START",
            "TO_BE_BUILT",
            "researcher_b",
        ),
        (
            "https://nemo.example.com/api/usage_events/?id=202",
            "JEOL-JEM-TEM",
            "2019-07-24T16:00:00-04:00",
            "END",
            "TO_BE_BUILT",
            "researcher_b",
        ),
        # Test Tool session (2021-08-02) - tool_id=6
        (
            "https://nemo.example.com/api/usage_events/?id=303",
            "testtool-TEST-A1234567",
            "2021-08-02T10:00:00-06:00",
            "START",
            "TO_BE_BUILT",
            "test_user",
        ),
        (
            "https://nemo.example.com/api/usage_events/?id=303",
            "testtool-TEST-A1234567",
            "2021-08-02T18:00:00-06:00",
            "END",
            "TO_BE_BUILT",
            "test_user",
        ),
    ]

    cursor.executemany(
        """
        INSERT INTO session_log
        (session_identifier, instrument, timestamp, event_type, record_status, user)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        sessions,
    )

    conn.commit()
    conn.close()

    # Reload the instrument_db to pick up the new instruments
    # This is necessary because instrument_db is populated at module import time
    # and needs to be refreshed with the newly populated test data
    from nexusLIMS import instruments

    instruments.instrument_db.clear()
    instruments.instrument_db.update(instruments._get_instrument_db(db_path=db_path))

    return db_path

    # Cleanup is handled by pytest teardown


# Instrument factory fixtures for reducing database dependencies


@pytest.fixture
def mock_instrument_from_filepath(monkeypatch):
    """
    Mock get_instr_from_filepath in extractor modules.

    This fixture returns a function that accepts an Instrument object and
    monkeypatches the get_instr_from_filepath function in all relevant
    extractor modules to return that instrument.

    This allows tests to explicitly specify what instrument they need without
    relying on database entries.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest's monkeypatch fixture

    Returns
    -------
    function
        A function that accepts an Instrument and sets up the monkeypatch

    Examples
    --------
    In a test:
        >>> def test_something(mock_instrument_from_filepath):
        ...     from tests.test_instrument_factory import make_titan_stem
        ...     instrument = make_titan_stem()
        ...     mock_instrument_from_filepath(instrument)
        ...     # Now any code calling get_instr_from_filepath gets this instrument
        ...     metadata = parse_metadata("some_file.dm3")
    """

    def _mock(instrument):
        """Apply the monkeypatch for the given instrument."""
        # Import here to avoid circular imports
        import nexusLIMS.extractors
        import nexusLIMS.extractors.digital_micrograph
        import nexusLIMS.extractors.fei_emi
        import nexusLIMS.extractors.utils

        # Monkeypatch all the places where get_instr_from_filepath is called
        monkeypatch.setattr(
            nexusLIMS.extractors.digital_micrograph,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.fei_emi,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors,
            "get_instr_from_filepath",
            lambda _: instrument,
        )

    return _mock
