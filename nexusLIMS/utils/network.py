"""Network and HTTP utilities for NexusLIMS."""

import logging
import tempfile
import time
from pathlib import Path

import certifi
from requests import Session
from requests.adapters import HTTPAdapter

from nexusLIMS.harvesters import CA_BUNDLE_CONTENT

_logger = logging.getLogger(__name__)


def nexus_req(
    url: str,
    function: str,
    *,
    retries: int = 5,
    token_auth: str | None = None,
    **kwargs: dict | None,
):
    """
    Make a request from NexusLIMS.

    A helper method that wraps a function from :py:mod:`requests`, but adds a
    local certificate authority chain to validate any custom certificates.
    Will automatically retry on transient server errors (502, 503, 504) with
    exponential backoff.

    Parameters
    ----------
    url
        The URL to fetch
    function
        The function from the ``requests`` library to use (e.g.
        ``'GET'``, ``'POST'``, ``'PATCH'``, etc.)
    retries
        The maximum number of retry attempts (total attempts = retries + 1)
    token_auth
        If a value is provided, it will be used as a token for authentication
    **kwargs :
        Other keyword arguments are passed along to the ``fn``

    Returns
    -------
    r : :py:class:`requests.Response`
        A requests response object
    """
    # if token_auth is desired, add it to any existing headers passed along
    # with the request
    if token_auth:
        if "headers" in kwargs:
            kwargs["headers"]["Authorization"] = f"Token {token_auth}"
        else:
            kwargs["headers"] = {"Authorization": f"Token {token_auth}"}

    # Status codes that should trigger a retry (transient server errors)
    retry_status_codes = {502, 503, 504}

    # Set up a session (without urllib3 retry logic - we'll handle it ourselves)
    s = Session()
    s.mount("https://", HTTPAdapter())
    s.mount("http://", HTTPAdapter())

    verify_arg = True
    response = None

    with tempfile.NamedTemporaryFile() as tmp:
        if CA_BUNDLE_CONTENT:
            with Path(certifi.where()).open(mode="rb") as sys_cert:
                lines = sys_cert.readlines()
            tmp.writelines(lines)
            tmp.writelines(CA_BUNDLE_CONTENT)
            tmp.seek(0)
            verify_arg = tmp.name

        # Retry loop with exponential backoff
        for attempt in range(retries + 1):
            response = s.request(function, url, verify=verify_arg, **kwargs)

            # If we got a successful response or non-retryable error, return it
            if response.status_code not in retry_status_codes:
                return response

            # If this is our last attempt, return the failed response
            if attempt == retries:
                _logger.warning(
                    "Request to %s failed with %s after %s attempts",
                    url,
                    response.status_code,
                    retries + 1,
                )
                return response

            # Calculate backoff delay: 1s, 2s, 4s, 8s, etc.
            delay = 2**attempt
            _logger.debug(
                "Request to %s returned %s, retrying in %ss (attempt %s/%s)",
                url,
                response.status_code,
                delay,
                attempt + 1,
                retries + 1,
            )
            time.sleep(delay)

    # This should never be reached in normal execution, but provides a fallback
    # if the retry loop somehow doesn't execute (e.g., invalid retries parameter)
    return response  # pragma: no cover
