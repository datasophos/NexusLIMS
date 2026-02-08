"""Add check constraints to session_log.

Adds CHECK constraints to session_log table for event_type and record_status.

This migration:
1. Adds CHECK constraint for event_type enum values
2. Adds CHECK constraint for record_status enum values (including BUILT_NOT_EXPORTED)

For SQLite, this requires recreating the table since ALTER TABLE doesn't support
adding CHECK constraints.

Revision ID: v2_4_0_2
Revises: v2_4_0_1
Create Date: 2026-01-25 10:28:38.768026

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from nexusLIMS.db.migrations.utils import verify_table_integrity

# revision identifiers, used by Alembic.
revision: str = "v2_4_0_2"
down_revision: Union[str, Sequence[str], None] = "v2_4_0_1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support adding CHECK constraints via ALTER TABLE,
    # so we need to recreate the table

    from alembic import context  # noqa: PLC0415

    connection = op.get_bind()

    # Skip data verification in offline/SQL mode (when generating SQL scripts)
    # In these modes, there's no actual database to query
    is_offline = context.is_offline_mode()

    if not is_offline:
        # Collect baseline data for verification (instruments table should be unchanged)
        result = connection.execute(sa.text("SELECT COUNT(*) FROM instruments"))
        instruments_count = result.scalar()

        # Collect session_log data for integrity verification
        result = connection.execute(sa.text("SELECT COUNT(*) FROM session_log"))
        session_log_count = result.scalar()

        result = connection.execute(
            sa.text("SELECT MIN(id_session_log), MAX(id_session_log) FROM session_log")
        )
        min_id, max_id = result.fetchone()

        result = connection.execute(
            sa.text(
                "SELECT record_status, COUNT(*) FROM session_log "
                "GROUP BY record_status ORDER BY record_status"
            )
        )
        status_counts = dict(result.fetchall())

        # Only show migration message if there's data to migrate
        if session_log_count > 0:
            print(f"→ Migrating {session_log_count} session logs...")  # noqa: T201
    else:
        # In offline mode, set dummy values (won't be used)
        instruments_count = 0
        session_log_count = 0
        min_id = None
        max_id = None
        status_counts = {}

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

    # Step 2a: Verify data integrity before dropping old table
    # Only verify if there's data to verify and we're not in offline/SQL mode
    if not is_offline and (session_log_count > 0 or instruments_count > 0):
        # Verify instruments unchanged
        verify_table_integrity(connection, "instruments", instruments_count)

        # Verify session_log data preserved
        verify_table_integrity(
            connection,
            "session_log_new",
            session_log_count,
            expected_pk_range=(min_id, max_id),
            expected_distribution=status_counts,
            distribution_column="record_status",
            pk_column="id_session_log",
        )
        print(  # noqa: T201
            f"✓ Data integrity verified: {instruments_count} instruments, "
            f"{session_log_count} session logs preserved"
        )

    # Step 3: Drop any indexes from old table
    # Use IF EXISTS to handle both v1.4.3 databases (different index names)
    # and databases created via migration 001 (which have
    # ix_session_log_session_identifier)
    op.execute("DROP INDEX IF EXISTS ix_session_log_session_identifier")
    op.execute('DROP INDEX IF EXISTS "session_log.fk_instrument_idx"')

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

    from alembic import context  # noqa: PLC0415

    connection = op.get_bind()

    # Skip data verification in offline/SQL mode
    is_offline = context.is_offline_mode()

    if not is_offline:
        # Collect baseline data for verification
        result = connection.execute(sa.text("SELECT COUNT(*) FROM instruments"))
        instruments_count = result.scalar()

        # Collect session_log data for integrity verification
        result = connection.execute(sa.text("SELECT COUNT(*) FROM session_log"))
        session_log_count = result.scalar()

        result = connection.execute(
            sa.text("SELECT MIN(id_session_log), MAX(id_session_log) FROM session_log")
        )
        min_id, max_id = result.fetchone()

        result = connection.execute(
            sa.text(
                "SELECT record_status, COUNT(*) FROM session_log "
                "GROUP BY record_status ORDER BY record_status"
            )
        )
        status_counts = dict(result.fetchall())

        # Only show downgrade message if there's data to downgrade
        if session_log_count > 0:
            print(f"→ Downgrading {session_log_count} session logs...")  # noqa: T201
    else:
        # In offline mode, set dummy values
        instruments_count = 0
        session_log_count = 0
        min_id = None
        max_id = None
        status_counts = {}

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

    # Step 2a: Verify data integrity before dropping current table
    # Only verify if there's data to verify and we're not in offline/SQL mode
    if not is_offline and (session_log_count > 0 or instruments_count > 0):
        # Verify instruments unchanged
        verify_table_integrity(connection, "instruments", instruments_count)

        # Verify session_log data preserved
        verify_table_integrity(
            connection,
            "session_log_old",
            session_log_count,
            expected_pk_range=(min_id, max_id),
            expected_distribution=status_counts,
            distribution_column="record_status",
            pk_column="id_session_log",
        )
        print(  # noqa: T201
            f"✓ Data integrity verified: {instruments_count} instruments, "
            f"{session_log_count} session logs preserved"
        )

    # Step 3: Drop index from current table
    # Use IF EXISTS to handle different database states
    op.execute("DROP INDEX IF EXISTS ix_session_log_session_identifier")
    op.execute('DROP INDEX IF EXISTS "session_log.fk_instrument_idx"')

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
