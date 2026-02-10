"""
Base screen classes for NexusLIMS TUI applications.

Provides reusable screen patterns for common UI tasks like list views,
forms, and confirmation dialogs.
"""

from abc import abstractmethod
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static


class BaseListScreen(Screen):
    """
    Base screen for displaying data in a table.

    Subclasses must implement:
    - get_columns() -> list[str]: Column headers
    - get_data() -> list[dict]: Row data
    - on_row_selected(row_key, row_data): Handle row selection

    Provides:
    - DataTable with navigation and sorting
    - Search/filter bar
    - Add/Edit/Delete/Quit keybindings
    - Header and footer
    """

    BINDINGS: ClassVar = [
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
        ("?", "help", "Help"),
        ("/", "focus_filter", "Filter"),
    ]

    def __init__(self, **kwargs):
        """Initialize the list screen."""
        super().__init__(**kwargs)
        self._filter_text = ""
        self._all_data = []
        self._sort_column = None
        self._sort_reverse = False

    def compose(self) -> ComposeResult:
        """Compose the list screen layout."""
        yield Header()
        yield Input(placeholder="Filter (press / to focus)...", id="filter-input")
        yield DataTable(id="data-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table on mount."""
        table = self.query_one(DataTable)

        # Add columns (only if not already added)
        if not table.columns:
            columns = self.get_columns()
            table.add_columns(*columns)

        # Load data
        self.refresh_data()

        # Focus the table (not the filter input)
        table.focus()

    def refresh_data(self) -> None:
        """Reload data into the table."""
        # Get all data and store it
        self._all_data = self.get_data()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply current filter to the data and update table."""
        table = self.query_one(DataTable)
        table.clear()

        # Filter data based on filter text
        filtered_data = self._all_data
        if self._filter_text:
            filter_lower = self._filter_text.lower()
            filtered_data = [
                row
                for row in self._all_data
                if any(filter_lower in str(v).lower() for v in row.values())
            ]

        # Sort data if a sort column is set
        if self._sort_column:
            filtered_data = sorted(
                filtered_data,
                key=lambda row: str(row.get(self._sort_column, "")),
                reverse=self._sort_reverse,
            )

        # Add filtered rows to table
        for row in filtered_data:
            # Use first column value as row key (should be unique ID)
            row_key = next(iter(row.values())) if row else None
            table.add_row(*row.values(), key=row_key)

    @on(DataTable.HeaderSelected)
    def on_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click for sorting."""
        columns = self.get_columns()
        column_name = columns[event.column_index]

        # Toggle sort direction if clicking same column, otherwise sort ascending
        if self._sort_column == column_name:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column_name
            self._sort_reverse = False

        self._apply_filter()

    @on(Input.Changed, "#filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        self._filter_text = event.value
        self._apply_filter()

    def action_focus_filter(self) -> None:
        """Focus the filter input."""
        self.query_one("#filter-input", Input).focus()

    @abstractmethod
    def get_columns(self) -> list[str]:
        """
        Get column headers for the table.

        Returns
        -------
        list[str]
            Column header names
        """

    @abstractmethod
    def get_data(self) -> list[dict]:
        """
        Get data rows for the table.

        Returns
        -------
        list[dict]
            List of row dictionaries (column_name -> value)
        """

    @on(DataTable.RowSelected)
    def on_row_selected_event(self, event: DataTable.RowSelected) -> None:
        """Handle row selection from table."""
        # Get row data from the table using cursor_row
        table = self.query_one(DataTable)
        row_data = {}
        columns = self.get_columns()

        # Get the row values from the table
        row_values = table.get_row_at(event.cursor_row)
        for i, column in enumerate(columns):
            row_data[column] = row_values[i]

        self.on_row_selected(event.row_key.value, row_data)

    @abstractmethod
    def on_row_selected(self, row_key, row_data: dict) -> None:
        """
        Handle row selection.

        Parameters
        ----------
        row_key
            Row key (typically primary key value)
        row_data : dict
            Dictionary mapping column names to values
        """

    def action_add(self) -> None:
        """Handle add action (default: no-op, override in subclass)."""

    def action_edit(self) -> None:
        """Handle edit action (default: edit selected row)."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            # Trigger row selected event for current row
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = {}
            columns = self.get_columns()
            cursor_row = table.cursor_row

            for i, column in enumerate(columns):
                row_data[column] = table.get_row_at(cursor_row)[i]

            self.on_row_selected(row_key, row_data)

    def action_delete(self) -> None:
        """Handle delete action (default: no-op, override in subclass)."""

    def action_refresh(self) -> None:
        """Handle refresh action."""
        self.refresh_data()

    def action_quit(self) -> None:
        """Handle quit action."""
        self.app.exit()

    def action_help(self) -> None:
        """Show help screen."""
        self.app.action_help()


class BaseFormScreen(Screen):
    """
    Base screen for add/edit forms.

    Subclasses must implement:
    - get_form_fields() -> ComposeResult: Yield form field widgets
    - validate_form() -> dict[str, str]: Validate and return errors
    - on_save(data: dict): Handle save action

    Provides:
    - Form layout with save/cancel buttons
    - Validation on save
    - Header and footer
    """

    BINDINGS: ClassVar = [
        ("ctrl+s", "save", "Save"),
        ("escape", "cancel", "Cancel"),
        ("?", "help", "Help"),
    ]

    def __init__(self, title: str = "Form", **kwargs):
        """
        Initialize form screen.

        Parameters
        ----------
        title : str
            Screen title
        **kwargs
            Additional arguments passed to Screen
        """
        super().__init__(**kwargs)
        self.screen_title = title

    def compose(self) -> ComposeResult:
        """Compose the form layout."""
        yield Header()

        with Container(id="form-container"):
            yield Label(self.screen_title, classes="form-title")

            # Form fields (subclass provides these)
            with Vertical(id="form-fields"):
                yield from self.get_form_fields()

            # Error display
            yield Static("", id="form-error", classes="form-error")

            # Buttons
            with Horizontal(id="form-buttons"):
                yield Button("Save (Ctrl+S)", id="save-btn", variant="primary")
                yield Button("Cancel (Esc)", id="cancel-btn", variant="default")

        yield Footer()

    @abstractmethod
    def get_form_fields(self) -> ComposeResult:
        """
        Get form field widgets.

        Yields
        ------
        Widget
            Form field widgets (typically FormField instances)
        """

    @abstractmethod
    def validate_form(self) -> dict[str, str]:
        """
        Validate form data.

        Returns
        -------
        dict[str, str]
            Dictionary mapping field names to error messages.
            Empty dict if validation passes.
        """

    @abstractmethod
    def on_save(self, data: dict) -> None:
        """
        Handle save action.

        Parameters
        ----------
        data : dict
            Form data (field_name -> value)
        """

    def action_save(self) -> None:
        """Handle save action with validation."""
        errors = self.validate_form()

        if errors:
            # Show errors
            error_static = self.query_one("#form-error", Static)
            error_messages = "\n".join(f"  • {msg}" for msg in errors.values())
            error_static.update(f"Validation errors:\n{error_messages}")
            error_static.add_class("visible")
        else:
            # Clear errors and save
            error_static = self.query_one("#form-error", Static)
            error_static.update("")
            error_static.remove_class("visible")

            # Collect form data and save
            data = self.collect_form_data()
            self.on_save(data)

    @on(Button.Pressed, "#save-btn")
    def on_save_button(self) -> None:
        """Handle save button press."""
        self.action_save()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_button(self) -> None:
        """Handle cancel button press."""
        self.action_cancel()

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.app.pop_screen()

    def action_help(self) -> None:
        """Show help screen."""
        self.app.action_help()

    def collect_form_data(self) -> dict:
        """
        Collect data from all form fields.

        Returns
        -------
        dict
            Field name to value mapping
        """
        # Default implementation - override if needed
        return {}


class ConfirmDialog(ModalScreen[bool]):
    """
    Modal confirmation dialog.

    Displays a message and Yes/No buttons. Returns True if user confirms,
    False if they cancel.

    Parameters
    ----------
    message : str
        Confirmation message to display
    title : str
        Dialog title
    """

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #message {
        margin-bottom: 1;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, title: str = "Confirm", **kwargs):
        """Initialize confirmation dialog."""
        super().__init__(**kwargs)
        self.message = message
        self.title = title

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Vertical(id="dialog"):
            yield Label(self.title, classes="dialog-title")
            yield Static(self.message, id="message")
            with Horizontal(id="buttons"):
                yield Button("Yes", id="yes-btn", variant="error")
                yield Button("No", id="no-btn", variant="primary")

    @on(Button.Pressed, "#yes-btn")
    def on_yes(self) -> None:
        """Handle yes button."""
        self.dismiss(True)

    @on(Button.Pressed, "#no-btn")
    def on_no(self) -> None:
        """Handle no button."""
        self.dismiss(False)
