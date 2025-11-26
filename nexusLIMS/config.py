"""
Centralized environment variable management for NexusLIMS.

This module uses `pydantic-settings` to define, validate, and access
application settings from environment variables and .env files.
It provides a single source of truth for configuration, ensuring
type safety and simplifying access throughout the application.
"""

import logging
import os
import re
from functools import cached_property
from pathlib import Path
from typing import Literal

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
        ["*.mib", "*.db", "*.emi"],
        description=(
            "List of glob patterns to ignore when searching for experiment files. "
            "Default is `['*.mib','*.db','*.emi']`."
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
    NX_TEST_CDCS_URL: AnyHttpUrl | None = Field(
        None,
        description=(
            "(development setting) The root URL of a NexusLIMS CDCS instance to use "
            "for integration testing. If defined, this URL will be used for the CDCS "
            'tests rather than the "actual" URL defined in NX_CDCS_URL. If not '
            "defined, no integration tests will be run."
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
    NX_EMAIL_SENDER: EmailStr | None = Field(
        None,
        description=(
            "Email address to send from for notifications via the "
            "process_new_records.sh script."
        ),
    )
    NX_EMAIL_RECIPIENTS: list[EmailStr] | None = Field(
        None,
        description=(
            "Address(es) to email when an error is detected (used by "
            "process_new_records.sh)."
        ),
    )
    NX_SP_ROOT_URL: AnyHttpUrl | None = Field(
        None,
        description=("The root URL of the SharePoint calendar resource."),
        deprecated=True,
    )

    @property
    def nexuslims_instrument_data_path(self) -> Path:
        """Alias for NX_INSTRUMENT_DATA_PATH for easier access."""
        return self.NX_INSTRUMENT_DATA_PATH

    @cached_property
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
            NX_NEMO_ADDRESS_1=https://nemo1.com/api/
            NX_NEMO_TOKEN_1=token123
            NX_NEMO_ADDRESS_2=https://nemo2.com/api/
            NX_NEMO_TOKEN_2=token456
            NX_NEMO_TZ_2=America/New_York

        Returns
        -------
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


# Instantiate the settings object to be imported throughout the application
try:
    settings = Settings()
except ValidationError:
    logger.exception("Configuration validation error")
    raise
