"""Database engine and session management for NexusLIMS.

This module provides a centralized SQLModel engine and session factory
for database operations, replacing the manual sqlite3 connection management.
"""

from typing import TYPE_CHECKING

from sqlmodel import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

# Module-level engine variable (initialized lazily on first access)
_engine: "Engine | None" = None


def get_engine() -> "Engine":
    """
    Get the database engine.

    The engine is created lazily on first access to avoid triggering
    Settings validation during module import. This allows tools like
    ``nexuslims-config edit`` to run without a valid .env file.

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
        # Import settings only when needed (lazy)
        from nexusLIMS.config import settings  # noqa: PLC0415

        _engine = create_engine(
            f"sqlite:///{settings.NX_DB_PATH}",
            connect_args={"check_same_thread": False},  # Allow multi-thread access
            echo=False,  # Set to True for SQL debug logging
        )
    return _engine
