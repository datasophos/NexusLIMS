"""Unit tests for export_records() and was_successfully_exported()."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nexusLIMS.exporters import export_records, was_successfully_exported
from nexusLIMS.exporters.base import ExportResult


class TestExportRecordsValidation:
    """Test export_records validation and error handling."""

    def test_export_validation_error_mismatched_lengths(self, tmp_path):
        """Test that export_records raises error when file/session count mismatch."""
        # Create dummy XML file
        xml_file = tmp_path / "test_record.xml"
        xml_file.write_text("<record>Test</record>")

        # Create mock session
        mock_session = Mock()
        mock_session.session_identifier = "test-session-123"

        # Should raise ValueError when lengths don't match
        with pytest.raises(ValueError, match="must have the same length"):
            export_records([xml_file, xml_file], [mock_session])

    def test_export_logs_error_when_all_destinations_fail(self, tmp_path, caplog):
        """Test that export_records logs error when all destinations fail."""
        # Create dummy XML file
        xml_file = tmp_path / "test_record.xml"
        xml_file.write_text("<record>Test</record>")

        # Create mock session
        mock_session = Mock()
        mock_session.session_identifier = "test-session-456"
        mock_session.instrument.name = "test-instrument"
        mock_session.dt_from = datetime(2025, 1, 1, 10, 0, 0)
        mock_session.dt_to = datetime(2025, 1, 1, 12, 0, 0)
        mock_session.user = "testuser"

        # Mock registry to return all failures
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

            # Mock _log_to_database to avoid database operations
            with patch("nexusLIMS.exporters._log_to_database"):
                # Export with caplog to capture log messages
                import logging

                caplog.set_level(logging.ERROR, logger="nexusLIMS.exporters")
                results = export_records([xml_file], [mock_session])

                # Verify error was logged
                assert any(
                    "Export failed for test_record.xml" in record.message
                    and "all 1 destination(s) failed" in record.message
                    for record in caplog.records
                ), (
                    "Expected error log not found. "
                    f"Logs: {[r.message for r in caplog.records]}"
                )

                # Verify results still returned
                assert xml_file in results
                assert len(results[xml_file]) == 1
                assert results[xml_file][0].success is False

    def test_export_logs_success_when_some_destinations_succeed(self, tmp_path, caplog):
        """Test export_records logs success when some destinations succeed."""
        # Create dummy XML file
        xml_file = tmp_path / "test_record.xml"
        xml_file.write_text("<record>Test</record>")

        # Create mock session
        mock_session = Mock()
        mock_session.session_identifier = "test-session-789"
        mock_session.instrument.name = "test-instrument"
        mock_session.dt_from = datetime(2025, 1, 1, 10, 0, 0)
        mock_session.dt_to = datetime(2025, 1, 1, 12, 0, 0)
        mock_session.user = "testuser"

        # Mock registry to return mixed results
        with patch("nexusLIMS.exporters.get_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_registry.export_to_all.return_value = [
                ExportResult(
                    success=True,
                    destination_name="cdcs",
                    record_id="cdcs-123",
                ),
                ExportResult(
                    success=False,
                    destination_name="labarchives",
                    error_message="Failed",
                ),
            ]
            mock_get_registry.return_value = mock_registry

            # Mock _log_to_database
            with patch("nexusLIMS.exporters._log_to_database"):
                # Export with caplog
                import logging

                caplog.set_level(logging.INFO, logger="nexusLIMS.exporters")
                export_records([xml_file], [mock_session])

                # Verify success was logged (not error)
                assert any(
                    "Exported test_record.xml" in record.message
                    and "1/2 destination(s) succeeded" in record.message
                    for record in caplog.records
                ), (
                    "Expected success log not found. "
                    f"Logs: {[r.message for r in caplog.records]}"
                )


class TestWasSuccessfullyExported:
    """Test the was_successfully_exported helper function."""

    def test_successfully_exported_single_success(self):
        """Test was_successfully_exported with single successful export."""
        xml_file = Path("/tmp/test.xml")
        results = {
            xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123")
            ]
        }

        assert was_successfully_exported(xml_file, results) is True

    def test_successfully_exported_multiple_success(self):
        """Test was_successfully_exported with multiple successful exports."""
        xml_file = Path("/tmp/test.xml")
        results = {
            xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123"),
                ExportResult(
                    success=True, destination_name="labarchives", record_id="456"
                ),
            ]
        }

        assert was_successfully_exported(xml_file, results) is True

    def test_successfully_exported_partial_success(self):
        """Test was_successfully_exported when only some destinations succeed."""
        xml_file = Path("/tmp/test.xml")
        results = {
            xml_file: [
                ExportResult(success=True, destination_name="cdcs", record_id="123"),
                ExportResult(
                    success=False,
                    destination_name="labarchives",
                    error_message="Failed",
                ),
            ]
        }

        # Should still return True (at least one succeeded)
        assert was_successfully_exported(xml_file, results) is True

    def test_successfully_exported_all_failed(self):
        """Test was_successfully_exported when all exports fail."""
        xml_file = Path("/tmp/test.xml")
        results = {
            xml_file: [
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

        assert was_successfully_exported(xml_file, results) is False

    def test_successfully_exported_missing_file(self):
        """Test was_successfully_exported when file not in results."""
        xml_file = Path("/tmp/test.xml")
        results = {}

        assert was_successfully_exported(xml_file, results) is False
