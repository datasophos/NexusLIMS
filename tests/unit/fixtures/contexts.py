"""
Context fixtures that respond to pytest markers.

These fixtures are automatically injected when tests use markers like
@pytest.mark.needs_db or @pytest.mark.needs_files, providing opt-in
resource allocation instead of autouse fixtures.
"""

import pytest

from nexusLIMS.config import refresh_settings

from .database import INSTRUMENT_CONFIGS


@pytest.fixture
def db_context(request, db_factory, monkeypatch):
    """
    Database context activated by @pytest.mark.needs_db marker.

    This fixture reads marker arguments and creates a test database
    with only the requested instruments and sessions. It automatically
    updates the environment and reloads the instrument_db cache.

    Marker Usage
    ------------
    # Empty database
    @pytest.mark.needs_db
    def test_something():
        ...

    # Database with specific instruments
    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_with_instrument():
        from nexusLIMS.instruments import instrument_db
        titan = instrument_db["FEI-Titan-TEM"]
        ...

    # Database with instruments and sessions
    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"], sessions=True)
    def test_with_sessions():
        ...

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object containing marker information
    db_factory : DatabaseFactory
        Factory for creating databases
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture for environment variables

    Yields
    ------
    Path
        Path to the created test database

    Examples
    --------
    This fixture is automatically injected by pytest_collection_modifyitems
    when tests use the needs_db marker, so tests don't need to explicitly
    request it in their signature:

    @pytest.mark.needs_db(instruments=["FEI-Titan-TEM"])
    def test_something():  # db_context auto-injected
        # Database is already set up
        from nexusLIMS.instruments import instrument_db
        assert "FEI-Titan-TEM" in instrument_db
    """
    marker = request.node.get_closest_marker("needs_db")
    if not marker:
        pytest.skip("Test doesn't have needs_db marker")

    # Parse marker arguments
    kwargs = marker.kwargs if marker.kwargs else {}
    instrument_keys = kwargs.get("instruments", [])
    needs_sessions = kwargs.get("sessions", False)

    # Build instrument configs from keys
    instruments = [INSTRUMENT_CONFIGS[key] for key in instrument_keys]

    # Create default sessions if requested
    sessions = None
    if needs_sessions:
        sessions = _create_default_sessions(instrument_keys)

    # Create database
    db_path = db_factory.create_db(
        instruments=instruments if instruments else None,
        sessions=sessions,
    )

    # Update environment to point to new database
    monkeypatch.setenv("NX_DB_PATH", str(db_path))
    refresh_settings()

    # Reload instrument_db cache to pick up new database
    from nexusLIMS import instruments

    instruments.instrument_db.clear()
    instruments.instrument_db.update(instruments._get_instrument_db(db_path=db_path))  # noqa: SLF001

    # Recreate the engine to point to new database
    # The engine module creates a singleton at import time, so we need to patch it
    from sqlmodel import create_engine

    import nexusLIMS.db.engine

    new_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    monkeypatch.setattr(nexusLIMS.db.engine, "engine", new_engine)
    # Patch get_engine() function to return our test engine
    # This ensures all code using get_engine() gets the test database
    monkeypatch.setattr(nexusLIMS.db.engine, "get_engine", lambda: new_engine)

    return db_path

    # Cleanup handled by tmp_path fixture (db_factory uses temp_dir)


@pytest.fixture
def file_context(request, file_factory):
    """
    File context activated by @pytest.mark.needs_files marker.

    This fixture extracts only the test file archives specified in the
    marker arguments and provides access via a simple interface.

    Marker Usage
    ------------
    @pytest.mark.needs_files("QUANTA_TIF")
    def test_quanta(file_context):
        quanta_file = file_context.files["QUANTA_TIF"][0]
        ...

    @pytest.mark.needs_files("QUANTA_TIF", "FEI_SER")
    def test_multiple(file_context):
        quanta_files = file_context.files["QUANTA_TIF"]
        fei_files = file_context.files["FEI_SER"]
        ...

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object containing marker information
    file_factory : FileFactory
        Factory for extracting file archives

    Yields
    ------
    FileContext
        Object with .files attribute containing dict of extracted files

    Examples
    --------
    @pytest.mark.needs_files("QUANTA_TIF", "TITAN_EFTEM_DIFF")
    def test_parsing(file_context):
        # Access extracted files via file_context.files
        quanta = file_context.files["QUANTA_TIF"][0]
        titan = file_context.files["TITAN_EFTEM_DIFF"][0]
        # ... use files in test
    """
    marker = request.node.get_closest_marker("needs_files")
    if not marker:
        pytest.skip("Test doesn't have needs_files marker")

    # Extract requested archives
    archive_keys = marker.args
    if not archive_keys:
        pytest.fail("needs_files marker requires at least one archive key")

    files = file_factory.extract(*archive_keys)

    # Create simple context object with files attribute
    context = type("FileContext", (), {"files": files})()

    yield context

    # Cleanup extracted files
    file_factory.cleanup(*archive_keys)


@pytest.fixture
def settings_context(request, monkeypatch):
    """
    Build settings context activated by @pytest.mark.needs_settings marker.

    This fixture sets custom environment variables and refreshes settings
    based on marker keyword arguments.

    Marker Usage
    ------------
    @pytest.mark.needs_settings(NX_FILE_STRATEGY="inclusive")
    def test_with_custom_settings():
        from nexusLIMS.config import settings
        assert settings.NX_FILE_STRATEGY == "inclusive"

    @pytest.mark.needs_settings(
        NX_FILE_STRATEGY="exclusive",
        NX_IGNORE_PATTERNS='["*.mib", "*.db"]'
    )
    def test_with_multiple_settings():
        ...

    Parameters
    ----------
    request : pytest.FixtureRequest
        Pytest request object containing marker information
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture for environment variables

    Yields
    ------
    None
        Settings are configured via environment variables

    Notes
    -----
    Environment variables are automatically restored after the test
    via monkeypatch cleanup.
    """
    marker = request.node.get_closest_marker("needs_settings")
    if not marker:
        pytest.skip("Test doesn't have needs_settings marker")

    # Apply environment variables from marker kwargs
    if marker.kwargs:
        for key, value in marker.kwargs.items():
            monkeypatch.setenv(key, str(value))

        # Refresh settings to pick up new environment
        refresh_settings()

    # Cleanup handled by monkeypatch fixture


def _create_default_sessions(instrument_keys: list[str]) -> list[dict]:
    """
    Create default session logs for requested instruments.

    Parameters
    ----------
    instrument_keys : list[str]
        List of instrument keys from INSTRUMENT_CONFIGS

    Returns
    -------
    list[dict]
        List of session log dicts with START and END events

    Notes
    -----
    This creates test sessions with specific dates that match the
    test file modification times from test_record_files.tar.gz.
    These dates are critical for file-finding tests to work correctly.

    Session dates:
    - FEI-Titan-TEM: 2018-11-13 (matches Titan_TEM test files)
    - JEOL-JEM-TEM: 2019-07-24 (matches JEOL_TEM test files)
    - testtool-TEST-A1234567: 2021-08-02 (matches test tool files)
    """
    from datetime import datetime

    from nexusLIMS.db.enums import EventType, RecordStatus

    # Map instruments to their specific test dates
    # These dates MUST match the modification times of files in test_record_files.tar.gz
    session_dates = {
        "FEI-Titan-TEM": {
            "session_id": "https://nemo.example.com/api/usage_events/?id=101",
            "start": datetime.fromisoformat("2018-11-13T13:00:00-05:00"),
            "end": datetime.fromisoformat("2018-11-13T16:00:00-05:00"),
            "user": "researcher_a",
        },
        "JEOL-JEM-TEM": {
            "session_id": "https://nemo.example.com/api/usage_events/?id=202",
            "start": datetime.fromisoformat("2019-07-24T11:00:00-04:00"),
            "end": datetime.fromisoformat("2019-07-24T16:00:00-04:00"),
            "user": "researcher_b",
        },
        "testtool-TEST-A1234567": {
            "session_id": "https://nemo.example.com/api/usage_events/?id=303",
            "start": datetime.fromisoformat("2021-08-02T10:00:00-06:00"),
            "end": datetime.fromisoformat("2021-08-02T18:00:00-06:00"),
            "user": "test_user",
        },
    }

    sessions = []
    for key in instrument_keys:
        instrument_pid = INSTRUMENT_CONFIGS[key]["instrument_pid"]

        # Use specific dates if available, otherwise create generic recent session
        if instrument_pid in session_dates:
            session_info = session_dates[instrument_pid]
            session_id = session_info["session_id"]
            start_time = session_info["start"]
            end_time = session_info["end"]
            user = session_info["user"]
        else:
            # Fallback for instruments without predefined dates
            from datetime import timedelta

            from nexusLIMS.utils.time import current_system_tz

            tz = current_system_tz()
            start_time = datetime.now(tz=tz) - timedelta(days=1)
            end_time = start_time + timedelta(hours=2)
            session_id = f"test-session-{key}"
            user = "test_user"

        sessions.extend(
            [
                {
                    "session_identifier": session_id,
                    "instrument": instrument_pid,
                    "timestamp": start_time,
                    "event_type": EventType.START,
                    "record_status": RecordStatus.TO_BE_BUILT,
                    "user": user,
                },
                {
                    "session_identifier": session_id,
                    "instrument": instrument_pid,
                    "timestamp": end_time,
                    "event_type": EventType.END,
                    "record_status": RecordStatus.TO_BE_BUILT,
                    "user": user,
                },
            ]
        )

    return sessions
