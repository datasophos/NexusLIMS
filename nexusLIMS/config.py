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

_logger = logging.getLogger(__name__)

# ============================================================================
# TEST MODE: Disable Pydantic validation when running tests
# ============================================================================
# Check if we're in test mode BEFORE defining the Settings class
# This allows tests to control the environment setup without validation errors
TEST_MODE = os.getenv("NX_TEST_MODE", "").lower() in ("true", "1", "yes")

if TEST_MODE:
    _logger.warning("NX_TEST_MODE enabled - Pydantic validation disabled")

# Type aliases that conditionally use strict validation types or plain Path
# based on TEST_MODE. When TEST_MODE=True, use Path (no existence validation).
# When TEST_MODE=False, use DirectoryPath/FilePath (validates existence).
if TYPE_CHECKING:
    # For type checkers, always use the strict types for proper type hints
    TestAwareDirectoryPath = DirectoryPath
    TestAwareFilePath = FilePath
    TestAwareHttpUrl = AnyHttpUrl
    TestAwareEmailStr = EmailStr
else:
    # At runtime, conditionally use strict or lenient types
    TestAwareDirectoryPath = Path if TEST_MODE else DirectoryPath
    TestAwareFilePath = Path if TEST_MODE else FilePath
    TestAwareHttpUrl = str if TEST_MODE else AnyHttpUrl
    TestAwareEmailStr = str if TEST_MODE else EmailStr


class NemoHarvesterConfig(BaseModel):
    """Configuration for a single NEMO harvester instance."""

    # Uses TestAwareHttpUrl which is str in test mode, AnyHttpUrl in production
    address: TestAwareHttpUrl = Field(  # type: ignore[valid-type]
        "http://localhost:8080/api/" if TEST_MODE else ...,
        description=(
            "Full path to the root of the NEMO API, with trailing slash included "
            "(e.g., `https://nemo.example.com/api/`)"
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The full URL to the NEMO API root endpoint, including the trailing "
                "slash. For example: `https://nemo.yourinstitution.edu/api/`. This "
                "must point to the API root, not the NEMO web interface itself.\n\n"
                "You can verify the address is correct by navigating to it in a "
                "browser — a valid NEMO API root returns a JSON object listing "
                "available endpoints."
            ),
        },
    )
    token: str = Field(
        "test_nemo_token" if TEST_MODE else ...,
        description=(
            "Authentication token for the NEMO server. Obtain from the 'detailed "
            "administration' page of the NEMO installation."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The API authentication token for this NEMO server instance. To "
                "obtain: log in to NEMO as an administrator, navigate to the "
                "'Detailed administration' page (typically at "
                "`/admin/authtoken/token/`), and locate or create a token for the "
                "NexusLIMS service account. The token is a 40-character hex string."
            ),
        },
    )
    strftime_fmt: str = Field(
        "%Y-%m-%dT%H:%M:%S%z",
        description=(
            "Format string to send datetime values to the NEMO API. Uses Python "
            "strftime syntax. Default is ISO 8601 format."
        ),
        json_schema_extra={
            "detail": (
                "The Python strftime format string used when sending datetime values "
                "to this NEMO API instance. The default `%Y-%m-%dT%H:%M:%S%z` is "
                "ISO 8601 and works with all standard NEMO installations.\n\n"
                "Only change this if your NEMO server has a non-standard date format "
                "configuration. See https://docs.python.org/3/library/datetime.html"
                "#strftime-and-strptime-format-codes for format codes."
            )
        },
    )
    strptime_fmt: str = Field(
        "%Y-%m-%dT%H:%M:%S%z",
        description=(
            "Format string to parse datetime values from the NEMO API. Uses Python "
            "strptime syntax. Default is ISO 8601 format."
        ),
        json_schema_extra={
            "detail": (
                "The Python strptime format string used when parsing datetime values "
                "returned by this NEMO API instance. The default "
                "`%Y-%m-%dT%H:%M:%S%z` "
                "is ISO 8601 and works with all standard NEMO installations.\n\n"
                "Only change this if your NEMO server returns dates in a non-standard "
                "format. See https://docs.python.org/3/library/datetime.html"
                "#strftime-and-strptime-format-codes for format codes."
            )
        },
    )
    tz: str | None = Field(
        None,
        description=(
            "IANA timezone name (e.g., `America/Denver`) to coerce API datetime "
            "strings into. Only needed if the NEMO server doesn't return timezone "
            "information in API responses. If provided, overrides timezone from API."
        ),
        json_schema_extra={
            "detail": (
                "An IANA tz database timezone name (e.g., `America/Denver`, "
                "`Europe/Berlin`) to force onto datetime values received from this "
                "NEMO server. Only needed when your NEMO server returns "
                "reservation/usage event times without timezone information.\n\n"
                "Leave blank for NEMO servers that include timezone info in their "
                "API responses. See "
                "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones "
                "for valid timezone names."
            )
        },
    )

    @field_validator("address")
    @classmethod
    def validate_trailing_slash(cls, v: str | AnyHttpUrl) -> str | AnyHttpUrl:
        """Ensure the API address has a trailing slash."""
        if TEST_MODE:
            return v  # Skip validation in test mode
        if not str(v).endswith("/"):
            msg = "NEMO address must end with a trailing slash"
            raise ValueError(msg)
        return v


class EmailConfig(BaseModel):
    """Config for email notifications from the nexuslims-process-records script."""

    smtp_host: str = Field(
        "localhost" if TEST_MODE else ...,
        description="SMTP server hostname (e.g., 'smtp.gmail.com')",
        json_schema_extra={
            "required": True,
            "detail": (
                "The hostname or IP address of the SMTP server used to send "
                "error notification emails. For Gmail use `smtp.gmail.com`, for "
                "Outlook/Office365 use `smtp.office365.com`. For an on-premises "
                "mail relay this is typically a local hostname or IP address."
            ),
        },
    )
    smtp_port: int = Field(
        587,
        description="SMTP server port (default: 587 for STARTTLS)",
        json_schema_extra={
            "detail": (
                "The TCP port for the SMTP connection. Common values:\n"
                "  `587` — STARTTLS (recommended, default)\n"
                "  `465` — SMTPS / implicit TLS\n"
                "  `25`  — unencrypted (not recommended)\n\n"
                "The default `587` works with most modern mail servers when "
                "Use TLS is enabled."
            )
        },
    )
    smtp_username: str | None = Field(
        None,
        description="SMTP username for authentication (if required)",
        json_schema_extra={
            "detail": (
                "The username for SMTP authentication. For Gmail this is your "
                "full email address. Leave blank if your SMTP relay does not "
                "require authentication (e.g., an internal relay that accepts "
                "connections from trusted hosts without credentials)."
            )
        },
    )
    smtp_password: str | None = Field(
        None,
        description="SMTP password for authentication (if required)",
        json_schema_extra={
            "detail": (
                "The password for SMTP authentication. For Gmail, use an App "
                "Password (not your account password) if 2-factor authentication "
                "is enabled. Leave blank if your SMTP relay does not require "
                "authentication."
            )
        },
    )
    use_tls: bool = Field(
        default=True,
        description="Use TLS encryption (default: True)",
        json_schema_extra={
            "detail": (
                "Whether to use TLS encryption for the SMTP connection. When "
                "enabled (the default), NexusLIMS uses STARTTLS on the configured "
                "port (typically 587). Disable only when connecting to a plaintext "
                "SMTP relay on port 25."
            )
        },
    )
    sender: TestAwareEmailStr = Field(  # type: ignore[valid-type]
        "test@example.com" if TEST_MODE else ...,
        description="Email address to send from",
        json_schema_extra={
            "required": True,
            "detail": (
                "The 'From' email address for notification messages. This must "
                "be an address that your SMTP server is authorized to send from. "
                "If using Gmail or similar services, this must match the "
                "authenticated account's address."
            ),
        },
    )
    recipients: list[TestAwareEmailStr] = Field(  # type: ignore[valid-type]
        ["test@example.com"] if TEST_MODE else ...,
        description="List of recipient email addresses for error notifications",
        json_schema_extra={
            "required": True,
            "detail": (
                "One or more email addresses that will receive error notification "
                "messages when the record builder encounters problems. Provide as "
                "a comma-separated string, e.g.:\n"
                "  `NX_EMAIL_RECIPIENTS='admin@example.com,team@example.com'`\n\n"
                "Notifications are sent when `nexuslims-process-records` detects "
                "ERROR-level log entries."
            ),
        },
    )


class Settings(BaseSettings):
    """
    Manage application settings loaded from environment variables and `.env` files.

    This class utilizes `pydantic-settings` to provide a robust and type-safe way
    to define, validate, and access all application configurations. It ensures
    that settings are loaded with proper types and provides descriptions for each.
    """

    model_config = SettingsConfigDict(
        # CRITICAL: Disable .env file loading in TEST_MODE to prevent contamination
        # from local environment files during testing
        env_file=None if TEST_MODE else ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables not defined here
        # In test mode, disable path validation to allow non-existent paths
        validate_default=not TEST_MODE,
    )

    NX_FILE_STRATEGY: Literal["exclusive", "inclusive"] = Field(
        "exclusive",
        description=(
            "Defines how file finding will behave: 'exclusive' (only files with "
            "explicit extractors) or 'inclusive' (all files, with basic metadata "
            "for others). Default is 'exclusive'."
        ),
        json_schema_extra={
            "detail": (
                "Controls which files are included when searching for experiment "
                "data.\n\n"
                "`exclusive` (default): Only files for which NexusLIMS has an explicit "
                "metadata extractor are included. This produces cleaner records but "
                "may miss ancillary files.\n\n"
                "`inclusive`: All files within the session window are included. Files "
                "without a known extractor receive basic filesystem metadata only. "
                "Useful when you want a complete audit trail of every file created "
                "during an instrument session.\n\n"
                "See https://datasophos.github.io/NexusLIMS/stable/"
                "user_guide/extractors.html "
                "for the list of supported file formats and their extractors."
            )
        },
    )
    NX_IGNORE_PATTERNS: list[str] = Field(
        ["*.mib", "*.db", "*.emi", "*.hdr"],
        description=(
            "List of glob patterns to ignore when searching for experiment files. "
            "Default is `['*.mib','*.db','*.emi','*.hdr']`."
        ),
        json_schema_extra={
            "detail": (
                "Filename glob patterns to exclude when scanning for experiment files. "
                "Patterns follow the same syntax as the '-name' argument to GNU find "
                "(see https://manpages.org/find).\n\n"
                "This is stored in the config file as a JSON array string:\n"
                '  `NX_IGNORE_PATTERNS=\'["*.mib","*.db","*.emi","*.hdr"]\'`\n\n'
                "In the config editor, enter patterns as a comma-separated list.\n\n"
                "Common patterns to ignore:\n"
                "  `*.mib`  — Merlin detector raw frames (very large)\n"
                "  `*.db`   — SQLite lock/temp files\n"
                "  `*.emi`  — FEI TIA sidecar files (paired with .ser via FEI EMI "
                "extractor)\n"
                "  `*.hdr`  — header files paired with other data formats"
            )
        },
    )
    # Use TestAware types which are strict in production, lenient in test mode
    NX_INSTRUMENT_DATA_PATH: TestAwareDirectoryPath = Field(  # type: ignore[valid-type]
        Path("/tmp") / "test_instrument_data" if TEST_MODE else ...,  # noqa: S108
        description=(
            "Root path to the centralized file store for instrument data "
            "(mounted read-only). The directory must exist."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The root path to the centralized instrument data file store — "
                "typically a network share or mounted volume containing subdirectories "
                "for each instrument.\n\n"
                "IMPORTANT: This path should be mounted read-only to ensure data "
                "preservation. NexusLIMS will never write to this location.\n\n"
                "The `filestore_path` column in the NexusLIMS instruments database "
                "stores paths relative to this root. For example, if an instrument "
                "has `filestore_path='FEI_Titan/data'` and this value is "
                "`/mnt/instrument_data`, NexusLIMS searches under "
                "`/mnt/instrument_data/FEI_Titan/data`."
            ),
        },
    )
    NX_DATA_PATH: TestAwareDirectoryPath = Field(  # type: ignore[valid-type]
        Path("/tmp") / "test_data" if TEST_MODE else ...,  # noqa: S108
        description=(
            "Writable path parallel to NX_INSTRUMENT_DATA_PATH for "
            "extracted metadata and generated preview images. The directory must exist."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "A writable path that mirrors the directory structure of "
                "`NX_INSTRUMENT_DATA_PATH`. NexusLIMS writes extracted metadata files "
                "and generated preview images here, alongside the original data.\n\n"
                "This path must be accessible to the NexusLIMS CDCS frontend instance "
                "so it can serve preview images and metadata files to users browsing "
                "records. Configure your CDCS deployment to mount or serve files from "
                "this location."
            ),
        },
    )
    NX_DB_PATH: TestAwareFilePath = Field(  # type: ignore[valid-type]
        Path("/tmp") / "test.db" if TEST_MODE else ...,  # noqa: S108
        description=(
            "The writable path to the NexusLIMS SQLite database that is used to get "
            "information about instruments and sessions that are built into records."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The full filesystem path to the NexusLIMS SQLite database file. "
                "\n\n"
                "Must be writable by the NexusLIMS process. The database is created "
                "automatically on first run of `nexuslims-migrate init`. Recommended "
                "location: within `NX_DATA_PATH` for co-location with other data."
            ),
        },
    )
    NX_CDCS_TOKEN: str = Field(
        "test_token" if TEST_MODE else ...,
        description=(
            "API token for authenticating to the CDCS API for uploading "
            "built records to the NexusLIMS front-end."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The API authentication token for the NexusLIMS CDCS frontend. "
                "Used for all record upload requests.\n\n"
                "To obtain: log in to your CDCS instance as an administrator, navigate "
                "to the admin panel, and find or create an API token for the NexusLIMS "
                "service account. Alternatively, use the CDCS REST API token "
                "endpoint.\n\n"
                "Keep this value secret — anyone with this token can upload records "
                "to your CDCS instance."
            ),
        },
    )
    NX_CDCS_URL: TestAwareHttpUrl = Field(  # type: ignore[valid-type]
        "http://localhost:8000" if TEST_MODE else ...,
        description=(
            "The root URL of the NexusLIMS CDCS front-end. This will be the target for "
            "record uploads that are authenticated using the CDCS credentials."
        ),
        json_schema_extra={
            "required": True,
            "detail": (
                "The root URL of the NexusLIMS CDCS frontend instance. All record "
                "uploads are sent here using `NX_CDCS_TOKEN`.\n\n"
                "Include the trailing slash: `https://nexuslims.example.com/`\n\n"
                "This is the same URL users visit to browse experiment records. "
                "NexusLIMS POSTs new XML records to the CDCS REST API at this address."
            ),
        },
    )
    NX_EXPORT_STRATEGY: Literal["all", "first_success", "best_effort"] = Field(
        "all",
        description=(
            "Strategy for exporting records to multiple destinations. "
            "'all': All destinations must succeed (recommended). "
            "'first_success': Stop after first successful export. "
            "'best_effort': Try all destinations, succeed if any succeed."
        ),
        json_schema_extra={
            "detail": (
                "Controls behavior when exporting records to multiple destinations "
                "(e.g., both CDCS and eLabFTW are configured):\n\n"
                "`all` (default, recommended): Every configured destination must "
                "accept the record. If any destination fails, the session is marked "
                "`ERROR` and retried on the next run.\n\n"
                "`first_success`: Stop after the first destination that accepts the "
                "record. Useful if destinations are fallbacks for each other.\n\n"
                "`best_effort`: Attempt all destinations; mark `COMPLETED` if at least "
                "one succeeds. Failed destinations are logged but do not trigger "
                "a retry."
            )
        },
    )
    NX_CERT_BUNDLE_FILE: TestAwareFilePath | None = Field(
        None,
        description=(
            "If needed, a custom SSL certificate CA bundle can be used to verify "
            "requests to the CDCS or NEMO APIs. Provide this value with the full "
            "path to a certificate bundle and any certificates provided in the "
            "bundle will be appended to the existing system for all requests made "
            "by NexusLIMS."
        ),
        json_schema_extra={
            "detail": (
                "Path to a custom SSL/TLS CA bundle file in PEM format. Use this "
                "when your CDCS or NEMO servers use certificates signed by a private "
                "or institutional CA not in the system trust store.\n\n"
                "Any certificates in this bundle are appended to the existing system "
                "CA certificates — they do not replace them. Provide the full absolute "
                "path to the `.pem` or `.crt` file.\n\n"
                "If both `NX_CERT_BUNDLE` and `NX_CERT_BUNDLE_FILE` are set, "
                "`NX_CERT_BUNDLE` takes precedence."
            )
        },
    )
    NX_CERT_BUNDLE: str | None = Field(
        None,
        description=(
            "As an alternative to NX_CERT_BUNDLE_FILE, to you can provide the entire "
            "certificate bundle as a single string (this can be useful for CI/CD "
            "pipelines). If defined, this value will take precedence over "
            "NX_CERT_BUNDLE_FILE."
        ),
        json_schema_extra={
            "detail": (
                "The full text of a PEM-format CA certificate bundle, provided "
                "directly as a string rather than a file path. Certificate lines "
                "should be separated by '\\n' in the .env file, or just "
                "pasted into the config editor field.\n\n"
                "This is primarily useful in CI/CD pipelines or containerized "
                "deployments where injecting a certificate file is impractical but "
                "environment variables are easy to set as secrets.\n\n"
                "When defined, this value takes precedence over `NX_CERT_BUNDLE_FILE`."
            )
        },
    )
    NX_DISABLE_SSL_VERIFY: bool = Field(
        default=False,
        description=(
            "Disable SSL certificate verification for all outgoing HTTPS requests. "
            "This should ONLY be used during local development or testing with "
            "self-signed certificates. Never enable this in production."
        ),
        json_schema_extra={
            "detail": (
                "WARNING: Disables SSL certificate verification for ALL outgoing "
                "HTTPS requests, including connections to CDCS, NEMO, and eLabFTW.\n\n"
                "NEVER enable this in production. An attacker could intercept all "
                "communications including API tokens and uploaded records.\n\n"
                "Only appropriate for local development or testing with self-signed "
                "certificates when setting up a CA via `NX_CERT_BUNDLE_FILE` is "
                "impractical. If you need this in production, configure "
                "`NX_CERT_BUNDLE_FILE` instead."
            )
        },
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
        json_schema_extra={
            "detail": (
                "The maximum time (in days) to wait for instrument files to appear "
                "after a session ends before giving up.\n\n"
                "Background: On some systems, instrument data files are not "
                "immediately available on the network share after an experiment ends "
                "— they may be synced or transferred with a delay.\n\n"
                "When a session ends and no files are found, the record builder marks "
                "it `NO_FILES_FOUND` and retries on subsequent runs until this window "
                "expires.\n\n"
                "Example: With a value of 2, if a session ended Monday at 5 PM, "
                "the builder keeps retrying until Wednesday at 5 PM.\n\n"
                "Can be a fractional value (e.g., 0.5 for 12 hours). Must be > 0."
            )
        },
    )
    NX_CLUSTERING_SENSITIVITY: float = Field(
        1.0,
        description=(
            "Controls the sensitivity of file clustering into Acquisition Activities. "
            "Higher values (e.g., 2.0) make clustering more sensitive to time gaps, "
            "resulting in more activities. Lower values (e.g., 0.5) make clustering "
            "less sensitive, resulting in fewer activities. Set to 0 to disable "
            "clustering entirely and group all files into a single activity. "
            "Default is 1.0 (no change to automatic clustering)."
        ),
        ge=0,
        json_schema_extra={
            "detail": (
                "Controls how aggressively files are grouped into separate Acquisition "
                "Activities within a session record.\n\n"
                "NexusLIMS uses kernel density estimation (KDE) on file modification "
                "times to detect natural gaps in activity. This multiplier scales the "
                "KDE bandwidth.\n\n"
                "Higher values (e.g., `2.0`): more sensitive — smaller time gaps cause "
                "a split, producing more (smaller) activities.\n\n"
                "Lower values (e.g., `0.5`): less sensitive — only large gaps cause a "
                "split, producing fewer (larger) activities.\n\n"
                "Set to `0` to disable clustering and place all files into a single "
                "Acquisition Activity. Default is `1.0` (unmodified KDE bandwidth)."
            )
        },
    )
    NX_LOG_PATH: TestAwareDirectoryPath | None = Field(  # type: ignore[valid-type]
        None,
        description=(
            "Directory for application logs. If not specified, defaults to "
            "NX_DATA_PATH/logs/. Logs are organized by date: logs/YYYY/MM/DD/"
        ),
        json_schema_extra={
            "detail": (
                "Directory for NexusLIMS application logs. If not specified, logs "
                "are written to `NX_DATA_PATH/logs/` by default.\n\n"
                "Within this directory, logs are organized by date:\n"
                "  `YYYY/MM/DD/YYYYMMDD-HHMM.log`\n\n"
                "The directory must be writable by the NexusLIMS process. Leave "
                "blank to use the default location within `NX_DATA_PATH`."
            )
        },
    )
    NX_RECORDS_PATH: TestAwareDirectoryPath | None = Field(
        None,
        description=(
            "Directory for generated XML records. If not specified, defaults to "
            "NX_DATA_PATH/records/. Successfully uploaded records are moved to "
            "a 'uploaded' subdirectory."
        ),
        json_schema_extra={
            "detail": (
                "Directory where generated XML record files are stored before and "
                "after upload. If not specified, defaults to "
                "`NX_DATA_PATH/records/`.\n\n"
                "After a record is successfully uploaded, the XML file is moved to "
                "an `'uploaded'` subdirectory within this path for archival.\n\n"
                "Failed records remain in the main directory for inspection. The "
                "directory must be writable by the NexusLIMS process."
            )
        },
    )
    NX_LOCAL_PROFILES_PATH: TestAwareDirectoryPath | None = Field(
        None,
        description=(
            "Directory for site-specific instrument profiles. These profiles "
            "customize metadata extraction for instruments unique to your deployment "
            "without modifying the core NexusLIMS codebase. Profile files should be "
            "Python modules that register InstrumentProfile objects. If not specified, "
            "only built-in profiles will be loaded."
        ),
        json_schema_extra={
            "detail": (
                "Directory containing site-specific instrument profile Python modules. "
                "Profiles customize metadata extraction for instruments unique to your "
                "deployment without modifying the core NexusLIMS codebase.\n\n"
                "Each Python file in this directory should define one or more "
                "`InstrumentProfile` subclasses that are auto-discovered and loaded "
                "alongside built-in profiles.\n\n"
                "Use cases: adding static metadata fields, transforming extracted "
                "values, adding instrument-specific warnings, or overriding which "
                "extractor handles a particular instrument's files.\n\n"
                "Leave blank if you only need the built-in profiles."
            )
        },
    )

    # ========================================================================
    # eLabFTW Export Destination Configuration (Optional)
    # ========================================================================
    NX_ELABFTW_API_KEY: str | None = Field(
        "1-" + "a" * 84 if TEST_MODE else None,
        description=(
            "API key for authenticating to the eLabFTW API. Obtain from the user "
            "panel in your eLabFTW instance. If not configured, eLabFTW export will "
            "be disabled."
        ),
        json_schema_extra={
            "display_default": None,
            "detail": (
                "API key for authenticating to the eLabFTW API. If not configured, "
                "eLabFTW export will be disabled.\n\n"
                "To obtain: log in to your eLabFTW instance, go to user settings, "
                "and find the 'API keys' section. Create a new key for NexusLIMS.\n\n"
                "Format: `{id}-{key}` (e.g., `1-abc123...`). The key is typically "
                "a long alphanumeric string."
            ),
        },
    )
    NX_ELABFTW_URL: TestAwareHttpUrl | None = Field(  # type: ignore[valid-type]
        "http://elabftw.localhost:40080" if TEST_MODE else None,
        description=(
            "Root URL of the eLabFTW instance (e.g., 'https://elabftw.example.com'). "
            "If not configured, eLabFTW export will be disabled."
        ),
        json_schema_extra={
            "display_default": None,
            "detail": (
                "The root URL of your eLabFTW instance. If not configured, eLabFTW "
                "export will be disabled.\n\n"
                "Should NOT include `/api/` or any path — just the domain:\n"
                "  `https://elabftw.example.com`\n"
                "  `http://localhost:3148`\n\n"
                "NexusLIMS appends the appropriate API paths automatically."
            ),
        },
    )
    NX_ELABFTW_EXPERIMENT_CATEGORY: int | None = Field(
        None,
        description=(
            "Default category ID for created experiments. If not specified, "
            "eLabFTW will use its default category. Category IDs can be found "
            "in the eLabFTW admin panel."
        ),
        json_schema_extra={
            "detail": (
                "The default category ID for experiments created in eLabFTW. "
                "If not specified, eLabFTW uses its default category.\n\n"
                "To find category IDs: log in to eLabFTW as an administrator, "
                "navigate to the admin panel, and look under 'Experiment categories'. "
                "The ID is shown next to each category name."
            )
        },
    )
    NX_ELABFTW_EXPERIMENT_STATUS: int | None = Field(
        None,
        description=(
            "Default status ID for created experiments. If not specified, "
            "eLabFTW will use its default status. Status IDs can be found "
            "in the eLabFTW admin panel."
        ),
        json_schema_extra={
            "detail": (
                "The default status ID for experiments created in eLabFTW. "
                "If not specified, eLabFTW uses its default status.\n\n"
                "To find status IDs: log in to eLabFTW as an administrator, "
                "navigate to the admin panel, and look under 'Experiment statuses'. "
                "The ID is shown next to each status name."
            )
        },
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

        # CRITICAL: In TEST_MODE, do NOT load from .env file to prevent
        # test contamination from local environment configuration
        env_vars = {}
        if not TEST_MODE:
            # Load .env file to get NEMO variables (Pydantic doesn't load
            # variables that aren't defined as fields)
            env_file_path = Path(".env")
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
                    _logger.warning(
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
                    _logger.exception(
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
        # CRITICAL: In TEST_MODE, do NOT load from .env file to prevent
        # test contamination from local environment configuration
        env_vars = {}
        if not TEST_MODE:
            # Load .env file to get email variables
            env_file_path = Path(".env")
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
            _logger.exception("Invalid email configuration")
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
                f"See https://datasophos.github.io/NexusLIMS/{doc_version}/user_guide/configuration.html\n"
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


settings = _SettingsProxy()
"""The settings "singleton" - accessed like a normal object in the application"""
