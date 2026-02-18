# ruff: noqa: ERA001
"""Alembic migration environment configuration for NexusLIMS.

This module configures the Alembic migration environment for the NexusLIMS database.
It handles both online and offline migration modes and automatically configures the
database URL from the NexusLIMS settings.

Key features:
    - Automatically reads database path from NX_DB_PATH environment variable
    - Configures SQLModel metadata for autogenerate support
    - Supports both online (live database) and offline (SQL script) migrations
    - Imports all SQLModel classes to ensure complete schema detection

Usage:
    This file is automatically used by Alembic when running migration commands:
        uv run alembic upgrade head
        uv run alembic revision --autogenerate -m "description"

Note:
    All SQLModel model classes must be imported in this file (even if not directly
    used) to ensure Alembic can detect them for autogenerate operations.
"""

import os
import re
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool

# Import SQLModel metadata and models
from sqlmodel import SQLModel

from nexusLIMS.db.models import Instrument, SessionLog, UploadLog  # noqa: F401

# Derive the migrations directory from this file's own location.
# Works regardless of whether the package is installed or run from source.
_MIGRATIONS_DIR = Path(__file__).resolve().parent

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set sqlalchemy.url directly from the environment variable rather than going
# through nexusLIMS.config.settings, because Settings validation requires fields
# (like NX_CDCS_TOKEN, NX_DATA_PATH, etc.) that are irrelevant for database
# migrations. This allows 'nexuslims db' commands to work with only
# NX_DB_PATH set.
_db_path = os.getenv("NX_DB_PATH", "")
config.set_main_option("sqlalchemy.url", f"sqlite:///{_db_path}")

# Set target_metadata to SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def _generate_revision_id(context_obj) -> str:
    """Generate a user-friendly sequential revision ID.

    This function creates revision IDs in the format: NNN_description
    where NNN is a zero-padded sequential number.

    Examples: 001_initial_schema, 002_add_upload_log, 003_add_constraints

    This is much more readable than random hex values while maintaining
    clear ordering.
    """
    script = ScriptDirectory.from_config(config)

    # Find the highest existing numeric revision
    max_num = 0
    for rev in script.walk_revisions():
        if rev.revision and rev.revision[0].isdigit():
            try:
                # Extract numeric prefix (e.g., "001" from "001_description")
                num_part = rev.revision.split("_")[0]
                max_num = max(max_num, int(num_part))
            except (ValueError, IndexError):  # pragma: no cover
                # Skip if not in our format
                pass

    # Generate next sequential number
    next_num = max_num + 1

    # Get the message from the context (cleaned up for use in ID)
    message = context_obj.opts.get("message", "migration")
    if message:
        # Convert message to lowercase, replace spaces/special chars with underscores
        sanitized = re.sub(r"[^\w\s-]", "", message.lower())
        sanitized = re.sub(r"[-\s]+", "_", sanitized).strip("_")
        # Limit length to keep IDs reasonable
        sanitized = sanitized[:50]
    else:
        sanitized = "migration"

    return f"{next_num:03d}_{sanitized}"


def process_revision_directives(context_obj, _revision, directives):
    """Alembic hook to customize revision generation.

    This is called by Alembic when creating new migrations via
    'nexuslims db alembic revision --autogenerate'.

    It replaces the default random hex revision ID with a sequential
    numbered ID for better readability.
    """
    if config.cmd_opts and config.cmd_opts.autogenerate:
        script = directives[0]
        if script.upgrade_ops.is_empty():
            # Don't generate empty migrations
            directives[:] = []
            return

        # Use our custom revision ID generator
        script.rev_id = _generate_revision_id(context_obj)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from nexusLIMS.db.migrations.utils import create_backup  # noqa: PLC0415

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            # Create automatic backup before running migrations
            # Skip backup for new database initialization (no alembic_version table yet)
            try:
                destination_rev = context.get_context().opts.get("destination_rev")
                if destination_rev:
                    # Check if alembic_version table exists
                    # (indicates existing database)
                    inspector = sa.inspect(connection)
                    has_alembic_version = (
                        "alembic_version" in inspector.get_table_names()
                    )

                    if has_alembic_version:
                        create_backup(connection)
                    # else: new database initialization, skip backup
            except Exception:  # noqa: S110
                # If we can't determine if backup is needed, skip it
                # (e.g., for read-only operations like current/history)
                pass

            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
