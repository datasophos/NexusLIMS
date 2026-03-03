"""Unit tests for the LabArchives API client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest
import requests

from nexusLIMS.utils.labarchives import (
    LabArchivesAuthenticationError,
    LabArchivesClient,
    LabArchivesError,
    LabArchivesNotFoundError,
    LabArchivesPermissionError,
    LabArchivesRateLimitError,
    get_labarchives_client,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a LabArchivesClient with known test credentials."""
    return LabArchivesClient(
        base_url="https://mynotebook.labarchives.com",
        akid="test_akid",
        password="test_password",
        uid="test_uid",
    )


def _xml(content: str) -> str:
    return f'<?xml version="1.0"?><response>{content}</response>'


def _mock_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# TestLabArchivesClientAuth
# ---------------------------------------------------------------------------


class TestLabArchivesClientAuth:
    """Test HMAC-SHA-512 signature generation."""

    def test_sign_produces_correct_signature(self, client):
        """Verify _sign produces the expected HMAC-SHA-512 signature.

        The signing string is ``akid + method_name + expires`` where
        *method_name* is the bare method name only (e.g. ``"tree_level"``),
        not the full ``class/method`` path.  The returned signature is raw
        base64 — NOT pre-URL-encoded — so that ``requests`` can encode it
        exactly once when building the query string.
        """
        method = "tree_level"
        expires = "1700000000000"

        msg = "test_akid" + method + expires
        expected_raw = hmac.new(
            b"test_password",
            msg.encode("utf-8"),
            hashlib.sha512,
        ).digest()
        expected_b64 = base64.b64encode(expected_raw).decode("utf-8")

        with patch("nexusLIMS.utils.labarchives.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            mock_time.sleep = time.sleep
            returned_expires, returned_sig = client._sign(method)

        assert returned_expires == expires
        assert returned_sig == expected_b64

    def test_auth_params_includes_required_keys(self, client):
        """_auth_params should return akid, expires, and sig."""
        with patch("nexusLIMS.utils.labarchives.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            mock_time.sleep = time.sleep
            params = client._auth_params("tree_level")

        assert "akid" in params
        assert "expires" in params
        assert "sig" in params
        assert params["akid"] == "test_akid"

    def test_sign_different_methods_give_different_sigs(self, client):
        """Different methods produce different signatures."""
        with patch("nexusLIMS.utils.labarchives.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            mock_time.sleep = time.sleep
            _, sig1 = client._sign("tree_level")
            _, sig2 = client._sign("add_entry_to_page")

        assert sig1 != sig2


# ---------------------------------------------------------------------------
# TestLabArchivesClientErrors
# ---------------------------------------------------------------------------


class TestLabArchivesClientErrors:
    """Test _parse_response error mapping."""

    def test_404_raises_not_found(self, client):
        resp = _mock_response("Not Found", 404)
        with pytest.raises(LabArchivesNotFoundError):
            client._parse_response(resp, "some/method")

    def test_5xx_raises_rate_limit(self, client):
        resp = _mock_response("Server Error", 503)
        with pytest.raises(LabArchivesRateLimitError):
            client._parse_response(resp, "some/method")

    def test_auth_error_code_4504(self, client):
        xml = _xml("<error><code>4504</code><msg>Invalid signature</msg></error>")
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesAuthenticationError, match="4504"):
            client._parse_response(resp, "some/method")

    def test_auth_error_current_element_names(self, client):
        """Current LabArchives XML uses error-code / error-description elements."""
        xml = _xml(
            '<error><error-code type="integer">4520</error-code>'
            "<error-description>The supplied signature parameter was invalid"
            "</error-description></error>"
        )
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesAuthenticationError, match="4520"):
            client._parse_response(resp, "some/method")

    def test_auth_error_code_4506(self, client):
        xml = _xml("<error><code>4506</code><msg>Expired</msg></error>")
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesAuthenticationError):
            client._parse_response(resp, "some/method")

    def test_permission_error_code_4501(self, client):
        xml = _xml("<error><code>4501</code><msg>Access denied</msg></error>")
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesPermissionError):
            client._parse_response(resp, "some/method")

    def test_permission_error_code_4502(self, client):
        xml = _xml("<error><code>4502</code><msg>Permission denied</msg></error>")
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesPermissionError):
            client._parse_response(resp, "some/method")

    def test_generic_la_error(self, client):
        xml = _xml("<error><code>9999</code><msg>Unknown problem</msg></error>")
        resp = _mock_response(xml)
        with pytest.raises(LabArchivesError, match="9999"):
            client._parse_response(resp, "some/method")

    def test_invalid_xml_raises_error(self, client):
        resp = _mock_response("not valid xml at all!!!", 200)
        with pytest.raises(LabArchivesError, match="Failed to parse"):
            client._parse_response(resp, "some/method")

    def test_success_returns_element(self, client):
        xml = _xml("<tree_item><tree_id>42</tree_id></tree_item>")
        resp = _mock_response(xml)
        root = client._parse_response(resp, "some/method")
        assert isinstance(root, ET.Element)


# ---------------------------------------------------------------------------
# TestLabArchivesClientRequests
# ---------------------------------------------------------------------------


class TestLabArchivesClientRequests:
    """Test public API methods with mocked HTTP."""

    def _patch_get(self, client, xml_text: str):
        """Patch requests.get to return a mocked response."""
        return patch(
            "nexusLIMS.utils.labarchives.requests.get",
            return_value=_mock_response(xml_text),
        )

    def _patch_post(self, client, xml_text: str):
        return patch(
            "nexusLIMS.utils.labarchives.requests.post",
            return_value=_mock_response(xml_text),
        )

    def test_get_tree_level_returns_nodes(self, client):
        item_a = (
            "<tree_item>"
            "<tree_id>10</tree_id>"
            "<display_text>Folder A</display_text>"
            "<type>folder</type>"
            "</tree_item>"
        )
        item_b = (
            "<tree_item>"
            "<tree_id>20</tree_id>"
            "<display_text>Page B</display_text>"
            "<type>page</type>"
            "</tree_item>"
        )
        xml = _xml(f"<tree_items>{item_a}{item_b}</tree_items>")
        with self._patch_get(client, xml):
            nodes = client.get_tree_level("nbid123", "0")

        assert len(nodes) == 2
        assert nodes[0] == {
            "tree_id": "10",
            "display_text": "Folder A",
            "is_page": False,
        }
        assert nodes[1] == {"tree_id": "20", "display_text": "Page B", "is_page": True}

    def test_get_tree_level_empty(self, client):
        xml = _xml("<tree_items></tree_items>")
        with self._patch_get(client, xml):
            nodes = client.get_tree_level("nbid123", "0")
        assert nodes == []

    def test_insert_node_returns_tree_id(self, client):
        xml = _xml("<node><tree_id>99</tree_id></node>")
        with self._patch_post(client, xml):
            tree_id = client.insert_node("nbid123", "0", "New Folder", is_folder=True)
        assert tree_id == "99"

    def test_insert_node_missing_tree_id_raises(self, client):
        xml = _xml("<node><other>stuff</other></node>")
        with (
            self._patch_post(client, xml),
            pytest.raises(LabArchivesError, match="missing tree_id"),
        ):
            client.insert_node("nbid123", "0", "New Folder", is_folder=True)

    def test_add_entry_returns_eid(self, client):
        xml = _xml("<entry><eid>456</eid></entry>")
        with self._patch_post(client, xml):
            eid = client.add_entry("nbid123", "10", "<p>Hello</p>")
        assert eid == "456"

    def test_add_entry_missing_eid_raises(self, client):
        xml = _xml("<entry><other>x</other></entry>")
        with (
            self._patch_post(client, xml),
            pytest.raises(LabArchivesError, match="missing eid"),
        ):
            client.add_entry("nbid123", "10", "<p>Hello</p>")

    def test_add_attachment_returns_eid(self, client):
        xml = _xml("<entry><eid>789</eid></entry>")
        with self._patch_post(client, xml):
            eid = client.add_attachment("nbid123", "10", "record.xml", b"<xml/>")
        assert eid == "789"

    def test_get_user_info_parses_uid(self, client):
        xml = (
            "<?xml version='1.0'?>"
            "<users>"
            "<id>user_uid_42</id>"
            "<fullname>Test User</fullname>"
            "<first-name>Test</first-name>"
            "<last-name>User</last-name>"
            "<email>test@example.com</email>"
            "<notebooks type='array'>"
            "<notebook><id>nb_abc</id><name>My Notebook</name></notebook>"
            "</notebooks>"
            "</users>"
        )
        with self._patch_get(client, xml):
            info = client.get_user_info("test@example.com", "password")
        assert info["uid"] == "user_uid_42"
        assert info["email"] == "test@example.com"
        assert info["fullname"] == "Test User"
        assert info["notebooks"] == [{"id": "nb_abc", "name": "My Notebook"}]

    def test_get_retries_on_5xx(self, client):
        """GET should retry up to _MAX_RETRIES times on 5xx errors."""
        success_xml = _xml("<node><tree_id>1</tree_id></node>")
        responses_list = [
            _mock_response("Server Error", 503),
            _mock_response("Server Error", 503),
            _mock_response(success_xml, 200),
        ]
        with (
            patch(
                "nexusLIMS.utils.labarchives.requests.get",
                side_effect=responses_list,
            ),
            patch("nexusLIMS.utils.labarchives.time.sleep"),
            patch("nexusLIMS.utils.labarchives.time.time", return_value=9999999.0),
        ):
            root = client._get("notebooks", "tree_level", {})
        assert root is not None

    def test_get_raises_after_max_retries(self, client):
        """GET should raise LabArchivesRateLimitError after max retries."""
        error_resp = _mock_response("Server Error", 503)
        with (
            patch(
                "nexusLIMS.utils.labarchives.requests.get",
                return_value=error_resp,
            ),
            patch("nexusLIMS.utils.labarchives.time.sleep"),
            patch("nexusLIMS.utils.labarchives.time.time", return_value=9999999.0),
            pytest.raises(LabArchivesRateLimitError),
        ):
            client._get("notebooks", "tree_level", {})


# ---------------------------------------------------------------------------
# TestGetLabArchivesClient
# ---------------------------------------------------------------------------


class TestGetLabArchivesClient:
    """Test the factory function."""

    def test_returns_client_when_configured(self):
        with patch("nexusLIMS.utils.labarchives.settings") as mock_settings:
            mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            mock_settings.NX_LABARCHIVES_USER_ID = "uid"
            mock_settings.NX_LABARCHIVES_URL = "https://mynotebook.labarchives.com"

            client = get_labarchives_client()

        assert isinstance(client, LabArchivesClient)
        assert client.akid == "akid"
        assert client.password == "pw"
        assert client.uid == "uid"

    def test_raises_if_akid_missing(self):
        with patch("nexusLIMS.utils.labarchives.settings") as mock_settings:
            mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = None
            mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            mock_settings.NX_LABARCHIVES_USER_ID = "uid"
            mock_settings.NX_LABARCHIVES_URL = "https://mynotebook.labarchives.com"

            with pytest.raises(LabArchivesError, match="ACCESS_KEY_ID"):
                get_labarchives_client()

    def test_raises_if_password_missing(self):
        with patch("nexusLIMS.utils.labarchives.settings") as mock_settings:
            mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = None
            mock_settings.NX_LABARCHIVES_USER_ID = "uid"
            mock_settings.NX_LABARCHIVES_URL = "https://mynotebook.labarchives.com"

            with pytest.raises(LabArchivesError, match="ACCESS_PASSWORD"):
                get_labarchives_client()

    def test_raises_if_uid_missing(self):
        with patch("nexusLIMS.utils.labarchives.settings") as mock_settings:
            mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            mock_settings.NX_LABARCHIVES_USER_ID = None
            mock_settings.NX_LABARCHIVES_URL = "https://mynotebook.labarchives.com"

            with pytest.raises(LabArchivesError, match="USER_ID"):
                get_labarchives_client()

    def test_raises_if_url_missing(self):
        with patch("nexusLIMS.utils.labarchives.settings") as mock_settings:
            mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            mock_settings.NX_LABARCHIVES_USER_ID = "uid"
            mock_settings.NX_LABARCHIVES_URL = None

            with pytest.raises(LabArchivesError, match="URL"):
                get_labarchives_client()
