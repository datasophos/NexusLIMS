# NexusLIMS Database

## Overview

NexusLIMS uses a [SQLite](https://sqlite.org/index.html) database to track experimental sessions and instrument configuration. The database file location is specified by {ref}`NX_DB_PATH <config-db-path>`.

**Key features:**
- Single-file database for easy backup (just copy the file)
- Created from [SQL Schema Definition](https://github.com/datasophos/NexusLIMS/blob/main/nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql)
- Inspectable with database tools such as [DB Browser for SQLite](https://sqlitebrowser.org/)

## SQLModel ORM Migration

```{versionadded} 2.2.0
NexusLIMS now uses [SQLModel](https://sqlmodel.tiangolo.com/) for database operations instead of raw SQL queries. This provides type safety, automatic datetime handling, and cleaner code.
```

### Notable Changes

- The `db_query()` function for manual database queries has been completely removed from {py:mod}`nexusLIMS.db.session_handler`
- `EventType` and `RecordStatus` are now enums ({py:class}`~nexusLIMS.db.enums.EventType`, {py:class}`~nexusLIMS.db.enums.RecordStatus`) instead of string literals
- {py:class}`~nexusLIMS.db.models.SessionLog` and {py:class}`~nexusLIMS.db.models.Instrument` are now SQLModel classes with real object-relational mapping
- The `Instrument` dataclass has been replaced with a SQLModel class - use `instrument_pid` field instead of `name`

### Migration Examples

**Creating session log entries:**

```python
# New approach: has not changed significantly other than using enums
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.enums import EventType, RecordStatus
from datetime import datetime as dt

log = SessionLog(
    session_identifier="abc",
    instrument="FEI-Titan-TEM",
    timestamp=dt.fromisoformat("2025-01-15T10:00:00"),
    event_type=EventType.START,
    record_status=RecordStatus.TO_BE_BUILT,
    user="alice"
)
log.insert_log()
```

**Querying the database:**

```python
# Old approach (deprecated)
_, results = db_query("SELECT * FROM session_log WHERE record_status = ?", ("TO_BE_BUILT",))

# New approach
from sqlmodel import Session, select
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.enums import RecordStatus

with Session(get_engine()) as session:
    results = session.exec(
        select(SessionLog).where(SessionLog.record_status == RecordStatus.TO_BE_BUILT)
    ).all()
```

**Benefits of SQLModel:**
- Type-safe database operations with IDE autocomplete and type checking
- Automatic datetime serialization/deserialization
- Relationship navigation (e.g., `session_log.instrument_obj`)
- ~50% less boilerplate code
- Foundation for Alembic migrations (database schema version control)

## Database Migrations with Alembic

```{versionadded} 2.2.0
NexusLIMS now uses [Alembic](https://alembic.sqlalchemy.org/) for database schema version control and migrations.
```

Alembic provides a way to track and manage changes to the database schema over time, making it safe to upgrade existing installations and ensuring schema consistency across deployments.

### For Existing Installations

If you have an existing NexusLIMS database (created before version 2.2.0), you need to mark it as migrated to the baseline schema:

```bash
# Mark existing database as migrated to current schema
nexuslims-migrate alembic stamp head
```

This tells Alembic that your database already has the current schema structure and doesn't need the baseline migration applied.

```{versionadded} 2.5.0
The `nexuslims-migrate` command provides simple, user-friendly commands for
common database operations. It automatically locates the migrations directory
inside the installed package, making migrations work correctly after pip/uv
installation. Advanced users can access the full Alembic CLI via
`nexuslims-migrate alembic [COMMAND]`. The `uv run alembic` command still works
for development from source checkouts.
```

### Common Migration Commands

```bash
# Check current migration status
nexuslims-migrate current

# Check if database has pending migrations
nexuslims-migrate check

# View migration history
nexuslims-migrate history

# Upgrade to latest schema version
nexuslims-migrate upgrade

# Upgrade to specific revision
nexuslims-migrate upgrade abc123

# Downgrade one migration
nexuslims-migrate downgrade

# Generate a new migration (development only, requires source checkout)
nexuslims-migrate alembic revision --autogenerate -m "Description"
```

For advanced Alembic operations, use `nexuslims-migrate alembic [COMMAND]` to access all Alembic sub-commands. From a source checkout, you can also use `uv run alembic` directly.

### Creating New Migrations

When you modify the database schema (by changing {py:class}`~nexusLIMS.db.models.SessionLog` or {py:class}`~nexusLIMS.db.models.Instrument`), you should create a migration:

1. **Modify the SQLModel classes** in `nexusLIMS/db/models.py`
2. **Generate migration script** (requires source checkout):
   ```bash
   nexuslims-migrate alembic revision --autogenerate -m "Add new field to SessionLog"
   ```

   The migration will be created with a user-friendly sequential ID:
   ```
   nexusLIMS/migrations/versions/004_add_new_field_to_sessionlog.py
   ```

   Instead of random hex like `a1b2c3d4e5f6_add_new_field_to_sessionlog.py`

3. **Review the generated script** in `nexusLIMS/migrations/versions/`
4. **Test the migration**:
   ```bash
   # Apply migration
   nexuslims-migrate upgrade

   # Test downgrade
   nexuslims-migrate downgrade

   # Re-apply
   nexuslims-migrate upgrade
   ```
5. **Commit the migration script** to version control

```{note}
**Revision ID Format**

NexusLIMS uses sequential, descriptive revision IDs instead of random hex values:
- **Format**: `NNN_description` (e.g., `001_initial_schema`, `002_add_upload_log`)
- **Benefits**: Clear ordering, easy to understand, sortable by name
- **Automatic**: The message you provide in `-m "..."` is automatically sanitized and used
- **Existing migrations**: Old hex-based migrations (from before 2.5.0) continue to work normally
```

### Migration Configuration

Alembic configuration is stored in:
- `pyproject.toml` under `[tool.alembic]` - Source code configuration (migration paths, etc.)
- `nexusLIMS/migrations/env.py` - Migration environment setup (automatically reads {ref}`NX_DB_PATH <config-db-path>`)
- `nexusLIMS/migrations/versions/` - Migration scripts directory (shipped in the package)

The database URL is automatically set from the {ref}`NX_DB_PATH <config-db-path>` environment variable in `env.py`, so you don't need to configure it separately. All Alembic configuration lives in `pyproject.toml`, eliminating the need for a separate `alembic.ini` file.

The `nexuslims-migrate` CLI command automatically locates the migrations directory using `importlib.resources`, so migrations work correctly whether NexusLIMS is installed via pip, uv, or run from source.

### Important Notes

- **Always backup your database** before running migrations on production data
- **Test migrations thoroughly** in a development environment first
- **Never edit applied migrations** - create a new migration to fix issues
- The initial migration (`57f0798d0c6d_initial_schema_baseline.py`) is a no-op baseline for existing installations

## Database Structure

The database contains two primary tables:

1. **`session_log`** - Tracks experimental sessions and record building status
   - Records when users start/end experiments
   - Tracks record building attempts and completion
   - Populated by harvesters (e.g., {py:mod}`~nexusLIMS.harvesters.nemo`)

2. **`instruments`** - Stores authoritative instrument configuration
   - Instrument names and PIDs
   - Reservation system URLs
   - Data storage paths
   - Harvester configuration


## The `session_log` Table

### Purpose

The `session_log` table tracks experimental sessions from start to finish. Harvesters (like {py:mod}`~nexusLIMS.harvesters.nemo`) populate this table by parsing reservation system APIs and creating timestamped event logs.

### How It Works

1. **Session Events** - Each row represents a timestamped event:
   - `START` - User begins experiment
   - `END` - User completes experiment
   - `RECORD_GENERATION` - Record building attempted

2. **Session Linking** - Events are linked by `session_identifier` to represent a complete experimental session

3. **Record Building Workflow**:
   - Harvester creates `START` and `END` events with status `TO_BE_BUILT`
   - Back-end polls for sessions with `TO_BE_BUILT` status
   - Record builder finds files created between start/end timestamps
   - Status updated to `COMPLETED` or `ERROR` to prevent duplicates
   - See {doc}`record building <../user_guide/record_building>` for details

### Table Schema

The following columns define the `session_log` table structure:

| Column | Data type | Description |
|--------|-----------|-------------|
| `id_session_log` | INTEGER | The auto-incrementing primary key identifier for this table (just a generic number).<br><br>*Checks:* must not be `NULL` |
| `session_identifier` | VARCHAR(36) | A unique string (could be a UUID) that is consistent among a single record's `"START"`, `"END"`, and `"RECORD_GENERATION"` events.<br><br>*Checks:* must not be `NULL` |
| `instrument` | VARCHAR(100) | The instrument PID associated with this session (this value is a foreign key reference to the `instruments` table).<br><br>*Checks:* value must be one of those from the `instrument_pid` column of the [`instruments`](instr-table) table. |
| `timestamp` | DATETIME | The date and time of the logged event in ISO timestamp format.<br><br>*Default:* `strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')`<br><br>*Checks:* must not be `NULL` |
| `event_type` | TEXT | The type of log for this session.<br><br>*Checks:* must be one of `"START"`, `"END"`, or `"RECORD_GENERATION"`. |
| `record_status` | TEXT | The status of the record associated with this session. This value will be updated after a record is built for a given session.<br><br>*Default:* `"WAITING_FOR_END"`<br><br>*Checks:* must be one of:<br>• `"WAITING_FOR_END"` - session has a start event, but no end event<br>• `"TO_BE_BUILT"` - session has ended, but record not yet built<br>• `"COMPLETED"` - record has been built successfully<br>• `"ERROR"` - some error happened during record generation<br>• `"NO_FILES_FOUND"` - record generation occurred, but no files matched time span<br>• `"NO_CONSENT"` - user did not consent to data harvesting<br>• `"NO_RESERVATION"` - no matching reservation found for this session |
| `user` | VARCHAR(50) | A username associated with this session (if known) -- this value is not currently used by the back-end since it is not reliable across different instruments. |

(instr-table)=
## The `instruments` Table

This table serves as the authoritative data source for the NexusLIMS back-end
regarding information about the instruments in the Nexus Facility. By locating
this information in an external database, changes to instrument configuration
(or addition of a new instrument) requires making adjustments to just one
location, simplifying maintenance of the system.

**Back-end implementation details**

When the {py:mod}`nexusLIMS` module is imported, one of the "setup" tasks
performed is to perform a basic object-relational mapping between rows of
the `instruments` table from the database into
{py:class}`~nexusLIMS.db.models.Instrument` objects. These objects are
stored in a dictionary attribute named {py:data}`nexusLIMS.instruments.instrument_db`.
This is done by querying the database specified in the environment variable
{ref}`NX_DB_PATH <config-db-path>` and creating a dictionary of
{py:class}`~nexusLIMS.db.models.Instrument` objects that contain information
about all of the instruments specified in the database. These objects are used
widely throughout the code so that the database is only queried once at initial
import, rather than every time information is needed.

| Column | Data type | Description |
|--------|-----------|-------------|
| `instrument_pid` | VARCHAR(100) | The unique identifier for an instrument in the facility, typically built from the make, model, and type of instrument, plus a unique numeric code (e.g. `Vendor-Model-Type-12345` ) |
| `api_url` | TEXT | The calendar API endpoint url for this instrument's scheduler. For NEMO, should be of the format `https://<nemo_address>/api/tools/?id=<tool_id>` |
| `calendar_name` | TEXT | The "user-friendly" name of the calendar for this instrument as displayed on the reservation system resource (e.g. "FEI Titan TEM") |
| `calendar_url` | TEXT | **[Deprecated]** The URL to this instrument's web-accessible calendar on the SharePoint resource (this is no longer used after SharePoint support was removed) |
| `location` | VARCHAR(100) | The physical location of this instrument |
| `schema_name` | TEXT | The human-readable name of instrument as defined in the Nexus Microscopy schema and displayed in the records |
| `property_tag` | VARCHAR(20) | A unique numeric identifier for this instrument (not used by NexusLIMS, but for reference and potential future use) |
| `filestore_path` | TEXT | The path (relative to central storage location specified in {ref}`NX_INSTRUMENT_DATA_PATH <config-instrument-data-path>`) where this instrument stores its data (e.g. `./instrument_name`) |
| `computer_name` | TEXT | The hostname of the `support PC` connected to this instrument (for reference purposes) |
| `computer_ip` | VARCHAR(15) | The IP address of the `support PC` connected to this instrument (not currently utilized) |
| `computer_mount` | TEXT | The full path where the central file storage is mounted and files are saved on the 'support PC' for the instrument (for reference purposes) |
| `harvester` | TEXT | The specific submodule within {py:mod}`nexusLIMS.harvesters` that should be used to harvest reservation information for this instrument. Possible values: `nemo`. |
| `timezone` | TEXT | The timezone in which this instrument is located, in the format of the IANA timezone database (e.g. `America/New_York`). This is used to properly localize dates and times when communicating with the harvester APIs. |
