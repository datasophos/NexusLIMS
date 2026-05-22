"""Tests functionality related to the interacting with the CDCS frontend."""

# pylint: disable=missing-function-docstring
# ruff: noqa: ARG005

from http import HTTPStatus
from typing import NamedTuple
from unittest.mock import Mock, patch

import pytest

from nexusLIMS.utils import cdcs


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

        # Patch nexus_req in the cdcs module where it's imported
        monkeypatch.setattr("nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_bad_auth)

        with pytest.raises(cdcs.AuthenticationError):
            cdcs.get_workspace_id()
        with pytest.raises(cdcs.AuthenticationError):
            cdcs.get_template_id()

    def test_delete_record_bad_response(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req",
            lambda _x, _y, token_auth=None: MockResponse(
                status_code=404,
                text="This is a fake request error!",
            ),
        )
        cdcs.delete_record("dummy")
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

        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_unauthorized
        )

        with pytest.raises(
            cdcs.AuthenticationError, match="Could not authenticate to CDCS"
        ):
            cdcs.search_records(title="test")

    def test_search_records_bad_request(self, monkeypatch, caplog):
        """Test search_records with bad request error."""
        from http import HTTPStatus

        def mock_nexus_req_bad_request(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.BAD_REQUEST,
                text="Invalid query parameters",
            )

        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_bad_request
        )

        with pytest.raises(ValueError, match="Invalid search parameters"):
            cdcs.search_records(title="test")

        assert "Bad request while searching records" in caplog.text

    def test_search_records_server_error(self, monkeypatch, caplog):
        """Test search_records with server error returns empty list."""
        from http import HTTPStatus

        def mock_nexus_req_server_error(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Server error",
            )

        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_server_error
        )

        results = cdcs.search_records(title="test")

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

        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_unauthorized
        )

        with pytest.raises(
            cdcs.AuthenticationError, match="Could not authenticate to CDCS"
        ):
            cdcs.download_record("test_id")

    def test_download_record_not_found(self, monkeypatch):
        """Test download_record with record not found."""
        from http import HTTPStatus

        def mock_nexus_req_not_found(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.NOT_FOUND,
                text="Not found",
            )

        monkeypatch.setattr("nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_not_found)

        with pytest.raises(ValueError, match="Record with id test_id not found"):
            cdcs.download_record("test_id")

    def test_download_record_server_error(self, monkeypatch, caplog):
        """Test download_record with server error."""
        from http import HTTPStatus

        def mock_nexus_req_server_error(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                text="Server error",
            )

        monkeypatch.setattr(
            "nexusLIMS.utils.cdcs.nexus_req", mock_nexus_req_server_error
        )

        with pytest.raises(ValueError, match="Failed to download record test_id"):
            cdcs.download_record("test_id")

        assert "Got error while downloading test_id" in caplog.text


class TestCDCSUserManager:
    """Tests for CDCSUserManager."""

    BASE_URL = "http://localhost:8000/"
    TOKEN = "test-token"

    @pytest.fixture
    def manager(self):
        from nexusLIMS.utils.cdcs import CDCSUserManager

        return CDCSUserManager(self.BASE_URL, self.TOKEN)

    @pytest.fixture
    def user_list(self):
        return [
            {"id": 1, "username": "alice", "email": "alice@example.com"},
            {"id": 2, "username": "bob", "email": "bob@example.com"},
        ]

    def test_get_or_create_user_match_by_username(self, manager, user_list):
        """Returns existing user when username matches."""
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = user_list

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.get_or_create_user("alice", "other@example.com", "A", "L")

        assert result["id"] == 1
        assert result["username"] == "alice"

    def test_get_or_create_user_match_by_email(self, manager, user_list):
        """Falls back to email match when username is not found."""
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = user_list

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.get_or_create_user("newname", "bob@example.com", "B", "O")

        assert result["id"] == 2
        assert result["username"] == "bob"

    def test_get_or_create_user_creates_when_not_found(self, manager, user_list):
        """Creates a new user when neither username nor email matches."""
        mock_list_resp = Mock()
        mock_list_resp.ok = True
        mock_list_resp.json.return_value = user_list

        created_user = {"id": 3, "username": "carol", "email": "carol@example.com"}
        mock_create_resp = Mock()
        mock_create_resp.status_code = HTTPStatus.CREATED
        mock_create_resp.json.return_value = created_user

        with patch(
            "nexusLIMS.utils.cdcs.nexus_req",
            side_effect=[mock_list_resp, mock_create_resp],
        ):
            result = manager.get_or_create_user(
                "carol", "carol@example.com", "Carol", "C"
            )

        assert result["id"] == 3
        assert result["username"] == "carol"

    def test_get_or_create_user_create_fails(self, manager, user_list):
        """Returns None when user creation fails (non-201 response)."""
        mock_list_resp = Mock()
        mock_list_resp.ok = True
        mock_list_resp.json.return_value = user_list

        mock_create_resp = Mock()
        mock_create_resp.status_code = HTTPStatus.BAD_REQUEST
        mock_create_resp.text = "Username taken"

        with patch(
            "nexusLIMS.utils.cdcs.nexus_req",
            side_effect=[mock_list_resp, mock_create_resp],
        ):
            result = manager.get_or_create_user("new", "new@example.com", "N", "E")

        assert result is None

    def test_get_or_create_user_non_list_response(self, manager):
        """Returns None when GET rest/user/ does not return a list."""
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"detail": "unexpected object"}

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.get_or_create_user("alice", "alice@example.com", "A", "L")

        assert result is None

    def test_get_or_create_user_fetch_fails(self, manager):
        """Returns None when GET rest/user/ returns a non-OK response."""
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.text = "Forbidden"

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.get_or_create_user("alice", "alice@example.com", "A", "L")

        assert result is None

    def test_user_list_cached_across_calls(self, manager, user_list):
        """User list is fetched only once for multiple get_or_create_user calls."""
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.json.return_value = user_list

        with patch(
            "nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp
        ) as mock_req:
            manager.get_or_create_user("alice", None, None, None)
            manager.get_or_create_user("bob", None, None, None)

        # GET rest/user/ called once; alice and bob found without creating
        assert mock_req.call_count == 1

    def test_assign_record_owner_success(self, manager):
        """Returns True when PATCH change-owner returns 200."""
        mock_resp = Mock()
        mock_resp.status_code = HTTPStatus.OK

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.assign_record_owner(42, 7)

        assert result is True

    def test_assign_record_owner_failure(self, manager):
        """Returns False when PATCH change-owner returns an error status."""
        mock_resp = Mock()
        mock_resp.status_code = HTTPStatus.FORBIDDEN
        mock_resp.text = "Not allowed"

        with patch("nexusLIMS.utils.cdcs.nexus_req", return_value=mock_resp):
            result = manager.assign_record_owner(42, 7)

        assert result is False
