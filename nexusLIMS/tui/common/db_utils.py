"""
Database utilities for NexusLIMS TUI applications.

Provides session management and common database query patterns.
"""

from contextlib import contextmanager
from typing import Any

from sqlmodel import Session, select

from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.models import Instrument, SessionLog


@contextmanager
def get_db_session():
    """
    Context manager for database sessions.

    Yields
    ------
    Session
        Active database session

    Examples
    --------
    >>> from nexusLIMS.tui.common.db_utils import get_db_session
    >>> with get_db_session() as session:
    ...     instruments = session.exec(select(Instrument)).all()
    """
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()


def check_uniqueness(
    session: Session,
    model: type,
    field_name: str,
    value: Any,
    exclude_pk: Any | None = None,
) -> bool:
    """
    Check if a value is unique for a given field.

    Parameters
    ----------
    session : Session
        Active database session
    model : type
        SQLModel model class (e.g., Instrument)
    field_name : str
        Field name to check (e.g., "api_url")
    value : Any
        Value to check for uniqueness
    exclude_pk : Any | None
        Primary key value to exclude (for edit operations)

    Returns
    -------
    bool
        True if unique, False if duplicate exists

    Examples
    --------
    >>> from nexusLIMS.db.models import Instrument
    >>> with get_db_session() as session:
    ...     is_unique = check_uniqueness(
    ...         session, Instrument, "api_url",
    ...         "https://example.com/api/tools/?id=42"
    ...     )
    """
    # Skip check if value is None (for optional fields)
    if value is None:
        return True

    # Build query
    field = getattr(model, field_name)
    statement = select(model).where(field == value)

    # Exclude current record if editing
    if exclude_pk is not None:
        pk_field = getattr(model, model.__table__.primary_key.columns.keys()[0])
        statement = statement.where(pk_field != exclude_pk)

    # Check if any records exist
    existing = session.exec(statement).first()
    return existing is None


def get_session_log_count(session: Session, instrument_pid: str) -> int:
    """
    Get count of session_log entries for an instrument.

    Useful for warning users before deleting an instrument with associated data.

    Parameters
    ----------
    session : Session
        Active database session
    instrument_pid : str
        Instrument primary key

    Returns
    -------
    int
        Number of session_log entries

    Examples
    --------
    >>> with get_db_session() as session:
    ...     count = get_session_log_count(session, "FEI-Titan-TEM")
    ...     if count > 0:
    ...         print(f"Warning: {count} session logs will be orphaned")
    """
    statement = select(SessionLog).where(SessionLog.instrument == instrument_pid)
    results = session.exec(statement).all()
    return len(results)


def find_conflicting_instrument(
    session: Session,
    field_name: str,
    value: Any,
    exclude_pid: str | None = None,
) -> Instrument | None:
    """
    Find an instrument that conflicts with a unique field value.

    Parameters
    ----------
    session : Session
        Active database session
    field_name : str
        Unique field name (api_url, computer_name, computer_ip)
    value : Any
        Value to search for
    exclude_pid : str | None
        Instrument PID to exclude (for edit operations)

    Returns
    -------
    Instrument | None
        Conflicting instrument, or None if no conflict

    Examples
    --------
    >>> with get_db_session() as session:
    ...     conflict = find_conflicting_instrument(
    ...         session, "api_url", "https://example.com/api"
    ...     )
    ...     if conflict:
    ...         print(f"Already used by {conflict.instrument_pid}")
    """
    if value is None:
        return None

    field = getattr(Instrument, field_name)
    statement = select(Instrument).where(field == value)

    if exclude_pid is not None:
        statement = statement.where(Instrument.instrument_pid != exclude_pid)

    return session.exec(statement).first()
