# ruff: noqa: DTZ005
"""
Integration tests for NEMO harvester.

These tests verify that the NEMO harvester can correctly interact with a
real NEMO instance to fetch reservations, usage events, and other data.
"""

import logging
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
import requests

from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.nemo import res_event_from_session
from nexusLIMS.harvesters.nemo.connector import NemoConnector
from nexusLIMS.harvesters.nemo.exceptions import (
    NoDataConsentError,
    NoMatchingReservationError,
)

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
        raise ValueError(f"Instrument with PID {instrument_pid} not found in database")

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
class TestNemoConnector:
    """Test NEMO connector API interactions."""

    def test_nemo_service_is_accessible(self, nemo_url):
        """Test that NEMO service is accessible via HTTP."""
        response = requests.get(nemo_url, timeout=10)
        assert response.status_code == HTTPStatus.OK

    def test_nemo_api_is_accessible(self, nemo_api_url, nemo_client):
        """Test that NEMO API endpoint is accessible."""
        # Try to access the API root with authentication
        headers = {"Authorization": f"Token {nemo_client['token']}"}
        response = requests.get(nemo_api_url, headers=headers, timeout=10)
        # NEMO API should return 200 with valid authentication
        assert response.status_code == HTTPStatus.OK

    def test_create_nemo_connector(self, nemo_connector, nemo_client):
        """Test creating a NemoConnector instance."""
        assert nemo_connector is not None
        assert nemo_connector.config["base_url"] == nemo_client["url"]

    def test_get_users(self, nemo_connector, nemo_client, mock_users_data):
        """Test fetching users from NEMO API."""

        # get_users with None returns all users
        users = nemo_connector.get_users(user_id=None)
        assert isinstance(users, list)
        assert len(users) >= len(mock_users_data)  # Should have at least our test users

        # Check that expected users exist
        usernames = [u["username"] for u in users]
        expected_usernames = [u["username"] for u in mock_users_data]
        for expected_username in expected_usernames:
            assert expected_username in usernames

    def test_get_tools(self, nemo_connector, nemo_client, mock_tools_data):
        """Test fetching tools from NEMO API."""

        # Get a specific tool by ID
        tool_id = mock_tools_data[0]["id"]
        tools = nemo_connector.get_tools(tool_id=tool_id)
        assert isinstance(tools, list)
        assert len(tools) >= 1  # Should have at least one tool
        assert tools[0]["id"] == tool_id

    def test_get_projects(self, nemo_connector, nemo_client, mock_projects_data):
        """Test fetching projects from NEMO API."""

        # get_projects requires a proj_id parameter
        # Use an empty list to get all projects
        projects = nemo_connector.get_projects(proj_id=[])
        assert isinstance(projects, list)
        # Should have at least one project from seed data
        assert len(projects) >= len(mock_projects_data)

    def test_get_reservations_with_date_range(
        self, nemo_connector, nemo_client, mock_tools_data
    ):
        """Test fetching reservations for a specific date range and tool."""

        # Get the first test tool
        tool_id = mock_tools_data[0]["id"]

        # Use a wide date range to capture test reservations
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        try:
            reservations = nemo_connector.get_reservations(
                tool_id=tool_id,
                dt_from=dt_from,
                dt_to=dt_to,
            )
        except Exception as e:
            # Handle potential NEMO API issues (e.g., JSON serialization errors)
            if "JSONDecodeError" in str(e) or "question_data" in str(e):
                pytest.skip(f"NEMO API has JSON serialization issue: {e}")
            else:
                # Re-raise other exceptions
                raise

        assert isinstance(reservations, list)
        # Reservations list might be empty if no test data was created for this tool
        # But the API call should succeed

    def test_get_usage_events_with_date_range(
        self, nemo_connector, nemo_client, mock_tools_data
    ):
        """Test fetching usage events for a specific date range and tool."""

        # Get the first test tool
        tool_id = mock_tools_data[0]["id"]

        # Use a wide date range to capture test usage events
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # get_usage_events takes dt_range as a tuple
        usage_events = nemo_connector.get_usage_events(
            tool_id=tool_id,
            dt_range=(dt_from, dt_to),
        )

        assert isinstance(usage_events, list)
        # Usage events list might be empty if no test data was created
        # But the API call should succeed


@pytest.mark.integration
class TestNemoHarvester:
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
    def reservation_with_question_data(self, nemo_connector):
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
        assert experiment_title is None or isinstance(experiment_title, str)

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
        # sample_group should be a dict, list, or None
        assert sample_group is None or isinstance(sample_group, (dict, list))

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
        # data_consent should be a string or None
        assert data_consent is None or isinstance(data_consent, str)
        # If present, should be either "Agree" or "Disagree"
        if data_consent:
            assert data_consent in ["Agree", "Disagree"]


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

    def test_get_reservations_with_invalid_tool_id(self, nemo_connector):
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
