# NexusLIMS Database

## Overview

NexusLIMS uses a [SQLite](https://sqlite.org/index.html) database to track experimental sessions and instrument configuration. The database file location is specified by {ref}`NX_DB_PATH <config-db-path>`.

**Key features:**
- Single-file database for easy backup (just copy the file)
- Created from [SQLModel ORM Definitions](https://github.com/datasophos/NexusLIMS/blob/main/nexusLIMS/db/models.py)
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
# Mark existing database as consistent with the baseline pre-2.0 schema
nexuslims-migrate alembic stamp v1_4_3
```

This tells Alembic that your database already has the baseline schema structure and doesn't need to be created from scratch.

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
nexuslims-migrate upgrade v2_5_0a

# Downgrade one migration
nexuslims-migrate downgrade

# Generate a new migration (development only, requires source checkout)
nexuslims-migrate alembic revision --autogenerate -m "Description"
```

For advanced Alembic operations, use `nexuslims-migrate alembic [COMMAND]` to access all Alembic sub-commands. From a source checkout, you can also use `uv run alembic` directly.

### Creating New Migrations

When you modify the database schema (by changing {py:class}`~nexusLIMS.db.models.SessionLog` or {py:class}`~nexusLIMS.db.models.Instrument`, etc.), you should create a migration:

1. **Modify the SQLModel classes** in `nexusLIMS/db/models.py` or add new enums in `nexusLIMS/db/enums.py`

2. **Determine the revision ID** following the naming convention:
   - **Format**: `v[MAJOR]_[MINOR]_[PATCH][letter]_d[escription]` (e.g., `v2_5_0a_add_external_user_identifiers`)
   - **Version number**: Match the target release version where this schema change will land
   - **Letter suffix**: Use sequential letters (`a`, `b`, `c`, ...) for multiple migrations within the same version
   - **Description**: Brief, snake_case description of the change

3. **Generate migration script** (requires source checkout):
   ```bash
   nexuslims-migrate alembic revision --autogenerate \
       -m "add external user identifiers" \
       --rev-id "v2_5_0a"
   ```

   The migration will be created at:
   ```
   nexusLIMS/db/migrations/versions/v2_5_0a_add_external_user_identifiers.py
   ```

   **Note**: The filename combines the revision ID with the sanitized message for readability

4. **Review and edit the generated script** in `nexusLIMS/db/migrations/versions/`:
   - Verify the `upgrade()` function creates the expected schema changes
   - Verify the `downgrade()` function properly reverses those changes
   - For CHECK constraints or enums, you should use **hardcoded values** in the migration (preserves historical accuracy, migration won't break if enum changes later)
   - Add docstring explaining the migration's purpose if needed

5. **Test the migration thoroughly**:
   ```bash
   # Apply migration
   nexuslims-migrate upgrade

   # Test downgrade
   nexuslims-migrate downgrade

   # Re-apply
   nexuslims-migrate upgrade head
   ```

6. **Add integration tests** in `tests/integration/test_migrations.py`:
   - Test that upgrade creates expected tables/columns
   - Test that downgrade removes them
   - Test offline mode if migration has conditional logic

7. **Create changelog fragment** in `docs/changes/`:
   ```bash
   # Format: {issue_number}.{change_type}.md
   # Change types: feature, bugfix, doc, removal, misc
   docs/changes/48.feature.md
   ```

8. **Commit the migration script and tests** to version control

```{note}
**Revision ID Format**

NexusLIMS uses version-based revision IDs with letter suffixes:
- **Format**: `vMAJOR_MINOR_PATCHletter` (e.g., `v2_5_0a`, `v2_5_0b`, `v2_4_0a`)
- **Benefits**: Clear association with release versions, sequential ordering within a version
- **Multiple migrations per version**: Use sequential letters (`a`, `b`, `c`, ...)
- **Manual specification**: Use `--rev-id` flag when generating migrations
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
- The initial migration (`v1_4_3_initial_schema_baseline.py`) creates the basic database structure that serves as a basis for later migrations

## Database Structure

```{figure} ../_static/db_schema.png
:alt: NexusLIMS Database Schema Diagram
:align: center
:width: 100%

NexusLIMS Database Schema (auto-generated from SQLModel metadata)
```

```{note}
This diagram is automatically regenerated when you build the documentation, ensuring it always reflects the current database schema. Field descriptions are extracted from the SQLModel class docstrings.
```

For an interactive Mermaid diagram with detailed field descriptions and relationship documentation, see the [Database Schema Diagram](db_schema_diagram.md) (also auto-generated).

The database contains four primary tables:

1. **`session_log`** - Tracks experimental sessions and record building status
   - Records when users start/end experiments
   - Tracks record building attempts and completion
   - Populated by harvesters (e.g., {py:mod}`~nexusLIMS.harvesters.nemo`)

2. **`instruments`** - Stores authoritative instrument configuration
   - Instrument names and PIDs
   - Reservation system URLs
   - Data storage paths
   - Harvester configuration

3. **`upload_log`** - Tracks record uploads to CDCS and other export destinations
   - Session identifier and instrument linkage
   - CDCS record ID and PID
   - Upload timestamps and success status
   - Error tracking for failed uploads

4. **`external_user_identifiers`** - Maps NexusLIMS usernames to external system IDs
   - Star-topology design with `nexuslims_username` as canonical identifier
   - Supports NEMO, LabArchives ELN, LabArchives Scheduler, CDCS
   - Bidirectional lookup between internal and external identities
   - Tracks creation and verification timestamps


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

## The `upload_log` Table

```{versionadded} 2.4.0
The upload_log table was added to track record exports to external repositories.
```

### Purpose

The `upload_log` table tracks export attempts to destination repositories like CDCS and LabArchives. It enables multi-destination export with granular success/failure tracking per destination and session.

### How It Works

1. **Per-Destination Tracking** - Each export attempt creates a new row, allowing one session to be exported to multiple destinations
2. **Success/Failure Recording** - Stores whether export succeeded and captures error messages if it failed
3. **Record Linkage** - Stores destination-specific record IDs and URLs for successful exports
4. **Retry Logic** - Failed exports can be identified and retried based on `success` status

### Table Schema

| Column | Data type | Description |
|--------|-----------|-------------|
| `id` | INTEGER | The auto-incrementing primary key identifier for this table.<br><br>*Checks:* must not be `NULL` |
| `session_identifier` | VARCHAR(36) | Foreign key reference to `session_log.session_identifier`.<br><br>*Checks:* must not be `NULL`<br>*Indexed:* for efficient session lookup |
| `destination_name` | VARCHAR(100) | Name of the export destination (e.g., `"cdcs"`, `"labarchives"`).<br><br>*Checks:* must not be `NULL`<br>*Indexed:* for destination-specific queries |
| `success` | BOOLEAN | Whether the export succeeded (`TRUE`) or failed (`FALSE`).<br><br>*Checks:* must not be `NULL` |
| `timestamp` | DATETIME | When the export attempt occurred (timezone-aware).<br><br>*Checks:* must not be `NULL` |
| `record_id` | VARCHAR(255) | Destination-specific record identifier (e.g., CDCS document ID).<br><br>*Optional:* `NULL` if export failed |
| `record_url` | VARCHAR(500) | Direct URL to view the exported record in the destination system.<br><br>*Optional:* `NULL` if export failed |
| `error_message` | TEXT | Error message if export failed.<br><br>*Optional:* `NULL` if export succeeded |
| `metadata_json` | TEXT | JSON-serialized dict with destination-specific metadata.<br><br>*Optional:* for storing additional export context |

## The `external_user_identifiers` Table

```{versionadded} 2.5.0
The external_user_identifiers table was added to map NexusLIMS usernames to external system IDs.
```

### Purpose

The `external_user_identifiers` table maintains mappings between NexusLIMS usernames and user identifiers in external systems (NEMO, LabArchives ELN, LabArchives Scheduler, CDCS). This enables bidirectional user identity lookup and supports integration with external APIs.

### How It Works

1. **Star Topology Design** - Uses `nexuslims_username` (from `session_log.user`) as the canonical identifier, with mappings to each external system
2. **Bidirectional Lookup** - Supports both forward lookup (NexusLIMS → external ID) and reverse lookup (external ID → NexusLIMS)
3. **Uniqueness Constraints**:
   - One external ID per system per NexusLIMS user
   - One NexusLIMS user per external ID per system
4. **Verification Tracking** - Records when mappings are created and last verified for auditing

### Helper Functions

The {py:mod}`nexusLIMS.db.models` module provides convenience functions:

- {py:func}`~nexusLIMS.db.models.get_external_id` - Get external ID for a NexusLIMS username
- {py:func}`~nexusLIMS.db.models.get_nexuslims_username` - Reverse lookup from external ID
- {py:func}`~nexusLIMS.db.models.store_external_id` - Store or update a mapping (upsert)
- {py:func}`~nexusLIMS.db.models.get_all_external_ids` - Get all external IDs for a username

### Table Schema

| Column | Data type | Description |
|--------|-----------|-------------|
| `id` | INTEGER | The auto-incrementing primary key identifier for this table.<br><br>*Checks:* must not be `NULL` |
| `nexuslims_username` | VARCHAR | Canonical username in NexusLIMS (from `session_log.user`).<br><br>*Checks:* must not be `NULL`<br>*Indexed:* for efficient lookup<br>*Unique Constraint:* with `external_system` |
| `external_system` | TEXT | External system identifier.<br><br>*Checks:* must be one of `"nemo"`, `"labarchives_eln"`, `"labarchives_scheduler"`, `"cdcs"`<br>*Unique Constraints:* with `nexuslims_username` and with `external_id` |
| `external_id` | TEXT | User ID/username in the external system.<br><br>*Checks:* must not be `NULL`<br>*Unique Constraint:* with `external_system` |
| `email` | VARCHAR | User's email for verification/matching purposes.<br><br>*Optional:* may be `NULL` |
| `created_at` | DATETIME | When this mapping was created (timezone-aware, UTC).<br><br>*Checks:* must not be `NULL`<br>*Default:* current UTC timestamp |
| `last_verified_at` | DATETIME | Last time this mapping was verified (timezone-aware, UTC).<br><br>*Optional:* `NULL` until first verification |
| `notes` | TEXT | Additional notes about this mapping (e.g., `"OAuth registration"`, `"From NEMO harvester"`).<br><br>*Optional:* may be `NULL` |
