"""
Database factory for creating test databases on-demand.

This module provides a factory pattern for creating test databases with only
the resources each test needs, replacing the autouse fresh_test_db fixture.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from sqlmodel import SQLModel, create_engine

from nexusLIMS.db.enums import EventType, RecordStatus


class DatabaseFactory:
    """
    Factory for creating test databases on-demand.

    This factory uses SQLModel metadata to create databases
    with only the instruments and sessions that tests actually need,
    dramatically reducing test setup overhead.

    Attributes
    ----------
    temp_dir : Path
        Directory where test databases will be created
    _db_counter : int
        Counter for generating unique database names
    """

    def __init__(self, temp_dir: Path):
        """
        Initialize the database factory.

        Parameters
        ----------
        temp_dir : Path
            Directory for creating test databases
        """
        self.temp_dir = temp_dir
        self._db_counter = 0

    def create_db(
        self,
        instruments: list[dict] | None = None,
        sessions: list[dict] | None = None,
        name: str | None = None,
    ) -> Path:
        """
        Create a test database with specified instruments and sessions.

        Parameters
        ----------
        instruments : list[dict] | None
            List of instrument configuration dicts. Each dict should have keys:
            instrument_pid, api_url, calendar_name, calendar_url, location,
            schema_name, property_tag, filestore_path, harvester, timezone.
            If None, creates empty instruments table.
        sessions : list[dict] | None
            List of session log dicts. Each dict should have keys:
            session_identifier, instrument, timestamp, event_type,
            record_status, user.
            If None, creates empty session_log table.
        name : str | None
            Database filename. If None, auto-generates unique name.

        Returns
        -------
        Path
            Path to created database file

        Examples
        --------
        >>> factory = DatabaseFactory(tmp_path)
        >>> # Empty database
        >>> db_path = factory.create_db()
        >>> # Database with one instrument
        >>> db_path = factory.create_db(instruments=[{
        ...     "instrument_pid": "FEI-Titan-TEM",
        ...     "api_url": "https://nemo.example.com/api/tools/?id=2",
        ...     ...
        ... }])
        """
        # Generate unique name if not provided
        if name is None:
            self._db_counter += 1
            name = f"test_{self._db_counter}.db"

        db_path = self.temp_dir / name

        # Create database with SQLModel metadata (single source of truth)
        # Import all models to register them with SQLModel metadata
        from nexusLIMS.db.models import (  # noqa: F401
            ExternalUserIdentifier,
            Instrument,
            SessionLog,
            UploadLog,
        )

        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)
        engine.dispose()

        conn = sqlite3.connect(db_path)

        # Insert requested instruments
        if instruments:
            self._insert_instruments(conn, instruments)

        # Insert requested sessions
        if sessions:
            self._insert_sessions(conn, sessions)

        conn.commit()
        conn.close()

        return db_path

    def _insert_instruments(self, conn: sqlite3.Connection, instruments: list[dict]):
        """Insert instrument records into database."""
        cursor = conn.cursor()
        for inst in instruments:
            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    computer_name, computer_ip, computer_mount,
                    harvester, timezone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    inst.get("computer_name"),
                    inst.get("computer_ip"),
                    inst.get("computer_mount"),
                    inst["harvester"],
                    inst["timezone"],
                ),
            )

    def _insert_sessions(self, conn: sqlite3.Connection, sessions: list[dict]):
        """Insert session log records into database."""
        cursor = conn.cursor()
        for session in sessions:
            # Convert enum to value if needed
            event_type = (
                session["event_type"].value
                if isinstance(session["event_type"], EventType)
                else session["event_type"]
            )
            record_status = (
                session["record_status"].value
                if isinstance(session["record_status"], RecordStatus)
                else session["record_status"]
            )

            # Convert datetime to ISO format string
            timestamp = session["timestamp"]
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()

            cursor.execute(
                """
                INSERT INTO session_log (
                    session_identifier, instrument, timestamp,
                    event_type, record_status, user
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["session_identifier"],
                    session["instrument"],
                    timestamp,
                    event_type,
                    record_status,
                    session.get("user"),
                ),
            )


# Predefined instrument configurations for common test scenarios
INSTRUMENT_CONFIGS = {
    "FEI-Titan-STEM": {
        "instrument_pid": "FEI-Titan-STEM",
        "api_url": "https://nemo.example.com/api/tools/?id=1",
        "calendar_name": "FEI Titan TEM",
        "calendar_url": "https://nemo.example.com/calendar/titan-stem/",
        "location": "Test Building Room 300",
        "schema_name": "Titan TEM",
        "property_tag": "TEST-STEM-001",
        "filestore_path": "./Titan_STEM",
        "computer_name": None,
        "computer_ip": None,
        "computer_mount": None,
        "harvester": "nemo",
        "timezone": "America/New_York",
    },
    "FEI-Titan-TEM": {
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
    "FEI-Quanta-ESEM": {
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
    "JEOL-JEM-TEM": {
        "instrument_pid": "JEOL-JEM-TEM",
        "api_url": "https://nemo.example.com/api/tools/?id=5",
        "calendar_name": "JEOL 3010 TEM",
        "calendar_url": "https://nemo.example.com/calendar/jeol/",
        "location": "Test Building Room 303",
        "schema_name": "JEOL JEM-3010",
        "property_tag": "TEST-JEOL-001",
        "filestore_path": "./JEOL_TEM",
        "computer_name": None,
        "computer_ip": None,
        "computer_mount": None,
        "harvester": "nemo",
        "timezone": "America/Chicago",
    },
    "testtool-TEST-A1234567": {
        "instrument_pid": "testtool-TEST-A1234567",
        "api_url": "https://nemo.example.com/api/tools/?id=6",
        "calendar_name": "Test Tool",
        "calendar_url": "https://nemo.example.com/calendar/test-tool/",
        "location": "Test Building Room 400",
        "schema_name": "Test Tool",
        "property_tag": "TEST-TOOL-001",
        "filestore_path": "./Nexus_Test_Instrument",
        "computer_name": None,
        "computer_ip": None,
        "computer_mount": None,
        "harvester": "nemo",
        "timezone": "America/Denver",
    },
    "test-tool-10": {
        "instrument_pid": "test-tool-10",
        "api_url": "https://nemo.example.com/api/tools/?id=10",
        "calendar_name": "Test Tool",
        "calendar_url": "https://nemo.example.com/calendar/test-tool-10/",
        "location": "Test Building Room 100",
        "schema_name": "Test Tool",
        "property_tag": "TEST-TOOL-010",
        "filestore_path": "./Test_Tool_10",
        "computer_name": None,
        "computer_ip": None,
        "computer_mount": None,
        "harvester": "nemo",
        "timezone": "America/Denver",
    },
}
