(configuration)=
# Configuration

This guide provides comprehensive information about configuring NexusLIMS through environment variables. All configuration is managed through the centralized `nexusLIMS.config` module, which uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for validation and type safety.

## Configuration Files

NexusLIMS looks for its configuration file at `~/.config/nexuslims/config.toml`, followed by `/etc/nexuslims/config.toml` by default (where `~` represents the home directory of the user account used to run NexusLIMS). You can set the `NX_CONFIG_FILE` environment variable to select another TOML file or an older style `.env` file (if you have a configuration from a version before 2.9.0). Environment variables set for the process will override values provided in the config file. If the selected file does not exist, NexusLIMS will use environment variables and built-in defaults where possible, though the required variables still need to be supplied.

NexusLIMS selects one configuration file in this order:

1. The absolute path in `NX_CONFIG_FILE`, if set, even if that file does not exist.
2. `~/.config/nexuslims/config.toml`, if it exists.
3. `/etc/nexuslims/config.toml`, if it exists.
4. The user path `~/.config/nexuslims/config.toml`, when neither file exists.

The files are not merged. Files ending in `.toml` are read as TOML; other filenames are read as dotenv. Process environment variables override values from a config file. The editor and `nexuslims config load` use that same path, so changing a system-wide file requires write permission; use `--config-path` to choose another destination. A user file takes precedence over the system file, including for services running under that user account.

You can use `nexuslims config edit` to create the config file if one does not exist; the command displays the path to the config file in the top line of the TUI, for reference. `nexuslims config load` will use the same path. Both commands accept a `--config-path` option to explicitly select a different destination. The TOML file contains `[core]`, `[integrations]`, `[email_config]`, and `[nemo_harvesters.N]` sections as needed. The config editor creates new files with owner-only permissions by default. Since configuration files and JSON exports contain credentials, you should restrict access to their owner (for example, `chmod 600 /path/to/config.toml`) and protect backups.

See the {ref}`complete TOML reference example <configuration-example>` for a copyable configuration showing all supported settings.

The data directories and database file must exist before settings are validated. You should use absolute paths for all path settings so they resolve consistently. For a service or scheduled job (which often run from cron as a different user), you should explicitly set `NX_CONFIG_FILE` to the absolute path of the config file and ensure the service account can read it.

To migrate an existing working-directory `.env` (from versions of NexusLIMS prior to 2.9.0), export it using the `NX_CONFIG_FILE` environment variable, then import the resulting JSON into the default TOML location:

```bash
backup=$(mktemp "${TMPDIR:-/tmp}/nexuslims-config.XXXXXX")
NX_CONFIG_FILE="$PWD/.env" nexuslims config dump --output "$backup" &&
env -u NX_CONFIG_FILE nexuslims config load "$backup" \
  --config-path "$HOME/.config/nexuslims/config.toml"
```

Run the commands from the directory containing `.env`, after upgrading. This writes to the user configuration path even if a system configuration exists; to replace the system file instead, choose it with `--config-path` and ensure you have write permission. The dump validates the effective configuration and includes process environment overrides; incomplete NEMO or email configurations may be omitted. Check the resulting TOML and preserve the original `.env` until you have verified the migration. The temporary JSON contains credentials: keep it private and remove it when no longer needed.

Alternatively, you can keep using the old `.env` file by setting `NX_CONFIG_FILE` to its absolute path for every process, but it is recommended to upgrade to the new config format going forward. As of version 2.9.0, NexusLIMS will no longer automatically read the working directory for `.env`.

(configuration-management)=
## Configuration Management

NexusLIMS provides both CLI tools and an interactive terminal UI to help you manage, debug, and migrate your configurations between environments.

### Inspecting configuration selection

Commands report the selected configuration file and its source on standard error; help and version output stay quiet. The `nexuslims config status` command instead prints a complete report to standard output, including the selected file, user and system candidates, effective process user, and names of process environment variables that override settings. Values are never shown. This diagnostic works even when the selected file or application settings are invalid. Service accounts may use a different home directory from your login account.

### Interactive Configuration Editor (TUI)

The **NexusLIMS Configuration Editor** provides a user-friendly terminal interface for editing your configuration file:

```bash
# Launch the interactive configurator
nexuslims config edit

# Edit a specific configuration file
nexuslims config edit --config-path /path/to/config.toml
```

The editor shows the selected configuration file and waits for Enter before opening. Its title also displays the file path. `--config-path` (or its alias `--env-path`) opens a specific file and warns if it is not active. The editor requires an interactive terminal.

The configurator features:

- **Tabbed Interface**: Organized into logical sections (Core Paths, CDCS, File Processing, etc.)
- **Pre-populated Fields**: Loads existing configuration values automatically
- **Real-time Validation**: Catches errors before saving
- **Context-sensitive Help**: Press **F1** on any field for detailed documentation
- **Dynamic NEMO Management**: Add/remove multiple NEMO harvester instances
- **Toggle Sections**: Enable/disable optional features like eLabFTW and Email alerts

```{figure} ../images/tui/screenshots/config_main_screen.svg
:name: config-tui-main-screen

Main Screen of the configuration TUI
```

**Navigation:**
- **`Tab` / `Shift+Tab`**: Move between fields
- **`<` / `>`**: Navigate between tabs
- **`F1`**: Show field-specific help
- **`Ctrl+S`**: Save configuration
- **`Escape`**: Cancel/Exit
- **`?`**: Show the overall help screen

```{figure} ../images/tui/screenshots/config_help_screen.svg
:name: config-tui-help-screen

Configuration app general help screen (shown with `?` key)
```

**Field Help:** Press **F1** while focused on any field to see extended documentation:

```{figure} ../images/tui/screenshots/config_field_detail.svg
:name: config-tui-field-detail

Showing the detailed help for a particular field (by pressing `F1`)
```

#### Video Demonstrations

This demo shows opening the configuration tool, browsing around the "tabs" that separate
the logical grouping of config values, showing the help screen, and then exiting:

```{raw} html
<figure>
  <video src="../_images/config_main.mp4" width="100%" controls autoplay muted loop aria-label="Configuration tool demonstration video">
  </video>
  <figcaption>Demonstration of the main screens in the interactive configuration tool</figcaption>
</figure>
```
<!-- this hidden span is so Sphinx will properly copy the video to the right location -->
<span style="display: none;">![main config screen](../images/tui/recordings/config_main.mp4)</span>

This video demonstrates using the `F1` key to show detailed help for various configuration variables.
This capability can help you learn more about what each setting does and how to properly set the values:


```{raw} html
<figure>
  <video src="../_images/config_field_help.mp4" width="100%" controls autoplay muted loop></video>
  <figcaption>Using the <code>F1</code> key to view detailed help for different fields</figcaption>
</figure>
```
<!-- this hidden span is so Sphinx will properly copy the video to the right location -->
<span style="display: none;">![main config screen](../images/tui/recordings/config_field_help.mp4)</span>

This video demonstrates adding a NEMO harvester configuration to the application. Since NexusLIMS supports
multiple NEMO instances in one installation, the configuration tool allows you to add/delete harvesters
and fill out each harvester's configuration in a logical grouping:

```{raw} html
<figure>
  <video src="../_images/config_nemo_management.mp4" width="100%" controls autoplay muted loop></video>
  <figcaption>Adding a NEMO harvester configuration, then adding a second one, and finally deleting it</figcaption>
</figure>
```
<!-- this hidden span is so Sphinx will properly copy the video to the right location -->
<span style="display: none;">![main config screen](../images/tui/recordings/config_nemo_management.mp4)</span>

### Dumping Configuration

Use `nexuslims config dump` to export your current configuration as JSON:

```bash
# Print JSON to stdout
nexuslims config dump

# Dump to specific file
nexuslims config dump --output /path/to/my-config.json
```

The dumped configuration includes:

- All effective settings (from both environment and the selected file)
- Parsed NEMO harvester configurations
- Email configuration (if configured)
- Computed defaults for optional settings

```{danger}
**Security Warning**: The dumped JSON contains **live credentials** (API tokens, passwords, certificates). Handle it with the same care as your configuration file. Never commit it to version control or share it publicly. `--output` overwrites an existing file without prompting; restrict the destination's permissions before use.
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

Use `nexuslims config load` to convert a dumped JSON config back into the selected configuration file:

```bash
# Load config (creates or overwrites the selected file)
nexuslims config load nexuslims_config.json

# Load to a specific configuration file
nexuslims config load nexuslims_config.json --config-path /path/to/config.toml

# Skip confirmation prompt (useful for automation)
nexuslims config load nexuslims_config.json --force
```

**Safety features:**

- **Backup**: If the selected file exists, a timestamped backup is created before overwriting
- **Confirmation**: Prompts for confirmation before overwriting (unless `--force` is used)
- **Format**: TOML destinations use sections for NEMO and email; other destinations are written in dotenv format

**Migration workflow example:**

```bash
# On source server
nexuslims config dump --output production-config.json

# Securely transfer the file to new server (contains live credentials!)
scp production-config.json user@newserver:/path/to/

# On destination server (adjust paths and credentials for that deployment)
nexuslims config load production-config.json

# Clean up the dump file (it contains secrets)
rm production-config.json
```

### Configuration in Logs

When `nexuslims build-records` starts with a verbosity of `-v` or higher,
it logs a sanitized view of the loaded configuration to help with debugging.
Known secrets such as tokens, passwords, and certificate contents are redacted.
Other settings, including identifiers and paths, can still be present; handle logs
accordingly.

Example log output:
```
INFO - Effective configuration:
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
- Verifying that configuration changes were picked up
- Confirming which NEMO instances are configured
- Checking computed defaults for optional settings

## Required Configuration

These settings are required for configured operations such as record building and `config dump`; some standalone commands can run without them. The assignment examples below show environment variable names and dotenv syntax; they are not TOML syntax. Set them in the selected file or export them in the process environment. See the {ref}`TOML reference example <configuration-example>` for section and quoting conventions.

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

(config-cdcs-user-owned-records)=
#### `NX_CDCS_USER_OWNED_RECORDS`

```{config-detail} NX_CDCS_USER_OWNED_RECORDS
```

**Example:**
```bash
NX_CDCS_USER_OWNED_RECORDS=true
```

(config-cdcs-assign-workspace)=
#### `NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE`

```{config-detail} NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE
```

**Example:**
```bash
NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE=true
```

```{warning}
Store API tokens securely. Use environment variables or a secure secrets management system rather than committing tokens to version control.
```

### NEMO Integration

For NEMO-backed instruments, configure the corresponding NEMO instance. NexusLIMS supports multiple instances using numbered environment variable pairs; each instance requires an address and token. In TOML, configure each instance under `[nemo_harvesters.N]` using keys such as `address` and `token`.

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
- **Title:** `NexusLIMS Experiment - {XML filename without extension}`
- **Body:** HTML summary with session details and link to CDCS record (if available)
- **Tags:** NexusLIMS, instrument name, username
- **Metadata:** Structured extra_fields including session times, instrument, user, and CDCS cross-link
- **Attachment:** Full XML record file
```

(config-labarchives)=
### LabArchives Integration

NexusLIMS can optionally export records to [LabArchives](https://www.labarchives.com/), a
commercial electronic lab notebook system. Each NexusLIMS session creates one notebook page
with an HTML session summary and the full XML record attached as a file when a notebook ID is configured. Without a notebook ID, entries are added to the user’s Inbox.

LabArchives authentication uses HMAC-SHA-512 signed requests. Configure an Access Key ID and Access Password (provided by LabArchives), a User ID (uid), and the instance URL (which can usually use its default unless you are in a different region).

(config-labarchives-url)=
#### `NX_LABARCHIVES_URL`

```{config-detail} NX_LABARCHIVES_URL
```

**Example:**
```bash
NX_LABARCHIVES_URL=https://api.labarchives.com/api
```

(config-labarchives-access-key-id)=
#### `NX_LABARCHIVES_ACCESS_KEY_ID`

```{config-detail} NX_LABARCHIVES_ACCESS_KEY_ID
```

**Example:**
```bash
NX_LABARCHIVES_ACCESS_KEY_ID=your-access-key-id-here
```

(config-labarchives-access-password)=
#### `NX_LABARCHIVES_ACCESS_PASSWORD`

```{config-detail} NX_LABARCHIVES_ACCESS_PASSWORD
```

**Example:**
```bash
NX_LABARCHIVES_ACCESS_PASSWORD=your-access-password-here
```

(config-labarchives-user-id)=
#### `NX_LABARCHIVES_USER_ID`

```{config-detail} NX_LABARCHIVES_USER_ID
```

**Example:**
```bash
NX_LABARCHIVES_USER_ID=your-uid-here
```

```{note}
To obtain your UID, use the `nexuslims config labarchives-get-uid` command, or use
the button on the LabArchives page of the `nexuslims config edit` application. You will need to sign in
manually via the LabArchives web interface and generate a fresh **Password Token for
External Applications** (valid for 1 hour only), which will be exchanged for your
stable UID. This only has to be done once, as the
returned `uid` value is stable and does not change over time.
```

(config-labarchives-notebook-id)=
#### `NX_LABARCHIVES_NOTEBOOK_ID`

```{config-detail} NX_LABARCHIVES_NOTEBOOK_ID
```

**Example:**
```bash
NX_LABARCHIVES_NOTEBOOK_ID=12345  # optional
```

```{tip}
When LabArchives export is enabled, the following structure is created automatically:
- **Notebook:** The notebook specified by `NX_LABARCHIVES_NOTEBOOK_ID` (or Inbox if unset)
- **With a notebook ID:** Folder hierarchy `NexusLIMS Records/{instrument_pid}/` and a new `{YYYY-MM-DD} — {session_id}` page
- **Without a notebook ID:** Entries are added to the user’s Inbox
- **Entry:** HTML session summary with optional CDCS cross-link
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
NX_NEMO_STRFTIME_FMT_1="%Y-%m-%d %H:%M:%S"
```

(config-nemo-strptime-fmt)=
#### `NX_NEMO_STRPTIME_FMT_N`

```{config-detail} nemo.strptime_fmt
```

**Example:**
```bash
NX_NEMO_STRPTIME_FMT_1="%Y-%m-%d %H:%M:%S"
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

The pytest suite enables `NX_TEST_MODE`, which prevents automatic reads from user and system configuration files. Tests use environment variables and fixtures instead. The suite selects a temporary configuration path per test; commands that explicitly read or write a file still use the path given to them.

In tests, use `refresh_settings()` after modifying environment variables:

```python
from nexusLIMS.config import settings, refresh_settings

def test_with_custom_config(monkeypatch):
    # Set the value for this test; pytest restores it afterward
    monkeypatch.setenv("NX_FILE_STRATEGY", "inclusive")

    # Refresh to pick up changes
    refresh_settings()

    # Now settings reflects the new value
    assert settings.NX_FILE_STRATEGY == "inclusive"
```

## Configuration Validation

Core settings are loaded and validated when first accessed. Invalid core settings raise a `ValidationError`; NEMO and email settings are assembled and validated separately when requested.

Common validation errors:
- **Missing required fields**: Set all required environment variables
- **Invalid paths**: Ensure directories/files exist and are accessible
- **Invalid URLs**: Check URL format and trailing slashes
- **Invalid types**: Check value types (numbers, booleans, etc.)

## Example Configurations

These examples use dotenv syntax, not shell commands or TOML. To use them as a file, save them to a dotenv file and select it with an absolute `NX_CONFIG_FILE` path; NexusLIMS does not automatically read a working-directory `.env`.

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
# NX_DISABLE_SSL_VERIFY=true
```

## Troubleshooting

### Configuration Not Loading

If configuration changes aren't taking effect:

1. **Check the selected file**: Inspect `NX_CONFIG_FILE` or use the default path shown above
2. **Check environment variables**: process environment variables take precedence over the selected file
3. **Restart application**: Settings are cached after first access
4. **Check for typos**: Use the exact variable names and section keys shown in this guide

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
