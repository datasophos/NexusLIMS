"""
Integration tests for CDCS (Configurable Data Curation System) integration.

These tests verify that NexusLIMS can correctly interact with a CDCS instance
to upload, retrieve, and manage experiment records.
"""

import logging
from http import HTTPStatus

import pytest
import requests

from nexusLIMS import cdcs
from nexusLIMS.utils import AuthenticationError

logger = logging.getLogger(__name__)


def _handle_upload_result(result):
    """
    Helper to handle upload_record_content return value.

    upload_record_content returns either (response, record_id) on success
    or just response on failure.
    """
    if isinstance(result, tuple):
        return result
    return result, None


# Minimal valid XML record that conforms to the Nexus Experiment schema
# The summary element is a complex type with child elements
# The instrument element is inside the summary
MINIMAL_TEST_RECORD = """<?xml version="1.0" encoding="UTF-8"?>
<Experiment xmlns="https://data.nist.gov/od/dm/nexus/experiment/v1.0">
    <summary>
        <instrument pid="test-instrument-001">Test Instrument</instrument>
        <reservationStart>2024-01-01T10:00:00</reservationStart>
        <reservationEnd>2024-01-01T12:00:00</reservationEnd>
        <motivation>Testing CDCS integration</motivation>
    </summary>
</Experiment>
"""


@pytest.mark.integration
class TestCdcsServiceAccess:
    """Test basic CDCS service accessibility."""

    def test_cdcs_service_is_accessible(self, cdcs_url):
        """Test that CDCS service is accessible via HTTP."""
        response = requests.get(cdcs_url, timeout=10)
        assert response.status_code == 200

    def test_cdcs_rest_api_is_accessible(self, cdcs_url):
        """Test that CDCS REST API endpoint exists."""
        # Try to access workspace endpoint (should require auth)
        response = requests.get(
            f"{cdcs_url}/rest/workspace/read_access",
            timeout=10,
        )
        # Should return 401 Unauthorized without credentials
        assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.integration
class TestCdcsAuthentication:
    """Test CDCS authentication and authorization."""

    def test_get_workspace_id_with_valid_credentials(self, cdcs_client):
        """Test fetching workspace ID with valid credentials."""
        workspace_id = cdcs.get_workspace_id()
        assert workspace_id is not None
        assert isinstance(workspace_id, str)
        assert len(workspace_id) > 0

    def test_get_workspace_id_with_invalid_credentials(self, cdcs_url, monkeypatch):
        """Test that invalid credentials raise AuthenticationError."""
        from nexusLIMS.config import refresh_settings

        # Set invalid credentials
        monkeypatch.setenv("NX_CDCS_URL", cdcs_url)
        monkeypatch.setenv("NX_CDCS_USER", "invalid_user")
        monkeypatch.setenv("NX_CDCS_PASS", "invalid_password")
        refresh_settings()

        # Should raise AuthenticationError
        with pytest.raises(AuthenticationError):
            cdcs.get_workspace_id()

    def test_get_template_id_with_valid_credentials(self, cdcs_client):
        """Test fetching template ID with valid credentials."""
        template_id = cdcs.get_template_id()
        assert template_id is not None
        assert isinstance(template_id, str)
        assert len(template_id) > 0

    def test_get_template_id_with_invalid_credentials(self, cdcs_url, monkeypatch):
        """Test that invalid credentials raise AuthenticationError."""
        from nexusLIMS.config import refresh_settings

        # Set invalid credentials
        monkeypatch.setenv("NX_CDCS_URL", cdcs_url)
        monkeypatch.setenv("NX_CDCS_USER", "invalid_user")
        monkeypatch.setenv("NX_CDCS_PASS", "invalid_password")
        refresh_settings()

        # Should raise AuthenticationError
        with pytest.raises(AuthenticationError):
            cdcs.get_template_id()


@pytest.mark.integration
class TestCdcsRecordOperations:
    """Test CDCS record upload, retrieval, and deletion."""

    def test_upload_minimal_record(self, cdcs_client):
        """Test uploading a minimal valid XML record to CDCS."""
        title = "Test Record - Minimal"
        response, record_id = _handle_upload_result(
            cdcs.upload_record_content(MINIMAL_TEST_RECORD, title)
        )

        # Verify upload was successful
        assert response.status_code == HTTPStatus.CREATED
        assert record_id is not None
        assert isinstance(record_id, str)
        assert len(record_id) > 0

        # Register for cleanup
        cdcs_client["register_record"](record_id)

    def test_upload_record_with_special_characters_in_title(self, cdcs_client):
        """Test uploading a record with special characters in title."""
        title = "Test Record: Special Characters & Symbols (2024)"
        response, record_id = _handle_upload_result(
            cdcs.upload_record_content(MINIMAL_TEST_RECORD, title)
        )

        # Verify upload was successful
        assert response.status_code == HTTPStatus.CREATED
        assert record_id is not None

        # Register for cleanup
        cdcs_client["register_record"](record_id)

    def test_upload_invalid_xml_record(self, cdcs_client):
        """Test that uploading invalid XML fails appropriately."""
        invalid_xml = "<InvalidRoot>This is not a valid Nexus Experiment</InvalidRoot>"
        title = "Test Record - Invalid"

        response, record_id = _handle_upload_result(
            cdcs.upload_record_content(invalid_xml, title)
        )

        # Should fail (not return 201 CREATED)
        assert response.status_code != HTTPStatus.CREATED
        # record_id should be None on failure
        assert record_id is None

    def test_delete_existing_record(self, cdcs_client):
        """Test deleting an existing record from CDCS."""
        # First upload a record
        title = "Test Record - To Be Deleted"
        upload_response, record_id = _handle_upload_result(
            cdcs.upload_record_content(
                MINIMAL_TEST_RECORD,
                title,
            )
        )
        assert upload_response.status_code == HTTPStatus.CREATED

        # Now delete it
        delete_response = cdcs.delete_record(record_id)

        # Verify deletion was successful (204 No Content)
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Note: We don't register for cleanup since we already deleted it

    def test_delete_nonexistent_record(self, cdcs_client):
        """Test deleting a non-existent record."""
        # Use a fake record ID that doesn't exist
        fake_record_id = "000000000000000000000000"  # 24-character hex string

        delete_response = cdcs.delete_record(fake_record_id)

        # Should fail (not return 204 No Content)
        assert delete_response.status_code != HTTPStatus.NO_CONTENT

    def test_upload_multiple_records(self, cdcs_client):
        """Test uploading multiple records in sequence."""
        record_ids = []

        for i in range(3):
            title = f"Test Record - Multiple Upload {i + 1}"
            response, record_id = _handle_upload_result(
                cdcs.upload_record_content(
                    MINIMAL_TEST_RECORD,
                    title,
                )
            )

            assert response.status_code == HTTPStatus.CREATED
            assert record_id is not None
            record_ids.append(record_id)

            # Register for cleanup
            cdcs_client["register_record"](record_id)

        # Verify we got unique record IDs
        assert len(record_ids) == len(set(record_ids))


@pytest.mark.integration
class TestCdcsRecordRetrieval:
    """Test retrieving records from CDCS."""

    def test_retrieve_uploaded_record(self, cdcs_client, cdcs_url):
        """Test that an uploaded record can be retrieved via API."""
        # Upload a record first
        title = "Test Record - Retrieval"
        upload_response, record_id = _handle_upload_result(
            cdcs.upload_record_content(
                MINIMAL_TEST_RECORD,
                title,
            )
        )
        assert upload_response.status_code == HTTPStatus.CREATED

        # Register for cleanup
        cdcs_client["register_record"](record_id)

        # Now try to retrieve it via REST API
        from urllib.parse import urljoin

        from nexusLIMS.utils import nexus_req

        endpoint = urljoin(cdcs_url, f"rest/data/{record_id}")
        response = nexus_req(endpoint, "GET", basic_auth=True)

        # Verify retrieval was successful
        assert response.status_code == HTTPStatus.OK
        record_data = response.json()
        assert record_data["id"] == record_id
        assert record_data["title"] == title

    def test_retrieve_record_xml_content(self, cdcs_client, cdcs_url):
        """Test retrieving the XML content of an uploaded record."""
        # Upload a record first
        title = "Test Record - XML Content Retrieval"
        upload_response, record_id = _handle_upload_result(
            cdcs.upload_record_content(
                MINIMAL_TEST_RECORD,
                title,
            )
        )
        assert upload_response.status_code == HTTPStatus.CREATED

        # Register for cleanup
        cdcs_client["register_record"](record_id)

        # Retrieve the record
        from urllib.parse import urljoin

        from nexusLIMS.utils import nexus_req

        endpoint = urljoin(cdcs_url, f"rest/data/{record_id}")
        response = nexus_req(endpoint, "GET", basic_auth=True)

        assert response.status_code == HTTPStatus.OK
        record_data = response.json()

        # Check that XML content is present
        assert "xml_content" in record_data
        # The uploaded XML should be in the response
        assert "Experiment" in record_data["xml_content"]
        assert "Testing CDCS integration" in record_data["xml_content"]


@pytest.mark.integration
class TestCdcsWorkspaceAssignment:
    """Test workspace assignment functionality."""

    def test_record_assigned_to_workspace(self, cdcs_client, cdcs_url):
        """Test that uploaded records are assigned to the workspace."""
        # Upload a record
        title = "Test Record - Workspace Assignment"
        upload_response, record_id = _handle_upload_result(
            cdcs.upload_record_content(
                MINIMAL_TEST_RECORD,
                title,
            )
        )
        assert upload_response.status_code == HTTPStatus.CREATED

        # Register for cleanup
        cdcs_client["register_record"](record_id)

        # Verify the record is in the workspace
        from urllib.parse import urljoin

        from nexusLIMS.utils import nexus_req

        workspace_id = cdcs.get_workspace_id()
        endpoint = urljoin(
            cdcs_url,
            f"rest/workspace/{workspace_id}/data/",
        )
        response = nexus_req(endpoint, "GET", basic_auth=True)

        assert response.status_code == HTTPStatus.OK
        workspace_records = response.json()

        # Check that our record is in the workspace
        record_ids = [r["id"] for r in workspace_records]
        assert record_id in record_ids


@pytest.mark.integration
class TestCdcsErrorHandling:
    """Test error handling in CDCS integration."""

    def test_upload_with_empty_xml(self, cdcs_client):
        """Test handling of empty XML content."""
        title = "Test Record - Empty XML"
        response, record_id = _handle_upload_result(
            cdcs.upload_record_content("", title)
        )

        # Should fail (not return 201 CREATED)
        assert response.status_code != HTTPStatus.CREATED

    def test_upload_with_malformed_xml(self, cdcs_client):
        """Test handling of malformed XML."""
        malformed_xml = "<Experiment><unclosed>"
        title = "Test Record - Malformed XML"
        response, record_id = _handle_upload_result(
            cdcs.upload_record_content(malformed_xml, title)
        )

        # Should fail (not return 201 CREATED)
        assert response.status_code != HTTPStatus.CREATED

    def test_upload_with_empty_title(self, cdcs_client):
        """Test uploading a record with empty title."""
        # This might be allowed by CDCS, or it might fail
        # Either way, we should handle it gracefully
        response, record_id = _handle_upload_result(
            cdcs.upload_record_content(MINIMAL_TEST_RECORD, "")
        )

        # Check result - either succeeds with empty title or fails gracefully
        if response.status_code == HTTPStatus.CREATED:
            # If it succeeded, register for cleanup
            cdcs_client["register_record"](record_id)
        else:
            # If it failed, that's also acceptable
            assert response.status_code != HTTPStatus.CREATED


@pytest.mark.integration
class TestCdcsUrlConfiguration:
    """Test CDCS URL configuration and validation."""

    def test_get_cdcs_url(self, cdcs_client, cdcs_url):
        """Test retrieving configured CDCS URL."""
        url = cdcs.get_cdcs_url()
        # Pydantic may add trailing slash, so normalize for comparison
        assert url.rstrip("/") == cdcs_url.rstrip("/")
        assert url.startswith("http")

    def test_cdcs_url_with_trailing_slash(self, cdcs_client, cdcs_url, monkeypatch):
        """Test that CDCS URLs are handled correctly with/without trailing slash."""
        from nexusLIMS.config import refresh_settings

        # Test with trailing slash
        monkeypatch.setenv("NX_CDCS_URL", f"{cdcs_url}/")
        refresh_settings()

        # Should still work (urljoin handles this)
        workspace_id = cdcs.get_workspace_id()
        assert workspace_id is not None
