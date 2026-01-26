"""LabArchives export destination plugin.

Exports NexusLIMS XML records to a LabArchives instance using the LabArchives
API. This is a skeleton implementation to be completed once the API details
are known.
"""

from __future__ import annotations

import logging

from nexusLIMS.config import settings
from nexusLIMS.exporters.base import ExportContext, ExportResult

_logger = logging.getLogger(__name__)


class LabArchivesDestination:
    """LabArchives export destination plugin.

    Uploads NexusLIMS XML records to a LabArchives instance and creates
    appropriate notebook entries.

    Attributes
    ----------
    name : str
        Destination identifier: "labarchives"
    priority : int
        Export priority: 90 (runs after CDCS at 100, allowing access to CDCS URLs)
    """

    name = "labarchives"
    priority = 90

    @property
    def enabled(self) -> bool:
        """Check if LabArchives is configured and enabled.

        Returns
        -------
        bool
            True if both NX_LABARCHIVES_API_KEY and NX_LABARCHIVES_URL are configured
        """
        return (
            hasattr(settings, "NX_LABARCHIVES_API_KEY")
            and hasattr(settings, "NX_LABARCHIVES_URL")
            and settings.NX_LABARCHIVES_API_KEY is not None
            and settings.NX_LABARCHIVES_URL is not None
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate LabArchives configuration.

        Tests:
        - NX_LABARCHIVES_API_KEY is configured
        - NX_LABARCHIVES_URL is configured
        - Can authenticate to LabArchives API (TODO: implement once API is known)

        Returns
        -------
        tuple[bool, str | None]
            (is_valid, error_message)
        """
        if not hasattr(settings, "NX_LABARCHIVES_API_KEY"):
            return False, "NX_LABARCHIVES_API_KEY not configured"
        if not settings.NX_LABARCHIVES_API_KEY:
            return False, "NX_LABARCHIVES_API_KEY is empty"
        if not hasattr(settings, "NX_LABARCHIVES_URL"):
            return False, "NX_LABARCHIVES_URL not configured"
        if not settings.NX_LABARCHIVES_URL:
            return False, "NX_LABARCHIVES_URL is empty"

        # TODO: Test authentication once API details are known
        # For now, just validate the config variables exist
        _logger.warning(
            "LabArchives authentication validation not yet implemented - "
            "skipping connectivity check"
        )

        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to LabArchives.

        Reads the XML file and creates an appropriate LabArchives entry.
        Can optionally include links to CDCS or other destinations if they
        have already run successfully (via context.previous_results).

        Never raises exceptions - all errors are caught and returned as
        ExportResult with success=False.

        Parameters
        ----------
        context
            Export context with file path, session metadata, and results
            from higher-priority destinations (e.g., CDCS)

        Returns
        -------
        ExportResult
            Result of the export attempt
        """
        try:
            # Read XML content
            with context.xml_file_path.open(encoding="utf-8") as f:
                xml_content = f.read()

            # Check if CDCS export was successful (for potential linking)
            cdcs_result = context.get_result("cdcs")
            cdcs_url = (
                cdcs_result.record_url if cdcs_result and cdcs_result.success else None
            )

            # Upload to LabArchives
            entry_id, entry_url = self._upload_to_labarchives(
                xml_content=xml_content,
                title=context.xml_file_path.stem,
                session_id=context.session_identifier,
                instrument_id=context.instrument_pid,
                cdcs_url=cdcs_url,
            )

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=str(entry_id),
                record_url=entry_url,
            )

        except Exception as e:
            _logger.exception(
                "Failed to export to LabArchives: %s",
                context.xml_file_path.name,
            )
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )

    def _upload_to_labarchives(
        self,
        xml_content: str,
        title: str,
        session_id: str,
        instrument_id: str,
        cdcs_url: str | None = None,
    ) -> tuple[str, str]:
        """Upload content to LabArchives and return (entry_id, entry_url).

        TODO: Implement once LabArchives API details are known.

        Parameters
        ----------
        xml_content
            XML content to upload
        title
            Title for the entry
        session_id
            Session identifier
        instrument_id
            Instrument identifier
        cdcs_url
            Optional URL to CDCS record (for cross-linking)

        Returns
        -------
        tuple[str, str]
            (entry_id, entry_url)

        Raises
        ------
        NotImplementedError
            Until API details are known
        RuntimeError
            If upload fails
        """
        # TODO: Implement LabArchives API integration
        # This is a placeholder that should be replaced with actual API calls
        # once the LabArchives API documentation is available.
        #
        # Expected workflow (to be confirmed):
        # 1. Authenticate using API key
        # 2. Create or identify target notebook/folder
        # 3. Create new entry with XML content (or attach as file)
        # 4. Optionally include link to CDCS record
        # 5. Return entry ID and URL
        #
        # Implementation notes:
        # - You may need: from http import HTTPStatus
        # - You may need: from urllib.parse import urljoin
        # - You may need: from nexusLIMS.utils.network import nexus_req
        # - Construct API endpoint: urljoin(str(settings.NX_LABARCHIVES_URL), "api/...")
        # - Prepare payload with title, content, and notebook_id
        # - Include cdcs_url in payload if available for cross-linking
        # - Make POST request with API key authentication
        # - Parse response to get entry_id and construct entry_url

        msg = (
            "LabArchives API integration not yet implemented. "
            "Please refer to LabArchives API documentation and complete "
            "this method in nexusLIMS/exporters/destinations/labarchives.py"
        )
        raise NotImplementedError(msg)

    def _get_notebook_id(self, instrument_id: str) -> str:
        """Get or create notebook ID for an instrument.

        TODO: Implement once LabArchives API details are known.

        Parameters
        ----------
        instrument_id
            Instrument identifier

        Returns
        -------
        str
            Notebook ID for this instrument

        Raises
        ------
        NotImplementedError
            Until API details are known
        """
        # TODO: Implement LabArchives notebook management
        # Expected workflow:
        # 1. Query API for existing notebook by instrument_id
        # 2. If found, return notebook ID
        # 3. If not found, create new notebook with name "NexusLIMS - {instrument_id}"
        # 4. Return newly created notebook ID

        msg = (
            "LabArchives notebook management not yet implemented. "
            "Complete this method based on LabArchives API documentation."
        )
        raise NotImplementedError(msg)
