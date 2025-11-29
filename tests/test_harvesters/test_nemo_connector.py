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
        nemo_address = str(next(iter(settings.nemo_harvesters.values())).address)
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

        # test format seen on ***REMOVED*** coerced to timezone
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
