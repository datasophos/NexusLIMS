"""SQLModel database models for NexusLIMS.

This module defines the SQLModel ORM classes that map to the NexusLIMS
database tables (`instruments` and `session_log`).
"""

import datetime
import json
import logging

import pytz
from pytz.tzinfo import BaseTzInfo
from sqlalchemy import CheckConstraint, UniqueConstraint, types
from sqlalchemy.types import TypeDecorator
from sqlmodel import Column, Field, Relationship, SQLModel, select
from sqlmodel import Session as DBSession

from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, ExternalSystem, RecordStatus

_logger = logging.getLogger(__name__)


class TZDateTime(TypeDecorator):
    """
    Custom DateTime type that preserves timezone information in SQLite.

    SQLite stores datetimes as TEXT and doesn't preserve timezone info.
    This TypeDecorator stores timezone-aware datetimes as ISO-8601 strings
    with timezone offset, and restores them as timezone-aware datetime objects.
    """

    impl = types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ARG002
        """Convert timezone-aware datetime to ISO string for storage."""
        if value is not None:
            if isinstance(value, datetime.datetime):
                # Store as ISO string with timezone offset
                return value.isoformat()
            # Already a string
            return value
        return value

    def process_result_value(self, value, dialect):  # noqa: ARG002
        """Convert ISO string back to timezone-aware datetime."""
        if value is not None:
            if isinstance(value, str):
                # Parse ISO string with timezone
                return datetime.datetime.fromisoformat(value)
            # Already a datetime object
            return value
        return value


class Instrument(SQLModel, table=True):
    """
    Instrument configuration from the NexusLIMS database.

    Represents an electron microscopy instrument in the facility,
    with configuration for calendar integration, file storage, and metadata.

    Parameters
    ----------
    instrument_pid
        Unique identifier for the instrument (e.g., "FEI-Titan-TEM-012345")
    api_url
        Calendar API endpoint URL for this instrument's scheduler (e.g.,
        `https://<nemo_address>/api/tools/?id=<tool_id>`)
    calendar_url
        URL to the instrument's web-accessible calendar
    location
        Physical location (building and room number)
    display_name
        Human-readable instrument name displayed in NexusLIMS records
    property_tag
        Unique numeric identifier (for reference)
    filestore_path
        Relative path under NX_INSTRUMENT_DATA_PATH where data is stored
    harvester
        Harvester module to use ("nemo" or "sharepoint")
    timezone_str
        IANA timezone database string (e.g., "America/New_York")
    """

    __tablename__ = "instruments"

    # Primary key
    instrument_pid: str = Field(primary_key=True, max_length=100)

    # Required fields
    api_url: str = Field(unique=True)
    calendar_url: str
    location: str = Field(max_length=100)
    display_name: str
    property_tag: str = Field(max_length=20)
    filestore_path: str
    harvester: str = Field(default="nemo")
    timezone_str: str = Field(
        sa_column_kwargs={"name": "timezone"}, default="America/New_York"
    )

    # Relationships
    session_logs: list["SessionLog"] = Relationship(back_populates="instrument_obj")

    @property
    def name(self) -> str:
        """Alias for instrument_pid (backward compatibility)."""
        return self.instrument_pid

    @property
    def timezone(self) -> BaseTzInfo:
        """Convert timezone string to pytz timezone object."""
        return pytz.timezone(self.timezone_str)

    def __repr__(self):
        """Return custom representation of an Instrument."""
        return (
            f"Nexus Instrument: {self.name}\n"
            f"API url:          {self.api_url}\n"
            f"Calendar url:     {self.calendar_url}\n"
            f"Display name:     {self.display_name}\n"
            f"Location:         {self.location}\n"
            f"Property tag:     {self.property_tag}\n"
            f"Filestore path:   {self.filestore_path}\n"
            f"Harvester:        {self.harvester}\n"
            f"Timezone:         {self.timezone}"
        )

    def __str__(self):
        """Return custom string representation of an Instrument."""
        return f"{self.name} in {self.location}" if self.location else ""

    def localize_datetime(self, _dt: datetime.datetime) -> datetime.datetime:
        """
        Localize a datetime to an Instrument's timezone.

        Convert a date and time to the timezone of this instrument. If the
        supplied datetime is naive (i.e. does not have a timezone), it will be
        assumed to already be in the timezone of the instrument, and the
        displayed time will not change. If the timezone of the supplied
        datetime is different than the instrument's, the time will be
        adjusted to compensate for the timezone offset.

        Parameters
        ----------
        _dt
            The datetime object to localize

        Returns
        -------
        datetime.datetime
            A datetime object with the same timezone as the instrument
        """
        _logger = logging.getLogger(__name__)

        if self.timezone is None:
            _logger.warning(
                "Tried to localize a datetime with instrument that does not have "
                "timezone information (%s)",
                self.name,
            )
            return _dt
        if _dt.tzinfo is None:
            # dt is timezone naive
            return self.timezone.localize(_dt)

        # dt has timezone info
        return _dt.astimezone(self.timezone)

    def localize_datetime_str(
        self,
        _dt: datetime.datetime,
        fmt: str = "%Y-%m-%d %H:%M:%S %Z",
    ) -> str:
        """
        Localize a datetime to an Instrument's timezone and return as string.

        Convert a date and time to the timezone of this instrument, returning
        a textual representation of the object, rather than the datetime
        itself. Uses :py:meth:`localize_datetime` for the actual conversion.

        Parameters
        ----------
        _dt
            The datetime object to localize
        fmt
            The strftime format string to use to format the output

        Returns
        -------
        str
            The formatted textual representation of the localized datetime
        """
        return self.localize_datetime(_dt).strftime(fmt)

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the Instrument object.

        Handles special cases like renaming 'instrument_pid' and
        converting timezone objects to strings.

        Returns
        -------
        dict
            A dictionary representation of the instrument, suitable for database
            insertion or JSON serialization.
        """
        # Convert SQLModel to dict (excludes relationships by default)
        return {
            "instrument_pid": self.instrument_pid,
            "api_url": self.api_url,
            "calendar_url": self.calendar_url,
            "location": self.location,
            "display_name": self.display_name,
            "property_tag": self.property_tag,
            "filestore_path": self.filestore_path,
            "harvester": self.harvester,
            "timezone": self.timezone_str,
        }

    def to_json(self, **kwargs) -> str:
        """
        Return a JSON string representation of the Instrument object.

        Parameters
        ----------
        **kwargs
            Additional keyword arguments to pass to `json.dumps`.

        Returns
        -------
        str
            A JSON string representation of the instrument.
        """
        return json.dumps(self.to_dict(), **kwargs)


class SessionLog(SQLModel, table=True):
    """
    Individual session log entry (START, END, or RECORD_GENERATION event).

    A simple mapping of one row in the session_log table. Each session
    typically has a START and END log with matching session_identifier,
    and may have additional RECORD_GENERATION logs.

    Parameters
    ----------
    session_identifier
        A unique string consistent among a single record's START, END,
        and RECORD_GENERATION events (often a UUID)
    instrument
        The instrument associated with this session (foreign key reference
        to instruments table)
    timestamp
        The datetime representing when the event occurred
    event_type
        The type of log (START, END, or RECORD_GENERATION)
    user
        The username associated with this session (if known)
    record_status
        The status for this record (defaults to WAITING_FOR_END)
    """

    __tablename__ = "session_log"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('START', 'END', 'RECORD_GENERATION')",
            name="check_event_type",
        ),
        CheckConstraint(
            "record_status IN ('COMPLETED', 'WAITING_FOR_END', 'TO_BE_BUILT', "
            "'BUILT_NOT_EXPORTED', 'ERROR', 'NO_FILES_FOUND', 'NO_CONSENT', "
            "'NO_RESERVATION')",
            name="check_record_status",
        ),
    )

    # Primary key
    id_session_log: int | None = Field(default=None, primary_key=True)

    # Required fields
    session_identifier: str = Field(max_length=36, index=True)
    instrument: str = Field(foreign_key="instruments.instrument_pid", max_length=100)
    timestamp: datetime.datetime = Field(
        sa_column=Column(TZDateTime)
    )  # Preserve timezone
    event_type: EventType  # Enum for type safety
    record_status: RecordStatus = Field(default=RecordStatus.WAITING_FOR_END)

    # Optional field
    user: str | None = Field(default=None, max_length=50)

    # Relationships
    instrument_obj: Instrument | None = Relationship(back_populates="session_logs")

    def __repr__(self):
        """Return custom representation of a SessionLog."""
        return (
            f"SessionLog (id={self.session_identifier}, "
            f"instrument={self.instrument}, "
            f"timestamp={self.timestamp}, "
            f"event_type={self.event_type.value}, "
            f"user={self.user}, "
            f"record_status={self.record_status.value})"
        )

    def insert_log(self) -> bool:
        """
        Insert this log into the NexusLIMS database.

        Inserts a log into the database with the information contained within
        this SessionLog's attributes (used primarily for NEMO ``usage_event``
        integration). It will check for the presence of a matching record first
        and warn without inserting anything if it finds one.

        Returns
        -------
        success : bool
            Whether or not the session log row was inserted successfully
        """
        with DBSession(get_engine()) as session:
            # Check for existing log
            statement = select(SessionLog).where(
                SessionLog.session_identifier == self.session_identifier,
                SessionLog.instrument == self.instrument,
                SessionLog.timestamp == self.timestamp,
                SessionLog.event_type == self.event_type,
            )
            existing = session.exec(statement).first()

            if existing:
                _logger.warning("SessionLog already exists: %s", self)
                return True

            # Insert new log
            session.add(self)
            session.commit()
            return True


class UploadLog(SQLModel, table=True):
    """
    Log of export attempts to destination repositories.

    Tracks per-destination export results for each session, enabling
    multi-destination export with granular success/failure tracking.

    Parameters
    ----------
    id
        Auto-incrementing primary key
    session_identifier
        Foreign key reference to session_log.session_identifier
    destination_name
        Name of the export destination (e.g., "cdcs", "labarchives")
    success
        Whether the export succeeded
    record_id
        Destination-specific record identifier (if successful)
    record_url
        Direct URL to view the exported record (if successful)
    error_message
        Error message if export failed
    timestamp
        When the export attempt occurred
    metadata_json
        JSON-serialized metadata dict with destination-specific details
    """

    __tablename__ = "upload_log"

    # Primary key
    id: int | None = Field(default=None, primary_key=True)

    # Required fields
    session_identifier: str = Field(index=True, max_length=36)
    destination_name: str = Field(index=True, max_length=100)
    success: bool
    timestamp: datetime.datetime = Field(sa_column=Column(TZDateTime))

    # Optional fields
    record_id: str | None = Field(default=None, max_length=255)
    record_url: str | None = Field(default=None, max_length=500)
    error_message: str | None = Field(default=None)
    metadata_json: str | None = Field(default=None)

    def __repr__(self):
        """Return custom representation of an UploadLog."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"UploadLog (session={self.session_identifier}, "
            f"destination={self.destination_name}, "
            f"status={status}, "
            f"timestamp={self.timestamp})"
        )


class ExternalUserIdentifier(SQLModel, table=True):
    """
    Maps NexusLIMS usernames to external system user IDs.

    Maintains a star topology with nexuslims_username (from session_log.user)
    as the canonical identifier, mapping to external system IDs.

    Parameters
    ----------
    id
        Auto-incrementing primary key
    nexuslims_username
        Canonical username in NexusLIMS (from session_log.user)
    external_system
        External system identifier (nemo, labarchives_eln, etc.)
    external_id
        User ID/username in the external system
    email
        User's email for verification/matching (optional)
    created_at
        When this mapping was created
    last_verified_at
        Last time this mapping was verified (optional)
    notes
        Additional notes about this mapping (optional)

    Examples
    --------
    >>> # NEMO harvester user ID
    >>> ExternalUserIdentifier(
    ...     nexuslims_username='jsmith',
    ...     external_system=ExternalSystem.NEMO,
    ...     external_id='12345'
    ... )

    >>> # LabArchives UID from OAuth
    >>> ExternalUserIdentifier(
    ...     nexuslims_username='jsmith',
    ...     external_system=ExternalSystem.LABARCHIVES_ELN,
    ...     external_id='285489257Ho...',
    ...     email='jsmith@upenn.edu'
    ... )
    """

    __tablename__ = "external_user_identifiers"
    __table_args__ = (
        # NOTE: This CHECK constraint is dynamically generated from ExternalSystem enum
        # to keep the model in sync with the enum. However, migrations should hardcode
        # the values to preserve historical accuracy. When adding a new system, create
        # a new migration to update the CHECK constraint.
        CheckConstraint(
            f"external_system IN ({', '.join(repr(s.value) for s in ExternalSystem)})",
            name="valid_external_system",
        ),
        # UNIQUE constraints to enforce star-topology design
        UniqueConstraint(
            "nexuslims_username",
            "external_system",
            name="nexuslims_username_system_UNIQUE",
        ),
        UniqueConstraint(
            "external_system", "external_id", name="system_external_id_UNIQUE"
        ),
    )

    # Primary key
    id: int | None = Field(default=None, primary_key=True)

    # Required fields
    nexuslims_username: str = Field(index=True)
    external_system: str = Field()
    external_id: str = Field()

    # Optional fields
    email: str | None = Field(default=None)
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(pytz.UTC),
        sa_column=Column(TZDateTime),
    )
    last_verified_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(TZDateTime, nullable=True)
    )
    notes: str | None = Field(default=None)

    def __repr__(self):
        """Return custom representation of an ExternalUserIdentifier."""
        return (
            f"ExternalUserIdentifier (username={self.nexuslims_username}, "
            f"system={self.external_system}, "
            f"external_id={self.external_id})"
        )


def get_external_id(
    nexuslims_username: str, external_system: ExternalSystem
) -> str | None:
    """
    Get external system ID for a NexusLIMS user.

    Parameters
    ----------
    nexuslims_username
        Username from session_log.user
    external_system
        Target external system

    Returns
    -------
    str | None
        External ID if found, None otherwise

    Examples
    --------
    >>> from nexusLIMS.db.models import get_external_id
    >>> from nexusLIMS.db.enums import ExternalSystem
    >>> uid = get_external_id('jsmith', ExternalSystem.LABARCHIVES_ELN)
    >>> print(uid)
    '285489257Ho...'
    """
    with DBSession(get_engine()) as session:
        result = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username,
                ExternalUserIdentifier.external_system == external_system.value,
            )
        ).first()
        return result.external_id if result else None


def get_nexuslims_username(
    external_id: str, external_system: ExternalSystem
) -> str | None:
    """
    Reverse lookup: find NexusLIMS username from external ID.

    Useful for harvesters that receive external IDs (e.g., NEMO user IDs)
    and need to map them to NexusLIMS usernames for session_log entries.

    Parameters
    ----------
    external_id
        ID in external system
    external_system
        Source external system

    Returns
    -------
    str | None
        NexusLIMS username if found, None otherwise

    Examples
    --------
    >>> from nexusLIMS.db.models import get_nexuslims_username
    >>> from nexusLIMS.db.enums import ExternalSystem
    >>> username = get_nexuslims_username('12345', ExternalSystem.NEMO)
    >>> print(username)
    'jsmith'
    """
    with DBSession(get_engine()) as session:
        result = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.external_id == external_id,
                ExternalUserIdentifier.external_system == external_system.value,
            )
        ).first()
        return result.nexuslims_username if result else None


def store_external_id(
    nexuslims_username: str,
    external_system: ExternalSystem,
    external_id: str,
    email: str | None = None,
    notes: str | None = None,
) -> ExternalUserIdentifier:
    """
    Store or update external ID mapping.

    If mapping exists for this user/system combination, updates it and
    refreshes last_verified_at. Otherwise, creates new mapping.

    Parameters
    ----------
    nexuslims_username
        Username from session_log.user
    external_system
        Target external system
    external_id
        ID in external system
    email
        Optional email for verification
    notes
        Optional notes about this mapping

    Returns
    -------
    ExternalUserIdentifier
        Created or updated ExternalUserIdentifier record

    Examples
    --------
    >>> from nexusLIMS.db.models import store_external_id
    >>> from nexusLIMS.db.enums import ExternalSystem
    >>> record = store_external_id(
    ...     nexuslims_username='jsmith',
    ...     external_system=ExternalSystem.LABARCHIVES_ELN,
    ...     external_id='285489257Ho...',
    ...     email='jsmith@upenn.edu',
    ...     notes='OAuth registration portal 2026-01-25'
    ... )
    """
    with DBSession(get_engine()) as session:
        # Check if mapping exists
        existing = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username,
                ExternalUserIdentifier.external_system == external_system.value,
            )
        ).first()

        if existing:
            # Update existing
            existing.external_id = external_id
            if email:
                existing.email = email
            if notes:
                existing.notes = notes
            existing.last_verified_at = datetime.datetime.now(pytz.UTC)
            session.add(existing)
        else:
            # Create new
            existing = ExternalUserIdentifier(
                nexuslims_username=nexuslims_username,
                external_system=external_system.value,
                external_id=external_id,
                email=email,
                notes=notes,
            )
            session.add(existing)

        session.commit()
        session.refresh(existing)
        return existing


def get_all_external_ids(nexuslims_username: str) -> dict[str, str]:
    """
    Get all external IDs for a user.

    Returns dict mapping external system name to external ID.
    Useful for debugging or user profile displays.

    Parameters
    ----------
    nexuslims_username
        Username from session_log.user

    Returns
    -------
    dict[str, str]
        Dict mapping external system name to external ID

    Examples
    --------
    >>> from nexusLIMS.db.models import get_all_external_ids
    >>> ids = get_all_external_ids('jsmith')
    >>> print(ids)
    {
        'nemo': '12345',
        'labarchives_eln': '285489257Ho...',
        'cdcs': 'jsmith@upenn.edu'
    }
    """
    with DBSession(get_engine()) as session:
        results = session.exec(
            select(ExternalUserIdentifier).where(
                ExternalUserIdentifier.nexuslims_username == nexuslims_username
            )
        ).all()
        return {r.external_system: r.external_id for r in results}
