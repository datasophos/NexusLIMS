"""Unit tests for the LabArchives export destination plugin."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.destinations.labarchives import (
    LabArchivesDestination,
    _build_entry_url,
    _find_node_by_text,
)
from nexusLIMS.utils.labarchives import LabArchivesError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_enabled():
    """Mock settings with LabArchives fully enabled."""
    with patch(
        "nexusLIMS.exporters.destinations.labarchives.settings"
    ) as mock_settings:
        mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = "test_akid"
        mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = "test_password"
        mock_settings.NX_LABARCHIVES_USER_ID = "test_uid"
        mock_settings.NX_LABARCHIVES_URL = "http://localhost:9000"
        mock_settings.NX_LABARCHIVES_NOTEBOOK_ID = None
        yield mock_settings


@pytest.fixture
def mock_config_with_notebook(mock_config_enabled):
    """Extend mock_config_enabled with a notebook ID."""
    mock_config_enabled.NX_LABARCHIVES_NOTEBOOK_ID = "nb_42"
    return mock_config_enabled


@pytest.fixture
def mock_config_disabled():
    """Mock settings with LabArchives disabled."""
    with patch(
        "nexusLIMS.exporters.destinations.labarchives.settings"
    ) as mock_settings:
        mock_settings.NX_LABARCHIVES_ACCESS_KEY_ID = None
        mock_settings.NX_LABARCHIVES_ACCESS_PASSWORD = None
        mock_settings.NX_LABARCHIVES_USER_ID = None
        mock_settings.NX_LABARCHIVES_URL = None
        mock_settings.NX_LABARCHIVES_NOTEBOOK_ID = None
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


def _make_mock_client(
    *,
    get_tree_level_returns=None,
    insert_node_side_effect=None,
    add_entry_returns="eid_001",
    add_attachment_returns="eid_002",
) -> MagicMock:
    """Build a mock LabArchivesClient."""
    client = MagicMock()
    if get_tree_level_returns is not None:
        client.get_tree_level.side_effect = get_tree_level_returns
    client.insert_node.side_effect = insert_node_side_effect or (
        lambda _nbid, _parent, text, **_kw: f"tree_{text[:10]}"
    )
    client.add_entry.return_value = add_entry_returns
    client.add_attachment.return_value = add_attachment_returns
    return client


# ---------------------------------------------------------------------------
# TestLabArchivesDestinationConfiguration
# ---------------------------------------------------------------------------


class TestLabArchivesDestinationConfiguration:
    """Test configuration checks."""

    def test_name_and_priority(self):
        dest = LabArchivesDestination()
        assert dest.name == "labarchives"
        assert dest.priority == 90

    def test_enabled_when_fully_configured(self, mock_config_enabled):
        dest = LabArchivesDestination()
        assert dest.enabled is True

    def test_disabled_without_akid(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = None
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            cfg.NX_LABARCHIVES_USER_ID = "uid"
            cfg.NX_LABARCHIVES_URL = "http://localhost:9000"
            assert LabArchivesDestination().enabled is False

    def test_disabled_without_password(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = None
            cfg.NX_LABARCHIVES_USER_ID = "uid"
            cfg.NX_LABARCHIVES_URL = "http://localhost:9000"
            assert LabArchivesDestination().enabled is False

    def test_disabled_without_uid(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            cfg.NX_LABARCHIVES_USER_ID = None
            cfg.NX_LABARCHIVES_URL = "http://localhost:9000"
            assert LabArchivesDestination().enabled is False

    def test_disabled_without_url(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            cfg.NX_LABARCHIVES_USER_ID = "uid"
            cfg.NX_LABARCHIVES_URL = None
            assert LabArchivesDestination().enabled is False

    def test_disabled_when_all_none(self, mock_config_disabled):
        assert LabArchivesDestination().enabled is False

    def test_validate_config_missing_akid(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = None
            is_valid, msg = LabArchivesDestination().validate_config()
        assert is_valid is False
        assert "ACCESS_KEY_ID" in msg

    def test_validate_config_missing_password(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = None
            is_valid, msg = LabArchivesDestination().validate_config()
        assert is_valid is False
        assert "ACCESS_PASSWORD" in msg

    def test_validate_config_missing_uid(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            cfg.NX_LABARCHIVES_USER_ID = None
            is_valid, msg = LabArchivesDestination().validate_config()
        assert is_valid is False
        assert "USER_ID" in msg

    def test_validate_config_missing_url(self):
        with patch("nexusLIMS.exporters.destinations.labarchives.settings") as cfg:
            cfg.NX_LABARCHIVES_ACCESS_KEY_ID = "akid"
            cfg.NX_LABARCHIVES_ACCESS_PASSWORD = "pw"
            cfg.NX_LABARCHIVES_USER_ID = "uid"
            cfg.NX_LABARCHIVES_URL = None
            is_valid, msg = LabArchivesDestination().validate_config()
        assert is_valid is False
        assert "URL" in msg


# ---------------------------------------------------------------------------
# TestLabArchivesDestinationExport
# ---------------------------------------------------------------------------


class TestLabArchivesDestinationExport:
    """Test export functionality."""

    def test_export_success_inbox(self, mock_config_enabled, export_context):
        """Export without notebook ID goes to Inbox (nbid='0', page_tree_id='0')."""
        mock_client = _make_mock_client()
        dest = LabArchivesDestination()

        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is True
        assert result.destination_name == "labarchives"
        assert result.record_id == "eid_001"
        mock_client.add_entry.assert_called_once()
        mock_client.add_attachment.assert_called_once()

    def test_export_success_with_notebook(
        self, mock_config_with_notebook, export_context
    ):
        """Export with notebook ID creates folder hierarchy and page."""
        nexuslims_nodes: list[dict] = []  # "NexusLIMS Records" not yet created
        instrument_nodes: list[dict] = []  # instrument folder not yet created

        call_count = [0]

        def tree_level_side_effect(nbid, parent_tree_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return nexuslims_nodes  # root — no NexusLIMS Records folder yet
            if call_count[0] == 2:
                return instrument_nodes  # NexusLIMS Records — no instrument folder yet
            return []

        mock_client = _make_mock_client(
            get_tree_level_returns=tree_level_side_effect,
        )
        dest = LabArchivesDestination()

        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is True
        # insert_node called 3x: NexusLIMS Records folder, instrument folder, page
        assert mock_client.insert_node.call_count == 3

    def test_export_reuses_existing_folders(
        self, mock_config_with_notebook, export_context
    ):
        """When folders already exist, no new ones are created."""
        existing_nodes_root = [
            {"tree_id": "100", "display_text": "NexusLIMS Records", "is_page": False}
        ]
        existing_nodes_instrument = [
            {"tree_id": "200", "display_text": "test-instrument", "is_page": False}
        ]

        call_count = [0]

        def tree_level_side_effect(nbid, parent_tree_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return existing_nodes_root
            if call_count[0] == 2:
                return existing_nodes_instrument
            return []

        mock_client = _make_mock_client(
            get_tree_level_returns=tree_level_side_effect,
        )
        dest = LabArchivesDestination()

        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is True
        # Only the page should be created — not the existing folders
        assert mock_client.insert_node.call_count == 1

    def test_export_propagates_cdcs_url(self, mock_config_enabled, export_context):
        """HTML body should include CDCS link when CDCS export succeeded."""
        cdcs_result = ExportResult(
            success=True,
            destination_name="cdcs",
            record_id="123",
            record_url="http://cdcs.example.com/data?id=123",
        )
        export_context.previous_results["cdcs"] = cdcs_result

        captured_html: list[str] = []

        mock_client = _make_mock_client()
        mock_client.add_entry.side_effect = lambda _n, _p, html, **_kw: (
            captured_html.append(html) or "eid_xyz"
        )

        dest = LabArchivesDestination()
        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is True
        assert captured_html
        assert "http://cdcs.example.com/data?id=123" in captured_html[0]

    def test_export_handles_client_error(self, mock_config_enabled, export_context):
        """A LabArchivesError in the client should produce success=False."""
        mock_client = MagicMock()
        mock_client.add_entry.side_effect = LabArchivesError("API unreachable")

        dest = LabArchivesDestination()
        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is False
        assert result.destination_name == "labarchives"
        assert result.error_message is not None

    def test_export_never_raises(self, mock_config_enabled, export_context):
        """export() must never raise exceptions."""
        mock_client = MagicMock()
        mock_client.add_entry.side_effect = RuntimeError("unexpected boom")

        dest = LabArchivesDestination()
        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is False

    def test_export_file_read_error(self, mock_config_enabled, tmp_path):
        """Missing XML file produces success=False."""
        context = ExportContext(
            xml_file_path=tmp_path / "nonexistent.xml",
            session_identifier="sess",
            instrument_pid="inst",
            dt_from=datetime.now(),
            dt_to=datetime.now(),
        )
        dest = LabArchivesDestination()
        mock_client = MagicMock()
        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(context)

        assert result.success is False

    def test_export_url_with_notebook(self, mock_config_with_notebook, export_context):
        """record_url should include notebook and page tree IDs when notebook is set."""
        mock_client = _make_mock_client(
            get_tree_level_returns=lambda _nbid, _pid: [],
        )
        dest = LabArchivesDestination()
        with patch(
            "nexusLIMS.exporters.destinations.labarchives.get_labarchives_client",
            return_value=mock_client,
        ):
            result = dest.export(export_context)

        assert result.success is True
        assert result.record_url is not None
        assert "nb_42" in result.record_url


# ---------------------------------------------------------------------------
# TestLabArchivesHelpers
# ---------------------------------------------------------------------------


class TestLabArchivesHelpers:
    """Test module-level helper functions."""

    def test_find_node_by_text_found(self):
        nodes = [
            {"tree_id": "1", "display_text": "Alpha", "is_page": False},
            {"tree_id": "2", "display_text": "Beta", "is_page": False},
        ]
        assert _find_node_by_text(nodes, "Beta") == "2"

    def test_find_node_by_text_not_found(self):
        nodes = [{"tree_id": "1", "display_text": "Alpha", "is_page": False}]
        assert _find_node_by_text(nodes, "Gamma") is None

    def test_find_node_by_text_empty(self):
        assert _find_node_by_text([], "anything") is None

    def test_build_entry_url_with_notebook(self):
        url = _build_entry_url("https://la.example.com", "nb123", "page456")
        assert "nb123" in url
        assert "page456" in url

    def test_build_entry_url_inbox(self):
        url = _build_entry_url("https://la.example.com", "0", "0")
        assert url == "https://la.example.com"

    def test_build_entry_url_strips_trailing_slash(self):
        url = _build_entry_url("https://la.example.com/", "nb1", "p1")
        assert not url.startswith("https://la.example.com//")

    def test_build_entry_url_cloud_uses_web_host(self):
        url = _build_entry_url("https://api.labarchives.com/api", "nb123", "page456")
        assert url == "https://mynotebook.labarchives.com/#/nb123/page456"

    def test_build_entry_url_cloud_with_trailing_slash(self):
        url = _build_entry_url("https://api.labarchives.com/api/", "nb123", "page456")
        assert url == "https://mynotebook.labarchives.com/#/nb123/page456"
