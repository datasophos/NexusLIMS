"""Database engine and session management for NexusLIMS.

This module provides a centralized SQLModel engine and session factory
for database operations, replacing the manual sqlite3 connection management.
"""

from sqlmodel import create_engine

from nexusLIMS.config import settings

# Create SQLite engine (connects to NexusLIMS database)
engine = create_engine(
    f"sqlite:///{settings.NX_DB_PATH}",
    connect_args={"check_same_thread": False},  # Allow multi-thread access
    echo=False,  # Set to True for SQL debug logging
)


def get_engine():
    """
    Get the database engine.

    Returns
    -------
    Engine
        The SQLModel engine for the NexusLIMS database.

    Examples
    --------
    >>> from nexusLIMS.db.engine import get_engine
    >>> engine = get_engine()
    >>> # Use engine for advanced operations
    """
    return engine
