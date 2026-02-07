# Remove SQL Creation Script and Move to Fully Automated ORM System

## Overview

Remove the manual database creation script (`nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql`) and migrate to a fully automated ORM-based system with intelligent Alembic migration support. All database schema definitions will be managed through SQLModel ORM classes, with schema creation and evolution handled entirely through Python code.

## Current State

**SQL Script Usage (3 locations):**
- `scripts/initialize_db.py:43-96` - Database initialization (calls `get_sql_script_path()`, reads and executes SQL script)
- `tests/unit/fixtures/database.py:31-44,96-97` - DatabaseFactory for test databases (takes `schema_path` parameter, executes SQL script)
- `nexusLIMS/db/dev/migrate_db.py` - Legacy migration script (deprecated, still references SQL script)

**Existing Infrastructure:**
- SQLModel ORM models: `Instrument`, `SessionLog`, `UploadLog` (in `nexusLIMS/db/models.py`)
- Alembic configured in `pyproject.toml` and `migrations/env.py`
- Three migrations exist:
  1. `57f0798d0c6d_initial_schema_baseline.py` - No-op baseline (assumes schema exists)
  2. `0ea2bc3d2ebe_add_upload_log_table_and_built_not_.py` - Added upload_log table
  3. `2e1408e573b1_add_check_constraints_to_session_log.py` - Added CHECK constraints

**SQLModel Already Working:**
- `tests/conftest.py:47` - `create_test_database()` uses `SQLModel.metadata.create_all()`
- Test infrastructure partially migrated to SQLModel approach

## Implementation Plan

### Phase 1: Create True Initial Migration

**Goal:** Replace the no-op baseline with a migration that actually creates the full schema from SQLModel definitions.

**Actions:**

1. **Generate initial migration using Alembic autogenerate**
   ```bash
   # Create temporary empty database for comparison
   uv run alembic revision --autogenerate -m "create initial schema from sqlmodel"
   ```

2. **Manually review and enhance the generated migration**
   - File location: `migrations/versions/XXXXXX_create_initial_schema_from_sqlmodel.py`
   - Ensure CHECK constraints match current implementation (from migration `2e1408e573b1`)
   - Verify indexes are created:
     - `session_log.fk_instrument_idx` on `session_log(instrument)`
     - `ix_session_log_session_identifier` on `session_log(session_identifier)`
     - `ix_upload_log_destination_name` on `upload_log(destination_name)`
     - `ix_upload_log_session_identifier` on `upload_log(session_identifier)`
   - Verify foreign key constraints and CASCADE behavior
   - Ensure AUTOINCREMENT is set for primary keys where needed
   - Add proper `PRAGMA foreign_keys = ON` handling if needed

3. **Set migration revision chain**
   - `down_revision = None` (true initial migration)
   - Keep existing `57f0798d0c6d` as-is for backward compatibility
   - Both migrations can coexist (parallel initial states)

4. **Test the migration**
   ```bash
   # Test upgrade on empty database
   uv run alembic upgrade head

   # Test downgrade
   uv run alembic downgrade base
   ```

**Expected Migration Structure:**
```python
def upgrade() -> None:
    # Create instruments table
    op.create_table(
        'instruments',
        sa.Column('instrument_pid', sa.String(length=100), nullable=False),
        sa.Column('api_url', sa.String(), nullable=False),
        sa.Column('calendar_name', sa.String(), nullable=False),
        # ... all columns
        sa.PrimaryKeyConstraint('instrument_pid'),
        sa.UniqueConstraint('api_url', name='api_url_UNIQUE'),
        sa.UniqueConstraint('computer_name', name='computer_name_UNIQUE'),
        sa.UniqueConstraint('computer_ip', name='computer_ip_UNIQUE'),
    )

    # Create session_log table with CHECK constraints
    op.create_table(
        'session_log',
        # ... columns
        sa.CheckConstraint(
            "event_type IN ('START', 'END', 'RECORD_GENERATION')",
            name='ck_session_log_event_type'
        ),
        sa.CheckConstraint(
            "record_status IN ('COMPLETED', 'WAITING_FOR_END', 'TO_BE_BUILT', "
            "'BUILT_NOT_EXPORTED', 'ERROR', 'NO_FILES_FOUND', 'NO_CONSENT', "
            "'NO_RESERVATION')",
            name='ck_session_log_record_status'
        ),
        sa.ForeignKeyConstraint(
            ['instrument'],
            ['instruments.instrument_pid'],
            name='fk_instrument',
            ondelete='CASCADE',
            onupdate='CASCADE'
        ),
    )

    # Create upload_log table
    # ...

    # Create indexes
    op.create_index('session_log.fk_instrument_idx', 'session_log', ['instrument'])
    # ...

def downgrade() -> None:
    op.drop_table('upload_log')
    op.drop_table('session_log')
    op.drop_table('instruments')
```

---

### Phase 2: Update initialize_db.py

**Goal:** Replace SQL script execution with SQLModel-based schema creation.

**File:** `scripts/initialize_db.py`

**Changes:**

1. **Remove SQL script dependency (lines 43-53)**
   - Delete `get_sql_script_path()` function entirely

2. **Replace `initialize_database()` function (lines 56-96)**

   **New implementation:**
   ```python
   def initialize_database(db_path: str, force: bool = False):
       """Initialize the SQLite database using SQLModel ORM definitions."""
       from sqlmodel import SQLModel, create_engine
       from nexusLIMS.db.models import Instrument, SessionLog, UploadLog
       import subprocess

       db_file = Path(db_path)

       if db_file.exists():
           if force:
               logger.warning("Overwriting existing database file at '%s'.", db_path)
               db_file.unlink()
           else:
               logger.error(
                   "Database file already exists at '%s'. "
                   "Use -f or --force to overwrite. Exiting to prevent data loss.",
                   db_path,
               )
               return None

       logger.info("Creating new database at '%s'...", db_path)

       try:
           # Create engine and tables using SQLModel
           engine = create_engine(f"sqlite:///{db_path}")
           SQLModel.metadata.create_all(engine)
           engine.dispose()

           logger.info("Database schema created successfully.")

           # Mark database as migrated to latest schema version
           logger.info("Marking database as migrated (alembic stamp head)...")
           result = subprocess.run(
               ["uv", "run", "alembic", "stamp", "head"],
               check=True,
               capture_output=True,
               text=True,
               env={**os.environ, "NX_DB_PATH": str(db_path)},
           )

           if result.returncode == 0:
               logger.info("Database marked as migrated successfully.")
           else:
               logger.warning(
                   "Failed to mark database as migrated. You may need to run "
                   "'alembic stamp head' manually."
               )

           # Return SQLite connection for instrument insertion
           import sqlite3
           conn = sqlite3.connect(db_path)
           return conn

       except Exception:
           logger.exception("Error initializing database")
           return None
   ```

3. **Update function signature and call site (line 346)**
   ```python
   # OLD:
   conn = initialize_database(db_abs_path, sql_script_path, args.force)

   # NEW:
   conn = initialize_database(str(db_abs_path), args.force)
   ```

4. **Remove variable assignment (line 344)**
   ```python
   # DELETE this line:
   sql_script_path = get_sql_script_path()
   ```

5. **Update module docstring (lines 3-32)**
   ```python
   """
   Initialize a NexusLIMS SQLite database.

   Creates the database schema using SQLModel ORM definitions and marks
   it as migrated using Alembic. Can optionally populate with default
   instrument data or allow interactive instrument entry.

   Usage:
       python initialize_db.py [db_path] [--defaults] [-f | --force]

   Arguments:
       db_path (str, optional): Path to the SQLite database file.
                                Defaults to 'nexuslims_db.sqlite'.

   Options:
       --defaults: Populate the database with default instrument data from
                   `test_instrument_factory.py`.
       -f, --force: Overwrite the existing database file if it exists.
                    Use with caution as this will result in data loss.

   Examples
   --------
       # Initialize a new database named 'nexuslims_db.sqlite' with default data
       python initialize_db.py nexuslims_db.sqlite --defaults

       # Initialize with interactive instrument entry, overwriting if exists
       python initialize_db.py -f

       # Initialize with default name and default data
       python initialize_db.py --defaults

   Notes
   -----
       The database is automatically marked as migrated using 'alembic stamp head'
       so future schema migrations can be applied with 'alembic upgrade head'.
   """
   ```

6. **Add import for os module** (needed for subprocess env)
   ```python
   import os  # Add to imports at top
   ```

---

### Phase 3: Update DatabaseFactory for Tests

**Goal:** Remove SQL script dependency from test infrastructure.

**File:** `tests/unit/fixtures/database.py`

**Changes:**

1. **Update `__init__` method (lines 31-44)**

   **Remove `schema_path` parameter:**
   ```python
   def __init__(self, temp_dir: Path):
       """
       Initialize the database factory.

       Parameters
       ----------
       temp_dir : Path
           Directory for creating test databases
       """
       self.temp_dir = temp_dir
       self._db_counter = 0
   ```

2. **Update `create_db` method (lines 93-98)**

   **Replace SQL script execution with SQLModel:**
   ```python
   db_path = self.temp_dir / name

   # Create database with SQLModel schema
   from sqlmodel import SQLModel, create_engine
   from nexusLIMS.db.models import Instrument, SessionLog, UploadLog

   engine = create_engine(f"sqlite:///{db_path}")
   SQLModel.metadata.create_all(engine)
   engine.dispose()

   # Get connection for data insertion
   conn = sqlite3.connect(db_path)
   ```

3. **Update class docstring (lines 15-29)**
   ```python
   """
   Factory for creating test databases on-demand.

   This factory uses SQLModel ORM definitions to create databases
   with only the instruments and sessions that tests actually need,
   dramatically reducing test setup overhead.

   Attributes
   ----------
   temp_dir : Path
       Directory where test databases will be created
   """
   ```

4. **Update method docstring (lines 76-86)**

   **Remove schema_path from example:**
   ```python
   Examples
   --------
   >>> factory = DatabaseFactory(tmp_path)
   >>> # Empty database
   >>> db_path = factory.create_db()
   >>> # Database with one instrument
   >>> db_path = factory.create_db(instruments=[{
   ...     "instrument_pid": "FEI-Titan-TEM",
   ...     "api_url": "https://nemo.example.com/api/tools/?id=2",
   ...     ...
   ... }])
   ```

5. **Find and update all DatabaseFactory instantiations**

   **Search command:**
   ```bash
   grep -r "DatabaseFactory(" tests/
   ```

   **Expected changes:**
   - Remove `schema_path` parameter from all instantiation calls
   - Update fixture definitions that provide schema_path

---

### Phase 4: Remove Legacy Migration Script

**Goal:** Remove the old migration script completely (user preference: immediate removal).

**Actions:**

1. **Delete file:** `nexusLIMS/db/dev/migrate_db.py`

2. **Search for references and update:**
   ```bash
   # Find any documentation or code references
   grep -r "migrate_db" docs/
   grep -r "migrate_db" .claude/
   ```

3. **Remove from documentation** (if referenced anywhere)

4. **Note in changelog** as a breaking change with migration instructions

---

### Phase 5: Update Documentation

#### File: `docs/dev_guide/database.md`

**Line 9 - Update database structure section:**

```markdown
## Database Structure

NexusLIMS uses a SQLite database with three main tables:

- **Schema Definition**: Defined by [SQLModel ORM models](https://github.com/datasophos/NexusLIMS/blob/main/nexusLIMS/db/models.py) (`Instrument`, `SessionLog`, `UploadLog`)
- **Schema Creation**: Automated via `SQLModel.metadata.create_all()` from model definitions
- **Schema Evolution**: Managed by [Alembic migrations](https://github.com/datasophos/NexusLIMS/tree/main/migrations/versions/)
- **Migration History**: Tracked in `alembic_version` table (automatically managed)

All database operations use type-safe ORM queries through SQLModel, ensuring data integrity and preventing SQL injection vulnerabilities.
```

**After line 148 - Add new section:**

```markdown
## Creating New Databases

### Using the Initialization Script (Recommended)

The recommended way to create a new NexusLIMS database is using the provided initialization script:

```bash
# Create database with interactive instrument entry
python scripts/initialize_db.py /path/to/nexuslims_db.sqlite

# Create with default test instruments (useful for development)
python scripts/initialize_db.py --defaults

# Force overwrite if file exists (CAUTION: destroys existing data)
python scripts/initialize_db.py -f
```

The initialization script automatically:
1. Creates the database file with full schema from SQLModel ORM definitions
2. Marks it as migrated using `alembic stamp head`
3. Optionally populates instrument data (default test instruments or interactive entry)

**No manual schema application needed** - the script handles everything.

---

### Manual Database Creation (Advanced)

If you need to create a database programmatically:

```python
from pathlib import Path
from sqlmodel import SQLModel, create_engine
import subprocess
import os

# Import all models to register with metadata
from nexusLIMS.db.models import Instrument, SessionLog, UploadLog

# Create database
db_path = Path("nexuslims_db.sqlite")
engine = create_engine(f"sqlite:///{db_path}")
SQLModel.metadata.create_all(engine)
engine.dispose()

# Mark as migrated (CRITICAL - don't skip this step)
subprocess.run(
    ["uv", "run", "alembic", "stamp", "head"],
    check=True,
    env={**os.environ, "NX_DB_PATH": str(db_path)},
)
```

**Important:** Always run `alembic stamp head` after manual creation. This marks the database as migrated to the current schema version, ensuring future migrations are tracked correctly.

---

### Test Databases

Test databases are created automatically using the same SQLModel approach:

```python
from tests.conftest import create_test_database

# Creates database with full schema (no migration tracking needed for tests)
create_test_database(Path("test.db"))
```

This is used by pytest fixtures to create temporary test databases with the full schema.
```

**Lines 79-88 - Update migration instructions:**

```markdown
### Applying Migrations

#### For New Installations

New databases created using `scripts/initialize_db.py` are automatically marked as migrated. No manual steps required.

The initialization script:
1. Creates schema from SQLModel definitions
2. Automatically runs `alembic stamp head`
3. Ready for future migrations

---

#### For Existing Installations (Pre-v2.3.0)

If you have an existing NexusLIMS database created with the SQL script (before v2.3.0), mark it as migrated:

```bash
# One-time operation: mark existing database as migrated to current schema
uv run alembic stamp head
```

This tells Alembic that your database already has the current schema structure and doesn't need the initial migration applied.

**Note:** Only run this ONCE when first upgrading to v2.3.0 or later. After this, use `alembic upgrade head` for future migrations.

---

#### For Future Schema Changes

When a new version includes database schema changes:

```bash
# Apply all pending migrations
uv run alembic upgrade head

# View current migration status
uv run alembic current

# View migration history
uv run alembic history
```
```

---

#### File: `docs/user_guide/getting_started.md`

**Lines 118-127 - Update database setup section:**

```markdown
## Database Setup

### Initialize the Database

NexusLIMS uses SQLite to track instruments and sessions. Initialize the database using the provided script:

```bash
# Create database with schema (interactive instrument entry)
python scripts/initialize_db.py $NX_DB_PATH

# Or with default test instruments (useful for initial setup/testing)
python scripts/initialize_db.py $NX_DB_PATH --defaults
```

The initialization script:
- Creates the database with full schema from ORM definitions
- Automatically marks it as migrated for future schema updates
- Provides interactive instrument entry (or uses defaults with `--defaults` flag)
- Ensures database is ready for use immediately

For more details on database management, see the [Database Documentation](../dev_guide/database.md).

---

### Configure Instruments

After creating the database, you can:

1. **Use default test instruments** (already done if you used `--defaults` flag above)
2. **Add instruments interactively** during initialization (default behavior)
3. **Manually insert instruments** using SQL or Python

**Note:** The `--defaults` flag populates test instruments from `test_instrument_factory.py`, useful for development but should be replaced with real instrument configurations for production.

For details on instrument configuration, see {ref}`instrument-configuration`.
```

---

#### File: `.claude/plans/external-user-identifiers.md`

**Lines 54-84 - Update to reference SQLModel approach:**

```markdown
### 1. Create SQLModel Class for External User Identifiers

**File:** `nexusLIMS/db/models.py`

Add new model class after the existing `UploadLog` class:

```python
class ExternalUserIdentifier(SQLModel, table=True):
    """
    Maps NexusLIMS usernames to external system user IDs.

    This table stores mappings between local usernames (from session logs)
    and external identifiers (from NEMO, Active Directory, etc.).
    """
    __tablename__ = "external_user_identifiers"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, nullable=False, index=True)
    external_system: str = Field(max_length=50, nullable=False)
    external_id: str = Field(max_length=100, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Unique constraint: one mapping per username per system
    __table_args__ = (
        UniqueConstraint('username', 'external_system', name='uq_username_system'),
    )
```

**Important:** SQLModel will automatically create the table schema when:
- `SQLModel.metadata.create_all(engine)` is called (new databases)
- Alembic autogenerate creates a migration for it (existing databases)

---

### 2. Create Alembic Migration

Generate and apply migration for the new table:

```bash
# Generate migration from model changes
uv run alembic revision --autogenerate -m "add external_user_identifiers table"

# Review the generated migration
cat migrations/versions/XXXXXX_add_external_user_identifiers_table.py

# Apply migration to database
uv run alembic upgrade head
```

The autogenerated migration will include:
- Table creation with all columns
- Indexes on `username` field
- Unique constraint on `(username, external_system)` combination
- Proper upgrade and downgrade paths

**Verification:**

```bash
# Check migration was applied
uv run alembic current

# Should show:
# XXXXXX (head)
```

---

### 3. Update Database Utilities

No manual SQL required - SQLModel handles schema creation automatically based on the model definition.
```

---

### Phase 6: Add Comprehensive Tests

**Goal:** Ensure schema creation works correctly in all scenarios.

**New file:** `tests/unit/test_db/test_database_initialization.py`

```python
"""Tests for database initialization and schema creation."""

import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlmodel import SQLModel, create_engine

from nexusLIMS.db.models import Instrument, SessionLog, UploadLog


def test_initialize_db_script_creates_schema(tmp_path):
    """Test that initialize_db.py creates correct schema."""
    from scripts.initialize_db import initialize_database

    db_path = tmp_path / "test.db"

    # Run initialization
    conn = initialize_database(str(db_path), force=False)

    assert conn is not None
    conn.close()

    # Verify schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert 'instruments' in tables
    assert 'session_log' in tables
    assert 'upload_log' in tables
    assert 'alembic_version' in tables

    # Check constraints on session_log
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='session_log'")
    schema = cursor.fetchone()[0]
    assert 'CHECK' in schema
    assert 'FOREIGN KEY' in schema

    conn.close()


def test_initialize_db_script_stamps_alembic(tmp_path, monkeypatch):
    """Test that initialize_db.py marks database as migrated."""
    from scripts.initialize_db import initialize_database

    db_path = tmp_path / "test.db"

    # Mock subprocess to capture alembic stamp call
    calls = []
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        calls.append((args, kwargs))
        # Actually run alembic stamp for real
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Run initialization
    conn = initialize_database(str(db_path), force=False)
    conn.close()

    # Verify alembic stamp was called
    assert len(calls) == 1
    assert "alembic" in calls[0][0][0]
    assert "stamp" in calls[0][0][0]
    assert "head" in calls[0][0][0]


def test_database_factory_creates_schema(tmp_path):
    """Test DatabaseFactory creates correct schema without SQL script."""
    from tests.unit.fixtures.database import DatabaseFactory

    factory = DatabaseFactory(tmp_path)
    db_path = factory.create_db()

    # Verify schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert 'instruments' in tables
    assert 'session_log' in tables
    assert 'upload_log' in tables

    conn.close()


def test_sqlmodel_schema_matches_sql_script():
    """Ensure SQLModel schema creates same structure as SQL script."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)

        # Get schema from SQLModel
        inspector = inspect(engine)
        sqlmodel_tables = set(inspector.get_table_names())

        # Should have exactly these tables
        assert sqlmodel_tables == {'instruments', 'session_log', 'upload_log'}

        # Verify instruments table structure
        instruments_cols = {
            col['name'] for col in inspector.get_columns('instruments')
        }
        expected_cols = {
            'instrument_pid', 'api_url', 'calendar_name', 'calendar_url',
            'location', 'schema_name', 'property_tag', 'filestore_path',
            'computer_name', 'computer_ip', 'computer_mount',
            'harvester', 'timezone'
        }
        assert instruments_cols == expected_cols

        # Verify session_log foreign key exists
        fks = inspector.get_foreign_keys('session_log')
        assert len(fks) >= 1
        assert any(
            fk['referred_table'] == 'instruments'
            for fk in fks
        )

        engine.dispose()
    finally:
        db_path.unlink()


def test_database_force_overwrite(tmp_path):
    """Test that force flag overwrites existing database."""
    from scripts.initialize_db import initialize_database

    db_path = tmp_path / "test.db"

    # Create first database
    conn1 = initialize_database(str(db_path), force=False)
    assert conn1 is not None
    conn1.close()

    # Try to create again without force (should fail)
    conn2 = initialize_database(str(db_path), force=False)
    assert conn2 is None  # Should return None (file exists)

    # Create again with force (should succeed)
    conn3 = initialize_database(str(db_path), force=True)
    assert conn3 is not None
    conn3.close()
```

**Update existing test:** `tests/unit/conftest.py`

Find and update the `db_factory` fixture to remove `schema_path`:

```python
@pytest.fixture
def db_factory(tmp_path):
    """Provide a DatabaseFactory for creating test databases on demand."""
    from tests.unit.fixtures.database import DatabaseFactory

    # OLD: return DatabaseFactory(tmp_path, schema_path)
    # NEW:
    return DatabaseFactory(tmp_path)
```

---

### Phase 7: Update Changelog

**File:** `docs/changes/README.rst` (create new changelog fragment)

**New file:** `docs/changes/XXX.removal.rst`

```rst
Removed manual SQL database creation script (``NexusLIMS_db_creation_script.sql``)
in favor of fully automated ORM-based schema management. All database operations
now use SQLModel ORM definitions with Alembic migrations for schema evolution.

**Breaking Changes:**

- **REMOVED:** ``nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql`` - No longer used or maintained
- **REMOVED:** ``nexusLIMS/db/dev/migrate_db.py`` - Legacy migration script removed (use ``alembic upgrade head`` instead)
- ``scripts/initialize_db.py`` no longer accepts ``sql_script_path`` parameter (uses SQLModel internally)
- ``DatabaseFactory`` (test utility) no longer accepts ``schema_path`` parameter (uses SQLModel internally)

**Migration Guide:**

For existing installations: No changes required. Run ``alembic stamp head`` once
if you haven't already (see v2.2.0 migration guide).

For new installations: Use ``python scripts/initialize_db.py`` to create databases.
The script automatically creates the schema from ORM models and marks it as migrated.

For test code: Update ``DatabaseFactory`` instantiation to remove ``schema_path``
parameter::

    # OLD:
    factory = DatabaseFactory(tmp_path, schema_path)

    # NEW:
    factory = DatabaseFactory(tmp_path)
```

---

## Migration Paths

### Brand New Installations

**Workflow:**
1. Run `python scripts/initialize_db.py /path/to/nexuslims_db.sqlite`
2. Database is created with full schema from SQLModel
3. Automatically marked as migrated (`alembic stamp head` runs internally)
4. Ready to use immediately

**No manual steps required.**

---

### Existing Installations (Pre-v2.3.0)

**Workflow:**
1. Already ran `alembic stamp head` when upgrading to v2.2.0 (per existing docs)
2. No changes needed for this upgrade
3. Future migrations work normally with `alembic upgrade head`

**No changes required.**

---

### Development/Testing

**Workflow:**
1. Tests already use `SQLModel.metadata.create_all()` (via `create_test_database()`)
2. Update `DatabaseFactory` instantiation to remove `schema_path` parameter
3. All tests continue working (schema creation method unchanged in practice)

**Minimal test updates required** (remove one parameter).

---

## Backward Compatibility Strategy

### SQL Script Removal

**Immediate removal (v2.3.0 - This Release):**
- Delete `nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql` entirely
- Remove all references in code and documentation
- Update all workflows to use SQLModel approach
- Note removal in changelog as breaking change

**Rationale:** Clean break from legacy approach. All schema management now exclusively through ORM. Users migrating from older versions follow Alembic migration path, not SQL script execution.

---

### Migration Baseline Handling

**Strategy:**
- Keep existing `57f0798d0c6d_initial_schema_baseline.py` migration unchanged
- New initial migration (`create_initial_schema_from_sqlmodel.py`) coexists
- Both have `down_revision = None` (parallel initial states)
- Alembic handles this correctly (uses whichever is stamped)

**Why this works:**
- Existing installations already stamped at `57f0798d0c6d` → no changes
- New installations stamp to new migration → schema created from SQLModel
- No conflicts, both approaches valid

---

## Verification Checklist

### Schema Validation
- [ ] SQLModel creates all tables correctly
- [ ] All constraints match SQL script (CHECK, FOREIGN KEY, UNIQUE)
- [ ] All indexes are created
- [ ] AUTOINCREMENT works for primary keys
- [ ] Foreign key CASCADE behavior works

### Migration Testing
- [ ] New migration upgrades empty database successfully
- [ ] New migration downgrades correctly
- [ ] Existing installations unaffected (alembic current shows correct revision)
- [ ] Migration history is linear and consistent

### Code Changes
- [ ] `initialize_db.py` uses SQLModel instead of SQL script
- [ ] `initialize_db.py` calls `alembic stamp head` automatically
- [ ] `DatabaseFactory` uses SQLModel instead of SQL script
- [ ] All `DatabaseFactory` instantiations updated (no `schema_path`)
- [ ] `NexusLIMS_db_creation_script.sql` deleted completely
- [ ] `migrate_db.py` deleted completely
- [ ] All references to deleted files removed from documentation

### Documentation
- [ ] Database creation instructions updated
- [ ] Migration workflow documented clearly
- [ ] Examples show SQLModel approach
- [ ] Troubleshooting section added
- [ ] Changelog fragment created

### Testing
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] New schema validation tests added
- [ ] Initialize script tested manually
- [ ] Migration upgrade/downgrade tested

---

## Rollback Plan

If issues are discovered after merging:

1. **Immediate:** Revert the PR that introduced these changes
2. **Fix:** Address specific issues identified
3. **Re-test:** Run full test suite and manual verification
4. **Re-deploy:** Merge fixed version

**Risk Mitigation:**
- Comprehensive tests reduce rollback likelihood
- Backward compatibility ensures existing installations unaffected

---

## Critical Files for Implementation

### Files to Create
1. `migrations/versions/XXXXXX_create_initial_schema_from_sqlmodel.py` - New initial migration
2. `tests/unit/test_db/test_database_initialization.py` - New comprehensive tests
3. `docs/changes/XXX.removal.rst` - Changelog fragment

### Files to Modify
1. `scripts/initialize_db.py` - Replace SQL script with SQLModel (lines 43-96, 344-346)
2. `tests/unit/fixtures/database.py` - Remove SQL script dependency (lines 31-44, 93-98)
3. `tests/unit/conftest.py` - Update `db_factory` fixture
4. `docs/dev_guide/database.md` - Update schema creation documentation
5. `docs/user_guide/getting_started.md` - Update database setup instructions
6. `.claude/plans/external-user-identifiers.md` - Update to reference SQLModel

### Files to Delete
1. `nexusLIMS/db/dev/NexusLIMS_db_creation_script.sql` - Delete entirely (immediate removal)
2. `nexusLIMS/db/dev/migrate_db.py` - Delete entirely (legacy script, superseded by Alembic)

---

## Implementation Order

1. **Create new initial migration** (Phase 1) - Foundation for everything else
2. **Update initialize_db.py** (Phase 2) - Enable new database creation
3. **Update DatabaseFactory** (Phase 3) - Fix test infrastructure
4. **Run all tests** - Verify nothing broke
5. **Delete legacy files** (Phase 4) - Remove SQL script and migrate_db.py entirely
6. **Update documentation** (Phase 5) - Remove all references to deleted files
7. **Add comprehensive tests** (Phase 6) - Ensure quality
8. **Create changelog** (Phase 7) - Document breaking changes
9. **Code review and merge**

---

## Success Criteria

- ✅ New databases created without SQL script execution
- ✅ All tests pass (unit, integration, new validation tests)
- ✅ Existing installations continue working unchanged
- ✅ Documentation clearly explains new vs existing installation workflows
- ✅ No manual SQL execution required for any workflow
- ✅ Alembic migrations work correctly for both new and existing databases
- ✅ Schema validation confirms SQLModel matches previous SQL script structure
