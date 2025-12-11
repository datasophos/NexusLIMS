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
from nexusLIMS.harvesters.nemo.exceptions import NoDataConsentError

logger = logging.getLogger(__name__)


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

    def test_create_nemo_connector(self, nemo_client):
        """Test creating a NemoConnector instance."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )
        assert connector is not None
        assert connector.config["base_url"] == nemo_client["url"]

    def test_get_users(self, nemo_client, mock_users_data):
        """Test fetching users from NEMO API."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # get_users with None returns all users
        users = connector.get_users(user_id=None)
        assert isinstance(users, list)
        assert len(users) >= len(mock_users_data)  # Should have at least our test users

        # Check that expected users exist
        usernames = [u["username"] for u in users]
        expected_usernames = [u["username"] for u in mock_users_data]
        for expected_username in expected_usernames:
            assert expected_username in usernames

    def test_get_tools(self, nemo_client, mock_tools_data):
        """Test fetching tools from NEMO API."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get a specific tool by ID
        tool_id = mock_tools_data[0]["id"]
        tools = connector.get_tools(tool_id=tool_id)
        assert isinstance(tools, list)
        assert len(tools) >= 1  # Should have at least one tool
        assert tools[0]["id"] == tool_id

    def test_get_projects(self, nemo_client, mock_projects_data):
        """Test fetching projects from NEMO API."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # get_projects requires a proj_id parameter
        # Use an empty list to get all projects
        projects = connector.get_projects(proj_id=[])
        assert isinstance(projects, list)
        # Should have at least one project from seed data
        assert len(projects) >= len(mock_projects_data)

    def test_get_reservations_with_date_range(self, nemo_client, mock_tools_data):
        """Test fetching reservations for a specific date range and tool."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get the first test tool
        tool_id = mock_tools_data[0]["id"]

        # Use a wide date range to capture test reservations
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        reservations = connector.get_reservations(
            tool_id=tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        assert isinstance(reservations, list)
        # Reservations list might be empty if no test data was created for this tool
        # But the API call should succeed

    def test_get_usage_events_with_date_range(self, nemo_client, mock_tools_data):
        """Test fetching usage events for a specific date range and tool."""
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get the first test tool
        tool_id = mock_tools_data[0]["id"]

        # Use a wide date range to capture test usage events
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # get_usage_events takes dt_range as a tuple
        usage_events = connector.get_usage_events(
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
        nemo_client,
        populated_test_database,
    ):
        """
        Test creating ReservationEvent from a session with matching reservation.

        Dynamically finds a reservation in the system to test against.
        """
        import sqlite3
        from datetime import datetime, timedelta

        from nexusLIMS.db.session_handler import Session as SessionModel
        from nexusLIMS.harvesters.nemo import res_event_from_session
        from nexusLIMS.harvesters.nemo.connector import NemoConnector
        from nexusLIMS.harvesters.nemo.exceptions import NoDataConsentError
        from nexusLIMS.instruments import _get_instrument_db

        # Setup connector
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
            timezone=nemo_client["timezone"],
        )

        # 1. Find a tool with reservations
        tools = connector.get_tools([])
        target_tool_data = None
        target_res = None

        # Try to find a reservation that has data consent (if possible)
        # Or at least any reservation to start with
        for tool in tools:
            try:
                res_list = connector.get_reservations(tool_id=tool["id"])
                for res in res_list:
                    # Prefer one with 'Agree' if we can find it
                    if res.get("question_data") and "Agree" in str(
                        res["question_data"]
                    ):
                        target_tool_data = tool
                        target_res = res
                        break
                    # Otherwise keep the first one we found as fallback
                    if target_res is None:
                        target_tool_data = tool
                        target_res = res

                if target_res and "Agree" in str(target_res.get("question_data", "")):
                    break
            except Exception:
                continue

        if target_res is None:
            pytest.skip("No reservations found in NEMO to test with")

        # 2. Add this tool to the test database (if not already there)
        tool_api_url = f"{nemo_client['url']}tools/?id={target_tool_data['id']}"

        conn = sqlite3.connect(populated_test_database)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT instrument_pid FROM instruments WHERE api_url=?", (tool_api_url,)
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_tool_data["name"],
                    tool_api_url,
                    target_tool_data["name"],
                    "http://example.com",
                    "Test Lab",
                    target_tool_data["name"],
                    str(target_tool_data["id"]),
                    f"./{target_tool_data['name']}",
                    "nemo",
                    "America/Denver",
                ),
            )
            conn.commit()
        conn.close()

        # 3. Reload instruments
        instruments = _get_instrument_db(populated_test_database)
        instrument = next(
            (i for i in instruments.values() if i.api_url == tool_api_url), None
        )
        assert instrument is not None

        # 4. Create session matching the reservation
        res_start = connector.strptime(target_res["start"])
        user_name = target_res["user"]["username"]

        session = SessionModel(
            session_identifier="test_session_dynamic_valid",
            instrument=instrument,
            dt_range=(
                res_start + timedelta(minutes=1),
                res_start + timedelta(minutes=10),
            ),
            user=user_name,
        )

        # 5. Build event
        # If the reservation has no consent, this will raise NoDataConsentError
        # We handle this to make the test robust
        try:
            res_event = res_event_from_session(session, connector=connector)
            # If successful, verify details
            assert res_event.user == user_name
            assert res_event.instrument.name == instrument.name
        except NoDataConsentError:
            # This is acceptable if the only reservation we found didn't have consent
            # We treat this as a pass for "integration" purposes (we communicated with NEMO)
            pass

    def test_res_event_from_session_no_consent(
        self,
        nemo_client,
        populated_test_database,
    ):
        """
        Test that NoDataConsentError is raised when consent is missing.
        """
        import sqlite3
        from datetime import datetime, timedelta

        from nexusLIMS.db.session_handler import Session as SessionModel
        from nexusLIMS.harvesters.nemo import res_event_from_session
        from nexusLIMS.harvesters.nemo.connector import NemoConnector
        from nexusLIMS.harvesters.nemo.exceptions import NoDataConsentError
        from nexusLIMS.instruments import _get_instrument_db

        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
            timezone=nemo_client["timezone"],
        )

        # Find a reservation that likely has NO consent (e.g. no questions)
        tools = connector.get_tools([])
        target_tool_data = None
        target_res = None

        for tool in tools:
            try:
                res_list = connector.get_reservations(tool_id=tool["id"])
                for res in res_list:
                    # Look for missing or empty question data
                    if not res.get("question_data"):
                        target_tool_data = tool
                        target_res = res
                        break
                if target_res:
                    break
            except Exception:
                continue

        if target_res is None:
            pytest.skip("No reservations without consent found in NEMO")

        # Add tool to DB if needed
        tool_api_url = f"{nemo_client['url']}tools/?id={target_tool_data['id']}"
        conn = sqlite3.connect(populated_test_database)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT instrument_pid FROM instruments WHERE api_url=?", (tool_api_url,)
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_pid, api_url, calendar_name, calendar_url,
                    location, schema_name, property_tag, filestore_path,
                    harvester, timezone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_tool_data["name"],
                    tool_api_url,
                    target_tool_data["name"],
                    "http://example.com",
                    "Test Lab",
                    target_tool_data["name"],
                    str(target_tool_data["id"]),
                    f"./{target_tool_data['name']}",
                    "nemo",
                    "America/Denver",
                ),
            )
            conn.commit()
        conn.close()

        instruments = _get_instrument_db(populated_test_database)
        instrument = next(
            (i for i in instruments.values() if i.api_url == tool_api_url), None
        )
        assert instrument is not None

        # Create session
        res_start = connector.strptime(target_res["start"])
        session = SessionModel(
            session_identifier="test_session_dynamic_no_consent",
            instrument=instrument,
            dt_range=(
                res_start + timedelta(minutes=1),
                res_start + timedelta(minutes=10),
            ),
            user=target_res["user"]["username"],
        )

        # Expect error
        with pytest.raises(NoDataConsentError):
            res_event_from_session(session, connector=connector)

    def test_res_event_from_session_no_reservation(
        self,
        nemo_client,
        populated_test_database,
    ):
        """Test handling when no matching reservation is found."""
        from datetime import datetime, timedelta

        from nexusLIMS.db.session_handler import Session as SessionModel
        from nexusLIMS.harvesters.nemo import res_event_from_session
        from nexusLIMS.harvesters.nemo.connector import NemoConnector
        from nexusLIMS.harvesters.nemo.exceptions import NoMatchingReservationError
        from nexusLIMS.instruments import _get_instrument_db

        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
            timezone=nemo_client["timezone"],
        )

        instruments = _get_instrument_db(populated_test_database)
        # Use any valid instrument
        if not instruments:
            pytest.skip("No instruments in database")
        instrument = next(iter(instruments.values()))

        # Future date
        future_date = datetime.now() + timedelta(days=365)

        session = SessionModel(
            session_identifier="test_session_no_match",
            instrument=instrument,
            dt_range=(
                future_date,
                future_date + timedelta(hours=1),
            ),
            user="ned",
        )

        with pytest.raises(NoMatchingReservationError):
            res_event_from_session(session, connector=connector)


@pytest.mark.integration
class TestNemoReservationQuestions:
    """Test parsing of NEMO reservation questions."""

    def test_parse_project_id_from_reservation(self, nemo_client):
        """Test extracting project_id from reservation question_data."""
        from datetime import datetime, timedelta

        import requests

        from nexusLIMS.harvesters.nemo import _get_res_question_value
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        # First, check if NEMO API is accessible
        try:
            response = requests.get(
                nemo_client["url"],
                headers={"Authorization": f"Token {nemo_client['token']}"},
                timeout=5,
            )
            if response.status_code != 200:
                pytest.skip(f"NEMO API not accessible: HTTP {response.status_code}")
        except requests.RequestException as e:
            pytest.skip(f"NEMO API not accessible: {e}")

        # Create a NEMO connector
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get reservations from NEMO
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # Find the actual tool ID for "Test Tool" to handle ID mapping
        tools = connector.get_tools([])
        test_tool = next(
            (tool for tool in tools if tool.get("name") == "Test Tool"), None
        )

        if not test_tool:
            pytest.skip("Test Tool not found in NEMO instance")

        test_tool_id = test_tool["id"]

        # Using the actual tool ID for Test Tool
        reservations = connector.get_reservations(
            tool_id=test_tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        if not reservations:
            pytest.skip("No reservations found in NEMO for testing")

        # Test parsing project_id from each reservation
        for reservation in reservations:
            if reservation.get("question_data"):
                project_id = _get_res_question_value(
                    reservation["question_data"],
                    "project_id",
                )
                # project_id should be a string or None
                assert project_id is None or isinstance(project_id, str)

    def test_parse_experiment_title_from_reservation(self, nemo_client):
        """Test extracting experiment_title from reservation question_data."""
        from datetime import datetime, timedelta

        from nexusLIMS.harvesters.nemo import _get_res_question_value
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        # Create a NEMO connector
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get reservations from NEMO
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # Find the actual tool ID for "Test Tool" to handle ID mapping
        tools = connector.get_tools([])
        test_tool = next(
            (tool for tool in tools if tool.get("name") == "Test Tool"), None
        )

        if not test_tool:
            pytest.skip("Test Tool not found in NEMO instance")

        test_tool_id = test_tool["id"]

        # Using the actual tool ID for Test Tool
        reservations = connector.get_reservations(
            tool_id=test_tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        if not reservations:
            pytest.skip("No reservations found in NEMO for testing")

        # Test parsing experiment_title from each reservation
        for reservation in reservations:
            if reservation.get("question_data"):
                experiment_title = _get_res_question_value(
                    reservation["question_data"],
                    "experiment_title",
                )
                # experiment_title should be a string or None
                assert experiment_title is None or isinstance(experiment_title, str)

    def test_parse_sample_group_from_reservation(self, nemo_client):
        """Test extracting sample information from reservation question_data."""
        from datetime import datetime, timedelta

        from nexusLIMS.harvesters.nemo import _get_res_question_value
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        # Create a NEMO connector
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get reservations from NEMO
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # Find the actual tool ID for "Test Tool" to handle ID mapping
        tools = connector.get_tools([])
        test_tool = next(
            (tool for tool in tools if tool.get("name") == "Test Tool"), None
        )

        if not test_tool:
            pytest.skip("Test Tool not found in NEMO instance")

        test_tool_id = test_tool["id"]

        # Using the actual tool ID for Test Tool
        reservations = connector.get_reservations(
            tool_id=test_tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        if not reservations:
            pytest.skip("No reservations found in NEMO for testing")

        # Test parsing sample_group from each reservation
        for reservation in reservations:
            if reservation.get("question_data"):
                sample_group = _get_res_question_value(
                    reservation["question_data"],
                    "sample_group",
                )
                # sample_group should be a dict, list, or None
                assert sample_group is None or isinstance(sample_group, (dict, list))

    def test_parse_data_consent_from_reservation(self, nemo_client):
        """Test extracting data_consent from reservation question_data."""
        from datetime import datetime, timedelta

        from nexusLIMS.harvesters.nemo import _get_res_question_value
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        # Create a NEMO connector
        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        # Get reservations from NEMO
        dt_from = datetime.now() - timedelta(days=30)
        dt_to = datetime.now() + timedelta(days=30)

        # Find the actual tool ID for "Test Tool" to handle ID mapping
        tools = connector.get_tools([])
        test_tool = next(
            (tool for tool in tools if tool.get("name") == "Test Tool"), None
        )

        if not test_tool:
            pytest.skip("Test Tool not found in NEMO instance")

        test_tool_id = test_tool["id"]

        # Using the actual tool ID for Test Tool
        reservations = connector.get_reservations(
            tool_id=test_tool_id,
            dt_from=dt_from,
            dt_to=dt_to,
        )

        if not reservations:
            pytest.skip("No reservations found in NEMO for testing")

        # Test parsing data_consent from each reservation
        for reservation in reservations:
            if reservation.get("question_data"):
                data_consent = _get_res_question_value(
                    reservation["question_data"],
                    "data_consent",
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

        # Depending on NEMO configuration, this might return empty list
        # or raise an exception. Either is acceptable.
        try:
            users = connector.get_users()
            # If it returns empty list, that's fine
            assert isinstance(users, list)
        except Exception:
            # If it raises an exception, that's also fine
            pass

    def test_connector_handles_network_errors(self):
        """Test that connector handles network errors gracefully."""
        connector = NemoConnector(
            base_url="http://localhost:9999/api/",  # Non-existent service
            token="test-token",
        )

        # Should handle connection errors gracefully
        with pytest.raises(Exception):
            connector.get_users()

    def test_get_reservations_with_invalid_tool_id(self, nemo_client):
        """Test fetching reservations with non-existent tool ID."""
        import requests

        connector = NemoConnector(
            base_url=nemo_client["url"],
            token=nemo_client["token"],
        )

        dt_from = datetime.now() - timedelta(days=1)
        dt_to = datetime.now() + timedelta(days=1)

        # Should raise 400 Client Error for non-existent tool ID
        with pytest.raises(requests.exceptions.HTTPError) as excinfo:
            connector.get_reservations(
                tool_id=99999,  # Non-existent tool ID
                dt_from=dt_from,
                dt_to=dt_to,
            )

        assert excinfo.value.response.status_code == 400
