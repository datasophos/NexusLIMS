(configuration)=
# Configuration

This guide provides comprehensive information about configuring NexusLIMS through environment variables. All configuration is managed through the centralized `nexusLIMS.config` module, which uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for validation and type safety.

## Configuration Files

NexusLIMS loads configuration from environment variables and optionally from a `.env` file in the project root. See `.env.example` in the repository for a complete template with examples.

```{tip}
Copy `.env.example` to `.env` and customize it for your deployment. The `.env` file should never be committed to version control.
```

(configuration-management)=
## Configuration Management

NexusLIMS provides CLI tools to help you manage, debug, and migrate configuration between environments.

### Dumping Configuration

Use `nexuslims-config dump` to export your current configuration to a JSON file:

```bash
# Dump to default file (nexuslims_config.json)
nexuslims-config dump

# Dump to specific file
nexuslims-config dump --output /path/to/my-config.json
```

The dumped configuration includes:

- All environment variables (from both environment and `.env` file)
- Parsed NEMO harvester configurations
- Email configuration (if configured)
- Computed defaults for optional settings

```{danger}
**Security Warning**: The dumped JSON file contains **live credentials** (API tokens, passwords, certificates). Handle it with the same care as your `.env` file. Never commit it to version control or share it publicly.
```

Example output:
```json
{
  "NX_DATA_PATH": "/var/nexuslims/data",
  "NX_INSTRUMENT_DATA_PATH": "/mnt/nexus_instruments",
  "NX_DB_PATH": "/var/nexuslims/data/nexuslims.db",
  "NX_CDCS_URL": "https://nexuslims.example.com",
  "NX_CDCS_TOKEN": "live-secret-token-here",
  "nemo_harvesters": {
    "1": {
      "address": "https://nemo.example.com/api/",
      "token": "live-secret-token-here",
      "tz": null
    }
  },
  "email_config": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_password": "live-password-here",
    "sender": "nexuslims@example.com",
    "recipients": ["admin@example.com"]
  }
}
```

**Use cases for config dumps:**

- **Backup**: Create a complete snapshot of a working configuration
- **Migration**: Transfer configuration to a new server (see Loading Configuration below)
- **Comparison**: Diff configs between environments to identify differences
- **Disaster recovery**: Quick restoration of configuration after system failure

### Loading Configuration

Use `nexuslims-config load` to convert a dumped JSON config back into a `.env` file:

```bash
# Load config (creates/overwrites .env in current directory)
nexuslims-config load nexuslims_config.json

# Load to specific .env file
nexuslims-config load nexuslims_config.json --env-path /path/to/.env

# Skip confirmation prompt (useful for automation)
nexuslims-config load nexuslims_config.json --force
```

**Safety features:**

- **Backup**: If `.env` exists, it's automatically backed up to `.env.bak.YYYYMMDD-HHMMSS` before overwriting
- **Confirmation**: Prompts for confirmation before overwriting (unless `--force` is used)
- **Flattening**: Structured config (nested harvesters, email config) is converted back to flat environment variables

**Migration workflow example:**

```bash
# On source server
nexuslims-config dump --output production-config.json

# Securely transfer the file to new server (contains live credentials!)
scp production-config.json user@newserver:/path/to/

# On destination server
nexuslims-config load production-config.json

# Clean up the dump file (it contains secrets)
rm production-config.json
```

### Configuration in Logs

When `nexuslims-process-records` starts with a verbosity of `-v` or higher,
it logs a sanitized view of the loaded configuration to help with debugging.
The log output is sanitized, ensuring no sensitive environment variables
are exposed in logs.

Example log output:
```
INFO - Loaded configuration:
INFO - {
INFO -   "NX_DATA_PATH": "/var/nexuslims/data",
INFO -   "NX_CDCS_TOKEN": "***",
INFO -   "nemo_harvesters": {
INFO -     "1": {"address": "https://nemo.example.com/api/", "token": "***"}
INFO -   }
INFO - }
```

This is particularly useful when:

- Troubleshooting why a specific setting isn't taking effect
- Verifying that `.env` changes were picked up
- Confirming which NEMO instances are configured
- Checking computed defaults for optional settings

## Required Configuration

These variables **must** be configured for NexusLIMS to function.

### File System Paths

(config-instrument-data-path)=
#### `NX_INSTRUMENT_DATA_PATH`

```{config-detail} NX_INSTRUMENT_DATA_PATH
```

**Example:**
```bash
NX_INSTRUMENT_DATA_PATH=/mnt/nexus_instruments
```

(config-data-path)=
#### `NX_DATA_PATH`

```{config-detail} NX_DATA_PATH
```

**Example:**
```bash
NX_DATA_PATH=/var/nexuslims/data
```

(config-db-path)=
#### `NX_DB_PATH`

```{config-detail} NX_DB_PATH
```

**Example:**
```bash
NX_DB_PATH=/var/nexuslims/data/nexuslims.db
```

### CDCS Integration

(config-cdcs-url)=
#### `NX_CDCS_URL`

```{config-detail} NX_CDCS_URL
```

**Example:**
```bash
NX_CDCS_URL=https://nexuslims.example.com
```

(config-cdcs-token)=
#### `NX_CDCS_TOKEN`

```{config-detail} NX_CDCS_TOKEN
```

**Example:**
```bash
NX_CDCS_TOKEN=your-api-token-here
```

```{warning}
Store API tokens securely. Use environment variables or a secure secrets management system rather than committing tokens to version control.
```

### NEMO Integration

NexusLIMS supports multiple NEMO instances by using numbered environment variable pairs. Each NEMO instance requires an address and token.

(config-nemo-address)=
#### `NX_NEMO_ADDRESS_N`

```{config-detail} nemo.address
```

**Example:**
```bash
NX_NEMO_ADDRESS_1=https://nemo1.example.com/api/
NX_NEMO_ADDRESS_2=https://nemo2.example.com/api/
```

(config-nemo-token)=
#### `NX_NEMO_TOKEN_N`

```{config-detail} nemo.token
```

**Example:**
```bash
NX_NEMO_TOKEN_1=abc123def456...
NX_NEMO_TOKEN_2=xyz789uvw012...
```

## Optional Configuration


### eLabFTW Integration

(config-elabftw)=

NexusLIMS can optionally export records to [eLabFTW](https://www.elabftw.net/), an open-source electronic lab notebook. Each NexusLIMS session creates one eLabFTW experiment with a structured summary and the full XML record attached.

(config-elabftw-url)=
#### `NX_ELABFTW_URL`

```{config-detail} NX_ELABFTW_URL
```

**Example:**
```bash
NX_ELABFTW_URL=https://elabftw.example.com
```

(config-elabftw-api-key)=
#### `NX_ELABFTW_API_KEY`

```{config-detail} NX_ELABFTW_API_KEY
```

**Example:**
```bash
NX_ELABFTW_API_KEY=1-abcdef0123456789...
```

```{note}
eLabFTW API keys have the format `{id}-{key}` where the key portion is 84 hexadecimal characters.
```

(config-elabftw-experiment-category)=
#### `NX_ELABFTW_EXPERIMENT_CATEGORY`

```{config-detail} NX_ELABFTW_EXPERIMENT_CATEGORY
```

**Example:**
```bash
NX_ELABFTW_EXPERIMENT_CATEGORY=1
```

(config-elabftw-experiment-status)=
#### `NX_ELABFTW_EXPERIMENT_STATUS`

```{config-detail} NX_ELABFTW_EXPERIMENT_STATUS
```

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

### Export Configuration

(config-export-strategy)=
#### `NX_EXPORT_STRATEGY`

```{config-detail} NX_EXPORT_STRATEGY
```

**Example:**
```bash
NX_EXPORT_STRATEGY=best_effort
```

```{note}
See the {ref}`exporters` page for a full description of how strategies interact with destination priorities and inter-destination dependencies (e.g. eLabFTW cross-linking to a CDCS record).
```


### File Handling

(config-file-strategy)=
#### `NX_FILE_STRATEGY`

```{config-detail} NX_FILE_STRATEGY
```

**Example:**
```bash
NX_FILE_STRATEGY=inclusive
```

(config-ignore-patterns)=
#### `NX_IGNORE_PATTERNS`

```{config-detail} NX_IGNORE_PATTERNS
```

**Example:**
```bash
NX_IGNORE_PATTERNS=["*.mib", "*.db", "*.emi", "*.tmp", "*~"]
```

(config-file-delay-days)=
#### `NX_FILE_DELAY_DAYS`

```{config-detail} NX_FILE_DELAY_DAYS
```

```bash
NX_FILE_DELAY_DAYS=2.5
```

(config-clustering-sensitivity)=
#### `NX_CLUSTERING_SENSITIVITY`

```{config-detail} NX_CLUSTERING_SENSITIVITY
```

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

```{config-detail} NX_LOG_PATH
```

**Example:**
```bash
NX_LOG_PATH=/var/log/nexuslims
```

(config-records-path)=
#### `NX_RECORDS_PATH`

```{config-detail} NX_RECORDS_PATH
```

**Example:**
```bash
NX_RECORDS_PATH=/var/nexuslims/records
```

(config-local-profiles-path)=
#### `NX_LOCAL_PROFILES_PATH`

```{config-detail} NX_LOCAL_PROFILES_PATH
```

See {ref}`instrument-profiles` for details on writing profile modules.

**Example:**
```bash
NX_LOCAL_PROFILES_PATH=/etc/nexuslims/profiles
```

### NEMO Advanced Options

(config-nemo-strftime-fmt)=
#### `NX_NEMO_STRFTIME_FMT_N`

```{config-detail} nemo.strftime_fmt
```

**Example:**
```bash
NX_NEMO_STRFTIME_FMT_1=%Y-%m-%d %H:%M:%S
```

(config-nemo-strptime-fmt)=
#### `NX_NEMO_STRPTIME_FMT_N`

```{config-detail} nemo.strptime_fmt
```

**Example:**
```bash
NX_NEMO_STRPTIME_FMT_1=%Y-%m-%d %H:%M:%S
```

(config-nemo-tz)=
#### `NX_NEMO_TZ_N`

```{config-detail} nemo.tz
```

**Example:**
```bash
NX_NEMO_TZ_1=America/Denver
NX_NEMO_TZ_2=America/New_York
```

### SSL/TLS Configuration

(config-cert-bundle-file)=
#### `NX_CERT_BUNDLE_FILE`

```{config-detail} NX_CERT_BUNDLE_FILE
```

**Example:**
```bash
NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca-bundle.crt
```

(config-cert-bundle)=
#### `NX_CERT_BUNDLE`

```{config-detail} NX_CERT_BUNDLE
```

**Example:**
```bash
NX_CERT_BUNDLE="-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----"
```

(config-disable-ssl-verify)=
#### `NX_DISABLE_SSL_VERIFY`

```{config-detail} NX_DISABLE_SSL_VERIFY
```

**Example:**
```bash
NX_DISABLE_SSL_VERIFY=true
```

### Email Notifications

Email notifications are optional but recommended for production deployments. They alert administrators when record building fails.

(config-email-smtp-host)=
#### `NX_EMAIL_SMTP_HOST`

**Required for email:** Yes

```{config-detail} email.smtp_host
```

**Example:**
```bash
NX_EMAIL_SMTP_HOST=smtp.gmail.com
```

(config-email-smtp-port)=
#### `NX_EMAIL_SMTP_PORT`

```{config-detail} email.smtp_port
```

**Example:**
```bash
NX_EMAIL_SMTP_PORT=587
```

(config-email-smtp-username)=
#### `NX_EMAIL_SMTP_USERNAME`

```{config-detail} email.smtp_username
```

**Example:**
```bash
NX_EMAIL_SMTP_USERNAME=nexuslims@example.com
```

(config-email-smtp-password)=
#### `NX_EMAIL_SMTP_PASSWORD`

```{config-detail} email.smtp_password
```

**Example:**
```bash
NX_EMAIL_SMTP_PASSWORD=app_specific_password
```

(config-email-use-tls)=
#### `NX_EMAIL_USE_TLS`

```{config-detail} email.use_tls
```

**Example:**
```bash
NX_EMAIL_USE_TLS=true
```

(config-email-sender)=
#### `NX_EMAIL_SENDER`

**Required for email:** Yes

```{config-detail} email.sender
```

**Example:**
```bash
NX_EMAIL_SENDER=nexuslims@example.com
```

(config-email-recipients)=
#### `NX_EMAIL_RECIPIENTS`

**Required for email:** Yes

```{config-detail} email.recipients
```

**Example:**
```bash
NX_EMAIL_RECIPIENTS=admin@example.com,team@example.com
```

## Configuration in Code (for developers)

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

### Full Example Production Configuration

```bash
# ============================================================================
# File paths
# ============================================================================
NX_INSTRUMENT_DATA_PATH=/mnt/nexus_instruments
NX_DATA_PATH=/var/nexuslims/data
NX_DB_PATH=/var/nexuslims/data/nexuslims.db
NX_LOG_PATH=/var/log/nexuslims
NX_RECORDS_PATH=/var/nexuslims/records

# Local profiles
NX_LOCAL_PROFILES_PATH=/etc/nexuslims/profiles

# ============================================================================
# CDCS Integration
# ============================================================================
NX_CDCS_URL=https://nexuslims.example.com
NX_CDCS_TOKEN=your-api-token-here

# ============================================================================
# Export Configuration
# ============================================================================
# Strategy for exporting to multiple destinations ('all', 'first_success', 'best_effort')
NX_EXPORT_STRATEGY=all

# ============================================================================
# eLabFTW Integration (optional)
# ============================================================================
NX_ELABFTW_URL=https://elabftw.example.com
NX_ELABFTW_API_KEY=your-elabftw-api-key
NX_ELABFTW_EXPERIMENT_CATEGORY=1
NX_ELABFTW_EXPERIMENT_STATUS=1

# ============================================================================
# File Handling
# ============================================================================
NX_FILE_STRATEGY=inclusive
NX_FILE_DELAY_DAYS=2.5
NX_CLUSTERING_SENSITIVITY=1.0
NX_IGNORE_PATTERNS='["*.mib","*.db","*.emi","*.hdr"]'

# ============================================================================
# NEMO Harvesters
# ============================================================================
# First NEMO instance
NX_NEMO_ADDRESS_1=https://nemo1.example.com/api/
NX_NEMO_TOKEN_1=token1_here
NX_NEMO_TZ_1=America/Denver
NX_NEMO_STRFTIME_FMT_1=%Y-%m-%dT%H:%M:%S%z
NX_NEMO_STRPTIME_FMT_1=%Y-%m-%dT%H:%M:%S%z

# Second NEMO instance (optional)
NX_NEMO_ADDRESS_2=https://nemo2.example.com/api/
NX_NEMO_TOKEN_2=token2_here
NX_NEMO_TZ_2=America/New_York

# ============================================================================
# Email Notifications (optional)
# ============================================================================
NX_EMAIL_SMTP_HOST=smtp.gmail.com
NX_EMAIL_SMTP_PORT=587
NX_EMAIL_SMTP_USERNAME=nexuslims@example.com
NX_EMAIL_SMTP_PASSWORD=app_password
NX_EMAIL_USE_TLS=true
NX_EMAIL_SENDER=nexuslims@example.com
NX_EMAIL_RECIPIENTS=admin@example.com,team@example.com

# ============================================================================
# SSL Certificate Configuration (optional)
# ============================================================================
# Option 1: Path to certificate bundle file
NX_CERT_BUNDLE_FILE=/etc/ssl/certs/custom-ca.crt

# Option 2: Certificate bundle as string (alternative to NX_CERT_BUNDLE_FILE)
# NX_CERT_BUNDLE="-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"

# Option 3: Disable SSL verification (NEVER use in production!)
# NX_DISABLE_SSL_VERIFY=false
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
