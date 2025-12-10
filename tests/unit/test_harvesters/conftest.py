# ruff: noqa: ARG001
"""Shared fixtures for harvester tests."""

import warnings

import pytest

from nexusLIMS.harvesters.nemo.connector import NemoConnector

warnings.filterwarnings(
    action="ignore",
    message=r"DeprecationWarning: Using Ntlm()*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    r"Manually creating the cbt stuct from the cert hash will be removed",
    DeprecationWarning,
)


@pytest.fixture(name="nemo_connector")
def nemo_connector_test_instance(  # noqa: PLR0913
    monkeypatch,
    mock_users_data,
    mock_tools_data,
    mock_projects_data,
    mock_reservations_data,
    mock_usage_events_data,
):
    """
    Return a NemoConnector instance with mocked API calls.

    This fixture mocks the _api_caller method to return test data instead of
    making real HTTP requests to a NEMO server.
    """
    from tests.unit.fixtures.nemo_mock_data import filter_by_params

    connector = NemoConnector(
        base_url="https://nemo.example.com/api/",
        token="test-token-12345",
        timezone="America/Denver",
    )

    # Create a mock _api_caller that returns appropriate mock data
    def mock_api_caller(verb, endpoint, params):
        if endpoint == "users/":
            return filter_by_params(mock_users_data, params)
        if endpoint == "tools/":
            return filter_by_params(mock_tools_data, params)
        if endpoint == "projects/":
            return filter_by_params(mock_projects_data, params)
        if endpoint == "reservations/":
            return filter_by_params(mock_reservations_data, params)
        if endpoint == "usage_events/":
            return filter_by_params(mock_usage_events_data, params)
        return []

    monkeypatch.setattr(connector, "_api_caller", mock_api_caller)
    return connector


@pytest.fixture(name="bogus_nemo_connector_url")
def bogus_nemo_connector_url_test_instance(monkeypatch):
    """
    Return a NemoConnector with a bad URL and token that should fail.

    This connector only uses one retry to speed up the tests where this is used.
    """
    return NemoConnector("https://a_url_that_doesnt_exist/", "notneeded", retries=1)


@pytest.fixture(name="bogus_nemo_connector_token")
def bogus_nemo_connector_token_test_instance():
    """
    Return a NemoConnector with a bad URL and token that should fail.

    This connector only uses one retry to speed up the tests where this is used.
    """
    return NemoConnector("https://nemo.example.com/api/", "badtokenvalue", retries=1)
