# Command-Line Interface Reference

NexusLIMS provides command-line tools for record processing and configuration management.

## nexuslims-process-records

The main record processing command that searches for completed sessions, builds XML records,
and uploads them to configured export destinations.

### Basic Usage

```bash
nexuslims-process-records [OPTIONS]
```

Or using the Python module directly:

```bash
python -m nexusLIMS.cli.process_records [OPTIONS]
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
- `none` or `all` - Disable the lower bound and process all sessions regardless of start date

**Examples:**
```bash
# Process sessions from January 1, 2024 onward
nexuslims-process-records --from 2024-01-01

# Process sessions from a specific date to present
nexuslims-process-records --from 2024-06-15

# Process all sessions regardless of date (disable default 1-week filter)
nexuslims-process-records --from none
```

**Note:** Times are interpreted in the instrument's timezone as configured in the database.
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

**Note:** Times are interpreted in the instrument's timezone as configured in the database.
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
- `-v`: INFO level (normal operation details)
- `-vv`: DEBUG level (detailed debugging information)

**Examples:**
```bash
# Normal verbosity
nexuslims-process-records -v

# Maximum verbosity for debugging
nexuslims-process-records -vvv
```

#### `--version`

Display the NexusLIMS version and exit.

**Example:**
```bash
nexuslims-process-records --version
# Output: nexuslims-process-records version 2.7.0
```

#### `-h, --help`

Display help message with all available options and exit.

**Example:**
```bash
nexuslims-process-records --help
```

### Exit Codes

- **0**: Success (records processed or no sessions found)
- **1**: Error occurred during processing
- **2**: Another instance is already running (lock file exists)

### Logging

The command creates timestamped log files in the configured log directory
({ref}`NX_LOG_PATH <config-log-path>` or `{NX_DATA_PATH}/logs/`):

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

This is the typical usage when run via cron/systemd. By default, it processes sessions
from the **last week** with `TO_BE_BUILT` status and uploads completed records.

#### Process All Pending Sessions

To process all sessions regardless of date:

```bash
nexuslims-process-records --from none -v
```

This disables the default 1-week filter and processes all sessions with `TO_BE_BUILT` status.

#### Reprocess a Specific Date Range

If you need to reprocess sessions from a specific time period (e.g., after fixing a bug
or updating metadata extractors):

```bash
# First, manually update the database to reset session status
sqlite3 /path/to/nexuslims.db
> UPDATE session_log SET record_status = 'TO_BE_BUILT'
  WHERE timestamp >= '2024-01-01' AND timestamp <= '2024-01-31';
> .quit

# Then process with date filters
nexuslims-process-records --from 2024-01-01 --to 2024-01-31 -v
```

#### Preview Weekly Processing

Check what would be processed for a specific week without making changes:

```bash
nexuslims-process-records -n --from 2024-02-05 --to 2024-02-11 -vv
```

This dry-run with verbose output shows:
- Which sessions match the date criteria
- What files would be included
- Whether reservations are found
- Any errors that would occur

#### Automated Scheduled Execution

Typical cron configuration for hourly processing:

```bash
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
running, the command exits with code 2 and logs an error.

**Lock file location:** `{NX_DATA_PATH}/.builder.lock`

**Force unlock (if process crashed):**
```bash
rm /path/to/nexuslims/data/.builder.lock
```

### Email Notifications

If email is configured (see {doc}`configuration guide <configuration>`), error notifications
are sent when:
- Record building fails (session marked ERROR)
- Uploads fail
- Unexpected exceptions occur

See the {doc}`configuration guide <configuration>` Email Notifications section for setup details.

---

## nexuslims-config

Configuration management utility for viewing and exporting NexusLIMS configuration.

See the {py:mod}`nexusLIMS.cli.config` module documentation for details.

### Basic Usage

```bash
# View current configuration
nexuslims-config

# Dump configuration to YAML file
nexuslims-config dump

# Load configuration from YAML file
nexuslims-config load config.yaml
```

**Note:** This tool provides read-only configuration inspection and import/export.
It does not modify the underlying `.env` file or environment variables.
