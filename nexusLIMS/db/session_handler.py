"""Classes and methods to interact with sessions from the NexusLIMS database."""

import contextlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime as dt
from typing import List, Tuple

from nexusLIMS.config import settings
from nexusLIMS.instruments import Instrument, instrument_db
from nexusLIMS.utils import current_system_tz

logger = logging.getLogger(__name__)


def db_query(query, args=None):
    """Make a query on the NexusLIMS database."""
    if args is None:
        args = ()
    success = False
    with (
        contextlib.closing(
            sqlite3.connect(str(settings.NX_DB_PATH)),
        ) as conn,
        conn,
        contextlib.closing(conn.cursor()) as cursor,
    ):  # auto-commits
        results = cursor.execute(query, args).fetchall()
        success = True
    return success, results


@dataclass
class SessionLog:
    """
    A log of the start or end of a Session.

    A simple mapping of one row in the ``session_log`` table of the NexusLIMS
    database (all values are strings).

    Parameters
    ----------
    session_identifier
         A unique string that is consistent among a single
         record's `"START"`, `"END"`, and `"RECORD_GENERATION"` events (often a
         UUID, but is not required to be so)
    instrument
        The instrument associated with this session (foreign key reference to
        the ``instruments`` table)
    timestamp
        The ISO format timestamp representing the date and time of the logged
        event
    event_type
        The type of log for this session (either `"START"`, `"END"`,
        or `"RECORD_GENERATION"`)
    user
        The username associated with this session (if known)
    record_status
        The status to use for this record (defaults to ``'TO_BE_BUILT'``)
    """

    session_identifier: str
    instrument: str
    timestamp: str
    event_type: str
    user: str
    record_status: str = "TO_BE_BUILT"

    def __repr__(self):
        """Return custom representation of a SessionLog."""
        return (
            f"SessionLog (id={self.session_identifier}, "
            f"instrument={self.instrument}, "
            f"timestamp={self.timestamp}, "
            f"event_type={self.event_type}, "
            f"user={self.user}, "
            f"record_status={self.record_status})"
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
        query = (
            "SELECT * FROM session_log "
            "WHERE session_identifier=? AND "
            "instrument=? AND "
            "timestamp=? AND "
            "event_type=? AND "
            "record_status=? AND "
            "user=?"
        )
        args = (
            self.session_identifier,
            self.instrument,
            self.timestamp,
            self.event_type,
            self.record_status,
            self.user,
        )

        success, results = db_query(query, args)
        if results:
            # There was a matching record in the DB, so warn and return success
            logger.warning(
                "SessionLog already existed in DB, so no row was added: %s",
                self,
            )
            return success

        query = (
            "INSERT INTO session_log(session_identifier, instrument, "
            "timestamp, event_type, record_status, user) VALUES "
            "(?, ?, ?, ?, ?, ?)"
        )
        success, results = db_query(query, args)

        return success


class Session:
    """
    A representation of a session in the NexusLIMS database.

    A record of an individual session as read from the Nexus Microscopy
    facility session database. Created by combining two
    :py:class:`~nexusLIMS.db.session_handler.SessionLog` objects with status
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

    def update_session_status(self, status):
        """
        Update the status of this Session in the NexusLIMS database.

        Specifically, update the ``record_status`` in any session logs for this
        :py:class:`~nexusLIMS.db.session_handler.Session`.

        Parameters
        ----------
        status : str
            One of ``"COMPLETED"``, ``"WAITING_FOR_END"``, ``"TO_BE_BUILT"``,
            ``"ERROR"``, ``"NO_FILES_FOUND"``, ``"NO_CONSENT"``, or ``"NO_RESERVATION"``
            (the allowed values in the NexusLIMS database). Status value will be
            validated by a check constraint in the database

        Returns
        -------
        success : bool
            Whether the update operation was successful
        """
        update_query = (
            "UPDATE session_log SET record_status = ? WHERE session_identifier = ?"
        )

        # use contextlib to auto-close the connection and database cursors
        with (
            contextlib.closing(
                sqlite3.connect(str(settings.NX_DB_PATH)),
            ) as conn,
            conn,
            contextlib.closing(conn.cursor()) as cursor,
        ):  # auto-commits
            _ = cursor.execute(update_query, (status, self.session_identifier))
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
            A dictionary containing the results from the query to check that
            a RECORD_GENERATION event was added
        """
        logger.debug("Logging RECORD_GENERATION for %s", self.session_identifier)
        insert_query = (
            "INSERT INTO session_log "
            "(instrument, event_type, session_identifier, "
            "user, timestamp) VALUES (?, ?, ?, ?, ?)"
        )
        args = (
            self.instrument.name,
            "RECORD_GENERATION",
            self.session_identifier,
            settings.NX_CDCS_USER,
            dt.now(tz=current_system_tz()),
        )

        # use contextlib to auto-close the connection and database cursors
        with (
            contextlib.closing(
                sqlite3.connect(str(settings.NX_DB_PATH)),
            ) as conn,
            conn,
            contextlib.closing(conn.cursor()) as cursor,
        ):  # auto-commits
            results = cursor.execute(insert_query, args)

        check_query = (
            "SELECT id_session_log, event_type, "
            "session_identifier, timestamp FROM session_log "
            "WHERE instrument = ?"
            "AND event_type = ?"
            "ORDER BY timestamp DESC LIMIT 1"
        )
        args = (self.instrument.name, "RECORD_GENERATION")

        # use contextlib to auto-close the connection and database cursors
        with (
            contextlib.closing(
                sqlite3.connect(str(settings.NX_DB_PATH)),
            ) as conn,
            conn,
        ):  # auto-commits
            conn.row_factory = sqlite3.Row
            with contextlib.closing(conn.cursor()) as cursor:
                results = cursor.execute(check_query, args)
                res = results.fetchone()

        event_match = res["event_type"] == "RECORD_GENERATION"
        id_match = res["session_identifier"] == self.session_identifier
        if event_match and id_match:
            logger.debug(
                "Confirmed RECORD_GENERATION insertion for %s",
                self.session_identifier,
            )

        return dict(res)


def get_sessions_to_build() -> List[Session]:
    """
    Get list of sessions that need to be built from the NexusLIMS database.

    Query the NexusLIMS database for pairs of logs with status
    ``'TO_BE_BUILT'`` and return the information needed to build a record for
    that session.

    Returns
    -------
    sessions : List[Session]
        A list of :py:class:`~nexusLIMS.db.session_handler.Session` objects
        containing the sessions that the need their record built. Will be an
        empty list if there's nothing to do.
    """
    sessions = []

    query_string = (
        "SELECT session_identifier, instrument, timestamp, "
        "event_type, user "
        "FROM session_log WHERE record_status == 'TO_BE_BUILT'"
    )

    # use contextlib to auto-close the connection and database cursors
    with (
        contextlib.closing(
            sqlite3.connect(str(settings.NX_DB_PATH)),
        ) as conn,
        conn,
        contextlib.closing(conn.cursor()) as cursor,
    ):  # auto-commits
        results = cursor.execute(query_string).fetchall()

    session_logs = [SessionLog(*i) for i in results]
    start_logs = [sl for sl in session_logs if sl.event_type == "START"]
    end_logs = [sl for sl in session_logs if sl.event_type == "END"]

    for start_l in start_logs:
        # for every log that has a 'START', there should be one corresponding
        # log with 'END' that has the same session identifier. If not,
        # the database is in an inconsistent state and we should know about it
        el_list = [
            el for el in end_logs if el.session_identifier == start_l.session_identifier
        ]
        if len(el_list) != 1:
            msg = (
                "There was not exactly one 'END' log for this 'START' log; "
                f"len(el_list) was {len(el_list)}; sl was {start_l}; el_list "
                f"was {el_list}"
            )
            raise ValueError(msg)

        end_l = el_list[0]
        dt_from = dt.fromisoformat(start_l.timestamp)
        dt_to = dt.fromisoformat(end_l.timestamp)
        session = Session(
            session_identifier=start_l.session_identifier,
            instrument=instrument_db[start_l.instrument],
            dt_range=(dt_from, dt_to),
            user=start_l.user,
        )
        sessions.append(session)

    logger.info("Found %i new sessions to build", len(sessions))
    return sessions
