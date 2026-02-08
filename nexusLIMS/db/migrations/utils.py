"""Utilities for database migrations.

Provides helper functions for data integrity verification and backup creation
that can be used by migration scripts.
"""

import shutil
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa


def create_backup(connection) -> Path:
    """Create timestamped backup of database before migration.

    Parameters
    ----------
    connection
        SQLAlchemy connection to get database path from

    Returns
    -------
    pathlib.Path
        Path to the backup file

    Examples
    --------
    >>> from alembic import op
    >>> from nexusLIMS.migrations.utils import create_backup
    >>> def upgrade():
    ...     connection = op.get_bind()
    ...     create_backup(connection)
    ...     # ... perform migration ...
    """
    # Get database path from connection
    db_path = Path(connection.engine.url.database)

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"

    # Copy database file
    shutil.copy2(db_path, backup_path)

    print(f"✓ Database backup created: {backup_path}")  # noqa: T201
    return backup_path


def verify_table_integrity(  # noqa: PLR0913
    connection,
    table_name: str,
    expected_count: int,
    expected_pk_range: tuple[int, int] | None = None,
    expected_distribution: dict | None = None,
    distribution_column: str | None = None,
    pk_column: str = "id",
):
    """Verify table data was preserved during migration.

    Parameters
    ----------
    connection
        SQLAlchemy connection for queries
    table_name : str
        Name of the table to verify
    expected_count : int
        Expected number of rows
    expected_pk_range : tuple[int, int] | None
        Expected (min, max) primary key values
    expected_distribution : dict | None
        Expected distribution of values in a column (e.g., status counts)
    distribution_column : str | None
        Column name for distribution check
    pk_column : str
        Primary key column name (default: "id")

    Raises
    ------
    RuntimeError
        If data integrity checks fail

    Examples
    --------
    >>> from alembic import op
    >>> from nexusLIMS.migrations.utils import verify_table_integrity
    >>> def upgrade():
    ...     connection = op.get_bind()
    ...     # Before migration: collect baseline
    ...     result = connection.execute(sa.text("SELECT COUNT(*) FROM my_table"))
    ...     count = result.scalar()
    ...     # After migration: verify
    ...     verify_table_integrity(connection, "my_table_new", count)
    """
    # Count rows
    result = connection.execute(
        sa.text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
    )
    actual_count = result.scalar()

    if actual_count != expected_count:
        msg = (
            f"Data integrity check FAILED for {table_name}: "
            f"Row count mismatch! Expected: {expected_count}, Actual: {actual_count}"
        )
        raise RuntimeError(msg)

    # Verify primary key range if provided
    if expected_pk_range is not None:
        result = connection.execute(
            sa.text(
                f"SELECT MIN({pk_column}), MAX({pk_column}) FROM {table_name}"  # noqa: S608
            )
        )
        min_pk, max_pk = result.fetchone()

        if (min_pk, max_pk) != expected_pk_range:
            msg = (
                f"Data integrity check FAILED for {table_name}: "
                f"Primary key range mismatch! "
                f"Expected: {expected_pk_range}, Actual: ({min_pk}, {max_pk})"
            )
            raise RuntimeError(msg)

    # Verify distribution if provided
    if expected_distribution is not None and distribution_column is not None:
        result = connection.execute(
            sa.text(
                f"SELECT {distribution_column}, COUNT(*) FROM {table_name} "  # noqa: S608
                f"GROUP BY {distribution_column} ORDER BY {distribution_column}"
            )
        )
        actual_distribution = dict(result.fetchall())

        if actual_distribution != expected_distribution:
            msg = (
                f"Data integrity check FAILED for {table_name}: "
                f"Distribution mismatch in {distribution_column}! "
                f"Expected: {expected_distribution}, Actual: {actual_distribution}"
            )
            raise RuntimeError(msg)

    print(  # noqa: T201
        f"✓ Data integrity verified for {table_name}: {actual_count} rows preserved"
    )
