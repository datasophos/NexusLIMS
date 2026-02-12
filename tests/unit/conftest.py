"""Set up pytest configuration."""

# pylint: disable=unused-argument

import contextlib
import os
import shutil
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

# Set environment variables BEFORE create_test_database, because that call
# imports nexusLIMS.db.models → nexusLIMS.db.engine, which creates the engine
# singleton from settings.NX_DB_PATH.  If the env vars aren't set yet the
# singleton ends up pointing at the root-conftest temp path (no schema).
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
os.environ["NX_CDCS_TOKEN"] = "test-api-token-not-for-production"
os.environ["NX_CERT_BUNDLE"] = (
    "-----BEGIN CERTIFICATE-----\nDUMMY\n-----END CERTIFICATE-----"
)

# Create required directory structure
(_nexuslims_path / "test_files").mkdir(parents=True, exist_ok=True)

# Create database using shared function from top-level conftest
# This ensures consistency between unit and integration test databases
from tests.conftest import create_test_database  # noqa: E402

create_test_database(_test_db_path)

# ============================================================================
# NOW it's safe to import nexusLIMS modules
# ============================================================================

import pytest  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402

from nexusLIMS.config import settings  # noqa: E402
from nexusLIMS.utils.time import current_system_tz  # noqa: E402

# Import context fixtures for marker-based resource allocation
# These must be imported directly (not via pytest_plugins) to avoid conflicts
# when running integration tests alongside unit tests
from .fixtures.contexts import (  # noqa: E402, F401
    db_context,
    file_context,
    settings_context,
)
from .utils import delete_files, extract_files  # noqa: E402


@pytest.fixture(autouse=True)
def reset_unit_test_environment(request):
    """
    Reset all singletons before and after each unit test.

    This fixture ensures complete isolation between unit tests by resetting
    all module-level singletons (database engine, instrument cache, settings,
    etc.) before each test runs.

    Skips tests marked with @pytest.mark.needs_db as those tests use db_context
    which handles engine/cache reset internally to avoid conflicts.

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object to check for markers

    Notes
    -----
    This is the primary defense against test pollution in the unit test suite.
    It runs before db_context, file_context, and other resource fixtures to
    ensure a clean slate.
    """
    from tests.fixtures.core import SingletonResetter

    # Skip if test uses db_context (marker-based database)
    # db_context handles its own engine/cache management
    if request.node.get_closest_marker("needs_db"):
        yield
        return

    # Reset all singletons before test
    SingletonResetter.reset_all()

    yield  # Test runs here

    # Reset all singletons after test to prevent pollution
    SingletonResetter.reset_all()


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """
    Clear settings cache before and after each test to prevent pollution.

    This ensures that any environment variable changes made during a test
    don't leak into subsequent tests. Tests that modify environment variables
    should call refresh_settings() to pick up the changes.

    Notes
    -----
    This fixture is kept for backwards compatibility and as an additional
    safety net. The primary cleanup is now handled by reset_unit_test_environment.
    """
    # Clear BEFORE test (in case previous test left pollution)
    from nexusLIMS.config import clear_settings

    clear_settings()

    yield  # Test runs here

    # Clear AFTER test (to prevent pollution to next test)
    clear_settings()


@pytest.fixture
def isolated_env():
    """
    Provide fully isolated environment for tests that need maximum isolation.

    This fixture is for special cases where a test needs complete isolation
    from all other tests, including those that might be running in parallel
    or have left unexpected state.

    Use this fixture when:
    - Testing singleton behavior itself
    - Debugging test pollution issues
    - Tests that modify global state in unusual ways

    Example
    -------
    >>> def test_something_with_isolation(isolated_env):
    ...     # Your test code here
    ...     pass

    Yields
    ------
    None
        Context manager provides isolation, no value is yielded
    """
    from tests.fixtures.core import isolated_environment

    with isolated_environment():
        yield


def pytest_configure(config):
    """
    Configure pytest.

    Allows plugins and conftest files to perform initial configuration.
    This hook is called for every plugin and initial conftest
    file after command line options have been parsed.

    Note: The test database extraction now happens at module level (before imports)
    to ensure it's available when nexusLIMS.instruments is imported.
    """
    # Register custom markers for test organization
    config.addinivalue_line("markers", "unit: Unit tests (isolated, fast)")
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (require Docker services)",
    )
    config.addinivalue_line("markers", "slow: Tests that take significant time to run")
    config.addinivalue_line(
        "markers",
        "network: Tests that require network connectivity",
    )
    config.addinivalue_line(
        "markers",
        "database: Tests that interact with database",
    )
    config.addinivalue_line(
        "markers",
        "harvester: Tests for harvester modules (NEMO, SharePoint)",
    )
    # Phase 1: New marker-based resource allocation markers
    config.addinivalue_line(
        "markers",
        "needs_db: Opt-in to database setup (use: @pytest.mark.needs_db or"
        "@pytest.mark.needs_db(instruments=['FEI-Titan-TEM']))",
    )
    config.addinivalue_line(
        "markers",
        "needs_files: Opt-in to file extraction (use:"
        "@pytest.mark.needs_files('QUANTA_TIF', 'FEI_SER'))",
    )
    config.addinivalue_line(
        "markers",
        "needs_settings: Opt-in to custom settings (use:"
        "@pytest.mark.needs_settings(NX_FILE_STRATEGY='inclusive'))",
    )
    config.addinivalue_line(
        "markers",
        "extractor: Tests for metadata extractor modules",
    )
    config.addinivalue_line(
        "markers",
        "record_builder: Tests for record builder functionality",
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test items after collection.

    This hook automatically injects fixture dependencies based on markers.
    Tests marked with @pytest.mark.needs_db will automatically get db_context,
    tests with @pytest.mark.needs_files will get file_context, etc.

    This enables the new marker-based resource allocation system where tests
    explicitly opt-in to resources they need, rather than auto-loading everything.

    Phase 2 implementation detail: This hook bridges markers to fixtures.
    """
    for item in items:
        # Auto-inject db_context for tests with needs_db marker
        if (
            item.get_closest_marker("needs_db")
            and "db_context" not in item.fixturenames
        ):
            item.fixturenames.append("db_context")

        # Auto-inject file_context for tests with needs_files marker
        if (
            item.get_closest_marker("needs_files")
            and "file_context" not in item.fixturenames
        ):
            item.fixturenames.append("file_context")

        # Auto-inject settings_context for tests with needs_settings marker
        if (
            item.get_closest_marker("needs_settings")
            and "settings_context" not in item.fixturenames
        ):
            item.fixturenames.append("settings_context")


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
    import nexusLIMS.utils.time  # pylint: disable=import-outside-toplevel

    tz_string = current_system_tz().tzname(dt.now(tz=current_system_tz()))

    # if timezone is MST or MDT, we're 2 hours behind, so we need to adjust
    # datetime objects to match file store
    if tz_string in ["MST", "MDT"]:
        # get current timezone, and adjust tz_offset as needed
        monkey_session.setattr(nexusLIMS.utils.time, "tz_offset", td(hours=-2))
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
    from sqlmodel import Session, select

    from nexusLIMS.db.engine import get_engine
    from nexusLIMS.db.models import SessionLog

    to_remove = (
        "https://nemo.example.com/api/usage_events/?id=29",
        "https://nemo.example.com/api/usage_events/?id=30",
        "https://nemo.example.com/api/usage_events/?id=31",
        "test_session",
    )

    with Session(get_engine()) as session:
        statement = select(SessionLog).where(
            SessionLog.session_identifier.in_(to_remove)
        )
        logs = session.exec(statement).all()
        for log in logs:
            session.delete(log)
        session.commit()


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


@pytest.fixture(scope="module")
def tecnai_tem_diff():
    """Tecnai TEM diffraction file with Indicated Magnification present."""
    files = extract_files("TECNAI_TEM_DIFF")
    yield files
    delete_files("TECNAI_TEM_DIFF")


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


# Zeiss Orion/Fibics test files
@pytest.fixture(scope="module")
def orion_fibics_zeroed_file():
    """Zeiss Orion with Fibics HIM data file (data zeroed for size)."""
    files = extract_files("ORION_FIBICS_ZEROED")
    yield files[0] if files else None
    delete_files("ORION_FIBICS_ZEROED")


# Tescan PFIB/SEM test files
@pytest.fixture(scope="module")
def tescan_pfib_files():
    """Tescan PFIB/SEM TIFF and HDR files (data zeroed for size)."""
    files = extract_files("TESCAN_PFIB")
    yield files
    delete_files("TESCAN_PFIB")


@pytest.fixture(scope="module")
def orion_zeiss_zeroed_file():
    """Zeiss Orion with Zeiss XML metadata (data zeroed for size)."""
    return Path(__file__).parent / "files" / "orion-zeiss_dataZeroed.tif"


# NeoArm Gatan test files
@pytest.fixture(scope="module")
def neoarm_gatan_si_file():
    """NeoArm Gatan spectrum image file (data zeroed for size)."""
    files = extract_files("NEOARM_GATAN_SI")
    yield files[0] if files else None
    delete_files("NEOARM_GATAN_SI")


@pytest.fixture(scope="module")
def neoarm_gatan_image_file():
    """NeoArm Gatan image file (data zeroed for size)."""
    files = extract_files("NEOARM_GATAN_IMAGE")
    yield files[0] if files else None
    delete_files("NEOARM_GATAN_IMAGE")


# Quanta FEI 2 test file
@pytest.fixture(scope="module")
def quanta_fei_2_file():
    """Quanta FEI 2 example TIFF file (data zeroed for size)."""
    files = extract_files("QUANTA_FEI_2")
    yield files[0] if files else None
    delete_files("QUANTA_FEI_2")


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

    import nexusLIMS.utils.network

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

    # Patch the nexus_req function in the utils module
    monkeypatch.setattr(nexusLIMS.utils.network, "nexus_req", mock_nexus_req)


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
        ...     from tests.unit.test_instrument_factory import make_titan_stem
        ...     instrument = make_titan_stem()
        ...     mock_instrument_from_filepath(instrument)
        ...     # Now any code calling get_instr_from_filepath gets this instrument
        ...     metadata = parse_metadata("some_file.dm3")
    """

    def _mock(instrument):
        """Apply the monkeypatch for the given instrument."""
        # Import here to avoid circular imports
        import nexusLIMS.extractors
        import nexusLIMS.extractors.plugins.digital_micrograph
        import nexusLIMS.extractors.plugins.fei_emi
        import nexusLIMS.extractors.utils

        # Monkeypatch all the places where get_instr_from_filepath is called
        monkeypatch.setattr(
            nexusLIMS.extractors.plugins.digital_micrograph,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.plugins.fei_emi,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors,
            "get_instr_from_filepath",
            lambda _: instrument,
        )

    return _mock


# SQLModel test fixtures for database testing


@pytest.fixture
def test_db_engine():
    """
    Create in-memory SQLite engine for testing.

    This fixture provides a clean SQLite database engine with all tables
    created. Use this when you need a fresh database for isolated testing.

    Yields
    ------
    sqlmodel.engine.Engine
        SQLite engine with all tables created

    Examples
    --------
    >>> def test_query(test_db_engine):
    ...     with Session(test_db_engine) as session:
    ...         instruments = session.exec(select(Instrument)).all()
    ...         assert len(instruments) == 0
    """
    from sqlmodel import SQLModel, create_engine

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """
    Provide database session with automatic rollback.

    This fixture provides a SQLModel Session that automatically rolls back
    all changes after the test completes. This ensures tests don't affect
    each other even if they modify the database.

    Parameters
    ----------
    test_db_engine : sqlmodel.engine.Engine
        Test database engine from test_db_engine fixture

    Yields
    ------
    sqlmodel.Session
        Database session with automatic rollback

    Examples
    --------
    >>> def test_insert(test_db_session):
    ...     instrument = Instrument(instrument_pid="TEST", ...)
    ...     test_db_session.add(instrument)
    ...     test_db_session.commit()
    ...     # Automatically rolled back after test
    """
    from sqlmodel import Session

    with Session(test_db_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def sample_instrument(test_db_session):
    """
    Create a test instrument in the database.

    This fixture creates and persists a test instrument that can be used
    in tests requiring an existing instrument.

    Parameters
    ----------
    test_db_session : sqlmodel.Session
        Test database session from test_db_session fixture

    Returns
    -------
    nexusLIMS.db.models.Instrument
        Test instrument with id=1

    Examples
    --------
    >>> def test_with_instrument(sample_instrument):
    ...     assert sample_instrument.instrument_pid == "TEST-INSTRUMENT-001"
    ...     assert sample_instrument.id is not None
    """
    from nexusLIMS.db.models import Instrument

    instrument = Instrument(
        instrument_pid="TEST-INSTRUMENT-001",
        api_url="https://test.example.com/api",
        calendar_url="https://test.example.com/calendar",
        location="Test Lab",
        display_name="Test Instrument",
        property_tag="TEST001",
        filestore_path="./test_data",
        timezone_str="America/New_York",
        harvester="nemo",
    )
    test_db_session.add(instrument)
    test_db_session.commit()
    test_db_session.refresh(instrument)
    return instrument


@pytest.fixture
def sample_session_log(test_db_session, sample_instrument):
    """
    Create a test session log entry in the database.

    This fixture creates and persists a test session log that can be used
    in tests requiring an existing session.

    Parameters
    ----------
    test_db_session : sqlmodel.Session
        Test database session from test_db_session fixture
    sample_instrument : nexusLIMS.db.models.Instrument
        Test instrument from sample_instrument fixture

    Returns
    -------
    nexusLIMS.db.models.SessionLog
        Test session log entry

    Examples
    --------
    >>> def test_with_session(sample_session_log):
    ...     assert sample_session_log.event_type == EventType.START
    ...     assert sample_session_log.record_status == RecordStatus.TO_BE_BUILT
    """
    from nexusLIMS.db.enums import EventType, RecordStatus
    from nexusLIMS.db.models import SessionLog

    log = SessionLog(
        session_identifier="test-session-001",
        instrument=sample_instrument.instrument_pid,
        timestamp=dt.now(tz=current_system_tz()),
        event_type=EventType.START,
        record_status=RecordStatus.TO_BE_BUILT,
        user="test_user",
    )
    test_db_session.add(log)
    test_db_session.commit()
    test_db_session.refresh(log)
    return log


# ============================================================================
# Phase 1: New Marker-Based Infrastructure (Opt-In Fixtures)
# ============================================================================
# These fixtures implement the new marker-based resource allocation system
# that replaces autouse fixtures with explicit opt-in via pytest markers.
# See: /Users/josh/.claude/plans/inherited-exploring-rose.md
# ============================================================================


@pytest.fixture(scope="session")
def db_factory(tmp_path_factory):
    """
    Provide database factory for creating test databases on-demand.

    This factory creates databases with only the instruments and sessions
    that tests actually need, replacing the autouse fresh_test_db fixture.

    Returns
    -------
    DatabaseFactory
        Factory for creating test databases

    Examples
    --------
    Used automatically by db_context fixture when tests use @pytest.mark.needs_db:

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_something():
        from nexusLIMS.instruments import instrument_db
        assert "FEI-Titan-TEM" in instrument_db
    """
    from tests.unit.fixtures.database import DatabaseFactory

    # Use session-scoped temp directory
    temp_dir = tmp_path_factory.mktemp("test_databases")

    return DatabaseFactory(temp_dir)


@pytest.fixture
def file_factory(tmp_path):
    """
    Provide file factory for extracting test archives on-demand.

    This factory extracts .tar.gz archives with only the files that
    tests need, replacing 50+ module-scoped file extraction fixtures.

    Returns
    -------
    FileFactory
        Factory for extracting test file archives

    Examples
    --------
    Used automatically by file_context fixture when tests use @pytest.mark.needs_files:

    @pytest.mark.needs_files("QUANTA_TIF", "FEI_SER")
    def test_something(file_context):
        quanta_file = file_context.files["QUANTA_TIF"][0]
        fei_file = file_context.files["FEI_SER"][0]
    """
    from tests.unit.fixtures.files import FileFactory

    # Test files are in tests/unit/files/
    test_files_dir = Path(__file__).parent / "files"

    return FileFactory(test_files_dir, tmp_path)


@pytest.fixture
def with_validation(monkeypatch, tmp_path):
    """
    Temporarily enable validation for tests that specifically test validation behavior.

    By default, tests run with NX_TEST_MODE=true (from conftest.py), which disables
    validation. This fixture temporarily disables test mode to allow validation tests
    to run as expected.

    IMPORTANT: Changes to a temporary directory to avoid loading from any .env files
    in the repository root, which would interfere with validation testing.
    """
    import importlib
    import os
    import sys

    import nexusLIMS.config

    # Helper function to reload nexusLIMS modules that import from config
    def reload_dependent_modules():
        """Reload modules that import from config to pick up type alias changes."""
        # List of modules that import from config and need reloading
        # Note: We DON'T reload profiles module because it has a registry that
        # would be cleared and not properly repopulated
        modules_to_reload = [
            "nexusLIMS.db.engine",
            "nexusLIMS.db.session_handler",
            "nexusLIMS.builder.record_builder",
            "nexusLIMS.extractors.utils",
            "nexusLIMS.extractors.registry",
        ]

        for module_name in modules_to_reload:
            if module_name in sys.modules:
                with contextlib.suppress(Exception):
                    # If reload fails, just continue - module might have dependencies
                    importlib.reload(sys.modules[module_name])

    # Save original directory
    original_cwd = Path.cwd()

    # Change to temp directory to avoid loading .env files from repo root
    # This ensures validation tests run in a clean environment
    os.chdir(tmp_path)

    # Temporarily disable test mode
    monkeypatch.setenv("NX_TEST_MODE", "false")

    # Clear any cached settings BEFORE reloading
    nexusLIMS.config.clear_settings()

    # Reload the config module so that Settings class is redefined with validation
    # This is necessary because the class fields are evaluated at class definition time
    importlib.reload(nexusLIMS.config)

    # Clear settings again after reload to ensure fresh instance with new class
    nexusLIMS.config.clear_settings()

    # Reload dependent modules to pick up new type aliases
    reload_dependent_modules()

    yield

    # Restore original directory FIRST (before cleanup)
    os.chdir(original_cwd)

    # Cleanup: Restore test mode and reload config again to restore test defaults
    monkeypatch.setenv("NX_TEST_MODE", "true")
    nexusLIMS.config.clear_settings()
    importlib.reload(nexusLIMS.config)
    nexusLIMS.config.clear_settings()

    # Reload dependent modules again to restore test mode state
    reload_dependent_modules()
