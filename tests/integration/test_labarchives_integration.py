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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values

from nexusLIMS.config import read_labarchives_env, refresh_settings
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.destinations.labarchives import LabArchivesDestination
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


# ---------------------------------------------------------------------------
# TestLabArchivesFullRecordExport
# ---------------------------------------------------------------------------


@pytest.mark.labarchives_live
class TestLabArchivesFullRecordExport:
    """End-to-end test: build an ExportContext and export via LabArchivesDestination.

    This test exercises the full production export path — ``_find_or_create_page()``,
    ``add_entry()``, and ``add_attachment()`` — against a live LabArchives server,
    then verifies the result by querying the server directly with ``la_client``.

    **Cleanup**: LabArchives provides no delete API. After running these tests,
    manually delete the ``NexusLIMS Records`` folder in the LabArchives UI to
    clean up the created pages. Re-running creates a new page per session
    (the destination always creates new pages).
    """

    _INSTRUMENT_PID = "FEI-Titan-TEM"

    def test_export_record_to_labarchives(  # noqa: PLR0915
        self,
        la_client: LabArchivesClient,
        nbid: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Export a NexusLIMS XML record to LabArchives and verify on the server.

        Steps
        -----
        1. Patch settings with live LA credentials and refresh.
        2. Write a valid NexusLIMS XML record to a temp file.
        3. Build an ExportContext with an activity that has a preview image.
           Simulate a prior CDCS export by injecting a fake ``ExportResult``
           into ``previous_results`` so the HTML summary includes a CDCS link.
        4. Call ``LabArchivesDestination().export(context)``.
        5. Assert the returned ``ExportResult`` indicates success.
        6. Navigate the live notebook tree to find the created page.
        7. Verify the HTML summary contains the instrument PID, a base64 preview
           gallery, and a link to the simulated CDCS record; and that the XML
           attachment round-trips byte-for-byte.
        """
        import base64
        from dataclasses import dataclass
        from dataclasses import field as dc_field

        # 1. Patch settings so LabArchivesDestination.enabled is True
        monkeypatch.setenv("NX_LABARCHIVES_URL", _LA["NX_LABARCHIVES_URL"])  # type: ignore[arg-type]
        monkeypatch.setenv(
            "NX_LABARCHIVES_ACCESS_KEY_ID",
            _LA["NX_LABARCHIVES_ACCESS_KEY_ID"],  # type: ignore[arg-type]
        )
        monkeypatch.setenv(
            "NX_LABARCHIVES_ACCESS_PASSWORD",
            _LA["NX_LABARCHIVES_ACCESS_PASSWORD"],  # type: ignore[arg-type]
        )
        monkeypatch.setenv("NX_LABARCHIVES_USER_ID", _LA["NX_LABARCHIVES_USER_ID"])  # type: ignore[arg-type]
        monkeypatch.setenv("NX_LABARCHIVES_NOTEBOOK_ID", nbid)
        refresh_settings()

        # 2. Write valid NexusLIMS XML record
        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<nx:Experiment
    xmlns:nx="https://data.nist.gov/od/dm/nexus/experiment/v1.0"
    pid="labarchives-e2e-test-001">
    <nx:title>LabArchives E2E Export Test</nx:title>
    <nx:summary>
        <nx:experimenter>test_user</nx:experimenter>
        <nx:instrument pid="FEI-Titan-TEM">FEI Titan TEM</nx:instrument>
        <nx:reservationStart>2025-02-01T09:00:00+00:00</nx:reservationStart>
        <nx:reservationEnd>2025-02-01T12:00:00+00:00</nx:reservationEnd>
        <nx:motivation>
            End-to-end integration test of LabArchives export functionality.
        </nx:motivation>
    </nx:summary>
    <nx:acquisitionActivity seqno="1">
        <nx:startTime>2025-02-01T09:15:00+00:00</nx:startTime>
        <nx:dataset type="Image">
            <nx:name>test_image.dm3</nx:name>
            <nx:location>researcher/project/test_image.dm3</nx:location>
        </nx:dataset>
    </nx:acquisitionActivity>
</nx:Experiment>"""
        xml_file = tmp_path / "test_nexuslims_record.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        # 3. Set up stub activities with 24 preview images across 3 activities,
        #    mirroring a realistic session: 3 activities x ~8 files each.
        #    All previews re-use the same test PNG (content doesn't matter for layout).
        preview_src = _DATA_DIR / "test_attachment.png"
        preview_bytes = preview_src.read_bytes()

        @dataclass
        class _StubActivity:
            files: list = dc_field(default_factory=list)
            previews: list = dc_field(default_factory=list)

        def _make_activity(names: list[str]) -> _StubActivity:
            previews = []
            for name in names:
                p = tmp_path / f"preview_{name}"
                p.write_bytes(preview_bytes)
                previews.append(str(p))
            return _StubActivity(files=names, previews=previews)

        activities = [
            _make_activity(
                [
                    "image_001.dm3",
                    "image_002.dm3",
                    "image_003.dm3",
                    "image_004.dm3",
                    "image_005.dm3",
                    "image_006.dm3",
                    "image_007.dm3",
                    "image_008.dm3",
                ]
            ),
            _make_activity(
                [
                    "spectrum_001.dm3",
                    "spectrum_002.dm3",
                    "spectrum_003.dm3",
                    "spectrum_004.dm3",
                    "spectrum_005.dm3",
                    "spectrum_006.dm3",
                    "spectrum_007.dm3",
                    "spectrum_008.dm3",
                ]
            ),
            _make_activity(
                [
                    "diffraction_001.dm3",
                    "diffraction_002.dm3",
                    "diffraction_003.dm3",
                    "diffraction_004.dm3",
                    "diffraction_005.dm3",
                    "diffraction_006.dm3",
                    "diffraction_007.dm3",
                    "diffraction_008.dm3",
                ]
            ),
        ]

        # Use a unique session ID so re-runs create distinct pages
        session_id = f"labarchives-live-e2e-{uuid.uuid4().hex[:8]}"
        dt_from = datetime(2025, 2, 1, 9, 0, 0, tzinfo=UTC)
        dt_to = datetime(2025, 2, 1, 12, 0, 0, tzinfo=UTC)

        # Simulate a prior CDCS export result so the HTML summary includes a
        # "View in CDCS" link — exercises the inter-destination dependency path
        # without requiring a live CDCS instance.
        fake_cdcs_url = "https://cdcs.example.com/record/labarchives-e2e-test-001"
        fake_cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="labarchives-e2e-test-001",
            record_url=fake_cdcs_url,
        )

        # 4. Build ExportContext and run export
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier=session_id,
            instrument_pid=self._INSTRUMENT_PID,
            dt_from=dt_from,
            dt_to=dt_to,
            user="test_user",
            activities=activities,
            previous_results={"cdcs": fake_cdcs_result},
        )
        result = LabArchivesDestination().export(context)

        # 5. Assert ExportResult indicates success
        assert result.success is True, (
            f"Export failed with error: {result.error_message}"
        )
        assert result.record_id, "ExportResult.record_id should be a non-empty string"
        assert result.record_url, "ExportResult.record_url should be a non-empty string"
        assert nbid in result.record_url, (
            f"Expected nbid {nbid!r} in record_url {result.record_url!r}"
        )

        # Extract page_tree_id from the URL (format: {base}/#/{nbid}/{page_tree_id})
        page_tree_id = result.record_url.rstrip("/").rsplit("/", 1)[-1]
        assert page_tree_id and page_tree_id != nbid, (  # noqa: PT018
            f"Could not parse page_tree_id from record_url {result.record_url!r}"
        )

        # 6. Verify page exists in the notebook tree
        #    Navigate: root -> "NexusLIMS Records" -> instrument folder -> page
        root_nodes = la_client.get_tree_level(nbid, "0")
        nexuslims_folder = next(
            (n for n in root_nodes if n["display_text"] == "NexusLIMS Records"), None
        )
        assert nexuslims_folder is not None, (
            "'NexusLIMS Records' folder not found at notebook root"
        )

        instrument_nodes = la_client.get_tree_level(nbid, nexuslims_folder["tree_id"])
        instrument_folder = next(
            (n for n in instrument_nodes if n["display_text"] == self._INSTRUMENT_PID),
            None,
        )
        assert instrument_folder is not None, (
            f"Instrument folder {self._INSTRUMENT_PID!r} not found under "
            f"'NexusLIMS Records'"
        )

        page_nodes = la_client.get_tree_level(nbid, instrument_folder["tree_id"])
        expected_page_name = f"{dt_from:%Y-%m-%d} \u2014 {session_id}"
        matching_pages = [
            n for n in page_nodes if n["display_text"] == expected_page_name
        ]
        assert matching_pages, (
            f"Page {expected_page_name!r} not found under instrument folder. "
            f"Pages found: {[n['display_text'] for n in page_nodes]}"
        )

        # 7. Verify entries on the page
        entries = la_client.get_page_entries(nbid, page_tree_id, include_content=True)
        assert len(entries) >= 2, (
            f"Expected at least 2 entries (HTML summary + XML attachment), "
            f"got {len(entries)}: {entries}"
        )

        # HTML text entry — should contain the instrument PID and a preview gallery
        text_entries = [e for e in entries if "text" in e.get("part_type", "").lower()]
        assert text_entries, (
            f"No text entry found among entries: {[e['part_type'] for e in entries]}"
        )
        html_content = text_entries[0]["entry_data"]
        assert "NexusLIMS" in html_content, (
            f"Expected 'NexusLIMS' in HTML entry content: {html_content!r}"
        )
        assert self._INSTRUMENT_PID in html_content, (
            f"Expected {self._INSTRUMENT_PID!r} in HTML entry content: {html_content!r}"
        )
        assert fake_cdcs_url in html_content, (
            f"Expected simulated CDCS link {fake_cdcs_url!r} in HTML entry content. "
            f"HTML content (first 500 chars): {html_content[:500]!r}"
        )
        expected_b64 = base64.b64encode(preview_bytes).decode()
        gallery_count = html_content.count("data:image/png;base64,")
        assert gallery_count == 24, (
            f"Expected 24 base64 preview images in HTML entry, got {gallery_count}. "
            f"HTML content (first 500 chars): {html_content[:500]!r}"
        )
        assert expected_b64 in html_content, (
            "Base64-encoded preview bytes not found in HTML entry"
        )

        # XML attachment — verify byte-for-byte round-trip
        file_entries = [
            e for e in entries if "attachment" in e.get("part_type", "").lower()
        ]
        assert file_entries, (
            f"No file attachment found among entries: "
            f"{[e['part_type'] for e in entries]}"
        )
        downloaded = la_client.get_attachment_content(file_entries[0]["eid"])
        assert downloaded == xml_file.read_bytes(), (
            "Downloaded attachment content does not match original XML file bytes"
        )

    def test_export_real_record_to_labarchives(  # noqa: PLR0915
        self,
        la_client: LabArchivesClient,
        nbid: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Export a record built from real DM3 files to LabArchives.

        Steps
        -----
        1. Extract the TEST_RECORD_FILES archive to a temp directory.
        2. Point NX_INSTRUMENT_DATA_PATH / NX_DATA_PATH at that directory and refresh.
        3. Mock ``res_event_from_session`` and ``get_instr_from_filepath``.
        4. Call ``build_record()`` with a real ``Session`` and
           ``generate_previews=True``.
        5. Export the resulting ``RecordBuildResult`` via ``LabArchivesDestination``.
        6. Assert success and verify the live HTML entry contains real preview images.
        """
        import tarfile

        import nexusLIMS.extractors
        import nexusLIMS.extractors.plugins.digital_micrograph
        import nexusLIMS.extractors.plugins.fei_emi
        import nexusLIMS.extractors.utils
        from nexusLIMS.builder.record_builder import RecordBuildResult, build_record
        from nexusLIMS.db.session_handler import Session
        from nexusLIMS.harvesters.reservation_event import ReservationEvent
        from tests.unit.test_instrument_factory import make_test_tool
        from tests.unit.utils import tars

        instrument_pid = "TEST-TOOL"

        # 1. Patch settings with live LA credentials
        monkeypatch.setenv("NX_LABARCHIVES_URL", _LA["NX_LABARCHIVES_URL"])  # type: ignore[arg-type]
        monkeypatch.setenv(
            "NX_LABARCHIVES_ACCESS_KEY_ID",
            _LA["NX_LABARCHIVES_ACCESS_KEY_ID"],  # type: ignore[arg-type]
        )
        monkeypatch.setenv(
            "NX_LABARCHIVES_ACCESS_PASSWORD",
            _LA["NX_LABARCHIVES_ACCESS_PASSWORD"],  # type: ignore[arg-type]
        )
        monkeypatch.setenv("NX_LABARCHIVES_USER_ID", _LA["NX_LABARCHIVES_USER_ID"])  # type: ignore[arg-type]
        monkeypatch.setenv("NX_LABARCHIVES_NOTEBOOK_ID", nbid)

        # 2. Set up NexusLIMS data paths pointing at tmp_path
        instr_data_path = tmp_path / "InstrumentData"
        nexuslims_data_path = tmp_path / "NexusLIMS"
        instr_data_path.mkdir()
        nexuslims_data_path.mkdir()
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(instr_data_path))
        monkeypatch.setenv("NX_DATA_PATH", str(nexuslims_data_path))
        monkeypatch.setenv("NX_FILE_STRATEGY", "exclusive")
        monkeypatch.setenv("NX_IGNORE_PATTERNS", '["*.mib", "*.db", "*.emi"]')
        refresh_settings()

        # 3. Extract the TEST_RECORD_FILES archive
        #    (Produces Nexus_Test_Instrument/test_files/sample_00[1-4].dm3)
        with tarfile.open(tars["TEST_RECORD_FILES"], "r:gz") as tar:
            tar.extractall(path=instr_data_path)

        # 4. Build the instrument and session objects
        instrument = make_test_tool()
        dt_from = datetime.fromisoformat("2021-08-02T09:00:00-07:00")
        dt_to = datetime.fromisoformat("2021-08-02T11:00:00-07:00")

        # 5. Mock res_event_from_session (avoids live NEMO dependency)
        def _mock_res_event(session):
            return ReservationEvent(
                experiment_title="EDX spectroscopy of platinum-nickel alloys",
                instrument=session.instrument,
                username=session.user,
                user_full_name="Test User",
                start_time=session.dt_from,
                end_time=session.dt_to,
                experiment_purpose="Determine composition of Pt-Ni alloy samples",
                reservation_type="User session",
                sample_details=["Platinum-nickel alloy nanoparticles"],
                sample_pid=["sample-ptni-042"],
                sample_name=["Pt-Ni"],
                project_name=["Catalyst Development"],
                project_id=["project-042"],
            )

        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.res_event_from_session",
            _mock_res_event,
        )

        # 6. Mock get_instr_from_filepath in all extractor modules (avoids DB lookup)
        monkeypatch.setattr(
            nexusLIMS.extractors.plugins.digital_micrograph,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors.plugins.fei_emi,
            "get_instr_from_filepath",
            lambda _: instrument,
        )
        monkeypatch.setattr(
            nexusLIMS.extractors,
            "get_instr_from_filepath",
            lambda _: instrument,
        )

        # 7. Build a real NexusLIMS record from the extracted DM3 files
        session_id = f"real-record-e2e-{uuid.uuid4().hex[:8]}"
        session = Session(
            session_identifier=session_id,
            instrument=instrument,
            dt_range=(dt_from, dt_to),
            user="test_user",
        )
        result = build_record(session=session, generate_previews=True)

        assert isinstance(result, RecordBuildResult)
        assert result.xml_text, "build_record should return non-empty XML"
        assert result.activities, "build_record should return at least one activity"

        # Write the XML record to a temp file for attachment
        xml_file = tmp_path / f"{session_id}.xml"
        xml_file.write_text(result.xml_text, encoding="utf-8")

        # 8. Build ExportContext with the real activities and reservation event
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier=session_id,
            instrument_pid=instrument_pid,
            dt_from=dt_from,
            dt_to=dt_to,
            user="test_user",
            activities=result.activities,
            reservation_event=result.reservation_event,
        )

        # 9. Export to LabArchives via the production code path
        export_result = LabArchivesDestination().export(context)

        assert export_result.success is True, (
            f"Export failed with error: {export_result.error_message}"
        )
        assert export_result.record_url, (
            "ExportResult.record_url should be set after a successful export"
        )

        page_tree_id = export_result.record_url.rstrip("/").rsplit("/", 1)[-1]
        assert page_tree_id and page_tree_id != nbid, (  # noqa: PT018
            f"Could not parse page_tree_id from record_url {export_result.record_url!r}"
        )

        # 10. Verify the page and its entries on the live LabArchives server
        entries = la_client.get_page_entries(nbid, page_tree_id, include_content=True)
        assert len(entries) >= 2, (
            f"Expected at least 2 entries (HTML summary + XML attachment), "
            f"got {len(entries)}: {entries}"
        )

        text_entries = [e for e in entries if "text" in e.get("part_type", "").lower()]
        assert text_entries, (
            f"No text entry found among entries: {[e['part_type'] for e in entries]}"
        )
        html_content = text_entries[0]["entry_data"]

        assert "NexusLIMS" in html_content, "Expected 'NexusLIMS' in HTML entry"
        assert instrument_pid in html_content, (
            f"Expected {instrument_pid!r} in HTML entry"
        )

        # The real DM3 files should have produced at least one preview image
        gallery_count = html_content.count("data:image/png;base64,")
        assert gallery_count >= 1, (
            f"Expected at least one base64 preview in HTML entry, got 0. "
            f"HTML (first 500 chars): {html_content[:500]!r}"
        )

        # XML attachment — verify byte-for-byte round-trip
        file_entries = [
            e for e in entries if "attachment" in e.get("part_type", "").lower()
        ]
        assert file_entries, (
            f"No file attachment found among entries: "
            f"{[e['part_type'] for e in entries]}"
        )
        downloaded = la_client.get_attachment_content(file_entries[0]["eid"])
        assert downloaded == xml_file.read_bytes(), (
            "Downloaded attachment content does not match original XML file bytes"
        )
