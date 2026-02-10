# Command-Line Interface Reference

NexusLIMS provides command-line tools for record processing and configuration management. In all the examples below, if you are running
NexusLIMS from a `git`-cloned version of the repository, ensure you
add `uv run` before every command.

Every command (and any subcommands) also support the `--help` flag that can be
used to get interactive assistance for any operation.

## `nexuslims-process-records`

The main record processing command that searches for completed sessions, builds
XML records, and uploads them to configured export destinations.

### Basic Usage

```bash
nexuslims-process-records --help
```

```text
Usage: nexuslims-process-records [OPTIONS]

  Process new NexusLIMS records with logging and email notifications.

  This command runs the NexusLIMS record builder to process new experimental
  sessions and generate XML records. It provides file locking to prevent
  concurrent runs, timestamped logging, and email notifications on errors.

  By default, only sessions from the last week are processed. Use --from=none
  to process all sessions, or specify custom date ranges with --from and --to.

Options:
  -n, --dry-run  Dry run: find files without building records
  -v, --verbose  Increase verbosity (-v for INFO, -vv for DEBUG)
  --from TEXT    Start date for session filtering (ISO format: YYYY-MM-DD).
                 Defaults to 1 week ago. Use "none" to disable lower bound.
  --to TEXT      End date for session filtering (ISO format: YYYY-MM-DD). Omit
                 to disable upper bound.
  --version      Show the version and exit.
  --help         Show this message and exit.

  Examples:

      # Normal run (process records from last week)
      $ nexuslims-process-records

      # Process all sessions (no date filtering)
      $ nexuslims-process-records --from=none

      # Process sessions since a specific date
      $ nexuslims-process-records --from=2025-01-01

      # Process a specific date range
      $ nexuslims-process-records --from=2025-01-01 --to=2025-01-31

      # Dry run (find files only)
      $ nexuslims-process-records -n

      # Verbose output
      $ nexuslims-process-records -vv
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
```text
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
```text
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
```text
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

## `nexuslims-manage-instruments`

Terminal user interface (TUI) for managing the NexusLIMS instruments database.

Provides an interactive interface for adding, editing, and deleting instruments without
manual SQL manipulation. Features include sortable tables, real-time validation, search/filter,
theme switching, and automatic database initialization.

### Basic Usage

```bash
nexuslims-manage-instruments --help
```

```text
Usage: nexuslims-manage-instruments [OPTIONS]

  Manage NexusLIMS instruments database.

  Launch an interactive terminal UI for adding, editing, and deleting
  instruments in the NexusLIMS database. Provides form validation,
  uniqueness checks, and confirmation prompts for destructive actions.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.
```

### Features

- **Interactive table**: Sortable instrument list with real-time filtering
- **Add instruments**: Form validation ensures data integrity
- **Edit instruments**: Modify existing instruments with pre-filled forms
- **Delete instruments**: Confirmation prompts prevent accidental deletion
- **Search/filter**: Find instruments by any field
- **Theme switching**: Toggle between dark and light modes
- **Auto-init**: Automatically creates database if it doesn't exist
- **Help screen**: Built-in keybinding reference

### Keybindings

See the {doc}`instrument_manager` guide for detailed keybindings and usage examples.

Quick reference:
- **a**: Add new instrument
- **e**: Edit selected instrument
- **d**: Delete selected instrument
- **/**: Focus search/filter input
- **Ctrl+T**: Toggle theme
- **?**: Show help
- **q**: Quit

### Examples

```bash
# Launch the instrument manager TUI
nexuslims-manage-instruments

# Show version
nexuslims-manage-instruments --version
```

For a complete guide with screenshots and demonstrations, see the {doc}`instrument_manager` user guide.

---

## `nexuslims-config`

Configuration management utility for viewing and exporting NexusLIMS configuration.

See the {py:mod}`nexusLIMS.cli.config` module documentation for details.

### Basic Usage

```bash
nexuslims-config --help
```

```text
Usage: nexuslims-config [OPTIONS] COMMAND [ARGS]...

  Manage NexusLIMS configuration files.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  dump  Dump the current effective configuration to JSON.
  load  Load a previously dumped JSON config into a .env file.
```

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

---

## `nexuslims-migrate`

```{versionadded} 2.5.0
```

`nexuslims-migrate` is the NexusLIMS database management tool. It
provides simple commands for common database operations while allowing
advanced access to [Alembic](https://alembic.sqlalchemy.org/) functionality
for developers.

The migration command will automatically read the value of `NX_DB_PATH`
set in your `.env` file and apply any changes required to that database.
Backups of your database file will be made automatically during the upgrade
process.

```{note}
This command is generally only needed when upgrading NexusLIMS to new versions,
or when initially setting up a deployment of NexusLIMS. The release notes
for each NexusLIMS version will indicate if a database upgrade is necessary.
If so, you will need to run `nexuslims-migrate upgrade` as part of the
version upgrade.
```

**Database version naming:** Database migration revision IDs track NexusLIMS
version numbers. For example, revision `v2_4_0b` corresponds to the database
schema required for NexusLIMS v2.4.0. This makes it easy to identify which
database version matches your installed NexusLIMS version.

### Basic Usage

```bash
nexuslims-migrate --help
```

```text
Usage: nexuslims-migrate [OPTIONS] COMMAND [ARGS]...

  Manage NexusLIMS database schema migrations.

  This tool provides simple commands for common database operations. For
  advanced usage, use 'nexuslims-migrate alembic [COMMAND]' to access the full
  Alembic CLI.

Options:
  --version  Show version and exit
  --help     Show this message and exit.

Commands:
  alembic    Run Alembic commands directly (advanced usage).
  check      Check if the database has pending migrations.
  current    Show the current database migration version.
  downgrade  Downgrade database to an earlier version.
  history    Show migration history.
  init       Initialize a new NexusLIMS database.
  upgrade    Upgrade database to a later version.
```

### Commands

#### `init`

Initialize a new NexusLIMS database with.

Creates the database file at `NX_DB_PATH`, applies all migrations to create the schema,
and marks it as current.

**Usage:**
```bash
nexuslims-migrate init [OPTIONS]
```

**Options:**
- `--force` - Overwrite existing database file if it exists (use with caution)

**Examples:**
```bash
# Create new database
nexuslims-migrate init

# Force recreate (destroys existing data)
nexuslims-migrate init --force
```

**Notes:**
- Database location is read from `NX_DB_PATH` environment variable
- Parent directories are created automatically if they don't exist
- Fails with clear error if database already exists (unless `--force` is used)

#### `upgrade`

Upgrade an existing NexusLIMS database to a later schema version.

**Usage:**
```bash
nexuslims-migrate upgrade [REVISION] [OPTIONS]
```

**Arguments:**
- `REVISION` - Target migration version (default: `head` for latest)
  - `head` - Upgrade to latest version
  - `+1` - Upgrade one version
  - `abc` - Upgrade to specific revision ID (e.g., `v2_4_0a`)

**Options:**
- `--sql` - Generate SQL script instead of applying changes

**Examples:**
```bash
# Upgrade to latest version
nexuslims-migrate upgrade

# Upgrade one version at a time
nexuslims-migrate upgrade +1

# Upgrade to specific revision
nexuslims-migrate upgrade v2_4_0a

# Generate SQL without applying
nexuslims-migrate upgrade --sql
```

#### `downgrade`

Downgrade NexusLIMS database to an earlier schema version.

**Usage:**
```bash
nexuslims-migrate downgrade [REVISION] [OPTIONS]
```

**Arguments:**
- `REVISION` - Target migration version (default: `-1` for one step back)
  - `-1` - Downgrade one version
  - `-2` - Downgrade two versions
  - `abc` - Downgrade to specific revision ID (e.g., `002`)

**Options:**
- `--sql` - Generate SQL script instead of applying changes

**Examples:**
```bash
# Downgrade one version
nexuslims-migrate downgrade

# Downgrade to specific revision
nexuslims-migrate downgrade v1_4_3

# Generate SQL without applying
nexuslims-migrate downgrade --sql
```

#### `current`

Show the current database migration version.

**Usage:**
```bash
nexuslims-migrate current [OPTIONS]
```

**Options:**
- `-v, --verbose` - Show detailed information

**Examples:**
```bash
# Show current version
nexuslims-migrate current

# output: 
#   v2_4_0b (head)

# Show detailed information
nexuslims-migrate current -v

# output:
#  Current revision(s) for sqlite:///test_db.sqlite:
#  Rev: v2_4_0b (head)
#  Parent: v2_4_0a
#  Path: nexusLIMS/db/migrations/versions/v2_4_0b_add_check_constraints.py
```

#### `check`

Check if the database has any pending migrations.

Useful for automated monitoring or pre-deployment checks.

**Usage:**
```bash
nexuslims-migrate check
```

**Exit Codes:**
- **0** - Database is up-to-date
- **1** - Database has pending migrations
- **2** - Error occurred

**Examples:**
```bash
# Check migration status
nexuslims-migrate check

# output:
#   ⚠ Database has pending migrations
#   Current revision: v1_4_3
#   Latest revision:  v2_4_0b
```

#### `history`

Show migration history.

**Usage:**
```bash
nexuslims-migrate history [OPTIONS]
```

**Options:**
- `-v, --verbose` - Show detailed information
- `-i, --indicate-current` - Indicate current revision (Alembic default)

**Examples:**
```bash
# Show migration history
nexuslims-migrate history

# output:
#   v2_4_0a -> v2_4_0b (head), Add check constraints to session_log.
#   v1_4_3 -> v2_4_0a, Add upload_log table and BUILT_NOT_EXPORTED status.
#   <base> -> v1_4_3, Initial schema baseline.

# Show verbose history with current revision marked
nexuslims-migrate history -v -i
```

#### `alembic`

Run Alembic commands directly (advanced usage).

Provides access to the full Alembic CLI for advanced operations not covered by the
simplified commands above.

**Usage:**
```bash
nexuslims-migrate alembic [ALEMBIC_COMMAND] [ALEMBIC_OPTIONS]
```

**Examples:**
```bash
# Show detailed migration history
nexuslims-migrate alembic history --verbose

# Create a new migration (development only, requires source checkout)
nexuslims-migrate alembic revision --autogenerate -m "Add column"

# Show specific revision details
nexuslims-migrate alembic show 003

# Stamp database without running migrations (use with caution)
nexuslims-migrate alembic stamp head
```

**Note:** The `alembic` subcommand passes arguments directly to Alembic's CLI. See the
[Alembic documentation](https://alembic.sqlalchemy.org/) for available commands.

### Global Options

#### `--version`

Display the NexusLIMS version and exit.

**Example:**
```bash
nexuslims-migrate --version
# Output: nexuslims-migrate (NexusLIMS 2.4.1)
```

### Common Workflows

#### Setting Up a New Installation

```bash
# 1. Set database path in .env
echo "NX_DB_PATH=/var/nexuslims/database.db" >> .env

# 2. Initialize database
nexuslims-migrate init

# 3. Verify database status
nexuslims-migrate current
```

#### Upgrading After NexusLIMS Update

```bash
# 1. Check for pending migrations
nexuslims-migrate check

# 2. If migrations are pending, review what will change
nexuslims-migrate history -v

# 3. Manually ackup database (recommended, though the upgrade command will also backup)
cp /path/to/database.db /path/to/database.db.backup

# 4. Apply migrations
nexuslims-migrate upgrade

# 5. Verify upgrade
nexuslims-migrate current
```

#### Migrating from v1.x or Early v2.x

If you have an existing database from before v2.2.0 (when Alembic was introduced),
mark it as migrated to the baseline schema:

```bash
# Mark existing database as at the v1.4.3 migration level
nexuslims-migrate alembic stamp v1_4_3
```

See the {ref}`migration` guide for complete migration instructions.

### Configuration

The `nexuslims-migrate` command automatically:

- Reads database path from {ref}`NX_DB_PATH <config-db-path>` environment variable
- Locates migrations directory inside the installed package (works with pip/uv installations)
- Creates temporary Alembic configuration as needed

No manual configuration is required.

### Notes

- **Always backup your database** before running migrations on production data
- **Test migrations** in a development environment first
- **Never edit applied migrations** - create a new migration to fix issues
- The sequential revision IDs aligned to NexusLIMS versions (v1_4_3, v2_4_0, etc.) make it easy to track migration order

For more details on the migration system, see the {doc}`database migration documentation <../dev_guide/database>`.
