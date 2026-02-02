"""Low-level API client for eLabFTW electronic lab notebook.

This module provides a reusable client for interacting with eLabFTW's REST API v2.
It handles authentication, request/response formatting, and error handling for
CRUD operations on experiments.

eLabFTW API Documentation:
    https://doc.elabftw.net/api/v2/

Example usage:
    >>> from nexusLIMS.utils.elabftw import get_elabftw_client
    >>> client = get_elabftw_client()
    >>> exp = client.create_experiment(
    ...     title="My Experiment",
    ...     body="Experiment description",
    ...     tags=["microscopy", "nexuslims"]
    ... )
    >>> print(f"Created experiment {exp['id']}")
"""

import logging
from enum import IntEnum
from http import HTTPStatus
from pathlib import Path
from typing import Any

from nexusLIMS.config import settings
from nexusLIMS.utils.network import nexus_req

_logger = logging.getLogger(__name__)


class ELabFTWError(Exception):
    """Base exception for eLabFTW API errors."""


class ELabFTWAuthenticationError(ELabFTWError):
    """Authentication failed (invalid or missing API key)."""


class ELabFTWNotFoundError(ELabFTWError):
    """Requested resource not found (404)."""


class State(IntEnum):
    """eLabFTW experiment state enumeration.

    These states represent the lifecycle status of experiments in eLabFTW.
    Values correspond to the eLabFTW database schema.

    Attributes
    ----------
    Normal : int
        Standard active experiment (value: 1)
    Archived : int
        Experiment has been archived (value: 2)
    Deleted : int
        Experiment has been soft-deleted (value: 3)
    Pending : int
        Experiment is pending approval or processing (value: 4)
    Processing : int
        Experiment is currently being processed (value: 5)
    Error : int
        Experiment encountered an error state (value: 6)
    """

    Normal = 1
    Archived = 2
    Deleted = 3
    Pending = 4
    Processing = 5
    Error = 6


class ELabFTWClient:
    """Low-level client for eLabFTW API v2.

    This client provides basic CRUD operations for eLabFTW experiments using
    the REST API v2. It handles authentication via API key and provides
    consistent error handling.

    Parameters
    ----------
    base_url : str
        Root URL of the eLabFTW instance (e.g., "https://elabftw.example.com").
        Do not include the API path - it will be appended automatically.
    api_key : str
        API key from eLabFTW user panel. Must have write permissions for
        creating/updating experiments.

    Attributes
    ----------
    base_url : str
        Root URL of eLabFTW instance
    api_key : str
        API authentication key
    experiments_endpoint : str
        Full URL to experiments API endpoint

    Examples
    --------
    >>> client = ELabFTWClient(
    ...     base_url="https://elabftw.example.com",
    ...     api_key="your-api-key-here"
    ... )
    >>> experiments = client.list_experiments(limit=5)
    >>> for exp in experiments:
    ...     print(f"{exp['id']}: {exp['title']}")
    """

    def __init__(self, base_url: str, api_key: str):
        """Initialize eLabFTW API client.

        Parameters
        ----------
        base_url : str
            Root URL of eLabFTW instance
        api_key : str
            API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.experiments_endpoint = f"{self.base_url}/api/v2/experiments"

    def _make_request(
        self,
        method: str,
        url: str,
        json_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make authenticated HTTP request to eLabFTW API.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, PATCH, DELETE)
        url : str
            Full URL to request
        json_data : dict, optional
            JSON body for request
        files : dict, optional
            Files to upload (multipart/form-data)

        Returns
        -------
        dict or None
            Response JSON data, or None for 204 No Content

        Raises
        ------
        ELabFTWAuthenticationError
            If authentication fails (401)
        ELabFTWNotFoundError
            If resource not found (404)
        ELabFTWError
            For other API errors
        """
        headers = {"Authorization": self.api_key}

        # Make the request - wrap any network/request exceptions
        try:
            response = nexus_req(
                url,
                method,
                headers=headers,
                json=json_data,
                files=files,
            )
        except Exception as e:
            msg = f"Request to eLabFTW API failed: {e}"
            raise ELabFTWError(msg) from e

        # Handle different success status codes
        if response.status_code == HTTPStatus.NO_CONTENT:
            # No Content - successful delete
            return None

        if response.status_code == HTTPStatus.CREATED:
            # Created - eLabFTW returns Location header with experiment URL
            # Response body is typically empty
            location = response.headers.get("Location")
            if location:
                # Extract experiment ID by removing the endpoint URL
                # E.g., "http://host/api/v2/experiments/123" -> "123"
                try:
                    id_str = location.replace(url + "/", "").rstrip("/")
                    experiment_id = int(id_str)
                except ValueError as e:
                    msg = (
                        "Failed to parse experiment ID from "
                        f"Location header: {location}"
                    )
                    raise ELabFTWError(msg) from e
                else:
                    return {"id": experiment_id, "location": location}
            # Fallback: try to parse JSON response (in case API behavior changes)
            try:
                return response.json()
            except Exception:
                msg = "201 Created response missing Location header and JSON body"
                raise ELabFTWError(msg) from None

        if response.status_code == HTTPStatus.OK:
            # Success with JSON response - wrap JSON parsing exceptions
            try:
                return response.json()
            except Exception as e:
                msg = f"Failed to parse response JSON: {e}"
                raise ELabFTWError(msg) from e

        # Handle error responses
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            msg = "Authentication failed - check API key"
            raise ELabFTWAuthenticationError(msg)

        if response.status_code == HTTPStatus.NOT_FOUND:
            msg = f"Resource not found: {url}"
            raise ELabFTWNotFoundError(msg)

        # Generic error for other status codes
        msg = f"API request failed with status {response.status_code}: {response.text}"
        raise ELabFTWError(msg)

    def create_experiment(  # noqa: PLR0913
        self,
        title: str,
        body: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        category: int | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """Create a new experiment in eLabFTW.

        Parameters
        ----------
        title : str
            Experiment title (required)
        body : str, optional
            Experiment body content (supports markdown)
        tags : list of str, optional
            List of tag strings to apply
        metadata : dict, optional
            Experiment metadata. Can be either:

            1. **Flat key-value pairs** (simple):
               ``{"key": "value", "number": 123}``

            2. **eLabFTW extra_fields schema** (recommended):
               ``{``
               ``    "extra_fields": {``
               ``        "Field Name": {``
               ``            "type": "text|date|datetime-local|email|number|url|...",``
               ``            "value": "field value",``
               ``            "description": "Optional description",``
               ``            "position": 1,``
               ``            "group_id": 1,``
               ``            ...``
               ``        },``
               ``        ...``
               ``    },``
               ``    "elabftw": {``
               ``        "display_main_text": true,``
               ``        "extra_fields_groups": [``
               ``            {"id": 1, "name": "Group Name"},``
               ``            ...``
               ``        ]``
               ``    }``
               ``}``

            For extra_fields schema details, see:
            https://doc.elabftw.net/metadata.html#schema-description
        category : int, optional
            Category ID (uses eLabFTW default if not specified)
        status : int, optional
            Status ID (uses eLabFTW default if not specified)

        Returns
        -------
        dict
            Created experiment data including 'id' field

        Raises
        ------
        ELabFTWAuthenticationError
            If API key is invalid
        ELabFTWError
            If creation fails

        Examples
        --------
        Simple metadata (flat key-value pairs):

        >>> exp = client.create_experiment(
        ...     title="TEM Analysis",
        ...     body="Sample characterization with TEM",
        ...     tags=["microscopy", "analysis"],
        ...     metadata={"instrument": "FEI Titan", "operator": "jsmith"}
        ... )
        >>> print(f"Created experiment ID: {exp['id']}")

        Structured extra_fields (recommended):

        >>> exp = client.create_experiment(
        ...     title="TEM Analysis",
        ...     metadata={
        ...         "extra_fields": {
        ...             "Instrument": {
        ...                 "type": "text",
        ...                 "value": "FEI Titan",
        ...                 "description": "Instrument used",
        ...                 "position": 1,
        ...                 "group_id": 1
        ...             },
        ...             "Start Time": {
        ...                 "type": "datetime-local",
        ...                 "value": "2025-01-27T10:30",
        ...                 "description": "Session start time",
        ...                 "position": 2,
        ...                 "group_id": 1
        ...             },
        ...             "CDCS Record": {
        ...                 "type": "url",
        ...                 "value": "https://cdcs.example.com/record/123",
        ...                 "description": "Link to related CDCS record",
        ...                 "position": 3,
        ...                 "group_id": 2
        ...             }
        ...         },
        ...         "elabftw": {
        ...             "display_main_text": True,
        ...             "extra_fields_groups": [
        ...                 {"id": 1, "name": "Session Information"},
        ...                 {"id": 2, "name": "Related Records"}
        ...             ]
        ...         }
        ...     }
        ... )
        """
        payload: dict[str, Any] = {"title": title}

        if body is not None:
            payload["body"] = body

        if tags:
            # eLabFTW expects list of strings
            payload["tags"] = tags

        if metadata:
            payload["metadata"] = metadata

        if category is not None:
            payload["category"] = category

        if status is not None:
            payload["status"] = status

        _logger.debug("Creating experiment: %s", title)
        result = self._make_request(
            "POST", self.experiments_endpoint, json_data=payload
        )
        _logger.info("Created experiment %s: %s", result["id"], title)

        return result

    def get_experiment(self, experiment_id: int) -> dict[str, Any]:
        """Retrieve an experiment by ID.

        Parameters
        ----------
        experiment_id : int
            Experiment ID to retrieve

        Returns
        -------
        dict
            Full experiment data

        Raises
        ------
        ELabFTWNotFoundError
            If experiment doesn't exist
        ELabFTWError
            If retrieval fails

        Examples
        --------
        >>> exp = client.get_experiment(42)
        >>> print(exp['title'])
        """
        url = f"{self.experiments_endpoint}/{experiment_id}"
        _logger.debug("Fetching experiment %s", experiment_id)

        return self._make_request("GET", url)

    def list_experiments(
        self,
        limit: int = 15,
        offset: int = 0,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List experiments with pagination and optional search.

        Parameters
        ----------
        limit : int, default 15
            Maximum number of results to return
        offset : int, default 0
            Number of results to skip (for pagination)
        query : str, optional
            Full-text search query

        Returns
        -------
        list of dict
            List of experiment data dicts

        Raises
        ------
        ELabFTWError
            If listing fails

        Examples
        --------
        >>> # Get first 10 experiments
        >>> experiments = client.list_experiments(limit=10)
        >>>
        >>> # Search for experiments
        >>> results = client.list_experiments(query="microscopy")
        >>>
        >>> # Pagination
        >>> page2 = client.list_experiments(limit=10, offset=10)
        """
        params = {"limit": limit, "offset": offset}

        if query:
            params["q"] = query

        # Build URL with query parameters
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.experiments_endpoint}?{param_str}"

        _logger.debug(
            "Listing experiments (limit=%s, offset=%s, query=%s)",
            limit,
            offset,
            query,
        )

        return self._make_request("GET", url)

    def update_experiment(  # noqa: PLR0913
        self,
        experiment_id: int,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        category: int | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing experiment.

        Only fields provided as arguments will be updated. Other fields
        remain unchanged.

        Parameters
        ----------
        experiment_id : int
            ID of experiment to update
        title : str, optional
            New title
        body : str, optional
            New body content
        tags : list of str, optional
            New tag list (replaces existing tags)
        metadata : dict, optional
            New metadata (replaces existing metadata). Can be either:

            1. **Flat key-value pairs** (simple):
               ``{"key": "value", "number": 123}``

            2. **eLabFTW extra_fields schema** (recommended):
               See ``create_experiment()`` for full schema documentation.

            For extra_fields schema details, see:
            https://doc.elabftw.net/metadata.html#schema-description
        category : int, optional
            New category ID
        status : int, optional
            New status ID

        Returns
        -------
        dict
            Updated experiment data

        Raises
        ------
        ELabFTWNotFoundError
            If experiment doesn't exist
        ELabFTWError
            If update fails

        Examples
        --------
        Update title only:

        >>> client.update_experiment(42, title="New Title")

        Update multiple fields with flat metadata:

        >>> client.update_experiment(
        ...     42,
        ...     body="Updated description",
        ...     tags=["new-tag"],
        ...     metadata={"updated": "2025-01-31"}
        ... )

        Update with extra_fields schema:

        >>> client.update_experiment(
        ...     42,
        ...     metadata={
        ...         "extra_fields": {
        ...             "Status": {
        ...                 "type": "text",
        ...                 "value": "Completed",
        ...                 "description": "Experiment status",
        ...                 "position": 1
        ...             }
        ...         },
        ...         "elabftw": {"display_main_text": True}
        ...     }
        ... )
        """
        url = f"{self.experiments_endpoint}/{experiment_id}"
        payload: dict[str, Any] = {}

        if title is not None:
            payload["title"] = title

        if body is not None:
            payload["body"] = body

        if tags is not None:
            payload["tags"] = "|".join(tags)

        if metadata is not None:
            payload["metadata"] = metadata

        if category is not None:
            payload["category"] = category

        if status is not None:
            payload["status"] = status

        _logger.debug("Updating experiment %s", experiment_id)
        result = self._make_request("PATCH", url, json_data=payload)
        _logger.info("Updated experiment %s", experiment_id)

        return result

    def delete_experiment(self, experiment_id: int) -> None:
        """Delete an experiment.

        Note: This is a soft delete in eLabFTW - the experiment is marked
        as deleted but can be restored by administrators.

        Parameters
        ----------
        experiment_id : int
            ID of experiment to delete

        Raises
        ------
        ELabFTWNotFoundError
            If experiment doesn't exist
        ELabFTWError
            If deletion fails

        Examples
        --------
        >>> client.delete_experiment(42)
        """
        url = f"{self.experiments_endpoint}/{experiment_id}"
        _logger.debug("Deleting experiment %s", experiment_id)

        self._make_request("DELETE", url)
        _logger.info("Deleted experiment %s", experiment_id)

    def upload_file_to_experiment(
        self,
        experiment_id: int,
        file_path: Path | str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file as attachment to an experiment.

        Parameters
        ----------
        experiment_id : int
            ID of experiment to attach file to
        file_path : Path or str
            Path to file to upload
        comment : str, optional
            Comment/description for the uploaded file

        Returns
        -------
        dict
            Upload result data

        Raises
        ------
        FileNotFoundError
            If file doesn't exist
        ELabFTWNotFoundError
            If experiment doesn't exist
        ELabFTWError
            If upload fails

        Examples
        --------
        >>> result = client.upload_file_to_experiment(
        ...     experiment_id=42,
        ...     file_path="data.xml",
        ...     comment="NexusLIMS XML record"
        ... )
        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        url = f"{self.experiments_endpoint}/{experiment_id}/uploads"

        # Prepare multipart/form-data upload
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "application/octet-stream")}

            # Add comment as form data if provided
            data = {"comment": comment} if comment else None

            _logger.debug(
                "Uploading %s to experiment %s", file_path.name, experiment_id
            )

            # Note: When files are provided, nexus_req sends as multipart/form-data
            # We need to pass data as form data, not json
            response = nexus_req(
                url,
                "POST",
                headers={"Authorization": self.api_key},
                data=data,
                files=files,
            )

            if response.status_code == HTTPStatus.CREATED:
                _logger.info(
                    "Uploaded %s to experiment %s", file_path.name, experiment_id
                )
                # eLabFTW returns Location header with upload URL
                location = response.headers.get("Location")
                if location:
                    # Extract upload ID from URL
                    try:
                        id_str = location.replace(url + "/", "").rstrip("/")
                        upload_id = int(id_str)
                    except ValueError as e:
                        msg = (
                            "Failed to parse upload ID from "
                            f"Location header: {location}"
                        )
                        raise ELabFTWError(msg) from e
                    else:
                        return {"id": upload_id, "location": location}
                # Fallback: try to parse JSON response
                try:
                    return response.json()
                except Exception:
                    msg = "201 Created response missing Location header and JSON body"
                    raise ELabFTWError(msg) from None

            if response.status_code == HTTPStatus.UNAUTHORIZED:
                msg = "Authentication failed - check API key"
                raise ELabFTWAuthenticationError(msg)

            if response.status_code == HTTPStatus.NOT_FOUND:
                msg = f"Experiment {experiment_id} not found"
                raise ELabFTWNotFoundError(msg)

            msg = (
                f"File upload failed with status "
                f"{response.status_code}: {response.text}"
            )
            raise ELabFTWError(msg)


def get_elabftw_client() -> ELabFTWClient:
    """Get configured eLabFTW client from settings.

    Convenience function that creates a client using credentials from
    the NexusLIMS configuration.

    Returns
    -------
    ELabFTWClient
        Configured client instance

    Raises
    ------
    ValueError
        If NX_ELABFTW_API_KEY or NX_ELABFTW_URL not configured

    Examples
    --------
    >>> from nexusLIMS.utils.elabftw import get_elabftw_client
    >>> client = get_elabftw_client()
    >>> experiments = client.list_experiments(limit=10)
    """
    if not settings.NX_ELABFTW_API_KEY:
        msg = "NX_ELABFTW_API_KEY not configured"
        raise ValueError(msg)

    if not settings.NX_ELABFTW_URL:
        msg = "NX_ELABFTW_URL not configured"
        raise ValueError(msg)

    return ELabFTWClient(
        base_url=str(settings.NX_ELABFTW_URL),
        api_key=settings.NX_ELABFTW_API_KEY,
    )
