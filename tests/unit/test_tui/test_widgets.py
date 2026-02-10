"""Tests for custom TUI widgets."""

from textual.events import Key

from nexusLIMS.tui.common.widgets import (
    AutocompleteInput,
    FormField,
    NumpadInput,
    ValidatedInput,
)


class TestNumpadInput:
    """Tests for NumpadInput widget."""

    async def test_numpad_minus_key(self):
        """Test that numpad subtract key inserts minus sign (lines 51-53)."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NumpadInput(id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(NumpadInput)

            # Create a Key event for numpad subtract
            event = Key("subtract", "subtract")

            # Send the event
            input_widget.on_key(event)
            await pilot.pause(0.05)

            # Verify minus was inserted
            assert input_widget.value == "-"

    async def test_numpad_numeric_keys(self):
        """Test that numpad numeric keys work (lines 51-53)."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield NumpadInput(id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(NumpadInput)

            # Test numpad_5
            event = Key("numpad_5", "numpad_5")
            input_widget.on_key(event)
            await pilot.pause(0.05)

            assert input_widget.value == "5"


class TestValidatedInput:
    """Tests for ValidatedInput widget."""

    async def test_no_validator_returns_valid(self):
        """Test that input without validator is always valid (lines 111-113)."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield ValidatedInput(id="test-input", validator=None)

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(ValidatedInput)

            # Validate any value
            is_valid, error = input_widget.validate_value("anything")

            # Should always be valid with no validator
            assert is_valid is True
            assert error == ""

    async def test_watch_value_invalid(self):
        """Test that invalid value adds error class (lines 117-125)."""
        from textual.app import App

        def always_invalid(value):
            return (False, "Always invalid")

        class TestApp(App):
            def compose(self):
                yield ValidatedInput(validator=always_invalid, id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(ValidatedInput)

            # Directly call _watch_value to test the validation logic
            input_widget._watch_value("test")
            await pilot.pause(0.05)

            # Should have error class
            assert "error" in input_widget.classes
            assert input_widget.is_valid is False
            assert input_widget.error_message == "Always invalid"

    async def test_watch_value_valid(self):
        """Test that valid value removes error class (lines 117-125)."""
        from textual.app import App

        def length_validator(value):
            if len(value) > 3:
                return (True, "")
            return (False, "Too short")

        class TestApp(App):
            def compose(self):
                yield ValidatedInput(validator=length_validator, id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(ValidatedInput)

            # First call _watch_value with invalid value
            input_widget._watch_value("ab")
            await pilot.pause(0.05)
            assert "error" in input_widget.classes

            # Then call _watch_value with valid value
            input_widget._watch_value("abcd")
            await pilot.pause(0.05)

            # Error class should be removed
            assert "error" not in input_widget.classes
            assert input_widget.is_valid is True

    async def test_is_valid_property(self):
        """Test is_valid property (line 130)."""
        from textual.app import App

        def never_valid(value):
            return (False, "Never valid")

        class TestApp(App):
            def compose(self):
                yield ValidatedInput(validator=never_valid, id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(ValidatedInput)
            input_widget._watch_value("test")
            await pilot.pause(0.05)

            # Test the property
            assert input_widget.is_valid is False

    async def test_error_message_property(self):
        """Test error_message property (line 135)."""
        from textual.app import App

        def custom_error(value):
            return (False, "Custom error message")

        class TestApp(App):
            def compose(self):
                yield ValidatedInput(validator=custom_error, id="test-input")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(ValidatedInput)
            input_widget._watch_value("test")
            await pilot.pause(0.05)

            # Test the property
            assert input_widget.error_message == "Custom error message"


class TestAutocompleteInput:
    """Tests for AutocompleteInput widget."""

    async def test_set_suggestions(self):
        """Test updating suggestions dynamically (lines 186-187)."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield AutocompleteInput(
                    suggestions=["apple", "banana"], id="test-input"
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            input_widget = app.query_one(AutocompleteInput)

            # Update suggestions
            input_widget.set_suggestions(["cherry", "date"])
            await pilot.pause(0.05)

            # Verify suggestions were updated
            assert input_widget._suggestions == ["cherry", "date"]
            assert input_widget.suggester is not None

    async def test_get_suggestion_no_value(self):
        """Test suggester returns None for empty value (line 201)."""
        from nexusLIMS.tui.common.widgets import _ListSuggester

        suggester = _ListSuggester(["apple", "banana", "cherry"])

        # Empty value should return None
        result = await suggester.get_suggestion("")

        assert result is None


class TestFormField:
    """Tests for FormField widget."""

    async def test_required_field_label(self):
        """Test that required field adds asterisk to label (lines 289-295)."""
        from textual.app import App
        from textual.widgets import Input, Label

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input"),
                    required=True,
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            # Find the label
            label = app.query_one(Label)

            # Should have asterisk for required field
            # Check the label's render output
            assert "Test Field *" in str(label.render())

    async def test_help_text_displayed(self):
        """Test that help text is displayed (lines 289-295)."""
        from textual.app import App
        from textual.widgets import Input

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input"),
                    help_text="This is help text",
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            # Find help text static
            help_static = app.query(".field-help").first()

            assert help_static is not None
            assert "This is help text" in str(help_static.render())

    async def test_value_property_getter(self):
        """Test value property getter (line 303)."""
        from textual.app import App
        from textual.widgets import Input

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input", value="initial"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # Test value getter
            assert field.value == "initial"

    async def test_value_property_setter(self):
        """Test value property setter (line 308)."""
        from textual.app import App
        from textual.widgets import Input

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # Test value setter
            field.value = "new value"
            await pilot.pause(0.05)

            assert field.input_widget.value == "new value"

    async def test_is_valid_with_validated_input(self):
        """Test is_valid property with ValidatedInput (lines 313-315)."""
        from textual.app import App

        def always_valid(value):
            return (True, "")

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    ValidatedInput(validator=always_valid, id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)
            # Directly call _watch_value to trigger validation
            field.input_widget._watch_value("test")
            await pilot.pause(0.05)

            # Test is_valid property
            assert field.is_valid is True

    async def test_is_valid_with_regular_input(self):
        """Test is_valid returns True for non-validated input (lines 313-315)."""
        from textual.app import App
        from textual.widgets import Input

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # Regular Input should always return True
            assert field.is_valid is True

    async def test_error_message_with_validated_input(self):
        """Test error_message property with ValidatedInput (lines 320-322)."""
        from textual.app import App

        def custom_validator(value):
            return (False, "Test error")

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    ValidatedInput(validator=custom_validator, id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)
            # Directly call _watch_value to trigger validation
            field.input_widget._watch_value("test")
            await pilot.pause(0.05)

            # Test error_message property
            assert field.error_message == "Test error"

    async def test_error_message_with_regular_input(self):
        """Test error_message returns empty string for regular input (lines 320-322)."""
        from textual.app import App
        from textual.widgets import Input

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    Input(id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # Regular Input should return empty string
            assert field.error_message == ""

    async def test_on_input_changed_with_valid_input(self):
        """Test on_input_changed updates error display for valid input."""
        from textual.app import App
        from textual.widgets import Static

        def length_validator(value):
            if len(value) >= 3:
                return (True, "")
            return (False, "Too short")

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    ValidatedInput(validator=length_validator, id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # First trigger with invalid value
            field.input_widget._watch_value("ab")
            field.input_widget.post_message(
                field.input_widget.Changed(field.input_widget, "ab")
            )
            await pilot.pause(0.1)

            # Check error is shown
            error_static = field.query_one("#test-input-error", Static)
            assert "visible" in error_static.classes

            # Then trigger with valid value to test lines 290-292
            field.input_widget._watch_value("abc")
            field.input_widget.post_message(
                field.input_widget.Changed(field.input_widget, "abc")
            )
            await pilot.pause(0.1)

            # Error should be cleared
            error_static = field.query_one("#test-input-error", Static)
            assert "visible" not in error_static.classes
            # Check that the error message was cleared
            rendered = str(error_static.render())
            assert rendered == "" or "Too short" not in rendered

    async def test_on_input_changed_with_invalid_input(self):
        """Test on_input_changed updates error display for invalid input."""
        from textual.app import App
        from textual.widgets import Static

        def always_invalid(value):
            return (False, "Error message")

        class TestApp(App):
            def compose(self):
                yield FormField(
                    "Test Field",
                    ValidatedInput(validator=always_invalid, id="test-input"),
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            field = app.query_one(FormField)

            # Trigger with invalid value to test lines 293-295
            field.input_widget._watch_value("test")
            field.input_widget.post_message(
                field.input_widget.Changed(field.input_widget, "test")
            )
            await pilot.pause(0.1)

            # Error should be shown
            error_static = field.query_one("#test-input-error", Static)
            assert "visible" in error_static.classes
            assert "Error message" in str(error_static.render())
