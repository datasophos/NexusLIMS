"""CDCS interaction utilities for NexusLIMS.

This module provides functions for querying, downloading, and deleting records
from a CDCS instance. These are non-export operations used primarily for
testing and maintenance.

For exporting records to CDCS, use the CDCSDestination plugin in
nexusLIMS.exporters.destinations.cdcs instead.
"""

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

from tqdm import tqdm

from nexusLIMS.config import settings
from nexusLIMS.utils.network import nexus_req

_logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Class for showing an exception having to do with authentication."""

    def __init__(self, message):
        self.message = message


class CDCSDataRecord(Dict[str, Any]):
    """Type definition for a CDCS Data record returned by the API.

    This represents the structure of record objects returned by CDCS endpoints
    like /rest/data/query/ and /rest/data/query/keyword/.

    Attributes
    ----------
    id : int
        The record ID
    template : int
        The template ID
    workspace : int | None
        The workspace ID
    user_id : str
        The user ID that created the record
    title : str
        The record title
    checksum : str | None
        The record checksum
    creation_date : str | None
        The record creation date
    last_modification_date : str | None
        The last modification date
    last_change_date : str | None
        The last change date
    xml_content : str
        The XML content of the record
    """


def get_cdcs_url() -> str:
    """Return the URL to the NexusLIMS CDCS instance from environment.

    Returns
    -------
    str
        The URL of the NexusLIMS CDCS instance to use

    Raises
    ------
    ValueError
        If the NX_CDCS_URL setting is not defined
    """
    # NX_CDCS_URL is required, so validation ensures it exists
    # Convert AnyHttpUrl to string
    return str(settings.NX_CDCS_URL)


def get_workspace_id() -> int:
    """Get the workspace ID that the user has access to.

    This should be the Global Public Workspace in the current NexusLIMS CDCS
    implementation.

    Returns
    -------
    int
        The workspace ID

    Raises
    ------
    AuthenticationError
        If authentication to CDCS fails
    """
    # assuming there's only one workspace for this user (that is the public
    # workspace)
    endpoint = urljoin(get_cdcs_url(), "rest/workspace/read_access")
    r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)
    if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    return r.json()[0]["id"]  # return workspace id


def get_template_id() -> str:
    """Get the template ID for the schema.

    Returns the template ID so records can be associated with the correct schema.

    Returns
    -------
    str
        The template ID

    Raises
    ------
    AuthenticationError
        If authentication to CDCS fails
    """
    # get the current template (XSD) id value:
    endpoint = urljoin(get_cdcs_url(), "rest/template-version-manager/global")
    r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)
    if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    return r.json()[0]["current"]  # return template id


def delete_record(record_id: str):
    """Delete a Data record from the NexusLIMS CDCS instance via REST API.

    Parameters
    ----------
    record_id
        The id value (on the CDCS server) of the record to be deleted

    Returns
    -------
    requests.Response
        The REST response returned from the CDCS instance after attempting
        the delete operation
    """
    endpoint = urljoin(get_cdcs_url(), f"rest/data/{record_id}")
    response = nexus_req(endpoint, "DELETE", token_auth=settings.NX_CDCS_TOKEN)
    if response.status_code != HTTPStatus.NO_CONTENT:
        # anything other than 204 status means something went wrong
        _logger.error("Received error while deleting %s:\n%s", record_id, response.text)
    return response


def search_records(
    title: str | None = None,
    template_id: str | None = None,
    keyword: str | None = None,
) -> list[CDCSDataRecord]:
    """Search for records in the CDCS instance by title, keyword, or criteria.

    This function uses the CDCS query endpoint to search for records.
    If no parameters are provided, all records are returned.

    Note
    ----
    If ``keyword`` is provided, it takes precedence and the ``title`` parameter
    is ignored. The keyword search uses a different CDCS endpoint
    (``/rest/data/query/keyword/``) that performs full-text search but does not
    support title filtering. In this mode, only ``template_id`` can be combined
    with ``keyword`` to filter results.

    Parameters
    ----------
    title
        The title to search for (exact match). Only used when ``keyword`` is None.
    template_id
        The template ID to filter by. Can be combined with either ``title`` or
        ``keyword``.
    keyword
        Keyword(s) for full-text search across record content. When provided,
        takes precedence over ``title`` parameter.

    Returns
    -------
    list[CDCSDataRecord]
        List of matching record objects from CDCS. Each record is a dictionary
        containing id, title, xml_content, template, workspace, user_id, checksum,
        and date fields. See :class:`CDCSDataRecord` for complete structure.

    Raises
    ------
    AuthenticationError
        If authentication fails
    ValueError
        If keyword parameter is empty or search parameters are invalid
    """
    if keyword is not None and not keyword.strip():
        msg = "Keyword parameter cannot be empty"
        raise ValueError(msg)

    # Use keyword search endpoint if keyword is provided
    if keyword is not None:
        endpoint = urljoin(get_cdcs_url(), "rest/data/query/keyword/")
        payload = {
            "query": keyword,
            "all": "true",  # Return all results (not paginated)
        }
        if template_id is not None:
            payload["templates"] = [{"id": template_id}]
    else:
        endpoint = urljoin(get_cdcs_url(), "rest/data/query/")
        # Build query payload
        # The query endpoint expects a POST with JSON body
        payload = {
            "query": {},  # Empty query matches all records
            "all": "true",  # Return all results (not paginated)
        }
        if title is not None:
            payload["title"] = title
        if template_id is not None:
            payload["templates"] = [{"id": template_id}]

    response = nexus_req(
        endpoint, "POST", json=payload, token_auth=settings.NX_CDCS_TOKEN
    )

    if response.status_code == HTTPStatus.UNAUTHORIZED:
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    if response.status_code == HTTPStatus.BAD_REQUEST:
        _logger.error("Bad request while searching records:\n%s", response.text)
        msg = f"Invalid search parameters: {response.text}"
        raise ValueError(msg)

    if response.status_code != HTTPStatus.OK:
        _logger.error("Got error while searching records:\n%s", response.text)
        return []

    return response.json()


def download_record(record_id: str) -> str:
    """Download the XML content of a record from the CDCS instance.

    Parameters
    ----------
    record_id
        The id value (on the CDCS server) of the record to download

    Returns
    -------
    str
        The XML content of the record

    Raises
    ------
    AuthenticationError
        If authentication fails
    ValueError
        If the record is not found or another error occurs
    """
    endpoint = urljoin(get_cdcs_url(), f"rest/data/download/{record_id}/")
    response = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)

    if response.status_code == HTTPStatus.UNAUTHORIZED:
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    if response.status_code == HTTPStatus.NOT_FOUND:
        msg = f"Record with id {record_id} not found"
        raise ValueError(msg)

    if response.status_code != HTTPStatus.OK:
        _logger.error("Got error while downloading %s:\n%s", record_id, response.text)
        msg = f"Failed to download record {record_id}: {response.text}"
        raise ValueError(msg)

    return response.text


def upload_record_content(xml_content: str, title: str) -> tuple[Any, int | None]:
    """Upload a single XML record to the NexusLIMS CDCS instance.

    Note
    ----
    This is a low-level utility function primarily used for testing.
    For production record uploads, use the CDCSDestination exporter plugin
    in nexusLIMS.exporters.destinations.cdcs instead.

    Parameters
    ----------
    xml_content
        The actual content of an XML record (rather than a file)
    title
        The title to give to the record in CDCS

    Returns
    -------
    tuple[requests.Response, int | None]
        A tuple of (response, record_id). The response is the REST response
        returned from the CDCS instance after attempting the upload.
        The record_id is the id (on the server) of the record that was uploaded,
        or None if there was an error.
    """
    endpoint = urljoin(get_cdcs_url(), "rest/data/")

    payload = {
        "template": get_template_id(),
        "title": title,
        "xml_content": xml_content,
    }

    post_r = nexus_req(
        endpoint, "POST", json=payload, token_auth=settings.NX_CDCS_TOKEN
    )

    if post_r.status_code != HTTPStatus.CREATED:
        # anything other than 201 status means something went wrong
        _logger.error("Got error while uploading %s:\n%s", title, post_r.text)
        return post_r, None

    # assign this record to the public workspace
    record_id = post_r.json()["id"]
    record_url = urljoin(get_cdcs_url(), f"data?id={record_id}")
    wrk_endpoint = urljoin(
        get_cdcs_url(),
        f"rest/data/{record_id}/assign/{get_workspace_id()}",
    )

    _ = nexus_req(wrk_endpoint, "PATCH", token_auth=settings.NX_CDCS_TOKEN)

    _logger.info('Record "%s" available at %s', title, record_url)
    return post_r, record_id


def upload_record_files(
    files_to_upload: List[Path] | None,
    *,
    progress: bool = False,
) -> tuple[List[Path], List[int]]:
    """Upload record files to CDCS.

    Upload a list of .xml files (or all .xml files in the current directory)
    to the NexusLIMS CDCS instance using :py:meth:`upload_record_content`.

    Note
    ----
    This is a utility function primarily used for testing and manual uploads.
    For production record uploads, use the CDCSDestination exporter plugin
    in nexusLIMS.exporters.destinations.cdcs instead.

    Parameters
    ----------
    files_to_upload: List[pathlib.Path] | None
        The list of .xml files to upload. If ``None``, all .xml files in the
        current directory will be used instead.
    progress
        Whether to show a progress bar for uploading

    Returns
    -------
    tuple[list[pathlib.Path], list[int]]
        A tuple of (files_uploaded, record_ids). files_uploaded is a list of
        the files that were successfully uploaded. record_ids is a list of the
        record id values (on the server) that were uploaded.

    Raises
    ------
    ValueError
        If no .xml files are found
    """
    if files_to_upload is None:
        _logger.info("Using all .xml files in this directory")
        files_to_upload = list(Path().glob("*.xml"))
    else:
        _logger.info("Using .xml files from command line")

    _logger.info("Found %s files to upload\n", len(files_to_upload))
    if len(files_to_upload) == 0:
        msg = (
            "No .xml files were found (please specify on the "
            "command line, or run this script from a directory "
            "containing one or more .xml files"
        )
        _logger.error(msg)
        raise ValueError(msg)

    files_uploaded = []
    record_ids = []

    for f in tqdm(files_to_upload) if progress else files_to_upload:
        f_path = Path(f)
        with f_path.open(encoding="utf-8") as xml_file:
            xml_content = xml_file.read()

        title = f_path.stem
        response, record_id = upload_record_content(xml_content, title)

        if response.status_code != HTTPStatus.CREATED:
            _logger.warning("Could not upload %s", f_path.name)
            continue

        files_uploaded.append(f_path)
        record_ids.append(record_id)

    _logger.info(
        "Successfully uploaded %i of %i files",
        len(files_uploaded),
        len(files_to_upload),
    )

    return files_uploaded, record_ids
