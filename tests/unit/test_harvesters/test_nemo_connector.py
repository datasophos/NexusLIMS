# pylint: disable=C0116
# ruff: noqa: D102
"""
Test NEMO connector infrastructure.

Tests basic connector functionality, authentication, datetime handling,
and configuration.
"""

from datetime import datetime as dt
from datetime import timedelta

import pytest
import requests
from pytz import timezone

from nexusLIMS.harvesters.nemo import utils as nemo_utils
from nexusLIMS.harvesters.nemo.connector import NemoConnector


class TestNemoConnector:
    """
    NemoConnector tests.

    Testing NEMO integration. These tests aren't great since they're not
    general and require a running NEMO server (but we have to test
    integration, and I'm not about to write a whole NEMO installation into
    the test...). All of that is to say that if you want to run these tests
    in a different environment, these tests will have to be rewritten.
    """

    def test_nemo_connector_repr(self, nemo_connector):
        assert (
            str(nemo_connector)
            == "Connection to NEMO API at https://nemo.example.com/api/"
        )

    def test_nemo_multiple_harvesters_enabled(self, monkeypatch):
        from nexusLIMS.config import settings

        monkeypatch.setenv("NX_NEMO_ADDRESS_2", "https://nemo.address.com/api/")
        monkeypatch.setenv("NX_NEMO_TOKEN_2", "sometokenvalue")
        # Clear the cached property so it re-evaluates with new env vars
        if "nemo_harvesters" in settings.__dict__:
            del settings.__dict__["nemo_harvesters"]
        harvester_count = 2
        assert len(nemo_utils.get_harvesters_enabled()) == harvester_count
        assert "Connection to NEMO API at https://nemo.address.com/api/" in [
            str(n) for n in nemo_utils.get_harvesters_enabled()
        ]

    def test_nemo_harvesters_enabled(self):
        from nexusLIMS.config import settings

        assert len(nemo_utils.get_harvesters_enabled()) >= 1
        nemo_address = str(next(iter(settings.nemo_harvesters().values())).address)
        assert f"Connection to NEMO API at {nemo_address}" in [
            str(n) for n in nemo_utils.get_harvesters_enabled()
        ]

    def test_getting_nemo_data(self, nemo_connector):
        # Test that the connector can successfully get data via its API caller
        users = nemo_connector.get_users(user_id=1)
        assert len(users) == 1
        assert users[0]["username"] == "captain"

    def test_get_connector_by_base_url(self):
        with pytest.raises(LookupError):
            nemo_utils.get_connector_by_base_url("bogus_connector")

    def test_get_session_from_usage_event_no_event(self, nemo_connector, monkeypatch):
        def mock_get_usage_events(*_args, **_kwargs):
            return []

        monkeypatch.setattr(nemo_connector, "get_usage_events", mock_get_usage_events)
        assert nemo_connector.get_session_from_usage_event(123) is None

    def test_get_projects_expands_tools(self, nemo_connector, monkeypatch):
        def mock_api_caller(*_args, **_kwargs):
            return [{"id": 1, "name": "Test Project", "only_allow_tools": [1]}]

        def mock_get_tools(*_args, **_kwargs):
            return [{"id": 1, "name": "Test Tool"}]

        monkeypatch.setattr(nemo_connector, "_api_caller", mock_api_caller)
        monkeypatch.setattr(nemo_connector, "get_tools", mock_get_tools)

        projects = nemo_connector.get_projects(1)
        assert len(projects) == 1
        assert projects[0]["only_allow_tools"] == [{"id": 1, "name": "Test Tool"}]

    def test_connector_strftime(self):
        """Test conversion of datetimes to strings based on a connector's settings."""
        new_york = timezone("America/New_York")
        date_no_ms = dt(2022, 2, 16, 9, 39, 0, 0)  # noqa: DTZ001
        date_w_ms = dt(2022, 2, 16, 9, 39, 0, 1)  # noqa: DTZ001
        date_no_ms_tz = new_york.localize(date_no_ms)
        date_w_ms_tz = new_york.localize(date_w_ms)

        # test with no format settings (isoformat)
        nemo_conn = NemoConnector(base_url="https://example.org", token="not_needed")
        assert nemo_conn.strftime(date_no_ms) == "2022-02-16T09:39:00"
        assert nemo_conn.strftime(date_w_ms) == "2022-02-16T09:39:00.000001"
        assert nemo_conn.strftime(date_no_ms_tz) == "2022-02-16T09:39:00-05:00"
        assert nemo_conn.strftime(date_w_ms_tz) == "2022-02-16T09:39:00.000001-05:00"

        # test a few custom formats
        nemo_conn = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strftime_fmt="%Y-%m-%dT%H:%M:%S%z",
        )
        # these two will depend on whatever the local machine's offset is
        date_ = dt(2022, 2, 16, 9, 39, 0).astimezone().strftime("%z")
        assert nemo_conn.strftime(date_no_ms) == "2022-02-16T09:39:00" + date_
        assert nemo_conn.strftime(date_w_ms) == "2022-02-16T09:39:00" + date_
        assert nemo_conn.strftime(date_no_ms_tz) == "2022-02-16T09:39:00-0500"
        assert nemo_conn.strftime(date_w_ms_tz) == "2022-02-16T09:39:00-0500"

        # test %z in strftime_fmt for naive datetime with self.timezone set
        nemo_conn = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strftime_fmt="%Y-%m-%dT%H:%M:%S%z",
            timezone="America/New_York",
        )
        to_fmt = dt(2022, 2, 16, 23, 6, 12, 50)  # noqa: DTZ001
        to_fmt = new_york.localize(to_fmt)
        assert nemo_conn.strftime(to_fmt) == "2022-02-16T23:06:12-0500"

        # test %z in strftime_fmt for NAIVE datetime with self.timezone set
        # This tests connector.py where naive datetimes are localized
        nemo_conn_naive = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strftime_fmt="%Y-%m-%dT%H:%M:%S%z",
            timezone="America/New_York",
        )
        # Create a naive datetime (no tzinfo)
        naive_dt = dt(2022, 2, 16, 23, 6, 12, 50)  # noqa: DTZ001
        # Should be localized to America/New_York when strftime is called
        result = nemo_conn_naive.strftime(naive_dt)
        assert result == "2022-02-16T23:06:12-0500"

        # test %z in strftime_fmt for naive datetime with no self.timezone set
        nemo_conn = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strftime_fmt="%Y-%m-%dT%H:%M:%S%z",
        )
        to_fmt = dt(2022, 2, 16, 23, 6, 12, 50)  # noqa: DTZ001
        assert nemo_conn.strftime(to_fmt) == to_fmt.astimezone().strftime(
            "%Y-%m-%dT%H:%M:%S%z"
        )

    def test_parse_reservation_with_cancelled_by(self, nemo_connector, monkeypatch):
        """Test that _parse_reservation expands the cancelled_by field."""

        # Mock get_users to return a user dictionary
        def mock_get_users(user_id):
            if user_id == 5:
                return [
                    {"id": 5, "username": "canceller", "email": "canceller@example.com"}
                ]
            return []

        # Mock get_tools to return a tool dictionary
        def mock_get_tools(tool_id):
            if tool_id == 1:
                return [{"id": 1, "name": "Test Tool"}]
            return []

        # Mock get_projects to return a project dictionary
        def mock_get_projects(proj_id):
            if proj_id == 10:
                return [{"id": 10, "name": "Test Project"}]
            return []

        monkeypatch.setattr(nemo_connector, "get_users", mock_get_users)
        monkeypatch.setattr(nemo_connector, "get_tools", mock_get_tools)
        monkeypatch.setattr(nemo_connector, "get_projects", mock_get_projects)

        # Create a mock reservation with cancelled_by field
        reservation = {
            "id": 123,
            "user": 1,
            "creator": 2,
            "tool": 1,
            "project": 10,
            "cancelled_by": 5,  # This should be expanded to full user dict
            "start": "2024-01-01T10:00:00",
            "end": "2024-01-01T12:00:00",
        }

        # Parse the reservation
        parsed = nemo_connector._parse_reservation(reservation)  # noqa: SLF001

        # Verify that cancelled_by was expanded from ID to full user dict
        assert "cancelled_by" in parsed
        assert isinstance(parsed["cancelled_by"], dict)
        assert parsed["cancelled_by"]["id"] == 5
        assert parsed["cancelled_by"]["username"] == "canceller"
        assert parsed["cancelled_by"]["email"] == "canceller@example.com"

    def test_connector_strptime(self):
        """Test the conversion of string to datetime based on a connector's settings."""
        new_york = timezone("America/New_York")
        datestr_no_ms = "2022-02-16T09:39:00"
        datestr_w_ms = "2022-02-16T09:39:00.000001"
        datestr_no_ms_tz = "2022-02-16T09:39:00-05:00"
        datestr_w_ms_tz = "2022-02-16T09:39:00.000001-05:00"
        date_no_ms = dt(2022, 2, 16, 9, 39, 0, 0)  # noqa: DTZ001
        date_w_ms = dt(2022, 2, 16, 9, 39, 0, 1)  # noqa: DTZ001
        date_no_ms_tz = new_york.localize(date_no_ms)
        date_w_ms_tz = new_york.localize(date_w_ms)

        # test with no format settings (isoformat)
        nemo_conn = NemoConnector(base_url="https://example.org", token="not_needed")
        assert nemo_conn.strptime(datestr_no_ms) == date_no_ms
        assert nemo_conn.strptime(datestr_w_ms) == date_w_ms
        assert nemo_conn.strptime(datestr_no_ms_tz) == date_no_ms_tz
        assert nemo_conn.strptime(datestr_w_ms_tz) == date_w_ms_tz

        # test "iso-like" formats w/ and w/o timezone
        nemo_conn = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%Y-%m-%dT%H:%M:%S",
        )
        c_tz = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%Y-%m-%dT%H:%M:%S%z",
        )

        datestr_no_ms = "2022-02-16T09:39:00"
        datestr_w_ms = "2022-02-16T09:39:00.000001"
        datestr_no_ms_tz = "2022-02-16T09:39:00-05:00"
        datestr_w_ms_tz = "2022-02-16T09:39:00.000001-05:00"

        assert nemo_conn.strptime(datestr_no_ms) == date_no_ms
        with pytest.raises(
            ValueError,
            match=r"unconverted data remains: \.000001",
        ):  # should error since our fmt has no ms
            assert nemo_conn.strptime(datestr_w_ms) == date_w_ms
        with pytest.raises(
            ValueError,
            match="unconverted data remains: -05:00",
        ):  # should error since our fmt has no TZ
            assert nemo_conn.strptime(datestr_no_ms_tz) == date_no_ms_tz
        with pytest.raises(
            ValueError,
            match=r"unconverted data remains: \.000001-05:00",
        ):  # should error since our fmt has no TZ
            assert nemo_conn.strptime(datestr_w_ms_tz) == date_w_ms_tz

        with pytest.raises(
            ValueError,
            match=(
                "time data '2022-02-16T09:39:00' "
                "does not match format '%Y-%m-%dT%H:%M:%S%z'"
            ),
        ):  # should error since fmt expects TZ
            assert c_tz.strptime(datestr_no_ms) == date_no_ms
        with pytest.raises(
            ValueError,
            match=(
                r"time data '2022-02-16T09:39:00\.000001' does not "
                r"match format '%Y-%m-%dT%H:%M:%S%z'"
            ),
        ):  # should error since our fmt has no ms
            assert c_tz.strptime(datestr_w_ms) == date_w_ms
        assert c_tz.strptime(datestr_no_ms_tz) == date_no_ms_tz
        with pytest.raises(
            ValueError,
            match=(
                r"time data '2022-02-16T09:39:00\.000001-05:00' does not "
                r"match format '%Y-%m-%dT%H:%M:%S%z'"
            ),
        ):  # should error since our fmt has no ms
            assert c_tz.strptime(datestr_w_ms_tz) == date_w_ms_tz

        # test format seen on nemo.nist.gov
        nemo_conn_2 = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%m-%d-%Y %H:%M:%S",
        )
        datestr_no_ms = "02-16-2022 09:39:00"
        date_no_ms = dt(2022, 2, 16, 9, 39, 0, 0)  # noqa: DTZ001
        assert nemo_conn_2.strptime(datestr_no_ms) == date_no_ms

        # test format coerced to timezone
        nemo_conn_3 = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%m-%d-%Y %H:%M:%S",
            timezone="America/New_York",
        )
        datestr_no_ms = "02-16-2022 09:39:00"
        assert nemo_conn_3.strptime(datestr_no_ms) == date_no_ms_tz

        # test format with timezone coerced to different timezone (this will
        # keep the time the same, but switch the timezone to whatever
        # specified without adjusting the time)
        nemo_conn_4 = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%Y-%m-%dT%H:%M:%S%z",
            timezone="America/Denver",
        )
        # input is 9AM in Eastern time
        datestr_no_ms_tz = "2022-02-16T09:39:00-05:00"
        # result will be 9AM MT, so 2 hours past date_no_ms_tz (which is
        # 9AM ET)
        assert nemo_conn_4.strptime(datestr_no_ms_tz) == date_no_ms_tz + timedelta(
            hours=2,
        )
        assert nemo_conn_4.strptime(datestr_no_ms_tz) == dt.fromisoformat(
            "2022-02-16T09:39:00-07:00",
        )

        # test microsecond fallback
        nemo_conn_5 = NemoConnector(
            base_url="https://example.org",
            token="not_needed",
            strptime_fmt="%Y-%m-%dT%H:%M:%S.%f",
        )
        datestr_no_ms = "2022-02-16T09:39:00"
        date_no_ms = dt(2022, 2, 16, 9, 39, 0, 0)  # noqa: DTZ001
        assert nemo_conn_5.strptime(datestr_no_ms) == date_no_ms


class TestNemoConnectorAuthentication:
    """Testing NEMO connector authentication and error handling."""

    def test_get_users_bad_url(self, bogus_nemo_connector_url):
        with pytest.raises(requests.exceptions.ConnectionError):
            bogus_nemo_connector_url.get_users()

    def test_get_users_bad_token(self, bogus_nemo_connector_token, monkeypatch):
        def mock_api_caller_401(*_args, **_kwargs):
            """Mock _api_caller to raise 401 Unauthorized error."""
            response = requests.Response()
            response.status_code = 401
            response.reason = "Unauthorized"
            error_msg = "401 Client Error: Unauthorized"
            raise requests.exceptions.HTTPError(error_msg, response=response)

        monkeypatch.setattr(
            bogus_nemo_connector_token,
            "_api_caller",
            mock_api_caller_401,
        )

        with pytest.raises(requests.exceptions.HTTPError) as exception:
            bogus_nemo_connector_token.get_users()
        assert "401" in str(exception.value)
        assert "Unauthorized" in str(exception.value)


class TestNemoConnectorEquality:
    """Test the equality comparison of NemoConnector instances."""

    def test_equal_connectors(self):
        """Test that two connectors with identical configs are equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/Denver",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/Denver",
        )
        assert connector1 == connector2

    def test_unequal_base_url(self):
        """Test that connectors with different base URLs are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
        )
        connector2 = NemoConnector(
            base_url="https://different.example.com/api/",
            token="test-token-12345",
        )
        assert connector1 != connector2

    def test_unequal_token(self):
        """Test that connectors with different tokens are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="different-token-67890",
        )
        assert connector1 != connector2

    def test_unequal_timezone(self):
        """Test that connectors with different timezones are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/Denver",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/New_York",
        )
        assert connector1 != connector2

    def test_unequal_retries(self):
        """Test that connectors with different retry counts are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            retries=3,
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            retries=5,
        )
        assert connector1 != connector2

    def test_non_nemo_connector_comparison(self):
        """Test that comparison with non-NemoConnector objects returns False."""
        connector = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
        )
        assert connector != "not a connector"
        assert connector != 42
        assert connector is not None
        assert connector != {"base_url": "https://nemo.example.com/api/"}

    def test_all_config_parameters(self):
        """Test equality with all configuration parameters."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strftime_fmt="%Y-%m-%d",
            strptime_fmt="%Y-%m-%d",
            timezone="America/Denver",
            retries=3,
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strftime_fmt="%Y-%m-%d",
            strptime_fmt="%Y-%m-%d",
            timezone="America/Denver",
            retries=3,
        )
        assert connector1 == connector2

    def test_unequal_strftime_fmt(self):
        """Test that connectors with different strftime_fmt are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strftime_fmt="%Y-%m-%d",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strftime_fmt="%d-%m-%Y",
        )
        assert connector1 != connector2

    def test_unequal_strptime_fmt(self):
        """Test that connectors with different strptime_fmt are not equal."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strptime_fmt="%Y-%m-%d",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            strptime_fmt="%d-%m-%Y",
        )
        assert connector1 != connector2

    def test_api_caller_raise_for_status(self, monkeypatch):
        """Test that _api_caller calls raise_for_status on bad responses."""
        from unittest.mock import Mock

        # Create a fresh connector WITHOUT the mocked _api_caller
        connector = NemoConnector(
            base_url="https://test.example.com/api/",
            token="test-token",
        )

        # Create a mock response with a bad status code
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"

        # Make raise_for_status raise an HTTPError
        def mock_raise_for_status():
            error_msg = "500 Server Error: Internal Server Error"
            raise requests.exceptions.HTTPError(error_msg, response=mock_response)

        mock_response.raise_for_status = mock_raise_for_status

        # Mock nexus_req to return this bad response
        def mock_nexus_req(*_args, **_kwargs):
            return mock_response

        # Patch nexus_req in the connector module's namespace (where it's imported)
        import nexusLIMS.harvesters.nemo.connector as connector_module

        monkeypatch.setattr(connector_module, "nexus_req", mock_nexus_req)

        # Call _api_caller which should call raise_for_status
        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            connector._api_caller("GET", "users/", {})  # noqa: SLF001

        # Verify the error was raised from raise_for_status
        assert "500 Server Error" in str(exc_info.value)

    def test_api_caller_returns_json(self, monkeypatch):
        """Test that _api_caller returns parsed JSON."""
        from unittest.mock import Mock

        # Create a fresh connector WITHOUT the mocked _api_caller
        connector = NemoConnector(
            base_url="https://test.example.com/api/",
            token="test-token",
        )

        # Create a mock response with valid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()  # Does nothing for 200 OK

        # Mock json() to return parsed data
        expected_data = [{"id": 1, "username": "testuser"}]
        mock_response.json = Mock(return_value=expected_data)

        # Mock nexus_req to return this response
        def mock_nexus_req(*_args, **_kwargs):
            return mock_response

        # Patch nexus_req in the connector module's namespace (where it's imported)
        import nexusLIMS.harvesters.nemo.connector as connector_module

        monkeypatch.setattr(connector_module, "nexus_req", mock_nexus_req)

        # Call _api_caller which should return the JSON data
        result = connector._api_caller("GET", "users/", {})  # noqa: SLF001

        # Verify json() was called and data was returned
        assert mock_response.json.called
        assert result == expected_data

    def test_hash_identical_connectors(self):
        """Test that identical connectors have the same hash."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/Denver",
        )
        connector2 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
            timezone="America/Denver",
        )
        assert hash(connector1) == hash(connector2)

    def test_hash_different_connectors(self):
        """Test that different connectors have different hashes."""
        connector1 = NemoConnector(
            base_url="https://nemo.example.com/api/",
            token="test-token-12345",
        )
        connector2 = NemoConnector(
            base_url="https://different.example.com/api/",
            token="test-token-12345",
        )
        assert hash(connector1) != hash(connector2)
