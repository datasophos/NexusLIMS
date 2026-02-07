# Command-Line Interface Reference

NexusLIMS provides command-line tools for record processing and configuration management. In all the examples below, if you are running
NexusLIMS from a `git`-cloned version of the repository, ensure you
add `uv run` before every command.

## `nexuslims-process-records`

The main record processing command that searches for completed sessions, builds XML records,
and uploads them to configured export destinations.

### Basic Usage

```bash
nexuslims-process-records [OPTIONS]
```

### Options

#### `-n, --dry-run`

Run in dry-run mode to preview which sessions would be processed without actually building
or uploading records.

When enabled:
- Sessions are identified and logged
- No XML records are generated
- No uploads are performed
- Database is not modified

**Example:**
```bash
nexuslims-process-records --dry-run
```

#### `--from DATE`

Filter sessions to only process those that **started on or after** the specified date.

**Default:** If not specified, defaults to **1 week ago** from the current date/time.

**Date format:** `YYYY-MM-DD` (ISO 8601 date format)

**Special values:**
- `none` - Disable the lower bound and process all sessions regardless of start date

**Examples:**
```bash
# Process sessions from January 1, 2024 onward
nexuslims-process-records --from 2024-01-01

# Process sessions from a specific date to present
nexuslims-process-records --from 2024-06-15

# Process all sessions regardless of date (disable default 1-week filter)
nexuslims-process-records --from none
```

**Note:** Times are interpreted in the system timezone (where `nexuslims-process-records` is running).
The start of day (00:00:00) is used for the from date.

#### `--to DATE`

Filter sessions to only process those that **ended on or before** the specified date.

**Date format:** `YYYY-MM-DD` (ISO 8601 date format)

**Examples:**
```bash
# Process sessions up to and including December 31, 2023
nexuslims-process-records --to 2023-12-31

# Process sessions from the past up to a specific date
nexuslims-process-records --to 2024-01-15
```

**Note:** Times are interpreted in the system timezone (where `nexuslims-process-records` is running).
The end of day (23:59:59) is used for the to date to include all sessions that ended on
that day.

#### Combining `--from` and `--to`

Use both options together to process sessions within a specific date range.

**Examples:**
```bash
# Process sessions from January 2024 only
nexuslims-process-records --from 2024-01-01 --to 2024-01-31

# Process sessions from a specific week
nexuslims-process-records --from 2024-02-05 --to 2024-02-11

# Dry-run for a specific month
nexuslims-process-records -n --from 2024-03-01 --to 2024-03-31
```

**Date range interpretation:**
- Sessions are included if their **start time** is >= `--from` date at 00:00:00
- Sessions are included if their **end time** is <= `--to` date at 23:59:59
- Both bounds are inclusive

#### `-v, --verbose`

Increase logging verbosity. Can be specified multiple times for more detail.

**Verbosity levels:**
- No `-v`: WARNING level (default)
- `-v`: INFO level (normal operation details, prints configuration)
- `-vv`: DEBUG level (detailed debugging information, prints configuration)

**Note:** When `-v` or `-vv` is specified, a sanitized version of the
current configuration settings are printed at startup for transparency
and debugging.

**Examples:**
```bash
# Normal verbosity
nexuslims-process-records -v

# Maximum verbosity for debugging
nexuslims-process-records -vv
```

#### `--version`

Display the NexusLIMS version and exit.

**Example:**
```bash
nexuslims-process-records --version
# Output: nexuslims-process-records (NexusLIMS 2.4.1, released 2025-02-06)
```

#### `--help`

Display help message with all available options and exit.

**Example:**
```bash
nexuslims-process-records --help
```

### Exit Codes

- **0**: Success (records processed, no sessions found, or another instance is already running)
- **1**: Error occurred during processing (e.g., file logging setup failure)

### Logging

The command creates timestamped log files in the configured log directory
({ref}`NX_LOG_PATH <config-log-path>` or `{NX_DATA_PATH}/logs/` by default
if that config variable is not set):

```text
logs/
└── YYYY/
    └── MM/
        └── DD/
            └── process_records_HH-MM-SS.log
```

Logs include:
- Session discovery and filtering details
- Metadata extraction progress
- Upload results
- Error messages and tracebacks

### Examples

#### Process Recent Sessions (Default Behavior)

```bash
nexuslims-process-records -v
```

This is the typical usage when run via `cron`/`systemd`. By default, 
it processes pulls usage events from NEMO in the **last week** with,
and then builds records for any with `TO_BE_BUILT` status and
uploads completed records.

#### Process All Pending Sessions

To process all sessions regardless of date:

```bash
nexuslims-process-records --from none -v
```

This disables the default 1-week filter and fetches all usage events
from the NEMO API. Note, this may cause excessive runtimes for the
record builder.

#### Preview Weekly Processing

Check what would be processed for a specific week without making changes:

```text
nexuslims-process-records -n --from 2024-02-05 --to 2024-02-11 -vv
```

This dry-run with verbose output shows:

- Which sessions match the date criteria
- What files would be included
- Whether reservations are found
- Any errors that would occur

#### Automated Scheduled Execution

Typical cron configuration for hourly processing:

```text
# Process new microscopy records every hour
0 * * * * /path/to/nexuslims-process-records -v >> /var/log/nexuslims-cron.log 2>&1
```

Or systemd timer (recommended):

```ini
# /etc/systemd/system/nexuslims-process-records.timer
[Unit]
Description=NexusLIMS record processing timer

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/nexuslims-process-records.service
[Unit]
Description=NexusLIMS record processing

[Service]
Type=oneshot
ExecStart=/path/to/nexuslims-process-records -v
User=nexuslims
Group=nexuslims
```

### File Locking

The command uses file locking to prevent concurrent execution. If another instance is
running, the command exits with code 0 and skips that run.

**Lock file location:** `{NX_DATA_PATH}/.builder.lock`

**Force unlock (if process crashed):**
```bash
rm /path/to/nexuslims/data/.builder.lock
```

### Email Notifications

If email is configured (see {doc}`configuration guide <configuration>`), 
error notifications are sent when:

- Record building fails (session marked ERROR)
- Uploads fail
- Unexpected exceptions occur

See the {doc}`configuration guide <configuration>` Email Notifications section for setup details.

---

## `nexuslims-config`

Configuration management utility for viewing and exporting NexusLIMS configuration.

See the {py:mod}`nexusLIMS.cli.config` module documentation for details.

### Basic Usage

```bash
# View current configuration (prints to stdout)
nexuslims-config dump

# Save configuration to a JSON file
nexuslims-config dump --output nexuslims_config.json

# Load configuration from JSON file (if .env already exists,
# this command will detect it and create a backup of the current file)
nexuslims-config load nexuslims_config.json
```

**Note:** The `dump` command prints to stdout by default. Use `--output` to write to a file instead.

Example output of the dump command:

```json
{
  "NX_FILE_STRATEGY": "exclusive",
  "NX_IGNORE_PATTERNS": [
    "*.mib",
    "*.db",
    "*.emi"
  ],
  "NX_INSTRUMENT_DATA_PATH": "/tmp/nexuslims-test-instrument-data",
  "NX_DATA_PATH": "/tmp/nexuslims-test-data",
  "NX_DB_PATH": "/tmp/nexuslims-test-data/integration_test.db",
  "NX_CDCS_TOKEN": "nexuslims-dev-token-not-for-production",
  "NX_CDCS_URL": "http://cdcs.localhost:40080/",
  "NX_EXPORT_STRATEGY": "all",
  "NX_CERT_BUNDLE_FILE": null,
  "NX_CERT_BUNDLE": null,
  "NX_DISABLE_SSL_VERIFY": false,
  "NX_FILE_DELAY_DAYS": 2.0,
  "NX_CLUSTERING_SENSITIVITY": 1.0,
  "NX_LOG_PATH": null,
  "NX_RECORDS_PATH": null,
  "NX_LOCAL_PROFILES_PATH": null,
  "NX_ELABFTW_API_KEY": "1-aaaaaaaaaaaaaaaaaaaa",
  "NX_ELABFTW_URL": "https://elabftw.example.com/",
  "NX_ELABFTW_EXPERIMENT_CATEGORY": null,
  "NX_ELABFTW_EXPERIMENT_STATUS": null,
  "nemo_harvesters": {
    "1": {
      "address": "http://nemo.localhost:40080/api/",
      "token": "test-api-token_captain",
      "strftime_fmt": "%Y-%m-%dT%H:%M:%S%z",
      "strptime_fmt": "%Y-%m-%dT%H:%M:%S%z",
      "tz": null
    }
  },
  "email_config": {
    "smtp_host": "smtp.example.com",
    "smtp_port": 25,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "use_tls": false,
    "sender": "nexuslims@yourdomain.com",
    "recipients": [
      "admin@yourdomain.com",
      "team@yourdomain.com"
    ]
  }
}
```
