"""
A module to handle the uploading of previously-built XML records to a CDCS instance.

See https://github.com/usnistgov/NexusLIMS-CDCS for more details on the NexusLIMS
customizations to the CDCS application.

This module can also be run directly to upload records to a CDCS instance without
invoking the record builder.
"""

import argparse
import logging
import sys
from http import HTTPStatus
from pathlib import Path
from typing import List, TypedDict
from urllib.parse import urljoin

from requests.models import Response
from tqdm import tqdm

from nexusLIMS.config import settings
from nexusLIMS.utils import AuthenticationError, nexus_req

logging.basicConfig()
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


class CDCSDataRecord(TypedDict):
    """Type definition for a CDCS Data record returned by the API.

    This represents the structure of record objects returned by CDCS endpoints
    like /rest/data/query/ and /rest/data/query/keyword/.
    """

    id: int
    template: int
    workspace: int | None
    user_id: str
    title: str
    checksum: str | None
    creation_date: str | None
    last_modification_date: str | None
    last_change_date: str | None
    xml_content: str


def get_cdcs_url() -> str:
    """
    Return the url to the NexusLIMS CDCS instance by fetching it from the environment.

    Returns
    -------
    url : str
        The URL of the NexusLIMS CDCS instance to use

    Raises
    ------
    ValueError
        If the ``NX_CDCS_URL`` setting is not defined, raise a ``ValueError``
    """
    # NX_CDCS_URL is required, so validation ensures it exists
    # Convert AnyHttpUrl to string
    return str(settings.NX_CDCS_URL)


def get_workspace_id() -> int:
    """
    Get the workspace ID that the user has access to.

    This should be the Global Public Workspace in the current NexusLIMS CDCS
    implementation.

    Returns
    -------
    workspace_id : int
        The workspace ID
    """
    # assuming there's only one workspace for this user (that is the public
    # workspace)
    _endpoint = urljoin(get_cdcs_url(), "rest/workspace/read_access")
    _r = nexus_req(_endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)
    if _r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    return _r.json()[0]["id"]  # return workspace id


def get_template_id() -> str:
    """
    Get the template ID for the schema (so the record can be associated with it).

    Returns
    -------
    template_id : str
        The template ID
    """
    # get the current template (XSD) id value:
    _endpoint = urljoin(get_cdcs_url(), "rest/template-version-manager/global")
    _r = nexus_req(_endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)
    if _r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        msg = (
            "Could not authenticate to CDCS. Is the NX_CDCS_TOKEN "
            "environment variable set correctly?"
        )
        raise AuthenticationError(msg)

    return _r.json()[0]["current"]  # return template id


def upload_record_content(xml_content, title) -> tuple[Response, int | None]:
    """
    Upload a single XML record to the NexusLIMS CDCS instance.

    Parameters
    ----------
    xml_content : str
        The actual content of an XML record (rather than a file)
    title : str
        The title to give to the record in CDCS

    Returns
    -------
    post_r : :py:class:`~requests.Response`
        The REST response returned from the CDCS instance after attempting
        the upload
    record_id : int | None
        The id (on the server) of the record that was uploaded, or None if error
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


def delete_record(record_id):
    """
    Delete a Data record from the NexusLIMS CDCS instance via REST API.

    Parameters
    ----------
    record_id : str
        The id value (on the CDCS server) of the record to be deleted

    Returns
    -------
    response : :py:class:`~requests.Response`
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
    """
    Search for records in the CDCS instance by title, keyword, or other criteria.

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
    title : str, optional
        The title to search for (exact match). Only used when ``keyword`` is None.
    template_id : str, optional
        The template ID to filter by. Can be combined with either ``title`` or
        ``keyword``.
    keyword : str, optional
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


def download_record(record_id) -> str:
    """
    Download the XML content of a record from the CDCS instance.

    Parameters
    ----------
    record_id : str
        The id value (on the CDCS server) of the record to download

    Returns
    -------
    xml_content : str
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


def upload_record_files(
    files_to_upload: List[Path] | None,
    *,
    progress: bool = False,
) -> tuple[List[Path], List[int]]:
    """
    Upload record files to CDCS.

    Upload a list of .xml files (or all .xml files in the current directory)
    to the NexusLIMS CDCS instance using :py:meth:`upload_record_content`.

    Parameters
    ----------
    files_to_upload : typing.Optional[typing.List[pathlib.Path]]
        The list of .xml files to upload. If ``None``, all .xml files in the
        current directory will be used instead.
    progress : bool
        Whether to show a progress bar for uploading

    Returns
    -------
    files_uploaded : list of pathlib.Path
        A list of the files that were successfully uploaded
    record_ids : list of int
        A list of the record id values (on the server) that were uploaded
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


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Communicate with the Nexus CDCS instance",
    )
    parser.add_argument(
        "--upload-records",
        help="Upload .xml records to the Nexus CDCS",
        action="store_true",
    )
    parser.add_argument(
        "xml",
        nargs="*",
        help="(used with --upload-records) "
        "Files to upload (separated by space and "
        "surrounded by quotes, if needed). If no files "
        "are specified, all .xml files in the current "
        "directory will be used instead.",
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()

    if args.upload_records:
        if len(sys.argv) == 2:  # noqa: PLR2004
            # no files were provided, so assume the user wanted to glob all
            # .xml files in the current directory
            upload_record_files(None)
        elif len(sys.argv) > 2:  # noqa: PLR2004
            upload_record_files(args.xml)
