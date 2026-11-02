# ruff: noqa: D103
"""Configuration selection diagnostics and CLI output."""

from click.testing import CliRunner

from nexusLIMS import config
from nexusLIMS.cli.main import main


def test_status_reports_precedence_and_environment_names(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NX_CONFIG_FILE", raising=False)
    system = tmp_path / "system.toml"
    system.write_text("invalid = [")
    monkeypatch.setattr(config, "SYSTEM_CONFIG_PATH", system)
    monkeypatch.setenv("NX_CDCS_TOKEN", "secret-value")
    result = CliRunner(mix_stderr=False).invoke(main, ["config", "status"])
    assert result.exit_code == 0, result.output
    assert str(system) in result.stdout
    assert "system" in result.stdout
    assert "NX_CDCS_TOKEN" in result.stdout
    assert "secret-value" not in result.output
    assert "user" in result.stdout.lower()
    assert "Running as user: " in result.stdout
    assert "  User:            " in result.stdout
    assert "  System:          " in result.stdout
    assert "Home:" not in result.stdout
    assert result.stderr == ""
    assert "Active configuration:" in result.stdout
    assert "(system)" in result.stdout


def test_status_line_does_not_contaminate_stdout_and_help_is_quiet(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("NX_CONFIG_FILE", str(tmp_path / "missing.toml"))
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(main, ["completion", "--shell", "bash"])
    assert result.exit_code == 0
    assert "Configuration" not in result.stdout
    assert "NX_CONFIG_FILE" in result.stderr
    assert "Selected configuration does not exist" in result.stderr
    for args in (
        ["--help"],
        ["config", "--help"],
        ["config", "status", "--help"],
        ["--version"],
    ):
        assert runner.invoke(main, args).stderr == ""


def test_edit_without_terminal_fails_cleanly():
    result = CliRunner(mix_stderr=False).invoke(main, ["config", "edit"])
    assert result.exit_code != 0
    assert "terminal" in result.stderr.lower()


async def test_editor_opens_selected_file_and_shows_path(tmp_path):
    from nexusLIMS.tui.apps.config.app import ConfiguratorApp
    from nexusLIMS.tui.apps.config.screens import ConfigScreen

    selected = tmp_path / "config.toml"
    app = ConfiguratorApp(env_path=selected)
    async with app.run_test(size=(100, 35)):
        assert isinstance(app.screen, ConfigScreen)
        assert str(selected) in app.title


def test_status_groups_details_without_repeating_selected_path(monkeypatch, tmp_path):
    selected = tmp_path / "selected.toml"
    monkeypatch.setenv("NX_CONFIG_FILE", str(selected))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(config, "SYSTEM_CONFIG_PATH", tmp_path / "system.toml")
    result = CliRunner(mix_stderr=False).invoke(main, ["config", "status"])
    assert result.exit_code == 0
    assert result.stderr == ""
    assert f"  Selected file:   {selected} (NX_CONFIG_FILE)" in result.stdout
    assert "  File status:     missing" in result.stdout
    assert "Candidate files:" in result.stdout
    assert "ignored: NX_CONFIG_FILE takes precedence" in result.stdout


def test_status_invalid_selector_reports_problem_without_values(monkeypatch, tmp_path):
    monkeypatch.setenv("NX_CONFIG_FILE", "relative.toml")
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner(mix_stderr=False).invoke(main, ["config", "status"])
    assert result.exit_code == 0
    assert result.stderr == ""
    assert "absolute path" in result.stdout
    assert "NX_CONFIG_FILE" in result.stdout


def test_edit_displays_active_path_once_before_acknowledgement(monkeypatch, tmp_path):
    from unittest.mock import patch

    selected = tmp_path / "config.toml"
    selected.write_text("")
    monkeypatch.setenv("NX_CONFIG_FILE", str(selected))
    monkeypatch.setattr("nexusLIMS.cli.config._interactive_terminal", lambda: True)
    with patch("nexusLIMS.tui.apps.config.app.ConfiguratorApp"):
        result = CliRunner(mix_stderr=False).invoke(
            main, ["config", "edit"], input="\n"
        )
    assert result.exit_code == 0
    assert result.stderr.count(str(selected)) == 1
    assert f"Editing configuration: {selected} (NX_CONFIG_FILE)" in result.stderr
    assert "Using configuration" not in result.stderr
    assert "Press Enter" in result.stderr
