"""Initial schema baseline.

This is a baseline migration for existing NexusLIMS installations.
The database schema already exists (created via NexusLIMS_db_creation_script.sql),
so this migration does nothing - it just marks the initial state.

For existing installations: Run `alembic stamp head` to mark as migrated.
For new installations: The schema will be created by SQLModel.metadata.create_all()
or by running the creation script.

Revision ID: 57f0798d0c6d
Revises:
Create Date: 2025-12-29 11:08:25.723483

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "57f0798d0c6d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
