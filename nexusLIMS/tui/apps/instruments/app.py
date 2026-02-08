"""
Instrument Management TUI Application.

Provides an interactive terminal UI for CRUD operations on the NexusLIMS
instruments database.
"""

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
    """

    def on_mount(self) -> None:
        """Set up the app and show instrument list."""
        super().on_mount()

        # Push the list screen as the main screen
        self.push_screen(InstrumentListScreen())

    def get_app_name(self) -> str:
        """Get application name for help screen."""
        return "NexusLIMS Instrument Manager"

    def get_keybindings(self) -> list[tuple[str, str]]:
        """Get app-specific keybindings for help screen."""
        base_bindings = super().get_keybindings()

        app_bindings = [
            ("a", "Add new instrument"),
            ("e", "Edit selected instrument"),
            ("d", "Delete selected instrument"),
            ("r", "Refresh instrument list"),
            ("↑↓", "Navigate instrument list"),
            ("Enter", "Edit selected instrument"),
        ]

        return app_bindings + base_bindings
