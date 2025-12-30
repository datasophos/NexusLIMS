"""Database enumerations for NexusLIMS.

This module defines type-safe enums for database fields that have
constrained values (CHECK constraints in the database schema).
"""

from enum import Enum


class EventType(str, Enum):
    """Allowed event types for session logs.

    Maps to the CHECK constraint in session_log.event_type column.
    """

    START = "START"
    END = "END"
    RECORD_GENERATION = "RECORD_GENERATION"


class RecordStatus(str, Enum):
    """Allowed record status values for session logs.

    Maps to the CHECK constraint in session_log.record_status column.

    Attributes
    ----------
    WAITING_FOR_END
        Session has started but not yet ended
    TO_BE_BUILT
        Session has ended and needs record generation
    COMPLETED
        Record has been successfully built and uploaded
    ERROR
        Record building failed with an error
    NO_FILES_FOUND
        No files were found for this session
    NO_CONSENT
        User did not consent to data harvesting
    NO_RESERVATION
        No matching reservation found for this session
    """

    WAITING_FOR_END = "WAITING_FOR_END"
    TO_BE_BUILT = "TO_BE_BUILT"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    NO_FILES_FOUND = "NO_FILES_FOUND"
    NO_CONSENT = "NO_CONSENT"
    NO_RESERVATION = "NO_RESERVATION"
