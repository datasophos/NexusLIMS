"""Unified test data for both unit and integration tests.

This module provides standardized instrument configurations, session data,
and file metadata that are shared across unit and integration tests to
maintain consistency and eliminate test data conflicts.

CRITICAL: This is the single source of truth for test instrument PIDs and
configurations. Always import from here rather than hardcoding values.
"""

from datetime import datetime, timedelta, timezone

# ============================================================================
# Unified Instrument Configurations
# ============================================================================

# Standard timezone definitions for test instruments
TZ_EASTERN = timezone(timedelta(hours=-5))
TZ_MOUNTAIN = timezone(timedelta(hours=-7))
TZ_CENTRAL = timezone(timedelta(hours=-6))

# Unified instrument configurations - single source of truth
# These PIDs and configurations are used by both unit and integration tests
INSTRUMENTS = {
    "FEI-Titan-STEM": {
        "instrument_pid": "FEI-Titan-STEM",
        "api_url": "https://nemo.example.com/api/tools/?id=1",
        "calendar_url": "https://nemo.example.com/calendar/titan-stem/",
        "location": "Test Building Room 300",
        "display_name": "Titan TEM",
        "property_tag": "TEST-STEM-001",
        "filestore_path": "./Titan_STEM",
        "harvester": "nemo",
        "timezone": "America/New_York",
    },
    "FEI-Titan-TEM": {
        "instrument_pid": "FEI-Titan-TEM",
        "api_url": "https://nemo.example.com/api/tools/?id=2",
        "calendar_url": "https://nemo.example.com/calendar/titan/",
        "location": "Test Building Room 301",
        "display_name": "FEI Titan TEM",
        "property_tag": "TEST-TEM-001",
        "filestore_path": "./Titan_TEM",
        "harvester": "nemo",
        "timezone": "America/New_York",
    },
    "FEI-Quanta-ESEM": {
        "instrument_pid": "FEI-Quanta-ESEM",
        "api_url": "https://nemo.example.com/api/tools/?id=3",
        "calendar_url": "https://nemo.example.com/calendar/quanta/",
        "location": "Test Building Room 302",
        "display_name": "Quanta FEG 200",
        "property_tag": "TEST-SEM-001",
        "filestore_path": "./Quanta",
        "harvester": "nemo",
        "timezone": "America/New_York",
    },
    "JEOL-JEM-TEM": {
        "instrument_pid": "JEOL-JEM-TEM",
        "api_url": "https://nemo.example.com/api/tools/?id=5",
        "calendar_url": "https://nemo.example.com/calendar/jeol/",
        "location": "Test Building Room 303",
        "display_name": "JEOL JEM-3010",
        "property_tag": "TEST-JEOL-001",
        "filestore_path": "./JEOL_TEM",
        "harvester": "nemo",
        "timezone": "America/Chicago",
    },
    # Primary test instrument (replaces "testtool-TEST-A1234567")
    "TEST-TOOL": {
        "instrument_pid": "TEST-TOOL",
        "api_url": "https://nemo.example.com/api/tools/?id=6",
        "calendar_url": "https://nemo.example.com/calendar/test-tool/",
        "location": "Test Building Room 400",
        "display_name": "Test Tool",
        "property_tag": "TEST-TOOL-001",
        "filestore_path": "./Nexus_Test_Instrument",
        "harvester": "nemo",
        "timezone": "America/Denver",
    },
    # Secondary test instrument for NEMO API testing (tool ID 10)
    "test-tool-10": {
        "instrument_pid": "test-tool-10",
        "api_url": "https://nemo.example.com/api/tools/?id=10",
        "calendar_url": "https://nemo.example.com/calendar/test-tool-10/",
        "location": "Test Building Room 100",
        "display_name": "Test Tool 10",
        "property_tag": "TEST-TOOL-010",
        "filestore_path": "./Test_Tool_10",
        "harvester": "nemo",
        "timezone": "America/Denver",
    },
}

# ============================================================================
# Session Date Configurations
# ============================================================================

# Session dates aligned with actual test file timestamps
# FEI Titan TEM session (2018-11-13) - matches files in Titan_TEM archive
SESSION_DATES = {
    "FEI-Titan-TEM": {
        "start": datetime(2018, 11, 13, 13, 0, 0, tzinfo=TZ_EASTERN),
        "end": datetime(2018, 11, 13, 16, 0, 0, tzinfo=TZ_EASTERN),
        "user": "researcher_a",
        "session_id": "https://nemo.example.com/api/usage_events/?id=101",
    },
    "FEI-Titan-STEM": {
        "start": datetime(2019, 5, 15, 10, 0, 0, tzinfo=TZ_EASTERN),
        "end": datetime(2019, 5, 15, 14, 0, 0, tzinfo=TZ_EASTERN),
        "user": "researcher_b",
        "session_id": "https://nemo.example.com/api/usage_events/?id=202",
    },
    "FEI-Quanta-ESEM": {
        "start": datetime(2019, 8, 20, 9, 0, 0, tzinfo=TZ_EASTERN),
        "end": datetime(2019, 8, 20, 12, 0, 0, tzinfo=TZ_EASTERN),
        "user": "researcher_c",
        "session_id": "https://nemo.example.com/api/usage_events/?id=303",
    },
    "JEOL-JEM-TEM": {
        "start": datetime(2020, 3, 10, 14, 0, 0, tzinfo=TZ_CENTRAL),
        "end": datetime(2020, 3, 10, 17, 0, 0, tzinfo=TZ_CENTRAL),
        "user": "researcher_d",
        "session_id": "https://nemo.example.com/api/usage_events/?id=404",
    },
    "TEST-TOOL": {
        "start": datetime(2021, 8, 2, 10, 0, 0, tzinfo=TZ_MOUNTAIN),
        "end": datetime(2021, 8, 2, 18, 0, 0, tzinfo=TZ_MOUNTAIN),
        "user": "test_user",
        "session_id": "https://nemo.example.com/api/usage_events/?id=505",
    },
    "test-tool-10": {
        "start": datetime(2021, 9, 15, 11, 0, 0, tzinfo=TZ_MOUNTAIN),
        "end": datetime(2021, 9, 15, 15, 0, 0, tzinfo=TZ_MOUNTAIN),
        "user": "test_user_10",
        "session_id": "https://nemo.example.com/api/usage_events/?id=606",
    },
}

# ============================================================================
# File Archive Definitions (from unit test fixtures)
# ============================================================================

# Test file archives used by marker-based file extraction
# These archives are extracted on-demand by tests using @pytest.mark.needs_files
FILE_ARCHIVES = {
    "QUANTA_TIF": "Quanta_FEI_Helios.tar.gz",
    "FEI_EMI": "fei_emi_files.tar.gz",
    "DM3_FILES": "dm3_files.tar.gz",
    "STEM_EELS": "Titan_STEM_EELS.tar.gz",
    "EFTEM_DIFF": "JEOL_EFTEM_Diffraction.tar.gz",
    "EDAX_SPC": "edax_spc_map.tar.gz",
    # Add more archives as needed
}

# ============================================================================
# Helper Functions
# ============================================================================


def get_instrument_config(instrument_pid: str) -> dict:
    """
    Get instrument configuration by PID.

    Parameters
    ----------
    instrument_pid : str
        Instrument PID (e.g., "FEI-Titan-TEM", "TEST-TOOL")

    Returns
    -------
    dict
        Instrument configuration dictionary

    Raises
    ------
    KeyError
        If instrument PID is not found in INSTRUMENTS

    Examples
    --------
    >>> config = get_instrument_config("FEI-Titan-TEM")
    >>> print(config["display_name"])
    FEI Titan TEM
    """
    return INSTRUMENTS[instrument_pid]


def get_session_dates(instrument_pid: str) -> dict:
    """
    Get session date configuration for an instrument.

    Parameters
    ----------
    instrument_pid : str
        Instrument PID

    Returns
    -------
    dict
        Session date configuration with keys: start, end, user, session_id

    Raises
    ------
    KeyError
        If instrument PID is not found in SESSION_DATES

    Examples
    --------
    >>> dates = get_session_dates("FEI-Titan-TEM")
    >>> print(dates["start"])
    2018-11-13 13:00:00-05:00
    """
    return SESSION_DATES[instrument_pid]


def create_session_log_entry(
    instrument_pid: str, event_type: str, record_status: str = "TO_BE_BUILT"
) -> dict:
    """
    Create a session log entry for testing.

    Parameters
    ----------
    instrument_pid : str
        Instrument PID
    event_type : str
        Event type ("START" or "END")
    record_status : str, optional
        Record status (default: "TO_BE_BUILT")

    Returns
    -------
    dict
        Session log entry ready for database insertion

    Examples
    --------
    >>> entry = create_session_log_entry("FEI-Titan-TEM", "START")
    >>> print(entry["timestamp"])
    2018-11-13T13:00:00-05:00
    """
    session_info = get_session_dates(instrument_pid)

    return {
        "session_identifier": session_info["session_id"],
        "instrument": instrument_pid,
        "timestamp": (
            session_info["start"] if event_type == "START" else session_info["end"]
        ),
        "event_type": event_type,
        "record_status": record_status,
        "user": session_info["user"],
    }
