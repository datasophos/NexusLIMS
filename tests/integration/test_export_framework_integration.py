"""Integration tests for the multi-destination export framework.

Tests the complete export workflow including:
- Building records
- Exporting to multiple destinations
- Database logging to upload_log table
- Session status transitions
- Inter-destination dependencies
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import create_engine, select

from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import Instrument, SessionLog, UploadLog
from nexusLIMS.db.session_handler import Session
from nexusLIMS.exporters import export_records, was_successfully_exported
from nexusLIMS.exporters.base import ExportContext, ExportResult


@pytest.fixture
def db_session(test_database):
    """Create a test database session using the integration test database fixture."""
    # Create engine from test_database path
    engine = create_engine(f"sqlite:///{test_database}")

    # CRITICAL: Update the global engine to point to test database
    # This ensures export_records() uses the same database as the test
    from nexusLIMS.db import engine as engine_module

    original_engine = engine_module.engine
    engine_module.engine = engine

    try:
        # Create session
        with DBSession(engine) as session:
            yield session
    finally:
        # Restore original engine
        engine_module.engine = original_engine


@pytest.fixture
def instrument(db_session):
    """Create a test instrument in the database."""
    instrument = Instrument(
        instrument_pid="test-instrument-001",
        api_url="http://localhost:8000/api/",
        calendar_name="Test Instrument",
        calendar_url="http://localhost:8000/calendar/",
        location="Test Lab 101",
        schema_name="Test Instrument",
        property_tag="TEST001",
        filestore_path="test_instrument",
        harvester="nemo",
        timezone_str="America/New_York",
    )
    db_session.add(instrument)
    db_session.commit()
    db_session.refresh(instrument)
    return instrument


@pytest.fixture
def sample_xml_file(tmp_path):
    """Create a sample XML record file."""
    xml_file = tmp_path / "test_record.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<record>
    <session>test-session-123</session>
    <instrument>test-instrument</instrument>
    <data>Sample experiment data</data>
</record>"""
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def sample_session(db_session, instrument):
    """Create a sample Session object for testing."""
    # Create session logs in database
    start_log = SessionLog(
        session_identifier="test-session-123",
        instrument=instrument.instrument_pid,
        timestamp=datetime(2025, 1, 1, 10, 0, 0),
        event_type=EventType.START,
        user="testuser",
        record_status=RecordStatus.TO_BE_BUILT,
    )
    db_session.add(start_log)
    db_session.commit()

    # Create Session object
    return Session(
        session_identifier="test-session-123",
        instrument=instrument,
        dt_range=(datetime(2025, 1, 1, 10, 0, 0), datetime(2025, 1, 1, 12, 0, 0)),
        user="testuser",
    )


@pytest.fixture
def mock_cdcs_destination():
    """Create a mock CDCS destination for testing."""

    class MockCDCSDestination:
        name = "cdcs"
        priority = 100

        @property
        def enabled(self):
            return True

        def validate_config(self):
            return True, None

        def export(self, context: ExportContext) -> ExportResult:
            return ExportResult(
                success=True,
                destination_name="cdcs",
                record_id="cdcs-789",
                record_url="http://localhost:8000/data?id=cdcs-789",
            )

    return MockCDCSDestination()


@pytest.fixture
def mock_labarchives_destination():
    """Create a mock LabArchives destination that depends on CDCS."""

    class MockLabArchivesDestination:
        name = "labarchives"
        priority = 90

        @property
        def enabled(self):
            return True

        def validate_config(self):
            return True, None

        def export(self, context: ExportContext) -> ExportResult:
            # Check if CDCS succeeded and include link
            metadata = {}
            if context.has_successful_export("cdcs"):
                cdcs_result = context.get_result("cdcs")
                metadata["included_cdcs_link"] = True
                metadata["cdcs_url"] = cdcs_result.record_url
            else:
                metadata["included_cdcs_link"] = False

            return ExportResult(
                success=True,
                destination_name="labarchives",
                record_id="la-456",
                record_url="http://labarchives.example.com/notebook/la-456",
                metadata=metadata,
            )

    return MockLabArchivesDestination()


class TestExportRecordsBasic:
    """Test basic export_records functionality."""

    def test_export_single_file_single_destination(
        self, db_session, sample_xml_file, sample_session, mock_cdcs_destination
    ):
        """Test exporting a single file to a single destination."""
        # Mock the registry to return only CDCS
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(
                    success=True,
                    destination_name="cdcs",
                    record_id="cdcs-123",
                    record_url="http://localhost:8000/data?id=cdcs-123",
                )
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            results = export_records([sample_xml_file], [sample_session])

            # Verify results
            assert sample_xml_file in results
            assert len(results[sample_xml_file]) == 1
            assert results[sample_xml_file][0].success is True
            assert results[sample_xml_file][0].destination_name == "cdcs"

    def test_export_multiple_files(self, db_session, tmp_path, instrument):
        """Test exporting multiple files."""
        # Create multiple XML files
        xml_files = []
        sessions = []

        for i in range(3):
            xml_file = tmp_path / f"record_{i}.xml"
            xml_file.write_text(f"<record>Test {i}</record>")
            xml_files.append(xml_file)

            # Create session
            session_id = f"test-session-{i}"
            session_log = SessionLog(
                session_identifier=session_id,
                instrument=instrument.instrument_pid,
                timestamp=datetime.now(),
                event_type="START",
                record_status=RecordStatus.TO_BE_BUILT,
            )
            db_session.add(session_log)
            db_session.commit()

            session = Session(
                session_identifier=session_id,
                instrument=instrument,
                dt_range=(datetime.now(), datetime.now()),
                user="testuser",
            )
            sessions.append(session)

        # Mock registry
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(success=True, destination_name="cdcs", record_id="123")
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            results = export_records(xml_files, sessions)

            # Verify all files exported
            assert len(results) == 3
            for xml_file in xml_files:
                assert xml_file in results
                assert len(results[xml_file]) == 1

    def test_export_validation_error(self, sample_xml_file, sample_session):
        """Test that export_records raises error when file/session count mismatch."""
        with pytest.raises(ValueError, match="must have the same length"):
            export_records([sample_xml_file, sample_xml_file], [sample_session])


class TestUploadLogDatabase:
    """Test that export results are logged to upload_log table."""

    def test_upload_log_created_on_success(
        self, db_session, sample_xml_file, sample_session
    ):
        """Test that successful exports create upload_log entries."""
        # Mock registry
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(
                    success=True,
                    destination_name="cdcs",
                    record_id="cdcs-999",
                    record_url="http://localhost:8000/data?id=cdcs-999",
                    timestamp=datetime(2025, 1, 1, 13, 0, 0),
                )
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            export_records([sample_xml_file], [sample_session])

            # Query upload_log table
            logs = db_session.exec(
                select(UploadLog).where(
                    UploadLog.session_identifier == "test-session-123"
                )
            ).all()

            assert len(logs) == 1
            log = logs[0]
            assert log.destination_name == "cdcs"
            assert log.success is True
            assert log.record_id == "cdcs-999"
            assert log.record_url == "http://localhost:8000/data?id=cdcs-999"
            assert log.error_message is None
            assert log.metadata_json is None

    def test_upload_log_created_on_failure(
        self, db_session, sample_xml_file, sample_session
    ):
        """Test that failed exports create upload_log entries with error."""
        # Mock registry
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(
                    success=False,
                    destination_name="cdcs",
                    error_message="Connection timeout",
                    timestamp=datetime(2025, 1, 1, 13, 0, 0),
                )
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            export_records([sample_xml_file], [sample_session])

            # Query upload_log table
            logs = db_session.exec(
                select(UploadLog).where(
                    UploadLog.session_identifier == "test-session-123"
                )
            ).all()

            assert len(logs) == 1
            log = logs[0]
            assert log.destination_name == "cdcs"
            assert log.success is False
            assert log.record_id is None
            assert log.record_url is None
            assert log.error_message == "Connection timeout"

    def test_upload_log_with_metadata(
        self, db_session, sample_xml_file, sample_session
    ):
        """Test that upload_log stores metadata as JSON."""
        # Mock registry
        metadata = {"custom_field": "value", "count": 42, "flag": True}
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(
                    success=True,
                    destination_name="cdcs",
                    record_id="cdcs-123",
                    metadata=metadata,
                )
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            export_records([sample_xml_file], [sample_session])

            # Query upload_log table
            logs = db_session.exec(
                select(UploadLog).where(
                    UploadLog.session_identifier == "test-session-123"
                )
            ).all()

            assert len(logs) == 1
            log = logs[0]
            assert log.metadata_json is not None

            # Parse JSON
            stored_metadata = json.loads(log.metadata_json)
            assert stored_metadata == metadata

    def test_upload_log_multiple_destinations(
        self, db_session, sample_xml_file, sample_session
    ):
        """Test that upload_log creates separate entries for each destination."""
        # Mock registry with multiple destinations
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(success=True, destination_name="cdcs", record_id="cdcs-1"),
                ExportResult(
                    success=True, destination_name="labarchives", record_id="la-2"
                ),
                ExportResult(
                    success=False, destination_name="elabftw", error_message="Failed"
                ),
            ]
            mock_get_registry.return_value = mock_registry

            # Export
            export_records([sample_xml_file], [sample_session])

            # Query upload_log table
            logs = db_session.exec(
                select(UploadLog).where(
                    UploadLog.session_identifier == "test-session-123"
                )
            ).all()

            assert len(logs) == 3

            # Verify each destination
            dest_names = {log.destination_name for log in logs}
            assert dest_names == {"cdcs", "labarchives", "elabftw"}

            # Verify success status
            for log in logs:
                if log.destination_name == "elabftw":
                    assert log.success is False
                else:
                    assert log.success is True


class TestWasSuccessfullyExported:
    """Test the was_successfully_exported helper function."""

    def test_successfully_exported_single_success(self, sample_xml_file):
        """Test was_successfully_exported with single successful export."""
        results = {
            sample_xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123")
            ]
        }

        assert was_successfully_exported(sample_xml_file, results) is True

    def test_successfully_exported_multiple_success(self, sample_xml_file):
        """Test was_successfully_exported with multiple successful exports."""
        results = {
            sample_xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123"),
                ExportResult(
                    success=True, destination_name="labarchives", record_id="456"
                ),
            ]
        }

        assert was_successfully_exported(sample_xml_file, results) is True

    def test_successfully_exported_partial_success(self, sample_xml_file):
        """Test was_successfully_exported when only some destinations succeed."""
        results = {
            sample_xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123"),
                ExportResult(
                    success=False,
                    destination_name="labarchives",
                    error_message="Failed",
                ),
            ]
        }

        # Should still return True (at least one succeeded)
        assert was_successfully_exported(sample_xml_file, results) is True

    def test_successfully_exported_all_failed(self, sample_xml_file):
        """Test was_successfully_exported when all exports fail."""
        results = {
            sample_xml_file: [
                ExportResult(
                    success=False, destination_name="cdcs", error_message="Failed"
                ),
                ExportResult(
                    success=False,
                    destination_name="labarchives",
                    error_message="Failed",
                ),
            ]
        }

        assert was_successfully_exported(sample_xml_file, results) is False

    def test_successfully_exported_missing_file(self, sample_xml_file):
        """Test was_successfully_exported when file not in results."""
        results = {}
        assert was_successfully_exported(sample_xml_file, results) is False


class TestInterDestinationDependencies:
    """Test inter-destination dependencies in real export workflow."""

    def test_labarchives_accesses_cdcs_result(
        self, db_session, sample_xml_file, sample_session
    ):
        """Test that LabArchives can access CDCS result via context."""
        # Track whether LabArchives saw CDCS result
        labarchives_saw_cdcs = False

        class TestLabArchivesDestination:
            name = "labarchives"
            priority = 90

            @property
            def enabled(self):
                return True

            def validate_config(self):
                return True, None

            def export(self, context: ExportContext) -> ExportResult:
                nonlocal labarchives_saw_cdcs

                # Check if CDCS result is available
                if context.has_successful_export("cdcs"):
                    labarchives_saw_cdcs = True
                    cdcs_result = context.get_result("cdcs")
                    assert cdcs_result.record_id == "cdcs-123"
                    assert "cdcs-123" in cdcs_result.record_url

                return ExportResult(
                    success=True,
                    destination_name="labarchives",
                    record_id="la-456",
                )

        # Mock registry with both destinations
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()

            # Simulate sequential execution with result accumulation
            def mock_export_to_all(context, strategy):
                # Simulate CDCS export (priority 100, runs first)
                cdcs_result = ExportResult(
                    success=True,
                    destination_name="cdcs",
                    record_id="cdcs-123",
                    record_url="http://localhost:8000/data?id=cdcs-123",
                )
                context.previous_results["cdcs"] = cdcs_result

                # Simulate LabArchives export (priority 90, runs second)
                la_dest = TestLabArchivesDestination()
                la_result = la_dest.export(context)
                context.previous_results["labarchives"] = la_result

                return [cdcs_result, la_result]

            mock_registry.export_to_all = mock_export_to_all
            mock_get_registry.return_value = mock_registry

            # Export
            export_records([sample_xml_file], [sample_session])

            # Verify LabArchives saw CDCS result
            assert labarchives_saw_cdcs is True
