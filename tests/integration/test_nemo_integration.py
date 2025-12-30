# ruff: noqa: DTZ005
"""
Integration tests for NEMO harvester.

These tests verify that the NEMO harvester can correctly interact with a
real NEMO instance to fetch reservations, usage events, and other data.

These tests require Docker services to be running (NEMO, PostgreSQL, Redis).
They are designed to test actual external API interactions, not internal logic.
"""

import logging
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
import requests

from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.nemo import (
    get_connector_for_session,
    res_event_from_session,
)
from nexusLIMS.harvesters.nemo.connector import NemoConnector
from nexusLIMS.harvesters.nemo.exceptions import (
    NoDataConsentError,
    NoMatchingReservationError,
)
from nexusLIMS.harvesters.nemo.utils import (
    add_all_usage_events_to_db,
    get_connector_by_base_url,
    get_harvesters_enabled,
)
from tests.integration.conftest import NEMO_URL

logger = logging.getLogger(__name__)


def _create_session_from_iso_timestamps(  # noqa: PLR0913
    session_identifier: str,
    instrument_pid: str,
    start_iso: str,
    end_iso: str,
    user: str = "testuser",
    instrument_db=None,
) -> Session:
    """Create a Session object from ISO format timestamps and instrument PID.

    Args:
        session_identifier: Unique identifier for the session
        instrument_pid: Instrument PID to look up in the database
        start_iso: Start time as ISO format string
        end_iso: End time as ISO format string
        user: User associated with the session
        instrument_db: Instrument database to look up the instrument

    Returns
    -------
        Session object with the specified parameters
    """
    # Get the instrument from the database
    instrument = instrument_db.get(instrument_pid, None)
    if instrument is None:
        error_msg = f"Instrument with PID {instrument_pid} not found in database"
        raise ValueError(error_msg)

    # Parse ISO timestamps to datetime objects
    session_start = datetime.fromisoformat(start_iso)
    session_end = datetime.fromisoformat(end_iso)

    # Create and return the session
    return Session(
        session_identifier=session_identifier,
        instrument=instrument,
        dt_range=(session_start, session_end),
        user=user,
    )


@pytest.mark.integration
class TestNemoAPIConnectivity:
    """Test basic NEMO API connectivity and data fetching."""

    def test_nemo_service_is_accessible(self, nemo_url):
        """Test that NEMO service is accessible via HTTP."""
        response = requests.get(nemo_url, timeout=10)
        assert response.status_code == HTTPStatus.OK

    def test_nemo_api_is_accessible_with_auth(self, nemo_api_url, nemo_client):
        """Test that NEMO API endpoint is accessible."""
        # Try to access the API root with authentication
        headers = {"Authorization": f"Token {nemo_client['token']}"}
        response = requests.get(nemo_api_url, headers=headers, timeout=10)
        # NEMO API should return 200 with valid authentication
        assert response.status_code == HTTPStatus.OK

    def test_create_nemo_connector(self, nemo_connector: NemoConnector, nemo_client):
        """Test creating a NemoConnector instance."""
        assert nemo_connector is not None
        assert nemo_connector.config["base_url"] == nemo_client["url"]

    def test_get_users(self, nemo_connector: NemoConnector, mock_users_data):
        """Test fetching users from NEMO API."""
        # get_users with None returns all users
        users_from_connector = nemo_connector.get_users(user_id=None)
        assert isinstance(users_from_connector, list)
        assert len(users_from_connector) >= len(
            mock_users_data
        )  # Should have at least our test users

        # Check that expected users exist
        usernames_from_connector = [u["username"] for u in users_from_connector]
        expected_usernames = [u["username"] for u in mock_users_data]
        for expected_username in expected_usernames:
            assert expected_username in usernames_from_connector

    def test_get_tools(self, nemo_connector: NemoConnector, mock_tools_data):
        """Test fetching tools from NEMO API."""
        # Get a specific tool by ID
        tool_id = mock_tools_data[0]["id"]
        tools_from_connector = nemo_connector.get_tools(tool_id=tool_id)
        assert isinstance(tools_from_connector, list)
        assert len(tools_from_connector) >= 1  # Should have at least one tool
        # API should return the same tool_id
        assert tools_from_connector[0]["id"] == tool_id
        assert tools_from_connector[0]["name"] == "643 Titan (S)TEM (probe corrected)"

    def test_get_projects(self, nemo_connector: NemoConnector, mock_projects_data):
        """Test fetching projects from NEMO API."""
        # get_projects requires a proj_id parameter
        # Use an empty list to get all projects
        projects_from_connector = nemo_connector.get_projects(proj_id=[])
        assert isinstance(projects_from_connector, list)
        # Should have at least one project from seed data
        assert len(projects_from_connector) >= len(mock_projects_data)

        # Check that expected projects exist
        p_names_from_connector = [p["name"] for p in projects_from_connector]
        expected_project_names = [p["name"] for p in mock_projects_data]
        for expected_name in expected_project_names:
            assert expected_name in p_names_from_connector

    def test_get_reservations_with_date_range(self, nemo_connector: NemoConnector):
        """Test fetching reservations for a specific date range and tool.

        This test uses actual dates from seed_data.json to verify that
        the NEMO API correctly returns reservations within the specified range.

        Seed data contains reservations for tool_id=10 on:
        - 2021-08-02: 11:00-16:00 (with consent, experiment data) (id=187)
        - 2021-08-03: 10:00-17:00 (no question data) (id=188)
        - 2021-08-04: 10:00-17:00 (no consent) (id=191)
        - 2023-02-13:
            Multiple reservations at 10:00-11:00 (id=201), 11:00-12:00 (id=202),
                                     12:00-13:00 (id=203), 13:00-14:00 (id=200)
        - Cancelled reservations at:
            - 2021-08-06 10:00:00-06:00 (id=190)
            - 2021-08-05 11:00:00-06:00 (id=189)
        """
        tool_id = 10  # Test Tool from seed data

        # Test 1: Query for 2021-08-02 to 2021-08-04 - should get 3 reservations
        dt_from = datetime.fromisoformat("2021-08-02T00:00:00-06:00")
        dt_to = datetime.fromisoformat("2021-08-04T23:59:59-06:00")

        reservations = nemo_connector.get_reservations(
            tool_id=tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        assert isinstance(reservations, list)
        assert len(reservations) == 3, (
            f"Expected 3 reservations for 2021-08-02 to 2021-08-04, "
            f"got {len(reservations)}"
        )

        # Verify reservation IDs match seed data
        reservation_ids = {r["id"] for r in reservations}
        expected_ids = {187, 188, 191}
        assert reservation_ids == expected_ids, (
            f"Expected reservation IDs {expected_ids}, got {reservation_ids}"
        )

        # Test 2: Query for 2023-02-13 - should get 4 reservations
        dt_from_2023 = datetime.fromisoformat("2023-02-13T00:00:00-07:00")
        dt_to_2023 = datetime.fromisoformat("2023-02-13T23:59:59-07:00")

        reservations_2023 = nemo_connector.get_reservations(
            tool_id=tool_id,
            dt_from=dt_from_2023,
            dt_to=dt_to_2023,
        )

        assert isinstance(reservations_2023, list)
        assert len(reservations_2023) == 4, (
            f"Expected 4 reservations for 2023-02-13, got {len(reservations_2023)}"
        )

        # Verify reservation IDs match seed data
        reservation_ids_2023 = {r["id"] for r in reservations_2023}
        expected_ids_2023 = {200, 201, 202, 203}
        assert reservation_ids_2023 == expected_ids_2023, (
            f"Expected reservation IDs {expected_ids_2023}, got {reservation_ids_2023}"
        )

        # Test 3: Query for exact time range of one reservation
        dt_from_exact = datetime.fromisoformat("2021-08-02T11:00:00-06:00")
        dt_to_exact = datetime.fromisoformat("2021-08-02T16:00:00-06:00")

        reservations_exact = nemo_connector.get_reservations(
            tool_id=tool_id,
            dt_from=dt_from_exact,
            dt_to=dt_to_exact,
        )

        assert isinstance(reservations_exact, list)
        assert len(reservations_exact) == 1, (
            "Expected 1 reservation for exact time range"
        )

        # Should include reservation ID 187
        exact_id = reservations_exact[0]["id"]
        assert exact_id == 187

        # Test 4: Query for date range with no reservations
        dt_from_empty = datetime.fromisoformat("2020-01-01T00:00:00-06:00")
        dt_to_empty = datetime.fromisoformat("2020-01-02T00:00:00-06:00")

        reservations_empty = nemo_connector.get_reservations(
            tool_id=tool_id,
            dt_from=dt_from_empty,
            dt_to=dt_to_empty,
        )

        assert isinstance(reservations_empty, list)
        assert len(reservations_empty) == 0, (
            f"Expected 0 reservations for 2020-01-01, got {len(reservations_empty)}"
        )

    def test_get_usage_events_with_date_range(self, nemo_connector: NemoConnector):
        """Test fetching usage events for a specific date range.

        This test uses actual dates from seed_data.json to verify that
        the NEMO API correctly returns usage events within the specified range.

        Seed data contains four usage events (stored as Eastern Time in NEMO):
        - 2021-09-01: 17:00-20:00 ET (ID 29, tool 10, user 3, project 13)
        - 2021-09-05: 15:57-19:00 ET (ID 30, tool 10, user 3, project 13)
        - 2023-09-05: 15:57-19:00 ET (ID 31, tool 1, user 3, project 13)
        - 2018-11-13: 06:57-18:00 ET (ID 32, tool 3, user 3, project 13)

        Note: The connector filters usage events by tools in the NexusLIMS database,
        so this test queries without specific tool filtering to test date ranges.
        """
        # Test 1: Query for usage events by date range (September 2021)
        # Use Eastern Time since that's what NEMO stores
        dt_from = datetime.fromisoformat("2021-09-01T00:00:00-04:00")
        dt_to = datetime.fromisoformat("2021-09-05T23:59:59-04:00")

        # Query for events in this date range (will be filtered to known tools only)
        all_events = nemo_connector.get_usage_events(dt_range=(dt_from, dt_to))

        assert isinstance(all_events, list)
        assert len(all_events) == 2
        # Verify we get usage events back (tool filtering may limit which ones)
        # The key test is that the API call succeeds and returns a list
        # with the correct structure

        # Verify structure of returned events
        required_fields = {"id", "user", "project", "tool", "start", "end"}
        for event in all_events:
            assert required_fields.issubset(event.keys()), (
                f"Event {event.get('id', 'unknown')} missing required fields. "
                f"Expected all of {required_fields}, got {set(event.keys())}"
            )

        # Test 2: Query for single day (September 1st)
        dt_from_single = datetime.fromisoformat("2021-09-01T00:00:00-04:00")
        dt_to_single = datetime.fromisoformat("2021-09-01T23:59:59-04:00")

        single_day_events = nemo_connector.get_usage_events(
            dt_range=(dt_from_single, dt_to_single)
        )

        assert isinstance(single_day_events, list)
        # Should have same or fewer events than full date range
        assert len(single_day_events) == 1

        # Test 3: Query for date range with no usage events (far in past)
        dt_from_empty = datetime.fromisoformat("2020-01-01T00:00:00-04:00")
        dt_to_empty = datetime.fromisoformat("2020-01-02T00:00:00-04:00")

        usage_events_empty = nemo_connector.get_usage_events(
            dt_range=(dt_from_empty, dt_to_empty)
        )

        assert isinstance(usage_events_empty, list)
        # Should be empty since no events exist in this date range
        assert len(usage_events_empty) == 0

        # Test 4: Query without date range (gets all events for known tools)
        all_usage_events = nemo_connector.get_usage_events()

        assert isinstance(all_usage_events, list)
        # Should have at least as many events as our September query
        assert len(all_usage_events) == 4


@pytest.mark.integration
class TestNemoReservationHarvesting:
    """Test NEMO harvester functionality for building reservation events."""

    def test_res_event_from_session_with_valid_reservation(
        self,
        nemo_connector,
        test_instrument_db,
    ):
        """Test creating ReservationEvent from a session with matching reservation."""
        # Create a session that should match a reservation
        # Use the specific known test reservation dates from mock data
        # Reservation is between
        #       2021-08-02T11:00:00-06:00 and
        #       2021-08-02T16:00:00-06:00
        session = _create_session_from_iso_timestamps(
            session_identifier="test-session-123",
            instrument_pid="TEST-TOOL-010",
            start_iso="2021-08-02T11:00:00-06:00",
            end_iso="2021-08-02T16:00:00-06:00",
            user="testuser",
            instrument_db=test_instrument_db,
        )

        # This should succeed and return a ReservationEvent
        reservation_event = res_event_from_session(session, nemo_connector)

        # Verify the reservation event was created
        assert reservation_event is not None
        assert reservation_event.created_by == "ned"
        assert reservation_event.user_full_name == "Ned Land (ned)"

        # these values come from the reservation questions
        assert reservation_event.experiment_title == "Test Reservation Title"
        assert reservation_event.project_id == ["NexusLIMS-Test"]
        assert (
            reservation_event.experiment_purpose
            == "Testing the NEMO harvester integration."
        )
        assert reservation_event.sample_name == ["test_sample_1"]
        assert reservation_event.sample_elements == [None]

    def test_res_event_from_session_no_consent(
        self,
        nemo_connector,
        test_instrument_db,
    ):
        """Test that NoDataConsentError is raised when consent is missing.

        "tool": 10,
        "start": "2021-08-04T10:00:00-06:00",
        "end": "2021-08-04T17:00:00-06:00",
        """
        session = _create_session_from_iso_timestamps(
            session_identifier="test-session-123",
            instrument_pid="TEST-TOOL-010",
            start_iso="2021-08-04T09:00:00-06:00",
            end_iso="2021-08-04T17:40:00-06:00",
            user="testuser",
            instrument_db=test_instrument_db,
        )
        with pytest.raises(NoDataConsentError):
            res_event_from_session(session, nemo_connector)

    def test_res_event_from_session_no_reservation(
        self,
        nemo_connector,
        test_instrument_db,
    ):
        """Test handling when no matching reservation is found."""
        # this time range should have no reservations in NEMO
        session = _create_session_from_iso_timestamps(
            session_identifier="test-session-123",
            instrument_pid="TEST-TOOL-010",
            start_iso="2024-08-04T09:00:00-06:00",
            end_iso="2024-08-04T17:40:00-06:00",
            user="testuser",
            instrument_db=test_instrument_db,
        )
        with pytest.raises(NoMatchingReservationError):
            res_event_from_session(session, nemo_connector)


@pytest.mark.integration
class TestNemoReservationQuestions:
    """Test parsing of NEMO reservation questions."""

    @pytest.fixture
    def reservation_with_question_data(self, nemo_connector: NemoConnector):
        """Fixture to provide a known reservation with question data."""
        # Get reservations from NEMO
        dt_from = datetime.fromisoformat("2021-08-02T10:00:00-06:00")
        dt_to = datetime.fromisoformat("2021-08-02T16:00:00-06:00")

        # Using tool_id=10 to target known seed data (Test Tool)
        # should be one reservation with question data
        reservations = nemo_connector.get_reservations(
            tool_id=10,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        assert reservations != []
        return reservations[0]

    def test_parse_project_id_from_reservation(
        self,
        reservation_with_question_data,
    ):
        """Test extracting project_id from reservation question_data."""
        from nexusLIMS.harvesters.nemo import _get_res_question_value

        # Test parsing project_id from reservation
        project_id = _get_res_question_value(
            "project_id",
            reservation_with_question_data,
        )
        assert project_id == "NexusLIMS-Test"

    def test_parse_experiment_title_from_reservation(
        self,
        reservation_with_question_data,
    ):
        """Test extracting experiment_title from reservation question_data."""
        from nexusLIMS.harvesters.nemo import _get_res_question_value

        experiment_title = _get_res_question_value(
            "experiment_title",
            reservation_with_question_data,
        )
        # experiment_title should be a string or None
        assert experiment_title == "Test Reservation Title"

    def test_parse_sample_group_from_reservation(
        self,
        reservation_with_question_data,
    ):
        """Test extracting sample information from reservation question_data."""
        from nexusLIMS.harvesters.nemo import _get_res_question_value

        sample_group = _get_res_question_value(
            "sample_group",
            reservation_with_question_data,
        )
        expected = {
            "0": {
                "sample_name": "test_sample_1",
                "sample_or_pid": "Sample Name",
                "sample_details": "A test sample for harvester testing",
            }
        }
        assert sample_group == expected

    def test_parse_data_consent_from_reservation(
        self,
        reservation_with_question_data,
    ):
        """Test extracting data_consent from reservation question_data."""
        from nexusLIMS.harvesters.nemo import _get_res_question_value

        data_consent = _get_res_question_value(
            "data_consent",
            reservation_with_question_data,
        )
        assert data_consent == "Agree"


@pytest.mark.integration
class TestNemoErrorHandling:
    """Test error handling in NEMO integration."""

    def test_connector_handles_invalid_auth_token(self, nemo_api_url):
        """Test that connector handles invalid authentication properly."""
        connector = NemoConnector(
            base_url=nemo_api_url,
            token="invalid-token",
        )

        # should be a 403 forbidden
        with pytest.raises(requests.exceptions.HTTPError) as excinfo:
            connector.get_users()

        assert excinfo.value.response.status_code == HTTPStatus.FORBIDDEN

    def test_connector_handles_network_errors(self):
        """Test that connector handles network errors gracefully."""
        connector = NemoConnector(
            base_url="http://localhost:9999/api/",  # Non-existent service
            token="test-token",
            retries=2,
        )

        # Should pass through connection errors
        with pytest.raises(requests.exceptions.ConnectionError):
            connector.get_users()

    def test_get_reservations_with_invalid_tool_id(self, nemo_connector: NemoConnector):
        """Test fetching reservations with non-existent tool ID."""
        dt_from = datetime.now() - timedelta(days=1)
        dt_to = datetime.now() + timedelta(days=1)

        # Should raise 400 Client Error for non-existent tool ID
        with pytest.raises(requests.exceptions.HTTPError) as excinfo:
            nemo_connector.get_reservations(
                tool_id=99999,  # Non-existent tool ID
                dt_from=dt_from,
                dt_to=dt_to,
            )

        assert excinfo.value.response.status_code == HTTPStatus.BAD_REQUEST

    def test_res_event_from_session_no_overlap(
        self, nemo_connector, test_instrument_db
    ):
        """Test res_event_from_session when no reservations overlap with session."""
        # This tests the edge case where max(overlaps) == timedelta(0)
        # Create a session that doesn't overlap with any reservations
        session = Session(
            session_identifier="test-session-no-overlap",
            instrument=test_instrument_db.get("TEST-TOOL-010"),
            dt_range=(
                datetime.fromisoformat("2024-01-01T10:00:00-06:00"),
                datetime.fromisoformat("2024-01-01T12:00:00-06:00"),
            ),
            user="testuser",
        )

        # Should raise NoMatchingReservationError
        with pytest.raises(NoMatchingReservationError):
            res_event_from_session(session, nemo_connector)

    def test_res_event_from_session_empty_reservations(
        self, nemo_connector, test_instrument_db
    ):
        """Test res_event_from_session when no reservations exist for time range."""
        # This tests the edge case where len(reservations) == 0
        # Create a session for a future date with no reservations
        session = Session(
            session_identifier="test-session-future",
            instrument=test_instrument_db.get("TEST-TOOL-010"),
            dt_range=(
                datetime.fromisoformat("2100-01-01T10:00:00-06:00"),
                datetime.fromisoformat("2100-01-01T12:00:00-06:00"),
            ),
            user="testuser",
        )

        # Should raise NoMatchingReservationError
        with pytest.raises(NoMatchingReservationError):
            res_event_from_session(session, nemo_connector)


@pytest.mark.integration
class TestNemoAPIEdgeCases:
    """Test edge cases in NEMO API interactions."""

    def test_get_users_with_empty_list(
        self, nemo_connector: NemoConnector, mock_users_data: dict
    ):
        """Test get_users with empty list parameter."""
        # Should return all users
        users = nemo_connector.get_users([])
        assert isinstance(users, list)
        assert len(users) == 6
        usernames = {u["username"] for u in users}
        mock_usernames = {u["username"] for u in mock_users_data}
        assert mock_usernames.issubset(usernames)

    def test_get_tools_with_empty_list(
        self, nemo_connector: NemoConnector, mock_tools_data: dict
    ):
        """Test get_tools with empty list parameter."""
        # Should return all tools
        tools = nemo_connector.get_tools([])
        assert isinstance(tools, list)
        assert len(tools) > 100
        tool_names = {t["name"] for t in tools}
        mock_tool_names = {t["name"] for t in mock_tools_data}
        assert mock_tool_names.issubset(tool_names)

    def test_get_projects_with_empty_list(
        self, nemo_connector: NemoConnector, mock_projects_data: dict
    ):
        """Test get_projects with empty list parameter."""
        # Should return all projects
        projects = nemo_connector.get_projects([])
        assert isinstance(projects, list)
        project_names = {p["name"] for p in projects}
        mock_project_names = {p["name"] for p in mock_projects_data}
        assert mock_project_names.issubset(project_names)

    def test_get_reservations_with_none_parameters(
        self, nemo_connector: NemoConnector, mock_reservations_data: dict
    ):
        """Test get_reservations with all None parameters."""
        # Should return all non-cancelled reservations
        reservations = nemo_connector.get_reservations()
        assert isinstance(reservations, list)
        reservation_ids = {r["id"] for r in reservations}
        mock_reservation_ids = {
            r["id"] for r in mock_reservations_data if not r["cancelled"]
        }
        assert mock_reservation_ids.issubset(reservation_ids)

    def test_get_reservations_with_cancelled_none(
        self, nemo_connector: NemoConnector, mock_reservations_data: dict
    ):
        """Test get_reservations with all None parameters."""
        # Should return all reservations
        reservations = nemo_connector.get_reservations(cancelled=None)
        assert isinstance(reservations, list)
        reservation_ids = {r["id"] for r in reservations}
        mock_reservation_ids = {r["id"] for r in mock_reservations_data}
        assert mock_reservation_ids.issubset(reservation_ids)

    def test_get_reservations_with_cancelled_filter(
        self, nemo_connector: NemoConnector
    ):
        """Test get_reservations with cancelled parameter."""
        # Test with cancelled=True
        # Get reservations with cancelled filter
        reservations_cancelled = nemo_connector.get_reservations(cancelled=True)

        # Should return a list of length 2
        assert isinstance(reservations_cancelled, list)
        assert len(reservations_cancelled) == 2

        # Test with cancelled=False
        reservations_not_cancelled = nemo_connector.get_reservations(cancelled=False)

        # Should return a list of length 9
        assert isinstance(reservations_not_cancelled, list)
        assert len(reservations_not_cancelled) == 9

    def test_get_usage_events_with_none_parameters(
        self, nemo_connector: NemoConnector, mock_usage_events_data: dict
    ):
        """Test get_usage_events with all None parameters."""
        # Should return all usage events (might be limited by API)
        usage_events = nemo_connector.get_usage_events()
        assert isinstance(usage_events, list)
        usage_event_ids = {u["id"] for u in usage_events}
        mock_usage_event_ids = {u["id"] for u in mock_usage_events_data}
        assert mock_usage_event_ids.issubset(usage_event_ids)

    def test_get_usage_events_with_event_id_filter(self, nemo_connector: NemoConnector):
        """Test get_usage_events with event_id parameter."""
        # Test with a specific event ID
        usage_events = nemo_connector.get_usage_events(event_id=30)

        # Should return a list
        assert isinstance(usage_events, list)
        assert len(usage_events) == 1

        # If events are returned, verify they have the expected structure
        for event in usage_events:
            assert isinstance(event, dict)
            assert "id" in event
            assert "start" in event
            assert "end" in event

    def test_get_usage_events_with_user_filter(self, nemo_connector: NemoConnector):
        """Test get_usage_events with user parameter."""
        # Use the user with usage events mock data
        user_id = 3

        # Get usage events for this user
        usage_events = nemo_connector.get_usage_events(user=user_id)

        # Should return a list with three events (IDs 29, 30, 31 from seed data)
        assert isinstance(usage_events, list)
        assert len(usage_events) == 3

        # Verify that all events are for the specified user
        for event in usage_events:
            if event.get("user"):
                assert event["user"]["id"] == user_id

    def test_get_usage_events_with_tool_filter(self, nemo_connector: NemoConnector):
        """Test get_usage_events with tool_id parameter."""
        # Use the first tool from mock data
        tool_id = 10

        # Get usage events for this tool
        usage_events = nemo_connector.get_usage_events(tool_id=tool_id)

        # Should return a list with 2 usage events
        assert isinstance(usage_events, list)
        assert len(usage_events) == 2

        # Verify that all events are for the specified tool
        for event in usage_events:
            if event.get("tool"):
                assert event["tool"]["id"] == tool_id


@pytest.mark.integration
class TestNemoUtilityFunctions:
    """Test utility functions that require real NEMO connection."""

    def test_get_harvesters_enabled(self, nemo_connector):
        """Test get_harvesters_enabled functionality."""
        # This test verifies that the function returns a list of NemoConnector instances
        # there should be one in our test setup
        harvesters = get_harvesters_enabled()
        assert isinstance(harvesters, list)
        assert len(harvesters) == 1

        harvester = harvesters[0]
        assert isinstance(harvester, NemoConnector)
        assert hasattr(harvester, "config")
        assert "base_url" in harvester.config
        assert NEMO_URL in harvester.config["base_url"]

    def test_get_connector_by_base_url(self, nemo_connector: NemoConnector):
        """Test get_connector_by_base_url functionality."""
        # Use the base URL from the existing connector fixture
        base_url = nemo_connector.config["base_url"]

        # Get a connector using the base URL
        connector = get_connector_by_base_url(base_url)
        assert isinstance(connector, NemoConnector)
        assert base_url == connector.config["base_url"]

    def test_get_connector_by_base_url_not_found(self):
        """Test get_connector_by_base_url when no connector is found."""
        # Try to get a connector with a non-existent base URL
        with pytest.raises(LookupError) as excinfo:
            get_connector_by_base_url("http://nonexistent.example.com/api/")

        # Verify the error message
        assert "Did not find enabled NEMO harvester" in str(excinfo.value)
        assert "nonexistent.example.com" in str(excinfo.value)

    def test_get_connector_for_session(
        self, nemo_connector: NemoConnector, test_instrument_db
    ):
        """Test get_connector_for_session function."""
        # Create a session with an instrument from the test database
        instrument = test_instrument_db.get("TEST-TOOL-010")
        session = Session(
            session_identifier="test-session",
            instrument=instrument,
            dt_range=(
                datetime.fromisoformat("2023-01-15T10:00:00-06:00"),
                datetime.fromisoformat("2023-01-15T12:00:00-06:00"),
            ),
            user="testuser",
        )

        # Get the connector for this session
        connector = get_connector_for_session(session)
        assert isinstance(connector, NemoConnector)
        assert connector.config["base_url"] in instrument.api_url

    def test_get_connector_for_session_not_found(
        self, nemo_connector: NemoConnector, test_instrument_db
    ):
        """Test get_connector_for_session when no connector is found."""
        # Create a mock instrument with a different API URL
        from nexusLIMS.instruments import Instrument

        mock_instrument = Instrument(
            instrument_pid="UNKNOWN-INSTRUMENT",
            schema_name="Unknown Instrument",
            harvester="test",
            api_url="https://unknown.example.com/api/tools/?id=999",
            calendar_name="Unknown Instrument",
            calendar_url="https://unknown.example.com/calendar/",
            location="Unknown",
            property_tag="UNKNOWN",
            filestore_path="./unknown",
            timezone_str="America/New_York",
        )

        # Create a session with this unknown instrument
        session = Session(
            session_identifier="test-session",
            instrument=mock_instrument,
            dt_range=(
                datetime.fromisoformat("2023-01-15T10:00:00-06:00"),
                datetime.fromisoformat("2023-01-15T12:00:00-06:00"),
            ),
            user="testuser",
        )

        # Try to get the connector - should raise LookupError
        with pytest.raises(LookupError) as excinfo:
            get_connector_for_session(session)

        # Verify the error message
        assert "Did not find enabled NEMO harvester" in str(excinfo.value)
        assert "UNKNOWN-INSTRUMENT" in str(excinfo.value)

    def test_add_all_usage_events_to_db(self, nemo_connector: NemoConnector):
        """Test add_all_usage_events_to_db function with real API."""
        from nexusLIMS.db.session_handler import get_all_session_logs

        # This function writes to the database, so we test that it completes
        # Use filters to limit the scope
        # Call the function - it should complete without error
        before_logs = get_all_session_logs()
        add_all_usage_events_to_db()

        # Test the contents of the database to ensure it was updated
        # Query the session_log table to verify usage events were added

        # Query all session logs
        after_logs = get_all_session_logs()

        # Check that we added exactly 8 new session logs
        # (2 per usage event * 4 usage events)
        new_logs_count = len(after_logs) - len(before_logs)
        assert new_logs_count == 8, f"Expected 8 new session logs, got {new_logs_count}"

        # Also verify that the new logs contain the expected usage event IDs
        # Each usage event should have a START and END log
        new_logs = [log for log in after_logs if log not in before_logs]
        usage_event_ids = set()
        for log in new_logs:
            # Extract usage event ID from session_identifier
            if "?id=" in log.session_identifier:
                event_id = log.session_identifier.split("?id=")[1].split("&")[0]
                usage_event_ids.add(event_id)

        # We expect usage events 29, 30, 31, and 32
        expected_event_ids = {"29", "30", "31", "32"}
        assert usage_event_ids == expected_event_ids, (
            f"Expected event IDs {expected_event_ids}, got {usage_event_ids}"
        )


@pytest.mark.integration
class TestNemoEndToEndWorkflow:
    """Test complete NEMO integration workflows."""

    def test_complete_reservation_to_xml_workflow(
        self, nemo_connector, test_instrument_db
    ):
        """Test complete workflow from reservation to XML generation."""
        # 1. Create session from known reservation
        session = _create_session_from_iso_timestamps(
            session_identifier="test-workflow-session",
            instrument_pid="TEST-TOOL-010",
            start_iso="2021-08-02T11:00:00-06:00",
            end_iso="2021-08-02T16:00:00-06:00",
            user="testuser",
            instrument_db=test_instrument_db,
        )

        # 2. Get reservation event
        reservation_event = res_event_from_session(session, nemo_connector)

        # 3. Generate XML
        xml = reservation_event.as_xml()

        # 4. Validate XML structure
        assert hasattr(xml, "tag")  # Check if it's an XML element
        title = xml.find("title")
        assert title is not None
        assert title.text == "Test Reservation Title"
        motivation = xml.find("summary/motivation")
        assert motivation is not None
        assert motivation.text == "Testing the NEMO harvester integration."

    def test_get_known_tool_ids(self, nemo_connector: NemoConnector):
        """Test get_known_tool_ids functionality."""
        # Get known tool IDs
        tool_ids = nemo_connector.get_known_tool_ids()

        # Should return a list
        assert isinstance(tool_ids, list)

        # Each item should be an integer
        for tool_id in tool_ids:
            assert isinstance(tool_id, int)

    def test_connector_repr(self, nemo_connector: NemoConnector):
        """Test NemoConnector __repr__ method."""
        # Simple test that repr works
        repr_str = repr(nemo_connector)
        assert repr_str == f"Connection to NEMO API at {NEMO_URL}"
