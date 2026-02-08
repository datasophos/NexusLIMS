"""Remove unused fields and rename schema_name to display_name.

Removes computer_name, computer_ip, computer_mount (deprecated Session Logger App
fields) and calendar_name (unused field). Also renames schema_name to display_name
for clarity.

Revision ID: v2_5_0b
Revises: v2_5_0a
Create Date: 2026-02-08 14:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v2_5_0b"
down_revision: Union[str, Sequence[str], None] = "v2_5_0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unused fields and rename schema_name to display_name."""
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        # Drop unused computer fields
        batch_op.drop_column("computer_mount")
        batch_op.drop_column("computer_ip")
        batch_op.drop_column("computer_name")
        # Drop unused calendar_name field
        batch_op.drop_column("calendar_name")
        # Rename schema_name to display_name
        batch_op.alter_column("schema_name", new_column_name="display_name")


def downgrade() -> None:
    """Restore removed fields and revert display_name to schema_name."""
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        # Restore computer fields (all optional, no unique constraints for simplicity)
        batch_op.add_column(sa.Column("computer_name", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("computer_ip", sa.String(length=15), nullable=True)
        )
        batch_op.add_column(sa.Column("computer_mount", sa.String(), nullable=True))
        # Restore calendar_name field (nullable since we have no data to populate it)
        batch_op.add_column(sa.Column("calendar_name", sa.String(), nullable=True))
        # Revert display_name to schema_name
        batch_op.alter_column("display_name", new_column_name="schema_name")
