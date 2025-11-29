"""Tests functionality related to the interacting with the CDCS frontend."""

# pylint: disable=missing-function-docstring
# ruff: noqa: D102, ARG001, ARG002, ARG005

import os
from pathlib import Path
from typing import NamedTuple

import pytest

from nexusLIMS import cdcs
from nexusLIMS.utils import AuthenticationError


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
    """Test the CDCS module using mocked server."""

    @pytest.fixture(autouse=True)
    def _setup_cdcs_env(self, monkeypatch, mock_cdcs_server):
        """Set up CDCS environment variables and mock server."""
        monkeypatch.setenv("NX_CDCS_URL", "http://test-cdcs.example.com")
        monkeypatch.setenv("NX_CDCS_USER", "testuser")
        monkeypatch.setenv("NX_CDCS_PASS", "testpass")

    def test_upload_and_delete_record(self, test_xml_record_file):
        _files_uploaded, record_ids = cdcs.upload_record_files(
            [test_xml_record_file[0]],
        )
        cdcs.delete_record(record_ids[0])

    def test_upload_and_delete_record_glob(self, test_xml_record_file):
        prev_dir = Path.cwd()
        os.chdir(test_xml_record_file[0].parent)
        _files_uploaded, record_ids = cdcs.upload_record_files(None)
        for id_ in record_ids:
            cdcs.delete_record(id_)
        os.chdir(prev_dir)

    def test_upload_no_files_glob(self, test_xml_record_file):
        prev_dir = Path.cwd()
        os.chdir(test_xml_record_file[0].parent / "figs")
        with pytest.raises(ValueError, match=r"No \.xml files were found"):
            _files_uploaded, _record_ids = cdcs.upload_record_files(None)
        os.chdir(prev_dir)

    def test_upload_file_bad_response(
        self,
        monkeypatch,
        test_xml_record_file,
        caplog,
    ):
        def mock_upload(_xml_content, _title):
            return (
                MockResponse(status_code=404, text="This is a fake request error!"),
                "dummy_id",
            )

        monkeypatch.setattr(cdcs, "upload_record_content", mock_upload)

        files_uploaded, record_ids = cdcs.upload_record_files(
            [test_xml_record_file[0]],
        )
        assert len(files_uploaded) == 0
        assert len(record_ids) == 0
        assert f"Could not upload {test_xml_record_file[0].name}" in caplog.text

    def test_bad_auth(self, monkeypatch):
        """Test that bad authentication credentials raise AuthenticationError."""
        from http import HTTPStatus

        # Override the mock_cdcs_server to return 401 for bad auth
        def mock_nexus_req_bad_auth(_url, _method, **_kwargs):
            return MockResponse(
                status_code=HTTPStatus.UNAUTHORIZED,
                text="Unauthorized",
            )

        monkeypatch.setattr(cdcs, "nexus_req", mock_nexus_req_bad_auth)

        with pytest.raises(AuthenticationError):
            cdcs.get_workspace_id()
        with pytest.raises(AuthenticationError):
            cdcs.get_template_id()

    def test_delete_record_bad_response(self, monkeypatch, caplog):
        monkeypatch.setattr(
            cdcs,
            "nexus_req",
            lambda _x, _y, basic_auth: MockResponse(
                status_code=404,
                text="This is a fake request error!",
            ),
        )
        cdcs.delete_record("dummy")
        assert "Received error while deleting dummy:" in caplog.text
        assert "This is a fake request error!" in caplog.text

    def test_upload_content_bad_response(self, monkeypatch, caplog):
        """Test upload_record_content with bad server response."""

        # pylint: disable=unused-argument
        def mock_req(_a, _b, json=None, *, basic_auth=False):
            return MockResponseWithJson(
                status_code=404,
                text="This is a fake request error!",
                json=lambda: [{"id": "dummy", "current": "dummy"}],
            )

        monkeypatch.setattr(cdcs, "nexus_req", mock_req)

        resp = cdcs.upload_record_content("<xml>content</xml>", "title")
        # When upload fails, only the response is returned (not a tuple)
        assert isinstance(resp, (MockResponse, MockResponseWithJson))
        assert "Got error while uploading title:" in caplog.text
        assert "This is a fake request error!" in caplog.text

    # Note: test_no_env_variable removed - pydantic Settings now validates
    # NX_CDCS_URL at module import time, not at function call time
