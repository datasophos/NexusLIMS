"""Tests for the NEMO harvester utility functions."""

from unittest.mock import MagicMock, patch

import pytest

from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.nemo.utils import (
    _get_res_question_value,
    get_connector_by_base_url,
    get_connector_for_session,
    get_usage_events_as_sessions,
)


@patch("nexusLIMS.harvesters.nemo.utils.get_harvesters_enabled")
def test_get_usage_events_as_sessions(mock_get_harvesters):
    """Test that get_usage_events_as_sessions returns a list of sessions."""
    # Create a mock connector
    mock_connector = MagicMock()
    mock_connector.get_usage_events.return_value = [{"id": 1}, {"id": 2}]

    # Mock get_session_from_usage_event to return a Session object for the first call
    # and None for the second call to test the None handling.
    mock_session = MagicMock(spec=Session)
    mock_session.instrument = MagicMock()
    mock_connector.get_session_from_usage_event.side_effect = [mock_session, None]

    # Mock get_harvesters_enabled to return our mock connector
    mock_get_harvesters.return_value = [mock_connector]

    # Call the function
    sessions = get_usage_events_as_sessions()

    # Assert that the function returns a list with one session
    assert len(sessions) == 1
    assert sessions[0] == mock_session
    mock_connector.get_usage_events.assert_called_once()
    assert mock_connector.get_session_from_usage_event.call_count == 2  # noqa: PLR2004


@patch("nexusLIMS.harvesters.nemo.utils.get_harvesters_enabled")
def test_get_connector_for_session_success(mock_get_harvesters):
    """Test that get_connector_for_session returns the correct connector when found."""
    # Create a mock connector with matching base_url
    mock_connector = MagicMock()
    mock_connector.config = {"base_url": "http://test.com/"}

    # Mock get_harvesters_enabled to return our mock connector
    mock_get_harvesters.return_value = [mock_connector]

    # Create mock instrument and session
    mock_instrument = MagicMock()
    mock_instrument.api_url = "http://test.com/api/v1/"
    mock_instrument.name = "Test Instrument"

    mock_session = MagicMock(spec=Session)
    mock_session.instrument = mock_instrument

    # Call the function
    result = get_connector_for_session(mock_session)

    # Assert that it returns the correct connector
    assert result == mock_connector


def test_get_connector_for_session_raises_lookup_error():
    """Test that get_connector_for_session raises LookupError if no connector."""
    mock_instrument = MagicMock()
    mock_instrument.api_url = "http://test.com"
    mock_instrument.name = "Test Instrument"

    mock_session = MagicMock(spec=Session)
    mock_session.instrument = mock_instrument

    with pytest.raises(LookupError):
        get_connector_for_session(mock_session)


@patch("nexusLIMS.harvesters.nemo.utils.get_harvesters_enabled")
def test_get_connector_by_base_url_success(mock_get_harvesters):
    """Test that get_connector_by_base_url returns the correct connector when found."""
    # Create a mock connector with matching base_url
    mock_connector = MagicMock()
    mock_connector.config = {"base_url": "http://nemo.example.com/"}

    # Mock get_harvesters_enabled to return our mock connector
    mock_get_harvesters.return_value = [mock_connector]

    # Call the function with a base_url that should match
    result = get_connector_by_base_url("nemo.example.com")

    # Assert that it returns the correct connector
    assert result == mock_connector


def test_get_connector_by_base_url_raises_lookup_error():
    """Test that get_connector_by_base_url raises LookupError when no connector."""
    with pytest.raises(LookupError):
        get_connector_by_base_url("http://test.com")


def test_get_res_question_value_with_value():
    """Test _get_res_question_value when question_data contains the requested value."""
    res_dict = {
        "question_data": {
            "sample_name": {"user_input": "Test Sample"},
            "other_field": {"user_input": "Other Value"},
        }
    }

    result = _get_res_question_value("sample_name", res_dict)
    assert result == "Test Sample"


def test_get_res_question_value_missing_value():
    """Test _get_res_question_value when question_data doesn't contain value."""
    res_dict = {
        "question_data": {
            "other_field": {"user_input": "Other Value"},
        }
    }

    result = _get_res_question_value("sample_name", res_dict)
    assert result is None


def test_get_res_question_value_no_question_data():
    """Test _get_res_question_value when question_data doesn't exist."""
    # Test when question_data key doesn't exist at all
    res_dict = {"other_key": "value"}

    result = _get_res_question_value("sample_name", res_dict)
    assert result is None


def test_get_res_question_value_none_question_data():
    """Test _get_res_question_value when question_data is None."""
    res_dict = {"question_data": None}

    result = _get_res_question_value("sample_name", res_dict)
    assert result is None
