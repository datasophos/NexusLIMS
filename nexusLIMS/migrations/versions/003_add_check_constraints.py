"""Add check constraints to session_log.

Adds CHECK constraints to session_log table for event_type and record_status.

This migration:
1. Adds CHECK constraint for event_type enum values
2. Adds CHECK constraint for record_status enum values (including BUILT_NOT_EXPORTED)

For SQLite, this requires recreating the table since ALTER TABLE doesn't support
adding CHECK constraints.

Revision ID: 003
Revises: 002
Create Date: 2026-01-25 10:28:38.768026

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support adding CHECK constraints via ALTER TABLE,
    # so we need to recreate the table

    # Step 1: Create new table with CHECK constraints (without index yet)
    op.create_table(
        "session_log_new",
        sa.Column("id_session_log", sa.Integer(), nullable=False),
        sa.Column("session_identifier", sa.String(length=36), nullable=False),
        sa.Column("instrument", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=17), nullable=False),
        sa.Column("record_status", sa.String(length=18), nullable=False),
        sa.Column("user", sa.String(length=50), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('START', 'END', 'RECORD_GENERATION')",
            name="check_event_type",
        ),
        sa.CheckConstraint(
            "record_status IN ('COMPLETED', 'WAITING_FOR_END', 'TO_BE_BUILT', "
            "'BUILT_NOT_EXPORTED', 'ERROR', 'NO_FILES_FOUND', 'NO_CONSENT', "
            "'NO_RESERVATION')",
            name="check_record_status",
        ),
        sa.ForeignKeyConstraint(
            ["instrument"],
            ["instruments.instrument_pid"],
        ),
        sa.PrimaryKeyConstraint("id_session_log"),
    )

    # Step 2: Copy data from old table to new table
    op.execute(
        """
        INSERT INTO session_log_new (
            id_session_log, session_identifier, instrument, timestamp,
            event_type, record_status, user
        )
        SELECT
            id_session_log, session_identifier, instrument, timestamp,
            event_type, record_status, user
        FROM session_log
        """
    )

    # Step 3: Drop index from old table
    op.drop_index("ix_session_log_session_identifier", table_name="session_log")

    # Step 4: Drop old table
    op.drop_table("session_log")

    # Step 5: Rename new table to original name
    op.rename_table("session_log_new", "session_log")

    # Step 6: Create index on the renamed table (after old one is dropped)
    op.create_index(
        "ix_session_log_session_identifier",
        "session_log",
        ["session_identifier"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate table without CHECK constraints

    # Step 1: Create table without CHECK constraints (without index yet)
    op.create_table(
        "session_log_old",
        sa.Column("id_session_log", sa.Integer(), nullable=False),
        sa.Column("session_identifier", sa.String(length=36), nullable=False),
        sa.Column("instrument", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=17), nullable=False),
        sa.Column("record_status", sa.String(length=18), nullable=False),
        sa.Column("user", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument"],
            ["instruments.instrument_pid"],
        ),
        sa.PrimaryKeyConstraint("id_session_log"),
    )

    # Step 2: Copy data
    op.execute(
        """
        INSERT INTO session_log_old (
            id_session_log, session_identifier, instrument, timestamp,
            event_type, record_status, user
        )
        SELECT
            id_session_log, session_identifier, instrument, timestamp,
            event_type, record_status, user
        FROM session_log
        """
    )

    # Step 3: Drop index from current table
    op.drop_index("ix_session_log_session_identifier", table_name="session_log")

    # Step 4: Drop new table
    op.drop_table("session_log")

    # Step 5: Rename old table
    op.rename_table("session_log_old", "session_log")

    # Step 6: Create index on renamed table
    op.create_index(
        "ix_session_log_session_identifier",
        "session_log",
        ["session_identifier"],
        unique=False,
    )
