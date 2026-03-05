r"""Live integration tests for the LabArchives API client.

These tests run against a real LabArchives server and are **skipped by default**.
They are meant to be run manually when you need to verify end-to-end connectivity
or diagnose API issues.

Required environment variables (or .env file entries)
------------------------------------------------------
NX_LABARCHIVES_URL
    API base URL including the /api path, e.g. ``https://api.labarchives.com/api``
NX_LABARCHIVES_ACCESS_KEY_ID
    HMAC Access Key ID assigned by LabArchives.
NX_LABARCHIVES_ACCESS_PASSWORD
    HMAC signing secret (NOT your account password).
NX_LABARCHIVES_USER_ID
    LabArchives user ID (uid) for the account under test.
NX_LABARCHIVES_NOTEBOOK_ID
    Notebook ID to use for tree / entry tests (defaults to the Inbox notebook
    when not set, but tests that create nodes will always clean up after themselves).

Optional (only needed for the ``get_user_info`` credential test)
----------------------------------------------------------------
NX_LABARCHIVES_TEST_EMAIL
    Email address for the LabArchives account.
NX_LABARCHIVES_TEST_LA_PASSWORD
    LabArchives external app password (from the user menu →
    *External App authentication* in the LabArchives web UI).

Running
-------
.. code-block:: bash

    # From the project root — must explicitly select the labarchives_live marker:
    uv run pytest tests/integration/test_labarchives_integration.py \\
        -m labarchives_live -v

    # Or run a single test:
    uv run pytest tests/integration/test_labarchives_integration.py \\
        -m labarchives_live -v -k test_get_user_info
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values

from nexusLIMS.config import read_labarchives_env
from nexusLIMS.utils.labarchives import (
    LabArchivesAuthenticationError,
    LabArchivesClient,
    LabArchivesError,
    LabArchivesNotFoundError,
)

# ---------------------------------------------------------------------------
# Credential loading
#
# Values are resolved in this priority order (highest first):
#   1. Real environment variables
#   2. tests/.env.test        (tests directory — gitignored, for local dev)
#   3. .env                   (standard NexusLIMS config file)
#
# Copy tests/.env.test.example to tests/.env.test and fill in
# your credentials.  The example file lists all supported keys.
# ---------------------------------------------------------------------------

_TEST_ENV_FILE = Path(__file__).parents[1] / ".env.test"
_DATA_DIR = Path(__file__).parent / "data"

# Start from standard NexusLIMS LA vars (env > .env)
_LA: dict[str, str | None] = read_labarchives_env()

# Overlay with tests/.env.test when present, then re-apply real env vars
# so they always win over the file.
if _TEST_ENV_FILE.exists():
    _file_vals = dotenv_values(_TEST_ENV_FILE)
    for _k, _v in _file_vals.items():
        if _v:  # file value fills in blanks
            _LA.setdefault(_k, None)
            if not _LA.get(_k):
                _LA[_k] = _v
    # Real env vars always take final precedence
    for _k in list(_LA):
        if env_val := os.environ.get(_k):
            _LA[_k] = env_val

_REQUIRED_VARS = (
    "NX_LABARCHIVES_URL",
    "NX_LABARCHIVES_ACCESS_KEY_ID",
    "NX_LABARCHIVES_ACCESS_PASSWORD",
    "NX_LABARCHIVES_USER_ID",
)
_missing = [k for k in _REQUIRED_VARS if not _LA.get(k)]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.labarchives_live,
    pytest.mark.network,
    pytest.mark.skipif(
        bool(_missing),
        reason=(
            "LabArchives live tests require the following env vars to be set: "
            + ", ".join(_missing or ["(all present)"])
        ),
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tag() -> str:
    """Return a short unique string suitable for test node names."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def la_client() -> LabArchivesClient:
    """Return a configured LabArchivesClient from env vars."""
    return LabArchivesClient(
        base_url=_LA["NX_LABARCHIVES_URL"],  # type: ignore[arg-type]
        akid=_LA["NX_LABARCHIVES_ACCESS_KEY_ID"],  # type: ignore[arg-type]
        password=_LA["NX_LABARCHIVES_ACCESS_PASSWORD"],  # type: ignore[arg-type]
        uid=_LA["NX_LABARCHIVES_USER_ID"],  # type: ignore[arg-type]
    )


@pytest.fixture(scope="module")
def nbid() -> str:
    """Return the notebook ID to use for tests.

    Skips all tests that use this fixture when ``NX_LABARCHIVES_NOTEBOOK_ID``
    is not set — the API rejects requests with an empty nbid.
    """
    value = _LA.get("NX_LABARCHIVES_NOTEBOOK_ID")
    if not value:
        pytest.skip(
            "NX_LABARCHIVES_NOTEBOOK_ID must be set to run notebook / tree tests"
        )
    return value


_SUITE_FOLDER_NAME = "NexusLIMS Integration Tests"


@pytest.fixture(scope="module")
def suite_folder(la_client: LabArchivesClient, nbid: str) -> dict[str, Any]:
    """Find or create the top-level ``NexusLIMS Integration Tests`` folder.

    All per-test folders are created inside this one so the entire test run
    can be cleaned up by deleting a single folder in the LabArchives UI.
    """
    root_nodes = la_client.get_tree_level(nbid)
    existing = next(
        (n for n in root_nodes if n["display_text"] == _SUITE_FOLDER_NAME), None
    )
    if existing:
        tree_id = existing["tree_id"]
    else:
        tree_id = la_client.insert_folder(nbid, "0", _SUITE_FOLDER_NAME)
    return {"tree_id": tree_id, "name": _SUITE_FOLDER_NAME, "nbid": nbid}


def _node_name(request: pytest.FixtureRequest, prefix: str) -> str:
    """Build a human-readable node name encoding the test and a uniqueness tag."""
    test_name = request.node.name.removeprefix("test_")
    return f"{prefix} [{test_name}] {_tag()}"


@pytest.fixture
def test_folder(
    la_client: LabArchivesClient,
    suite_folder: dict[str, Any],
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    """Create a named folder inside *suite_folder* encoding the calling test.

    LabArchives provides no delete-node API, so created folders persist.
    Delete the single ``NexusLIMS Integration Tests`` folder in the UI to
    clean up after a test run.
    """
    name = _node_name(request, "folder")
    tree_id = la_client.insert_folder(
        suite_folder["nbid"], suite_folder["tree_id"], name
    )
    return {"tree_id": tree_id, "name": name, "nbid": suite_folder["nbid"]}


@pytest.fixture
def test_page(
    la_client: LabArchivesClient,
    test_folder: dict[str, Any],
    request: pytest.FixtureRequest,
):
    """Create a named page inside *test_folder* encoding the calling test."""
    name = _node_name(request, "page")
    page_tree_id = la_client.insert_page(
        test_folder["nbid"], test_folder["tree_id"], name
    )
    return {
        "nbid": test_folder["nbid"],
        "folder_tree_id": test_folder["tree_id"],
        "page_tree_id": page_tree_id,
        "name": name,
    }


# ---------------------------------------------------------------------------
# TestLabArchivesUserInfo
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesUserInfo:
    """Tests for the users/user_access_info endpoint."""

    @pytest.mark.xfail(
        reason=(
            "LabArchives external app passwords expire; "
            "update NX_LABARCHIVES_TEST_LA_PASSWORD if this fails"
        ),
        strict=False,
    )
    def test_get_user_info_with_credentials(self, la_client: LabArchivesClient):
        """get_user_info returns uid, email, and at least one notebook.

        Requires NX_LABARCHIVES_TEST_EMAIL and NX_LABARCHIVES_TEST_LA_PASSWORD
        to be set in addition to the standard API credentials.
        """
        email = _LA.get("NX_LABARCHIVES_TEST_EMAIL")
        if not email:
            pytest.skip("NX_LABARCHIVES_TEST_EMAIL must be set to run this test")
        la_password = _LA.get("NX_LABARCHIVES_TEST_LA_PASSWORD")
        if not la_password:
            pytest.skip("NX_LABARCHIVES_TEST_LA_PASSWORD must be set to run this test")

        info = la_client.get_user_info(email, la_password)

        assert "uid" in info, "Response should contain 'uid'"
        assert info["uid"], "uid should be a non-empty string"
        print(f"uid: {info['uid']}")  # noqa: T201
        assert "email" in info
        assert "notebooks" in info
        assert isinstance(info["notebooks"], list)
        assert len(info["notebooks"]) >= 1, "Account should have at least one notebook"
        nb = info["notebooks"][0]
        assert "id" in nb
        assert "name" in nb

    def test_get_user_info_by_uid(self, la_client: LabArchivesClient):
        """get_user_info_by_uid returns user info using only the configured uid."""
        info = la_client.get_user_info_by_uid()

        assert "uid" in info, "Response should contain 'uid'"
        assert info["uid"], "uid should be a non-empty string"
        assert "notebooks" in info
        assert isinstance(info["notebooks"], list)
        assert len(info["notebooks"]) >= 1, "Account should have at least one notebook"
        nb = info["notebooks"][0]
        assert "id" in nb
        assert "name" in nb

    def test_bad_credentials_raise_auth_error(self, la_client: LabArchivesClient):
        """Invalid login credentials should raise LabArchivesAuthenticationError."""
        with pytest.raises(LabArchivesAuthenticationError):
            la_client.get_user_info(
                "nonexistent-user@invalid.example.com", "wrong-password"
            )


# ---------------------------------------------------------------------------
# TestLabArchivesTreeOperations
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesTreeOperations:
    """Tests for get_tree_level, insert_folder, and insert_page."""

    def test_get_tree_level_root_returns_list(
        self, la_client: LabArchivesClient, nbid: str
    ):
        """Fetching the root tree level returns a list (may be empty)."""
        nodes = la_client.get_tree_level(nbid)
        assert isinstance(nodes, list)
        for node in nodes:
            assert "tree_id" in node
            assert "display_text" in node
            assert "is_page" in node
            assert isinstance(node["is_page"], bool)

    def test_insert_folder_appears_in_tree(
        self,
        la_client: LabArchivesClient,
        suite_folder: dict[str, Any],
        test_folder: dict[str, Any],
    ):
        """A newly inserted folder should appear when listing its parent."""
        nodes = la_client.get_tree_level(suite_folder["nbid"], suite_folder["tree_id"])
        tree_ids = [n["tree_id"] for n in nodes]
        assert test_folder["tree_id"] in tree_ids, (
            f"Created folder {test_folder['name']!r} "
            f"(tree_id={test_folder['tree_id']}) "
            f"not found in suite_folder children. tree_ids={tree_ids}"
        )

    def test_insert_folder_is_not_page(
        self,
        la_client: LabArchivesClient,
        suite_folder: dict[str, Any],
        test_folder: dict[str, Any],
    ):
        """An inserted folder should have is_page=False."""
        nodes = la_client.get_tree_level(suite_folder["nbid"], suite_folder["tree_id"])
        folder_node = next(
            (n for n in nodes if n["tree_id"] == test_folder["tree_id"]), None
        )
        assert folder_node is not None
        assert folder_node["is_page"] is False

    def test_insert_page_appears_in_folder(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """A newly inserted page should appear inside its parent folder."""
        children = la_client.get_tree_level(
            test_page["nbid"], test_page["folder_tree_id"]
        )
        child_ids = [n["tree_id"] for n in children]
        assert test_page["page_tree_id"] in child_ids, (
            f"Page (tree_id={test_page['page_tree_id']}) not found in folder. "
            f"child_ids={child_ids}"
        )

    def test_insert_page_is_page(
        self,
        la_client: LabArchivesClient,
        nbid: str,
        test_folder: dict[str, Any],
        request: pytest.FixtureRequest,
    ):
        """An inserted page node should have is_page=True."""
        page_name = _node_name(request, "page")
        page_tree_id = la_client.insert_page(nbid, test_folder["tree_id"], page_name)
        nodes = la_client.get_tree_level(nbid, parent_tree_id=test_folder["tree_id"])
        page_node = next((n for n in nodes if n["tree_id"] == page_tree_id), None)
        assert page_node is not None, f"Page {page_name!r} not found under folder"
        assert page_node["is_page"] is True

    def test_insert_folder_returns_non_empty_tree_id(
        self,
        la_client: LabArchivesClient,
        suite_folder: dict[str, Any],
        request: pytest.FixtureRequest,
    ):
        """insert_folder should return a non-empty tree_id string."""
        name = _node_name(request, "folder")
        tree_id = la_client.insert_folder(
            suite_folder["nbid"], suite_folder["tree_id"], name
        )
        assert tree_id
        assert tree_id != "0"


# ---------------------------------------------------------------------------
# TestLabArchivesEntryOperations
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesEntryOperations:
    """Tests for entries/add_entry_to_page and entries/add_attachment_to_page."""

    def test_add_text_entry_returns_eid(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """Adding a text entry should return eid; content is readable back."""
        content = "<p>Integration test entry from NexusLIMS test suite.</p>"
        eid = la_client.add_entry(
            test_page["nbid"],
            test_page["page_tree_id"],
            content,
        )
        assert eid
        assert eid != "0"

        entries = la_client.get_page_entries(
            test_page["nbid"], test_page["page_tree_id"], include_content=True
        )
        entry = next((e for e in entries if e["eid"] == eid), None)
        assert entry is not None, f"Entry {eid} not found on page after insert"
        assert content in entry["entry_data"], (
            f"Expected content not found in entry_data: {entry['entry_data']!r}"
        )

    def test_add_html_entry_returns_eid(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """Adding HTML entry with formatting; content is readable back."""
        html = (
            "<h2>NexusLIMS Integration Test</h2>"
            "<p>Created by the NexusLIMS test suite — can be deleted.</p>"
            "<ul><li>Instrument: Test SEM</li><li>User: test_user</li></ul>"
        )
        eid = la_client.add_entry(test_page["nbid"], test_page["page_tree_id"], html)
        assert eid

        entries = la_client.get_page_entries(
            test_page["nbid"], test_page["page_tree_id"], include_content=True
        )
        entry = next((e for e in entries if e["eid"] == eid), None)
        assert entry is not None, f"Entry {eid} not found on page after insert"
        assert html in entry["entry_data"], (
            f"Expected content not found in entry_data: {entry['entry_data']!r}"
        )

    def test_add_xml_attachment(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """Uploading an XML attachment should round-trip byte-for-byte."""
        fixture = _DATA_DIR / "test_attachment.xml"
        eid = la_client.attach_file(
            test_page["nbid"],
            test_page["page_tree_id"],
            fixture,
            caption="NexusLIMS integration test XML attachment",
        )
        assert eid
        assert eid != "0"

        assert la_client.get_attachment_content(eid) == fixture.read_bytes()

    def test_add_image_attachment(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """Uploading a PNG attachment should round-trip byte-for-byte."""
        fixture = _DATA_DIR / "test_attachment.png"
        eid = la_client.attach_file(
            test_page["nbid"],
            test_page["page_tree_id"],
            fixture,
            caption="NexusLIMS integration test PNG attachment",
        )
        assert eid
        assert eid != "0"

        assert la_client.get_attachment_content(eid) == fixture.read_bytes()

    def test_add_pdf_attachment(
        self, la_client: LabArchivesClient, test_page: dict[str, Any]
    ):
        """Uploading a PDF attachment should round-trip byte-for-byte."""
        fixture = _DATA_DIR / "test_attachment.pdf"
        eid = la_client.attach_file(
            test_page["nbid"],
            test_page["page_tree_id"],
            fixture,
            caption="NexusLIMS integration test PDF attachment",
        )
        assert eid
        assert eid != "0"

        assert la_client.get_attachment_content(eid) == fixture.read_bytes()


# ---------------------------------------------------------------------------
# TestLabArchivesErrorHandling
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesErrorHandling:
    """Tests that verify error responses from the live API are handled correctly."""

    def test_bad_akid_raises_auth_error(self, nbid: str):
        """A client with an invalid AKID should raise LabArchivesAuthenticationError."""
        bad_client = LabArchivesClient(
            base_url=_LA["NX_LABARCHIVES_URL"],  # type: ignore[arg-type]
            akid="invalid-akid-xyz",
            password=_LA["NX_LABARCHIVES_ACCESS_PASSWORD"],  # type: ignore[arg-type]
            uid=_LA["NX_LABARCHIVES_USER_ID"],  # type: ignore[arg-type]
        )
        with pytest.raises((LabArchivesAuthenticationError, LabArchivesError)):
            bad_client.get_tree_level(nbid, "0")

    def test_bad_password_raises_auth_error(self, nbid: str):
        """A client with a bad password should raise LabArchivesAuthenticationError."""
        bad_client = LabArchivesClient(
            base_url=_LA["NX_LABARCHIVES_URL"],  # type: ignore[arg-type]
            akid=_LA["NX_LABARCHIVES_ACCESS_KEY_ID"],  # type: ignore[arg-type]
            password="this-is-not-the-real-password",
            uid=_LA["NX_LABARCHIVES_USER_ID"],  # type: ignore[arg-type]
        )
        with pytest.raises((LabArchivesAuthenticationError, LabArchivesError)):
            bad_client.get_tree_level(nbid, "0")

    def test_get_attachment_content_bad_eid_raises(self, la_client: LabArchivesClient):
        """get_attachment_content with a nonexistent eid should raise an error."""
        with pytest.raises((LabArchivesNotFoundError, LabArchivesError)):
            la_client.get_attachment_content("this-eid-does-not-exist")


# ---------------------------------------------------------------------------
# TestLabArchivesClientFactory
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesClientFactory:
    """Smoke test for the get_labarchives_client() factory function."""

    def test_get_labarchives_client_returns_working_client(self):
        """get_labarchives_client() builds a working client from settings."""
        from unittest.mock import MagicMock, patch

        from nexusLIMS.utils.labarchives import get_labarchives_client

        mock_settings = MagicMock()
        mock_settings.NX_LABARCHIVES_URL = _LA["NX_LABARCHIVES_URL"]
        mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = _LA["NX_LABARCHIVES_ACCESS_KEY_ID"]
        mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = _LA[
            "NX_LABARCHIVES_ACCESS_PASSWORD"
        ]
        mock_settings.NX_LABARCHIVES_USER_ID = _LA["NX_LABARCHIVES_USER_ID"]

        with patch("nexusLIMS.utils.labarchives.settings", mock_settings):
            client = get_labarchives_client()

        info = client.get_user_info_by_uid()
        assert info["uid"]
