"""Unit tests for ExportContext and ExportResult."""

from datetime import datetime

import pytest

from nexusLIMS.exporters.base import ExportContext, ExportResult


class TestExportResult:
    """Test ExportResult data structure."""

    def test_successful_result(self):
        """Test creating a successful export result."""
        result = ExportResult(
            success=True,
            destination_name="test_destination",
            record_id="record-123",
            record_url="http://example.com/record/123",
        )

        assert result.success is True
        assert result.destination_name == "test_destination"
        assert result.record_id == "record-123"
        assert result.record_url == "http://example.com/record/123"
        assert result.error_message is None
        assert isinstance(result.timestamp, datetime)
        assert result.metadata == {}

    def test_failed_result(self):
        """Test creating a failed export result."""
        result = ExportResult(
            success=False,
            destination_name="test_destination",
            error_message="Connection failed",
        )

        assert result.success is False
        assert result.destination_name == "test_destination"
        assert result.record_id is None
        assert result.record_url is None
        assert result.error_message == "Connection failed"
        assert isinstance(result.timestamp, datetime)

    def test_result_with_metadata(self):
        """Test export result with custom metadata."""
        metadata = {"custom_field": "value", "count": 42}
        result = ExportResult(
            success=True,
            destination_name="test_destination",
            metadata=metadata,
        )

        assert result.metadata == metadata
        assert result.metadata["custom_field"] == "value"
        assert result.metadata["count"] == 42

    def test_result_repr(self):
        """Test ExportResult string representation."""
        result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="123",
        )

        repr_str = repr(result)
        assert "cdcs" in repr_str
        assert "SUCCESS" in repr_str
        assert "123" in repr_str


class TestExportContext:
    """Test ExportContext data structure and helper methods."""

    @pytest.fixture
    def base_context(self, tmp_path):
        """Create a basic export context for testing."""
        xml_file = tmp_path / "test_record.xml"
        xml_file.write_text("<record>test</record>")

        return ExportContext(
            xml_file_path=xml_file,
            session_identifier="session-123",
            instrument_pid="test-instrument",
            dt_from=datetime(2025, 1, 1, 10, 0, 0),
            dt_to=datetime(2025, 1, 1, 12, 0, 0),
            user="testuser",
        )

    def test_context_creation(self, base_context):
        """Test creating an export context."""
        assert base_context.session_identifier == "session-123"
        assert base_context.instrument_pid == "test-instrument"
        assert base_context.user == "testuser"
        assert base_context.metadata == {}
        assert base_context.previous_results == {}

    def test_context_with_metadata(self, tmp_path):
        """Test export context with custom metadata."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<record>test</record>")

        metadata = {"project": "test_project", "pi": "test_pi"}
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier="session-123",
            instrument_pid="test-instrument",
            dt_from=datetime.now(),
            dt_to=datetime.now(),
            metadata=metadata,
        )

        assert context.metadata == metadata

    def test_get_result_existing(self, base_context):
        """Test getting a result that exists in previous_results."""
        # Add a result to previous_results
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
        )
        base_context.add_result("cdcs", cdcs_result)

        # Retrieve it
        result = base_context.get_result("cdcs")
        assert result is cdcs_result
        assert result.record_id == "cdcs-123"

    def test_get_result_nonexistent(self, base_context):
        """Test getting a result that doesn't exist."""
        result = base_context.get_result("nonexistent")
        assert result is None

    def test_add_result(self, base_context):
        """Test adding a result to the context."""
        result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
        )

        base_context.add_result("cdcs", result)

        # Verify it was added
        assert "cdcs" in base_context.previous_results
        assert base_context.previous_results["cdcs"] is result
        assert base_context.get_result("cdcs") is result

    def test_add_result_overwrites_existing(self, base_context):
        """Test that add_result overwrites existing results."""
        # Add initial result
        first_result = ExportResult(
            success=False,
            destination_name="cdcs",
            error_message="First attempt failed",
        )
        base_context.add_result("cdcs", first_result)

        # Overwrite with new result
        second_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-456",
        )
        base_context.add_result("cdcs", second_result)

        # Verify only the second result remains
        assert base_context.get_result("cdcs") is second_result
        assert base_context.get_result("cdcs").success is True
        assert base_context.get_result("cdcs").record_id == "cdcs-456"

    def test_add_result_multiple_destinations(self, base_context):
        """Test adding results from multiple destinations."""
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
        )
        elabftw_result = ExportResult(
            success=True,
            destination_name="elabftw",
            record_id="elabftw-456",
        )
        labarchives_result = ExportResult(
            success=False,
            destination_name="labarchives",
            error_message="Connection failed",
        )

        base_context.add_result("cdcs", cdcs_result)
        base_context.add_result("elabftw", elabftw_result)
        base_context.add_result("labarchives", labarchives_result)

        # Verify all results are stored independently
        assert len(base_context.previous_results) == 3
        assert base_context.get_result("cdcs") is cdcs_result
        assert base_context.get_result("elabftw") is elabftw_result
        assert base_context.get_result("labarchives") is labarchives_result

    def test_has_successful_export_true(self, base_context):
        """Test has_successful_export when destination succeeded."""
        # Add a successful result
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-123",
        )
        base_context.add_result("cdcs", cdcs_result)

        assert base_context.has_successful_export("cdcs") is True

    def test_has_successful_export_failed(self, base_context):
        """Test has_successful_export when destination failed."""
        # Add a failed result
        cdcs_result = ExportResult(
            success=False,
            destination_name="cdcs",
            error_message="Upload failed",
        )
        base_context.add_result("cdcs", cdcs_result)

        assert base_context.has_successful_export("cdcs") is False

    def test_has_successful_export_missing(self, base_context):
        """Test has_successful_export when destination hasn't run."""
        assert base_context.has_successful_export("cdcs") is False

    def test_previous_results_accumulation(self, base_context):
        """Test that previous_results can accumulate multiple results."""
        # Simulate results from multiple destinations
        cdcs_result = ExportResult(
            success=True, destination_name="cdcs", record_id="cdcs-123"
        )
        labarchives_result = ExportResult(
            success=True, destination_name="labarchives", record_id="la-456"
        )
        elabftw_result = ExportResult(
            success=False,
            destination_name="elabftw",
            error_message="Connection timeout",
        )

        base_context.add_result("cdcs", cdcs_result)
        base_context.add_result("labarchives", labarchives_result)
        base_context.add_result("elabftw", elabftw_result)

        # Verify all results are accessible
        assert base_context.get_result("cdcs") is cdcs_result
        assert base_context.get_result("labarchives") is labarchives_result
        assert base_context.get_result("elabftw") is elabftw_result

        # Verify success checks
        assert base_context.has_successful_export("cdcs") is True
        assert base_context.has_successful_export("labarchives") is True
        assert base_context.has_successful_export("elabftw") is False

    def test_dependency_scenario(self, base_context):
        """Test a realistic dependency scenario (LabArchives accessing CDCS result)."""
        # Simulate CDCS export running first (priority 100)
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="cdcs-789",
            record_url="http://cdcs.example.com/data?id=cdcs-789",
        )
        base_context.add_result("cdcs", cdcs_result)

        # LabArchives (priority 90) runs second and can access CDCS result
        if base_context.has_successful_export("cdcs"):
            cdcs_info = base_context.get_result("cdcs")
            # Simulate using CDCS URL in LabArchives export
            assert cdcs_info.record_url == "http://cdcs.example.com/data?id=cdcs-789"
            labarchives_metadata = {
                "included_cdcs_link": True,
                "cdcs_url": cdcs_info.record_url,
            }

            labarchives_result = ExportResult(
                success=True,
                destination_name="labarchives",
                record_id="la-999",
                metadata=labarchives_metadata,
            )
            base_context.add_result("labarchives", labarchives_result)

        # Verify the dependency worked
        assert base_context.has_successful_export("labarchives") is True
        la_result = base_context.get_result("labarchives")
        assert la_result.metadata["included_cdcs_link"] is True
        assert "cdcs-789" in la_result.metadata["cdcs_url"]
