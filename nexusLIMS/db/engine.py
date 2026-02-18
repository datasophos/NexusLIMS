"""Database engine and session management for NexusLIMS.

This module provides a centralized SQLModel engine and session factory
for database operations, replacing the manual sqlite3 connection management.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

# Lazy singleton — created on first call to get_engine().
# Reset to None by SingletonResetter.reset_db_engine() between tests.
_engine: "Engine | None" = None


def get_engine() -> "Engine":
    """
    Get the database engine, creating it lazily on first access.

    Returns
    -------
    sqlalchemy.engine.base.Engine
        The SQLAlchemy/SQLModel engine for the NexusLIMS database.

    Examples
    --------
    >>> from nexusLIMS.db.engine import get_engine
    >>> engine = get_engine()
    >>> # Use engine for advanced operations
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        from sqlmodel import create_engine  # noqa: PLC0415

        from nexusLIMS.config import settings  # noqa: PLC0415

        _engine = create_engine(
            f"sqlite:///{settings.NX_DB_PATH}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine
