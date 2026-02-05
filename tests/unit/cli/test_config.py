"""Tests for the nexuslims-config CLI (dump / load) and helpers."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

from click.testing import CliRunner

from nexusLIMS.cli.config import (
    _build_config_dict,
    _flatten_to_env,
    _sanitize_config,
    main,
)

# ---------------------------------------------------------------------------
# Helpers to build realistic mock settings
# ---------------------------------------------------------------------------


def _mock_settings(
    *,
    with_nemo: bool = True,
    with_email: bool = True,
) -> Mock:
    """Return a Mock that behaves like the Settings proxy."""
    settings = Mock()
    settings.model_dump.return_value = {
        "NX_FILE_STRATEGY": "exclusive",
        "NX_IGNORE_PATTERNS": ["*.mib", "*.db"],
        "NX_INSTRUMENT_DATA_PATH": "/data/instruments",
        "NX_DATA_PATH": "/data/nx",
        "NX_DB_PATH": "/data/nx.db",
        "NX_CDCS_TOKEN": "secret-cdcs-token",
        "NX_CDCS_URL": "https://cdcs.example.com",
        "NX_EXPORT_STRATEGY": "all",
        "NX_CERT_BUNDLE_FILE": None,
        "NX_CERT_BUNDLE": "secret-pem-data",
        "NX_DISABLE_SSL_VERIFY": False,
        "NX_FILE_DELAY_DAYS": 2.0,
        "NX_CLUSTERING_SENSITIVITY": 1.0,
        "NX_LOG_PATH": None,
        "NX_RECORDS_PATH": None,
        "NX_LOCAL_PROFILES_PATH": None,
        "NX_ELABFTW_API_KEY": "secret-elab-key",
        "NX_ELABFTW_URL": "https://elab.example.com",
        "NX_ELABFTW_EXPERIMENT_CATEGORY": 1,
        "NX_ELABFTW_EXPERIMENT_STATUS": None,
    }

    if with_nemo:
        nemo_cfg = Mock()
        nemo_cfg.model_dump.return_value = {
            "address": "https://nemo.example.com/api/",
            "token": "secret-nemo-token",
            "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
            "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
            "tz": "America/Denver",
        }
        settings.nemo_harvesters.return_value = {1: nemo_cfg}
    else:
        settings.nemo_harvesters.return_value = {}

    if with_email:
        email_cfg = Mock()
        email_cfg.model_dump.return_value = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "user@example.com",
            "smtp_password": "secret-smtp-pass",
            "use_tls": True,
            "sender": "sender@example.com",
            "recipients": ["admin@example.com", "team@example.com"],
        }
        settings.email_config.return_value = email_cfg
    else:
        settings.email_config.return_value = None

    return settings


# ===========================================================================
# TestBuildConfigDict
# ===========================================================================


class TestBuildConfigDict:
    """Unit tests for _build_config_dict."""

    def test_includes_all_scalar_fields(self):
        """All top-level Settings fields appear in the returned dict."""
        config = _build_config_dict(_mock_settings())
        assert config["NX_FILE_STRATEGY"] == "exclusive"
        assert config["NX_CDCS_TOKEN"] == "secret-cdcs-token"
        assert config["NX_FILE_DELAY_DAYS"] == 2.0

    def test_nemo_harvesters_nested(self):
        """NEMO harvesters are nested under a 'nemo_harvesters' key."""
        config = _build_config_dict(_mock_settings(with_nemo=True))
        assert "nemo_harvesters" in config
        assert "1" in config["nemo_harvesters"]
        assert (
            config["nemo_harvesters"]["1"]["address"] == "https://nemo.example.com/api/"
        )
        assert config["nemo_harvesters"]["1"]["token"] == "secret-nemo-token"

    def test_nemo_harvesters_omitted_when_empty(self):
        """'nemo_harvesters' key is absent when no harvesters are configured."""
        config = _build_config_dict(_mock_settings(with_nemo=False))
        assert "nemo_harvesters" not in config

    def test_email_config_nested(self):
        """Email config is nested under an 'email_config' key."""
        config = _build_config_dict(_mock_settings(with_email=True))
        assert "email_config" in config
        assert config["email_config"]["smtp_host"] == "smtp.example.com"
        assert config["email_config"]["smtp_password"] == "secret-smtp-pass"

    def test_email_config_omitted_when_none(self):
        """'email_config' key is absent when email is not configured."""
        config = _build_config_dict(_mock_settings(with_email=False))
        assert "email_config" not in config


# ===========================================================================
# TestSanitizeConfig
# ===========================================================================


class TestSanitizeConfig:
    """Unit tests for _sanitize_config."""

    def _full_config(self) -> dict:
        return _build_config_dict(_mock_settings())

    def test_redacts_cdcs_token(self):
        """NX_CDCS_TOKEN is replaced with the redaction sentinel."""
        assert _sanitize_config(self._full_config())["NX_CDCS_TOKEN"] == "***"

    def test_redacts_cert_bundle(self):
        """NX_CERT_BUNDLE is replaced with the redaction sentinel."""
        assert _sanitize_config(self._full_config())["NX_CERT_BUNDLE"] == "***"

    def test_redacts_elabftw_api_key(self):
        """NX_ELABFTW_API_KEY is replaced with the redaction sentinel."""
        assert _sanitize_config(self._full_config())["NX_ELABFTW_API_KEY"] == "***"

    def test_redacts_nemo_tokens(self):
        """Each harvester's token is redacted; other fields survive."""
        sanitized = _sanitize_config(self._full_config())
        assert sanitized["nemo_harvesters"]["1"]["token"] == "***"
        assert (
            sanitized["nemo_harvesters"]["1"]["address"]
            == "https://nemo.example.com/api/"
        )

    def test_redacts_email_password(self):
        """smtp_password is redacted; other email fields survive."""
        sanitized = _sanitize_config(self._full_config())
        assert sanitized["email_config"]["smtp_password"] == "***"
        assert sanitized["email_config"]["smtp_host"] == "smtp.example.com"

    def test_does_not_mutate_original(self):
        """The input dict is not modified in place."""
        original = self._full_config()
        original_token = original["NX_CDCS_TOKEN"]
        _sanitize_config(original)
        assert original["NX_CDCS_TOKEN"] == original_token

    def test_handles_missing_nested_keys(self):
        """Sanitize works cleanly when nemo/email are absent."""
        config = _build_config_dict(_mock_settings(with_nemo=False, with_email=False))
        sanitized = _sanitize_config(config)
        # secrets that ARE present still get redacted
        assert sanitized["NX_CDCS_TOKEN"] == "***"
        # no crash from missing nested keys
        assert "nemo_harvesters" not in sanitized
        assert "email_config" not in sanitized

    def test_non_secret_scalars_unchanged(self):
        """Non-secret scalar and list values pass through unmodified."""
        sanitized = _sanitize_config(self._full_config())
        assert sanitized["NX_FILE_STRATEGY"] == "exclusive"
        assert sanitized["NX_FILE_DELAY_DAYS"] == 2.0
        assert sanitized["NX_IGNORE_PATTERNS"] == ["*.mib", "*.db"]


# ===========================================================================
# TestFlattenToEnv
# ===========================================================================


class TestFlattenToEnv:
    """Unit tests for _flatten_to_env."""

    def _full_config(self) -> dict:
        return _build_config_dict(_mock_settings())

    def test_scalar_passthrough(self):
        """Plain scalar values become string env-var values."""
        env = _flatten_to_env(self._full_config())
        assert env["NX_FILE_STRATEGY"] == "exclusive"
        assert env["NX_CDCS_TOKEN"] == "secret-cdcs-token"

    def test_list_is_json_encoded(self):
        """List values are serialised as a JSON array string."""
        env = _flatten_to_env(self._full_config())
        assert env["NX_IGNORE_PATTERNS"] == json.dumps(["*.mib", "*.db"])

    def test_booleans_are_lowercased(self):
        """Boolean values are emitted as lowercase 'true' / 'false'."""
        env = _flatten_to_env(self._full_config())
        assert env["NX_DISABLE_SSL_VERIFY"] == "false"

    def test_none_values_omitted(self):
        """Keys whose value is None do not appear in the output."""
        env = _flatten_to_env(self._full_config())
        assert "NX_CERT_BUNDLE_FILE" not in env
        assert "NX_LOG_PATH" not in env
        assert "NX_RECORDS_PATH" not in env
        assert "NX_LOCAL_PROFILES_PATH" not in env
        assert "NX_ELABFTW_EXPERIMENT_STATUS" not in env

    def test_nemo_harvesters_expanded(self):
        """Nested harvester fields expand to NX_NEMO_*_N env vars."""
        env = _flatten_to_env(self._full_config())
        assert env["NX_NEMO_ADDRESS_1"] == "https://nemo.example.com/api/"
        assert env["NX_NEMO_TOKEN_1"] == "secret-nemo-token"
        assert env["NX_NEMO_STRFTIME_FMT_1"] == "%Y-%m-%dT%H:%M:%S%z"
        assert env["NX_NEMO_TZ_1"] == "America/Denver"

    def test_email_config_expanded(self):
        """Nested email fields expand to NX_EMAIL_* env vars."""
        env = _flatten_to_env(self._full_config())
        assert env["NX_EMAIL_SMTP_HOST"] == "smtp.example.com"
        assert env["NX_EMAIL_SMTP_PORT"] == "587"
        assert env["NX_EMAIL_SMTP_PASSWORD"] == "secret-smtp-pass"
        assert env["NX_EMAIL_USE_TLS"] == "true"
        assert env["NX_EMAIL_SENDER"] == "sender@example.com"
        assert env["NX_EMAIL_RECIPIENTS"] == "admin@example.com,team@example.com"

    def test_empty_nemo_and_email(self):
        """No NX_NEMO_* or NX_EMAIL_* keys when both are unconfigured."""
        config = _build_config_dict(_mock_settings(with_nemo=False, with_email=False))
        env = _flatten_to_env(config)
        assert not any(k.startswith("NX_NEMO_") for k in env)
        assert not any(k.startswith("NX_EMAIL_") for k in env)


# ===========================================================================
# TestDumpCommand
# ===========================================================================


class TestDumpCommand:
    """Integration tests for ``nexuslims-config dump``."""

    def test_dump_writes_valid_json(self, tmp_path, monkeypatch):
        """Dump produces a valid JSON file with the full unsanitised config."""
        monkeypatch.setattr("nexusLIMS.config.settings", _mock_settings())
        output_file = tmp_path / "out.json"

        runner = CliRunner()
        result = runner.invoke(main, ["dump", "--output", str(output_file)])

        assert result.exit_code == 0, result.output
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["NX_CDCS_TOKEN"] == "secret-cdcs-token"

    def test_dump_prints_credential_warning(self, tmp_path, monkeypatch):
        """A credential warning is printed to stderr on every dump."""
        monkeypatch.setattr("nexusLIMS.config.settings", _mock_settings())
        output_file = tmp_path / "out.json"

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["dump", "--output", str(output_file)])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.stderr
        assert "credentials" in result.stderr

    def test_dump_default_output_name(self, tmp_path, monkeypatch):
        """Default output path is config.json in CWD."""
        monkeypatch.setattr("nexusLIMS.config.settings", _mock_settings())

        runner = CliRunner(mix_stderr=False)
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(main, ["dump"])
        finally:
            os.chdir(original_cwd)

        assert result.exit_code == 0, result.output
        assert (tmp_path / "config.json").exists()


# ===========================================================================
# TestLoadCommand
# ===========================================================================


class TestLoadCommand:
    """Integration tests for ``nexuslims-config load``."""

    def _write_config_json(self, path: Path) -> None:
        config = _build_config_dict(_mock_settings())
        path.write_text(json.dumps(config))

    def test_load_no_preexisting_env(self, tmp_path):
        """Load writes .env cleanly when none exists — no prompt."""
        input_file = tmp_path / "config.json"
        self._write_config_json(input_file)
        env_path = tmp_path / ".env"

        runner = CliRunner()
        result = runner.invoke(
            main, ["load", str(input_file), "--env-path", str(env_path)]
        )

        assert result.exit_code == 0, result.output
        assert env_path.exists()
        content = env_path.read_text()
        assert "NX_FILE_STRATEGY" in content
        assert "NX_NEMO_ADDRESS_1" in content
        assert "NX_EMAIL_SMTP_HOST" in content

    def test_load_backs_up_existing_env_on_confirm(self, tmp_path):
        """Pre-existing .env is backed up and overwritten on 'y'."""
        input_file = tmp_path / "config.json"
        self._write_config_json(input_file)
        env_path = tmp_path / ".env"
        env_path.write_text("OLD_CONTENT=1\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["load", str(input_file), "--env-path", str(env_path)],
            input="y\n",
        )

        assert result.exit_code == 0, result.output
        assert "OLD_CONTENT" not in env_path.read_text()
        backups = list(tmp_path.glob(".env.bak.*"))
        assert len(backups) == 1
        assert backups[0].read_text() == "OLD_CONTENT=1\n"

    def test_load_aborts_on_deny(self, tmp_path):
        """User says 'n' at the prompt -> .env is untouched, no backup."""
        input_file = tmp_path / "config.json"
        self._write_config_json(input_file)
        env_path = tmp_path / ".env"
        env_path.write_text("OLD_CONTENT=1\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["load", str(input_file), "--env-path", str(env_path)],
            input="n\n",
        )

        # click.confirm with abort=True raises Abort -> exit code 1
        assert result.exit_code != 0
        assert env_path.read_text() == "OLD_CONTENT=1\n"
        assert len(list(tmp_path.glob(".env.bak.*"))) == 0

    def test_load_force_skips_prompt_but_still_backs_up(self, tmp_path):
        """--force skips the confirmation prompt but still creates a backup."""
        input_file = tmp_path / "config.json"
        self._write_config_json(input_file)
        env_path = tmp_path / ".env"
        env_path.write_text("OLD_CONTENT=1\n")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["load", str(input_file), "--env-path", str(env_path), "--force"],
        )

        assert result.exit_code == 0, result.output
        assert "OLD_CONTENT" not in env_path.read_text()
        backups = list(tmp_path.glob(".env.bak.*"))
        assert len(backups) == 1

    def test_load_warns_about_existing_env(self, tmp_path):
        """The WARNING about pre-existing .env appears on stderr."""
        input_file = tmp_path / "config.json"
        self._write_config_json(input_file)
        env_path = tmp_path / ".env"
        env_path.write_text("OLD=1\n")

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            ["load", str(input_file), "--env-path", str(env_path), "--force"],
        )

        assert result.exit_code == 0
        assert "WARNING" in result.stderr
