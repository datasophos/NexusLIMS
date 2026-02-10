"""Tests functionality related to the config settings module."""

# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest

from nexusLIMS.config import Settings


@pytest.fixture(autouse=True)
def isolated_from_dotenv(monkeypatch):
    """
    Ensure tests are isolated from any .env file in the user's environment.

    This prevents local configurations from interfering with test results.
    """
    # For pydantic-settings, disable .env file loading by setting env_file to None
    # in the model_config, as requested.
    monkeypatch.setitem(Settings.model_config, "env_file", None)

    # The nemo_harvesters and email_config methods have their own logic to check
    # if '.env' exists. We patch Path.exists to return False for that specific file
    # to prevent them from loading it.
    original_exists = Path.exists

    def mock_exists(self):
        if self.name == ".env":
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists)


def test_trailing_slash_nemo_address_validation(mock_nemo_env):
    """Test that the NEMO address from the fixture has a trailing slash."""
    from nexusLIMS.config import settings

    # The mock_nemo_env fixture sets up a NEMO harvester with a trailing slash
    assert 1 in settings.nemo_harvesters()
    addr = str(settings.nemo_harvesters()[1].address)
    assert addr.endswith("/")


def test_nemo_address_missing_trailing_slash(with_validation):
    """Test that NEMO address without trailing slash raises validation error."""
    from pydantic import ValidationError

    from nexusLIMS.config import NemoHarvesterConfig

    with pytest.raises(ValidationError, match="trailing slash"):
        NemoHarvesterConfig(
            address="https://nemo.example.com/api",  # No trailing slash
            token="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            strftime_fmt="%Y-%m-%dT%H:%M:%S%z",
            strptime_fmt="%Y-%m-%dT%H:%M:%S%z",
            tz=None,
        )


def test_nemo_harvester_with_optional_fields(monkeypatch):
    """Test NEMO harvester config with all optional fields."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_NEMO_ADDRESS_2", "https://nemo2.example.com/api/")
    monkeypatch.setenv("NX_NEMO_TOKEN_2", "test-token-2")
    monkeypatch.setenv("NX_NEMO_STRFTIME_FMT_2", "%Y-%m-%d")
    monkeypatch.setenv("NX_NEMO_STRPTIME_FMT_2", "%Y-%m-%d %H:%M")
    monkeypatch.setenv("NX_NEMO_TZ_2", "America/New_York")

    # Refresh settings to pick up new environment variables
    refresh_settings()

    harvester = settings.nemo_harvesters()[2]
    assert harvester.strftime_fmt == "%Y-%m-%d"
    assert harvester.strptime_fmt == "%Y-%m-%d %H:%M"
    assert harvester.tz == "America/New_York"


def test_nemo_harvester_skipped_when_incomplete(monkeypatch, caplog):
    """Test that NEMO harvesters with missing address or token are skipped."""
    from nexusLIMS.config import refresh_settings, settings

    # Only provide address for harvester 5, not token
    monkeypatch.setenv("NX_NEMO_ADDRESS_5", "https://nemo5.example.com/api/")
    # Explicitly unset token if it exists
    monkeypatch.delenv("NX_NEMO_TOKEN_5", raising=False)

    # Refresh settings to pick up new environment variables
    refresh_settings()

    with caplog.at_level("WARNING"):
        harvesters = settings.nemo_harvesters()
        assert 5 not in harvesters
        assert "Skipping NEMO harvester 5" in caplog.text


def test_nemo_harvester_invalid_config_raises(monkeypatch, with_validation):
    """Test that an invalid NEMO harvester config raises a ValidationError."""
    from pydantic import ValidationError

    from nexusLIMS.config import refresh_settings, settings

    # Set an invalid URL for the address
    monkeypatch.setenv("NX_NEMO_ADDRESS_3", "not-a-valid-url")
    monkeypatch.setenv("NX_NEMO_TOKEN_3", "test-token-3")

    refresh_settings()

    with pytest.raises(ValidationError):
        settings.nemo_harvesters()


def test_email_config_full(monkeypatch):
    """Test email configuration with all fields using environment variables."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NX_EMAIL_SMTP_PORT", "587")
    monkeypatch.setenv("NX_EMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv(
        "NX_EMAIL_RECIPIENTS",
        "recipient1@example.com, recipient2@example.com",
    )
    monkeypatch.setenv("NX_EMAIL_SMTP_USERNAME", "user")
    monkeypatch.setenv("NX_EMAIL_SMTP_PASSWORD", "pass")
    monkeypatch.setenv("NX_EMAIL_USE_TLS", "true")

    # Refresh settings to pick up new environment variables
    refresh_settings()

    email = settings.email_config()

    assert email is not None
    assert email.smtp_host == "smtp.example.com"
    assert email.smtp_port == 587
    assert email.sender == "sender@example.com"
    assert email.recipients == ["recipient1@example.com", "recipient2@example.com"]
    assert email.smtp_username == "user"
    assert email.smtp_password == "pass"
    assert email.use_tls is True


def test_email_config_minimal(monkeypatch):
    """Test email configuration with only required fields."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NX_EMAIL_SENDER", "sender@example.com")
    monkeypatch.setenv("NX_EMAIL_RECIPIENTS", "recipient@example.com")

    # Refresh settings to pick up new environment variables
    refresh_settings()

    email = settings.email_config()

    assert email is not None
    assert email.smtp_host == "smtp.example.com"
    assert email.sender == "sender@example.com"
    assert email.recipients == ["recipient@example.com"]


def test_email_config_not_configured(mock_nemo_env, monkeypatch):
    """Test that email_config returns None when not configured."""
    from nexusLIMS.config import refresh_settings, settings

    # Unset any email variables that might be loaded from .env
    # (e.g., from cli.migrate module in other tests)
    monkeypatch.delenv("NX_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("NX_EMAIL_SENDER", raising=False)
    monkeypatch.delenv("NX_EMAIL_RECIPIENTS", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("NX_EMAIL_USE_TLS", raising=False)

    # Refresh settings to pick up the cleared environment
    refresh_settings()

    assert settings.email_config() is None


def test_email_config_partial_configuration(monkeypatch):
    """Test that email_config returns None when partially configured."""
    from nexusLIMS.config import refresh_settings, settings

    # Only SMTP host, missing sender and recipients
    monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("NX_EMAIL_SENDER", raising=False)
    monkeypatch.delenv("NX_EMAIL_RECIPIENTS", raising=False)

    # Refresh settings to pick up new environment variables
    refresh_settings()

    assert settings.email_config() is None


def test_email_config_invalid_returns_none(monkeypatch, caplog, with_validation):
    """Test that invalid email configuration returns None and logs error."""
    from nexusLIMS.config import refresh_settings, settings

    # Provide invalid email format
    monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("NX_EMAIL_SENDER", "not-an-email")  # Invalid
    monkeypatch.setenv("NX_EMAIL_RECIPIENTS", "recipient@example.com")

    # Refresh settings to pick up new environment variables
    refresh_settings()

    with caplog.at_level("ERROR"):
        email = settings.email_config()
        assert email is None
        assert "Invalid email configuration" in caplog.text


def test_email_use_tls_various_values(monkeypatch):
    """Test that USE_TLS accepts various boolean string representations."""
    from nexusLIMS.config import refresh_settings, settings

    test_cases = [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("no", False),
    ]

    for tls_value, expected in test_cases:
        monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("NX_EMAIL_SENDER", "sender@example.com")
        monkeypatch.setenv("NX_EMAIL_RECIPIENTS", "recipient@example.com")
        monkeypatch.setenv("NX_EMAIL_USE_TLS", tls_value)

        # Refresh settings to pick up new environment variables
        refresh_settings()

        assert settings.email_config().use_tls is expected


def test_settings_property_aliases(mock_nemo_env):
    """Test that property aliases work correctly."""
    from nexusLIMS.config import settings

    # Test nexuslims_instrument_data_path alias
    assert settings.nexuslims_instrument_data_path == settings.NX_INSTRUMENT_DATA_PATH

    # Test lock_file_path
    expected_lock = settings.NX_DATA_PATH / ".builder.lock"
    assert settings.lock_file_path == expected_lock

    # Test log_dir_path with default
    expected_log = settings.NX_DATA_PATH / "logs"
    assert settings.log_dir_path == expected_log

    # Test records_dir_path with default
    expected_records = settings.NX_DATA_PATH / "records"
    assert settings.records_dir_path == expected_records


def test_settings_proxy_callable(mock_nemo_env):
    """Test that callable attributes on the settings proxy work."""
    from nexusLIMS.config import settings

    # This test exercises the __getattr__ method of the _SettingsProxy class
    # for callable attributes (methods).
    harvesters = settings.nemo_harvesters()
    assert isinstance(harvesters, dict)


def test_settings_proxy_dir():
    """Exercise the __dir__ method of the _SettingsProxy class."""
    from nexusLIMS.config import settings

    assert "NX_CDCS_TOKEN" in dir(settings)


def test_settings_proxy_repr():
    """Exercise the __repr__ method of the _SettingsProxy class."""
    from nexusLIMS.config import settings

    assert repr(settings) == str(settings)


def test_settings_validation_error(monkeypatch, with_validation):
    """Test that a validation error during settings creation is logged and raised."""
    from pydantic import ValidationError

    from nexusLIMS.config import clear_settings, refresh_settings

    # Unset a required environment variable to create an invalid state
    monkeypatch.delenv("NX_CDCS_TOKEN", raising=False)

    # Clear any existing settings instance that was created at test startup
    # using the environment from conftest.py. This ensures the next access
    # will have to create a new instance using the now-modified environment.
    clear_settings()

    with pytest.raises(ValidationError) as exc_info:
        # refresh_settings() will now fail because it creates a new Settings
        # instance and NX_CDCS_TOKEN is missing.
        refresh_settings()

    # Verify the exception has the help note added (Python 3.11+)
    notes = "\n".join(exc_info.value.__notes__)
    assert "NexusLIMS configuration validation failed" in notes


def test_email_config_loads_from_dotenv_file(
    monkeypatch, mock_nemo_env, with_validation
):
    """Test that email_config loads variables from .env file when it exists."""
    from pathlib import Path
    from unittest.mock import Mock

    from nexusLIMS.config import refresh_settings, settings

    # Clear any email env vars that might be set in os.environ
    # (os.environ takes precedence over dotenv values in config.py)
    monkeypatch.delenv("NX_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("NX_EMAIL_SENDER", raising=False)
    monkeypatch.delenv("NX_EMAIL_RECIPIENTS", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("NX_EMAIL_SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("NX_EMAIL_USE_TLS", raising=False)

    # Mock Path.exists to return True for .env file (overriding isolated_from_dotenv)
    original_path_exists = Path.exists

    def mock_exists_allow_dotenv(self):
        # Allow .env to exist for this test
        if self.name == ".env":
            return True
        # Use the original patched behavior for other files
        return original_path_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists_allow_dotenv)

    # Mock dotenv_values to return email config as if loaded from .env file
    mock_dotenv_values = Mock(
        return_value={
            "NX_EMAIL_SMTP_HOST": "smtp.dotenv.com",
            "NX_EMAIL_SENDER": "dotenv@example.com",
            "NX_EMAIL_RECIPIENTS": "recipient@example.com",
            "NX_EMAIL_SMTP_PORT": "465",
        }
    )
    monkeypatch.setattr("nexusLIMS.config.dotenv_values", mock_dotenv_values)

    # Refresh settings to pick up changes
    refresh_settings()

    email = settings.email_config()

    # Verify dotenv_values was called
    assert mock_dotenv_values.called

    # Verify email config was loaded from .env file
    assert email is not None
    assert email.smtp_host == "smtp.dotenv.com"
    assert email.sender == "dotenv@example.com"
    assert email.recipients == ["recipient@example.com"]
    assert email.smtp_port == 465


def test_nemo_harvesters_loads_from_dotenv_file(
    monkeypatch, mock_nemo_env, with_validation
):
    """Test that nemo_harvesters loads variables from .env file when it exists."""
    from pathlib import Path
    from unittest.mock import Mock

    from nexusLIMS.config import refresh_settings, settings

    harvester_num = 10

    # Mock Path.exists to return True for .env file (overriding isolated_from_dotenv)
    original_path_exists = Path.exists

    def mock_exists_allow_dotenv(self):
        # Allow .env to exist for this test
        if self.name == ".env":
            return True
        # Use the original patched behavior for other files
        return original_path_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists_allow_dotenv)

    # Mock dotenv_values to return NEMO config as if loaded from .env file
    mock_dotenv_values = Mock(
        return_value={
            f"NX_NEMO_ADDRESS_{harvester_num}": "https://nemo10.dotenv.com/api/",
            f"NX_NEMO_TOKEN_{harvester_num}": "dotenv-token-123",
            f"NX_NEMO_TZ_{harvester_num}": "America/Los_Angeles",
        }
    )
    monkeypatch.setattr("nexusLIMS.config.dotenv_values", mock_dotenv_values)

    # Refresh settings to pick up changes
    refresh_settings()

    harvesters = settings.nemo_harvesters()

    # Verify dotenv_values was called
    assert mock_dotenv_values.called

    # Verify harvester config was loaded from .env file
    assert harvester_num in harvesters
    assert str(harvesters[10].address) == "https://nemo10.dotenv.com/api/"
    assert harvesters[10].token == "dotenv-token-123"
    assert harvesters[10].tz == "America/Los_Angeles"


def test_custom_log_and_records_paths(tmp_path, monkeypatch, mock_nemo_env):
    """Test NX_LOG_PATH and NX_RECORDS_PATH overrides."""
    from nexusLIMS.config import refresh_settings

    # Create custom directories
    custom_log = tmp_path / "custom_logs"
    custom_records = tmp_path / "custom_records"
    custom_log.mkdir()
    custom_records.mkdir()

    # Set environment variables
    monkeypatch.setenv("NX_LOG_PATH", str(custom_log))
    monkeypatch.setenv("NX_RECORDS_PATH", str(custom_records))

    # Refresh settings to pick up new environment variables
    settings = refresh_settings()

    assert settings.log_dir_path == custom_log
    assert settings.records_dir_path == custom_records
    assert custom_log == settings.NX_LOG_PATH
    assert custom_records == settings.NX_RECORDS_PATH


def test_elabftw_config_full(monkeypatch):
    """Test eLabFTW configuration with all fields."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_ELABFTW_API_KEY", "1-abcdef123456")
    monkeypatch.setenv("NX_ELABFTW_URL", "https://elabftw.example.com")
    monkeypatch.setenv("NX_ELABFTW_EXPERIMENT_CATEGORY", "5")
    monkeypatch.setenv("NX_ELABFTW_EXPERIMENT_STATUS", "3")

    # Refresh settings to pick up new environment variables
    refresh_settings()

    assert settings.NX_ELABFTW_API_KEY == "1-abcdef123456"
    # In TEST_MODE, URL is a string without trailing slash normalization
    assert str(settings.NX_ELABFTW_URL) == "https://elabftw.example.com"
    assert settings.NX_ELABFTW_EXPERIMENT_CATEGORY == 5
    assert settings.NX_ELABFTW_EXPERIMENT_STATUS == 3


def test_elabftw_config_minimal(monkeypatch):
    """Test eLabFTW configuration with only required fields."""
    from nexusLIMS.config import refresh_settings, settings

    # Only set API key and URL, not category/status
    monkeypatch.setenv("NX_ELABFTW_API_KEY", "2-test-key-minimal")
    monkeypatch.setenv("NX_ELABFTW_URL", "http://localhost:3148")
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_CATEGORY", raising=False)
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_STATUS", raising=False)

    # Refresh settings to pick up new environment variables
    refresh_settings()

    assert settings.NX_ELABFTW_API_KEY == "2-test-key-minimal"
    # In TEST_MODE, URL is a string without trailing slash normalization
    assert str(settings.NX_ELABFTW_URL) == "http://localhost:3148"
    # Optional fields should be None
    assert settings.NX_ELABFTW_EXPERIMENT_CATEGORY is None
    assert settings.NX_ELABFTW_EXPERIMENT_STATUS is None


def test_elabftw_config_not_configured(monkeypatch, with_validation):
    """Test eLabFTW config fields are None when not configured in production mode."""
    from nexusLIMS.config import refresh_settings, settings

    # Explicitly unset all eLabFTW environment variables
    monkeypatch.delenv("NX_ELABFTW_API_KEY", raising=False)
    monkeypatch.delenv("NX_ELABFTW_URL", raising=False)
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_CATEGORY", raising=False)
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_STATUS", raising=False)

    # Refresh settings to pick up new environment variables
    refresh_settings()

    # All fields should be None when not configured in production mode
    assert settings.NX_ELABFTW_API_KEY is None
    assert settings.NX_ELABFTW_URL is None
    assert settings.NX_ELABFTW_EXPERIMENT_CATEGORY is None
    assert settings.NX_ELABFTW_EXPERIMENT_STATUS is None


def test_elabftw_config_test_mode_defaults(monkeypatch):
    """Test that eLabFTW has appropriate defaults in TEST_MODE."""
    from nexusLIMS.config import TEST_MODE

    # This test only makes sense if TEST_MODE is enabled
    if not TEST_MODE:
        pytest.skip("TEST_MODE not enabled")

    # Unset any environment variables that might override TEST_MODE defaults
    # (e.g., from .env file loaded by cli.migrate module in other tests)
    monkeypatch.delenv("NX_ELABFTW_API_KEY", raising=False)
    monkeypatch.delenv("NX_ELABFTW_URL", raising=False)
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_CATEGORY", raising=False)
    monkeypatch.delenv("NX_ELABFTW_EXPERIMENT_STATUS", raising=False)

    from nexusLIMS.config import Settings

    # Create a fresh Settings instance (without environment overrides)
    # In TEST_MODE, it should have default values
    settings = Settings()

    # Verify test mode defaults
    assert settings.NX_ELABFTW_API_KEY == "1-" + "a" * 84
    # In TEST_MODE, URL is a string (not AnyHttpUrl), so no trailing slash normalization
    assert str(settings.NX_ELABFTW_URL) == "http://elabftw.localhost:40080"
    assert settings.NX_ELABFTW_EXPERIMENT_CATEGORY is None
    assert settings.NX_ELABFTW_EXPERIMENT_STATUS is None


def test_elabftw_api_key_format_validation(monkeypatch):
    """Test that various API key formats are accepted."""
    from nexusLIMS.config import refresh_settings, settings

    test_keys = [
        "1-" + "a" * 84,  # Format used in tests
        "42-" + "x" * 84,  # Different ID
        "999-" + "0" * 84,  # Numeric key portion
    ]

    for api_key in test_keys:
        monkeypatch.setenv("NX_ELABFTW_API_KEY", api_key)
        monkeypatch.setenv("NX_ELABFTW_URL", "http://localhost:3148")

        refresh_settings()

        assert api_key == settings.NX_ELABFTW_API_KEY


def test_elabftw_url_trailing_slash_normalized(monkeypatch, with_validation):
    """Test that eLabFTW URL gets normalized with trailing slash in production mode."""
    from nexusLIMS.config import refresh_settings, settings

    # Set URL without trailing slash
    monkeypatch.setenv("NX_ELABFTW_API_KEY", "1-testkey")
    monkeypatch.setenv("NX_ELABFTW_URL", "https://elabftw.example.com")

    refresh_settings()

    # URL should have trailing slash added by AnyHttpUrl validation
    # (with_validation fixture enables production mode where URLs are validated)
    assert str(settings.NX_ELABFTW_URL) == "https://elabftw.example.com/"


def test_elabftw_experiment_category_as_int(monkeypatch):
    """Test that experiment category is parsed as integer."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_ELABFTW_API_KEY", "1-test")
    monkeypatch.setenv("NX_ELABFTW_URL", "http://localhost:3148")
    monkeypatch.setenv("NX_ELABFTW_EXPERIMENT_CATEGORY", "42")

    refresh_settings()

    assert settings.NX_ELABFTW_EXPERIMENT_CATEGORY == 42
    assert isinstance(settings.NX_ELABFTW_EXPERIMENT_CATEGORY, int)


def test_elabftw_experiment_status_as_int(monkeypatch):
    """Test that experiment status is parsed as integer."""
    from nexusLIMS.config import refresh_settings, settings

    monkeypatch.setenv("NX_ELABFTW_API_KEY", "1-test")
    monkeypatch.setenv("NX_ELABFTW_URL", "http://localhost:3148")
    monkeypatch.setenv("NX_ELABFTW_EXPERIMENT_STATUS", "7")

    refresh_settings()

    assert settings.NX_ELABFTW_EXPERIMENT_STATUS == 7
    assert isinstance(settings.NX_ELABFTW_EXPERIMENT_STATUS, int)
