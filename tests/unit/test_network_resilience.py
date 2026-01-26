# ruff: noqa: ARG001
"""
Network resilience unit tests for NexusLIMS.

This module tests the retry logic and error handling in the nexus_req function
when communicating with external services (NEMO and CDCS). All tests use mocking
to simulate network conditions without requiring actual services.
"""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import Timeout

from nexusLIMS.utils.network import nexus_req


@pytest.fixture
def mock_retry_request():
    """
    Create mock request handlers with configurable retry behavior.

    Returns a function that creates a mock side effect function for testing retries.
    The returned function accepts:
    - error_status: HTTP status code to return on failure
    - error_text: Text description of the error
    - failures_before_success: Number of times to fail before succeeding
    - success_status: HTTP status code to return on success (default 200)
    - success_data: Dict to return from .json() on success
    """

    def _create_mock(
        error_status,
        error_text,
        failures_before_success=1,
        success_status=HTTPStatus.OK,
        success_data=None,
    ):
        call_count = 0

        def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            response = MagicMock(spec=requests.Response)
            if call_count <= failures_before_success:
                response.status_code = error_status
                response.text = error_text
            else:
                response.status_code = success_status
                response.text = "Success"
                if success_data:
                    response.json.return_value = success_data

            return response

        # Return both the side effect function and a call counter accessor
        return mock_request_side_effect, lambda: call_count

    return _create_mock


class TestNetworkResilience:
    """Test network error handling and retry logic in nexus_req function."""

    def test_nexus_req_retries_on_502_bad_gateway(self, mock_retry_request):
        """
        Test that nexus_req retries on 502 Bad Gateway errors.

        This verifies that transient server errors trigger the retry mechanism
        as expected. The function should retry on 502, 503, 504 status codes.
        """
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.BAD_GATEWAY,
            error_text="Bad Gateway",
            failures_before_success=2,
            success_data={"status": "ok"},
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep") as mock_sleep,
        ):
            mock_request.side_effect = mock_side_effect

            # Make the request
            response = nexus_req("http://test.example.com/api", "GET", retries=5)

            # Verify it eventually succeeded
            assert response.status_code == HTTPStatus.OK
            assert get_call_count() == 3, "Should have retried twice before succeeding"

            # Verify sleep was called for backoff (2 retries = 2 sleeps)
            assert mock_sleep.call_count == 2, "Should have slept between retries"

    def test_nexus_req_retries_on_503_service_unavailable(self, mock_retry_request):
        """
        Test that nexus_req retries on 503 Service Unavailable errors.

        This simulates a scenario where a service is temporarily overloaded
        or restarting.
        """
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.SERVICE_UNAVAILABLE,
            error_text="Service Unavailable",
            failures_before_success=1,
            success_data={"data": "test"},
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_request.side_effect = mock_side_effect

            response = nexus_req("http://test.example.com/api", "GET", retries=3)

            assert response.status_code == HTTPStatus.OK
            assert get_call_count() == 2, "Should have retried once"

    def test_nexus_req_retries_on_504_gateway_timeout(self, mock_retry_request):
        """
        Test that nexus_req retries on 504 Gateway Timeout errors.

        This simulates a scenario where an upstream service times out.
        """
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.GATEWAY_TIMEOUT,
            error_text="Gateway Timeout",
            failures_before_success=1,
            success_status=HTTPStatus.CREATED,
            success_data={"id": "123"},
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_request.side_effect = mock_side_effect

            response = nexus_req("http://test.example.com/api", "POST", retries=5)

            assert response.status_code == HTTPStatus.CREATED
            assert get_call_count() == 2

    def test_nexus_req_gives_up_after_max_retries(self, mock_retry_request):
        """
        Test that nexus_req gives up after max retries are exhausted.

        This verifies that the system doesn't retry indefinitely when a service
        is persistently unavailable.
        """
        # Mock that never succeeds (failures_before_success > retries)
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.BAD_GATEWAY,
            error_text="Persistent failure",
            failures_before_success=999,  # Never succeeds
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_request.side_effect = mock_side_effect

            # Request with only 2 retries
            response = nexus_req("http://test.example.com/api", "GET", retries=2)

            # Should eventually return the failed response
            assert response.status_code == HTTPStatus.BAD_GATEWAY

            # Should have tried initial + 2 retries = 3 total
            assert get_call_count() == 3

    def test_nexus_req_does_not_retry_on_4xx_errors(self, mock_retry_request):
        """
        Test that nexus_req does NOT retry on 4xx client errors.

        Client errors like 400, 401, 404 indicate a problem with the request
        itself, not a transient server issue, so retrying won't help.
        """
        # Mock that always returns 404 (non-retryable error)
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.NOT_FOUND,
            error_text="Not Found",
            failures_before_success=999,  # Never succeeds, but won't retry anyway
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_request.side_effect = mock_side_effect

            response = nexus_req("http://test.example.com/api", "GET", retries=5)

            # Should return immediately without retries
            assert response.status_code == HTTPStatus.NOT_FOUND
            assert get_call_count() == 1, "Should not retry on 404"

    def test_nexus_req_backoff_strategy(self, mock_retry_request):
        """
        Test that nexus_req uses exponential backoff between retries.

        The implementation uses exponential backoff (2^attempt):
        - First retry: 1 second delay (2^0)
        - Second retry: 2 second delay (2^1)
        - Third retry: 4 second delay (2^2)
        - etc.

        This test verifies the exact backoff values.
        """
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.BAD_GATEWAY,
            error_text="Bad Gateway",
            failures_before_success=2,
        )

        sleep_calls = []
        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep") as mock_sleep,
        ):
            mock_request.side_effect = mock_side_effect
            mock_sleep.side_effect = lambda x: sleep_calls.append(x)

            response = nexus_req("http://test.example.com/api", "GET", retries=5)

            assert response.status_code == HTTPStatus.OK
            assert get_call_count() == 3

            # Verify exponential backoff: 2^0=1s, 2^1=2s
            assert sleep_calls == [1, 2], f"Expected [1, 2] but got {sleep_calls}"

    def test_cdcs_connection_error_handling(self):
        """
        Test CDCS API handling when service is unreachable.

        This simulates a network partition or service being down completely.
        """
        from nexusLIMS.utils import cdcs

        # Mock nexus_req to raise a ConnectionError
        with patch("nexusLIMS.utils.cdcs.nexus_req") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )

            # This should raise a ConnectionError
            with pytest.raises(requests.exceptions.ConnectionError):
                cdcs.get_workspace_id()

    def test_nemo_connection_error_handling(self):
        """
        Test NEMO API handling when service is unreachable.

        This verifies that NEMO connector properly handles network errors.
        """
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        # Create a connector
        connector = NemoConnector(
            base_url="http://nemo.example.com/api/", token="test-token"
        )

        # Mock the request to raise a ConnectionError
        with patch("nexusLIMS.utils.network.Session.request") as mock_request:
            mock_request.side_effect = ConnectionError("Connection refused")

            # This should raise a ConnectionError
            with pytest.raises(ConnectionError):
                connector.get_tools(1)

    def test_cdcs_retry_on_transient_500_error(self, mock_retry_request):
        """
        Test that CDCS operations retry on transient 503 errors.

        This simulates a scenario where CDCS temporarily returns 503 errors
        (e.g., during high load or database hiccup) but recovers.
        """
        mock_side_effect, get_call_count = mock_retry_request(
            error_status=HTTPStatus.SERVICE_UNAVAILABLE,
            error_text="Service Unavailable",
            failures_before_success=1,
            success_data=[{"id": "workspace-123"}],
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_req,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_req.side_effect = mock_side_effect

            from nexusLIMS.utils import cdcs

            # This should retry and eventually succeed
            workspace_id = cdcs.get_workspace_id()
            assert workspace_id == "workspace-123"
            assert get_call_count() == 2

    def test_nemo_retry_on_transient_503_error(self):
        """
        Test that NEMO operations retry on transient 503 errors.

        This simulates a scenario where NEMO is temporarily unavailable
        (e.g., during a restart) but comes back online.
        """
        from nexusLIMS.harvesters.nemo.connector import NemoConnector

        call_count = 0

        def mock_request_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            response = MagicMock(spec=requests.Response)
            if call_count == 1:
                response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
                response.text = "Service Unavailable"
            else:
                response.status_code = HTTPStatus.OK
                response.json.return_value = []

            return response

        # Create a connector
        connector = NemoConnector(
            base_url="http://nemo.example.com/api/", token="test-token"
        )

        with (
            patch("nexusLIMS.utils.network.Session.request") as mock_request,
            patch("nexusLIMS.utils.network.time.sleep"),
        ):
            mock_request.side_effect = mock_request_side_effect

            # This should retry and succeed
            result = connector.get_tools([])
            assert result == []
            assert call_count == 2

    def test_authentication_failure_does_not_retry(self):
        """
        Test that authentication failures (401) do not trigger retries.

        Retrying with the same bad credentials won't help, so we should
        fail fast on authentication errors.
        """

        def mock_nexus_req_returns_401(*args, **kwargs):
            response = MagicMock(spec=requests.Response)
            response.status_code = HTTPStatus.UNAUTHORIZED
            response.text = "Unauthorized"
            return response

        with patch("nexusLIMS.utils.cdcs.nexus_req") as mock_req:
            mock_req.side_effect = mock_nexus_req_returns_401

            from nexusLIMS.utils import cdcs

            # Should raise authentication error
            with pytest.raises(cdcs.AuthenticationError):
                cdcs.get_workspace_id()

            # Should have only tried once (no retries)
            assert mock_req.call_count == 1

    def test_mixed_transient_and_permanent_errors(self):
        """
        Test handling of mixed error scenarios.

        This simulates a realistic scenario where:
        1. First request fails with 503 (transient) - should retry
        2. Second request fails with 502 (transient) - should retry
        3. Third request succeeds

        This tests that the retry mechanism correctly handles a sequence
        of different transient errors.
        """
        call_count = 0
        error_sequence = [
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.OK,
        ]

        def mock_request_error_sequence(*args, **kwargs):
            nonlocal call_count
            response = MagicMock(spec=requests.Response)
            response.status_code = error_sequence[call_count]
            response.text = f"Response {call_count}"
            if error_sequence[call_count] == HTTPStatus.OK:
                response.json.return_value = {"success": True}
            call_count += 1
            return response

        with patch("nexusLIMS.utils.network.Session.request") as mock_request:
            mock_request.side_effect = mock_request_error_sequence

            response = nexus_req("http://test.example.com/api", "GET", retries=5)

            assert response.status_code == HTTPStatus.OK
            assert call_count == 3

    def test_rate_limiting_429_handling(self):
        """
        Test handling of 429 Too Many Requests errors.

        While 429 is not currently in the retry list, this test documents
        current behavior. In production, rate limiting might benefit from
        retry-after headers.

        NOTE: Current implementation does NOT retry on 429. This test
        documents that behavior and could be updated if retry logic changes.
        """

        def mock_request_returns_429(*args, **kwargs):
            response = MagicMock(spec=requests.Response)
            response.status_code = 429
            response.text = "Too Many Requests"
            response.headers = {"Retry-After": "60"}
            return response

        with patch("nexusLIMS.utils.network.Session.request") as mock_request:
            mock_request.side_effect = mock_request_returns_429

            response = nexus_req("http://test.example.com/api", "GET", retries=5)

            # Current behavior: returns 429 without retrying
            assert response.status_code == 429
            assert mock_request.call_count == 1, (
                "Should not retry on 429 (current behavior)"
            )

    def test_connection_timeout_handling(self):
        """
        Test handling of connection timeouts.

        This verifies that requests that timeout are handled gracefully.
        Timeouts are NOT retried as they indicate deeper connection problems.
        """

        def mock_request_timeout(*args, **kwargs):
            msg = "Connection timed out"
            raise Timeout(msg)

        with patch("nexusLIMS.utils.network.Session.request") as mock_request:
            mock_request.side_effect = mock_request_timeout

            # Timeout should propagate up
            with pytest.raises(Timeout):
                nexus_req("http://test.example.com/api", "GET", retries=2)

            # Timeouts are not retried - should only try once
            assert mock_request.call_count == 1

    def test_ssl_certificate_error_handling(self):
        """
        Test handling of SSL certificate verification errors.

        This verifies that SSL errors are handled appropriately and don't
        cause infinite retries.
        """

        def mock_request_ssl_error(*args, **kwargs):
            msg = "Certificate verification failed"
            raise requests.exceptions.SSLError(msg)

        with patch("nexusLIMS.utils.network.Session.request") as mock_request:
            mock_request.side_effect = mock_request_ssl_error

            # SSL error should propagate
            with pytest.raises(requests.exceptions.SSLError):
                nexus_req("https://test.example.com/api", "GET", retries=3)

            # Should have tried only once (SSL errors are not retried by default)
            assert mock_request.call_count == 1
