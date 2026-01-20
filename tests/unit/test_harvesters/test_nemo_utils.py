"""Tests for the NEMO harvester utility functions."""

import json
from unittest.mock import MagicMock, patch

import pytest

from nexusLIMS.db.session_handler import Session
from nexusLIMS.harvesters.nemo.utils import (
    _get_res_question_value,
    get_connector_by_base_url,
    get_connector_for_session,
    get_usage_events_as_sessions,
    has_valid_question_data,
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
    assert mock_connector.get_session_from_usage_event.call_count == 2


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


class TestHasValidQuestionData:
    """Tests for the has_valid_question_data() helper function."""

    def test_valid_run_data(self):
        """Test that valid run_data with data_consent returns True."""
        question_data = {
            "experiment_title": {"user_input": "Test Experiment"},
            "data_consent": {"user_input": "Agree"},
        }
        event_dict = {"run_data": json.dumps(question_data)}

        assert has_valid_question_data(event_dict, field="run_data") is True

    def test_valid_pre_run_data(self):
        """Test that valid pre_run_data with data_consent returns True."""
        question_data = {
            "experiment_title": {"user_input": "Test Experiment"},
            "data_consent": {"user_input": "Agree"},
        }
        event_dict = {"pre_run_data": json.dumps(question_data)}

        assert has_valid_question_data(event_dict, field="pre_run_data") is True

    def test_missing_field(self):
        """Test that missing field in event_dict returns False."""
        event_dict = {"some_other_field": "value"}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_field_is_none(self):
        """Test that None field value returns False."""
        event_dict = {"run_data": None}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_field_not_string(self):
        """Test that non-string field value returns False."""
        question_data = {"data_consent": {"user_input": "Agree"}}
        event_dict = {"run_data": question_data}  # dict instead of JSON string

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_field_empty_string(self):
        """Test that empty string field value returns False."""
        event_dict = {"run_data": ""}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_field_invalid_json(self):
        """Test that invalid JSON in field returns False."""
        event_dict = {"run_data": "not valid JSON {{{"}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_parsed_data_empty_dict(self):
        """Test that empty dict after parsing returns False."""
        event_dict = {"run_data": json.dumps({})}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_parsed_data_not_dict(self):
        """Test that non-dict parsed data (e.g., list) returns False."""
        event_dict = {"run_data": json.dumps(["item1", "item2"])}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_parsed_data_missing_data_consent(self):
        """Test that parsed data without data_consent field returns False."""
        question_data = {
            "experiment_title": {"user_input": "Test Experiment"},
            "sample_name": {"user_input": "Sample 1"},
        }
        event_dict = {"run_data": json.dumps(question_data)}

        assert has_valid_question_data(event_dict, field="run_data") is False

    def test_default_field_parameter(self):
        """Test that default field parameter is 'run_data'."""
        question_data = {
            "experiment_title": {"user_input": "Test Experiment"},
            "data_consent": {"user_input": "Agree"},
        }
        event_dict = {"run_data": json.dumps(question_data)}

        # Call without specifying field - should default to "run_data"
        assert has_valid_question_data(event_dict) is True
