# ruff: noqa: SLF001
"""Unit tests for the LabArchives export destination plugin."""

from datetime import datetime
from unittest.mock import patch

import pytest

from nexusLIMS.exporters.base import ExportContext
from nexusLIMS.exporters.destinations.labarchives import LabArchivesDestination


@pytest.fixture
def mock_config_enabled():
    """Mock settings with LabArchives enabled."""
    with patch(
        "nexusLIMS.exporters.destinations.labarchives.settings"
    ) as mock_settings:
        mock_settings.NX_LABARCHIVES_API_KEY = "test_api_key"
        mock_settings.NX_LABARCHIVES_URL = "http://localhost:9000"
        yield mock_settings


@pytest.fixture
def mock_config_disabled():
    """Mock settings with LabArchives disabled."""
    with patch(
        "nexusLIMS.exporters.destinations.labarchives.settings"
    ) as mock_settings:
        mock_settings.NX_LABARCHIVES_API_KEY = None
        mock_settings.NX_LABARCHIVES_URL = None
        yield mock_settings


@pytest.fixture
def export_context(tmp_path):
    """Create a basic export context for testing."""
    xml_file = tmp_path / "test_record.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<record>
    <session>test-session-123</session>
    <instrument>test-instrument</instrument>
</record>"""
    xml_file.write_text(xml_content)

    return ExportContext(
        xml_file_path=xml_file,
        session_identifier="test-session-123",
        instrument_pid="test-instrument",
        dt_from=datetime(2025, 1, 1, 10, 0, 0),
        dt_to=datetime(2025, 1, 1, 12, 0, 0),
        user="testuser",
    )


class TestLabArchivesDestinationConfiguration:
    """Test LabArchives destination configuration and validation."""

    def test_name_and_priority(self):
        """Test that LabArchives destination has correct name and priority."""
        dest = LabArchivesDestination()
        assert dest.name == "labarchives"
        assert dest.priority == 90

    def test_enabled_with_config(self, mock_config_enabled):
        """Test that destination is enabled when configured."""
        dest = LabArchivesDestination()
        assert dest.enabled is True

    def test_enabled_without_api_key(self):
        """Test that destination is disabled without API key."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            mock_cfg.NX_LABARCHIVES_API_KEY = None
            mock_cfg.NX_LABARCHIVES_URL = "http://localhost:9000"

            dest = LabArchivesDestination()
            assert dest.enabled is False

    def test_enabled_without_url(self):
        """Test that destination is disabled without URL."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            mock_cfg.NX_LABARCHIVES_API_KEY = "test_api_key"
            mock_cfg.NX_LABARCHIVES_URL = None

            dest = LabArchivesDestination()
            assert dest.enabled is False

    def test_enabled_without_any_config(self, mock_config_disabled):
        """Test that destination is disabled without any config."""
        dest = LabArchivesDestination()
        assert dest.enabled is False

    def test_validate_config_missing_api_key(self):
        """Test validate_config when API key is missing."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            # Remove API key attribute entirely
            if hasattr(mock_cfg, "NX_LABARCHIVES_API_KEY"):
                delattr(mock_cfg, "NX_LABARCHIVES_API_KEY")

            dest = LabArchivesDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_LABARCHIVES_API_KEY not configured" in error_msg

    def test_validate_config_empty_api_key(self):
        """Test validate_config when API key is empty."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            mock_cfg.NX_LABARCHIVES_API_KEY = ""
            mock_cfg.NX_LABARCHIVES_URL = "http://localhost:9000"

            dest = LabArchivesDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_LABARCHIVES_API_KEY is empty" in error_msg

    def test_validate_config_missing_url(self):
        """Test validate_config when URL is missing."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            mock_cfg.NX_LABARCHIVES_API_KEY = "test_api_key"
            # Remove URL attribute entirely
            if hasattr(mock_cfg, "NX_LABARCHIVES_URL"):
                delattr(mock_cfg, "NX_LABARCHIVES_URL")

            dest = LabArchivesDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_LABARCHIVES_URL not configured" in error_msg

    def test_validate_config_empty_url(self):
        """Test validate_config when URL is empty."""
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as mock_cfg:
            mock_cfg.NX_LABARCHIVES_API_KEY = "test_api_key"
            mock_cfg.NX_LABARCHIVES_URL = ""

            dest = LabArchivesDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_LABARCHIVES_URL is empty" in error_msg

    def test_validate_config_success_without_auth_check(self, mock_config_enabled):
        """Test validate_config with valid config (auth check not yet implemented)."""
        dest = LabArchivesDestination()
        is_valid, error_msg = dest.validate_config()

        # Should pass basic validation but log warning about auth
        assert is_valid is True
        assert error_msg is None


class TestLabArchivesDestinationExport:
    """Test LabArchives destination export functionality."""

    def test_export_not_yet_implemented(self, mock_config_enabled, export_context):
        """Test that export raises NotImplementedError (skeleton implementation)."""
        dest = LabArchivesDestination()

        # Export should catch the NotImplementedError and return failed result
        result = dest.export(export_context)

        assert result.success is False
        assert result.destination_name == "labarchives"
        assert result.record_id is None
        assert result.record_url is None
        assert "not yet implemented" in result.error_message.lower()

    def test_export_never_raises_exception(self, mock_config_enabled, export_context):
        """Test that export never raises exceptions (catches all errors)."""
        dest = LabArchivesDestination()

        # Even though _upload_to_labarchives raises NotImplementedError,
        # export() should catch it and return a failed result
        result = dest.export(export_context)
        assert result.success is False
        assert result.error_message is not None

    def test_export_file_read_error(self, mock_config_enabled, tmp_path):
        """Test export failure when XML file cannot be read."""
        dest = LabArchivesDestination()

        # Create context with non-existent file
        xml_file = tmp_path / "nonexistent.xml"
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier="test-session",
            instrument_pid="test-instrument",
            dt_from=datetime.now(),
            dt_to=datetime.now(),
        )

        result = dest.export(context)

        assert result.success is False
        assert result.destination_name == "labarchives"
        assert result.error_message is not None

    def test_export_includes_cdcs_url_if_available(
        self, mock_config_enabled, export_context
    ):
        """Test that export method can access CDCS URL from context."""
        from nexusLIMS.exporters.base import ExportResult

        dest = LabArchivesDestination()

        # Add a successful CDCS result to the context
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="123",
            record_url="http://localhost:8000/data?id=123",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        # Export will fail (NotImplementedError), but we can verify the context
        # has the CDCS result available
        result = dest.export(export_context)

        # Verify CDCS result was accessible (even though export failed)
        cdcs_result_from_context = export_context.get_result("cdcs")
        assert cdcs_result_from_context is not None
        assert cdcs_result_from_context.success is True
        assert (
            cdcs_result_from_context.record_url == "http://localhost:8000/data?id=123"
        )

        # Export itself fails (not implemented)
        assert result.success is False


class TestLabArchivesDestinationHelperMethods:
    """Test LabArchives destination helper methods."""

    def test_get_notebook_id_not_implemented(self, mock_config_enabled):
        """Test _get_notebook_id raises NotImplementedError (skeleton)."""
        dest = LabArchivesDestination()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            dest._get_notebook_id("test-instrument")

    def test_upload_to_labarchives_not_implemented(self, mock_config_enabled):
        """Test _upload_to_labarchives raises NotImplementedError (skeleton)."""
        dest = LabArchivesDestination()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            dest._upload_to_labarchives(
                xml_content="<test/>",
                title="test",
                session_id="session-123",
                instrument_id="instrument-456",
            )
