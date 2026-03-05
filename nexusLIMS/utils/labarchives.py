"""Low-level API client for LabArchives electronic lab notebook.

This module provides a reusable client for interacting with the LabArchives API.
Authentication uses HMAC-SHA-512 signed requests (akid + method + expires, keyed
with the access password).

LabArchives API documentation:
    https://api.labarchives.com/api_docs/

Example usage:
    >>> from nexusLIMS.utils.labarchives import get_labarchives_client
    >>> client = get_labarchives_client()
    >>> nodes = client.get_tree_level("12345", "0")
    >>> for node in nodes:
    ...     print(f"{node['tree_id']}: {node['display_text']}")
    >>> folder_id = client.insert_folder("12345", "0", "My Folder")
    >>> page_id = client.insert_page("12345", folder_id, "My Page")
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import xml.etree.ElementTree as ET
from http import HTTPStatus
from pathlib import Path  # noqa: TC003
from typing import Any

import requests

from nexusLIMS.config import settings

_logger = logging.getLogger(__name__)

# Minimum interval between API calls (seconds) per LabArchives ToS
_MIN_CALL_INTERVAL = 1.0
# Exponential backoff settings for 5xx errors
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class LabArchivesError(Exception):
    """Base exception for LabArchives API errors."""


class LabArchivesAuthenticationError(LabArchivesError):
    """Authentication failed (invalid credentials or session expired)."""


class LabArchivesPermissionError(LabArchivesError):
    """Insufficient permissions for the requested operation."""


class LabArchivesNotFoundError(LabArchivesError):
    """Requested resource not found."""


class LabArchivesRateLimitError(LabArchivesError):
    """Server error or rate limit exceeded (5xx response)."""


# LabArchives error codes that indicate authentication failures.
# 4514 = "Login and/or password information is incorrect" — returned on 404 for
# user_access_info when the supplied user credentials are wrong.
_AUTH_ERROR_CODES = {"4504", "4506", "4507", "4514", "4520", "4533"}
# LabArchives error codes that indicate permission failures
_PERM_ERROR_CODES = {"4501", "4502"}


class LabArchivesClient:
    """Low-level client for the LabArchives API.

    Authentication uses HMAC-SHA-512 signed requests. Each request includes:
    - ``akid``: Access Key ID
    - ``expires``: Unix timestamp in milliseconds
    - ``sig``: URL-encoded base64 HMAC-SHA-512 signature of ``akid + method + expires``

    Parameters
    ----------
    base_url : str
        API base URL including the ``/api`` path segment
        (e.g., ``"https://api.labarchives.com/api"``).
    akid : str
        Access Key ID for API authentication.
    password : str
        Access password (HMAC signing secret).
    uid : str
        LabArchives user ID for the account that owns records.

    Examples
    --------
    >>> client = LabArchivesClient(
    ...     base_url="https://api.labarchives.com/api",
    ...     akid="your-akid",
    ...     password="your-password",
    ...     uid="your-uid",
    ... )
    >>> nodes = client.get_tree_level("12345", "0")
    """

    def __init__(self, base_url: str, akid: str, password: str, uid: str) -> None:
        """Initialize LabArchives API client.

        Parameters
        ----------
        base_url : str
            Root URL of the LabArchives instance
        akid : str
            Access Key ID
        password : str
            Access password (HMAC signing secret)
        uid : str
            LabArchives user ID
        """
        self.base_url = base_url.rstrip("/")
        self.akid = akid
        self.password = password
        self.uid = uid
        self._last_call_time: float = 0.0

    def _sign(self, method: str) -> tuple[str, str]:
        """Generate HMAC-SHA-512 signature for an API method call.

        Parameters
        ----------
        method : str
            API method name only, without class prefix (e.g., "tree_level")

        Returns
        -------
        tuple[str, str]
            ``(expires_ms, sig)`` where ``expires_ms`` is the Unix timestamp
            in milliseconds as a string and ``sig`` is the raw base64-encoded
            HMAC-SHA-512 signature.  Do **not** pre-encode the signature —
            ``requests`` URL-encodes query parameter values automatically, so
            pre-encoding with ``urllib.parse.quote`` would double-encode it
            and invalidate the signature on the wire.
        """
        expires = str(int(time.time() * 1000))
        msg = self.akid + method + expires
        raw_sig = hmac.new(
            self.password.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha512,
        ).digest()
        return expires, base64.b64encode(raw_sig).decode("utf-8")

    def _auth_params(self, method: str) -> dict[str, str]:
        """Build authentication parameters for a request.

        Parameters
        ----------
        method : str
            API method name

        Returns
        -------
        dict[str, str]
            Dict with ``akid``, ``expires``, and ``sig`` keys
        """
        expires, sig = self._sign(method)
        return {"akid": self.akid, "expires": expires, "sig": sig}

    def _throttle(self) -> None:
        """Enforce minimum interval between API calls per LabArchives ToS."""
        elapsed = time.time() - self._last_call_time
        if elapsed < _MIN_CALL_INTERVAL:
            time.sleep(_MIN_CALL_INTERVAL - elapsed)  # pragma: no cover
        self._last_call_time = time.time()

    def _get(
        self,
        api_class: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> ET.Element:
        """Make an authenticated GET request and return parsed XML root.

        Parameters
        ----------
        api_class : str
            API class path (e.g., "notebooks")
        method : str
            API method name (e.g., "tree_level")
        params : dict, optional
            Additional query parameters

        Returns
        -------
        ET.Element
            Parsed XML root element from the response

        Raises
        ------
        LabArchivesError
            For general API errors
        LabArchivesAuthenticationError
            For authentication failures
        LabArchivesPermissionError
            For permission failures
        LabArchivesNotFoundError
            For 404 responses
        LabArchivesRateLimitError
            For 5xx responses
        """
        full_method = f"{api_class}/{method}"
        auth = self._auth_params(method)
        all_params = {**auth, **({"uid": self.uid} if self.uid else {})}
        if params:
            all_params.update(params)

        url = f"{self.base_url}/{full_method}"
        self._throttle()
        _logger.debug("LabArchives GET %s", url)

        for attempt in range(_MAX_RETRIES):
            resp = requests.get(url, params=all_params, timeout=30)
            _logger.debug("LabArchives GET %s → HTTP %s", url, resp.status_code)
            if resp.status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
                break
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY ** (attempt + 1)
                _logger.warning(
                    "LabArchives GET %s returned %s, retrying in %.1fs",
                    url,
                    resp.status_code,
                    delay,
                )
                time.sleep(delay)
        else:
            msg = (
                f"LabArchives API server error after {_MAX_RETRIES} retries: "
                f"{resp.status_code}"
            )
            raise LabArchivesRateLimitError(msg)

        return self._parse_response(resp, full_method)

    def _get_raw(  # pragma: no cover
        self,
        api_class: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> bytes:
        """Make an authenticated GET request and return the raw response body.

        Used for endpoints that return binary data rather than XML (e.g.,
        ``entries/entry_attachment``).

        Parameters
        ----------
        api_class : str
            API class path (e.g., "entries")
        method : str
            API method name (e.g., "entry_attachment")
        params : dict, optional
            Additional query parameters

        Returns
        -------
        bytes
            Raw response body

        Raises
        ------
        LabArchivesNotFoundError
            For HTTP 404 responses
        LabArchivesRateLimitError
            For HTTP 5xx responses after retries
        LabArchivesError
            For other non-2xx responses
        """
        full_method = f"{api_class}/{method}"
        auth = self._auth_params(method)
        all_params = {**auth, **({"uid": self.uid} if self.uid else {})}
        if params:
            all_params.update(params)

        url = f"{self.base_url}/{full_method}"
        self._throttle()
        _logger.debug("LabArchives GET (raw) %s", url)

        for attempt in range(_MAX_RETRIES):
            resp = requests.get(url, params=all_params, timeout=30)
            _logger.debug("LabArchives GET (raw) %s → HTTP %s", url, resp.status_code)
            if resp.status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
                break
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_BASE_DELAY ** (attempt + 1)
                _logger.warning(
                    "LabArchives GET (raw) %s returned %s, retrying in %.1fs",
                    url,
                    resp.status_code,
                    delay,
                )
                time.sleep(delay)
        else:
            msg = (
                f"LabArchives API server error after {_MAX_RETRIES} retries: "
                f"{resp.status_code}"
            )
            raise LabArchivesRateLimitError(msg)

        if resp.status_code == HTTPStatus.NOT_FOUND:
            msg = f"LabArchives resource not found (HTTP 404): {full_method}"
            raise LabArchivesNotFoundError(msg)
        if not resp.ok:
            msg = f"LabArchives request failed (HTTP {resp.status_code}): {full_method}"
            raise LabArchivesError(msg)

        return resp.content

    def _post(
        self,
        api_class: str,
        method: str,
        params: dict[str, Any] | None = None,
        data: bytes | None = None,
        form: dict[str, Any] | None = None,
    ) -> ET.Element:
        """Make an authenticated POST request and return parsed XML root.

        Parameters
        ----------
        api_class : str
            API class path (e.g., "entries")
        method : str
            API method name (e.g., "add_entry_to_page")
        params : dict, optional
            Additional query parameters (appended to URL)
        data : bytes, optional
            Raw binary data for the request body
        form : dict, optional
            Form data (``application/x-www-form-urlencoded``)

        Returns
        -------
        ET.Element
            Parsed XML root element from the response
        """
        full_method = f"{api_class}/{method}"
        auth = self._auth_params(method)
        all_params = {**auth, **({"uid": self.uid} if self.uid else {})}
        if params:
            all_params.update(params)

        url = f"{self.base_url}/{full_method}"
        self._throttle()
        _logger.debug("LabArchives POST %s", url)

        headers: dict[str, str] = {}
        if data is not None:
            headers["Content-Type"] = "application/octet-stream"

        for attempt in range(_MAX_RETRIES):
            resp = requests.post(
                url,
                params=all_params,
                data=data if data is not None else (form or {}),
                headers=headers,
                timeout=60,
            )
            if resp.status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
                break
            if attempt < _MAX_RETRIES - 1:  # pragma: no cover
                delay = _RETRY_BASE_DELAY ** (attempt + 1)
                _logger.warning(
                    "LabArchives POST %s returned %s, retrying in %.1fs",
                    url,
                    resp.status_code,
                    delay,
                )
                time.sleep(delay)
        else:  # pragma: no cover
            msg = (
                f"LabArchives API server error after {_MAX_RETRIES} retries: "
                f"{resp.status_code}"
            )
            raise LabArchivesRateLimitError(msg)

        return self._parse_response(resp, full_method)

    def _parse_response(self, resp: requests.Response, method: str) -> ET.Element:
        """Parse XML response and raise typed exceptions for errors.

        Parameters
        ----------
        resp : requests.Response
            HTTP response from the LabArchives API
        method : str
            API method that was called (for error messages)

        Returns
        -------
        ET.Element
            Parsed XML root element

        Raises
        ------
        LabArchivesNotFoundError
            For HTTP 404 responses
        LabArchivesRateLimitError
            For HTTP 5xx responses
        LabArchivesAuthenticationError
            For LA error codes indicating auth failures
        LabArchivesPermissionError
            For LA error codes indicating permission failures
        LabArchivesError
            For other API errors
        """
        if resp.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            _logger.debug("LabArchives %s body: %s", resp.status_code, resp.text[:1000])
            msg = f"LabArchives server error HTTP {resp.status_code}: {method}"
            raise LabArchivesRateLimitError(msg)

        try:
            root = ET.fromstring(resp.text)  # noqa: S314
        except ET.ParseError as e:
            _logger.debug("LabArchives unparseable body: %s", resp.text[:1000])
            # Fall back to HTTP-status-based errors when XML is unparseable.
            if resp.status_code == HTTPStatus.NOT_FOUND:
                msg = f"LabArchives resource not found (HTTP 404): {method}"
                raise LabArchivesNotFoundError(msg) from e
            msg = (
                f"Failed to parse LabArchives XML response for {method} "
                f"(HTTP {resp.status_code}): {e}\n"
                f"Response: {resp.text[:500]}"
            )
            raise LabArchivesError(msg) from e

        # Check for LabArchives error responses.
        # The API uses two different element naming schemes:
        #   legacy:  <error><code>N</code><msg>…</msg></error>
        #   current: <error><error-code>N</error-code>
        #              <error-description>…</error-description></error>
        error_el = root.find(".//error")
        if error_el is not None:
            code_el = error_el.find("error-code")
            if code_el is None:
                code_el = error_el.find("code")
            msg_el = error_el.find("error-description")
            if msg_el is None:
                msg_el = error_el.find("msg")
            code = code_el.text.strip() if code_el is not None and code_el.text else ""
            msg = (
                msg_el.text.strip()
                if msg_el is not None and msg_el.text
                else "Unknown error"
            )
            _logger.debug(
                "LabArchives error response (HTTP %s, code %s): %s\nBody: %s",
                resp.status_code,
                code,
                msg,
                resp.text[:1000],
            )
            full_msg = f"HTTP {resp.status_code}, error code {code!r}: {msg}"

            if code in _AUTH_ERROR_CODES:
                raise LabArchivesAuthenticationError(full_msg)
            if code in _PERM_ERROR_CODES:
                raise LabArchivesPermissionError(full_msg)
            raise LabArchivesError(full_msg)

        # No XML error element — fall back to HTTP status for 404.
        if resp.status_code == HTTPStatus.NOT_FOUND:  # pragma: no cover
            msg = f"LabArchives resource not found (HTTP 404): {method}"
            raise LabArchivesNotFoundError(msg)

        return root

    @staticmethod
    def _pretty_print_response(root: ET.Element) -> None:  # pragma: no cover
        """Print a nicely formatted XML representation of an API response.

        Parameters
        ----------
        root : ET.Element
            Parsed XML root element (as returned by :meth:`_parse_response`)
        """
        ET.indent(root)
        print(ET.tostring(root, encoding="unicode"))  # noqa: T201

    # ------------------------------------------------------------------ #
    # Public API methods                                                   #
    # ------------------------------------------------------------------ #

    def get_tree_level(
        self,
        nbid: str,
        parent_tree_id: str = "0",
    ) -> list[dict[str, Any]]:
        """Get child nodes at a tree level in a notebook.

        Parameters
        ----------
        nbid : str
            Notebook ID
        parent_tree_id : str, optional
            Parent tree node ID; "0" for the root level

        Returns
        -------
        list of dict
            Each dict has ``tree_id``, ``display_text``, and ``is_page`` keys.

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        root = self._get(
            "tree_tools",
            "get_tree_level",
            params={"nbid": nbid, "parent_tree_id": parent_tree_id},
        )

        nodes = []
        for item in root.findall(".//level-node"):
            tree_id_el = item.find("tree-id")
            text_el = item.find("display-text")
            is_page_el = item.find("is-page")
            if tree_id_el is None or text_el is None:  # pragma: no cover
                continue
            nodes.append(
                {
                    "tree_id": tree_id_el.text or "",
                    "display_text": text_el.text or "",
                    "is_page": (is_page_el is not None and is_page_el.text == "true"),
                }
            )

        return nodes

    def get_page_entries(  # pragma: no cover
        self,
        nbid: str,
        page_tree_id: str,
        *,
        include_content: bool = False,
    ) -> list[dict[str, Any]]:
        """Get all entries on a notebook page.

        Parameters
        ----------
        nbid : str
            Notebook ID
        page_tree_id : str
            Tree ID of the page
        include_content : bool, optional
            When True, each entry dict will include an ``entry_data`` key
            containing the raw HTML/text content of the entry.

        Returns
        -------
        list of dict
            Each dict has ``eid`` and ``part_type`` keys, plus ``entry_data``
            when *include_content* is True.

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        root = self._get(
            "tree_tools",
            "get_entries_for_page",
            params={
                "nbid": nbid,
                "page_tree_id": page_tree_id,
                "entry_data": "true" if include_content else "false",
            },
        )

        entries = []
        for entry_el in root.findall(".//entry"):
            eid_el = entry_el.find("eid")
            part_type_el = entry_el.find("part-type")
            entry: dict[str, Any] = {
                "eid": eid_el.text.strip()
                if eid_el is not None and eid_el.text
                else "",
                "part_type": (
                    part_type_el.text.strip()
                    if part_type_el is not None and part_type_el.text
                    else ""
                ),
            }
            if include_content:
                # The API uses <entry_data> (underscore) per the docs
                data_el = entry_el.find("entry_data")
                if data_el is None:
                    data_el = entry_el.find("entry-data")
                entry["entry_data"] = (
                    data_el.text.strip() if data_el is not None and data_el.text else ""
                )
            entries.append(entry)

        return entries

    def _insert_node(
        self,
        nbid: str,
        parent_tree_id: str,
        display_text: str,
        *,
        is_folder: bool,
    ) -> str:
        """Create a folder or page node in a notebook tree.

        Parameters
        ----------
        nbid : str
            Notebook ID
        parent_tree_id : str
            Parent tree node ID
        display_text : str
            Display name for the new node
        is_folder : bool
            True to create a folder; False to create a page

        Returns
        -------
        str
            The ``tree_id`` of the newly created node

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        root = self._get(
            "tree_tools",
            "insert_node",
            params={
                "nbid": nbid,
                "parent_tree_id": parent_tree_id,
                "display_text": display_text,
                "is_folder": "true" if is_folder else "false",
            },
        )

        tree_id_el = root.find(".//tree-id")
        if tree_id_el is None or not tree_id_el.text:
            msg = f"insert_node response missing tree-id for '{display_text}'"
            raise LabArchivesError(msg)

        return tree_id_el.text.strip()

    def insert_folder(self, nbid: str, parent_tree_id: str, name: str) -> str:
        """Create a folder in a notebook tree.

        Parameters
        ----------
        nbid : str
            Notebook ID
        parent_tree_id : str
            Parent tree node ID; ``"0"`` for the root level
        name : str
            Display name for the new folder

        Returns
        -------
        str
            The ``tree_id`` of the newly created folder

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        return self._insert_node(nbid, parent_tree_id, name, is_folder=True)

    def insert_page(self, nbid: str, parent_tree_id: str, name: str) -> str:
        """Create a page in a notebook tree.

        Parameters
        ----------
        nbid : str
            Notebook ID
        parent_tree_id : str
            Parent tree node ID (folder ``tree_id`` or ``"0"`` for root)
        name : str
            Display name for the new page

        Returns
        -------
        str
            The ``tree_id`` of the newly created page

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        return self._insert_node(nbid, parent_tree_id, name, is_folder=False)

    def add_entry(
        self,
        nbid: str,
        page_tree_id: str,
        entry_data: str,
        part_type: str = "text entry",
    ) -> str:
        """Add a text/HTML entry to a notebook page.

        Parameters
        ----------
        nbid : str
            Notebook ID
        page_tree_id : str
            Tree ID of the target page
        entry_data : str
            HTML or plain-text content for the entry
        part_type : str, optional
            Entry part type (default: "text entry")

        Returns
        -------
        str
            The ``eid`` (entry ID) of the newly created entry

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        root = self._post(
            "entries",
            "add_entry",
            form={
                "nbid": nbid,
                "pid": page_tree_id,
                "entry_data": entry_data,
                "part_type": part_type,
            },
        )

        eid_el = root.find(".//eid")
        if eid_el is None or not eid_el.text:
            msg = f"add_entry response missing eid for page {page_tree_id}"
            raise LabArchivesError(msg)

        return eid_el.text.strip()

    def add_attachment(
        self,
        nbid: str,
        page_tree_id: str,
        filename: str,
        data: bytes,
        caption: str = "",
    ) -> str:
        """Upload a file attachment to a notebook page.

        Parameters
        ----------
        nbid : str
            Notebook ID
        page_tree_id : str
            Tree ID of the target page
        filename : str
            Name to use for the uploaded file
        data : bytes
            Raw file content
        caption : str, optional
            Caption for the attachment

        Returns
        -------
        str
            The ``eid`` (entry ID) of the attachment entry

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        root = self._post(
            "entries",
            "add_attachment",
            params={
                "nbid": nbid,
                "pid": page_tree_id,
                "filename": filename,
                "caption": caption,
            },
            data=data,
        )

        eid_el = root.find(".//eid")
        if eid_el is None or not eid_el.text:  # pragma: no cover
            msg = f"add_attachment response missing eid for page {page_tree_id}"
            raise LabArchivesError(msg)

        return eid_el.text.strip()

    def attach_file(  # pragma: no cover
        self,
        nbid: str,
        page_tree_id: str,
        path: Path,
        caption: str = "",
    ) -> str:
        """Upload a file from disk as an attachment to a notebook page.

        Convenience wrapper around :meth:`add_attachment` that reads the file
        and derives the filename from the path automatically.

        Parameters
        ----------
        nbid : str
            Notebook ID
        page_tree_id : str
            Tree ID of the target page
        path : Path
            Local file to upload
        caption : str, optional
            Caption for the attachment

        Returns
        -------
        str
            The ``eid`` (entry ID) of the attachment entry

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        return self.add_attachment(
            nbid, page_tree_id, path.name, path.read_bytes(), caption
        )

    def get_attachment_content(self, eid: str) -> bytes:  # pragma: no cover
        """Download the raw content of an attachment entry.

        Parameters
        ----------
        eid : str
            Entry ID of the attachment (as returned by :meth:`add_attachment`)

        Returns
        -------
        bytes
            Raw file content of the attachment

        Raises
        ------
        LabArchivesNotFoundError
            If the entry does not exist
        LabArchivesError
            If the API call fails
        """
        return self._get_raw("entries", "entry_attachment", params={"eid": eid})

    def get_user_info(self, login: str, password: str) -> dict[str, Any]:
        """Exchange login credentials for user info and notebook list.

        This method is used to obtain the ``uid`` for a LabArchives account.
        The returned ``uid`` should be stored in ``NX_LABARCHIVES_USER_ID``
        for subsequent API calls.

        Parameters
        ----------
        login : str
            LabArchives login (email address)
        password : str
            LabArchives account password

        Returns
        -------
        dict
            User info including ``uid``, ``email``, and ``notebooks`` list.

        Raises
        ------
        LabArchivesAuthenticationError
            If login credentials are invalid
        LabArchivesError
            If the API call fails
        """
        # Response root element IS <users> — _parse_response returns it directly.
        # Structure:
        #   <users>
        #     <id>…</id>
        #     <fullname>…</fullname>
        #     <email>…</email>
        #     <notebooks type="array">
        #       <notebook><id>…</id><name>…</name></notebook>
        #     </notebooks>
        #   </users>
        root = self._get(
            "users",
            "user_access_info",
            params={"login_or_email": login, "password": password},
        )

        # The <users> root may be a direct child of a <response> wrapper in
        # tests; use a helper that finds it wherever it lives.
        users_el = root if root.tag == "users" else root.find(".//users")
        if users_el is None:  # pragma: no cover
            users_el = root

        result: dict[str, Any] = {}

        id_el = users_el.find("id")
        if id_el is not None and id_el.text:
            result["uid"] = id_el.text.strip()

        for tag in ("fullname", "first-name", "last-name", "email"):
            el = users_el.find(tag)
            if el is not None and el.text:
                result[tag] = el.text.strip()

        notebooks = []
        for nb in users_el.findall("notebooks/notebook"):
            nb_id_el = nb.find("id")
            nb_name_el = nb.find("name")
            nb_data: dict[str, str] = {}
            if nb_id_el is not None and nb_id_el.text:
                nb_data["id"] = nb_id_el.text.strip()
            if nb_name_el is not None and nb_name_el.text:
                nb_data["name"] = nb_name_el.text.strip()
            notebooks.append(nb_data)
        result["notebooks"] = notebooks

        return result

    def get_user_info_by_uid(
        self, uid: str | None = None
    ) -> dict[str, Any]:  # pragma: no cover
        """Fetch user info for a LabArchives account using a uid.

        Calls the ``users/user_info_via_id`` endpoint, which requires only the
        uid (no login password).  When *uid* is omitted the client's own
        :attr:`uid` is used.

        Parameters
        ----------
        uid : str, optional
            LabArchives user ID.  Defaults to the client's configured uid.

        Returns
        -------
        dict
            User info including ``uid``, ``email``, and ``notebooks`` list.

        Raises
        ------
        LabArchivesError
            If the API call fails
        """
        # Structure mirrors user_access_info:
        #   <users>
        #     <id>…</id>
        #     <fullname>…</fullname>
        #     <email>…</email>
        #     <notebooks type="array">
        #       <notebook><id>…</id><name>…</name></notebook>
        #     </notebooks>
        #   </users>
        lookup_uid = uid if uid is not None else self.uid
        root = self._get(
            "users",
            "user_info_via_id",
            params={"uid": lookup_uid},
        )

        users_el = root if root.tag == "users" else root.find(".//users")
        if users_el is None:
            users_el = root

        result: dict[str, Any] = {}

        id_el = users_el.find("id")
        if id_el is not None and id_el.text:
            result["uid"] = id_el.text.strip()

        for tag in ("fullname", "first-name", "last-name", "email"):
            el = users_el.find(tag)
            if el is not None and el.text:
                result[tag] = el.text.strip()

        notebooks = []
        for nb in users_el.findall("notebooks/notebook"):
            nb_id_el = nb.find("id")
            nb_name_el = nb.find("name")
            nb_data: dict[str, str] = {}
            if nb_id_el is not None and nb_id_el.text:
                nb_data["id"] = nb_id_el.text.strip()
            if nb_name_el is not None and nb_name_el.text:
                nb_data["name"] = nb_name_el.text.strip()
            notebooks.append(nb_data)
        result["notebooks"] = notebooks

        return result


def get_labarchives_client() -> LabArchivesClient:
    """Get configured LabArchives client from settings.

    Creates a :class:`LabArchivesClient` using credentials from the NexusLIMS
    configuration (``NX_LABARCHIVES_*`` settings).

    Returns
    -------
    LabArchivesClient
        Configured client instance

    Raises
    ------
    LabArchivesError
        If required settings are not configured

    Examples
    --------
    >>> from nexusLIMS.utils.labarchives import get_labarchives_client
    >>> client = get_labarchives_client()
    >>> nodes = client.get_tree_level("12345", "0")
    >>> folder_id = client.insert_folder("12345", "0", "My Folder")
    >>> page_id = client.insert_page("12345", folder_id, "My Page")
    """
    if not settings.NX_LABARCHIVES_ACCESS_KEY_ID:
        msg = "NX_LABARCHIVES_ACCESS_KEY_ID not configured"
        raise LabArchivesError(msg)

    if not settings.NX_LABARCHIVES_ACCESS_PASSWORD:
        msg = "NX_LABARCHIVES_ACCESS_PASSWORD not configured"
        raise LabArchivesError(msg)

    if not settings.NX_LABARCHIVES_USER_ID:
        msg = "NX_LABARCHIVES_USER_ID not configured"
        raise LabArchivesError(msg)

    if not settings.NX_LABARCHIVES_URL:
        msg = "NX_LABARCHIVES_URL not configured"
        raise LabArchivesError(msg)

    return LabArchivesClient(
        base_url=str(settings.NX_LABARCHIVES_URL),
        akid=settings.NX_LABARCHIVES_ACCESS_KEY_ID,
        password=settings.NX_LABARCHIVES_ACCESS_PASSWORD,
        uid=settings.NX_LABARCHIVES_USER_ID,
    )
