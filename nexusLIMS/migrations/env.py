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

from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import SQLModel metadata and models
from sqlmodel import SQLModel

from nexusLIMS.config import settings
from nexusLIMS.db.models import Instrument, SessionLog, UploadLog  # noqa: F401

# Derive the migrations directory from this file's own location.
# Works regardless of whether the package is installed or run from source.
_MIGRATIONS_DIR = Path(__file__).resolve().parent

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set sqlalchemy.url from NexusLIMS settings
# This is always set dynamically from the environment rather than from config files
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.NX_DB_PATH}")

# Set target_metadata to SQLModel metadata for autogenerate support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


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
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
