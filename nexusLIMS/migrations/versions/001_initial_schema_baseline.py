"""Initial schema baseline.

Creates the core NexusLIMS database schema with instruments and session_log tables.

This migration creates the foundational schema based on SQLModel definitions.
For existing installations (pre-2.5.0): Run `alembic stamp 001` to mark as migrated.
For new installations: This migration creates the initial tables.

Revision ID: 001
Revises:
Create Date: 2025-12-29 11:08:25.723483

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial NexusLIMS schema.

    Creates:
    - instruments table: Instrument configuration and metadata
    - session_log table: Session event tracking (without CHECK constraints)

    Note: CHECK constraints on session_log are added in migration 003.
    """
    # Create instruments table
    op.create_table(
        "instruments",
        sa.Column("instrument_pid", sa.String(length=100), nullable=False),
        sa.Column("api_url", sa.String(), nullable=False),
        sa.Column("calendar_name", sa.String(), nullable=False),
        sa.Column("calendar_url", sa.String(), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=False),
        sa.Column("schema_name", sa.String(), nullable=False),
        sa.Column("property_tag", sa.String(length=20), nullable=False),
        sa.Column("filestore_path", sa.String(), nullable=False),
        sa.Column("harvester", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("computer_name", sa.String(), nullable=True),
        sa.Column("computer_ip", sa.String(length=15), nullable=True),
        sa.Column("computer_mount", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("instrument_pid"),
        sa.UniqueConstraint("api_url"),
        sa.UniqueConstraint("computer_name"),
        sa.UniqueConstraint("computer_ip"),
    )

    # Create session_log table (without CHECK constraints - added in migration 003)
    op.create_table(
        "session_log",
        sa.Column("id_session_log", sa.Integer(), nullable=False),
        sa.Column("session_identifier", sa.String(length=36), nullable=False),
        sa.Column("instrument", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("record_status", sa.String(), nullable=False),
        sa.Column("user", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument"],
            ["instruments.instrument_pid"],
        ),
        sa.PrimaryKeyConstraint("id_session_log"),
    )
    op.create_index(
        op.f("ix_session_log_session_identifier"),
        "session_log",
        ["session_identifier"],
        unique=False,
    )


def downgrade() -> None:
    """Drop initial schema tables."""
    op.drop_index(op.f("ix_session_log_session_identifier"), table_name="session_log")
    op.drop_table("session_log")
    op.drop_table("instruments")
