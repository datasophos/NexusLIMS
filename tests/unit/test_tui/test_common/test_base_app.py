"""Tests for BaseNexusApp theme system."""

from textual.app import App
from textual.widgets import Markdown

from nexusLIMS.tui.common.base_app import BaseNexusApp, HelpScreen


class TestThemeToggle:
    """Tests for theme toggling functionality."""

    def test_default_theme_is_dark(self):
        """Test that the default theme is dark mode."""
        app = BaseNexusApp()
        assert app.current_theme.name == "textual-dark"
        assert app.current_theme.dark is True

    def test_toggle_theme_switches_mode(self):
        """Test that toggle_theme switches between dark and light modes."""
        app = BaseNexusApp()

        # Start in dark mode
        assert app.current_theme.name == "textual-dark"

        # Toggle to light mode
        app.action_toggle_theme()
        assert app.current_theme.name == "textual-light"

        # Toggle back to dark mode
        app.action_toggle_theme()
        assert app.current_theme.name == "textual-dark"

    def test_multiple_toggles(self):
        """Test multiple theme toggles."""
        app = BaseNexusApp()

        # Perform multiple toggles
        for _ in range(5):
            initial_theme = app.current_theme.name
            app.action_toggle_theme()
            assert app.current_theme.name != initial_theme


class TestBaseAppInitialization:
    """Tests for BaseNexusApp initialization."""

    def test_app_inherits_from_textual_app(self):
        """Test that BaseNexusApp inherits from Textual's App."""
        app = BaseNexusApp()
        assert isinstance(app, App)

    def test_db_session_is_none_before_mount(self):
        """Test that db_session is None before mounting."""
        app = BaseNexusApp()
        assert app.db_session is None


class TestHelpScreen:
    """Tests for HelpScreen compose logic."""

    async def test_description_included_in_markdown(self):
        """Description text appears in the rendered Markdown when provided."""

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(
                    HelpScreen(
                        app_name="Test App",
                        keybindings=[("ctrl+s", "Save")],
                        description="This is the app description.",
                    )
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            md = app.screen.query_one("#help-content", Markdown)
            assert "This is the app description." in md._markdown

    async def test_no_description_omitted_from_markdown(self):
        """No description text is added when description is empty."""

        class TestApp(BaseNexusApp):
            def on_mount(self):
                self.push_screen(
                    HelpScreen(
                        app_name="Test App",
                        keybindings=[("ctrl+s", "Save")],
                    )
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.1)
            md = app.screen.query_one("#help-content", Markdown)
            # Only the title and keybindings section — no extra prose
            assert "## Keybindings" in md._markdown
            assert "This is the app description." not in md._markdown
