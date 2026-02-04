(configuration)=
# Configuration

This guide provides comprehensive information about configuring NexusLIMS through environment variables. All configuration is managed through the centralized `nexusLIMS.config` module, which uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for validation and type safety.

## Configuration Files

NexusLIMS loads configuration from environment variables and optionally from a `.env` file in the project root. See `.env.example` in the repository for a complete template with examples.

```{tip}
Copy `.env.example` to `.env` and customize it for your deployment. The `.env` file should never be committed to version control.
```

## Required Configuration

These variables **must** be set for NexusLIMS to function.

### File System Paths

(config-instrument-data-path)=
#### `NX_INSTRUMENT_DATA_PATH`

**Type:** Directory path (must exist)\
**Required:** Yes

The root path to the centralized file store for instrument data. This should be mounted read-only and is where instruments write their data files. Individual instrument paths (specified in the database) are relative to this root.

**Example:**
```bash
NX_INSTRUMENT_DATA_PATH=/mnt/nexus_instruments
```

(config-data-path)=
#### `NX_DATA_PATH`

**Type:** Directory path (must exist)\
**Required:** Yes

Writable path parallel to `NX_INSTRUMENT_DATA_PATH` for extracted metadata, generated preview images, and other NexusLIMS-generated content. This directory structure mirrors the instrument data path.

**Example:**
```bash
NX_DATA_PATH=/var/nexuslims/data
```

(config-db-path)=
#### `NX_DB_PATH`

**Type:** File path (must exist)\
**Required:** Yes

Full path to the NexusLIMS SQLite database file containing instrument configurations and session logs.

**Example:**
```bash
NX_DB_PATH=/var/nexuslims/data/nexuslims.db
```

### CDCS Integration

(config-cdcs-url)=
#### `NX_CDCS_URL`

**Type:** URL\
**Required:** Yes

Root URL of the NexusLIMS CDCS frontend where generated records will be uploaded.

**Example:**
```bash
NX_CDCS_URL=https://nexuslims.example.com
```

(config-cdcs-token)=
#### `NX_CDCS_TOKEN`

**Type:** String\
**Required:** Yes

API token for authenticating to the CDCS API for record uploads. Obtain this token from the CDCS admin panel or via the API token endpoint.

**Example:**
```bash
NX_CDCS_TOKEN=your-api-token-here
```

```{warning}
Store API tokens securely. Use environment variables or a secure secrets management system rather than committing tokens to version control.
```

### eLabFTW Integration

(config-elabftw)=

NexusLIMS can optionally export records to [eLabFTW](https://www.elabftw.net/), an open-source electronic lab notebook. Each NexusLIMS session creates one eLabFTW experiment with a structured summary and the full XML record attached.

(config-elabftw-url)=
#### `NX_ELABFTW_URL`

**Type:** URL\
**Required:** No (only if using eLabFTW export)

Root URL of your eLabFTW instance (without `/api/`). The eLabFTW export destination is automatically enabled when both `NX_ELABFTW_URL` and `NX_ELABFTW_API_KEY` are configured.

**Example:**
```bash
NX_ELABFTW_URL=https://elabftw.example.com
```

(config-elabftw-api-key)=
#### `NX_ELABFTW_API_KEY`

**Type:** String\
**Required:** No (only if using eLabFTW export)

API key for authenticating to the eLabFTW API. Generate this from your eLabFTW user panel under "API Keys". The key should have write permissions to create experiments and upload files.

**Example:**
```bash
NX_ELABFTW_API_KEY=1-abcdef0123456789...
```

```{note}
eLabFTW API keys have the format `{id}-{key}` where the key portion is 84 hexadecimal characters.
```

(config-elabftw-experiment-category)=
#### `NX_ELABFTW_EXPERIMENT_CATEGORY`

**Type:** Integer\
**Required:** No\
**Default:** None (uses eLabFTW default)

Optional category ID to assign to created experiments. Categories are defined in eLabFTW's admin panel and help organize experiments by project or type.

**Example:**
```bash
NX_ELABFTW_EXPERIMENT_CATEGORY=1
```

(config-elabftw-experiment-status)=
#### `NX_ELABFTW_EXPERIMENT_STATUS`

**Type:** Integer\
**Required:** No\
**Default:** None (uses eLabFTW default)

Optional status ID to assign to created experiments. Statuses represent the experiment lifecycle (e.g., "Running", "Success", "Need to be redone") and are configured in eLabFTW's admin panel.

**Example:**
```bash
NX_ELABFTW_EXPERIMENT_STATUS=2
```

```{tip}
When eLabFTW export is enabled, experiments are created with:
- **Title:** "NexusLIMS Experiment - {session_id}"
- **Body:** HTML summary with session details and link to CDCS record (if available)
- **Tags:** NexusLIMS, instrument name, username
- **Metadata:** Structured extra_fields including session times, instrument, user, and CDCS cross-link
- **Attachment:** Full XML record file
```

### NEMO Integration

NexusLIMS supports multiple NEMO instances by using numbered environment variable pairs. Each NEMO instance requires an address and token.

(config-nemo-address)=
#### `NX_NEMO_ADDRESS_N`

**Type:** URL (must end with trailing slash)\
**Required:** Yes (for each NEMO instance)

Full path to the NEMO API endpoint. The `_N` suffix can be any number (e.g., `_1`, `_2`, `_3`).

**Example:**
```bash
NX_NEMO_ADDRESS_1=https://nemo1.example.com/api/
NX_NEMO_ADDRESS_2=https://nemo2.example.com/api/
```

(config-nemo-token)=
#### `NX_NEMO_TOKEN_N`

**Type:** String\
**Required:** Yes (for each NEMO instance)

API authentication token for the corresponding NEMO instance. Obtain from the "Detailed Administration" → "Tokens" page in NEMO. The token authenticates as a specific user, so consider using a dedicated service account.

**Example:**
```bash
NX_NEMO_TOKEN_1=abc123def456...
NX_NEMO_TOKEN_2=xyz789uvw012...
```

## Optional Configuration

### File Handling

(config-file-strategy)=
#### `NX_FILE_STRATEGY`

**Type:** `"exclusive"` or `"inclusive"`\
**Default:** `"exclusive"`

Defines file discovery behavior:
- **`exclusive`**: Only include files with known extractors
- **`inclusive`**: Include all files, using basic metadata for unknown types

**Example:**
```bash
NX_FILE_STRATEGY=inclusive
```

(config-ignore-patterns)=
#### `NX_IGNORE_PATTERNS`

**Type:** JSON array of glob patterns\
**Default:** `["*.mib", "*.db", "*.emi", "*.hdr"]`

Glob patterns to exclude when searching for experiment files. Useful for filtering out temporary files, databases, or dedicated metadata files that do not contain data, and are read as-needed by extractors (such as `.hdr` and `.emi`).

**Example:**
```bash
NX_IGNORE_PATTERNS=["*.mib", "*.db", "*.emi", "*.tmp", "*~"]
```

(config-file-delay-days)=
#### `NX_FILE_DELAY_DAYS`

**Type:** Float (must be > 0)\
**Default:** `2.0`

Maximum delay (in days) between session end and when files are expected to be present. The record builder will continue searching for files until this delay expires. Fractional days are supported. This is useful if your file management system takes time to synchronize data files from the instrument to centralized storage.

**Example:** If set to `2.0` and a session ends Monday at 5 PM, the builder will retry until Wednesday at 5 PM.

```bash
NX_FILE_DELAY_DAYS=2.5
```

(config-clustering-sensitivity)=
#### `NX_CLUSTERING_SENSITIVITY`

**Type:** Float (must be >= 0)\
**Default:** `1.0`

Controls the sensitivity of file clustering into {ref}`Acquisition Activities <acquisition-activities>`. When building records, NexusLIMS groups files into activities based on temporal gaps in file modification times using Kernel Density Estimation (KDE). This setting allows you to adjust or disable this clustering behavior.

- **Values > 1.0**: More sensitive to time gaps, resulting in more activities (finer granularity)
- **Values < 1.0**: Less sensitive to time gaps, resulting in fewer activities (coarser granularity)
- **Value of 0**: Disables clustering entirely; all files are grouped into a single activity
- **Value of 1.0**: Default behavior with automatic clustering based on data distribution

This is useful when:
- The automatic clustering creates too many or too few activities for your workflow
- You want to disable clustering for simpler record structures
- Your data acquisition patterns don't match the default clustering assumptions

**Examples:**
```bash
# More sensitive - detects smaller time gaps as activity boundaries
NX_CLUSTERING_SENSITIVITY=2.0

# Less sensitive - only large time gaps create new activities
NX_CLUSTERING_SENSITIVITY=0.5

# Disable clustering - all files in one activity
NX_CLUSTERING_SENSITIVITY=0
```

### Directory Paths

(config-log-path)=
#### `NX_LOG_PATH`

**Type:** Directory path\
**Default:** `${NX_DATA_PATH}/logs/`

Directory for application logs. Logs are organized by date: `logs/YYYY/MM/DD/`.

**Example:**
```bash
NX_LOG_PATH=/var/log/nexuslims
```

(config-records-path)=
#### `NX_RECORDS_PATH`

**Type:** Directory path\
**Default:** `${NX_DATA_PATH}/records/`

Directory for generated XML records. Successfully uploaded records are moved to an `uploaded/` subdirectory.

**Example:**
```bash
NX_RECORDS_PATH=/var/nexuslims/records
```

(config-local-profiles-path)=
#### `NX_LOCAL_PROFILES_PATH`

**Type:** Directory path\
**Default:** None (only built-in profiles loaded)

Directory containing site-specific instrument profiles. Profiles customize metadata extraction for instruments unique to your deployment without modifying core NexusLIMS code.

Profile files should be Python modules that register `InstrumentProfile` objects. See {ref}`instrument-profiles` for details.

**Example:**
```bash
NX_LOCAL_PROFILES_PATH=/etc/nexuslims/profiles
```

### NEMO Advanced Options

(config-nemo-strftime-fmt)=
#### `NX_NEMO_STRFTIME_FMT_N`

**Type:** Python strftime format string\
**Default:** `"%Y-%m-%dT%H:%M:%S%z"` (ISO 8601)

Format string for sending datetime values to the NEMO API. Only needed if your NEMO instance uses non-standard date formats.

**Example:**
```bash
NX_NEMO_STRFTIME_FMT_1=%Y-%m-%d %H:%M:%S
```

(config-nemo-strptime-fmt)=
#### `NX_NEMO_STRPTIME_FMT_N`

**Type:** Python strptime format string\
**Default:** `"%Y-%m-%dT%H:%M:%S%z"` (ISO 8601)

Format string for parsing datetime values from the NEMO API. Only needed if your NEMO instance returns non-standard date formats.

**Example:**
```bash
NX_NEMO_STRPTIME_FMT_1=%Y-%m-%d %H:%M:%S
```

(config-nemo-tz)=
#### `NX_NEMO_TZ_N`

**Type:** IANA timezone name\
**Default:** None

Timezone to coerce NEMO API datetime strings into. Only needed if the NEMO server doesn't return timezone information in API responses.

**⚠️ Warning:** This overrides timezone from API responses. Only use if your NEMO instance doesn't provide timezone data.

**Example:**
```bash
NX_NEMO_TZ_1=America/Denver
NX_NEMO_TZ_2=America/New_York
```

See [IANA Time Zone Database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for valid timezone names.

### SSL/TLS Configuration

(config-cert-bundle-file)=
#### `NX_CERT_BUNDLE_FILE`

**Type:** File path\
**Default:** None

Path to a custom SSL certificate CA bundle for verifying HTTPS requests to CDCS or NEMO APIs. Certificates in this bundle are appended to the system's default certificates.

**Example:**
```bash
NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca-bundle.crt
```

(config-cert-bundle)=
#### `NX_CERT_BUNDLE`

**Type:** String (PEM-formatted certificates)\
**Default:** None

Alternative to `NX_CERT_BUNDLE_FILE` - provide the entire certificate bundle as a string. Useful for CI/CD pipelines. Lines should be separated by `\n`. Takes precedence over `NX_CERT_BUNDLE_FILE` if both are set.

**Example:**
```bash
NX_CERT_BUNDLE="-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----"
```

(config-disable-ssl-verify)=
#### `NX_DISABLE_SSL_VERIFY`

**Type:** Boolean\
**Default:** `false`

```{warning}
This setting should **only** be used during local development or testing.
Never enable it in production — it disables all certificate verification,
leaving connections vulnerable to interception.
```

Disable SSL certificate verification for all outgoing HTTPS requests made by
NexusLIMS (to CDCS, NEMO, eLabFTW, etc.). This is useful in local test
deployments where multiple services use self-signed or `mkcert`-issued
certificates and providing every CA via `NX_CERT_BUNDLE_FILE` is impractical.

When enabled, a warning is logged once per process run as a reminder.

**Example:**
```bash
NX_DISABLE_SSL_VERIFY=true
```

### Email Notifications

Email notifications are optional but recommended for production deployments. They alert administrators when record building fails.

(config-email-smtp-host)=
#### `NX_EMAIL_SMTP_HOST`

**Type:** String\
**Required for email:** Yes

SMTP server hostname for sending email notifications.

**Example:**
```bash
NX_EMAIL_SMTP_HOST=smtp.gmail.com
```

(config-email-smtp-port)=
#### `NX_EMAIL_SMTP_PORT`

**Type:** Integer\
**Default:** `587`

SMTP server port. Common values:
- `587` - STARTTLS (recommended)
- `465` - SSL/TLS
- `25` - Unencrypted (not recommended)

**Example:**
```bash
NX_EMAIL_SMTP_PORT=587
```

(config-email-smtp-username)=
#### `NX_EMAIL_SMTP_USERNAME`

**Type:** String\
**Default:** None

SMTP username for authentication (if required by your SMTP server).

**Example:**
```bash
NX_EMAIL_SMTP_USERNAME=nexuslims@example.com
```

(config-email-smtp-password)=
#### `NX_EMAIL_SMTP_PASSWORD`

**Type:** String\
**Default:** None

SMTP password for authentication (if required by your SMTP server).

**Example:**
```bash
NX_EMAIL_SMTP_PASSWORD=app_specific_password
```

(config-email-use-tls)=
#### `NX_EMAIL_USE_TLS`

**Type:** Boolean (`true`/`false`, `1`/`0`, `yes`/`no`)\
**Default:** `true`

Enable TLS encryption for SMTP connection. Recommended for security.

**Example:**
```bash
NX_EMAIL_USE_TLS=true
```

(config-email-sender)=
#### `NX_EMAIL_SENDER`

**Type:** Email address\
**Required for email:** Yes

Email address to send notifications from.

**Example:**
```bash
NX_EMAIL_SENDER=nexuslims@example.com
```

(config-email-recipients)=
#### `NX_EMAIL_RECIPIENTS`

**Type:** Comma-separated email addresses\
**Required for email:** Yes

List of recipient email addresses for error notifications.

**Example:**
```bash
NX_EMAIL_RECIPIENTS=admin@example.com,team@example.com
```

## Configuration in Code

### Accessing Configuration

Always access configuration through the `settings` object from the `nexusLIMS.config` module:

```python
from nexusLIMS.config import settings

# Access configuration values
data_path = settings.NX_DATA_PATH
file_strategy = settings.NX_FILE_STRATEGY
db_path = settings.NX_DB_PATH

# Access NEMO harvesters (returns dict of configurations)
nemo_harvesters = settings.nemo_harvesters()

# Access email configuration (returns EmailConfig or None)
email_config = settings.email_config()
```

```{danger}
**Never use `os.getenv()` or `os.environ` directly for NexusLIMS configuration.**

Always access configuration through the `settings` object from `nexusLIMS.config`. This ensures:
- Type safety and validation
- Consistent behavior across the codebase
- Proper defaults and error handling
- Easier testing (can mock the settings object)
```

### Testing with Configuration

In tests, use `refresh_settings()` after modifying environment variables:

```python
import os
from nexusLIMS.config import settings, refresh_settings

def test_with_custom_config():
    # Modify environment
    os.environ["NX_FILE_STRATEGY"] = "inclusive"

    # Refresh to pick up changes
    refresh_settings()

    # Now settings reflects the new value
    assert settings.NX_FILE_STRATEGY == "inclusive"
```

## Configuration Validation

Pydantic validates all configuration on startup. If validation fails, NexusLIMS will raise a `ValidationError` with details about what's wrong.

Common validation errors:
- **Missing required fields**: Set all required environment variables
- **Invalid paths**: Ensure directories/files exist and are accessible
- **Invalid URLs**: Check URL format and trailing slashes
- **Invalid types**: Check value types (numbers, booleans, etc.)

## Example Configurations

### Minimal Production Configuration

```bash
# File paths
NX_INSTRUMENT_DATA_PATH=/mnt/nexus_instruments
NX_DATA_PATH=/var/nexuslims/data
NX_DB_PATH=/var/nexuslims/data/nexuslims.db

# CDCS
NX_CDCS_URL=https://nexuslims.example.com
NX_CDCS_TOKEN=your-api-token-here

# NEMO
NX_NEMO_ADDRESS_1=https://nemo.example.com/api/
NX_NEMO_TOKEN_1=token_here
```

### Full Production Configuration

```bash
# File paths
NX_INSTRUMENT_DATA_PATH=/mnt/nexus_instruments
NX_DATA_PATH=/var/nexuslims/data
NX_DB_PATH=/var/nexuslims/data/nexuslims.db
NX_LOG_PATH=/var/log/nexuslims
NX_RECORDS_PATH=/var/nexuslims/records

# Local profiles
NX_LOCAL_PROFILES_PATH=/etc/nexuslims/profiles

# CDCS
NX_CDCS_URL=https://nexuslims.example.com
NX_CDCS_TOKEN=your-api-token-here

# File handling
NX_FILE_STRATEGY=inclusive
NX_FILE_DELAY_DAYS=2.5
NX_IGNORE_PATTERNS=["*.mib", "*.db", "*.emi", "*.tmp"]

# NEMO instances
NX_NEMO_ADDRESS_1=https://nemo1.example.com/api/
NX_NEMO_TOKEN_1=token1_here
NX_NEMO_TZ_1=America/Denver

NX_NEMO_ADDRESS_2=https://nemo2.example.com/api/
NX_NEMO_TOKEN_2=token2_here
NX_NEMO_TZ_2=America/New_York

# Email notifications
NX_EMAIL_SMTP_HOST=smtp.gmail.com
NX_EMAIL_SMTP_PORT=587
NX_EMAIL_SMTP_USERNAME=nexuslims@example.com
NX_EMAIL_SMTP_PASSWORD=app_password
NX_EMAIL_USE_TLS=true
NX_EMAIL_SENDER=nexuslims@example.com
NX_EMAIL_RECIPIENTS=admin@example.com,team@example.com

# SSL certificates (if needed)
NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca.crt
```

### Development/Testing Configuration

```bash
# File paths (local development)
NX_INSTRUMENT_DATA_PATH=/tmp/test_instruments
NX_DATA_PATH=/tmp/test_data
NX_DB_PATH=/tmp/test_data/nexuslims.db

# CDCS (test instance)
NX_CDCS_URL=https://nexuslims-test.example.com
NX_CDCS_TOKEN=test-api-token-here

# NEMO (test instance)
NX_NEMO_ADDRESS_1=https://nemo-test.example.com/api/
NX_NEMO_TOKEN_1=test_token

# Aggressive file finding for testing
NX_FILE_STRATEGY=inclusive
NX_FILE_DELAY_DAYS=0.1

# Skip SSL verification for local self-signed/mkcert certs
NX_DISABLE_SSL_VERIFY=true
```

## Troubleshooting

### Configuration Not Loading

If configuration changes aren't taking effect:

1. **Check .env file location**: Must be in project root
2. **Check environment variables**: `os.environ` takes precedence over `.env`
3. **Restart application**: Configuration is loaded on startup
4. **Check for typos**: Variable names are case-sensitive

### Path Validation Errors

If you get path validation errors:

1. **Ensure directories exist**: Create them before starting NexusLIMS
2. **Check permissions**: Ensure the user running NexusLIMS has read/write access
3. **Use absolute paths**: Avoid relative paths
4. **Check for typos**: Verify path spelling

### NEMO Configuration Issues

If NEMO harvesters aren't working:

1. **Check trailing slash**: `NX_NEMO_ADDRESS_N` must end with `/`
2. **Match suffixes**: `NX_NEMO_ADDRESS_1` must pair with `NX_NEMO_TOKEN_1`
3. **Verify tokens**: Test tokens in the NEMO admin interface
4. **Check timezone format**: Use IANA timezone names (e.g., `America/Denver`)

### Email Not Working

If email notifications aren't sending:

1. **Check required fields**: `NX_EMAIL_SMTP_HOST`, `NX_EMAIL_SENDER`, and `NX_EMAIL_RECIPIENTS` are required
2. **Verify SMTP credentials**: Test SMTP access independently
3. **Check firewall**: Ensure SMTP port (usually 587) isn't blocked
4. **Use app passwords**: Some providers (Gmail) require app-specific passwords

### Instrument Profile Issues

If instrument profiles aren't loading or working:

1. **Verify `NX_LOCAL_PROFILES_PATH`**: Ensure the environment variable points to a valid directory
2. **Check profile structure**: Profiles must create an `InstrumentProfile` instance and register it via `get_profile_registry().register()`
3. **Match `instrument_id` to database**: The `instrument_id` parameter in `InstrumentProfile()` must match the instrument's `name` field in the database (filename doesn't matter)
4. **Import errors**: Check that all dependencies are available in the environment

## See Also

- {ref}`getting_started` - Initial setup guide
- {ref}`instrument-profiles` - Customizing metadata extraction
- {ref}`record-building` - Understanding the record building process
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
