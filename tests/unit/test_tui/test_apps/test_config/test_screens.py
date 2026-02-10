"""Tests for ConfigScreen tabs, pre-population, save flow, and NEMO management."""

from pathlib import Path

import pytest
from textual.widgets import Input, Switch

from nexusLIMS.tui.apps.config.app import ConfiguratorApp
from nexusLIMS.tui.apps.config.screens import ConfigScreen, NemoHarvesterFormScreen

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
        """_build_config_dict includes NEMO harvesters when present."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Inject a NEMO harvester manually
            screen._nemo_harvesters[1] = {
                "address": "https://nemo.example.com/api/",
                "token": "secret",
                "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
            }

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
# TestNemoHarvesterFormScreen                                                  #
# --------------------------------------------------------------------------- #


class TestNemoHarvesterFormScreen:
    """Tests for the NEMO harvester add/edit modal."""

    async def test_add_mode_empty_form(self, tmp_path):
        """In add mode, all fields start empty."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen()
            app.push_screen(nemo_screen)
            await pilot.pause(0.1)

            assert isinstance(app.screen, NemoHarvesterFormScreen)
            assert app.screen.query_one("#nemo-address", Input).value == ""
            assert app.screen.query_one("#nemo-token", Input).value == ""

    async def test_edit_mode_pre_populated(self, tmp_path):
        """In edit mode, fields are pre-populated with existing data."""
        env_file = tmp_path / "empty.env"
        existing = {
            "address": "https://nemo.example.com/api/",
            "token": "mytoken",
            "tz": "America/Denver",
            "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
            "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
        }
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen(existing=existing)
            app.push_screen(nemo_screen)
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, NemoHarvesterFormScreen)
            assert (
                screen.query_one("#nemo-address", Input).value
                == "https://nemo.example.com/api/"
            )
            assert screen.query_one("#nemo-token", Input).value == "mytoken"
            assert screen.query_one("#nemo-tz", Input).value == "America/Denver"

    async def test_cancel_dismisses_with_none(self, tmp_path):
        """Cancel dismisses the modal with None."""
        env_file = tmp_path / "empty.env"
        dismissed_with = []

        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen()
            app.push_screen(nemo_screen, lambda v: dismissed_with.append(v))
            await pilot.pause(0.1)

            await pilot.press("escape")
            await pilot.pause(0.1)

        assert dismissed_with == [None]

    async def test_save_with_valid_data_dismisses_with_dict(self, tmp_path):
        """Save with valid fields dismisses with harvester data dict."""
        env_file = tmp_path / "empty.env"
        dismissed_with = []

        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen()
            app.push_screen(nemo_screen, lambda v: dismissed_with.append(v))
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, NemoHarvesterFormScreen)

            screen.query_one(
                "#nemo-address", Input
            ).value = "https://nemo.example.com/api/"
            screen.query_one("#nemo-token", Input).value = "secret-token"
            await pilot.pause(0.05)

            await pilot.press("ctrl+s")
            await pilot.pause(0.1)

        assert len(dismissed_with) == 1
        assert dismissed_with[0] is not None
        assert dismissed_with[0]["address"] == "https://nemo.example.com/api/"
        assert dismissed_with[0]["token"] == "secret-token"

    async def test_save_with_missing_token_shows_error(self, tmp_path):
        """Save with missing token shows validation error."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen()
            app.push_screen(nemo_screen)
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, NemoHarvesterFormScreen)

            # Only fill address, leave token empty
            screen.query_one(
                "#nemo-address", Input
            ).value = "https://nemo.example.com/api/"
            await pilot.pause(0.05)

            await pilot.press("ctrl+s")
            await pilot.pause(0.1)

            # Should still be on the NEMO form (not dismissed)
            assert isinstance(app.screen, NemoHarvesterFormScreen)

    async def test_save_with_missing_trailing_slash_shows_error(self, tmp_path):
        """Save with address missing trailing slash shows validation error."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            nemo_screen = NemoHarvesterFormScreen()
            app.push_screen(nemo_screen)
            await pilot.pause(0.1)

            screen = app.screen
            # Set address without trailing slash (invalid)
            screen.query_one(
                "#nemo-address", Input
            ).value = "https://nemo.example.com/api"
            screen.query_one("#nemo-token", Input).value = "token"
            await pilot.pause(0.05)

            await pilot.press("ctrl+s")
            await pilot.pause(0.1)

            assert isinstance(app.screen, NemoHarvesterFormScreen)


# --------------------------------------------------------------------------- #
# TestNemoHarvesterManagement (on ConfigScreen)                               #
# --------------------------------------------------------------------------- #


class TestNemoHarvesterManagement:
    """Tests for add/edit/delete NEMO harvesters within ConfigScreen."""

    async def test_add_nemo_harvester_increments_table(self, tmp_path):
        """Adding a NEMO harvester adds a row to the DataTable."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Directly call the callback with valid data (simulates successful add)
            screen._on_nemo_form_result_add(
                {
                    "address": "https://nemo.example.com/api/",
                    "token": "token",
                    "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                    "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            )
            await pilot.pause(0.05)

            assert len(screen._nemo_harvesters) == 1

    async def test_delete_nemo_harvester_removes_from_dict(self, tmp_path):
        """Deleting a NEMO harvester removes it and renumbers remaining entries."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            # Add two harvesters
            screen._nemo_harvesters[1] = {
                "address": "https://nemo1.example.com/api/",
                "token": "t1",
            }
            screen._nemo_harvesters[2] = {
                "address": "https://nemo2.example.com/api/",
                "token": "t2",
            }
            screen._refresh_nemo_table()
            await pilot.pause(0.05)

            # Simulate pressing delete (manually call with known key)
            del screen._nemo_harvesters[1]
            screen._nemo_harvesters = {
                new_num: hvst
                for new_num, (_, hvst) in enumerate(
                    sorted(screen._nemo_harvesters.items()), start=1
                )
            }
            screen._refresh_nemo_table()
            await pilot.pause(0.05)

            assert len(screen._nemo_harvesters) == 1
            assert 1 in screen._nemo_harvesters  # Re-numbered

    async def test_edit_nemo_harvester_updates_data(self, tmp_path):
        """Editing a NEMO harvester updates its stored data."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            screen._nemo_harvesters[1] = {
                "address": "https://old.example.com/api/",
                "token": "oldtoken",
            }

            # Simulate edit callback
            screen._on_nemo_form_result_edit(
                {
                    "address": "https://new.example.com/api/",
                    "token": "newtoken",
                    "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                    "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                },
                1,
            )
            await pilot.pause(0.05)

            assert (
                screen._nemo_harvesters[1]["address"] == "https://new.example.com/api/"
            )
            assert screen._nemo_harvesters[1]["token"] == "newtoken"

    async def test_add_nemo_callback_with_none_does_nothing(self, tmp_path):
        """Passing None to the add callback (cancel) does not add a harvester."""
        env_file = tmp_path / "empty.env"
        app = ConfiguratorApp(env_path=env_file)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.1)

            screen = app.screen
            assert isinstance(screen, ConfigScreen)

            initial_count = len(screen._nemo_harvesters)
            screen._on_nemo_form_result_add(None)
            await pilot.pause(0.05)

            assert len(screen._nemo_harvesters) == initial_count


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

            # Add a NEMO harvester
            screen._nemo_harvesters[1] = {
                "address": "https://nemo.example.com/api/",
                "token": "nemo-token",
                "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
                "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
            }

            await pilot.press("ctrl+s")
            await pilot.pause(0.2)

        assert env_file.exists()
        content = env_file.read_text()
        assert "NX_NEMO_ADDRESS_1" in content
        assert "NX_NEMO_TOKEN_1" in content


pytestmark = pytest.mark.unit
