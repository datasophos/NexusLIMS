# NexusLIMS Migration Guide: From v1.4.3 to 2.0.0+

This document outlines the necessary steps and changes for users migrating their NexusLIMS environment from version 1.4.3 to the latest version (2.0.0 at the time of writing). This update includes significant changes to dependency management and environment variable configuration to improve consistency and leverage modern tooling.

## 1. Introduction to `uv` and Dependency Management

The project has transitioned from `Poetry` and `pyenv` to `uv` for Python package and environment management. `uv` is a fast and modern package installer and resolver.

**Action Required:**
*   **Install `uv`**: If you don't have `uv` installed, please follow the official `uv` installation instructions.
*   **Remove `pyenv` references**: All `pyenv` related configurations and installations are no longer needed. You should remove any `pyenv` specific environment variables or shell initializations. `uv` handles Python version management directly if desired, but your system's Python or a virtual environment managed by `uv` is now the primary method.

## 2. Environment Variable Configuration Changes

Environment variable naming has been standardized for better consistency. Please review the updated `.env.example` file in the project root and update your local `.env` file accordingly.

### Key Changes and Discrepancies to Note:

*   **Standardized Naming:** Most NexusLIMS-specific environment variables now consistently use the `NX_` prefix.
*   **Renamed Paths:** `MMFNEXUS_PATH` has been renamed to `NX_INSTRUMENT_DATA_PATH`, and `NEXUSLIMS_PATH` has been renamed to `NX_DATA_PATH` for clarity and consistency.
*   **Certificate Bundle:**
    *   `NX_CERT_BUNDLE_FILE`: Path to a custom SSL certificate CA bundle file.
    *   `NX_CERT_BUNDLE`: (New) Allows providing the entire certificate bundle content as a string, useful for CI/CD pipelines. This takes precedence over `NX_CERT_BUNDLE_FILE` if both are defined.

### Centralized Configuration Module (`nexusLIMS.config`)

To improve maintainability, robustness, and testability, environment variable access across the codebase is centralized into a new module: `nexusLIMS/config.py`.

**What this means for developers:**
*   Instead of directly calling `os.environ.get("YOUR_VARIABLE")` or `os.getenv("YOUR_VARIABLE")`, the application will now access these values via a `config` object (e.g., `config.YOUR_VARIABLE`).
*   This module handles default values, type conversions, and basic validation, ensuring that configuration is consistently applied throughout the application.
*   For end-users, this change is largely internal. You should continue to define your environment variables in your `.env` file or as system environment variables as described below. The application will automatically pick up these values through the `nexusLIMS.config` module.

### General NexusLIMS Configuration Variables

| Variable                  | Purpose                                                                                                                                    | Example Value                   |
| :------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------ |
| `NX_FILE_STRATEGY`        | Defines how file finding will behave: `'exclusive'` (only files with explicit extractors) or `'inclusive'` (all files, with basic metadata for others). Default is `'exclusive'`. | `'exclusive'` or `'inclusive'`  |
| `NX_IGNORE_PATTERNS`      | JSON array string of glob patterns to ignore when searching for experiment files (e.g., `["*.mib","*.db"]`). Follows GNU `find -name` syntax. | `'["*.mib","*.db"]'`            |
| `NX_INSTRUMENT_DATA_PATH` | Root path to the centralized file store for instrument data (mounted read-only).                                                           | `'/path/to/instrument/data/mount'`|
| `NX_DATA_PATH`            | Writable path parallel to `NX_INSTRUMENT_DATA_PATH` for extracted metadata and generated preview images.                                   | `'/path/to/nexusLIMS/data'`     |
| `NX_DB_PATH`              | Writable path to the NexusLIMS SQLite database.                                                                                            | `'/path/to/nexuslims_db.sqlite'`|
| `NX_FILE_DELAY_DAYS`      | Controls the maximum delay (in days, can be fractional) for record building to wait for files after a session ends.                        | `2`                             |
| `RECORDS_JSON_PATH`       | Path to the JSON file where records are stored (used by dev scripts). Defaults to `records.json`.                                          | `'records.json'`                |

### Authentication & API Access Variables

| Variable                   | Purpose                                                                                | Example Value                                  |
| :------------------------- | :------------------------------------------------------------------------------------- | :--------------------------------------------- |
| `NX_CDCS_USER`           | Username for CDCS API authentication.                                                  | `'your_username'`                              |
| `NX_CDCS_PASS`           | Password for CDCS API authentication.                                                  | `'your_password'`                              |
| `NX_NX_CDCS_URL`                 | Root URL of the NexusLIMS CDCS front-end (for record uploads, includes trailing slash). | `'https://nexuslims.domain.com/'`              |
| `TEST_NX_NX_CDCS_URL`            | (Optional) Root URL of a CDCS instance for testing purposes.                           | `'https://test.nexuslims.domain.com/'`         |
| `NX_CERT_BUNDLE_FILE` | Path to a custom SSL certificate CA bundle file.                                       | `'/path/to/bundle.pem'`                        |
| `NX_CERT_BUNDLE`    | Full content of a custom SSL certificate CA bundle as a string.                        | `'-----BEGIN CERTIFICATE-----\n...'`           |
| `SHAREPOINT_ROOT_URL`      | (Deprecated in `.env.example`, but currently used in code) Root URL of SharePoint calendar. | `'https://path.to.sharepoint/calendar/'` 

### NEMO Harvester Variables

Multiple NEMO harvesters can be configured by duplicating these variables with a suffix (e.g., `NX_NX_NEMO_ADDRESS_1`, `NX_NX_NEMO_ADDRESS_2`).

| Variable                  | Purpose                                                                                                                                                                                                                                                               | Example Value                                |
| :------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------- |
| `NEMO_ADDRESS_X`          | Full path to the root of the NEMO API (includes trailing slash).                                                                                                                                                                                                      | `'https://nemo.address.com/api/'`            |
| `NEMO_TOKEN_X`            | Authentication token for the NEMO server.                                                                                                                                                                                                                             | `'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'`         |
| `NEMO_STRFTIME_FMT_X`     | (Optional) `strftime` format for sending dates/times to the NEMO API. Defaults to ISO 8601.                                                                                                                                                                           | `"%Y-%m-%dT%H:%M:%S%z"`                      |
| `NEMO_STRPTIME_FMT_X`     | (Optional) `strptime` format for interpreting dates/times from the NEMO API. Defaults to ISO 8601.                                                                                                                                                                    | `"%Y-%m-%dT%H:%M:%S%z"`                      |
| `NEMO_TZ_X`               | (Optional) IANA timezone name (`America/Denver`) to coerce API datetime strings into. Use for NEMO servers that do not return time zone information.                                                                                                                  | `'America/Denver'`                           |

### Email Notification Variables (for `process_new_records.sh`)

| Variable                   | Purpose                                                                                                 | Example Value                                  |
| :------------------------- | :------------------------------------------------------------------------------------------------------ | :--------------------------------------------- |
| `NX_EMAIL_SENDER`   | Email address to use as the "sender" for notification emails.                                           | `'email.to.send.from@email.com'`               |
| `NX_EMAIL_RECIPIENTS` | Comma-separated list of email addresses to notify when an error is detected by the processing script. | `'email1@example.com,email2@example.com'`      |

## 3. Actionable Migration Steps for Users

1.  **Install `uv`**:
    ```bash
    # See uv documentation for your specific OS
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
2.  **Remove `pyenv` Configuration**: Locate and remove any `pyenv` related configurations from your shell's startup files (e.g., `.bashrc`, `.zshrc`, `.profile`).
3.  **Update `.env` File**:
    *   **Crucially, review the new `.env.example` file** in the project root.
    *   Compare it with your existing `.env` file.
    *   **Merge relevant changes**, adding new variables and updating names as necessary.
    *   Pay special attention to the `SHAREPOINT_ROOT_URL` vs. `NX_SP_ROOT_URL` note above.
4.  **Re-create Virtual Environment**:
    ```bash
    # If you have an old virtual environment, you might want to remove it
    # rm -rf .venv

    # Create a new virtual environment using uv
    uv venv

    # Activate the new virtual environment
    source .venv/bin/activate  # On Unix/macOS
    .venv\Scripts\activate     # On Windows

    # Install dependencies using uv
    uv pip install -e .
    ```
5.  **Test Your Setup**: After updating your environment variables and re-installing dependencies, run your NexusLIMS applications and tests to ensure everything is functioning as expected.

By following these steps, you should be able to successfully migrate your NexusLIMS environment to the latest version.
