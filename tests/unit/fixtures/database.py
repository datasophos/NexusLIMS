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
from tests.fixtures.test_data import INSTRUMENTS


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
            instrument_pid, api_url, calendar_url, location, display_name,
            property_tag, filestore_path, harvester, timezone.
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
# Using unified configurations from tests.fixtures.test_data (imported at top)
INSTRUMENT_CONFIGS = {
    key: INSTRUMENTS[key]
    for key in [
        "FEI-Titan-STEM",
        "FEI-Titan-TEM",
        "FEI-Quanta-ESEM",
        "JEOL-JEM-TEM",
        "TEST-TOOL",
    ]
}
