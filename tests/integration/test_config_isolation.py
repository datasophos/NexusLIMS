"""
Test configuration isolation in integration tests.

This module ensures that integration tests are properly isolated from
local environment configuration files (.env) to prevent test contamination.
"""

import os
from pathlib import Path


def test_test_mode_enabled():
    """Verify NX_TEST_MODE is properly set."""
    assert os.environ.get("NX_TEST_MODE", "").lower() in (
        "true",
        "1",
        "yes",
    ), "NX_TEST_MODE must be enabled for integration tests"


def test_env_file_not_loaded_in_test_mode(monkeypatch, tmp_path):
    """
    Verify that .env files are NOT loaded when NX_TEST_MODE is enabled.

    This is CRITICAL for test isolation - we must ensure that local
    environment configuration does not contaminate test runs.
    """
    # Create a fake .env file with a poison value
    fake_env_file = tmp_path / ".env"
    fake_env_file.write_text("NX_CDCS_TOKEN=POISON_VALUE_FROM_ENV_FILE\n")

    # Change to the temporary directory (so Settings would find .env if it looked)
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Clear and refresh settings to force a reload
        from nexusLIMS.config import clear_settings, refresh_settings, settings

        clear_settings()

        # Set required environment variables for Settings validation
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(tmp_path / "instrument_data"))
        monkeypatch.setenv("NX_DATA_PATH", str(tmp_path / "data"))
        monkeypatch.setenv("NX_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("NX_CDCS_URL", "http://test.example.com")
        monkeypatch.setenv("NX_CDCS_TOKEN", "SAFE_TOKEN_FROM_ENVIRON")

        # Create required directories and database for validation
        (tmp_path / "instrument_data").mkdir(exist_ok=True)
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "test.db").touch(exist_ok=True)

        # Refresh settings - this should NOT load from .env in TEST_MODE
        refresh_settings()

        # Verify that the token comes from os.environ, NOT from .env
        assert settings.NX_CDCS_TOKEN == "SAFE_TOKEN_FROM_ENVIRON", (
            "Settings loaded from .env file instead of os.environ in TEST_MODE!"
        )

        # Verify the poison value was NOT loaded
        assert settings.NX_CDCS_TOKEN != "POISON_VALUE_FROM_ENV_FILE", (
            "CRITICAL: .env file was loaded in TEST_MODE! Test isolation is broken!"
        )

    finally:
        # Restore original directory
        os.chdir(original_cwd)


def test_nemo_harvesters_no_env_file_in_test_mode(monkeypatch, tmp_path):
    """
    Verify that nemo_harvesters() does NOT load from .env in TEST_MODE.

    The nemo_harvesters() method dynamically loads NEMO configuration
    from environment variables. It must NOT load from .env files in TEST_MODE.
    """
    # Create a fake .env file with poison NEMO config
    fake_env_file = tmp_path / ".env"
    fake_env_file.write_text(
        "NX_NEMO_ADDRESS_1=http://poison.example.com/api/\n"
        "NX_NEMO_TOKEN_1=POISON_NEMO_TOKEN\n"
    )

    # Change to the temporary directory
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Set up safe NEMO config in os.environ
        monkeypatch.setenv("NX_NEMO_ADDRESS_2", "http://safe.example.com/api/")
        monkeypatch.setenv("NX_NEMO_TOKEN_2", "SAFE_NEMO_TOKEN")

        # Set up required Settings fields
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(tmp_path / "instrument_data"))
        monkeypatch.setenv("NX_DATA_PATH", str(tmp_path / "data"))
        monkeypatch.setenv("NX_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("NX_CDCS_URL", "http://test.example.com")
        monkeypatch.setenv("NX_CDCS_TOKEN", "test_token")

        # Create required directories and database
        (tmp_path / "instrument_data").mkdir(exist_ok=True)
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "test.db").touch(exist_ok=True)

        # Refresh settings and get NEMO harvesters
        from nexusLIMS.config import clear_settings, refresh_settings, settings

        clear_settings()
        refresh_settings()

        harvesters = settings.nemo_harvesters()

        # Verify that only harvester #2 (from os.environ) is loaded
        assert 2 in harvesters, "Should have loaded harvester #2 from os.environ"
        assert 1 not in harvesters, (
            "CRITICAL: Harvester #1 from .env file was loaded in TEST_MODE!"
        )

        # Verify harvester #2 has the safe values
        assert harvesters[2].address == "http://safe.example.com/api/"
        assert harvesters[2].token == "SAFE_NEMO_TOKEN"

    finally:
        os.chdir(original_cwd)


def test_email_config_no_env_file_in_test_mode(monkeypatch, tmp_path):
    """
    Verify that email_config() does NOT load from .env in TEST_MODE.

    The email_config() method dynamically loads email configuration
    from environment variables. It must NOT load from .env files in TEST_MODE.
    """
    # Create a fake .env file with poison email config
    fake_env_file = tmp_path / ".env"
    fake_env_file.write_text(
        "NX_EMAIL_SMTP_HOST=poison.smtp.example.com\n"
        "NX_EMAIL_SENDER=poison@example.com\n"
        "NX_EMAIL_RECIPIENTS=poison1@example.com,poison2@example.com\n"
    )

    # Change to the temporary directory
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        # Set up safe email config in os.environ
        monkeypatch.setenv("NX_EMAIL_SMTP_HOST", "safe.smtp.example.com")
        monkeypatch.setenv("NX_EMAIL_SENDER", "safe@example.com")
        monkeypatch.setenv("NX_EMAIL_RECIPIENTS", "safe@example.com")

        # Set up required Settings fields
        monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(tmp_path / "instrument_data"))
        monkeypatch.setenv("NX_DATA_PATH", str(tmp_path / "data"))
        monkeypatch.setenv("NX_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("NX_CDCS_URL", "http://test.example.com")
        monkeypatch.setenv("NX_CDCS_TOKEN", "test_token")

        # Create required directories and database
        (tmp_path / "instrument_data").mkdir(exist_ok=True)
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "test.db").touch(exist_ok=True)

        # Refresh settings and get email config
        from nexusLIMS.config import clear_settings, refresh_settings, settings

        clear_settings()
        refresh_settings()

        email_config = settings.email_config()

        # Verify that email config comes from os.environ, NOT .env
        assert email_config is not None, "Email config should be loaded from os.environ"
        assert email_config.smtp_host == "safe.smtp.example.com"
        assert email_config.sender == "safe@example.com"
        assert email_config.recipients == ["safe@example.com"]

        # Verify poison values were NOT loaded
        assert email_config.smtp_host != "poison.smtp.example.com"
        assert email_config.sender != "poison@example.com"

    finally:
        os.chdir(original_cwd)


def test_all_config_values_have_safe_defaults_in_test_mode():
    """
    Verify that all Settings fields either have test defaults or are optional.

    This ensures that tests can run without requiring every config value
    to be explicitly set in fixtures.
    """
    from nexusLIMS.config import settings

    # These are the required fields that MUST be set (no defaults)
    # They should be set in pytest_configure or test fixtures
    required_fields = {
        "NX_INSTRUMENT_DATA_PATH",
        "NX_DATA_PATH",
        "NX_DB_PATH",
        "NX_CDCS_TOKEN",
        "NX_CDCS_URL",
    }

    # Verify all required fields are set
    for field in required_fields:
        value = getattr(settings, field)
        assert value is not None, f"Required field {field} is not set in test mode"
        assert value != "", f"Required field {field} is empty in test mode"

    # These fields should have safe defaults or be optional
    # Just verify they can be accessed without errors
    optional_or_defaulted_fields = [
        "NX_FILE_STRATEGY",
        "NX_IGNORE_PATTERNS",
        "NX_EXPORT_STRATEGY",
        "NX_CERT_BUNDLE_FILE",
        "NX_CERT_BUNDLE",
        "NX_DISABLE_SSL_VERIFY",
        "NX_FILE_DELAY_DAYS",
        "NX_CLUSTERING_SENSITIVITY",
        "NX_LOG_PATH",
        "NX_RECORDS_PATH",
        "NX_LOCAL_PROFILES_PATH",
        "NX_ELABFTW_API_KEY",
        "NX_ELABFTW_URL",
        "NX_ELABFTW_EXPERIMENT_CATEGORY",
        "NX_ELABFTW_EXPERIMENT_STATUS",
    ]

    for field in optional_or_defaulted_fields:
        # Should not raise an exception
        _ = getattr(settings, field)
