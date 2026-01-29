"""CDCS export destination plugin.

Exports NexusLIMS XML records to a CDCS (Configurable Data Curation System)
instance using the CDCS REST API.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from urllib.parse import urljoin

from nexusLIMS.config import settings
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.utils.cdcs import AuthenticationError
from nexusLIMS.utils.network import nexus_req

_logger = logging.getLogger(__name__)


class CDCSDestination:
    """CDCS export destination plugin.

    Uploads NexusLIMS XML records to a CDCS instance and assigns them
    to the configured workspace.

    Attributes
    ----------
    name : str
        Destination identifier: "cdcs"
    priority : int
        Export priority: 100 (high priority, runs first)
    """

    name = "cdcs"
    priority = 100

    @property
    def enabled(self) -> bool:
        """Check if CDCS is configured and enabled.

        Returns
        -------
        bool
            True if both NX_CDCS_TOKEN and NX_CDCS_URL are configured
        """
        return (
            hasattr(settings, "NX_CDCS_TOKEN")
            and hasattr(settings, "NX_CDCS_URL")
            and settings.NX_CDCS_TOKEN is not None
            and settings.NX_CDCS_URL is not None
        )

    def validate_config(self) -> tuple[bool, str | None]:  # noqa: PLR0911
        """Validate CDCS configuration.

        Tests:
        - NX_CDCS_TOKEN is configured
        - NX_CDCS_URL is configured
        - Can authenticate to CDCS API

        Returns
        -------
        tuple[bool, str | None]
            (is_valid, error_message)
        """
        if not hasattr(settings, "NX_CDCS_TOKEN"):
            return False, "NX_CDCS_TOKEN not configured"
        if not settings.NX_CDCS_TOKEN:
            return False, "NX_CDCS_TOKEN is empty"
        if not hasattr(settings, "NX_CDCS_URL"):
            return False, "NX_CDCS_URL not configured"
        if not settings.NX_CDCS_URL:
            return False, "NX_CDCS_URL is empty"

        # Test authentication by getting workspace ID
        try:
            self._get_workspace_id()
        except AuthenticationError as e:
            return False, f"CDCS authentication failed: {e}"
        except Exception as e:
            return False, f"CDCS configuration error: {e}"

        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to CDCS.

        Reads the XML file, uploads it to CDCS, and assigns it to the
        configured workspace. Never raises exceptions - all errors are
        caught and returned as ExportResult with success=False.

        Parameters
        ----------
        context
            Export context with file path and session metadata

        Returns
        -------
        ExportResult
            Result of the export attempt
        """
        try:
            # Read XML content
            with context.xml_file_path.open(encoding="utf-8") as f:
                xml_content = f.read()

            # Upload to CDCS
            title = context.xml_file_path.stem
            record_id, record_url = self._upload_to_cdcs(xml_content, title)

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=str(record_id),
                record_url=record_url,
            )

        except Exception as e:
            _logger.exception(
                "Failed to export to CDCS: %s",
                context.xml_file_path.name,
            )
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )

    def _upload_to_cdcs(self, xml_content: str, title: str) -> tuple[int, str]:
        """Upload XML to CDCS and return (record_id, record_url).

        Parameters
        ----------
        xml_content
            XML content to upload
        title
            Title for the record

        Returns
        -------
        tuple[int, str]
            (record_id, record_url)

        Raises
        ------
        RuntimeError
            If upload fails
        """
        endpoint = urljoin(str(settings.NX_CDCS_URL), "rest/data/")

        payload = {
            "template": self._get_template_id(),
            "title": title,
            "xml_content": xml_content,
        }

        post_r = nexus_req(
            endpoint, "POST", json=payload, token_auth=settings.NX_CDCS_TOKEN
        )

        if post_r.status_code != HTTPStatus.CREATED:
            msg = f"CDCS upload failed: {post_r.text}"
            raise RuntimeError(msg)

        record_id = post_r.json()["id"]

        # Assign to workspace
        wrk_endpoint = urljoin(
            str(settings.NX_CDCS_URL),
            f"rest/data/{record_id}/assign/{self._get_workspace_id()}",
        )
        _ = nexus_req(wrk_endpoint, "PATCH", token_auth=settings.NX_CDCS_TOKEN)

        record_url = urljoin(str(settings.NX_CDCS_URL), f"data?id={record_id}")
        _logger.info('Record "%s" available at %s', title, record_url)

        return record_id, record_url

    def _get_template_id(self) -> str:
        """Get current template ID from CDCS.

        Returns
        -------
        str
            Template ID

        Raises
        ------
        AuthenticationError
            If authentication fails
        """
        endpoint = urljoin(
            str(settings.NX_CDCS_URL), "rest/template-version-manager/global"
        )
        r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)

        if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            msg = "Could not authenticate to CDCS"
            raise AuthenticationError(msg)

        return r.json()[0]["current"]

    def _get_workspace_id(self) -> int:
        """Get workspace ID from CDCS.

        Returns
        -------
        int
            Workspace ID

        Raises
        ------
        AuthenticationError
            If authentication fails
        """
        endpoint = urljoin(str(settings.NX_CDCS_URL), "rest/workspace/read_access")
        r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)

        if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            msg = "Could not authenticate to CDCS"
            raise AuthenticationError(msg)

        return r.json()[0]["id"]
