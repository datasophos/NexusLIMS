"""Add external_user_identifiers table.

Adds table for mapping NexusLIMS usernames to external system user IDs using
a star topology design with nexuslims_username as the canonical identifier.

Supports integration with:
- NEMO (lab management system)
- LabArchives ELN (electronic lab notebook)
- LabArchives Scheduler (reservation system)
- CDCS (Configurable Data Curation System)

Revision ID: v2_5_0a
Revises: v2_4_0b
Create Date: 2026-02-08 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v2_5_0a"
down_revision: Union[str, Sequence[str], None] = "v2_4_0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create external_user_identifiers table."""
    # Create table with CHECK constraint and UNIQUE constraints
    # NOTE: CHECK constraint values are hardcoded to preserve this migration's
    # historical accuracy. If ExternalSystem enum changes in the future, a new
    # migration should be created to update the constraint.
    op.create_table(
        "external_user_identifiers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nexuslims_username", sa.String(), nullable=False),
        sa.Column("external_system", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("last_verified_at", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.CheckConstraint(
            "external_system IN ('nemo', 'labarchives_eln', "
            "'labarchives_scheduler', 'cdcs')",
            name="valid_external_system",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "nexuslims_username",
            "external_system",
            name="nexuslims_username_system_UNIQUE",
        ),
        sa.UniqueConstraint(
            "external_system", "external_id", name="system_external_id_UNIQUE"
        ),
    )

    # Create indexes
    op.create_index(
        "idx_external_lookup",
        "external_user_identifiers",
        ["external_system", "external_id"],
        unique=False,
    )
    op.create_index(
        "idx_nexuslims_username",
        "external_user_identifiers",
        ["nexuslims_username"],
        unique=False,
    )


def downgrade() -> None:
    """Drop external_user_identifiers table."""
    # Drop indexes
    op.drop_index("idx_nexuslims_username", table_name="external_user_identifiers")
    op.drop_index("idx_external_lookup", table_name="external_user_identifiers")

    # Drop table
    op.drop_table("external_user_identifiers")
