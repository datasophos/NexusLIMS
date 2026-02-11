"""Tests for ConfigScreen tabs, pre-population, save flow, and NEMO management."""

from pathlib import Path

import pytest
from textual.widgets import Button, Input, Switch, TabbedContent, TextArea

from nexusLIMS.tui.apps.config.app import ConfiguratorApp
from nexusLIMS.tui.apps.config.screens import ConfigScreen

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def full_env_file(tmp_path) -> Path:
    """Return a Path to an env file pre-populated with all sections."""
    env_file = tmp_path / "full.env"
    env_file.write_text(
        "NX_INSTRUMENT_DATA_PATH='/data/instruments'\n"
        "NX_DATA_PATH='/data/nexuslims'\n"
        "NX_DB_PATH='/data/nexuslims.db'\n"
        "NX_LOG_PATH='/data/logs'\n"
        "NX_RECORDS_PATH='/data/records'\n"
        "NX_CDCS_URL='https://cdcs.example.com'\n"
        "NX_CDCS_TOKEN='cdcs-secret-token'\n"
        "NX_FILE_STRATEGY='inclusive'\n"
        "NX_EXPORT_STRATEGY='best_effort'\n"
        "NX_FILE_DELAY_DAYS='3.5'\n"
        "NX_CLUSTERING_SENSITIVITY='2.0'\n"
        'NX_IGNORE_PATTERNS=\'["*.mib", "*.db"]\'\n'
        "NX_NEMO_ADDRESS_1='https://nemo1.example.com/api/'\n"
        "NX_NEMO_TOKEN_1='nemo-token-1'\n"
        "NX_NEMO_TZ_1='America/New_York'\n"
        "NX_NEMO_ADDRESS_2='https://nemo2.example.com/api/'\n"
        "NX_NEMO_TOKEN_2='nemo-token-2'\n"
        "NX_ELABFTW_URL='https://elabftw.example.com'\n"
        "NX_ELABFTW_API_KEY='elabftw-api-key'\n"
        "NX_ELABFTW_EXPERIMENT_CATEGORY='5'\n"
        "NX_EMAIL_SMTP_HOST='smtp.example.com'\n"
        "NX_EMAIL_SMTP_PORT='465'\n"
        "NX_EMAIL_SENDER='noreply@example.com'\n"
        "NX_EMAIL_RECIPIENTS='admin@example.com'\n"
        "NX_EMAIL_USE_TLS='true'\n"
        "NX_DISABLE_SSL_VERIFY='false'\n"
    )
    return env_file


# --------------------------------------------------------------------------- #
# TestConfigScreen pre-population                                              #
# --------------------------------------------------------------------------- #


class TestConfigScreenPrePopulation:
    """Tests that the ConfigScreen pre-populates form fields from an env file."""

    async def test_core_paths_pre_populated(self, full_env_file):
        """Core path fields are pre-populated from the env file."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            assert (
                screen.query_one("#nx-instrument-data-path", Input).value
                == "/data/instruments"
            )
            assert screen.query_one("#nx-data-path", Input).value == "/data/nexuslims"
            assert screen.query_one("#nx-db-path", Input).value == "/data/nexuslims.db"
            assert screen.query_one("#nx-log-path", Input).value == "/data/logs"
            assert screen.query_one("#nx-records-path", Input).value == "/data/records"

    async def test_cdcs_pre_populated(self, full_env_file):
        """CDCS fields are pre-populated from the env file."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert (
                screen.query_one("#nx-cdcs-url", Input).value
                == "https://cdcs.example.com"
            )
            assert (
                screen.query_one("#nx-cdcs-token", Input).value == "cdcs-secret-token"
            )

    async def test_file_processing_pre_populated(self, full_env_file):
        """File processing fields are pre-populated from the env file."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert screen.query_one("#nx-file-delay-days", Input).value == "3.5"
            assert screen.query_one("#nx-clustering-sensitivity", Input).value == "2.0"

    async def test_nemo_harvesters_parsed(self, full_env_file):
        """NEMO harvesters are parsed and stored from the env file."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)
            assert len(screen._nemo_harvesters) == 2
            assert (
                screen._nemo_harvesters[1]["address"]
                == "https://nemo1.example.com/api/"
            )
            assert screen._nemo_harvesters[1]["tz"] == "America/New_York"
            assert (
                screen._nemo_harvesters[2]["address"]
                == "https://nemo2.example.com/api/"
            )

    async def test_elabftw_enabled_when_configured(self, full_env_file):
        """The eLabFTW section is enabled when env vars are present."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert screen.query_one("#elabftw-enabled", Switch).value is True

    async def test_email_enabled_when_configured(self, full_env_file):
        """Email section is enabled when env vars are present."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert screen.query_one("#email-enabled", Switch).value is True

    async def test_empty_env_all_fields_blank(self, tmp_path):
        """With no env file, all fields start empty or at defaults."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert screen.query_one("#nx-cdcs-url", Input).value == ""
            assert screen.query_one("#nx-cdcs-token", Input).value == ""
            assert screen.query_one("#elabftw-enabled", Switch).value is False
            assert screen.query_one("#email-enabled", Switch).value is False


# --------------------------------------------------------------------------- #
# TestConfigScreenSaveFlow                                                     #
# --------------------------------------------------------------------------- #


class TestConfigScreenSaveFlow:
    """Tests for the save workflow (validation and .env writing)."""

    async def test_save_with_required_fields_writes_env(self, tmp_path):
        """Save writes a .env file when all required fields are filled."""
        env_file = tmp_path / "output.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Fill required fields
            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "mytoken"
            await pilot.pause(0.05)

            # Trigger save
            await pilot.press("ctrl+s")
            await pilot.pause(0.2)

        # After app exits, verify the file was written
        assert env_file.exists()
        content = env_file.read_text()
        assert "NX_CDCS_URL" in content
        assert "NX_CDCS_TOKEN" in content

    async def test_save_blocked_when_cdcs_url_missing(self, tmp_path):
        """Save shows error when NX_CDCS_URL is missing."""
        env_file = tmp_path / "output.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Fill only some required fields (missing CDCS URL)
            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            await pilot.pause(0.05)

            await pilot.press("ctrl+s")
            await pilot.pause(0.1)

            # Save should be blocked — file should not exist
            assert not env_file.exists()
            # App should still be running
            assert app.is_running

    async def test_validate_all_returns_errors_for_empty_form(self, tmp_path):
        """_validate_all reports errors when required fields are empty."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            errors = screen._validate_all()
            # Expect at least errors for the 5 required fields
            assert len(errors) >= 3  # NX_INSTRUMENT_DATA_PATH, NX_DATA_PATH, NX_DB_PATH

    async def test_validate_all_passes_with_required_fields(self, tmp_path):
        """_validate_all returns no errors when all required fields are filled."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"
            await pilot.pause(0.05)

            errors = screen._validate_all()
            assert errors == []

    async def test_build_config_dict_includes_nemo_harvesters(self, tmp_path):
        """_build_config_dict includes NEMO harvesters when present in DOM."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='secret'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Set required fields so _build_config_dict can run
            screen.query_one("#nx-instrument-data-path", Input).value = "/data"
            screen.query_one("#nx-data-path", Input).value = "/data"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"

            config = screen._build_config_dict()
            assert "nemo_harvesters" in config
            assert "1" in config["nemo_harvesters"]
            assert (
                config["nemo_harvesters"]["1"]["address"]
                == "https://nemo.example.com/api/"
            )

    async def test_ignore_patterns_roundtrip(self, tmp_path):
        """NX_IGNORE_PATTERNS is read, displayed, and saved correctly."""
        env_file = tmp_path / "env.env"
        env_file.write_text('NX_IGNORE_PATTERNS=\'["*.mib", "*.db"]\'\n')

        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            patterns_val = screen.query_one("#nx-ignore-patterns", Input).value
            # Should show comma-separated display
            assert "*.mib" in patterns_val
            assert "*.db" in patterns_val

    async def test_email_config_in_dict_when_enabled(self, tmp_path):
        """Email config appears in config_dict when email is enabled."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Enable email
            screen.query_one("#email-enabled", Switch).value = True
            await pilot.pause(0.05)

            screen.query_one("#nx-email-smtp-host", Input).value = "smtp.example.com"
            screen.query_one("#nx-email-sender", Input).value = "bot@example.com"
            screen.query_one("#nx-email-recipients", Input).value = "admin@example.com"
            screen.query_one("#nx-instrument-data-path", Input).value = "/data"
            screen.query_one("#nx-data-path", Input).value = "/data"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"

            config = screen._build_config_dict()
            assert "email_config" in config
            assert config["email_config"]["smtp_host"] == "smtp.example.com"


# --------------------------------------------------------------------------- #
# TestNemoHarvesterInlineForm                                                  #
# --------------------------------------------------------------------------- #


class TestNemoHarvesterInlineForm:
    """Tests for inline NEMO harvester groups in the NEMO tab."""

    async def test_nemo_groups_pre_populated_from_env(self, tmp_path):
        """NEMO harvester groups are pre-populated from the env file."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo1.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='token1'\n"
            "NX_NEMO_TZ_1='America/Denver'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)
            assert (
                screen.query_one("#nemo-address-1", Input).value
                == "https://nemo1.example.com/api/"
            )
            assert screen.query_one("#nemo-token-1", Input).value == "token1"
            assert screen.query_one("#nemo-tz-1", Input).value == "America/Denver"

    async def test_add_button_mounts_new_group(self, tmp_path):
        """Clicking '+ Add NEMO Harvester' mounts a new inline group."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            groups_before = len(screen.query(".nemo-group"))
            screen._on_nemo_add()
            await pilot.pause(0.1)

            assert len(screen.query(".nemo-group")) == groups_before + 1

    async def test_add_button_creates_empty_fields(self, tmp_path):
        """A newly added NEMO group has empty address and token fields."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            screen._on_nemo_add()
            await pilot.pause(0.1)

            n = screen._next_nemo_index() - 1
            assert screen.query_one(f"#nemo-address-{n}", Input).value == ""
            assert screen.query_one(f"#nemo-token-{n}", Input).value == ""

    async def test_delete_button_removes_group(self, tmp_path):
        """Clicking the Delete button on a NEMO group removes it from the DOM."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            screen._on_nemo_add()
            await pilot.pause(0.1)

            groups_after_add = len(screen.query(".nemo-group"))
            n = screen._next_nemo_index() - 1

            # Switch to the NEMO tab so the delete button is visible/clickable
            screen.query_one(TabbedContent).active = "tab-nemo"
            await pilot.pause(0.1)

            delete_btn = screen.query_one(f"#nemo-delete-{n}", Button)
            await pilot.click(delete_btn)
            await pilot.pause(0.1)

            assert len(screen.query(".nemo-group")) == groups_after_add - 1

    async def test_two_nemo_groups_pre_populated(self, full_env_file):
        """Two NEMO groups are created when env has two NEMO instances."""
        app = ConfiguratorApp(env_path=full_env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            groups = screen.query(".nemo-group")
            assert len(groups) == 2
            assert (
                screen.query_one("#nemo-address-1", Input).value
                == "https://nemo1.example.com/api/"
            )
            assert (
                screen.query_one("#nemo-address-2", Input).value
                == "https://nemo2.example.com/api/"
            )


# --------------------------------------------------------------------------- #
# TestNemoHarvesterManagement (on ConfigScreen)                               #
# --------------------------------------------------------------------------- #


class TestNemoHarvesterManagement:
    """Tests for add/edit/delete NEMO harvesters within ConfigScreen."""

    async def test_add_nemo_harvester_increments_group_count(self, tmp_path):
        """Calling _on_nemo_add adds a new inline NEMO group."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            groups_before = len(screen.query(".nemo-group"))
            screen._on_nemo_add()
            await pilot.pause(0.05)

            assert len(screen.query(".nemo-group")) == groups_before + 1

    async def test_delete_nemo_harvester_removes_from_dom(self, tmp_path):
        """Removing a NEMO group from the DOM reduces group count."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo1.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='t1'\n"
            "NX_NEMO_ADDRESS_2='https://nemo2.example.com/api/'\n"
            "NX_NEMO_TOKEN_2='t2'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)
            assert len(screen.query(".nemo-group")) == 2

            # Switch to the NEMO tab so the delete button is visible/clickable
            screen.query_one(TabbedContent).active = "tab-nemo"
            await pilot.pause(0.1)

            delete_btn = screen.query_one("#nemo-delete-1", Button)
            await pilot.click(delete_btn)
            await pilot.pause(0.1)

            assert len(screen.query(".nemo-group")) == 1

    async def test_edit_nemo_harvester_updates_input_value(self, tmp_path):
        """Setting an input value in a NEMO group is reflected in _build_config_dict."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://old.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='oldtoken'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            screen.query_one(
                "#nemo-address-1", Input
            ).value = "https://new.example.com/api/"
            screen.query_one("#nemo-token-1", Input).value = "newtoken"
            # Set required fields to allow _build_config_dict to run
            screen.query_one("#nx-instrument-data-path", Input).value = "/data"
            screen.query_one("#nx-data-path", Input).value = "/data"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"

            config = screen._build_config_dict()
            assert "nemo_harvesters" in config
            assert (
                config["nemo_harvesters"]["1"]["address"]
                == "https://new.example.com/api/"
            )
            assert config["nemo_harvesters"]["1"]["token"] == "newtoken"

    async def test_add_nemo_then_fill_appears_in_config(self, tmp_path):
        """A newly added NEMO group with filled fields appears in _build_config_dict."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            screen._on_nemo_add()
            await pilot.pause(0.05)

            n = screen._next_nemo_index() - 1
            screen.query_one(
                f"#nemo-address-{n}", Input
            ).value = "https://nemo.example.com/api/"
            screen.query_one(f"#nemo-token-{n}", Input).value = "secret"
            screen.query_one("#nx-instrument-data-path", Input).value = "/data"
            screen.query_one("#nx-data-path", Input).value = "/data"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"

            config = screen._build_config_dict()
            assert "nemo_harvesters" in config
            assert len(config["nemo_harvesters"]) == 1
            assert (
                config["nemo_harvesters"]["1"]["address"]
                == "https://nemo.example.com/api/"
            )


# --------------------------------------------------------------------------- #
# TestConfigScreenSaveWithNEMO                                                #
# --------------------------------------------------------------------------- #


class TestConfigScreenSaveWithNEMO:
    """Integration tests for saving configuration including NEMO harvesters."""

    async def test_full_save_includes_nemo_in_env_file(self, tmp_path):
        """Saved .env includes NEMO harvester variables."""
        env_file = tmp_path / "output.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Set required fields
            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "mytoken"

            # Add a NEMO harvester inline
            screen._on_nemo_add()
            await pilot.pause(0.05)
            n = screen._next_nemo_index() - 1
            screen.query_one(
                f"#nemo-address-{n}", Input
            ).value = "https://nemo.example.com/api/"
            screen.query_one(f"#nemo-token-{n}", Input).value = "nemo-token"

            await pilot.press("ctrl+s")
            await pilot.pause(0.2)

        assert env_file.exists()
        content = env_file.read_text()
        assert "NX_NEMO_ADDRESS_1" in content
        assert "NX_NEMO_TOKEN_1" in content


# --------------------------------------------------------------------------- #
# TestButtonHandlersAndTabNavigation  (task 5)                                #
# --------------------------------------------------------------------------- #


class TestButtonHandlersAndTabNavigation:
    """Tests for save/cancel button handlers and tab navigation actions."""

    async def test_save_button_triggers_action_save(self, tmp_path):
        """Clicking the Save button calls action_save (line 899)."""
        env_file = tmp_path / "out.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Fill required fields so save succeeds
            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"
            await pilot.pause(0.05)

            save_btn = screen.query_one("#config-save-btn", Button)
            await pilot.click(save_btn)
            await pilot.pause(0.2)

        assert env_file.exists()

    async def test_cancel_button_triggers_action_cancel(self, tmp_path):
        """Clicking the Cancel button calls action_cancel (line 903)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            cancel_btn = screen.query_one("#config-cancel-btn", Button)
            await pilot.click(cancel_btn)
            await pilot.pause(0.1)

        # App should exit without writing the env file
        assert not env_file.exists()

    async def test_next_tab_action_advances_tab(self, tmp_path):
        """Pressing '>' moves to the next tab (line 1011)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            tc = screen.query_one(TabbedContent)
            initial_tab = tc.active
            await pilot.press(">")
            await pilot.pause(0.1)

            assert tc.active != initial_tab

    async def test_previous_tab_action_goes_back(self, tmp_path):
        """Pressing '<' moves to the previous tab (line 1015)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            tc = screen.query_one(TabbedContent)
            # Move to second tab first, then go back
            tc.active = "tab-cdcs"
            await pilot.pause(0.1)
            await pilot.press("<")
            await pilot.pause(0.1)

            assert tc.active == "tab-core-paths"


# --------------------------------------------------------------------------- #
# TestToggleSwitchHandlers  (task 6)                                          #
# --------------------------------------------------------------------------- #


class TestToggleSwitchHandlers:
    """Tests for eLabFTW and SSL toggle switch handlers."""

    async def test_elabftw_toggle_enables_fields(self, tmp_path):
        """Enabling the eLabFTW switch enables the eLabFTW input fields (922-931)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            # Enable eLabFTW
            screen.query_one("#elabftw-enabled", Switch).value = True
            await pilot.pause(0.1)

            assert not screen.query_one("#nx-elabftw-url", Input).disabled
            assert not screen.query_one("#nx-elabftw-api-key", Input).disabled

    async def test_elabftw_toggle_disables_fields(self, tmp_path):
        """Disabling the eLabFTW switch disables the eLabFTW input fields (922-931)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        env_file.write_text("NX_ELABFTW_URL='https://elab.example.com'\n")
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            # Disable eLabFTW (was enabled from env)
            screen.query_one("#elabftw-enabled", Switch).value = False
            await pilot.pause(0.1)

            assert screen.query_one("#nx-elabftw-url", Input).disabled
            assert screen.query_one("#nx-elabftw-api-key", Input).disabled

    async def test_ssl_verify_toggle_adds_warning_class(self, tmp_path):
        """Enabling disable-ssl-verify adds 'visible' class to warning (951-953)."""
        from textual.widgets import Static, Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#nx-disable-ssl-verify", Switch).value = True
            await pilot.pause(0.1)

            warning = screen.query_one("#ssl-verify-warning", Static)
            assert warning.has_class("visible")

    async def test_ssl_verify_toggle_removes_warning_class(self, tmp_path):
        """Disabling disable-ssl-verify removes 'visible' from warning (954-955)."""
        from textual.widgets import Static, Switch

        env_file = tmp_path / "empty.env"
        env_file.write_text("NX_DISABLE_SSL_VERIFY='true'\n")
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#nx-disable-ssl-verify", Switch).value = False
            await pilot.pause(0.1)

            warning = screen.query_one("#ssl-verify-warning", Static)
            assert not warning.has_class("visible")


# --------------------------------------------------------------------------- #
# TestActionSaveErrorPaths  (task 7)                                          #
# --------------------------------------------------------------------------- #


class TestActionSaveErrorPaths:
    """Tests for uncovered branches in action_save and action_cancel."""

    async def test_save_with_many_errors_truncates_message(self, tmp_path):
        """More than 2 validation errors adds '(and N more)' to message (967)."""
        from unittest.mock import patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        notify_messages = []

        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Leave all required fields empty → 5 errors
            def _cap_notify(msg, **_kw):
                notify_messages.append(msg)

            with patch.object(app, "notify", side_effect=_cap_notify):
                screen.action_save()

        assert any("and" in m and "more" in m for m in notify_messages)

    async def test_save_exception_shows_error_notification(self, tmp_path):
        """Exception during _write_env_file triggers error notify (981-982)."""
        from unittest.mock import patch

        env_file = tmp_path / "out.env"
        app = ConfiguratorApp(env_path=env_file)
        notify_calls = []

        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#nx-instrument-data-path", Input).value = "/data/instr"
            screen.query_one("#nx-data-path", Input).value = "/data/nx"
            screen.query_one("#nx-db-path", Input).value = "/data/nx.db"
            screen.query_one("#nx-cdcs-url", Input).value = "https://cdcs.example.com"
            screen.query_one("#nx-cdcs-token", Input).value = "tok"

            with (
                patch(
                    "nexusLIMS.tui.apps.config.screens._write_env_file",
                    side_effect=OSError("disk full"),
                ),
                patch.object(
                    app,
                    "notify",
                    side_effect=lambda msg, **_kw: notify_calls.append(msg),
                ),
            ):
                screen.action_save()

        assert any("Failed to save" in m for m in notify_calls)

    async def test_cancel_with_no_changes_exits_immediately(self, tmp_path):
        """Cancel with no changes exits without showing dialog (995-996)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            # No changes made — _has_changes() should be False
            await pilot.press("escape")
            await pilot.pause(0.1)

        assert not env_file.exists()

    async def test_cancel_confirmed_exits_app(self, tmp_path):
        """Confirming unsaved-changes dialog calls app.exit() (1006-1007)."""
        from nexusLIMS.tui.common.base_screens import ConfirmDialog

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            # Make a change so _has_changes() returns True
            screen.query_one(
                "#nx-cdcs-url", Input
            ).value = "https://changed.example.com"
            await pilot.pause(0.05)

            await pilot.press("escape")
            await pilot.pause(0.1)

            # Dialog should be on screen
            assert isinstance(app.screen, ConfirmDialog)

            # Confirm exit
            confirmed = True
            screen._on_cancel_confirmed(confirmed)
            await pilot.pause(0.1)


# --------------------------------------------------------------------------- #
# TestValidationErrorPaths  (task 9)                                          #
# --------------------------------------------------------------------------- #


class TestValidationErrorPaths:
    """Tests for validation helpers when fields contain invalid values."""

    async def test_validate_file_delay_days_invalid(self, tmp_path):
        """Invalid NX_FILE_DELAY_DAYS produces an error (line 1113)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            screen.query_one("#nx-file-delay-days", Input).value = "not-a-number"
            errors = screen._validate_file_processing()
            assert any("NX_FILE_DELAY_DAYS" in e for e in errors)

    async def test_validate_clustering_sensitivity_invalid(self, tmp_path):
        """Invalid NX_CLUSTERING_SENSITIVITY produces an error (line 1119)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            screen.query_one("#nx-clustering-sensitivity", Input).value = "bad"
            errors = screen._validate_file_processing()
            assert any("NX_CLUSTERING_SENSITIVITY" in e for e in errors)

    async def test_validate_elabftw_when_enabled_with_errors(self, tmp_path):
        """_validate_elabftw returns errors when enabled with bad data (1125-1145)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            screen.query_one("#elabftw-enabled", Switch).value = True
            await pilot.pause(0.05)

            # Leave api key empty, set invalid category
            screen.query_one("#nx-elabftw-api-key", Input).value = ""
            screen.query_one("#nx-elabftw-category", Input).value = "not-int"
            errors = screen._validate_elabftw()
            assert any("NX_ELABFTW_API_KEY" in e for e in errors)
            assert any("CATEGORY" in e for e in errors)

    async def test_validate_email_when_enabled_with_errors(self, tmp_path):
        """_validate_email returns errors when enabled with missing fields (1150)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            screen.query_one("#email-enabled", Switch).value = True
            await pilot.pause(0.05)

            # Leave host/sender/recipients empty and set bad port
            screen.query_one("#nx-email-smtp-port", Input).value = "99999"
            errors = screen._validate_email()
            assert any("SMTP Host" in e for e in errors)
            assert any("65535" in e for e in errors)

    async def test_validate_nemo_bad_address(self, tmp_path):
        """Invalid NEMO address produces an error (line 1177)."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='not-a-valid-url'\nNX_NEMO_TOKEN_1='tok'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            errors = screen._validate_nemo()
            assert any("API Address" in e for e in errors)

    async def test_validate_nemo_missing_token(self, tmp_path):
        """Missing NEMO token produces an error (line 1181)."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text("NX_NEMO_ADDRESS_1='https://nemo.example.com/api/'\n")
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            errors = screen._validate_nemo()
            assert any("Token" in e for e in errors)

    async def test_validate_nemo_invalid_timezone(self, tmp_path):
        """Invalid NEMO timezone produces an error (lines 1184-1186)."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='tok'\n"
            "NX_NEMO_TZ_1='Not/A/Valid/TZ'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            errors = screen._validate_nemo()
            assert any("Timezone" in e for e in errors)


# --------------------------------------------------------------------------- #
# TestConfigDictBuilderOptionalBranches  (task 10)                            #
# --------------------------------------------------------------------------- #


class TestConfigDictBuilderOptionalBranches:
    """Tests for optional branches in _build_* config dict helpers."""

    async def test_build_elabftw_config_when_enabled(self, tmp_path):
        """_build_elabftw_config populates all fields when enabled (1252-1267)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#elabftw-enabled", Switch).value = True
            await pilot.pause(0.05)
            screen.query_one(
                "#nx-elabftw-url", Input
            ).value = "https://elab.example.com"
            screen.query_one("#nx-elabftw-api-key", Input).value = "elab-key"
            screen.query_one("#nx-elabftw-category", Input).value = "3"
            screen.query_one("#nx-elabftw-status", Input).value = "1"

            config = screen._build_elabftw_config()
            assert config["NX_ELABFTW_URL"] == "https://elab.example.com"
            assert config["NX_ELABFTW_API_KEY"] == "elab-key"
            assert config["NX_ELABFTW_EXPERIMENT_CATEGORY"] == 3
            assert config["NX_ELABFTW_EXPERIMENT_STATUS"] == 1

    async def test_build_email_config_with_optional_credentials(self, tmp_path):
        """smtp_username and smtp_password appear when filled (1289, 1291)."""
        from textual.widgets import Switch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#email-enabled", Switch).value = True
            await pilot.pause(0.05)
            screen.query_one("#nx-email-smtp-host", Input).value = "smtp.example.com"
            screen.query_one(
                "#nx-email-smtp-username", Input
            ).value = "user@example.com"
            screen.query_one("#nx-email-smtp-password", Input).value = "secret"
            screen.query_one("#nx-email-sender", Input).value = "sender@example.com"
            screen.query_one("#nx-email-recipients", Input).value = "r@example.com"

            config = screen._build_email_config()
            assert config["email_config"]["smtp_username"] == "user@example.com"
            assert config["email_config"]["smtp_password"] == "secret"

    async def test_build_ssl_config_with_cert_fields(self, tmp_path):
        """NX_CERT_BUNDLE_FILE and NX_CERT_BUNDLE appear when filled (1298, 1301)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#nx-cert-bundle-file", Input).value = "/etc/ssl/cert.pem"
            screen.query_one("#nx-cert-bundle", TextArea).text = "-----BEGIN CERT-----"

            config = screen._build_ssl_config()
            assert config["NX_CERT_BUNDLE_FILE"] == "/etc/ssl/cert.pem"
            assert "BEGIN CERT" in config["NX_CERT_BUNDLE"]

    async def test_build_nemo_config_includes_tz_when_set(self, tmp_path):
        """'tz' key is included in harvester dict when timezone is set (1326)."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo.example.com/api/'\n"
            "NX_NEMO_TOKEN_1='tok'\n"
            "NX_NEMO_TZ_1='America/Denver'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            config = screen._build_nemo_config()
            assert config["nemo_harvesters"]["1"]["tz"] == "America/Denver"


# --------------------------------------------------------------------------- #
# TestHasChangesExceptionPath  (lines 988-989)                                #
# --------------------------------------------------------------------------- #


class TestHasChangesExceptionPath:
    """Tests for the exception branch in _has_changes."""

    async def test_has_changes_returns_true_on_build_exception(self, tmp_path):
        """_has_changes returns True when _build_config_dict raises (988-989)."""
        from unittest.mock import patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            with patch.object(
                screen, "_build_config_dict", side_effect=RuntimeError("boom")
            ):
                result = screen._has_changes()

            assert result is True


# --------------------------------------------------------------------------- #
# TestActionCancelNoChanges  (lines 995-996)                                  #
# --------------------------------------------------------------------------- #


class TestActionCancelNoChanges:
    """Tests for the early-exit branch of action_cancel when there are no changes."""

    async def test_action_cancel_calls_exit_when_no_changes(self, tmp_path):
        """action_cancel calls app.exit() when no changes exist."""
        from unittest.mock import patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        exited = []

        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            with (
                patch.object(screen, "_has_changes", return_value=False),
                patch.object(app, "exit", side_effect=lambda: exited.append(True)),
            ):
                screen.action_cancel()

        assert exited, "app.exit() was not called"


# --------------------------------------------------------------------------- #
# TestResolveFieldDetailHelpers  (lines 1019-1060)                            #
# --------------------------------------------------------------------------- #


class TestResolveFieldDetailHelpers:
    """Tests for _resolve_focused_field_detail and its sub-methods."""

    async def test_resolve_input_settings_field(self, tmp_path):
        """Focused Input with a known settings id returns the field name (1035-1044)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            inp = screen.query_one("#nx-data-path", Input)
            name, _detail = screen._resolve_focused_field_detail(inp)
            assert name == "NX_DATA_PATH"

    async def test_resolve_input_email_field(self, tmp_path):
        """Focused Input with an email model id returns the field name (1038-1044)."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            inp = screen.query_one("#nx-email-smtp-host", Input)
            name, _detail = screen._resolve_focused_field_detail(inp)
            assert name == "smtp_host"

    async def test_resolve_input_nemo_prefix(self, tmp_path):
        """Focused Input with a NEMO prefix returns NX_NEMO_*_N name (1045-1048)."""
        env_file = tmp_path / "nemo.env"
        env_file.write_text(
            "NX_NEMO_ADDRESS_1='https://nemo.example.com/api/'\nNX_NEMO_TOKEN_1='tok'\n"
        )
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            inp = screen.query_one("#nemo-address-1", Input)
            name, _detail = screen._resolve_focused_field_detail(inp)
            assert name == "NX_NEMO_ADDRESS_N"

    async def test_resolve_input_unknown_id_returns_none(self, tmp_path):
        """Focused Input with an unmapped id returns (None, '') (1049)."""
        from unittest.mock import MagicMock

        from textual.widgets import Input as _Input

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_inp = MagicMock(spec=_Input)
            mock_inp.id = "some-unknown-input-id"
            name, detail = screen._resolve_input_field_detail(mock_inp)
            assert name is None
            assert detail == ""

    async def test_resolve_switch_ssl_verify(self, tmp_path):
        """Focused Switch nx-disable-ssl-verify returns correct env var."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            sw = screen.query_one("#nx-disable-ssl-verify", Switch)
            name, _detail = screen._resolve_focused_field_detail(sw)
            assert name == "NX_DISABLE_SSL_VERIFY"

    async def test_resolve_textarea_cert_bundle(self, tmp_path):
        """Focused TextArea nx-cert-bundle returns NX_CERT_BUNDLE (1025-1028)."""
        from textual.widgets import TextArea

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            ta = screen.query_one("#nx-cert-bundle", TextArea)
            name, _detail = screen._resolve_focused_field_detail(ta)
            assert name == "NX_CERT_BUNDLE"

    async def test_resolve_select_file_strategy(self, tmp_path):
        """Focused Select nx-file-strategy returns NX_FILE_STRATEGY (1053-1059)."""
        from textual.widgets import Select

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            sel = screen.query_one("#nx-file-strategy", Select)
            name, _detail = screen._resolve_focused_field_detail(sel)
            assert name == "NX_FILE_STRATEGY"

    async def test_resolve_select_unknown_id_returns_none(self, tmp_path):
        """Focused Select with unmapped id returns (None, '') (1060)."""
        from unittest.mock import MagicMock

        from textual.widgets import Select as _Select

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_sel = MagicMock(spec=_Select)
            mock_sel.id = "some-unknown-select-id"
            name, detail = screen._resolve_select_field_detail(mock_sel)
            assert name is None
            assert detail == ""

    async def test_resolve_unknown_widget_type_returns_none(self, tmp_path):
        """Unsupported widget types return (None, '') for field detail."""
        from unittest.mock import MagicMock

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_widget = MagicMock()  # not a spec'd Textual widget
            name, detail = screen._resolve_focused_field_detail(mock_widget)
            assert name is None
            assert detail == ""


# --------------------------------------------------------------------------- #
# TestActionShowFieldDetail  (lines 1064-1075)                                #
# --------------------------------------------------------------------------- #


class TestActionShowFieldDetail:
    """Tests for action_show_field_detail with different focused-widget states."""

    async def test_show_field_detail_pushes_screen_when_detail_available(
        self, tmp_path
    ):
        """action_show_field_detail pushes detail screen when detail exists."""
        from unittest.mock import patch

        from nexusLIMS.tui.apps.config.screens import FieldDetailScreen

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            with patch.object(
                screen,
                "_resolve_focused_field_detail",
                return_value=("NX_DATA_PATH", "Some help text"),
            ):
                screen.action_show_field_detail()
                await pilot.pause(0.1)

            assert isinstance(app.screen, FieldDetailScreen)

    async def test_show_field_detail_notifies_when_no_detail(self, tmp_path):
        """action_show_field_detail notifies when detail is empty."""
        from unittest.mock import patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        notify_calls = []

        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            with (
                patch.object(
                    screen,
                    "_resolve_focused_field_detail",
                    return_value=("NX_DATA_PATH", ""),
                ),
                patch.object(
                    app,
                    "notify",
                    side_effect=lambda msg, **_kw: notify_calls.append(msg),
                ),
            ):
                screen.action_show_field_detail()

        assert any("NX_DATA_PATH" in m for m in notify_calls)

    async def test_show_field_detail_silent_when_no_field(self, tmp_path):
        """action_show_field_detail returns silently when no field resolved."""
        from unittest.mock import patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        notify_calls = []

        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            with (
                patch.object(
                    screen,
                    "_resolve_focused_field_detail",
                    return_value=(None, ""),
                ),
                patch.object(
                    app,
                    "notify",
                    side_effect=lambda msg, **_kw: notify_calls.append(msg),
                ),
            ):
                screen.action_show_field_detail()

        assert notify_calls == []


# --------------------------------------------------------------------------- #
# TestValidateElabFTWInvalidUrl  (line 1129)                                  #
# --------------------------------------------------------------------------- #


class TestValidateElabFTWInvalidUrl:
    """Tests for invalid URL path in _validate_elabftw."""

    async def test_elabftw_invalid_url_produces_error(self, tmp_path):
        """Invalid eLabFTW URL produces validation error."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            screen.query_one("#elabftw-enabled", Switch).value = True
            await pilot.pause(0.05)
            # Set a non-empty, clearly invalid URL
            screen.query_one("#nx-elabftw-url", Input).value = "not-a-valid-url"
            screen.query_one("#nx-elabftw-api-key", Input).value = "some-key"

            errors = screen._validate_elabftw()
            assert any("NX_ELABFTW_URL" in e for e in errors)


# --------------------------------------------------------------------------- #
# TestGuardContinueBranches  (lines 1172, 1312)                               #
# --------------------------------------------------------------------------- #


class TestGuardContinueBranches:
    """Tests for defensive guard branches in NEMO validation and config building."""

    async def test_validate_nemo_skips_group_with_none_id(self, tmp_path):
        """_validate_nemo skips groups where id is None (line 1172)."""
        from unittest.mock import MagicMock, patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_group = MagicMock()
            mock_group.id = None
            with patch.object(screen, "query", return_value=[mock_group]):
                errors = screen._validate_nemo()

            # No errors because the group was skipped
            assert errors == []

    async def test_validate_nemo_skips_group_with_wrong_id_prefix(self, tmp_path):
        """_validate_nemo skips groups without 'nemo-group-' prefix."""
        from unittest.mock import MagicMock, patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_group = MagicMock()
            mock_group.id = "other-group-1"
            with patch.object(screen, "query", return_value=[mock_group]):
                errors = screen._validate_nemo()

            assert errors == []

    async def test_build_nemo_config_skips_group_with_none_id(self, tmp_path):
        """_build_nemo_config skips groups where id is None (line 1312)."""
        from unittest.mock import MagicMock, patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_group = MagicMock()
            mock_group.id = None
            with patch.object(screen, "query", return_value=[mock_group]):
                config = screen._build_nemo_config()

            # No harvesters because the group was skipped
            assert config == {}

    async def test_build_nemo_config_skips_group_with_wrong_id_prefix(self, tmp_path):
        """_build_nemo_config skips groups without 'nemo-group-' prefix."""
        from unittest.mock import MagicMock, patch

        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)
            screen = app.screen

            mock_group = MagicMock()
            mock_group.id = "other-group-1"
            with patch.object(screen, "query", return_value=[mock_group]):
                config = screen._build_nemo_config()

            assert config == {}


pytestmark = pytest.mark.unit
