"""
Centralized environment variable management for NexusLIMS.

This module uses `pydantic-settings` to define, validate, and access
application settings from environment variables and .env files.
It provides a single source of truth for configuration, ensuring
type safety and simplifying access throughout the application.

The settings object can be imported and used throughout the application.
In tests, use refresh_settings() to reload settings after modifying
environment variables.
"""

import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from dotenv import dotenv_values
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    DirectoryPath,
    EmailStr,
    Field,
    FilePath,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from nexusLIMS.version import __version__

logger = logging.getLogger(__name__)


class NemoHarvesterConfig(BaseModel):
    """Configuration for a single NEMO harvester instance."""

    address: AnyHttpUrl = Field(
        ...,
        description=(
            "Full path to the root of the NEMO API, with trailing slash included "
            "(e.g., 'https://nemo.example.com/api/')"
        ),
    )
    token: str = Field(
        ...,
        description=(
            "Authentication token for the NEMO server. Obtain from the 'detailed "
            "administration' page of the NEMO installation."
        ),
    )
    strftime_fmt: str = Field(
        "%Y-%m-%dT%H:%M:%S%z",
        description=(
            "Format string to send datetime values to the NEMO API. Uses Python "
            "strftime syntax. Default is ISO 8601 format."
        ),
    )
    strptime_fmt: str = Field(
        "%Y-%m-%dT%H:%M:%S%z",
        description=(
            "Format string to parse datetime values from the NEMO API. Uses Python "
            "strptime syntax. Default is ISO 8601 format."
        ),
    )
    tz: str | None = Field(
        None,
        description=(
            "IANA timezone name (e.g., 'America/Denver') to coerce API datetime "
            "strings into. Only needed if the NEMO server doesn't return timezone "
            "information in API responses. If provided, overrides timezone from API."
        ),
    )

    @field_validator("address")
    @classmethod
    def validate_trailing_slash(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        """Ensure the API address has a trailing slash."""
        if not str(v).endswith("/"):
            msg = "NEMO address must end with a trailing slash"
            raise ValueError(msg)
        return v


class EmailConfig(BaseModel):
    """Config for email notifications from the nexuslims-process-records script."""

    smtp_host: str = Field(
        ...,
        description="SMTP server hostname (e.g., 'smtp.gmail.com')",
    )
    smtp_port: int = Field(
        587,
        description="SMTP server port (default: 587 for STARTTLS)",
    )
    smtp_username: str | None = Field(
        None,
        description="SMTP username for authentication (if required)",
    )
    smtp_password: str | None = Field(
        None,
        description="SMTP password for authentication (if required)",
    )
    use_tls: bool = Field(
        default=True,
        description="Use TLS encryption (default: True)",
    )
    sender: EmailStr = Field(
        ...,
        description="Email address to send from",
    )
    recipients: list[EmailStr] = Field(
        ...,
        description="List of recipient email addresses for error notifications",
    )


class Settings(BaseSettings):
    """
    Manage application settings loaded from environment variables and `.env` files.

    This class utilizes `pydantic-settings` to provide a robust and type-safe way
    to define, validate, and access all application configurations. It ensures
    that settings are loaded with proper types and provides descriptions for each.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables not defined here
    )

    NX_FILE_STRATEGY: Literal["exclusive", "inclusive"] = Field(
        "exclusive",
        description=(
            "Defines how file finding will behave: 'exclusive' (only files with "
            "explicit extractors) or 'inclusive' (all files, with basic metadata "
            "for others). Default is 'exclusive'."
        ),
    )
    NX_IGNORE_PATTERNS: list[str] = Field(
        ["*.mib", "*.db", "*.emi", "*.hdr"],
        description=(
            "List of glob patterns to ignore when searching for experiment files. "
            "Default is `['*.mib','*.db','*.emi','*.hdr']`."
        ),
    )
    NX_INSTRUMENT_DATA_PATH: DirectoryPath = Field(
        ...,
        description=(
            "Root path to the centralized file store for instrument data "
            "(mounted read-only). The directory must exist."
        ),
    )
    NX_DATA_PATH: DirectoryPath = Field(
        ...,
        description=(
            "Writable path parallel to NX_INSTRUMENT_DATA_PATH for "
            "extracted metadata and generated preview images. The directory must exist."
        ),
    )
    NX_DB_PATH: FilePath = Field(
        ...,
        description=(
            "The writable path to the NexusLIMS SQLite database that is used to get "
            "information about instruments and sessions that are built into records."
        ),
    )
    NX_CDCS_USER: str = Field(
        ...,
        description=(
            "The username used to authenticate to the CDCS API for uploading "
            "built records to the NexusLIMS front-end."
        ),
    )
    NX_CDCS_PASS: str = Field(
        ...,
        description=(
            "The password used to authenticate to the CDCS API for uploading "
            "built records to the NexusLIMS front-end."
        ),
    )
    NX_CDCS_URL: AnyHttpUrl = Field(
        ...,
        description=(
            "The root URL of the NexusLIMS CDCS front-end. This will be the target for "
            "record uploads that are authenticated using the CDCS credentials."
        ),
    )
    NX_CERT_BUNDLE_FILE: FilePath | None = Field(
        None,
        description=(
            "If needed, a custom SSL certificate CA bundle can be used to verify "
            "requests to the CDCS or NEMO APIs. Provide this value with the full "
            "path to a certificate bundle and any certificates provided in the "
            "bundle will be appended to the existing system for all requests made "
            "by NexusLIMS."
        ),
    )
    NX_CERT_BUNDLE: str | None = Field(
        None,
        description=(
            "As an alternative to NX_CERT_BUNDLE_FILE, to you can provide the entire "
            "certificate bundle as a single string (this can be useful for CI/CD "
            "pipelines). Lines should be separated by a single '\n' character If "
            "defined, this value will take precedence over NX_CERT_BUNDLE_FILE."
        ),
    )
    NX_FILE_DELAY_DAYS: float = Field(
        2.0,
        description=(
            "NX_FILE_DELAY_DAYS controls the maximum delay between observing a "
            "session ending and when the files are expected to be present. For the "
            "number of days set below (can be a fraction of a day, if desired), record "
            "building will not fail if no files are found, and the builder will search "
            'for again until the delay has passed. So if the value is "2", and a '
            "session ended Monday at 5PM, the record builder will continue to try "
            "looking for files until Wednesday at 5PM. "
        ),
        gt=0,
    )
    NX_LOG_PATH: DirectoryPath | None = Field(
        None,
        description=(
            "Directory for application logs. If not specified, defaults to "
            "NX_DATA_PATH/logs/. Logs are organized by date: logs/YYYY/MM/DD/"
        ),
    )
    NX_RECORDS_PATH: DirectoryPath | None = Field(
        None,
        description=(
            "Directory for generated XML records. If not specified, defaults to "
            "NX_DATA_PATH/records/. Successfully uploaded records are moved to "
            "a 'uploaded' subdirectory."
        ),
    )
    NX_LOCAL_PROFILES_PATH: DirectoryPath | None = Field(
        None,
        description=(
            "Directory for site-specific instrument profiles. These profiles "
            "customize metadata extraction for instruments unique to your deployment "
            "without modifying the core NexusLIMS codebase. Profile files should be "
            "Python modules that register InstrumentProfile objects. If not specified, "
            "only built-in profiles will be loaded."
        ),
    )

    @property
    def nexuslims_instrument_data_path(self) -> Path:
        """Alias for NX_INSTRUMENT_DATA_PATH for easier access."""
        return self.NX_INSTRUMENT_DATA_PATH

    @property
    def lock_file_path(self) -> Path:
        """Path to the record builder lock file."""
        return self.NX_DATA_PATH / ".builder.lock"

    @property
    def log_dir_path(self) -> Path:
        """Base directory for timestamped log files."""
        return self.NX_LOG_PATH if self.NX_LOG_PATH else self.NX_DATA_PATH / "logs"

    @property
    def records_dir_path(self) -> Path:
        """Base directory for generated XML records."""
        if self.NX_RECORDS_PATH:
            return self.NX_RECORDS_PATH
        return self.NX_DATA_PATH / "records"

    def nemo_harvesters(self) -> dict[int, NemoHarvesterConfig]:
        """
        Dynamically discover and parse all NEMO harvester configurations.

        Searches environment variables for NX_NEMO_ADDRESS_N patterns and
        constructs NemoHarvesterConfig objects for each numbered harvester.

        Returns
        -------
        dict[int, NemoHarvesterConfig]
            Dictionary mapping harvester number (1, 2, 3, ...) to configuration
            objects. Empty dict if no harvesters are configured.

        Examples
        --------
        With environment variables:

        ```python
        NX_NEMO_ADDRESS_1=https://nemo1.com/api/
        NX_NEMO_TOKEN_1=token123
        NX_NEMO_ADDRESS_2=https://nemo2.com/api/
        NX_NEMO_TOKEN_2=token456
        NX_NEMO_TZ_2=America/New_York
        ```

        The resulting output will be of the following format:

        ```python
        {
            1: NemoHarvesterConfig(
                address='https://nemo1.com/api/', token='token123', ...
            ),
            2: NemoHarvesterConfig(
                address='https://nemo2.com/api/',
                token='token456',
                tz='America/New_York',
                ...
            )
        }
        ```
        """
        harvesters = {}

        # Load .env file to get NEMO variables (Pydantic doesn't load
        # variables that aren't defined as fields)
        env_file_path = Path(".env")
        env_vars = {}
        if env_file_path.exists():
            env_vars = dotenv_values(env_file_path)

        # Merge with os.environ (os.environ takes precedence)
        all_env = {**env_vars, **os.environ}

        # Find all NX_NEMO_ADDRESS_N environment variables
        address_pattern = re.compile(r"^NX_NEMO_ADDRESS_(\d+)$")

        for env_var in all_env:
            match = address_pattern.match(env_var)
            if match:
                harvester_num = int(match.group(1))

                # Get required address and token
                address = all_env.get(f"NX_NEMO_ADDRESS_{harvester_num}")
                token = all_env.get(f"NX_NEMO_TOKEN_{harvester_num}")

                if not address or not token:
                    logger.warning(
                        "Skipping NEMO harvester %d: "
                        "both NX_NEMO_ADDRESS_%d and "
                        "NX_NEMO_TOKEN_%d must be set",
                        harvester_num,
                        harvester_num,
                        harvester_num,
                    )
                    continue

                # Build config dict with optional fields
                config_dict = {
                    "address": address,
                    "token": token,
                }

                # Add optional fields if present
                if strftime_fmt := all_env.get(f"NX_NEMO_STRFTIME_FMT_{harvester_num}"):
                    config_dict["strftime_fmt"] = strftime_fmt

                if strptime_fmt := all_env.get(f"NX_NEMO_STRPTIME_FMT_{harvester_num}"):
                    config_dict["strptime_fmt"] = strptime_fmt

                if tz := all_env.get(f"NX_NEMO_TZ_{harvester_num}"):
                    config_dict["tz"] = tz

                try:
                    harvesters[harvester_num] = NemoHarvesterConfig(**config_dict)
                except ValidationError:
                    logger.exception(
                        "Invalid configuration for NEMO harvester %d",
                        harvester_num,
                    )
                    raise

        return harvesters

    def email_config(self) -> EmailConfig | None:
        """
        Load email configuration from environment variables if available.

        This method is cached per Settings instance for performance.

        Returns
        -------
        EmailConfig | None
            Email configuration object if all required settings are present,
            None otherwise (email notifications will be disabled).

        Examples
        --------
        With environment variables:

        ```python
        NX_EMAIL_SMTP_HOST=smtp.gmail.com
        NX_EMAIL_SENDER=nexuslims@example.com
        NX_EMAIL_RECIPIENTS=admin@example.com,team@example.com
        ```

        Optional variables:

        ```python
        NX_EMAIL_SMTP_PORT=587
        NX_EMAIL_SMTP_USERNAME=user@example.com
        NX_EMAIL_SMTP_PASSWORD=secret
        NX_EMAIL_USE_TLS=true
        ```
        """
        # Load .env file to get email variables
        env_file_path = Path(".env")
        env_vars = {}
        if env_file_path.exists():
            env_vars = dotenv_values(env_file_path)

        # Merge with os.environ (os.environ takes precedence)
        all_env = {**env_vars, **os.environ}

        # Check if required email vars are present
        smtp_host = all_env.get("NX_EMAIL_SMTP_HOST")
        sender = all_env.get("NX_EMAIL_SENDER")
        recipients_str = all_env.get("NX_EMAIL_RECIPIENTS")

        if not all([smtp_host, sender, recipients_str]):
            return None  # Email not configured

        recipients = [r.strip() for r in recipients_str.split(",")]

        config_dict = {
            "smtp_host": smtp_host,
            "sender": sender,
            "recipients": recipients,
        }

        # Add optional fields
        if smtp_port := all_env.get("NX_EMAIL_SMTP_PORT"):
            config_dict["smtp_port"] = int(smtp_port)
        if smtp_username := all_env.get("NX_EMAIL_SMTP_USERNAME"):
            config_dict["smtp_username"] = smtp_username
        if smtp_password := all_env.get("NX_EMAIL_SMTP_PASSWORD"):
            config_dict["smtp_password"] = smtp_password
        if use_tls := all_env.get("NX_EMAIL_USE_TLS"):
            config_dict["use_tls"] = use_tls.lower() in ("true", "1", "yes")

        try:
            return EmailConfig(**config_dict)
        except ValidationError:
            logger.exception("Invalid email configuration")
            return None


class _SettingsManager:
    """
    Internal manager for the settings singleton.

    Provides a refresh mechanism for testing while maintaining
    the convenient import pattern for production code.
    """

    def __init__(self):
        self._settings: Settings | None = None

    def get(self) -> Settings:
        """Get the current settings instance, creating if needed."""
        if self._settings is None:
            self._settings = self._create()
        return self._settings

    def _create(self) -> Settings:
        """Create a new Settings instance."""
        try:
            return Settings()
        except ValidationError as e:
            # Add help message to exception using add_note (Python 3.11+)
            # This appears after the exception traceback
            # Strip .dev* suffix from version for documentation link
            doc_version = re.sub(r"\.dev.*$", "", __version__)
            help_msg = (
                "\n" + "=" * 80 + "\n"
                "NexusLIMS configuration validation failed.\n"
                f"See https://datasophos.github.io/NexusLIMS/v{doc_version}/configuration.html\n"
                "for complete environment variable reference.\n" + "=" * 80
            )
            if hasattr(e, "add_note"):
                e.add_note(help_msg)
            raise

    def refresh(self) -> Settings:
        """
        Refresh settings from current environment variables.

        Creates a new Settings instance and replaces the cached singleton.
        Primarily used in testing when environment variables are modified.

        Returns
        -------
        Settings
            The newly created settings instance

        Examples
        --------
        >>> import os
        >>> from nexusLIMS.config import settings, refresh_settings
        >>>
        >>> # In a test, modify environment
        >>> os.environ["NX_FILE_STRATEGY"] = "inclusive"
        >>>
        >>> # Refresh to pick up changes
        >>> refresh_settings()
        >>>
        >>> assert settings.NX_FILE_STRATEGY == "inclusive"
        """
        self._settings = self._create()
        return self._settings

    def clear(self) -> None:
        """
        Clear the settings cache.

        The next access to settings will create a new instance.
        This is equivalent to refresh() but doesn't immediately create
        a new instance.
        """
        self._settings = None


if TYPE_CHECKING:
    # For type checkers, make the proxy look like Settings
    # This gives us proper type hints and autocomplete
    class _SettingsProxy(Settings):  # type: ignore[misc]
        """Type stub for the settings proxy."""

else:

    class _SettingsProxy:
        """
        Proxy that provides attribute access to the current settings instance.

        This allows settings to be used like a normal object while supporting
        the refresh mechanism for testing.
        """

        def __getattr__(self, name: str):
            # Get the attribute from the actual Settings instance
            attr = getattr(_manager.get(), name)

            # If it's a method, wrap it to ensure it's called on the right instance
            if callable(attr):

                def method_wrapper(*args, **kwargs):
                    # Re-get the attribute from the current Settings instance
                    # in case it was refreshed between getting the method and calling it
                    current_attr = getattr(_manager.get(), name)
                    return current_attr(*args, **kwargs)

                return method_wrapper

            return attr

        def __dir__(self):
            return dir(_manager.get())

        def __repr__(self):
            return repr(_manager.get())


# Create the settings manager
_manager = _SettingsManager()


def refresh_settings() -> Settings:
    """
    Refresh the settings singleton from current environment variables.

    This forces a reload of all settings from the environment.
    Primarily useful for testing.

    Returns
    -------
    Settings
        The newly created settings instance

    Examples
    --------
    >>> from nexusLIMS.config import settings, refresh_settings
    >>> import os
    >>>
    >>> os.environ["NX_FILE_STRATEGY"] = "inclusive"
    >>> refresh_settings()
    >>>
    >>> assert settings.NX_FILE_STRATEGY == "inclusive"
    """
    return _manager.refresh()


def clear_settings() -> None:
    """
    Clear the settings cache without immediately creating a new instance.

    The next import or access to settings will create a fresh instance.
    Useful in test teardown to ensure clean state.
    """
    _manager.clear()


# The settings "singleton" - accessed like a normal object throughout the application
settings = _SettingsProxy()
