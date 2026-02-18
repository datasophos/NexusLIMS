"""Tests for the unified nexuslims CLI entrypoint."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nexusLIMS.cli.main import LazyGroup, main


class TestUnifiedCLI:
    """Tests for the unified ``nexuslims`` command."""

    def test_help_lists_all_subcommands(self):
        """``nexuslims --help`` should list all four subcommand groups."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "build-records" in result.output
        assert "config" in result.output
        assert "db" in result.output
        assert "instruments" in result.output

    def test_version_flag(self):
        """``nexuslims --version`` should show the version string."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "nexuslims" in result.output
        assert "NexusLIMS" in result.output

    def test_build_records_help(self):
        """``nexuslims build-records --help`` should show build-records options."""
        runner = CliRunner()
        result = runner.invoke(main, ["build-records", "--help"])

        assert result.exit_code == 0
        assert "Process new NexusLIMS records" in result.output
        assert "--dry-run" in result.output

    def test_config_help(self):
        """``nexuslims config --help`` should show config subcommands."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--help"])

        assert result.exit_code == 0
        assert "dump" in result.output
        assert "edit" in result.output
        assert "load" in result.output

    def test_config_dump_help(self):
        """``nexuslims config dump --help`` should show dump options."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "dump", "--help"])

        assert result.exit_code == 0
        assert "Dump the current effective configuration" in result.output

    def test_config_edit_help(self):
        """``nexuslims config edit --help`` should show edit options."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "edit", "--help"])

        assert result.exit_code == 0
        assert "Interactively edit" in result.output

    def test_config_load_help(self):
        """``nexuslims config load --help`` should show load options."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "load", "--help"])

        assert result.exit_code == 0
        assert "Load a previously dumped JSON config" in result.output

    def test_db_help(self):
        """``nexuslims db --help`` should show db subcommands."""
        runner = CliRunner()
        result = runner.invoke(main, ["db", "--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "upgrade" in result.output
        assert "downgrade" in result.output
        assert "current" in result.output
        assert "check" in result.output

    def test_instruments_help(self):
        """``nexuslims instruments --help`` should show instruments subcommands."""
        runner = CliRunner()
        result = runner.invoke(main, ["instruments", "--help"])

        assert result.exit_code == 0
        assert "manage" in result.output

    def test_instruments_manage_help(self):
        """``nexuslims instruments manage --help`` should show manage options."""
        runner = CliRunner()
        result = runner.invoke(main, ["instruments", "manage", "--help"])

        assert result.exit_code == 0
        assert "Launch the interactive instrument management TUI" in result.output
        assert "Keybindings" in result.output

    def test_no_subcommand_shows_help(self):
        """Running ``nexuslims`` with no subcommand should show help."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        # Click groups show help when invoked without a subcommand
        assert result.exit_code == 0
        assert "build-records" in result.output

    def test_build_records_version(self):
        """``nexuslims build-records --version`` should work."""
        runner = CliRunner()
        result = runner.invoke(main, ["build-records", "--version"])

        assert result.exit_code == 0
        assert "NexusLIMS" in result.output

    def test_config_version(self):
        """``nexuslims config --version`` should work."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--version"])

        assert result.exit_code == 0
        assert "NexusLIMS" in result.output

    def test_db_version(self):
        """``nexuslims db --version`` should work."""
        runner = CliRunner()
        result = runner.invoke(main, ["db", "--version"])

        assert result.exit_code == 0
        assert "NexusLIMS" in result.output


class TestInstrumentsManage:
    """Tests for the ``nexuslims instruments manage`` command body."""

    def test_manage_invokes_tui(self):
        """``nexuslims instruments manage`` should call the TUI entrypoints."""
        runner = CliRunner()
        with (
            patch(
                "nexusLIMS.cli.manage_instruments._ensure_database_initialized"
            ) as mock_ensure,
            patch(
                "nexusLIMS.cli.manage_instruments._run_instrument_manager"
            ) as mock_run,
        ):
            result = runner.invoke(main, ["instruments", "manage"])

        assert result.exit_code == 0
        mock_ensure.assert_called_once()
        mock_run.assert_called_once()


class TestLazyGroup:
    """Tests for the LazyGroup get_command fallthrough."""

    def test_get_command_returns_none_for_unknown(self):
        """get_command returns None for a command not in eager or lazy registries."""
        import click

        group = LazyGroup(
            name="test",
            lazy_commands={"known": ("some.module", "attr")},
        )
        ctx = click.Context(group)
        assert group.get_command(ctx, "nonexistent") is None


class TestLazyLoading:
    """Tests for the lazy loading mechanism."""

    def test_help_does_not_import_heavy_modules(self):
        """``nexuslims --help`` should not import heavy modules like hyperspy."""
        import sys

        # Remove hyperspy from sys.modules if present
        hyperspy_modules = [k for k in sys.modules if k.startswith("hyperspy")]

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0

        # Check that no new hyperspy modules were loaded
        new_hyperspy = [
            k
            for k in sys.modules
            if k.startswith("hyperspy") and k not in hyperspy_modules
        ]
        assert new_hyperspy == [], (
            f"Heavy modules imported during --help: {new_hyperspy}"
        )


class TestCompletionCommand:
    """Tests for the ``nexuslims completion`` command."""

    def test_completion_help(self):
        """``nexuslims completion --help`` should show shell option."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--help"])

        assert result.exit_code == 0
        assert "--shell" in result.output

    def test_explicit_bash(self):
        """``--shell bash`` outputs the bash eval line and ~/.bashrc."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--shell", "bash"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=bash_source nexuslims" in result.output
        assert "~/.bashrc" in result.output

    def test_explicit_zsh(self):
        """``--shell zsh`` outputs the zsh eval line and ~/.zshrc."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--shell", "zsh"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=zsh_source nexuslims" in result.output
        assert "~/.zshrc" in result.output

    def test_explicit_fish(self):
        """``--shell fish`` outputs the fish source line and config.fish."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--shell", "fish"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=fish_source nexuslims | source" in result.output
        assert "~/.config/fish/config.fish" in result.output

    def test_auto_detect_zsh(self):
        """Auto-detection uses zsh when $SHELL contains 'zsh'."""
        runner = CliRunner()
        with patch.dict("os.environ", {"SHELL": "/usr/bin/zsh"}):
            result = runner.invoke(main, ["completion"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=zsh_source nexuslims" in result.output
        assert "~/.zshrc" in result.output

    def test_auto_detect_fish(self):
        """Auto-detection uses fish when $SHELL contains 'fish'."""
        runner = CliRunner()
        with patch.dict("os.environ", {"SHELL": "/usr/local/bin/fish"}):
            result = runner.invoke(main, ["completion"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=fish_source nexuslims | source" in result.output
        assert "~/.config/fish/config.fish" in result.output

    def test_auto_detect_bash_fallback(self):
        """Auto-detection falls back to bash when $SHELL is unrecognised."""
        runner = CliRunner()
        with patch.dict("os.environ", {"SHELL": "/bin/sh"}):
            result = runner.invoke(main, ["completion"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=bash_source nexuslims" in result.output
        assert "~/.bashrc" in result.output

    def test_auto_detect_empty_shell_env(self):
        """Auto-detection falls back to bash when $SHELL is not set."""
        runner = CliRunner()
        env = {k: v for k, v in __import__("os").environ.items() if k != "SHELL"}
        with patch.dict("os.environ", env, clear=True):
            result = runner.invoke(main, ["completion"])

        assert result.exit_code == 0
        assert "_NEXUSLIMS_COMPLETE=bash_source nexuslims" in result.output
        assert "~/.bashrc" in result.output

    def test_output_includes_path_note(self):
        """Output always includes the PATH note regardless of shell."""
        runner = CliRunner()
        for shell in ("bash", "zsh", "fish"):
            result = runner.invoke(main, ["completion", "--shell", shell])
            assert result.exit_code == 0
            assert "nexuslims must be on your PATH" in result.output

    def test_invalid_shell_rejected(self):
        """Passing an unsupported shell value is rejected by Click."""
        runner = CliRunner()
        result = runner.invoke(main, ["completion", "--shell", "tcsh"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output


pytestmark = pytest.mark.unit
