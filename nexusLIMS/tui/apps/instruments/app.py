"""
Instrument Management TUI Application.

Provides an interactive terminal UI for CRUD operations on the NexusLIMS
instruments database.
"""

from pathlib import Path

from sqlmodel import Session

from nexusLIMS import config
from nexusLIMS.db.engine import create_transient_sqlite_engine
from nexusLIMS.tui.apps.instruments.screens import InstrumentListScreen
from nexusLIMS.tui.common.base_app import BaseNexusApp


class InstrumentManagerApp(BaseNexusApp):
    """
    TUI application for managing NexusLIMS instruments.

    Provides:
    - List view of all instruments
    - Add new instruments
    - Edit existing instruments
    - Delete instruments (with confirmation)
    - Theme switching
    - Help screen

    Parameters
    ----------
    db_path : pathlib.Path | None
        Path to the database file. If provided, overrides NX_DB_PATH from config.
        If None, uses the value from config.settings.NX_DB_PATH.
    """

    def __init__(self, db_path: Path | None = None, **kwargs):
        """Initialize the instrument manager app."""
        self._db_path = db_path
        self._custom_engine = None
        super().__init__(**kwargs)

    @property
    def db_path(self) -> Path:
        """Get the database path (override or from config)."""
        return (
            self._db_path if self._db_path is not None else config.settings.NX_DB_PATH
        )

    def on_mount(self) -> None:
        """Set up the app and show instrument list."""
        # If custom db_path provided, create custom session
        if self._db_path is not None:
            try:
                self._custom_engine = create_transient_sqlite_engine(self._db_path)
                self.db_session = Session(self._custom_engine)
            except Exception as e:
                self.show_error(f"Database connection failed: {e}")
                return

        # Call parent on_mount (which creates default db_session if not set)
        super().on_mount()

        # Set title with database path
        self.title = f"NexusLIMS Instrument Manager - {self.db_path}"

        # Push the list screen as the main screen
        self.push_screen(InstrumentListScreen())

    def on_unmount(self) -> None:
        """Clean up database connection and custom engine."""
        super().on_unmount()
        if self._custom_engine is not None:
            self._custom_engine.dispose()
            self._custom_engine = None

    def get_app_name(self) -> str:
        """Get application name for help screen."""
        return "NexusLIMS Instrument Manager"

    def get_keybindings(self) -> list[tuple[str, str]]:
        """Get app-specific keybindings for help screen."""
        base_bindings = super().get_keybindings()

        app_bindings = [
            ("a", "Add new instrument"),
            ("e / Enter", "Edit selected instrument"),
            ("d", "Delete selected instrument"),
            ("r", "Refresh instrument list"),
            ("s", "Cycle sort column (press repeatedly to change column/direction)"),
            ("/", "Focus filter/search bar"),
            ("↑↓", "Navigate instrument list"),
            ("Click column header", "Sort by that column (click again to reverse)"),
            ("Double click instrument row", "Edit that instrument's data"),
        ]

        return app_bindings + base_bindings
