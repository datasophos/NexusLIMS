"""Read-only NexusLIMS database browser TUI.

Provides :class:`NexusLIMSDBApp`, a Textual app that wraps Squall's
``SQLiteClientApp`` to give a stripped-down, read-only view of the database:

* The "Open Database" button and "Execute SQL" tab are removed.
* The Table Viewer tab gains a live filter input and click-to-sort column
  headers, both implemented via parameterised SQL queries so they compose
  correctly and never expose the database to modification.

Usage
-----

.. code-block:: python

    from argparse import Namespace
    from nexusLIMS.tui.apps.db_browser import NexusLIMSDBApp

    app = NexusLIMSDBApp(Namespace(filepath="/path/to/nexuslims.db"))
    app.run()
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from squall import db_utility
from squall.database_structure_tree import DatabaseStructurePane
from squall.squall import SQLiteClientApp
from textual import on
from textual.widgets import DataTable, Input, Select, TabbedContent, TabPane
from textual.widgets._select import NULL as SELECT_BLANK

if TYPE_CHECKING:
    from textual.app import ComposeResult

# ---------------------------------------------------------------------------
# Resolve squall's stylesheet at import time so the subclass can reference it
# as a class variable regardless of where *this* module lives on disk.
# ---------------------------------------------------------------------------
import squall as _squall_pkg

_SQUALL_TCSS = str(Path(_squall_pkg.__file__).parent / "squall.tcss")


class NexusLIMSTableViewerPane(TabPane):
    """Table viewer with live full-text filter and sortable column headers.

    All filtering and sorting is performed via parameterised SQL queries
    so they compose naturally and the database is never modified.
    """

    DEFAULT_CSS = """
    NexusLIMSTableViewerPane {
        Select {
            margin: 1;
            border: round gold;
        }

        #filter_input {
            margin: 1;
            border: round $accent;
            width: 100%;
        }

        DataTable {
            margin: 1;
            border: round gold;
            height: 1fr;
        }
    }
    """

    def __init__(self, db_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db_path = db_path
        self.tables: list[str] = sorted(db_utility.get_table_names(db_path))
        self._filter_text: str = ""
        self._sort_col: str | None = None
        self._sort_asc: bool = True
        self._col_names: list[str] = []

    def compose(self) -> ComposeResult:
        """Build the table viewer layout."""
        yield Select.from_values(
            self.tables, id="table_names_select", value=self.tables[0]
        )
        yield Input(
            placeholder="Filter rows… (searches all columns)",
            id="filter_input",
        )
        yield DataTable(id="sqlite_table_data")

    def on_mount(self) -> None:
        """Load the initial table on mount."""
        # Inline style wins over squall's CSS_PATH rule (Input { width: 80% })
        self.query_one("#filter_input", Input).styles.width = "100%"
        self._load_table()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(Select.Changed, "#table_names_select")
    def _on_table_changed(self, event: Select.Changed) -> None:
        """Reset filter and sort state when the selected table changes."""
        if event.value is SELECT_BLANK:
            return
        self._filter_text = ""
        self._sort_col = None
        self._sort_asc = True
        self.query_one("#filter_input", Input).value = ""
        self._load_table()

    @on(Input.Changed, "#filter_input")
    def _on_filter_changed(self, event: Input.Changed) -> None:
        """Re-query the database whenever the filter text changes."""
        self._filter_text = event.value
        self._load_table()

    @on(DataTable.HeaderSelected, "#sqlite_table_data")
    def _on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Cycle sort direction on repeated clicks; change column otherwise."""
        clicked_col = event.column_key.value  # str key we supplied to add_column
        if self._sort_col == clicked_col:
            if self._sort_asc:
                self._sort_asc = False
            else:
                # Third click on the same column clears sorting
                self._sort_col = None
                self._sort_asc = True
        else:
            self._sort_col = clicked_col
            self._sort_asc = True
        self._load_table()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_table(self) -> None:
        """Fetch rows from SQLite and populate the DataTable.

        Builds a single parameterised ``SELECT`` statement that combines the
        current filter text (``WHERE … LIKE ?``) and sort column
        (``ORDER BY … ASC/DESC``) so both features compose correctly.
        """
        table_name = str(self.app.query_one("#table_names_select", Select).value)
        filter_text = self._filter_text.strip()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Discover column names without fetching any data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")  # noqa: S608
        col_names = [d[0] for d in cursor.description]
        self._col_names = col_names

        # Build WHERE clause — cast every column to TEXT so LIKE works on
        # integers, datetimes, etc.
        params: list[str] = []
        where = ""
        if filter_text:
            conditions = [f"CAST({col} AS TEXT) LIKE ?" for col in col_names]
            where = "WHERE " + " OR ".join(conditions)
            params = [f"%{filter_text}%" for _ in col_names]

        # Build ORDER BY clause
        order = ""
        if self._sort_col and self._sort_col in col_names:
            direction = "ASC" if self._sort_asc else "DESC"
            order = f"ORDER BY {self._sort_col} {direction}"

        sql = f"SELECT * FROM {table_name} {where} {order} LIMIT 1000"  # noqa: S608
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # Build display labels: add ↑/↓ to the sorted column header
        display_labels = [self._sort_label(name) for name in col_names]

        dt = self.query_one("#sqlite_table_data", DataTable)
        dt.clear(columns=True)
        for name, label in zip(col_names, display_labels):
            dt.add_column(label, key=name)

        if rows:
            dt.add_rows(rows)
        else:
            dt.add_rows([tuple("" for _ in col_names)])

        dt.cursor_type = "row"

    def _sort_label(self, col_name: str) -> str:
        """Return the display label for a column header, with sort indicator."""
        if col_name == self._sort_col:
            indicator = " ↑" if self._sort_asc else " ↓"
            return f"{col_name}{indicator}"
        return col_name


class NexusLIMSDBApp(SQLiteClientApp):
    """Read-only NexusLIMS database browser.

    Extends Squall's ``SQLiteClientApp`` with:

    * The "Open Database" button hidden (path always comes from ``NX_DB_PATH``)
    * The "Execute SQL" tab removed to prevent accidental modifications
    * The Table Viewer replaced with :class:`NexusLIMSTableViewerPane`, which
      adds a live filter input and sortable column headers
    """

    CSS_PATH = _SQUALL_TCSS
    DEFAULT_CSS = "#center { display: none; }"

    async def update_ui(self, db_file_path: Path) -> None:
        """Load the database into the read-only browser tabs."""
        if not Path(db_file_path).exists():
            self.notify("Database not found")
            return

        tabbed_content = self.query_one("#tabbed_ui", TabbedContent)
        await tabbed_content.clear_panes()
        await tabbed_content.add_pane(
            NexusLIMSTableViewerPane(db_file_path, title="Table Viewer")
        )
        await tabbed_content.add_pane(
            DatabaseStructurePane(
                db_file_path,
                title="Database Structure",
                id="db_structure",
            )
        )
        self.title = f"NexusLIMS DB — {db_file_path}"
