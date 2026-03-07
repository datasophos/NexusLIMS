"""Unit tests for the db view and create-demo CLI commands."""

from __future__ import annotations

import sqlite3
from argparse import Namespace
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from sqlmodel import Session, create_engine

from nexusLIMS.db.models import Instrument


@pytest.fixture
def demo_db(tmp_path) -> Path:
    """Create a demo database with sample instruments."""
    from nexusLIMS.tui.demo_helpers import create_demo_database

    db_path = tmp_path / "demo.db"
    create_demo_database(db_path)
    return db_path


@pytest.fixture
def small_db(tmp_path) -> Path:
    """Small SQLite database with 5 instruments for TUI tests."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Instrument.metadata.create_all(engine)
    instruments = [
        Instrument(
            instrument_pid=f"Test-Instrument-{i:03d}",
            api_url=f"https://nemo.example.com/api/tools/?id={i}",
            calendar_url="https://nemo.example.com/calendar",
            display_name=f"Test Instrument {i}",
            location=f"Building {i}, Room 100",
            property_tag=f"PRP-{i:05d}",
            filestore_path=f"instrument_{i:03d}",
            harvester="nemo",
            timezone_str="America/New_York",
        )
        for i in range(1, 6)
    ]
    with Session(engine) as session:
        session.add_all(instruments)
        session.commit()
    return db_path


# ---------------------------------------------------------------------------
# create-demo command
# ---------------------------------------------------------------------------


class TestCreateDemoCommand:
    """Tests for the ``nexuslims db create-demo`` command."""

    def test_creates_db_at_default_path(self, tmp_path, monkeypatch):
        from nexusLIMS.cli.migrate import _cli

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(_cli(), ["create-demo"])

        assert result.exit_code == 0
        assert (tmp_path / "nexuslims_demo.db").exists()
        assert "✓" in result.output

    def test_creates_db_at_explicit_path(self, tmp_path):
        from nexusLIMS.cli.migrate import _cli

        db_path = tmp_path / "my_demo.db"
        runner = CliRunner()
        result = runner.invoke(_cli(), ["create-demo", str(db_path)])

        assert result.exit_code == 0
        assert db_path.exists()

    def test_populates_10_instruments(self, tmp_path):
        from nexusLIMS.cli.migrate import _cli

        db_path = tmp_path / "demo.db"
        runner = CliRunner()
        runner.invoke(_cli(), ["create-demo", str(db_path)])

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
        conn.close()
        assert count == 10

    def test_refuses_to_overwrite_without_force(self, tmp_path):
        from nexusLIMS.cli.migrate import _cli

        db_path = tmp_path / "demo.db"
        db_path.touch()
        runner = CliRunner()
        result = runner.invoke(_cli(), ["create-demo", str(db_path)])

        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_force_flag_overwrites_existing(self, demo_db):
        from nexusLIMS.cli.migrate import _cli

        runner = CliRunner()
        result = runner.invoke(_cli(), ["create-demo", str(demo_db), "--force"])

        assert result.exit_code == 0, result.output
        assert "✓" in result.output
        # Confirm it's still a valid demo db
        conn = sqlite3.connect(demo_db)
        count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
        conn.close()
        assert count == 10

    def test_help_text(self):
        from nexusLIMS.cli.migrate import _cli

        runner = CliRunner()
        result = runner.invoke(_cli(), ["create-demo", "--help"])

        assert result.exit_code == 0
        assert "demo" in result.output.lower()
        assert "PATH" in result.output
        assert "--force" in result.output

    def test_error_on_exception(self, tmp_path):
        from nexusLIMS.cli.migrate import _cli

        db_path = tmp_path / "demo.db"
        with patch(
            "nexusLIMS.tui.demo_helpers.create_demo_database",
            side_effect=RuntimeError("disk full"),
        ):
            result = CliRunner().invoke(_cli(), ["create-demo", str(db_path)])

        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# view command
# ---------------------------------------------------------------------------


class TestViewCommand:
    """Tests for the ``nexuslims db view`` command."""

    def test_help_text(self):
        from nexusLIMS.cli.migrate import _cli

        runner = CliRunner()
        result = runner.invoke(_cli(), ["view", "--help"])

        assert result.exit_code == 0
        assert "read-only" in result.output.lower()

    def test_exits_when_nx_db_path_not_set(self):
        from nexusLIMS.cli.migrate import _cli

        # load_dotenv uses override=False by default, so it will not overwrite
        # the empty string we set via CliRunner's env parameter.
        result = CliRunner().invoke(_cli(), ["view"], env={"NX_DB_PATH": ""})

        assert result.exit_code != 0
        assert "NX_DB_PATH" in result.output

    def test_exits_when_db_does_not_exist(self, tmp_path):
        from nexusLIMS.cli.migrate import _cli

        missing = str(tmp_path / "missing.db")
        result = CliRunner().invoke(_cli(), ["view"], env={"NX_DB_PATH": missing})

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_launches_app_when_db_exists(self, demo_db):
        from nexusLIMS.cli.migrate import _cli

        with patch("nexusLIMS.tui.apps.db_browser.NexusLIMSDBApp.run") as mock_run:
            result = CliRunner().invoke(
                _cli(), ["view"], env={"NX_DB_PATH": str(demo_db)}
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# NexusLIMSTableViewerPane — logic tests (no pilot)
# ---------------------------------------------------------------------------


class TestNexusLIMSTableViewerPaneLogic:
    """Tests for pane helper methods that don't require a running app."""

    def test_sort_label_unsorted(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = None
        pane._sort_asc = True

        assert pane._sort_label("instrument_pid") == "instrument_pid"

    def test_sort_label_ascending(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = True

        assert pane._sort_label("instrument_pid") == "instrument_pid ↑"

    def test_sort_label_descending(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = False

        assert pane._sort_label("instrument_pid") == "instrument_pid ↓"

    def test_sort_label_other_column_unchanged(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = True

        assert pane._sort_label("location") == "location"

    def test_header_selected_sets_sort_col(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = None
        pane._sort_asc = True
        pane._load_table = MagicMock()

        event = SimpleNamespace(column_key=SimpleNamespace(value="instrument_pid"))
        pane._on_header_selected(event)

        assert pane._sort_col == "instrument_pid"
        assert pane._sort_asc is True
        pane._load_table.assert_called_once()

    def test_header_selected_second_click_reverses(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = True
        pane._load_table = MagicMock()

        event = SimpleNamespace(column_key=SimpleNamespace(value="instrument_pid"))
        pane._on_header_selected(event)

        assert pane._sort_col == "instrument_pid"
        assert pane._sort_asc is False

    def test_header_selected_third_click_clears(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = False
        pane._load_table = MagicMock()

        event = SimpleNamespace(column_key=SimpleNamespace(value="instrument_pid"))
        pane._on_header_selected(event)

        assert pane._sort_col is None
        assert pane._sort_asc is True

    def test_on_table_changed_blank_value_returns_early(self):
        from textual.widgets._select import NULL as SELECT_BLANK

        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._load_table = MagicMock()

        event = SimpleNamespace(value=SELECT_BLANK)
        pane._on_table_changed(event)

        pane._load_table.assert_not_called()

    def test_on_filter_changed_updates_text_and_reloads(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._load_table = MagicMock()

        event = SimpleNamespace(value="my_filter")
        pane._on_filter_changed(event)

        assert pane._filter_text == "my_filter"
        pane._load_table.assert_called_once()

    def test_header_selected_different_column_resets_to_asc(self):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSTableViewerPane

        pane = object.__new__(NexusLIMSTableViewerPane)
        pane._sort_col = "instrument_pid"
        pane._sort_asc = False
        pane._load_table = MagicMock()

        event = SimpleNamespace(column_key=SimpleNamespace(value="location"))
        pane._on_header_selected(event)

        assert pane._sort_col == "location"
        assert pane._sort_asc is True


# ---------------------------------------------------------------------------
# NexusLIMSTableViewerPane — TUI integration tests
# ---------------------------------------------------------------------------


class TestNexusLIMSTableViewerPaneTUI:
    """TUI integration tests for NexusLIMSTableViewerPane."""

    @pytest.mark.asyncio
    async def test_app_launches(self, small_db):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            assert app.is_running

    @pytest.mark.asyncio
    async def test_title_includes_db_path(self, small_db):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            assert str(small_db) in app.title

    @pytest.mark.asyncio
    async def test_execute_sql_tab_absent(self, small_db):
        from textual.widgets import TabbedContent

        from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            tc = app.query_one("#tabbed_ui", TabbedContent)
            tab_labels = [str(pane._title) for pane in tc.query("TabPane")]
            assert not any("SQL" in label for label in tab_labels)

    @pytest.mark.asyncio
    async def test_table_viewer_is_first_tab(self, small_db):
        from textual.widgets import TabbedContent

        from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            tc = app.query_one("#tabbed_ui", TabbedContent)
            panes = list(tc.query("TabPane"))
            assert "Table Viewer" in str(panes[0]._title)

    @pytest.mark.asyncio
    async def test_table_viewer_loads_rows(self, small_db):
        from textual.widgets import DataTable, Select

        from nexusLIMS.tui.apps.db_browser import (
            NexusLIMSDBApp,
            NexusLIMSTableViewerPane,
        )

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            pane = app.query_one(NexusLIMSTableViewerPane)
            # Explicitly select instruments (first table alphabetically may differ)
            app.query_one("#table_names_select", Select).value = "instruments"
            pane._load_table()
            await pilot.pause(0.1)
            dt = app.query_one("#sqlite_table_data", DataTable)
            assert dt.row_count == 5

    @pytest.mark.asyncio
    async def test_filter_narrows_results(self, small_db):
        from textual.widgets import DataTable

        from nexusLIMS.tui.apps.db_browser import (
            NexusLIMSDBApp,
            NexusLIMSTableViewerPane,
        )

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            pane = app.query_one(NexusLIMSTableViewerPane)
            # Set filter directly and reload
            pane._filter_text = "001"
            pane._load_table()
            await pilot.pause(0.1)
            dt = app.query_one("#sqlite_table_data", DataTable)
            assert dt.row_count == 1

    @pytest.mark.asyncio
    async def test_load_table_with_sort_col(self, small_db):
        from textual.widgets import DataTable, Select

        from nexusLIMS.tui.apps.db_browser import (
            NexusLIMSDBApp,
            NexusLIMSTableViewerPane,
        )

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            pane = app.query_one(NexusLIMSTableViewerPane)
            app.query_one("#table_names_select", Select).value = "instruments"
            pane._sort_col = "instrument_pid"
            pane._sort_asc = True
            pane._load_table()
            await pilot.pause(0.1)
            dt = app.query_one("#sqlite_table_data", DataTable)
            assert dt.row_count == 5

    @pytest.mark.asyncio
    async def test_update_ui_notifies_when_db_missing(self, small_db):
        from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            await app.update_ui("/nonexistent/path/missing.db")
            await pilot.pause(0.1)
            # App should still be running — notify() was called, not exit
            assert app.is_running

    @pytest.mark.asyncio
    async def test_filter_no_results_shows_blank_row(self, small_db):
        from textual.widgets import DataTable

        from nexusLIMS.tui.apps.db_browser import (
            NexusLIMSDBApp,
            NexusLIMSTableViewerPane,
        )

        app = NexusLIMSDBApp(Namespace(filepath=str(small_db)))
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause(0.5)
            pane = app.query_one(NexusLIMSTableViewerPane)
            pane._filter_text = "ZZZNOMATCH"
            pane._load_table()
            await pilot.pause(0.1)
            dt = app.query_one("#sqlite_table_data", DataTable)
            assert dt.row_count == 1  # one blank placeholder row


pytestmark = pytest.mark.database
