"""
Base application class for NexusLIMS TUI applications.

Provides common functionality including theme switching, database session
management, help screens, and error notifications.
"""

import logging
from typing import ClassVar

from sqlmodel import Session
from textual.app import App
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown

from nexusLIMS.db.engine import get_engine

_logger = logging.getLogger(__name__)


class HelpScreen(Screen):
    """Help screen showing keybindings and usage information."""

    BINDINGS: ClassVar = [
        ("escape", "dismiss", "Close Help"),
        ("q", "dismiss", "Close Help"),
    ]

    def __init__(self, app_name: str, keybindings: list[tuple[str, str]], **kwargs):
        """
        Initialize help screen.

        Parameters
        ----------
        app_name : str
            Name of the application
        keybindings : list[tuple[str, str]]
            List of (key, description) tuples
        **kwargs
            Additional arguments passed to Screen
        """
        super().__init__(**kwargs)
        self.app_name = app_name
        self.keybindings = keybindings

    def compose(self):
        """Compose help screen layout."""
        yield Header()

        help_text = f"# {self.app_name}\n\n"
        help_text += "## Keybindings\n\n"

        for key, description in self.keybindings:
            help_text += f"- **{key}**: {description}\n"

        help_text += "\n## Theme Switching\n\n"
        help_text += "- **Ctrl+T**: Toggle between dark and light themes\n"
        help_text += "\n## Navigation\n\n"
        help_text += "- **Arrow keys**: Navigate menus and forms\n"
        help_text += "- **Tab**: Move between form fields\n"
        help_text += "- **Enter**: Select/Submit\n"
        help_text += "- **Escape**: Cancel/Go back\n"

        yield Markdown(help_text, id="help-content")
        yield Footer()

    def action_dismiss(self):
        """Dismiss the help screen."""
        self.app.pop_screen()


class BaseNexusApp(App):
    """
    Base application class for NexusLIMS TUI apps.

    Provides:
    - Theme switching (dark/light) using Textual's built-in themes
    - Database session management
    - Help screen
    - Error notifications
    - Common keybindings

    Subclasses should:
    - Define their own screens
    - Override get_app_name() to return app name
    - Override get_keybindings() to add app-specific bindings
    """

    # CSS using Textual's built-in design system variables
    # Colors automatically adapt to dark/light mode via self.dark property
    CSS = """
    /* DataTable styling */
    DataTable {
        height: 1fr;
        border: solid $primary;
    }

    DataTable > .datatable--header {
        background: $primary;
        color: $background;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $accent 20%;
    }

    /* Form layout */
    #form-container {
        width: 100%;
        height: 100%;
        padding: 1 2;
        overflow-y: auto;
    }

    #form-fields {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    .form-title {
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
        color: $primary;
    }

    .field-label {
        margin-top: 1;
    }

    .field-help {
        color: $text-muted;
        text-style: italic;
        margin-bottom: 1;
    }

    .field-error {
        color: $error;
        margin-top: 1;
        display: none;
    }

    .field-error.visible {
        display: block;
    }

    #form-error {
        color: $error;
        background: $error 10%;
        border: solid $error;
        padding: 1;
        margin: 1 0;
        display: none;
    }

    #form-error.visible {
        display: block;
    }

    #form-buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    /* Input styling */
    Input {
        width: 100%;
        margin-bottom: 1;
    }

    Input:focus {
        border: tall $accent;
    }

    Input.error {
        border: tall $error;
    }

    /* Button styling */
    Button {
        margin: 0 1;
    }

    Button:focus {
        text-style: bold;
    }

    /* General layout */
    Label {
        width: 100%;
    }

    Static {
        width: 100%;
    }

    Vertical {
        width: 100%;
        height: auto;
    }

    Horizontal {
        width: 100%;
        height: auto;
    }
    """

    BINDINGS: ClassVar = [
        ("ctrl+t", "toggle_theme", "Toggle Theme"),
        ("ctrl+q", "quit", "Quit"),
        ("?", "help", "Help"),
    ]

    def __init__(self, **kwargs):
        """Initialize the base application with dark mode by default."""
        # Will be set in on_mount
        self.db_session: Session | None = None

        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """Set up database connection."""
        # Create database session
        try:
            self.db_session = Session(get_engine())
            _logger.debug("Database session created")
        except Exception as e:
            _logger.exception("Failed to create database session")
            self.show_error(f"Database connection failed: {e}")

    def on_unmount(self) -> None:
        """Clean up database connection."""
        if self.db_session:
            self.db_session.close()
            _logger.debug("Database session closed")

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light themes using Textual's built-in system."""
        # Use Textual's built-in action to toggle between textual-dark and textual-light
        self.action_toggle_dark()

        # Show notification
        theme_name = "light" if self.current_theme.name == "textual-light" else "dark"
        self.notify(f"Switched to {theme_name} mode", timeout=2)
        _logger.debug("Theme toggled to: %s", self.current_theme.name)

    def action_help(self) -> None:
        """Show help screen."""
        help_screen = HelpScreen(
            app_name=self.get_app_name(),
            keybindings=self.get_keybindings(),
        )
        self.push_screen(help_screen)

    def get_app_name(self) -> str:
        """
        Get application name for help screen.

        Returns
        -------
        str
            Application name (override in subclass)
        """
        return "NexusLIMS TUI"

    def get_keybindings(self) -> list[tuple[str, str]]:
        """
        Get app-specific keybindings for help screen.

        Returns
        -------
        list[tuple[str, str]]
            List of (key, description) tuples (override in subclass)
        """
        return [
            ("ctrl+q", "Quit application"),
            ("ctrl+t", "Toggle theme (dark/light)"),
            ("?", "Show this help"),
        ]

    def show_error(self, message: str) -> None:
        """
        Display an error notification.

        Parameters
        ----------
        message : str
            Error message to display
        """
        # Use Textual's notify system
        self.notify(message, severity="error", timeout=5)
        _logger.error(message)

    def show_success(self, message: str) -> None:
        """
        Display a success notification.

        Parameters
        ----------
        message : str
            Success message to display
        """
        self.notify(message, severity="information", timeout=3)
        _logger.info(message)

    def show_warning(self, message: str) -> None:
        """
        Display a warning notification.

        Parameters
        ----------
        message : str
            Warning message to display
        """
        self.notify(message, severity="warning", timeout=4)
        _logger.warning(message)
