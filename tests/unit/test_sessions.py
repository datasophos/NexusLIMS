"""Tests functionality related to handling of session objects."""

# pylint: disable=missing-function-docstring
# ruff: noqa: D102

from datetime import datetime as dt
from uuid import uuid4

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.db import session_handler
from nexusLIMS.db.engine import engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog, TZDateTime
from nexusLIMS.utils import current_system_tz

from .test_instrument_factory import make_test_tool


@pytest.mark.needs_db(instruments=["testtool-TEST-A1234567"], sessions=True)
class TestSession:
    """Test the Session class representing a unit of time on an instrument."""

    @pytest.fixture
    def session(self, db_context):  # noqa: ARG002
        # Depend on db_context to ensure test database setup
        return session_handler.Session(
            session_identifier="test_session",
            instrument=make_test_tool(),
            dt_range=(
                dt.fromisoformat("2020-02-04T09:00:00.000"),
                dt.fromisoformat("2020-02-04T12:00:00.000"),
            ),
            user="None",
        )

    def test_session_repr(self, session):
        assert (
            repr(session) == "2020-02-04T09:00:00 to "
            "2020-02-04T12:00:00 on "
            "testtool-TEST-A1234567"
        )

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_record_generation_timestamp(self, session):
        row_dict = session.insert_record_generation_event()
        with DBSession(engine) as db_session:
            statement = select(SessionLog).where(
                SessionLog.id_session_log == row_dict["id_session_log"]
            )
            log = db_session.exec(statement).first()
            assert log.timestamp.tzinfo is not None

    def test_bad_db_status(self):
        uuid_str = str(uuid4())
        # Add a START log with TO_BE_BUILT status
        log = SessionLog(
            session_identifier=uuid_str,
            instrument="FEI-Titan-TEM-012345",
            timestamp=dt.now(tz=current_system_tz()),
            event_type=EventType.START,
            record_status=RecordStatus.TO_BE_BUILT,
            user="test",
        )
        with DBSession(engine) as db_session:
            db_session.add(log)
            db_session.commit()

        # because we put in an extra START log with TO_BE_BUILT status,
        # this should raise an error:
        with pytest.raises(
            ValueError,
            match="There was not exactly one 'END' log for this 'START' log; ",
        ):
            session_handler.get_sessions_to_build()

        # remove the session log we added
        with DBSession(engine) as db_session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == uuid_str
            )
            log = db_session.exec(statement).first()
            if log:
                db_session.delete(log)
                db_session.commit()


@pytest.mark.needs_db(instruments=["testtool-TEST-A1234567"])
class TestSessionLog:
    """
    Test the SessionLog class.

    A SessionLog object represents a single row in the session_log table of the
    NexusLIMS database
    """

    @pytest.fixture
    def sl(self, db_context):  # noqa: ARG002
        """Create a test SessionLog instance."""
        # Depend on db_context to ensure test database setup
        return SessionLog(
            session_identifier="testing-session-log",
            instrument="testtool-TEST-A1234567",
            timestamp=dt.fromisoformat("2020-02-04T09:00:00"),
            event_type=EventType.START,
            user="ear1",
            record_status=RecordStatus.TO_BE_BUILT,
        )

    @pytest.fixture(name="_record_cleanup_session_log")
    def cleanup_session_log(self):
        # this fixture removes the rows for the session logs added in
        # this test class, so it doesn't mess up future record building tests
        yield None
        # below runs on test teardown
        with DBSession(engine) as db_session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == "testing-session-log"
            )
            logs = db_session.exec(statement).all()
            for log in logs:
                db_session.delete(log)
            db_session.commit()

    def test_repr(self, sl):
        assert (
            repr(sl) == "SessionLog "
            "(id=testing-session-log, "
            "instrument=testtool-TEST-A1234567, "
            "timestamp=2020-02-04 09:00:00, "
            "event_type=START, "
            "user=ear1, "
            "record_status=TO_BE_BUILT)"
        )

    @pytest.mark.usefixtures("_record_cleanup_session_log")
    def test_insert_log(self, sl):
        # Count existing session logs
        with DBSession(engine) as db_session:
            res_before = db_session.exec(select(SessionLog)).all()

        # Insert a new log
        sl.insert_log()

        # Count session logs after insert
        with DBSession(engine) as db_session:
            res_after = db_session.exec(select(SessionLog)).all()

        assert len(res_after) - len(res_before) == 1

    @pytest.mark.usefixtures("_record_cleanup_session_log")
    def test_insert_duplicate_log(self, caplog):
        # Create a session log to insert
        sl = SessionLog(
            session_identifier="testing-session-log",
            instrument="testtool-TEST-A1234567",
            timestamp=dt.fromisoformat("2020-02-04T09:00:00"),
            event_type=EventType.START,
            user="ear1",
            record_status=RecordStatus.TO_BE_BUILT,
        )
        # First insert - should succeed
        sl.insert_log()

        # Create another SessionLog with same data
        sl2 = SessionLog(
            session_identifier="testing-session-log",
            instrument="testtool-TEST-A1234567",
            timestamp=dt.fromisoformat("2020-02-04T09:00:00"),
            event_type=EventType.START,
            user="ear1",
            record_status=RecordStatus.TO_BE_BUILT,
        )
        # Second insert - should trigger warning
        result = sl2.insert_log()
        assert "WARNING" in caplog.text
        assert "SessionLog already exists:" in caplog.text
        assert result

    @pytest.mark.usefixtures("_record_cleanup_session_log")
    def test_get_all_session_logs(self, sl):
        # Test that get_all_session_logs returns the expected SessionLog objects
        # First insert our test session log
        sl.insert_log()

        # Get all session logs
        all_logs = session_handler.get_all_session_logs()

        # Verify that our test log is in the results
        test_logs = [
            log for log in all_logs if log.session_identifier == "testing-session-log"
        ]
        assert len(test_logs) == 1

        # Verify the content of the returned log (use hardcoded expected values)
        found_log = test_logs[0]
        assert found_log.session_identifier == "testing-session-log"
        assert found_log.instrument == "testtool-TEST-A1234567"
        assert found_log.timestamp == dt.fromisoformat("2020-02-04T09:00:00")
        assert found_log.event_type == EventType.START
        assert found_log.user == "ear1"
        assert found_log.record_status == RecordStatus.TO_BE_BUILT

    def test_get_all_session_logs_empty(self):
        # Test that get_all_session_logs returns empty list when no logs exist
        # This assumes the database is clean (no session logs)
        all_logs = session_handler.get_all_session_logs()
        assert isinstance(all_logs, list)
        # Note: We don't assert len(all_logs) == 0 because there might be other logs
        # from other tests, but we verify it returns a list


class TestTZDateTime:
    """Test the TZDateTime custom type decorator."""

    @pytest.fixture
    def tz_datetime(self):
        """Create a TZDateTime instance for testing."""
        return TZDateTime()

    def test_process_bind_param_with_datetime(self, tz_datetime):
        """Test process_bind_param converts datetime to ISO string."""
        test_dt = dt.fromisoformat("2020-02-04T09:00:00+00:00")
        result = tz_datetime.process_bind_param(test_dt, dialect=None)
        assert isinstance(result, str)
        assert result == "2020-02-04T09:00:00+00:00"

    def test_process_bind_param_with_string(self, tz_datetime):
        """Test process_bind_param passes through strings unchanged."""
        test_str = "2020-02-04T09:00:00+00:00"
        result = tz_datetime.process_bind_param(test_str, dialect=None)
        assert result == test_str
        assert isinstance(result, str)

    def test_process_bind_param_with_none(self, tz_datetime):
        """Test process_bind_param handles None."""
        result = tz_datetime.process_bind_param(None, dialect=None)
        assert result is None

    def test_process_result_value_with_string(self, tz_datetime):
        """Test process_result_value converts ISO string to datetime."""
        test_str = "2020-02-04T09:00:00+00:00"
        result = tz_datetime.process_result_value(test_str, dialect=None)
        assert isinstance(result, dt)
        assert result == dt.fromisoformat("2020-02-04T09:00:00+00:00")

    def test_process_result_value_with_datetime(self, tz_datetime):
        """Test process_result_value passes through datetime unchanged."""
        test_dt = dt.fromisoformat("2020-02-04T09:00:00+00:00")
        result = tz_datetime.process_result_value(test_dt, dialect=None)
        assert result == test_dt
        assert isinstance(result, dt)

    def test_process_result_value_with_none(self, tz_datetime):
        """Test process_result_value handles None."""
        result = tz_datetime.process_result_value(None, dialect=None)
        assert result is None
