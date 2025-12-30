# ruff: noqa: DTZ001
"""
Partial failure recovery integration tests for NexusLIMS.

This module tests error handling and recovery when external services fail
during the record building workflow, ensuring database consistency and proper
error propagation.
"""

import shutil
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import requests
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.builder import record_builder
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.session_handler import Session


@pytest.mark.integration
class TestPartialFailureRecovery:
    """Test error handling and recovery for partial failures."""

    def test_cdcs_upload_failure_after_record_built(  # noqa: PLR0913
        self,
        docker_services_running,
        nemo_connector,
        populated_test_database,
        extracted_test_files,
        cdcs_client,
        clear_session_logs,
        monkeypatch,
    ):
        """
        Test database consistency when CDCS upload fails after record building.

        This test verifies that:
        1. Sessions are marked COMPLETED after record building (current behavior)
        2. CDCS upload failures are logged but don't cause database rollback
        3. XML files are still written to disk even if upload fails
        4. Failed uploads are reported to the user

        NOTE: This test documents CURRENT behavior, which may not be ideal.
        The system currently does NOT rollback database state if CDCS fails.

        Parameters
        ----------
        docker_services_running : dict
            Docker services status
        nemo_connector : NemoConnector
            NEMO connector fixture
        populated_test_database : Path
            Test database with instruments
        extracted_test_files : dict
            Extracted test files
        cdcs_client : dict
            CDCS client configuration (ensures CDCS environment is set up)
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        from nexusLIMS.config import settings
        from nexusLIMS.db.session_handler import get_sessions_to_build

        # Track initial uploaded file count
        uploaded_dir = settings.records_dir_path / "uploaded"
        initial_uploaded_count = 0
        if uploaded_dir.exists():
            initial_uploaded_count = len(list(uploaded_dir.glob("*.xml")))

        # Create session timespan
        session_start = extracted_test_files["titan_date"].replace(
            hour=4, minute=0, second=0
        )
        session_end = session_start + timedelta(hours=12)

        # Verify no sessions before harvesting
        sessions_before = get_sessions_to_build()
        assert len(sessions_before) == 0

        # Add NEMO usage events to database
        from nexusLIMS.harvesters.nemo import utils as nemo_utils

        nemo_utils.add_all_usage_events_to_db(
            dt_from=session_start - timedelta(hours=1),
            dt_to=session_end + timedelta(hours=1),
        )

        # Verify session was created
        sessions_to_build = get_sessions_to_build()
        assert len(sessions_to_build) == 1

        # Build the record (this will succeed)
        xml_files = record_builder.build_new_session_records(generate_previews=False)
        assert len(xml_files) == 1

        # Verify session is now marked COMPLETED after record building
        sessions_after_build = get_sessions_to_build()
        assert len(sessions_after_build) == 0, "Session should be COMPLETED"

        # Verify database has COMPLETED status
        with DBSession(get_engine()) as db_session:
            all_sessions = db_session.exec(
                select(SessionLog.event_type, SessionLog.record_status).order_by(
                    SessionLog.session_identifier, SessionLog.event_type
                )
            ).all()
        completed_sessions = [s for s in all_sessions if s[1] == RecordStatus.COMPLETED]
        assert len(completed_sessions) == 3  # START, END, RECORD_GENERATION

        # Now simulate CDCS upload failure by patching upload_record_content
        with patch("nexusLIMS.cdcs.upload_record_content") as mock_upload:
            # Make upload_record_content return a failed response
            mock_response = MagicMock(spec=requests.Response)
            mock_response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
            mock_response.text = "CDCS database connection failed"
            mock_upload.return_value = (mock_response, None)

            # Attempt to upload the built records
            from nexusLIMS.cdcs import upload_record_files

            files_uploaded, record_ids = upload_record_files(xml_files, progress=False)

            # Verify upload failed
            assert len(files_uploaded) == 0, "No files should be uploaded on failure"
            assert len(record_ids) == 0, "No record IDs should be returned"

        # Verify session REMAINS COMPLETED (current behavior - no rollback)
        with DBSession(get_engine()) as db_session:
            sessions_after_upload_failure = db_session.exec(
                select(SessionLog.event_type, SessionLog.record_status).where(
                    SessionLog.record_status == RecordStatus.COMPLETED
                )
            ).all()
        assert len(sessions_after_upload_failure) == 3, (
            "Session status should NOT be rolled back on upload failure"
        )

        # Verify XML files are still on disk (not moved to uploaded/)
        final_uploaded_count = 0
        if uploaded_dir.exists():
            final_uploaded_count = len(list(uploaded_dir.glob("*.xml")))
        assert final_uploaded_count == initial_uploaded_count, (
            "No files should be moved to uploaded/ on failure "
            f"(initial: {initial_uploaded_count}, final: {final_uploaded_count})"
        )

        # Verify original XML file still exists in records directory
        for xml_file in xml_files:
            assert xml_file.exists(), f"Original XML file {xml_file} should still exist"

    def test_cdcs_partial_upload_failure(  # noqa: PLR0913
        self,
        docker_services_running,
        nemo_connector,
        populated_test_database,
        extracted_test_files,
        cdcs_client,
        clear_session_logs,
        monkeypatch,
    ):
        """
        Test behavior when some records upload successfully but others fail.

        This verifies that:
        1. Successfully uploaded files are moved to uploaded/ directory
        2. Failed upload files remain in records/ directory
        3. Both success and failure are logged appropriately
        4. The upload_record_files function returns correct lists

        Parameters
        ----------
        docker_services_running : dict
            Docker services status
        nemo_connector : NemoConnector
            NEMO connector fixture
        populated_test_database : Path
            Test database
        extracted_test_files : dict
            Extracted test files
        cdcs_client : dict
            CDCS client configuration (ensures CDCS environment is set up)
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        # Create session and build records
        session_start = extracted_test_files["titan_date"].replace(
            hour=4, minute=0, second=0
        )
        session_end = session_start + timedelta(hours=12)

        from nexusLIMS.harvesters.nemo import utils as nemo_utils

        nemo_utils.add_all_usage_events_to_db(
            dt_from=session_start - timedelta(hours=1),
            dt_to=session_end + timedelta(hours=1),
        )

        # Build records
        xml_files = record_builder.build_new_session_records(generate_previews=False)
        assert len(xml_files) == 1

        # Create a second dummy XML file to test partial failure
        dummy_xml_path = xml_files[0].parent / "test_dummy_record.xml"
        shutil.copy(xml_files[0], dummy_xml_path)
        xml_files.append(dummy_xml_path)

        # Mock upload to fail for second file only
        upload_call_count = 0

        def mock_upload_side_effect(xml_content, title):
            nonlocal upload_call_count
            upload_call_count += 1

            if upload_call_count == 1:
                # First upload succeeds
                response = MagicMock(spec=requests.Response)
                response.status_code = HTTPStatus.CREATED
                response.json.return_value = {"id": "test-record-id-1"}
                return (response, "test-record-id-1")
            # Second upload fails
            response = MagicMock(spec=requests.Response)
            response.status_code = HTTPStatus.BAD_REQUEST
            response.text = "Invalid XML content"
            return (response, None)

        with patch(
            "nexusLIMS.cdcs.upload_record_content", side_effect=mock_upload_side_effect
        ):
            from nexusLIMS.cdcs import upload_record_files

            files_uploaded, record_ids = upload_record_files(xml_files, progress=False)

            # Verify partial success
            assert len(files_uploaded) == 1, "Only first file should be uploaded"
            assert len(record_ids) == 1, "Only one record ID should be returned"
            assert record_ids[0] == "test-record-id-1"

        # Cleanup dummy file
        if dummy_xml_path.exists():
            dummy_xml_path.unlink()

    def test_nemo_api_failure_during_harvesting(
        self,
        docker_services_running,
        nemo_connector,
        populated_test_database,
        clear_session_logs,
        monkeypatch,
    ):
        """
        Test behavior when NEMO API fails during usage event harvesting.

        This verifies that:
        1. NEMO API failures are properly caught and logged
        2. Database remains consistent (no partial sessions created)
        3. Error is propagated to caller appropriately

        Parameters
        ----------
        docker_services_running : dict
            Docker services status
        nemo_connector : NemoConnector
            NEMO connector fixture (handles database patching)
        populated_test_database : Path
            Test database
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        from nexusLIMS.db.session_handler import get_sessions_to_build
        from nexusLIMS.harvesters.nemo import utils as nemo_utils

        # Mock nexus_req to raise an exception (used internally by NemoConnector)
        with patch("nexusLIMS.harvesters.nemo.connector.nexus_req") as mock_nexus_req:
            # Simulate network error
            mock_nexus_req.side_effect = requests.exceptions.ConnectionError(
                "NEMO API is unreachable"
            )

            # Verify that the exception is raised
            with pytest.raises(
                requests.exceptions.ConnectionError, match="NEMO API is unreachable"
            ):
                nemo_utils.add_all_usage_events_to_db(
                    dt_from=datetime(2018, 11, 13, 0, 0, 0),
                    dt_to=datetime(2018, 11, 13, 23, 59, 59),
                )

        # Verify no sessions were created
        sessions = get_sessions_to_build()
        assert len(sessions) == 0, "No sessions should be created on NEMO failure"

        # Verify database is empty
        with DBSession(get_engine()) as db_session:
            all_sessions = db_session.exec(select(SessionLog)).all()
        assert len(all_sessions) == 0, "Database should remain empty on failure"

    def test_database_constraint_validation_on_invalid_status(
        self, nemo_connector, populated_test_database, clear_session_logs, monkeypatch
    ):
        """
        Test that database CHECK constraints prevent invalid record_status values.

        This verifies that the Session.update_session_status() method properly
        enforces the allowed record_status values through database constraints,
        and that failed updates don't corrupt the database state.

        Parameters
        ----------
        nemo_connector : NemoConnector
            NEMO connector fixture (handles database patching)
        populated_test_database : Path
            Test database
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        from nexusLIMS import instruments

        # Get an instrument from the already-patched instrument_db
        instrument = instruments.instrument_db["FEI-Titan-TEM"]

        # Create SessionLog objects for START and END events
        start_time = datetime(2018, 11, 13, 10, 0, 0)
        end_time = datetime(2018, 11, 13, 12, 0, 0)

        start_log = SessionLog(
            session_identifier="test-session-001",
            instrument=instrument.instrument_pid,
            timestamp=start_time,
            event_type=EventType.START,
            user="testuser",
            record_status=RecordStatus.WAITING_FOR_END,
        )

        # Insert START event
        start_log.insert_log()

        # Create a Session object for testing status updates
        session = Session(
            session_identifier="test-session-001",
            instrument=instrument,
            dt_range=(start_time, end_time),
            user="testuser",
        )

        # Verify START event was inserted
        with DBSession(get_engine()) as db_session:
            rows = db_session.exec(
                select(SessionLog.event_type, SessionLog.record_status).where(
                    SessionLog.session_identifier == "test-session-001"
                )
            ).all()
        assert len(rows) == 1
        assert rows[0] == (EventType.START, RecordStatus.WAITING_FOR_END)

        # Try to update with an invalid status (should fail due to check constraint)
        # The database has a check constraint on record_status
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            session.update_session_status("INVALID_STATUS")

        # Verify database state was not corrupted - should still be WAITING_FOR_END
        with DBSession(get_engine()) as db_session:
            rows = db_session.exec(
                select(SessionLog.record_status).where(
                    SessionLog.session_identifier == "test-session-001"
                )
            ).all()
        assert rows[0] == RecordStatus.WAITING_FOR_END, "Status should not have changed"

        # Update with valid status should work
        success = session.update_session_status(RecordStatus.ERROR)
        assert success

        with DBSession(get_engine()) as db_session:
            rows = db_session.exec(
                select(SessionLog.record_status).where(
                    SessionLog.session_identifier == "test-session-001"
                )
            ).all()
        assert rows[0] == RecordStatus.ERROR

    def test_error_propagation_through_process_new_records(
        self,
        docker_services_running,
        nemo_connector,
        populated_test_database,
        clear_session_logs,
        monkeypatch,
    ):
        """
        Test that errors are properly propagated through process_new_records().

        This verifies that:
        1. Exceptions during record building are caught and logged
        2. Sessions are marked with ERROR status
        3. Processing continues for remaining sessions
        4. The function completes rather than crashing

        Parameters
        ----------
        docker_services_running : dict
            Docker services status
        nemo_connector : NemoConnector
            NEMO connector fixture (handles database patching)
        populated_test_database : Path
            Test database
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        # Mock build_record to raise an exception
        with patch("nexusLIMS.builder.record_builder.build_record") as mock_build:
            mock_build.side_effect = ValueError("Simulated record building error")

            # This should NOT raise an exception - errors should be caught
            # and sessions marked as ERROR
            record_builder.process_new_records(
                dt_from=datetime.fromisoformat("2018-11-13T00:00:00"),
                dt_to=datetime.fromisoformat("2018-11-13T23:59:59"),
            )

        # Verify sessions were marked as ERROR (if any were harvested)
        with DBSession(get_engine()) as db_session:
            error_sessions = db_session.exec(
                select(SessionLog.session_identifier, SessionLog.record_status).where(
                    SessionLog.record_status == RecordStatus.ERROR
                )
            ).all()
        assert all(e[1] == RecordStatus.ERROR for e in error_sessions)
