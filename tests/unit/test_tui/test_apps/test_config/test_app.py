"""Tests for ConfiguratorApp initialization, mounting, and env_path wiring."""

from pathlib import Path

import pytest

from nexusLIMS.tui.apps.config.app import ConfiguratorApp
from nexusLIMS.tui.apps.config.screens import ConfigScreen
from nexusLIMS.tui.common.base_app import HelpScreen


class TestConfiguratorApp:
    """Tests for ConfiguratorApp class."""

    async def test_app_initializes_default_env_path(self):
        """App initializes with default env_path of '.env'."""
        app = ConfiguratorApp()
        assert app.env_path == Path(".env")

    async def test_app_accepts_custom_env_path(self, tmp_path):
        """App accepts and stores a custom env_path."""
        env_file = tmp_path / "custom.env"
        app = ConfiguratorApp(env_path=env_file)
        assert app.env_path == env_file

    async def test_app_accepts_string_env_path(self, tmp_path):
        """App converts a string env_path to Path."""
        env_file = tmp_path / "test.env"
        app = ConfiguratorApp(env_path=str(env_file))
        assert app.env_path == env_file

    async def test_app_get_app_name(self):
        """get_app_name returns expected string."""
        app = ConfiguratorApp()
        assert app.get_app_name() == "NexusLIMS Configurator"

    async def test_app_get_keybindings_includes_save(self):
        """get_keybindings includes ctrl+s save binding."""
        app = ConfiguratorApp()
        bindings = app.get_keybindings()
        keys = [k for k, _ in bindings]
        assert "ctrl+s" in keys

    async def test_app_get_keybindings_includes_escape(self):
        """get_keybindings includes escape binding."""
        app = ConfiguratorApp()
        bindings = app.get_keybindings()
        keys = [k for k, _ in bindings]
        assert "escape" in keys

    async def test_app_does_not_create_db_session(self, tmp_path):
        """App does not create a real database session on mount."""
        from sqlmodel import Session

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            # ConfiguratorApp sets db_session to a falsy sentinel to skip DB
            # creation; it must NOT be an actual sqlmodel Session instance.
            assert not isinstance(app.db_session, Session)

    async def test_app_title_includes_env_path(self, tmp_path):
        """App title includes the env file path."""
        env_file = tmp_path / "test.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert str(env_file) in app.title

    async def test_app_shows_config_screen_on_mount(self, tmp_path):
        """App pushes ConfigScreen on mount."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ConfigScreen)

    async def test_app_runs_without_existing_env_file(self, tmp_path):
        """App starts normally when the env file does not exist."""
        env_file = tmp_path / "nonexistent.env"
        assert not env_file.exists()
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.is_running

    async def test_app_runs_with_existing_env_file(self, tmp_path):
        """App starts normally when an env file exists with values."""
        env_file = tmp_path / "existing.env"
        env_file.write_text(
            "NX_INSTRUMENT_DATA_PATH='/data/instruments'\n"
            "NX_DATA_PATH='/data/nexuslims'\n"
            "NX_DB_PATH='/data/nexuslims.db'\n"
            "NX_CDCS_URL='https://cdcs.example.com'\n"
            "NX_CDCS_TOKEN='test-token'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.is_running

    async def test_action_help_pushes_help_screen(self, tmp_path):
        """Pressing '?' pushes a HelpScreen with app name and keybindings."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("?")
            await pilot.pause(0.1)
            assert isinstance(app.screen, HelpScreen)

    async def test_app_cancel_via_escape(self, tmp_path):
        """Pressing Escape exits the app without saving."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause(0.1)
            # App should exit; env file should not be created
            assert not env_file.exists()


pytestmark = pytest.mark.unit
