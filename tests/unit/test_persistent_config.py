"""Tests for selecting and reading persistent configuration files."""

from nexusLIMS import config


def test_selected_config_path_is_independent_of_working_directory(
    monkeypatch, tmp_path
):
    """The default path is rooted in the user home."""
    monkeypatch.delenv("NX_CONFIG_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert config.get_config_path() == tmp_path / ".config/nexuslims/config.toml"


def test_toml_file_reads_nested_configuration(tmp_path):
    """Nested NEMO configuration maps to environment names."""
    path = tmp_path / "config.toml"
    path.write_text(
        '[core]\nNX_FILE_STRATEGY = "inclusive"\n'
        '[nemo_harvesters.1]\naddress = "https://example.org/api/"\ntoken = "secret"\n'
    )
    values = config.read_config_file(path)
    assert values["NX_FILE_STRATEGY"] == "inclusive"
    assert values["NX_NEMO_ADDRESS_1"] == "https://example.org/api/"
    assert values["NX_NEMO_TOKEN_1"] == "secret"


def test_settings_use_selected_file_and_environment_overrides(monkeypatch, tmp_path):
    """Environment values override the selected file."""
    path = tmp_path / "config.toml"
    path.write_text('[core]\nNX_FILE_STRATEGY = "inclusive"\n')
    monkeypatch.setenv("NX_CONFIG_FILE", str(path))
    monkeypatch.setattr(config, "TEST_MODE", False)
    monkeypatch.delenv("NX_FILE_STRATEGY", raising=False)
    assert config.Settings().NX_FILE_STRATEGY == "inclusive"
    monkeypatch.setenv("NX_FILE_STRATEGY", "exclusive")
    assert config.Settings().NX_FILE_STRATEGY == "exclusive"


def test_toml_write_round_trip(tmp_path):
    """TOML output can be read back without losing configuration."""
    from nexusLIMS.cli.config import _write_config_file

    path = tmp_path / "nested" / "config.toml"
    expected = {
        "NX_FILE_STRATEGY": "inclusive",
        "NX_NEMO_ADDRESS_1": "https://example.org/api/",
        "NX_NEMO_TOKEN_1": "secret-🔬",
    }
    _write_config_file(expected, path)
    assert config.read_config_file(path) == expected


def test_test_mode_ignores_selected_file(monkeypatch, tmp_path):
    """Tests do not accidentally inherit a user's configuration."""
    path = tmp_path / "config.toml"
    path.write_text('[core]\nNX_FILE_STRATEGY = "inclusive"\n')
    monkeypatch.setenv("NX_CONFIG_FILE", str(path))
    monkeypatch.delenv("NX_FILE_STRATEGY", raising=False)
    monkeypatch.setattr(config, "TEST_MODE", True)
    assert config.Settings().NX_FILE_STRATEGY == "exclusive"


def test_invalid_relative_selector_is_rejected(monkeypatch):
    """A relative selector cannot reintroduce working directory dependence."""
    import pytest

    monkeypatch.setenv("NX_CONFIG_FILE", "config.toml")
    with pytest.raises(ValueError, match="absolute"):
        config.get_config_path()


def test_config_load_uses_selected_toml_path(monkeypatch, tmp_path):
    """Import writes the same path subsequently used by the loader."""
    import json

    from click.testing import CliRunner

    from nexusLIMS.cli.config import main

    selected = tmp_path / "configuration" / "config.toml"
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"NX_FILE_STRATEGY": "inclusive"}))
    monkeypatch.setenv("NX_CONFIG_FILE", str(selected))
    result = CliRunner().invoke(main, ["load", str(source)])
    assert result.exit_code == 0, result.output
    assert str(selected) in result.output
    assert config.read_config_file(selected)["NX_FILE_STRATEGY"] == "inclusive"


def test_toml_integrations_and_email_round_trip(tmp_path):
    """The editor format preserves integration credentials and email settings."""
    from nexusLIMS.cli.config import _write_config_file

    path = tmp_path / "config.toml"
    values = {
        "NX_EMAIL_SMTP_HOST": "smtp.example.org",
        "NX_EMAIL_RECIPIENTS": "first@example.org,second@example.org",
        "NX_EMAIL_USE_TLS": "true",
        "NX_LABARCHIVES_ACCESS_KEY_ID": "key",
    }
    _write_config_file(values, path)
    assert config.read_config_file(path) == values


def test_selected_file_is_used_from_different_working_directories(tmp_path):
    """Separate processes read the same file even beside a conflicting .env."""
    import os
    import subprocess
    import sys

    path = tmp_path / "config.toml"
    path.write_text('[core]\nNX_FILE_STRATEGY = "inclusive"\n')
    other = tmp_path / "other"
    other.mkdir()
    (other / ".env").write_text("NX_FILE_STRATEGY=exclusive\n")
    env = os.environ.copy()
    env.update(NX_CONFIG_FILE=str(path), NX_TEST_MODE="false")
    env.pop("NX_FILE_STRATEGY", None)
    cmd = [
        sys.executable,
        "-c",
        "from nexusLIMS.config import get_config_value; "
        "print(get_config_value('NX_FILE_STRATEGY'))",
    ]
    for directory in (tmp_path, other):
        result = subprocess.run(
            cmd, cwd=directory, env=env, check=True, capture_output=True, text=True
        )
        assert result.stdout.strip() == "inclusive"


def test_database_init_uses_selected_toml(tmp_path):
    """Alembic initializes the database named by the selected configuration."""
    import os
    import sqlite3
    import subprocess
    import sys

    database = tmp_path / "database.db"
    path = tmp_path / "config.toml"
    path.write_text(f'[core]\nNX_DB_PATH = "{database}"\n')
    env = os.environ.copy()
    env.update(NX_CONFIG_FILE=str(path), NX_TEST_MODE="false")
    env.pop("NX_DB_PATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from nexusLIMS.cli.main import main; main()",
            "db",
            "init",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM alembic_version").fetchone()[0]
            == 1
        )


def test_environment_list_override_ignores_invalid_file_value(monkeypatch, tmp_path):
    """An environment override wins even when the file value is malformed."""
    path = tmp_path / "config.toml"
    path.write_text('[core]\nNX_IGNORE_PATTERNS = "not json"\n')
    monkeypatch.setenv("NX_CONFIG_FILE", str(path))
    monkeypatch.setenv("NX_IGNORE_PATTERNS", '["*.tmp"]')
    monkeypatch.setattr(config, "TEST_MODE", False)
    assert config.Settings().NX_IGNORE_PATTERNS == ["*.tmp"]


def test_pytest_selects_a_temporary_configuration_file(tmp_path):
    """Commands without path options cannot target a developer's config file."""
    assert config.get_config_path() == tmp_path / "nexuslims-test-config.toml"


def test_config_load_without_path_uses_test_isolation(monkeypatch, tmp_path):
    """A default config load writes to the isolated path, not the user's home."""
    import json

    from click.testing import CliRunner

    from nexusLIMS.cli.config import main

    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"NX_FILE_STRATEGY": "inclusive"}))

    result = CliRunner().invoke(main, ["load", str(source)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "nexuslims-test-config.toml").is_file()
    assert not (fake_home / ".config/nexuslims/config.toml").exists()
