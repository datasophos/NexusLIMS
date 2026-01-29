# ruff: noqa: SLF001
"""Unit tests for the CDCS export destination plugin."""

from datetime import datetime
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from nexusLIMS.exporters.base import ExportContext
from nexusLIMS.exporters.destinations.cdcs import CDCSDestination
from nexusLIMS.utils.cdcs import AuthenticationError


@pytest.fixture
def mock_config_enabled():
    """Mock settings with CDCS enabled."""
    with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_settings:
        mock_settings.NX_CDCS_TOKEN = "test_token"
        mock_settings.NX_CDCS_URL = "http://localhost:8000"
        yield mock_settings


@pytest.fixture
def mock_config_disabled():
    """Mock settings with CDCS disabled."""
    with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_settings:
        mock_settings.NX_CDCS_TOKEN = None
        mock_settings.NX_CDCS_URL = None
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


class TestCDCSDestinationConfiguration:
    """Test CDCS destination configuration and validation."""

    def test_name_and_priority(self):
        """Test that CDCS destination has correct name and priority."""
        dest = CDCSDestination()
        assert dest.name == "cdcs"
        assert dest.priority == 100

    def test_enabled_with_config(self, mock_config_enabled):
        """Test that destination is enabled when configured."""
        dest = CDCSDestination()
        assert dest.enabled is True

    def test_enabled_without_token(self):
        """Test that destination is disabled without token."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            mock_cfg.NX_CDCS_TOKEN = None
            mock_cfg.NX_CDCS_URL = "http://localhost:8000"

            dest = CDCSDestination()
            assert dest.enabled is False

    def test_enabled_without_url(self):
        """Test that destination is disabled without URL."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            mock_cfg.NX_CDCS_TOKEN = "test_token"
            mock_cfg.NX_CDCS_URL = None

            dest = CDCSDestination()
            assert dest.enabled is False

    def test_enabled_without_any_config(self, mock_config_disabled):
        """Test that destination is disabled without any config."""
        dest = CDCSDestination()
        assert dest.enabled is False

    def test_validate_config_missing_token(self):
        """Test validate_config when token is missing."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            # Remove token attribute entirely
            if hasattr(mock_cfg, "NX_CDCS_TOKEN"):
                delattr(mock_cfg, "NX_CDCS_TOKEN")

            dest = CDCSDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_CDCS_TOKEN not configured" in error_msg

    def test_validate_config_empty_token(self):
        """Test validate_config when token is empty."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            mock_cfg.NX_CDCS_TOKEN = ""
            mock_cfg.NX_CDCS_URL = "http://localhost:8000"

            dest = CDCSDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_CDCS_TOKEN is empty" in error_msg

    def test_validate_config_missing_url(self):
        """Test validate_config when URL is missing."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            mock_cfg.NX_CDCS_TOKEN = "test_token"
            # Remove URL attribute entirely
            if hasattr(mock_cfg, "NX_CDCS_URL"):
                delattr(mock_cfg, "NX_CDCS_URL")

            dest = CDCSDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_CDCS_URL not configured" in error_msg

    def test_validate_config_empty_url(self):
        """Test validate_config when URL is empty."""
        with patch("nexusLIMS.exporters.destinations.cdcs.settings") as mock_cfg:
            mock_cfg.NX_CDCS_TOKEN = "test_token"
            mock_cfg.NX_CDCS_URL = ""

            dest = CDCSDestination()
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "NX_CDCS_URL is empty" in error_msg

    def test_validate_config_authentication_failure(self, mock_config_enabled):
        """Test validate_config when authentication fails."""
        dest = CDCSDestination()

        # Mock _get_workspace_id to raise AuthenticationError
        with patch.object(
            dest, "_get_workspace_id", side_effect=AuthenticationError("Auth failed")
        ):
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "CDCS authentication failed" in error_msg
            assert "Auth failed" in error_msg

    def test_validate_config_generic_exception(self, mock_config_enabled):
        """Test validate_config when generic exception occurs."""
        dest = CDCSDestination()

        # Mock _get_workspace_id to raise a generic exception
        with patch.object(
            dest, "_get_workspace_id", side_effect=RuntimeError("Connection timeout")
        ):
            is_valid, error_msg = dest.validate_config()

            assert is_valid is False
            assert "CDCS configuration error" in error_msg
            assert "Connection timeout" in error_msg

    def test_validate_config_success(self, mock_config_enabled):
        """Test validate_config when everything is configured correctly."""
        dest = CDCSDestination()

        # Mock _get_workspace_id to succeed
        with patch.object(dest, "_get_workspace_id", return_value=1):
            is_valid, error_msg = dest.validate_config()

            assert is_valid is True
            assert error_msg is None


class TestCDCSDestinationExport:
    """Test CDCS destination export functionality."""

    def test_export_success(self, mock_config_enabled, export_context):
        """Test successful export to CDCS."""
        dest = CDCSDestination()

        # Mock _upload_to_cdcs
        with patch.object(
            dest,
            "_upload_to_cdcs",
            return_value=(123, "http://localhost:8000/data?id=123"),
        ):
            result = dest.export(export_context)

            assert result.success is True
            assert result.destination_name == "cdcs"
            assert result.record_id == "123"
            assert result.record_url == "http://localhost:8000/data?id=123"
            assert result.error_message is None

    def test_export_failure_exception(self, mock_config_enabled, export_context):
        """Test export failure when exception is raised."""
        dest = CDCSDestination()

        # Mock _upload_to_cdcs to raise exception
        with patch.object(
            dest, "_upload_to_cdcs", side_effect=RuntimeError("Upload failed")
        ):
            result = dest.export(export_context)

            assert result.success is False
            assert result.destination_name == "cdcs"
            assert result.record_id is None
            assert result.record_url is None
            assert "Upload failed" in result.error_message

    def test_export_file_read_error(self, mock_config_enabled, tmp_path):
        """Test export failure when XML file cannot be read."""
        dest = CDCSDestination()

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
        assert result.destination_name == "cdcs"
        assert result.error_message is not None

    def test_export_never_raises_exception(self, mock_config_enabled, export_context):
        """Test that export never raises exceptions (catches all errors)."""
        dest = CDCSDestination()

        # Mock _upload_to_cdcs to raise various exceptions
        exceptions = [
            RuntimeError("Runtime error"),
            ValueError("Value error"),
            Exception("Generic exception"),
        ]

        for exc in exceptions:
            with patch.object(dest, "_upload_to_cdcs", side_effect=exc):
                # Should not raise, should return failed result
                result = dest.export(export_context)
                assert result.success is False
                assert result.error_message is not None


class TestCDCSDestinationHelperMethods:
    """Test CDCS destination helper methods."""

    def test_get_template_id_success(self, mock_config_enabled):
        """Test _get_template_id with successful response."""
        dest = CDCSDestination()

        mock_response = Mock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.json.return_value = [{"current": "template-456"}]

        with patch(
            "nexusLIMS.exporters.destinations.cdcs.nexus_req",
            return_value=mock_response,
        ):
            template_id = dest._get_template_id()
            assert template_id == "template-456"

    def test_get_template_id_unauthorized(self, mock_config_enabled):
        """Test _get_template_id with unauthorized response."""
        dest = CDCSDestination()

        mock_response = Mock()
        mock_response.status_code = HTTPStatus.UNAUTHORIZED

        with (
            patch(
                "nexusLIMS.exporters.destinations.cdcs.nexus_req",
                return_value=mock_response,
            ),
            pytest.raises(AuthenticationError, match="Could not authenticate to CDCS"),
        ):
            dest._get_template_id()

    def test_get_template_id_forbidden(self, mock_config_enabled):
        """Test _get_template_id with forbidden response."""
        dest = CDCSDestination()

        mock_response = Mock()
        mock_response.status_code = HTTPStatus.FORBIDDEN

        with (
            patch(
                "nexusLIMS.exporters.destinations.cdcs.nexus_req",
                return_value=mock_response,
            ),
            pytest.raises(AuthenticationError, match="Could not authenticate to CDCS"),
        ):
            dest._get_template_id()

    def test_get_workspace_id_success(self, mock_config_enabled):
        """Test _get_workspace_id with successful response."""
        dest = CDCSDestination()

        mock_response = Mock()
        mock_response.status_code = HTTPStatus.OK
        mock_response.json.return_value = [{"id": 789}]

        with patch(
            "nexusLIMS.exporters.destinations.cdcs.nexus_req",
            return_value=mock_response,
        ):
            workspace_id = dest._get_workspace_id()
            assert workspace_id == 789

    def test_get_workspace_id_unauthorized(self, mock_config_enabled):
        """Test _get_workspace_id with unauthorized response."""
        dest = CDCSDestination()

        mock_response = Mock()
        mock_response.status_code = HTTPStatus.UNAUTHORIZED

        with (
            patch(
                "nexusLIMS.exporters.destinations.cdcs.nexus_req",
                return_value=mock_response,
            ),
            pytest.raises(AuthenticationError, match="Could not authenticate to CDCS"),
        ):
            dest._get_workspace_id()

    def test_upload_to_cdcs_success(self, mock_config_enabled):
        """Test _upload_to_cdcs with successful upload."""
        dest = CDCSDestination()

        # Mock POST request (create record)
        mock_post_response = Mock()
        mock_post_response.status_code = HTTPStatus.CREATED
        mock_post_response.json.return_value = {"id": 789}

        # Mock PATCH request (assign to workspace)
        mock_patch_response = Mock()
        mock_patch_response.status_code = HTTPStatus.OK

        with (
            patch.object(dest, "_get_template_id", return_value="template-123"),
            patch.object(dest, "_get_workspace_id", return_value=456),
            patch(
                "nexusLIMS.exporters.destinations.cdcs.nexus_req",
                side_effect=[mock_post_response, mock_patch_response],
            ),
        ):
            record_id, record_url = dest._upload_to_cdcs(
                "<record>test</record>", "test_title"
            )

            assert record_id == 789
            assert record_url == "http://localhost:8000/data?id=789"

    def test_upload_to_cdcs_create_failure(self, mock_config_enabled):
        """Test _upload_to_cdcs when record creation fails."""
        dest = CDCSDestination()

        with patch.object(dest, "_get_template_id", return_value="template-123"):
            # Mock failed POST request
            mock_post_response = Mock()
            mock_post_response.status_code = HTTPStatus.BAD_REQUEST
            mock_post_response.text = "Invalid XML"

            with (
                patch(
                    "nexusLIMS.exporters.destinations.cdcs.nexus_req",
                    return_value=mock_post_response,
                ),
                pytest.raises(RuntimeError, match="CDCS upload failed"),
            ):
                dest._upload_to_cdcs("<record>test</record>", "test_title")


class TestCDCSDestinationIntegration:
    """Integration-style tests for CDCS destination."""

    def test_full_export_workflow(self, mock_config_enabled, export_context):
        """Test complete export workflow from context to result."""
        dest = CDCSDestination()

        # Mock all external dependencies
        mock_template_response = Mock()
        mock_template_response.status_code = HTTPStatus.OK
        mock_template_response.json.return_value = [{"current": "template-123"}]

        mock_workspace_response = Mock()
        mock_workspace_response.status_code = HTTPStatus.OK
        mock_workspace_response.json.return_value = [{"id": 456}]

        mock_create_response = Mock()
        mock_create_response.status_code = HTTPStatus.CREATED
        mock_create_response.json.return_value = {"id": 789}

        mock_assign_response = Mock()
        mock_assign_response.status_code = HTTPStatus.OK

        with patch(
            "nexusLIMS.exporters.destinations.cdcs.nexus_req",
            side_effect=[
                mock_template_response,  # get_template_id
                mock_create_response,  # create record
                mock_workspace_response,  # get_workspace_id
                mock_assign_response,  # assign to workspace
            ],
        ):
            result = dest.export(export_context)

            assert result.success is True
            assert result.destination_name == "cdcs"
            assert result.record_id == "789"
            assert "data?id=789" in result.record_url
