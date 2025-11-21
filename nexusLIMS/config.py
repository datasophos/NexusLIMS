"""
Centralized environment variable management for NexusLIMS.

This module uses `pydantic-settings` to define, validate, and access
application settings from environment variables and .env files.
It provides a single source of truth for configuration, ensuring
type safety and simplifying access throughout the application.
"""
import logging
from pathlib import Path
from typing import Literal

import ssl

from pydantic import AnyHttpUrl, DirectoryPath, Field, FilePath, ValidationError, field_validator, NewPath
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
            "As an alternative NX_CERT_BUNDLE_FILE, to you can provide the entire "
            "certificate bundle as a single string (this can be useful for CI/CD "
            "pipelines). Lines should be separated by a single '\n' character If "
            "defined, this value will take precedence over NX_CERT_BUNDLE_FILE."
        ),
    )
    NX_FILE_DELAY_DAYS: int = Field(
        2,
        description=(
            "NX_FILE_DELAY_DAYS controls the maximum delay between observing a "
            "session ending and when the files are expected to be present. For the "
            "number of days set below (can be a fraction of a day, if desired), record "
            "building will not fail if no files are found, and the builder will search "
            'foragain until the delay has passed. So if the value is "2", and a '
            "session ended Monday at 5PM, the record builder will continue to try "
            "looking for files until Wednesday at 5PM. "
        ),
    )

    @property
    def nexuslims_instrument_data_path(self) -> Path:
        """Alias for NX_INSTRUMENT_DATA_PATH for easier access."""
        return self.NX_INSTRUMENT_DATA_PATH

    # ... other environment variables as fields ...


# Instantiate the settings object to be imported throughout the application
try:
    settings = Settings()
except ValidationError as e:
    logger.exception(f"Configuration validation error: {e}")
    raise
