"""Add upload_log table and BUILT_NOT_EXPORTED status.

Revision ID: v2_4_0_1
Revises: v1_4_3
Create Date: 2026-01-23 12:12:15.867734

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v2_4_0_1"
down_revision: Union[str, Sequence[str], None] = "v1_4_3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create upload_log table
    op.create_table(
        "upload_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_identifier", sa.String(length=36), nullable=False),
        sa.Column("destination_name", sa.String(length=100), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=True),
        sa.Column("record_url", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        op.f("ix_upload_log_session_identifier"),
        "upload_log",
        ["session_identifier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_upload_log_destination_name"),
        "upload_log",
        ["destination_name"],
        unique=False,
    )

    # Note: BUILT_NOT_EXPORTED status is added to the RecordStatus enum in code.
    # SQLite stores enums as strings, so no schema migration is needed for the enum.
    # The new status will be available immediately upon deploying the updated code.


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f("ix_upload_log_destination_name"), table_name="upload_log")
    op.drop_index(op.f("ix_upload_log_session_identifier"), table_name="upload_log")

    # Drop table
    op.drop_table("upload_log")

    # Note: Downgrading the BUILT_NOT_EXPORTED status would require updating
    # any session_log rows that use it. Since SQLite stores enums as strings,
    # the old code will simply not recognize this status value.
    # Manual cleanup may be needed if any rows use BUILT_NOT_EXPORTED.
