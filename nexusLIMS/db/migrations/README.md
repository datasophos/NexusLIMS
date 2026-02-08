# NexusLIMS Database Migrations

The `nexusLIMS/db/migrations` directory in the NexusLIMS source code contains 
[Alembic](https://alembic.sqlalchemy.org/) database migration scripts for NexusLIMS.
Migrations provide version control for the database schema, making it safe to upgrade
existing installations and ensuring schema consistency across deployments.

## Directory Structure

```text
nexusLIMS/db/migrations/
├── README.md                                    # This file
├── env.py                                       # Migration environment configuration
├── utils.py                                     # Backup and verification utilities
├── script.py.mako                               # Template for new migration scripts
└── versions/                                    # Migration scripts (version-based IDs)
    ├── v1_4_3_initial_schema_baseline.py        # v1.4.3: instruments + session_log
    ├── v2_4_0a_add_upload_log_table.py         # v2.4.0: upload_log table
    └── v2_4_0b_add_check_constraints.py        # v2.4.0: CHECK constraints
```

## Quick Start

**Note:** The `nexuslims-migrate` command will use the `NX_DB_PATH` setting
configured in the `.env` file. If you would like to operate on a different
database file, you will need to set that variable in every command, such as:

```bash
NX_DB_PATH=/path/to/other/database.sqlite nexuslims-migrate check
```

### New Installations

To initialize a new NexusLIMS database with the latest schema, run:

```bash
nexuslims-migrate init
```

This creates the database file at `NX_DB_PATH`, applies all migrations, and marks it as current.

### Existing Installations

#### Upgrading from v1.4.3

If you have a v1.4.3 database from a prior installation of NexusLIMS,
you will first have to mark it as at the baseline version, and then and apply
updates to make the database compatible with the current version of NexusLIMS:

```bash
# Mark database as having the v1.4.3 baseline schema
nexuslims-migrate alembic stamp v1_4_3

# Apply pending migrations (v2.4.0 updates)
nexuslims-migrate upgrade

# Check the current version
nexuslims-migrate check
```

The last command should output something like the following:

```text
✓ Database is up-to-date (revision: v2_4_0b)
```

## Common Commands

### Check Status

```bash
# Show current database version
nexuslims-migrate current

# Check for pending migrations
nexuslims-migrate check

# View migration history
nexuslims-migrate history
```

### Upgrade/Downgrade

```bash
# Upgrade to latest schema
nexuslims-migrate upgrade

# Upgrade to specific version
nexuslims-migrate upgrade v2_4_0a

# Downgrade one migration
nexuslims-migrate downgrade

# Downgrade to specific version
nexuslims-migrate downgrade v1_4_3
```

### Advanced Commands (including Alembic CLI)

```bash
# View detailed history
nexuslims-migrate history --verbose

# Generate SQL without applying (to preview)
nexuslims-migrate upgrade --sql

# all Alembic commands are also available through `nexuslims-migrate alembic`:
nexuslims-migrate alembic [COMMAND] [OPTIONS]
```

## Creating New Migrations (for developers)

When you modify the database schema (SQLModel models in `nexusLIMS/db/models.py`):

1. **Edit the models** in `nexusLIMS/db/models.py`
2. **Generate migration** (requires source checkout):
   ```bash
   nexuslims-migrate alembic revision --autogenerate -m "Add field to SessionLog"
   ```
   This creates a new migration with a version-based ID (e.g., `v2_5_0_add_field_to_sessionlog.py`)

3. **Review generated script** in `versions/` directory
   - Check SQL operations are correct
   - Add data verification if needed (use `verify_table_integrity()` from `utils.py`)
   - Update upgrade() and downgrade() functions as needed

4. **Test migration**:
   ```bash
   nexuslims-migrate upgrade      # Apply
   nexuslims-migrate downgrade    # Rollback
   nexuslims-migrate upgrade      # Re-apply
   ```

5. **Commit migration script** to version control

## Migration Features

### Automatic Backups

Migrations automatically create timestamped backups before making changes:

```text
✓ Database backup created: database_backup_20260207_143216.sqlite
```

New database initialization (via `init`) skips backups since there's no data to protect.

### Data Integrity Verification

Migrations that recreate tables automatically verify data is preserved:

```text
→ Migrating 2270 session logs...
✓ Data integrity verified: 23 instruments, 2270 session logs preserved
```

Empty databases skip verification messages.

### Smart Output

- **New databases**: Clean, minimal output
- **Existing databases**: Detailed progress and verification

## Version-Based Migration IDs

Migration IDs use semantic versioning instead of random hex:

- **v1_4_3**: Baseline schema from NexusLIMS v1.4.3
- **v2_4_0a**: First migration in v2.4.0 (upload_log)
- **v2_4_0b**: Second migration in v2.4.0 (CHECK constraints)

This makes it immediately clear which NexusLIMS version introduced each database change.

## Configuration

- **Database path**: Automatically reads from `NX_DB_PATH` environment variable
- **Migration location**: Configured in `pyproject.toml` under `[tool.alembic]`
- **Environment setup**: `env.py` configures migration context and automatic backups

## Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [NexusLIMS Database Documentation](../../docs/dev_guide/database.md)
- [NexusLIMS CLI Reference](../../docs/user_guide/cli_reference.md)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
