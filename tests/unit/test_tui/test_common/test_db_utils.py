"""Tests for TUI database utilities."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from nexusLIMS.db.models import Instrument, SessionLog
from nexusLIMS.tui.common.db_utils import (
    check_uniqueness,
    find_conflicting_instrument,
    get_session_log_count,
)


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(in_memory_db):
    """Create a database session with test data."""
    with Session(in_memory_db) as session:
        # Add test instruments
        instrument1 = Instrument(
            instrument_pid="TEST-INSTRUMENT-001",
            api_url="https://example.com/api/tools/?id=1",
            calendar_url="https://example.com/calendar/1",
            location="Building 1 Room 101",
            display_name="Test 1",
            property_tag="TAG001",
            filestore_path="./test1",
            harvester="nemo",
            timezone_str="America/New_York",
        )

        instrument2 = Instrument(
            instrument_pid="TEST-INSTRUMENT-002",
            api_url="https://example.com/api/tools/?id=2",
            calendar_url="https://example.com/calendar/2",
            location="Building 1 Room 102",
            display_name="Test 2",
            property_tag="TAG002",
            filestore_path="./test2",
            harvester="nemo",
            timezone_str="America/Los_Angeles",
        )

        session.add(instrument1)
        session.add(instrument2)
        session.commit()

        yield session


class TestCheckUniqueness:
    """Tests for check_uniqueness function."""

    def test_unique_value(self, db_session):
        """Test that a unique value returns True."""
        is_unique = check_uniqueness(
            db_session,
            Instrument,
            "api_url",
            "https://example.com/api/tools/?id=999",
        )
        assert is_unique is True

    def test_duplicate_value(self, db_session):
        """Test that a duplicate value returns False."""
        is_unique = check_uniqueness(
            db_session,
            Instrument,
            "api_url",
            "https://example.com/api/tools/?id=1",
        )
        assert is_unique is False

    def test_exclude_current_record(self, db_session):
        """Test that current record is excluded from uniqueness check."""
        # Should be unique when excluding TEST-INSTRUMENT-001
        is_unique = check_uniqueness(
            db_session,
            Instrument,
            "api_url",
            "https://example.com/api/tools/?id=1",
            exclude_pk="TEST-INSTRUMENT-001",
        )
        assert is_unique is True

    def test_none_value(self, db_session):
        """Test that None is considered unique (for optional fields)."""
        # Using a non-existent field to test None handling
        is_unique = check_uniqueness(
            db_session,
            Instrument,
            "api_url",
            None,
        )
        assert is_unique is True


class TestFindConflictingInstrument:
    """Tests for find_conflicting_instrument function."""

    def test_no_conflict(self, db_session):
        """Test that None is returned when no conflict exists."""
        conflict = find_conflicting_instrument(
            db_session,
            "api_url",
            "https://example.com/api/tools/?id=999",
        )
        assert conflict is None

    def test_finds_conflict(self, db_session):
        """Test that conflicting instrument is found."""
        conflict = find_conflicting_instrument(
            db_session,
            "api_url",
            "https://example.com/api/tools/?id=1",
        )
        assert conflict is not None
        assert conflict.instrument_pid == "TEST-INSTRUMENT-001"

    def test_exclude_current_instrument(self, db_session):
        """Test that current instrument is excluded from conflict check."""
        # Should not find conflict when excluding TEST-INSTRUMENT-001
        conflict = find_conflicting_instrument(
            db_session,
            "api_url",
            "https://example.com/api/tools/?id=1",
            exclude_pid="TEST-INSTRUMENT-001",
        )
        assert conflict is None

    def test_none_value(self, db_session):
        """Test that None returns no conflict (for optional fields)."""
        conflict = find_conflicting_instrument(
            db_session,
            "api_url",
            None,
        )
        assert conflict is None


class TestGetSessionLogCount:
    """Tests for get_session_log_count function."""

    def test_no_session_logs(self, db_session):
        """Test that count is 0 when no session logs exist."""
        count = get_session_log_count(db_session, "TEST-INSTRUMENT-001")
        assert count == 0

    def test_with_session_logs(self, db_session):
        """Test that session logs are counted correctly."""
        # Add session logs for TEST-INSTRUMENT-001
        from datetime import datetime

        import pytz

        from nexusLIMS.db.enums import EventType, RecordStatus

        log1 = SessionLog(
            session_identifier="session-1",
            instrument="TEST-INSTRUMENT-001",
            timestamp=datetime.now(pytz.UTC),
            event_type=EventType.START,
            record_status=RecordStatus.COMPLETED,
        )

        log2 = SessionLog(
            session_identifier="session-2",
            instrument="TEST-INSTRUMENT-001",
            timestamp=datetime.now(pytz.UTC),
            event_type=EventType.START,
            record_status=RecordStatus.COMPLETED,
        )

        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()

        count = get_session_log_count(db_session, "TEST-INSTRUMENT-001")
        assert count == 2

    def test_only_counts_specific_instrument(self, db_session):
        """Test that only logs for specified instrument are counted."""
        from datetime import datetime

        import pytz

        from nexusLIMS.db.enums import EventType, RecordStatus

        # Add logs for both instruments
        log1 = SessionLog(
            session_identifier="session-1",
            instrument="TEST-INSTRUMENT-001",
            timestamp=datetime.now(pytz.UTC),
            event_type=EventType.START,
            record_status=RecordStatus.COMPLETED,
        )

        log2 = SessionLog(
            session_identifier="session-2",
            instrument="TEST-INSTRUMENT-002",
            timestamp=datetime.now(pytz.UTC),
            event_type=EventType.START,
            record_status=RecordStatus.COMPLETED,
        )

        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()

        # Should only count logs for TEST-INSTRUMENT-001
        count = get_session_log_count(db_session, "TEST-INSTRUMENT-001")
        assert count == 1
