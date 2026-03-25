"""Database engine and session management for NexusLIMS."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

# Lazy singleton — created on first call to get_engine().
# Reset to None by SingletonResetter.reset_db_engine() between tests.
_engine: "Engine | None" = None


def create_transient_sqlite_engine(
    db_path: Path | str,
    *,
    echo: bool = False,
) -> "Engine":
    """
    Create a short-lived file-backed SQLite engine without connection pooling.

    This is the preferred helper for one-shot CLI utilities, fixtures, and tests
    that create a file-backed SQLite engine for a narrow scope and dispose it
    explicitly when finished.
    """
    from sqlalchemy.pool import NullPool  # noqa: PLC0415
    from sqlmodel import create_engine  # noqa: PLC0415

    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        echo=echo,
    )


def create_in_memory_engine(*, echo: bool = False) -> "Engine":
    """
    Create an in-memory SQLite engine backed by a single shared connection.

    Tests that need an in-memory database should use this helper so the same
    SQLite database remains available across sessions and threads.
    """
    from sqlalchemy.pool import StaticPool  # noqa: PLC0415
    from sqlmodel import create_engine  # noqa: PLC0415

    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=echo,
    )


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
