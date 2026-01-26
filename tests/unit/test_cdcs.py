"""Tests functionality related to the interacting with the CDCS frontend."""

# pylint: disable=missing-function-docstring
# ruff: noqa: D102, ARG005

from typing import NamedTuple

import pytest

from nexusLIMS.utils import AuthenticationError, CDCSUtils


class MockResponse(NamedTuple):
    """Mock response for HTTP requests in tests."""

    status_code: int
    text: str


class MockResponseWithJson(NamedTuple):
    """Mock response with JSON field for HTTP requests in tests."""

    status_code: int
    text: str
    json: object


class TestCDCS:
    """Test the CDCS utility functions."""

    @pytest.fixture(autouse=True)
    def _setup_cdcs_env(self, monkeypatch, mock_cdcs_server):
        """Set up CDCS environment variables and mock server."""
        monkeypatch.setenv("NX_CDCS_URL", "http://test-cdcs.example.com")
        monkeypatch.setenv("NX_CDCS_TOKEN", "test-api-token-not-for-production")

    def test_bad_auth(self, monkeypatch):
        """Test that bad authentication credentials raise AuthenticationError."""
        from http import HTTPStatus

        # Override the mock_cdcs_server to return 401 for bad auth
        def mock_nexus_req_bad_auth(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.UNAUTHORIZED,
                text="Unauthorized",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_bad_auth)

        with pytest.raises(AuthenticationError):
            CDCSUtils.get_workspace_id()
        with pytest.raises(AuthenticationError):
            CDCSUtils.get_template_id()

    def test_delete_record_bad_response(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "nexusLIMS.utils.nexus_req",
            lambda _x, _y, token_auth=None: MockResponse(
                status_code=404,
                text="This is a fake request error!",
            ),
        )
        CDCSUtils.delete_record("dummy")
        assert "Received error while deleting dummy:" in caplog.text
        assert "This is a fake request error!" in caplog.text

    def test_search_records_unauthorized(self, monkeypatch):
        """Test search_records with authentication error."""
        from http import HTTPStatus

        def mock_nexus_req_unauthorized(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.UNAUTHORIZED,
                text="Unauthorized",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_unauthorized)

        with pytest.raises(AuthenticationError, match="Could not authenticate to CDCS"):
            CDCSUtils.search_records(title="test")

    def test_search_records_bad_request(self, monkeypatch, caplog):
        """Test search_records with bad request error."""
        from http import HTTPStatus

        def mock_nexus_req_bad_request(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.BAD_REQUEST,
                text="Invalid query parameters",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_bad_request)

        with pytest.raises(ValueError, match="Invalid search parameters"):
            CDCSUtils.search_records(title="test")

        assert "Bad request while searching records" in caplog.text

    def test_search_records_server_error(self, monkeypatch, caplog):
        """Test search_records with server error returns empty list."""
        from http import HTTPStatus

        def mock_nexus_req_server_error(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Server error",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_server_error)

        results = CDCSUtils.search_records(title="test")

        assert results == []
        assert "Got error while searching records" in caplog.text

    def test_download_record_unauthorized(self, monkeypatch):
        """Test download_record with authentication error."""
        from http import HTTPStatus

        def mock_nexus_req_unauthorized(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.UNAUTHORIZED,
                text="Unauthorized",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_unauthorized)

        with pytest.raises(AuthenticationError, match="Could not authenticate to CDCS"):
            CDCSUtils.download_record("test_id")

    def test_download_record_not_found(self, monkeypatch):
        """Test download_record with record not found."""
        from http import HTTPStatus

        def mock_nexus_req_not_found(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.NOT_FOUND,
                text="Not found",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_not_found)

        with pytest.raises(ValueError, match="Record with id test_id not found"):
            CDCSUtils.download_record("test_id")

    def test_download_record_server_error(self, monkeypatch, caplog):
        """Test download_record with server error."""
        from http import HTTPStatus

        def mock_nexus_req_server_error(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Server error",
            )

        monkeypatch.setattr("nexusLIMS.utils.nexus_req", mock_nexus_req_server_error)

        with pytest.raises(ValueError, match="Failed to download record test_id"):
            CDCSUtils.download_record("test_id")

        assert "Got error while downloading test_id" in caplog.text
