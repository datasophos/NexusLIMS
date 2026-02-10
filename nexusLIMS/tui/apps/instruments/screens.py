"""
Screens for the instrument management TUI application.

Provides List, Add, Edit, and Delete screens for instrument CRUD operations.
"""

import pytz
from sqlmodel import select
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from nexusLIMS.db.models import Instrument
from nexusLIMS.tui.apps.instruments.validators import (
    get_example_values,
    validate_api_url_unique,
    validate_instrument_pid,
)
from nexusLIMS.tui.common.base_screens import (
    BaseFormScreen,
    BaseListScreen,
    ConfirmDialog,
)
from nexusLIMS.tui.common.db_utils import get_session_log_count
from nexusLIMS.tui.common.validators import (
    validate_timezone,
)
from nexusLIMS.tui.common.widgets import AutocompleteInput, FormField, NumpadInput


class WelcomeDialog(ModalScreen):
    """Welcome dialog shown when instruments table is empty."""

    DEFAULT_CSS = """
    WelcomeDialog {
        align: center middle;
    }

    #welcome-dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 2;
    }

    #welcome-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #welcome-message {
        margin: 1 0;
    }

    #welcome-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
        margin-top: 1;
        grid-gutter: 1 0;
    }

    #add-btn {
        min-width: 30;
        width: auto;
    }

    #close-btn {
        min-width: 30;
        width: auto;
    }

    """

    def compose(self) -> ComposeResult:
        """Compose the welcome dialog."""
        with Vertical(id="welcome-dialog"):
            yield Label(
                "Welcome to the NexusLIMS Instrument Manager!", id="welcome-title"
            )
            yield Static(
                "No instruments were found in the database! If this is your first time "
                "running NexusLIMS, welcome!\n\n"
                "To get started, add your first instrument by pressing 'a' or clicking "
                "the button below.\n\n"
                "You can also:\n"
                "• Press '?' for help and keybindings\n"
                "• Press Ctrl+T to toggle dark/light theme\n"
                "• Press Ctrl+Q or 'q' to quit",
                id="welcome-message",
            )
            with Vertical(id="welcome-buttons"):
                yield Button(
                    "Add First Instrument (a)", id="add-btn", variant="primary"
                )
                yield Button("Close", id="close-btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-btn":
            self.dismiss(True)  # Signal to open add screen
        else:
            self.dismiss(False)  # Just close


class InstrumentListScreen(BaseListScreen):
    """Screen displaying all instruments in a table."""

    def on_mount(self) -> None:
        """Set up the screen and check if welcome dialog should be shown."""
        super().on_mount()

        # Check if instruments table is empty
        instruments = self.app.db_session.exec(select(Instrument)).all()

        if not instruments:
            # Show welcome dialog
            self.app.push_screen(WelcomeDialog(), self.on_welcome_complete)

    def on_welcome_complete(self, should_add: bool) -> None:
        """Handle welcome dialog completion."""
        if should_add:
            # User wants to add first instrument
            self.action_add()

    def get_columns(self) -> list[str]:
        """Get column headers."""
        return [
            "Display Name",
            "PID",
            "API URL",
            "Filestore Path",
            "Location",
            "Property Tag",
            "Timezone",
        ]

    def get_data(self) -> list[dict]:
        """Get instrument data from database."""
        instruments = self.app.db_session.exec(select(Instrument)).all()

        data = []
        for instr in instruments:
            data.append(
                {
                    "Display Name": instr.display_name,
                    "PID": instr.instrument_pid,
                    "API URL": instr.api_url,
                    "Filestore Path": instr.filestore_path,
                    "Location": instr.location,
                    "Property Tag": instr.property_tag,
                    "Timezone": instr.timezone_str,
                }
            )

        return data

    def on_row_selected(self, _row_key, row_data: dict) -> None:
        """Handle row selection - show edit screen."""
        # Load full instrument from database
        instrument_pid = row_data["PID"]
        instrument = self.app.db_session.get(Instrument, instrument_pid)

        if instrument:
            # Push edit screen
            edit_screen = InstrumentEditScreen(instrument)
            self.app.push_screen(edit_screen, self.on_edit_complete)

    def on_edit_complete(self, result) -> None:
        """Handle edit screen completion."""
        if result:
            self.refresh_data()

    def action_add(self) -> None:
        """Show add instrument screen."""
        add_screen = InstrumentAddScreen()
        self.app.push_screen(add_screen, self.on_add_complete)

    def on_add_complete(self, result) -> None:
        """Handle add screen completion."""
        if result:
            self.refresh_data()

    def action_delete(self) -> None:
        """Delete selected instrument."""
        table = self.query_one("DataTable")
        if table.cursor_row is not None and table.row_count > 0:
            # Get instrument PID from current row
            columns = self.get_columns()
            cursor_row = table.cursor_row
            row_data = {}

            for i, column in enumerate(columns):
                row_data[column] = table.get_row_at(cursor_row)[i]

            instrument_pid = row_data["PID"]

            # Load instrument
            instrument = self.app.db_session.get(Instrument, instrument_pid)
            if instrument:
                # Check for session logs
                session_count = get_session_log_count(
                    self.app.db_session, instrument_pid
                )

                # Build confirmation message
                message = f"Delete instrument '{instrument_pid}'?"
                if session_count > 0:
                    message += (
                        f"\n\nWarning: This instrument has {session_count} "
                        "session log entries.\nThese entries will NOT be deleted "
                        "but will reference a non-existent instrument."
                    )

                # Show confirmation dialog
                def on_confirm(confirmed: bool):
                    if confirmed:
                        self.delete_instrument(instrument_pid)

                self.app.push_screen(
                    ConfirmDialog(message, title="Confirm Delete"),
                    on_confirm,
                )

    def delete_instrument(self, instrument_pid: str) -> None:
        """Delete an instrument from the database."""
        try:
            instrument = self.app.db_session.get(Instrument, instrument_pid)
            if instrument:
                self.app.db_session.delete(instrument)
                self.app.db_session.commit()
                self.app.show_success(f"Deleted instrument: {instrument_pid}")
                self.refresh_data()
        except Exception as e:
            self.app.db_session.rollback()
            self.app.show_error(f"Failed to delete instrument: {e}")


class InstrumentAddScreen(BaseFormScreen):
    """Screen for adding a new instrument."""

    # Disable auto-focus to prevent scrolling to first input
    AUTO_FOCUS = ""

    def __init__(self, **kwargs):
        """Initialize add screen."""
        super().__init__(title="Add New Instrument", **kwargs)
        self.examples = get_example_values()

    def on_mount(self) -> None:
        """Focus first input without scrolling."""
        # Focus the first input without scrolling the viewport
        first_input = self.query_one("#instrument_pid", Input)
        first_input.focus(scroll_visible=False)

    def get_form_fields(self) -> ComposeResult:
        """Generate form fields for instrument creation."""
        # Required fields
        yield FormField(
            "Instrument PID",
            NumpadInput(
                placeholder=self.examples["instrument_pid"],
                id="instrument_pid",
            ),
            required=True,
            help_text=f"Unique identifier (e.g., {self.examples['instrument_pid']})",
        )

        yield FormField(
            "API URL",
            Input(
                placeholder=self.examples["api_url"],
                id="api_url",
            ),
            required=True,
            help_text=f"Calendar API endpoint URL (e.g., {self.examples['api_url']})",
        )

        yield FormField(
            "Calendar URL",
            Input(
                placeholder=self.examples["calendar_url"],
                id="calendar_url",
            ),
            required=True,
            help_text=(
                f"Web-accessible calendar URL (e.g., {self.examples['calendar_url']})"
            ),
        )

        yield FormField(
            "Location",
            Input(
                placeholder=self.examples["location"],
                id="location",
            ),
            required=True,
            help_text=f"Physical location (e.g., {self.examples['location']})",
        )

        yield FormField(
            "Display Name",
            Input(
                placeholder=self.examples["display_name"],
                id="display_name",
            ),
            required=True,
            help_text=(
                f"Human-readable instrument name for NexusLIMS records "
                f"(e.g., {self.examples['display_name']})"
            ),
        )

        yield FormField(
            "Property Tag",
            Input(
                placeholder=self.examples["property_tag"],
                id="property_tag",
            ),
            required=True,
            help_text=(
                f"Unique numeric identifier (e.g., {self.examples['property_tag']})"
            ),
        )

        yield FormField(
            "Filestore Path",
            Input(
                placeholder=self.examples["filestore_path"],
                id="filestore_path",
            ),
            required=True,
            help_text=(
                f"Relative path under NX_INSTRUMENT_DATA_PATH "
                f"(e.g., {self.examples['filestore_path']})"
            ),
        )

        yield FormField(
            "Harvester",
            Select(
                [("nemo", "nemo")],
                value="nemo",
                id="harvester",
            ),
            required=True,
            help_text='Harvester module ("nemo" is the only option, currently)',
        )

        yield FormField(
            "Timezone",
            AutocompleteInput(
                suggestions=pytz.common_timezones,
                placeholder=self.examples["timezone_str"],
                value="America/New_York",
                id="timezone_str",
            ),
            required=True,
            help_text="IANA timezone (e.g., America/New_York)",
        )

    def collect_form_data(self) -> dict:
        """Collect data from form fields."""
        # Get form fields
        return {
            "instrument_pid": self.query_one("#instrument_pid", Input).value,
            "api_url": self.query_one("#api_url", Input).value,
            "calendar_url": self.query_one("#calendar_url", Input).value,
            "location": self.query_one("#location", Input).value,
            "display_name": self.query_one("#display_name", Input).value,
            "property_tag": self.query_one("#property_tag", Input).value,
            "filestore_path": self.query_one("#filestore_path", Input).value,
            "harvester": self.query_one("#harvester", Select).value,
            "timezone_str": self.query_one("#timezone_str", Input).value,
        }

    def validate_form(self) -> dict[str, str]:
        """Validate form data."""
        errors = {}
        data = self.collect_form_data()

        # Validate instrument_pid
        is_valid, error = validate_instrument_pid(data["instrument_pid"])
        if not is_valid:
            errors["instrument_pid"] = error

        # Validate api_url (with uniqueness check)
        is_valid, error = validate_api_url_unique(self.app.db_session, data["api_url"])
        if not is_valid:
            errors["api_url"] = error

        # Validate timezone
        is_valid, error = validate_timezone(data["timezone_str"])
        if not is_valid:
            errors["timezone_str"] = error

        # Show a notification if there are validation errors (without logging as error)
        if errors:
            error_count = len(errors)
            field_names = ", ".join(errors.keys())
            msg = (
                f"Validation failed: {error_count} error(s) in {field_names}. "
                "See details at bottom of form."
            )
            self.app.notify(msg, severity="warning", timeout=5)

        return errors

    def on_save(self, data: dict) -> None:
        """Save new instrument to database."""
        try:
            # Create instrument
            instrument = Instrument(**data)

            # Add to database
            self.app.db_session.add(instrument)
            self.app.db_session.commit()

            self.app.show_success(f"Created instrument: {data['instrument_pid']}")
            self.dismiss(True)

        except Exception as e:
            self.app.db_session.rollback()
            self.app.show_error(f"Failed to create instrument: {e}")


class InstrumentEditScreen(InstrumentAddScreen):
    """Screen for editing an existing instrument."""

    def __init__(self, instrument: Instrument, **kwargs):
        """
        Initialize edit screen.

        Parameters
        ----------
        instrument : Instrument
            Instrument to edit
        **kwargs
            Additional arguments passed to BaseFormScreen
        """
        self.instrument = instrument
        super().__init__(**kwargs)
        self.screen_title = f"Edit Instrument: {instrument.instrument_pid}"

    def on_mount(self) -> None:
        """Populate form with existing instrument data."""
        super().on_mount()

        # Populate fields
        self.query_one("#instrument_pid", Input).value = self.instrument.instrument_pid
        self.query_one("#instrument_pid", Input).disabled = True  # Can't change PID

        self.query_one("#api_url", Input).value = self.instrument.api_url
        self.query_one("#calendar_url", Input).value = self.instrument.calendar_url
        self.query_one("#location", Input).value = self.instrument.location
        self.query_one("#display_name", Input).value = self.instrument.display_name
        self.query_one("#property_tag", Input).value = self.instrument.property_tag
        self.query_one("#filestore_path", Input).value = self.instrument.filestore_path
        self.query_one("#harvester", Select).value = self.instrument.harvester
        self.query_one("#timezone_str", Input).value = self.instrument.timezone_str

    def validate_form(self) -> dict[str, str]:
        """Validate form data (excluding PID from uniqueness checks)."""
        errors = {}
        data = self.collect_form_data()

        # Validate api_url (with uniqueness check, excluding current instrument)
        is_valid, error = validate_api_url_unique(
            self.app.db_session,
            data["api_url"],
            exclude_pid=self.instrument.instrument_pid,
        )
        if not is_valid:
            errors["api_url"] = error

        # Validate timezone
        is_valid, error = validate_timezone(data["timezone_str"])
        if not is_valid:
            errors["timezone_str"] = error

        # Show a notification if there are validation errors (without logging as error)
        if errors:
            error_count = len(errors)
            field_names = ", ".join(errors.keys())
            msg = (
                f"Validation failed: {error_count} error(s) in {field_names}. "
                "See details at bottom of form."
            )
            self.app.notify(msg, severity="warning", timeout=5)

        return errors

    def on_save(self, data: dict) -> None:
        """Update existing instrument in database."""
        try:
            # Update instrument fields (except PID)
            self.instrument.api_url = data["api_url"]
            self.instrument.calendar_url = data["calendar_url"]
            self.instrument.location = data["location"]
            self.instrument.display_name = data["display_name"]
            self.instrument.property_tag = data["property_tag"]
            self.instrument.filestore_path = data["filestore_path"]
            self.instrument.harvester = data["harvester"]
            self.instrument.timezone_str = data["timezone_str"]

            # Commit changes
            self.app.db_session.add(self.instrument)
            self.app.db_session.commit()

            self.app.show_success(f"Updated instrument: {data['instrument_pid']}")
            self.dismiss(True)

        except Exception as e:
            self.app.db_session.rollback()
            self.app.show_error(f"Failed to update instrument: {e}")
