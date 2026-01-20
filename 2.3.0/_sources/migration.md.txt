(migration)=
# Migration Guide

This guide is for system administrators, and will help you migrate your NexusLIMS installation from v1.4.3 to v2.3.0.

## What Changed

The major changes you need to know about:

1. **Package Manager**: Poetry → `uv` (faster, simpler installation)
2. **Environment Variables**: All variables now use `NX_` prefix
3. **Metadata System**: New Pydantic schemas with EM Glossary integration and validation
4. **Configuration**: Better validation with helpful error messages

## Transition to uv

The project has transitioned from Poetry to `uv` for Python package and environment management. `uv` is a fast, modern package installer and resolver written in Rust that provides:

- Significantly faster dependency resolution and installation
- Better reproducibility with lock files
- Simpler workflow for both development and deployment
- Direct Python version management (no need for separate tools like pyenv)

### Installing uv

Install `uv` using the official installation script:

```bash
# Unix/macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

For alternative installation methods, see the [uv documentation](https://docs.astral.sh/uv/).

## Environment Variable Changes

Environment variable naming has been standardized for better consistency. **You must update your `.env` file** to use the new variable names.

### Renamed Variables

The following variables have been renamed:

| **Old Name (v1.x)** | **New Name (v2.0+)** | **Required** |
|---------------------|----------------------|--------------|
| `mmfnexus_path` | `NX_INSTRUMENT_DATA_PATH` | Yes |
| `nexusLIMS_path` | `NX_DATA_PATH` | Yes |
| `nexusLIMS_db_path` | `NX_DB_PATH` | Yes |
| `nexusLIMS_user` | `NX_CDCS_TOKEN` | Yes |
| `nexusLIMS_pass` | `NX_CDCS_TOKEN` | Yes |
| `cdcs_url` | `NX_CDCS_URL` | Yes |
| `NexusLIMS_cert_bundle_file` | `NX_CERT_BUNDLE_FILE` | No |
| `NexusLIMS_cert_bundle` | `NX_CERT_BUNDLE` | No |
| `NexusLIMS_file_strategy` | `NX_FILE_STRATEGY` | No |
| `NexusLIMS_ignore_patterns` | `NX_IGNORE_PATTERNS` | No |
| `nexusLIMS_file_delay_days` | `NX_FILE_DELAY_DAYS` | No |
| `NEMO_address_*` | `NX_NEMO_ADDRESS_*` | If using NEMO |
| `NEMO_token_*` | `NX_NEMO_TOKEN_*` | If using NEMO |
| `NEMO_strftime_fmt_*` | `NX_NEMO_STRFTIME_FMT_*` | No |
| `NEMO_strptime_fmt_*` | `NX_NEMO_STRPTIME_FMT_*` | No |
| `NEMO_tz_*` | `NX_NEMO_TZ_*` | No |

```{note}
**v2.3.0+ Authentication Change**: CDCS authentication has changed from username/password (`NX_CDCS_USER` and `NX_CDCS_PASS`) to token-based authentication (`NX_CDCS_TOKEN`). Replace your username and password with an API token obtained from the CDCS admin panel. See {ref}`config-cdcs-token` for details.
```

### New Variables

The following variables are new in v2.0:

| **Variable** | **Purpose** | **Required** |
|--------------|-------------|--------------|
| `NX_LOG_PATH` | Custom directory for application logs | No |
| `NX_RECORDS_PATH` | Custom directory for generated XML records | No |
| `NX_LOCAL_PROFILES_PATH` | Directory for site-specific instrument profiles | No |
| `NX_EMAIL_SMTP_HOST` | SMTP server hostname | If using email |
| `NX_EMAIL_SMTP_PORT` | SMTP server port (default: 587) | No |
| `NX_EMAIL_SMTP_USERNAME` | SMTP username for authentication | No |
| `NX_EMAIL_SMTP_PASSWORD` | SMTP password for authentication | No |
| `NX_EMAIL_USE_TLS` | Use TLS encryption (default: true) | No |
| `NX_EMAIL_SENDER` | Email address to send from | If using email |
| `NX_EMAIL_RECIPIENTS` | Comma-separated recipient addresses | If using email |

### Removed Variables

The following variables from v1.x are no longer used:

| **Variable** | **Reason for Removal** |
|--------------|------------------------|
| `test_cdcs_url` | Tests now run as independent unit tests and integration tests against a Docker-deployed instance created on demand |
| `sharepoint_root_url` | SharePoint harvester has been removed |
| `email_sender` | Replaced by enhanced email configuration (`NX_EMAIL_*`) |
| `email_recipients` | Replaced by enhanced email configuration (`NX_EMAIL_*`) |

## Complete Environment Variable Reference

### General Configuration

| **Variable** | **Description** | **Example** |
|--------------|-----------------|-------------|
| `NX_FILE_STRATEGY` | File inclusion strategy: `exclusive` (only files with extractors) or `inclusive` (all files) | `exclusive` |
| `NX_IGNORE_PATTERNS` | JSON array of glob patterns to ignore | `["*.mib","*.db","*.emi"]` |
| `NX_INSTRUMENT_DATA_PATH` | Root path to centralized instrument data (read-only mount) | `/mnt/microscopy/data` |
| `NX_DATA_PATH` | Writable parallel path for metadata and previews | `/var/nexuslims/data` |
| `NX_DB_PATH` | Path to NexusLIMS SQLite database | `/var/nexuslims/nexuslims.db` |
| `NX_FILE_DELAY_DAYS` | Maximum days to wait for files (can be fractional) | `2` |
| `NX_LOG_PATH` | Optional: Directory for logs (defaults to `NX_DATA_PATH/logs/`) | `/var/log/nexuslims` |
| `NX_RECORDS_PATH` | Optional: Directory for records (defaults to `NX_DATA_PATH/records/`) | `/var/nexuslims/records` |
| `NX_LOCAL_PROFILES_PATH` | Optional: Directory for site-specific instrument profiles | `/var/nexuslims/profiles` |

### CDCS Authentication

| **Variable** | **Description** | **Example** |
|--------------|-----------------|-------------|
| `NX_CDCS_TOKEN` | API token for CDCS authentication | `your-api-token-here` |
| `NX_CDCS_URL` | Root URL of NexusLIMS CDCS instance (with trailing slash) | `https://nexuslims.example.com/` |
| `NX_CERT_BUNDLE_FILE` | Optional: Path to SSL certificate bundle | `/etc/ssl/certs/custom-ca.pem` |
| `NX_CERT_BUNDLE` | Optional: SSL certificate bundle as string | `-----BEGIN CERTIFICATE-----\n...` |

### NEMO Harvester Configuration

Multiple NEMO harvesters can be configured using numbered suffixes (`_1`, `_2`, etc.):

| **Variable** | **Description** | **Example** |
|--------------|-----------------|-------------|
| `NX_NEMO_ADDRESS_N` | Full path to NEMO API root (with trailing slash) | `https://nemo.example.com/api/` |
| `NX_NEMO_TOKEN_N` | Authentication token for NEMO server | `abc123def456...` |
| `NX_NEMO_STRFTIME_FMT_N` | Optional: Format for sending datetimes to API | `%Y-%m-%dT%H:%M:%S%z` |
| `NX_NEMO_STRPTIME_FMT_N` | Optional: Format for parsing datetimes from API | `%Y-%m-%dT%H:%M:%S%z` |
| `NX_NEMO_TZ_N` | Optional: IANA timezone for API datetimes | `America/Denver` |

### Email Notification Configuration

Email notifications are sent by `nexuslims-process-records` when errors are detected:

| **Variable** | **Description** | **Example** |
|--------------|-----------------|-------------|
| `NX_EMAIL_SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `NX_EMAIL_SMTP_PORT` | Optional: SMTP port (default: 587) | `587` |
| `NX_EMAIL_SMTP_USERNAME` | Optional: SMTP username for authentication | `user@example.com` |
| `NX_EMAIL_SMTP_PASSWORD` | Optional: SMTP password for authentication | `your-app-password` |
| `NX_EMAIL_USE_TLS` | Optional: Use TLS encryption (default: true) | `true` |
| `NX_EMAIL_SENDER` | Email address to send from | `nexuslims@example.com` |
| `NX_EMAIL_RECIPIENTS` | Comma-separated list of recipient addresses | `admin@example.com,team@example.com` |

## Centralized Configuration Module

To improve maintainability and type safety, all environment variable access is centralized in the `nexusLIMS.config` module using [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

For complete configuration documentation, see {ref}`configuration`.

### What This Means for Users

- **No file structure changes required**: Continue defining variables in your `.env` file or system environment
- **Automatic validation**: The application validates configuration at startup and provides clear error messages
- **Type safety**: Configuration values are automatically converted to appropriate Python types
- **Default values**: Sensible defaults are provided where applicable
- **Mocking for tests**: The design of the system allows for a fully mocked setup
for use in the test suite, ensuring more reliable code quality testing.

### What This Means for Developers

Instead of accessing environment variables directly:

```python
# Old approach (v1.x) - Don't use
import os
path = os.environ.get("nexusLIMS_path")
```

Use the centralized config module:

```python
# New approach (v2.0+)
from nexusLIMS.config import settings
path = settings.NX_DATA_PATH
```

This provides:

- Type hints and autocomplete in IDEs
- Validation at import time
- Consistent defaults throughout the application
- Easier testing with `refresh_settings()`

## Step-by-Step Migration Instructions

Follow these steps to migrate your NexusLIMS installation from v1.x to v2.0:

### 1. Backup Your Current Installation

```{note}
**Good news**: The database schema has **not changed** between v1.4.3 and v2.2.0. Your existing database will work without any migration or modifications. We still recommend backing up as a precaution.
```

```bash
# Backup your database
cp /path/to/nexuslims_db.sqlite /path/to/nexuslims_db.sqlite.backup

# Backup your .env file
cp .env .env.v1.backup
```

### 2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 3. Update Your .env File

Create a new `.env` file based on `.env.example`:

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
nano .env  # or your preferred editor
```

**Map your old variables to new names** using the table in the "Renamed Variables" section above.

**Key changes to make**:

- Rename `mmfnexus_path` → `NX_INSTRUMENT_DATA_PATH`
- Rename `nexusLIMS_path` → `NX_DATA_PATH`
- Rename `nexusLIMS_db_path` → `NX_DB_PATH`
- Replace `nexusLIMS_user` and `nexusLIMS_pass` → `NX_CDCS_TOKEN` (obtain token from CDCS admin panel)
- Rename `cdcs_url` → `NX_CDCS_URL`
- Rename `NexusLIMS_cert_bundle_file` → `NX_CERT_BUNDLE_FILE` (if used)
- Rename `NexusLIMS_cert_bundle` → `NX_CERT_BUNDLE` (if used)
- Rename `NexusLIMS_file_strategy` → `NX_FILE_STRATEGY` (if customized)
- Rename `NexusLIMS_ignore_patterns` → `NX_IGNORE_PATTERNS` (if customized)
- Rename `nexusLIMS_file_delay_days` → `NX_FILE_DELAY_DAYS` (if customized)
- Rename `NEMO_address_*` → `NX_NEMO_ADDRESS_*` (if using NEMO)
- Rename `NEMO_token_*` → `NX_NEMO_TOKEN_*` (if using NEMO)
- Remove `test_cdcs_url`, `sharepoint_root_url`, `email_sender`, `email_recipients`
- Add new email configuration variables (`NX_EMAIL_*`) if you want email notifications

### 4. Remove Old Virtual Environment

```bash
# If you have an old Poetry or pyenv environment
rm -rf .venv

# Remove Poetry lock file
rm poetry.lock  # if it exists
```

### 5. Create New Environment with uv

```bash
# Install NexusLIMS with dependencies (this will create the virtualenvironment as necessary)
uv sync
```

### 6. Mark Database as Migrated

```{versionadded} 2.2.0
NexusLIMS now uses Alembic for database schema version control. You need to mark your existing database as migrated to the current schema.
```

```bash
# Mark database as at current schema version
uv run alembic stamp head
```

This tells Alembic that your database already has the current schema structure and doesn't need any migrations applied. This is a one-time operation for existing installations.

### 7. Verify Installation

```bash
# Test configuration loading
uv run python -c "from nexusLIMS.config import settings; print(settings.NX_DATA_PATH)"

# Run unit tests (not necessary, but will provide confidence things are working)
uv run pytest tests/unit

# Check database connection and list instruments
uv run python -c "from nexusLIMS.instruments import instrument_db; print(f'{len(instrument_db)} instruments found:'); [print(f'  - {pid}') for pid in instrument_db.keys()]"
```

### 8. Update Deployment Scripts

If you have cron jobs or systemd services running NexusLIMS:

**Old command style (v1.x)**:

```bash
# Using Poetry
cd /path/to/NexusLIMS
poetry run python -m nexusLIMS.builder.record_builder
```

**New command style (v2.0+)**:

```bash
# Using uv
cd /path/to/NexusLIMS
uv run nexuslims-process-records

# Or using the module directly
uv run python -m nexusLIMS.cli.process_records
```

### 9. Test Record Building

Run a test record build to verify everything works:

```bash
# Dry run mode (find files but don't build records)
uv run nexuslims-process-records -n

# Verbose mode (with detailed logging)
uv run nexuslims-process-records -vv
```

## Common Migration Issues

### Database Path Not Found

**Error**: `ValidationError: NX_DB_PATH ... does not exist`

**Solution**: Ensure your database file exists at the path specified in `NX_DB_PATH`. If you migrated the path, update it in your `.env` file.

### Directory Does Not Exist

**Error**: `ValidationError: NX_INSTRUMENT_DATA_PATH ... does not exist`

**Solution**: Pydantic validates that paths exist. Ensure all directory paths in your `.env` file point to existing directories:

```bash
mkdir -p /path/to/nexuslims/data
mkdir -p /path/to/nexuslims/logs
```

### SSL Certificate Errors

**Error**: `SSLError: certificate verify failed`

**Solution**: If your CDCS or NEMO servers use custom SSL certificates, configure `NX_CERT_BUNDLE_FILE`:

```bash
NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca-bundle.pem
```

### NEMO Harvester Not Found

**Error**: No NEMO reservations being harvested

**Solution**: Verify your NEMO configuration uses the new `NX_` prefix:

```bash
NX_NEMO_ADDRESS_1=https://nemo.example.com/api/
NX_NEMO_TOKEN_1=your-token-here
```

## What's New in v2.2.0

### Metadata Improvements

- **Pydantic Schemas**: All metadata validated before record building
- **EM Glossary Integration**: 50+ standardized field names
- **Formal Unit Handling**: Type-safe quantity handling with automatic conversion
- **Helper Functions**: `emg_field()` and `add_to_extensions()` for cleaner code

### Other Improvements

- **Email notifications**: Optional alerts for record building errors
- **Custom paths**: Specify log/record directories with `NX_LOG_PATH` / `NX_RECORDS_PATH`
- **Local profiles**: Load site-specific profiles from `NX_LOCAL_PROFILES_PATH`
- **Better errors**: Pydantic provides detailed, actionable validation messages
- **Faster installation**: `uv` is significantly faster than Poetry

### Removed Features

- **SharePoint harvester**: Deprecated (use NEMO instead)
- **Poetry**: Replaced by `uv`

## Getting Help

If you encounter issues during migration:

1. **Review the error message carefully** - Pydantic provides detailed validation errors
2. **Check the example file**: Compare your `.env` with `.env.example`
3. **Consult the logs**: Check `NX_LOG_PATH` (or `NX_DATA_PATH/logs/`) for details
4. **Open an issue**: [https://github.com/datasophos/NexusLIMS/issues](https://github.com/datasophos/NexusLIMS/issues)

For professional migration support, deployment assistance, or custom development:

- **Contact Datasophos**: https://datasophos.co/#contact

## Further Reading

- {ref}`getting_started` - Fresh installation guide for v2.0
- {ref}`record-building` - Understanding the record building workflow
- {py:mod}`nexusLIMS.config` - Configuration module API documentation
- [uv documentation](https://docs.astral.sh/uv/) - Learn more about uv
