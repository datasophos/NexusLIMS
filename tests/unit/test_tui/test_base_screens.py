"""Tests for base screen classes."""

from textual.widgets import Button, DataTable, Input

from nexusLIMS.tui.common.base_screens import (
    BaseFormScreen,
    BaseListScreen,
    ConfirmDialog,
)


class TestBaseListScreen:
    """Tests for BaseListScreen functionality."""

    async def test_sort_by_column_toggle(self):
        """Test clicking column header to sort and toggle sort direction."""

        # Create a concrete implementation of BaseListScreen
        class TestListScreen(BaseListScreen):
            def get_columns(self):
                return ["Name", "Value"]

            def get_data(self):
                return [
                    {"Name": "Zebra", "Value": "10"},
                    {"Name": "Apple", "Value": "20"},
                    {"Name": "Banana", "Value": "5"},
                ]

            def on_row_selected(self, row_key, row_data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestListScreen())

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            table = screen.query_one(DataTable)

            # Initially, data should be unsorted
            rows = list(table.rows)
            assert len(rows) == 3

            # Simulate clicking on "Name" column header by triggering the event handler
            from textual.widgets import DataTable as DT

            # Create a HeaderSelected event for column 0
            column_key = table.ordered_columns[0]
            event = DT.HeaderSelected(
                table, column_index=0, column_key=column_key, label="Name"
            )
            screen.on_header_selected(event)
            await pilot.pause(0.1)

            # Verify sort column was set
            assert screen._sort_column == "Name"
            assert screen._sort_reverse is False

            # Click same header again to reverse sort
            event = DT.HeaderSelected(
                table, column_index=0, column_key=column_key, label="Name"
            )
            screen.on_header_selected(event)
            await pilot.pause(0.1)

            # Verify sort direction reversed (line 117-122)
            assert screen._sort_column == "Name"
            assert screen._sort_reverse is True

    async def test_cycle_sort_empty_columns(self):
        """Test action_cycle_sort early return when screen has no columns."""

        class EmptyListScreen(BaseListScreen):
            def get_columns(self):
                return []

            def get_data(self):
                return []

            def on_row_selected(self, row_key, row_data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(EmptyListScreen())

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            # _sort_column should remain None after pressing 's' with no columns
            assert screen._sort_column is None
            await pilot.press("s")
            await pilot.pause(0.05)
            assert screen._sort_column is None

    async def test_filter_rows_empty_result(self):
        """Test filtering that results in no matches (line 97)."""

        class TestListScreen(BaseListScreen):
            def get_columns(self):
                return ["Name", "Value"]

            def get_data(self):
                return [
                    {"Name": "Apple", "Value": "10"},
                    {"Name": "Banana", "Value": "20"},
                ]

            def on_row_selected(self, row_key, row_data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestListScreen())

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            filter_input = screen.query_one("#filter-input", Input)

            # Set filter that matches nothing
            filter_input.value = "NonexistentValue"
            await pilot.pause(0.1)

            # Verify empty filtered_data list is handled (line 97)
            table = screen.query_one(DataTable)
            assert table.row_count == 0

    async def test_action_quit(self):
        """Test quit action exits the app (line 211)."""

        class TestListScreen(BaseListScreen):
            def get_columns(self):
                return ["Name"]

            def get_data(self):
                return [{"Name": "Test"}]

            def on_row_selected(self, row_key, row_data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestListScreen())

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen

            # Call action_quit
            screen.action_quit()
            await pilot.pause(0.1)

            # App should be exiting (return_code will be set)
            assert app.return_code is not None


class TestBaseFormScreen:
    """Tests for BaseFormScreen functionality."""

    async def test_on_save_button(self):
        """Test clicking save button triggers action_save (line 331)."""

        class TestFormScreen(BaseFormScreen):
            def get_form_fields(self):
                yield Input(id="test-field")

            def validate_form(self):
                return {}  # No errors

            def on_save(self, data):
                # Mark that save was called
                self.save_called = True

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestFormScreen(title="Test Form"))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            screen.save_called = False

            # Click save button
            save_btn = screen.query_one("#save-btn", Button)
            await pilot.click(Button, offset=(0, 0))
            await pilot.pause(0.1)

            # Verify on_save was called via action_save
            assert screen.save_called

    async def test_on_cancel_button(self):
        """Test clicking cancel button calls action_cancel (line 336)."""

        class TestFormScreen(BaseFormScreen):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.action_cancel_called = False

            def get_form_fields(self):
                yield Input(id="test-field")

            def validate_form(self):
                return {}

            def on_save(self, data):
                pass

            def action_cancel(self):
                # Track that action_cancel was called
                self.action_cancel_called = True
                super().action_cancel()

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestFormScreen(title="Test Form"))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            # Get the form screen
            form_screen = app.screen

            # Simulate clicking the cancel button by calling on_cancel_button directly
            form_screen.on_cancel_button()
            await pilot.pause(0.1)

            # Verify action_cancel was called (line 336)
            assert form_screen.action_cancel_called

            # Verify we're no longer on the form screen (it was popped)
            assert app.screen is not form_screen

    async def test_action_help(self):
        """Test help action on form screen (line 344)."""

        class TestFormScreen(BaseFormScreen):
            def get_form_fields(self):
                yield Input(id="test-field")

            def validate_form(self):
                return {}

            def on_save(self, data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp, HelpScreen

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestFormScreen(title="Test Form"))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen

            # Call action_help
            screen.action_help()
            await pilot.pause(0.1)

            # Verify help screen was pushed
            assert isinstance(app.screen, HelpScreen)

    async def test_collect_form_data_default(self):
        """Test default collect_form_data returns empty dict (line 356)."""

        class TestFormScreen(BaseFormScreen):
            def get_form_fields(self):
                yield Input(id="test-field")

            def validate_form(self):
                return {}

            def on_save(self, data):
                pass

        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(TestFormScreen(title="Test Form"))

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            screen = app.screen

            # Call default collect_form_data (not overridden)
            data = screen.collect_form_data()

            # Should return empty dict by default
            assert data == {}


class TestConfirmDialog:
    """Tests for ConfirmDialog."""

    async def test_on_no_button(self):
        """Test clicking No button dismisses with False (line 425)."""
        from nexusLIMS.tui.common.base_app import BaseNexusApp

        class TestApp(BaseNexusApp):
            pass

        app = TestApp()

        result = None

        def handle_result(confirmed: bool):
            nonlocal result
            result = confirmed

        async with app.run_test() as pilot:
            await pilot.pause(0.1)

            # Push confirm dialog
            dialog = ConfirmDialog("Test message", title="Confirm")
            app.push_screen(dialog, handle_result)
            await pilot.pause(0.1)

            # Call on_no directly to test line 425
            dialog.on_no()
            await pilot.pause(0.1)

            # Verify result is False
            assert result is False
