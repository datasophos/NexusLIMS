"""
Reusable widgets for NexusLIMS TUI applications.

Provides form inputs, validation feedback, and other common UI components.
"""

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.suggester import Suggester
from textual.widgets import Input, Label, Static


class ValidatedInput(Input):
    """
    Input widget with validation support.

    Displays validation errors below the input field and provides
    custom messages for invalid states.

    Attributes
    ----------
    validator : Callable | None
        Validation function that takes the input value and returns
        (is_valid, error_message) tuple
    """

    def __init__(
        self,
        *args,
        validator: Callable | None = None,
        **kwargs,
    ):
        """
        Initialize ValidatedInput.

        Parameters
        ----------
        validator : Callable | None
            Validation function: (value: str) -> (bool, str)
        *args
            Positional arguments passed to Input
        **kwargs
            Keyword arguments passed to Input
        """
        self._validator = validator
        self._is_valid = True
        self._error_message = ""
        # Disable Textual's built-in validation to avoid conflicts
        kwargs["validators"] = None
        kwargs["validate_on"] = []
        super().__init__(*args, **kwargs)

    def validate_value(self, value: str) -> tuple[bool, str]:
        """
        Validate the input value.

        Parameters
        ----------
        value : str
            Value to validate

        Returns
        -------
        tuple[bool, str]
            (is_valid, error_message)
        """
        if self._validator is None:
            return True, ""
        return self._validator(value)

    def _watch_value(self, value: str) -> None:
        """Watch for value changes and validate."""
        is_valid, error = self.validate_value(value)
        self._is_valid = is_valid
        self._error_message = error

        # Update visual state
        if not is_valid:
            self.add_class("error")
        else:
            self.remove_class("error")

    @property
    def is_valid(self) -> bool:
        """Check if current value is valid."""
        return self._is_valid

    @property
    def error_message(self) -> str:
        """Get current error message."""
        return self._error_message


class AutocompleteInput(Input):
    """
    Input widget with autocomplete suggestions.

    Uses Textual's built-in Suggester for dropdown suggestions.

    Attributes
    ----------
    suggestions : list[str]
        List of suggestion strings
    """

    def __init__(
        self,
        suggestions: list[str] | None = None,
        *args,
        **kwargs,
    ):
        """
        Initialize AutocompleteInput.

        Parameters
        ----------
        suggestions : list[str] | None
            List of autocomplete suggestions
        *args
            Positional arguments passed to Input
        **kwargs
            Keyword arguments passed to Input
        """
        self._suggestions = suggestions or []

        # Create custom suggester
        if self._suggestions:
            suggester = _ListSuggester(self._suggestions)
            kwargs["suggester"] = suggester

        super().__init__(*args, **kwargs)

    def set_suggestions(self, suggestions: list[str]) -> None:
        """
        Update autocomplete suggestions.

        Parameters
        ----------
        suggestions : list[str]
            New list of suggestions
        """
        self._suggestions = suggestions
        self.suggester = _ListSuggester(suggestions) if suggestions else None


class _ListSuggester(Suggester):
    """Internal suggester for AutocompleteInput."""

    def __init__(self, suggestions: list[str]):
        """Initialize with suggestion list."""
        super().__init__()
        self.suggestions = suggestions

    async def get_suggestion(self, value: str) -> str | None:
        """Get suggestion for current input value."""
        if not value:
            return None

        value_lower = value.lower()
        for suggestion in self.suggestions:
            if suggestion.lower().startswith(value_lower):
                return suggestion

        return None


class FormField(Vertical):
    """
    Container for a labeled form field with validation error display.

    Provides consistent layout for label + input + error message.

    Attributes
    ----------
    label_text : str
        Field label text
    input_widget : Input
        Input widget (ValidatedInput, AutocompleteInput, etc.)
    required : bool
        Whether field is required
    """

    class Changed(Message):
        """Message emitted when field value changes."""

        def __init__(self, field: "FormField", value: str) -> None:
            """Initialize message with field and value."""
            super().__init__()
            self.field = field
            self.value = value

    def __init__(
        self,
        label_text: str,
        input_widget: Input,
        *,
        required: bool = False,
        help_text: str | None = None,
        **kwargs,
    ):
        """
        Initialize FormField.

        Parameters
        ----------
        label_text : str
            Label text for the field
        input_widget : Input
            Input widget to use
        required : bool
            Whether field is required
        help_text : str | None
            Optional help text shown below label
        **kwargs
            Additional arguments passed to Vertical
        """
        super().__init__(**kwargs)
        self.label_text = label_text
        self.input_widget = input_widget
        self.required = required
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        """Compose the field layout."""
        # Label with required indicator
        label = self.label_text
        if self.required:
            label += " *"

        yield Label(label, classes="field-label")

        if self.help_text:
            yield Static(self.help_text, classes="field-help")

        yield self.input_widget

        # Error message placeholder
        yield Static("", classes="field-error", id=f"{self.input_widget.id}-error")

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Forward input changes and update error display."""
        # Update error display if input is ValidatedInput
        if isinstance(self.input_widget, ValidatedInput):
            error_static = self.query_one(f"#{self.input_widget.id}-error", Static)
            if self.input_widget.is_valid:
                error_static.update("")
                error_static.remove_class("visible")
            else:
                error_static.update(self.input_widget.error_message)
                error_static.add_class("visible")

        # Emit changed message
        self.post_message(self.Changed(self, event.value))

    @property
    def value(self) -> str:
        """Get current field value."""
        return self.input_widget.value

    @value.setter
    def value(self, value: str) -> None:
        """Set field value."""
        self.input_widget.value = value

    @property
    def is_valid(self) -> bool:
        """Check if field value is valid."""
        if isinstance(self.input_widget, ValidatedInput):
            return self.input_widget.is_valid
        return True

    @property
    def error_message(self) -> str:
        """Get current error message."""
        if isinstance(self.input_widget, ValidatedInput):
            return self.input_widget.error_message
        return ""
