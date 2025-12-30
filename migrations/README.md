# NexusLIMS Database Migrations

This directory contains
[Alembic](https://alembic.sqlalchemy.org/) database
migration scripts for NexusLIMS. Alembic provides
version control for the database schema, making it safe 
to upgrade existing installations and ensuring schema
consistency across deployments.

## Directory Structure

```
migrations/
├── README.md                 # This file
├── env.py                    # Migration environment configuration
├── script.py.mako           # Template for new migration scripts
└── versions/                 # Migration scripts
    └── 57f0798d0c6d_initial_schema_baseline.py
```

## Quick Start

### For Existing Installations (Upgrading from < 2.2.0)

If you have an existing NexusLIMS database created before version 2.2.0, mark it as migrated:

```bash
# Mark database as at current schema version
uv run alembic stamp head
```

### For New Installations

New installations automatically have the correct schema when the database is created. No migration needed.

## Common Commands

```bash
# Check current migration status
uv run alembic current

# View migration history
uv run alembic history --verbose

# Upgrade to latest schema
uv run alembic upgrade head

# Downgrade one migration
uv run alembic downgrade -1

# Create a new migration after modifying models
uv run alembic revision --autogenerate -m "Description of changes"
```

## Creating New Migrations

When you modify the database schema (SQLModel models in `nexusLIMS/db/models.py`):

1. **Edit the models** in `nexusLIMS/db/models.py`
2. **Generate migration**:
   ```bash
   uv run alembic revision --autogenerate -m "Add field to SessionLog"
   ```
3. **Review generated script** in `versions/` directory
4. **Test migration**:
   ```bash
   uv run alembic upgrade head    # Apply
   uv run alembic downgrade -1    # Rollback
   uv run alembic upgrade head    # Re-apply
   ```
5. **Commit migration script** to version control

## Configuration

- Database URL automatically read from `NX_DB_PATH` environment variable
- Source code configuration in `[tool.alembic]` section of `pyproject.toml`
- Migration environment setup in `env.py`

## Important Notes

- **Always backup production databases** before running migrations
- **Never edit applied migrations** - create new ones to fix issues
- **Test migrations thoroughly** in development first
- The baseline migration (`57f0798d0c6d`) is a no-op for existing installations

## Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [NexusLIMS Database Docs](../docs/dev_guide/database.md)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)