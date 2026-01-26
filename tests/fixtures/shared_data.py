# ruff: noqa: E501
"""
Shared test fixtures and data for both unit and integration tests.

This module provides common test data, utility functions, and fixtures that can be
used across both unit and integration tests to maintain consistency and reduce
duplication.
"""

from datetime import datetime as dt
from datetime import timedelta as td
from pathlib import Path

import pytest

# ============================================================================
# Common Test Constants
# ============================================================================

# Standard test dates and times (timezone-aware)
TEST_SESSION_START_TIME = dt(2021, 8, 2, 10, 0, 0)
TEST_SESSION_END_TIME = dt(2021, 8, 2, 18, 0, 0)
TEST_SESSION_DURATION = TEST_SESSION_END_TIME - TEST_SESSION_START_TIME

# Test user information
TEST_USER_USERNAME = "test_user"
TEST_USER_EMAIL = "test_user@example.com"
TEST_USER_FIRST_NAME = "Test"
TEST_USER_LAST_NAME = "User"

# Test project information
TEST_PROJECT_NAME = "Test Project"
TEST_PROJECT_ID = 1

# Test instrument information
TEST_INSTRUMENT_PID = "testtool-TEST-A1234567"
TEST_INSTRUMENT_SCHEMA_NAME = "Test Tool"


# ============================================================================
# Sample File Data
# ============================================================================


@pytest.fixture
def sample_dm3_metadata():
    """
    Return sample DigitalMicrograph metadata structure.

    This represents the expected metadata structure extracted from a .dm3/.dm4 file.
    """
    return {
        "nx_meta": {
            "DatasetType": "Image",
            "Data Type": "STEM",
            "Creation Time": TEST_SESSION_START_TIME.isoformat(),
            "Operator": TEST_USER_USERNAME,
            "Microscope": TEST_INSTRUMENT_SCHEMA_NAME,
            "Instrument ID": TEST_INSTRUMENT_PID,
            "Magnification": 100000,
            "Stage Position": {"x": 0.0, "y": 0.0, "z": 0.0},
        },
        "file_path": "/path/to/test_image.dm3",
        "file_size": 1024000,
    }


@pytest.fixture
def sample_tif_metadata():
    """
    Return sample FEI/Thermo TIF metadata structure.

    This represents the expected metadata structure extracted from a .tif file
    from FEI/Thermo Fisher instruments (Quanta, Helios, etc.).
    """
    return {
        "nx_meta": {
            "DatasetType": "Image",
            "Data Type": "SEM",
            "Creation Time": TEST_SESSION_START_TIME.isoformat(),
            "Operator": TEST_USER_USERNAME,
            "Microscope": "FEI Quanta 200",
            "Instrument ID": "FEI-Quanta-ESEM",
            "Magnification": 5000,
            "Beam Energy (keV)": 10.0,
            "Working Distance (mm)": 10.0,
        },
        "file_path": "/path/to/test_image.tif",
        "file_size": 512000,
    }


@pytest.fixture
def sample_file_list():
    """
    Return sample list of file paths for testing file clustering and record building.

    This list includes various file types with realistic names and is designed to
    test temporal clustering and activity grouping logic.
    """
    base_time = TEST_SESSION_START_TIME
    return [
        {
            "path": "/data/test_survey_001.dm3",
            "mtime": base_time,
            "size": 1024000,
        },
        {
            "path": "/data/test_image_001.dm3",
            "mtime": base_time + td(minutes=5),
            "size": 2048000,
        },
        {
            "path": "/data/test_image_002.dm3",
            "mtime": base_time + td(minutes=10),
            "size": 2048000,
        },
        # Gap in time to create separate activity
        {
            "path": "/data/test_eds_spectrum_001.dm3",
            "mtime": base_time + td(hours=1),
            "size": 512000,
        },
        {
            "path": "/data/test_eels_si_001.dm3",
            "mtime": base_time + td(hours=2),
            "size": 4096000,
        },
    ]


# ============================================================================
# Mock Database Fixtures
# ============================================================================


@pytest.fixture
def sample_instrument_data():
    """
    Return sample instrument database entries.

    This provides a standardized set of test instruments that can be used
    across unit and integration tests.
    """
    return [
        {
            "instrument_pid": "FEI-Titan-TEM",
            "api_url": "https://nemo.example.com/api/tools/?id=2",
            "calendar_name": "FEI Titan TEM",
            "calendar_url": "https://nemo.example.com/calendar/titan/",
            "location": "Test Building Room 301",
            "schema_name": "FEI Titan TEM",
            "property_tag": "TEST-TEM-001",
            "filestore_path": "./Titan_TEM",
            "computer_name": None,
            "computer_ip": None,
            "computer_mount": None,
            "harvester": "nemo",
            "timezone": "America/New_York",
        },
        {
            "instrument_pid": "FEI-Quanta-ESEM",
            "api_url": "https://nemo.example.com/api/tools/?id=3",
            "calendar_name": "FEI Quanta 200 ESEM",
            "calendar_url": "https://nemo.example.com/calendar/quanta/",
            "location": "Test Building Room 302",
            "schema_name": "Quanta FEG 200",
            "property_tag": "TEST-SEM-001",
            "filestore_path": "./Quanta",
            "computer_name": None,
            "computer_ip": None,
            "computer_mount": None,
            "harvester": "nemo",
            "timezone": "America/New_York",
        },
        {
            "instrument_pid": TEST_INSTRUMENT_PID,
            "api_url": "https://nemo.example.com/api/tools/?id=6",
            "calendar_name": "Test Tool",
            "calendar_url": "https://nemo.example.com/calendar/test-tool/",
            "location": "Test Building Room 400",
            "schema_name": TEST_INSTRUMENT_SCHEMA_NAME,
            "property_tag": "TEST-TOOL-001",
            "filestore_path": "./Nexus_Test_Instrument",
            "computer_name": None,
            "computer_ip": None,
            "computer_mount": None,
            "harvester": "nemo",
            "timezone": "America/Denver",
        },
    ]


@pytest.fixture
def sample_session_log_entries():
    """
    Return sample session log database entries.

    This provides standardized test session data that matches the test instruments
    and can be used for testing session handling and record building.
    """
    return [
        {
            "session_identifier": "https://nemo.example.com/api/usage_events/?id=101",
            "instrument": "FEI-Titan-TEM",
            "timestamp": "2018-11-13T13:00:00-05:00",
            "event_type": "START",
            "record_status": "TO_BE_BUILT",
            "user": "researcher_a",
        },
        {
            "session_identifier": "https://nemo.example.com/api/usage_events/?id=101",
            "instrument": "FEI-Titan-TEM",
            "timestamp": "2018-11-13T16:00:00-05:00",
            "event_type": "END",
            "record_status": "TO_BE_BUILT",
            "user": "researcher_a",
        },
        {
            "session_identifier": "https://nemo.example.com/api/usage_events/?id=303",
            "instrument": TEST_INSTRUMENT_PID,
            "timestamp": TEST_SESSION_START_TIME.isoformat(),
            "event_type": "START",
            "record_status": "TO_BE_BUILT",
            "user": TEST_USER_USERNAME,
        },
        {
            "session_identifier": "https://nemo.example.com/api/usage_events/?id=303",
            "instrument": TEST_INSTRUMENT_PID,
            "timestamp": TEST_SESSION_END_TIME.isoformat(),
            "event_type": "END",
            "record_status": "TO_BE_BUILT",
            "user": TEST_USER_USERNAME,
        },
    ]


# ============================================================================
# XML Schema and Validation
# ============================================================================


@pytest.fixture
def sample_xml_record():
    """
    Return sample XML record conforming to Nexus Experiment schema.

    This provides a minimal but valid XML record that can be used for
    testing CDCS uploads, validation, and record manipulation.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nx:Experiment xmlns:nx="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <nx:summary>
        <nx:title>Test Experiment</nx:title>
        <nx:instrument pid="{TEST_INSTRUMENT_PID}">{TEST_INSTRUMENT_SCHEMA_NAME}</nx:instrument>
        <nx:startTime>{TEST_SESSION_START_TIME.isoformat()}</nx:startTime>
        <nx:endTime>{TEST_SESSION_END_TIME.isoformat()}</nx:endTime>
        <nx:motivation>Testing</nx:motivation>
        <nx:user>
            <nx:name>{TEST_USER_USERNAME}</nx:name>
            <nx:role>Experimenter</nx:role>
        </nx:user>
    </nx:summary>
    <nx:acquisitionActivity>
        <nx:startTime>{TEST_SESSION_START_TIME.isoformat()}</nx:startTime>
        <nx:endTime>{(TEST_SESSION_START_TIME + td(minutes=30)).isoformat()}</nx:endTime>
        <nx:setup>
            <nx:description>Test acquisition activity</nx:description>
        </nx:setup>
    </nx:acquisitionActivity>
</nx:Experiment>"""


# ============================================================================
# Environment Configuration
# ============================================================================


@pytest.fixture
def test_env_vars():
    """
    Return dictionary of test environment variables.

    This provides a complete set of environment variables needed for testing
    NexusLIMS functionality, suitable for both unit and integration tests.
    """
    return {
        "NX_FILE_STRATEGY": "exclusive",
        "NX_IGNORE_PATTERNS": '["*.mib", "*.db", "*.emi"]',
        "NX_FILE_DELAY_DAYS": "7",
        "NX_CDCS_URL": "https://cdcs.example.com",
        "NX_CDCS_TOKEN": "test-api-token-not-for-production",
        "NX_NEMO_ADDRESS_1": "https://nemo.example.com/api/",
        "NX_NEMO_TOKEN_1": "test-token-12345",
        "NX_NEMO_TZ_1": "America/Denver",
        "NX_CERT_BUNDLE": "-----BEGIN CERTIFICATE-----\\nDUMMY\\n-----END CERTIFICATE-----",
    }


# ============================================================================
# Utility Functions
# ============================================================================


def create_mock_file_structure(base_path: Path, file_list: list):
    """
    Create mock file structure for testing.

    Parameters
    ----------
    base_path : Path
        Base directory to create files in
    file_list : list
        List of file dictionaries with 'path', 'mtime', and 'size' keys

    Returns
    -------
    list[Path]
        List of created file paths
    """
    created_files = []
    for file_info in file_list:
        file_path = base_path / Path(file_info["path"]).name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with specified size
        with file_path.open("wb") as f:
            f.write(b"\x00" * file_info["size"])

        # Set modification time
        import os

        mtime = file_info["mtime"].timestamp()
        os.utime(file_path, (mtime, mtime))

        created_files.append(file_path)

    return created_files


def assert_valid_xml_structure(xml_string: str):
    """
    Assert that XML string is well-formed and contains expected elements.

    Parameters
    ----------
    xml_string : str
        XML string to validate

    Raises
    ------
    AssertionError
        If XML is not well-formed or missing expected elements
    """
    from lxml import etree

    # Parse XML to ensure it's well-formed
    try:
        root = etree.fromstring(xml_string.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        msg = f"XML is not well-formed: {e}"
        raise AssertionError(msg) from e

    # Check for namespace
    assert root.nsmap is not None, "XML should have namespace declaration"

    # Check for basic required elements
    ns = {"nx": "https://data.nist.gov/od/dm/nexus/experiment/v1.0"}
    summary = root.find("nx:summary", ns)
    assert summary is not None, "XML should contain summary element"


def get_session_identifier_from_url(url: str) -> str:
    """
    Extract session identifier from NEMO API URL.

    Parameters
    ----------
    url : str
        NEMO API URL (e.g., "https://nemo.example.com/api/usage_events/?id=123")

    Returns
    -------
    str
        Session identifier (the full URL)
    """
    return url
