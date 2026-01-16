"""Classes and methods to interact with sessions from the NexusLIMS database."""

import logging
from datetime import datetime as dt
from typing import Tuple

from sqlalchemy.orm import selectinload
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import Instrument, SessionLog
from nexusLIMS.utils import current_system_tz

_logger = logging.getLogger(__name__)


class Session:
    """
    A representation of a session in the NexusLIMS database.

    A record of an individual session as read from the Nexus Microscopy
    facility session database. Created by combining two
    :py:class:`~nexusLIMS.db.models.SessionLog` objects with status
    ``"TO_BE_BUILT"``.

    Parameters
    ----------
    session_identifier
        The unique identifier for an individual session on an instrument
    instrument
        An object representing the instrument associated with this session
    dt_range
        A tuple of two :py:class:`~datetime.datetime` objects representing the start
        and end of this session )in that order
    user : str
        The username associated with this session (may not be trustworthy)
    """

    def __init__(
        self,
        session_identifier: str,
        instrument: Instrument,
        dt_range: Tuple[dt, dt],
        user: str,
    ):
        self.session_identifier = session_identifier
        self.instrument = instrument
        self.dt_from, self.dt_to = dt_range
        self.user = user

    def __repr__(self):
        """Return custom representation of a Session."""
        return (
            f"{self.dt_from.isoformat()} to {self.dt_to.isoformat()} on "
            f"{self.instrument.name}"
        )

    def update_session_status(self, status: RecordStatus):
        """
        Update the status of this Session in the NexusLIMS database.

        Specifically, update the ``record_status`` in any session logs for this
        :py:class:`~nexusLIMS.db.session_handler.Session`.

        Parameters
        ----------
        status : RecordStatus
            The new status for this session (type-safe enum value)

        Returns
        -------
        success : bool
            Whether the update operation was successful
        """
        with DBSession(get_engine()) as session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == self.session_identifier
            )
            logs = session.exec(statement).all()
            for log in logs:
                log.record_status = status
            session.commit()
            return True

    def insert_record_generation_event(self) -> dict:
        """
        Insert record generation event to session log.

        Insert a log for this session into the session database with
        ``event_type`` `"RECORD_GENERATION"` and the current time (with local
        system timezone) as the timestamp.

        Returns
        -------
        res : dict
            A dictionary containing the inserted log information
        """
        _logger.debug("Logging RECORD_GENERATION for %s", self.session_identifier)

        log = SessionLog(
            session_identifier=self.session_identifier,
            instrument=self.instrument.instrument_pid,
            timestamp=dt.now(tz=current_system_tz()),
            event_type=EventType.RECORD_GENERATION,
            user="nexuslims",
            record_status=RecordStatus.WAITING_FOR_END,
        )

        with DBSession(get_engine()) as session:
            session.add(log)
            session.commit()
            session.refresh(log)

        _logger.debug(
            "Confirmed RECORD_GENERATION insertion for %s",
            self.session_identifier,
        )

        return {
            "id_session_log": log.id_session_log,
            "event_type": log.event_type.value,
            "session_identifier": log.session_identifier,
            "timestamp": log.timestamp,
        }


def get_sessions_to_build() -> list[Session]:
    """
    Get list of sessions that need to be built from the NexusLIMS database.

    Query the NexusLIMS database for pairs of logs with status
    ``TO_BE_BUILT`` and return the information needed to build a record for
    that session.

    Returns
    -------
    sessions : list[Session]
        A list of :py:class:`~nexusLIMS.db.session_handler.Session` objects
        containing the sessions that need their record built. Will be an
        empty list if there's nothing to do.
    """
    sessions = []

    with DBSession(get_engine()) as db_session:
        # Query for all TO_BE_BUILT logs with eager loading of instrument relationship
        statement = (
            select(SessionLog)
            .where(SessionLog.record_status == RecordStatus.TO_BE_BUILT)
            .options(selectinload(SessionLog.instrument_obj))
        )
        session_logs = db_session.exec(statement).all()

        # Separate START and END logs
        start_logs = [sl for sl in session_logs if sl.event_type == EventType.START]
        end_logs = [sl for sl in session_logs if sl.event_type == EventType.END]

        for start_l in start_logs:
            # for every log that has a 'START', there should be one corresponding
            # log with 'END' that has the same session identifier. If not,
            # the database is in an inconsistent state and we should know about it
            el_list = [
                el
                for el in end_logs
                if el.session_identifier == start_l.session_identifier
            ]
            if len(el_list) != 1:
                msg = (
                    "There was not exactly one 'END' log for this 'START' log; "
                    f"len(el_list) was {len(el_list)}; sl was {start_l}; el_list "
                    f"was {el_list}"
                )
                raise ValueError(msg)

            end_l = el_list[0]
            # Use relationship to get Instrument object (eagerly loaded above)
            session = Session(
                session_identifier=start_l.session_identifier,
                instrument=start_l.instrument_obj,  # Relationship navigation!
                dt_range=(start_l.timestamp, end_l.timestamp),  # No fromisoformat()!
                user=start_l.user,
            )
            sessions.append(session)

    _logger.info("Found %i new sessions to build", len(sessions))
    return sessions


def get_all_session_logs() -> list[SessionLog]:
    """
    Fetch all session logs from the database and return SessionLogs.

    Returns
    -------
    session_logs : list[SessionLog]
        A list of all SessionLog objects from the database, ordered by timestamp.
        Will be an empty list if there are no session logs.
    """
    with DBSession(get_engine()) as db_session:
        # Query for all session logs, ordered by timestamp
        statement = select(SessionLog).order_by(SessionLog.timestamp)
        session_logs = list(db_session.exec(statement).all())

    _logger.info("Found %i session logs in database", len(session_logs))
    return session_logs
