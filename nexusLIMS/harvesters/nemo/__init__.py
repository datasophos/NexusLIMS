"""
NEMO harvester module.

This module contains the functionality to harvest instruments, reservations,
etc. from an instance of NEMO (https://github.com/usnistgov/NEMO/), a
calendering and laboratory logistics application.
"""

import json
import logging
from datetime import timedelta

from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.reservation_event import ReservationEvent
from nexusLIMS.utils import get_timespan_overlap

from .connector import NemoConnector
from .exceptions import NoDataConsentError, NoMatchingReservationError
from .utils import (
    _get_res_question_value,
    get_connector_for_session,
    has_valid_question_data,
    id_from_url,
    process_res_question_samples,
)

_logger = logging.getLogger(__name__)


def create_res_event_from_usage_event(
    usage_event: dict,
    session: Session,
    nemo_connector: NemoConnector,
    field: str = "run_data",
) -> ReservationEvent:
    """
    Create ReservationEvent from usage event with question data.

    Assumes usage_event has been expanded via _parse_event() and
    has valid question data in the specified field (run_data or pre_run_data).

    Both run_data and pre_run_data fields are JSON-encoded strings that use
    the same structure as reservation question_data, so we can parse them and
    reuse existing helper functions by creating a wrapper dict.

    Parameters
    ----------
    usage_event
        The usage event dictionary from NEMO API
    session
        The Session object
    nemo_connector
        The NemoConnector instance
    field
        Which field to extract question data from ("run_data" or "pre_run_data")

    Returns
    -------
    ReservationEvent
        The created reservation event

    Raises
    ------
    ValueError
        If the field cannot be parsed as JSON
    NoDataConsentError
        If data_consent is missing or the user declined consent
    """
    # Parse JSON-encoded question data string
    try:
        question_data_parsed = json.loads(usage_event[field])
    except (json.JSONDecodeError, TypeError) as e:
        msg = f"Failed to parse {field} for usage event {usage_event['id']}: {e}"
        raise ValueError(msg) from e

    # Wrap parsed data as question_data for compatibility with helper functions
    wrapped_event = {"question_data": question_data_parsed}

    # Validate consent first
    consent = _get_res_question_value("data_consent", wrapped_event)
    if consent is None:
        msg = (
            f"Usage event {usage_event['id']} did not have data_consent defined, "
            "so we should not harvest its data"
        )
        raise NoDataConsentError(msg)

    if consent.lower() in ["disagree", "no", "false", "negative"]:
        msg = (
            f"Usage event {usage_event['id']} requested not to have "
            "their data harvested"
        )
        raise NoDataConsentError(msg)

    # Process sample information
    (
        sample_details,
        sample_pid,
        sample_name,
        sample_elements,
    ) = process_res_question_samples(wrapped_event)

    # Use operator as creator (who started the session)
    # Fallback to user if operator is None
    creator = usage_event.get("operator") or usage_event["user"]

    # Create ReservationEvent (using wrapped_event for question data)
    return ReservationEvent(
        experiment_title=_get_res_question_value("experiment_title", wrapped_event),
        instrument=session.instrument,
        last_updated=nemo_connector.strptime(usage_event["start"]),  # No creation_time
        username=usage_event["user"]["username"],
        user_full_name=(
            f"{usage_event['user']['first_name']} "
            f"{usage_event['user']['last_name']} "
            f"({usage_event['user']['username']})"
        ),
        created_by=creator["username"],
        created_by_full_name=(
            f"{creator['first_name']} {creator['last_name']} ({creator['username']})"
        ),
        start_time=nemo_connector.strptime(usage_event["start"]),
        end_time=nemo_connector.strptime(usage_event["end"]),
        reservation_type=None,
        experiment_purpose=_get_res_question_value("experiment_purpose", wrapped_event),
        sample_details=sample_details,
        sample_pid=sample_pid,
        sample_name=sample_name,
        sample_elements=sample_elements,
        project_name=[None],
        project_id=[_get_res_question_value("project_id", wrapped_event)],
        project_ref=[None],
        internal_id=str(usage_event["id"]),  # Usage event ID
        division=None,
        group=None,
        url=nemo_connector.config["base_url"].replace(
            "api/",
            f"event_details/usage/{usage_event['id']}/",  # Usage event URL
        ),
    )


def res_event_from_session(
    session: Session, connector: NemoConnector | None = None
) -> ReservationEvent:
    """
    Create reservation event from session.

    Create an internal
    :py:class:`~nexusLIMS.harvesters.reservation_event.ReservationEvent` representation
    of a session by finding a matching reservation in the NEMO
    system and parsing the data contained within into a ``ReservationEvent``.

    This method assumes a certain format for the "reservation questions"
    associated with each reservation and parses that information into the resulting
    ``ReservationEvent``. The most critical of these is the ``data_consent`` field.
    If an affirmative response in this field is not found (because the user declined
    consent or the reservation questions are missing), a record will not be built.

    The following JSON object represents a minimal schema for a set of NEMO "Reservation
    Questions" that will satisfy the expectations of this method. Please see the
    NEMO documentation on this feature for more details.

    ```json
    [
      {
        "type": "textbox",
        "name": "project_id",
        "title": "Project ID",
      },
      {
        "type": "textbox",
        "name": "experiment_title",
        "title": "Title of Experiment",
      },
      {
        "type": "textarea",
        "name": "experiment_purpose",
        "title": "Experiment Purpose",
      },
      {
        "type": "radio",
        "title": "Agree to NexusLIMS curation",
        "choices": ["Agree", "Disagree"],
        "name": "data_consent",
        "default_choice": "Agree"
      },
      {
        "type": "group",
        "title": "Sample information",
        "name": "sample_group",
        "questions": [
          {
            "type": "textbox",
            "name": "sample_name",
            "title": "Sample Name / PID",
          },
          {
            "type": "radio",
            "title": "Sample or PID?",
            "choices": ["Sample Name", "PID"],
            "name": "sample_or_pid",
          },
          {
            "type": "textarea",
            "name": "sample_details",
            "title": "Sample Details",
          }
        ]
      }
    ]
    ```

    Parameters
    ----------
    session
        The session for which to get a reservation event
    connector : Optional[NemoConnector], optional
        Optional NemoConnector to use instead of looking one up. Useful for testing.

    Returns
    -------
    res_event : ~nexusLIMS.harvesters.reservation_event.ReservationEvent
        The matching reservation event
    """
    # a session has instrument, dt_from, dt_to, and user

    # we should fetch all reservations +/- two days, and then find the one
    # with the maximal overlap with the session time range
    # probably don't want to filter by user for now, since sometimes users
    # will enable/reserve on behalf of others, etc.

    # in order to get reservations, we need a NemoConnector
    if connector is None:
        nemo_connector = get_connector_for_session(session)
    else:
        nemo_connector = connector

    # NEW: Three-tier fallback - try to get usage event question data first
    # This eliminates the need for reservation matching when usage events
    # contain all necessary metadata (run_data filled at END of experiment,
    # or pre_run_data filled at START of experiment)
    usage_event_id = id_from_url(session.session_identifier)
    if usage_event_id is not None:
        usage_events = nemo_connector.get_usage_events(event_id=usage_event_id)
        if usage_events and len(usage_events) > 0:
            usage_event = usage_events[0]

            # Priority 1: Check run_data (most recent - filled at END)
            if has_valid_question_data(usage_event, field="run_data"):
                _logger.info(
                    "Usage event %s has run_data with questions, "
                    "using it instead of reservation",
                    usage_event_id,
                )
                return create_res_event_from_usage_event(
                    usage_event, session, nemo_connector, field="run_data"
                )

            # Priority 2: Check pre_run_data (backup - filled at START)
            if has_valid_question_data(usage_event, field="pre_run_data"):
                _logger.info(
                    "Usage event %s has pre_run_data with questions, "
                    "using it instead of reservation",
                    usage_event_id,
                )
                return create_res_event_from_usage_event(
                    usage_event, session, nemo_connector, field="pre_run_data"
                )

    # Priority 3: Fall back to reservation matching (existing behavior)
    _logger.info(
        "Usage event does not have valid question data in run_data or pre_run_data, "
        "falling back to reservation matching"
    )

    # get reservation with maximum overlap
    reservations = nemo_connector.get_reservations(
        # tool id can be extracted from instrument api_url query parameter
        tool_id=id_from_url(session.instrument.api_url),
        dt_from=session.dt_from - timedelta(days=2),
        dt_to=session.dt_to + timedelta(days=2),
    )

    _logger.info(
        "Found %i reservations between %s and %s with ids: %s",
        len(reservations),
        session.dt_from - timedelta(days=2),
        session.dt_to + timedelta(days=2),
        [i["id"] for i in reservations],
    )
    for i, res in enumerate(reservations):
        _logger.debug(
            "Reservation %i: %sreservations/?id=%s from %s to %s",
            i + 1,
            nemo_connector.config["base_url"],
            res["id"],
            res["start"],
            res["end"],
        )

    starts = [nemo_connector.strptime(r["start"]) for r in reservations]
    ends = [nemo_connector.strptime(r["end"]) for r in reservations]

    overlaps = [
        get_timespan_overlap((session.dt_from, session.dt_to), (s, e))
        for s, e in zip(starts, ends)
    ]

    #   handle if there are no matching sessions (i.e. reservations is an empty list
    #   also need to handle if there is no overlap at all with any reservation
    if len(reservations) == 0 or max(overlaps) == timedelta(0):
        # there were no reservations that matched this usage event time range,
        # or none of the reservations overlapped with the usage event
        # so we'll use what limited information we have from the usage event
        # session
        _logger.warning(
            "No reservations found with overlap for this usage "
            "event, so raising NoDataConsentError",
        )
        msg = (
            "No reservation found matching this session, so assuming NexusLIMS "
            "does not have user consent for data harvesting."
        )
        raise NoMatchingReservationError(msg)

    # select the reservation with the most overlap
    res = reservations[overlaps.index(max(overlaps))]
    _logger.info(
        "Using reservation %sreservations/?id=%s as match for "
        "usage event %s with overlap of %s",
        nemo_connector.config["base_url"],
        res["id"],
        session.session_identifier,
        max(overlaps),
    )

    # DONE: check for presence of sample_group in the reservation metadata
    #  and change the harvester to process the sample group metadata by
    #  providing lists to the ReservationEvent constructor
    (
        sample_details,
        sample_pid,
        sample_name,
        sample_elements,
    ) = process_res_question_samples(res)

    # DONE: respect user choice not to harvest data (data_consent)
    consent = "disagree"
    consent = _get_res_question_value("data_consent", res)
    # consent will be None here if it wasn't given (i.e. there was no
    # data_consent field in the reservation questions)
    if consent is None:
        msg = (
            f"Reservation {res['id']} did not have data_consent defined, "
            "so we should not harvest its data"
        )
        raise NoDataConsentError(msg)

    if consent.lower() in ["disagree", "no", "false", "negative"]:
        msg = f"Reservation {res['id']} requested not to have their data harvested"
        raise NoDataConsentError(msg)

    # Create ReservationEvent from NEMO reservation dict
    return ReservationEvent(
        experiment_title=_get_res_question_value("experiment_title", res),
        instrument=session.instrument,
        last_updated=nemo_connector.strptime(res["creation_time"]),
        username=res["user"]["username"],
        user_full_name=(
            f"{res['user']['first_name']} "
            f"{res['user']['last_name']} "
            f"({res['user']['username']})"
        ),
        created_by=res["creator"]["username"],
        created_by_full_name=(
            f"{res['creator']['first_name']} "
            f"{res['creator']['last_name']} "
            f"({res['creator']['username']})"
        ),
        start_time=nemo_connector.strptime(res["start"]),
        end_time=nemo_connector.strptime(res["end"]),
        reservation_type=None,  # reservation type is not collected in NEMO
        experiment_purpose=_get_res_question_value("experiment_purpose", res),
        sample_details=sample_details,
        sample_pid=sample_pid,
        sample_name=sample_name,
        sample_elements=sample_elements,
        project_name=[None],
        project_id=[_get_res_question_value("project_id", res)],
        project_ref=[None],
        internal_id=str(res["id"]),
        division=None,
        group=None,
        url=nemo_connector.config["base_url"].replace(
            "api/",
            f"event_details/reservation/{res['id']}/",
        ),
    )
