"""
Mock NEMO API response data for unit testing, loaded from consolidated JSON source.

This module provides pytest fixtures with realistic NEMO API responses
based on the consolidated JSON data source that is also used by integration tests.
"""

import copy
import json
from pathlib import Path

import pytest


def load_consolidated_nemo_data():
    """Load NEMO test data from the consolidated JSON source."""
    json_path = (
        Path(__file__).parent.parent.parent
        / "integration"
        / "docker"
        / "nemo"
        / "fixtures"
        / "seed_data.json"
    )

    with json_path.open(encoding="utf-8") as f:
        return json.load(f)


def convert_to_python_types(data):
    """Convert JSON-compatible types to Python types (e.g., JSON null to None)."""
    if isinstance(data, list):
        return [convert_to_python_types(item) for item in data]
    if isinstance(data, dict):
        return {key: convert_to_python_types(value) for key, value in data.items()}
    if data == "null":
        return None
    if data == "true":
        return True
    if data == "false":
        return False
    return data


# Load the consolidated data
consolidated_data = load_consolidated_nemo_data()


@pytest.fixture
def mock_users_data():
    """
    Mock NEMO users API response data from consolidated source.

    Based on actual /api/users/ endpoint structure.
    Returns list of user dictionaries matching NEMO API schema.
    """
    return convert_to_python_types(consolidated_data["users"])


@pytest.fixture
def mock_tools_data():
    """
    Mock NEMO tools API response data from consolidated source.

    Based on actual /api/tools/ endpoint structure.
    Returns list of tool dictionaries matching NEMO API schema.
    """
    return convert_to_python_types(consolidated_data["tools"])


@pytest.fixture
def mock_projects_data():
    """
    Mock NEMO projects API response data from consolidated source.

    Based on actual /api/projects/ endpoint structure.
    Returns list of project dictionaries matching NEMO API schema.
    """
    return convert_to_python_types(consolidated_data["projects"])


@pytest.fixture
def mock_reservations_data():
    """
    Mock NEMO reservations API response data from consolidated source.

    Based on actual /api/reservations/ endpoint structure.
    Returns list of reservation dictionaries matching NEMO API schema.
    """
    return convert_to_python_types(consolidated_data.get("reservations", []))


@pytest.fixture
def mock_usage_events_data():
    """
    Mock NEMO usage_events API response data from consolidated source.

    Based on actual /api/usage_events/ endpoint structure.
    Returns list of usage event dictionaries matching NEMO API schema.
    """
    return convert_to_python_types(consolidated_data.get("usage_events", []))


@pytest.fixture
def filter_by_params():
    """
    Filter mock API data based on query parameters.

    Helper function to simulate NEMO API filtering logic.
    """

    def _filter_by_params(data, params):  # noqa: PLR0912
        """
        Filter mock API data based on query parameters.

        Parameters
        ----------
        data : list
            List of dictionaries representing API objects
        params : dict
            Query parameters for filtering

        Returns
        -------
        filtered : list
            Filtered list matching the parameters (deep copied to avoid mutation)
        """
        from datetime import datetime as dt

        # Deep copy to avoid mutation when connector modifies returned objects
        filtered = copy.deepcopy(data)

        # Filter by ID
        if "id" in params:
            filtered = [item for item in filtered if item["id"] == params["id"]]
        if "id__in" in params:
            ids = [int(i) for i in params["id__in"].split(",")]
            filtered = [item for item in filtered if item["id"] in ids]

        # Filter by username (for users)
        if "username__iexact" in params:
            filtered = [
                item
                for item in filtered
                if item.get("username", "").lower()
                == params["username__iexact"].lower()
            ]
        if "username__in" in params:
            usernames = [u.lower() for u in params["username__in"].split(",")]
            filtered = [
                item
                for item in filtered
                if item.get("username", "").lower() in usernames
            ]

        # Filter by tool_id (for reservations/usage_events)
        if "tool_id" in params:
            tool_id = (
                int(params["tool_id"])
                if isinstance(params["tool_id"], str)
                else params["tool_id"]
            )
            filtered = [item for item in filtered if item.get("tool") == tool_id]
        if "tool_id__in" in params:
            tool_ids = [int(i) for i in params["tool_id__in"].split(",")]
            filtered = [item for item in filtered if item.get("tool") in tool_ids]

        # Filter by user_id (for usage_events)
        if "user_id" in params:
            user_id = (
                int(params["user_id"])
                if isinstance(params["user_id"], str)
                else params["user_id"]
            )
            filtered = [item for item in filtered if item.get("user") == user_id]

        # Filter by cancelled status (for reservations)
        if "cancelled" in params:
            cancelled_val = params["cancelled"]
            if isinstance(cancelled_val, str):
                cancelled_val = cancelled_val.lower() in ["true", "1", "yes"]
            filtered = [
                item
                for item in filtered
                if item.get("cancelled", False) == cancelled_val
            ]

        # Filter by date range (for reservations/usage_events)
        if "start__gte" in params:
            start_gte = params["start__gte"]
            if isinstance(start_gte, str):
                start_gte = dt.fromisoformat(start_gte)
            filtered = [
                item
                for item in filtered
                if item.get("start") and dt.fromisoformat(item["start"]) >= start_gte
            ]

        if "end__lte" in params:
            end_lte = params["end__lte"]
            if isinstance(end_lte, str):
                end_lte = dt.fromisoformat(end_lte)
            filtered = [
                item
                for item in filtered
                if item.get("end") and dt.fromisoformat(item["end"]) <= end_lte
            ]

        return filtered

    return _filter_by_params


@pytest.fixture
def mock_usage_events_with_question_data(mock_usage_events_data):
    """
    Mock NEMO usage events with question data for testing three-tier fallback.

    This fixture filters usage events (IDs 100-106) from the consolidated data
    and returns them with expanded user/operator/tool fields.

    Test scenarios:
    - ID 100: run_data populated (highest priority)
    - ID 101: Only pre_run_data populated (medium priority)
    - ID 102: Both populated (should prefer run_data)
    - ID 103: pre_run_data with Disagree consent
    - ID 104: Missing user_input fields
    - ID 105: Empty strings (should fall back to reservation)
    - ID 106: Malformed JSON (should fall back to reservation)
    """
    # Filter for test usage events (IDs 100-106)
    test_event_ids = {100, 101, 102, 103, 104, 105, 106}
    test_events = [e for e in mock_usage_events_data if e["id"] in test_event_ids]

    # Expand user/operator/tool fields (simulating _parse_event())
    # Load user/tool/project data for expansion
    users_data = convert_to_python_types(consolidated_data["users"])
    tools_data = convert_to_python_types(consolidated_data["tools"])

    # Create lookup dicts
    users_by_id = {u["id"]: u for u in users_data}
    tools_by_id = {t["id"]: t for t in tools_data}

    # Expand each event
    for event in test_events:
        if event["user"] and event["user"] in users_by_id:
            event["user"] = users_by_id[event["user"]]
        if event["operator"] and event["operator"] in users_by_id:
            event["operator"] = users_by_id[event["operator"]]
        if event["tool"] and event["tool"] in tools_by_id:
            event["tool"] = tools_by_id[event["tool"]]

    return test_events
