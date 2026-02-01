"""eLabFTW export destination plugin.

Exports NexusLIMS XML records to eLabFTW electronic lab notebook by creating
experiments with markdown summaries and attaching the full XML record.
"""

from __future__ import annotations

import logging

from nexusLIMS.config import settings
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.utils.elabftw import (
    ELabFTWAuthenticationError,
    get_elabftw_client,
)

_logger = logging.getLogger(__name__)


class ELabFTWDestination:
    """eLabFTW export destination plugin.

    Creates one eLabFTW experiment per NexusLIMS session, with a markdown
    summary of the session and the full XML record attached as a file.

    Attributes
    ----------
    name : str
        Destination identifier: "elabftw"
    priority : int
        Export priority: 85 (after CDCS but before LabArchives)
    """

    name = "elabftw"
    priority = 85  # After CDCS (100), before LabArchives (90)

    @property
    def enabled(self) -> bool:
        """Check if eLabFTW is configured and enabled.

        Returns
        -------
        bool
            True if both NX_ELABFTW_API_KEY and NX_ELABFTW_URL are configured
        """
        return (
            settings.NX_ELABFTW_API_KEY is not None
            and settings.NX_ELABFTW_API_KEY != ""
            and settings.NX_ELABFTW_URL is not None
            and settings.NX_ELABFTW_URL != ""
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate eLabFTW configuration.

        Tests:
        - NX_ELABFTW_API_KEY is configured
        - NX_ELABFTW_URL is configured
        - Can authenticate to eLabFTW API

        Returns
        -------
        tuple[bool, str | None]
            (is_valid, error_message)
        """
        if not settings.NX_ELABFTW_API_KEY:
            return False, "NX_ELABFTW_API_KEY not configured"

        if not settings.NX_ELABFTW_URL:
            return False, "NX_ELABFTW_URL not configured"

        # Test authentication by listing experiments (limit 1)
        try:
            client = get_elabftw_client()
            client.list_experiments(limit=1)
        except ELabFTWAuthenticationError as e:
            return False, f"eLabFTW authentication failed: {e}"
        except Exception as e:
            return False, f"eLabFTW configuration error: {e}"

        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to eLabFTW.

        Creates an experiment with a markdown summary of the session,
        then attaches the XML record file. Never raises exceptions - all
        errors are caught and returned as ExportResult with success=False.

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
            # Get eLabFTW client
            client = get_elabftw_client()

            # Build experiment content
            title = self._build_title(context)
            body = self._build_markdown_body(context)
            tags = self._build_tags(context)
            metadata = self._build_metadata(context)

            # Create experiment
            experiment = client.create_experiment(
                title=title,
                body=body,
                tags=tags,
                metadata=metadata,
                category=settings.NX_ELABFTW_EXPERIMENT_CATEGORY,
                status=settings.NX_ELABFTW_EXPERIMENT_STATUS,
            )

            experiment_id = experiment["id"]
            _logger.info("Created eLabFTW experiment %s: %s", experiment_id, title)

            # Upload XML file as attachment
            client.upload_file_to_experiment(
                experiment_id=experiment_id,
                file_path=context.xml_file_path,
                comment="NexusLIMS XML record",
            )

            # Build experiment URL
            experiment_url = (
                f"{settings.NX_ELABFTW_URL}/"
                f"experiments.php?mode=view&id={experiment_id}"
            )

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=str(experiment_id),
                record_url=experiment_url,
            )

        except Exception as e:
            _logger.exception(
                "Failed to export to eLabFTW: %s",
                context.xml_file_path.name,
            )
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )

    def _build_title(self, context: ExportContext) -> str:
        """Build experiment title.

        Parameters
        ----------
        context
            Export context

        Returns
        -------
        str
            Title in format: "NexusLIMS - {instrument} - {session_id}"
        """
        return f"NexusLIMS - {context.instrument_pid} - {context.session_identifier}"

    def _build_markdown_body(self, context: ExportContext) -> str:
        """Build markdown body for experiment.

        Parameters
        ----------
        context
            Export context

        Returns
        -------
        str
            Markdown-formatted body with session details and CDCS link
        """
        lines = [
            "# NexusLIMS Microscopy Session",
            "",
            "## Session Details",
            f"- **Session ID**: {context.session_identifier}",
            f"- **Instrument**: {context.instrument_pid}",
        ]

        # Add user if available
        if context.user:
            lines.append(f"- **User**: {context.user}")

        # Add timestamps
        lines.extend(
            [
                f"- **Start**: {context.dt_from.isoformat()}",
                f"- **End**: {context.dt_to.isoformat()}",
                "",
            ]
        )

        # Add CDCS link if available
        cdcs_result = context.get_result("cdcs")
        if cdcs_result and cdcs_result.success and cdcs_result.record_url:
            lines.extend(
                [
                    "## Related Records",
                    f"- [View in CDCS]({cdcs_result.record_url})",
                    "",
                ]
            )

        # Add note about XML attachment
        lines.extend(
            [
                "## Files",
                "The complete NexusLIMS XML record is attached to this experiment.",
            ]
        )

        return "\n".join(lines)

    def _build_tags(self, context: ExportContext) -> list[str]:
        """Build tag list for experiment.

        Parameters
        ----------
        context
            Export context

        Returns
        -------
        list of str
            Tags including "NexusLIMS", instrument, and user
        """
        tags = ["NexusLIMS", context.instrument_pid]

        if context.user:
            tags.append(context.user)

        return tags

    def _build_metadata(self, context: ExportContext) -> dict:
        """Build metadata dict for experiment.

        Parameters
        ----------
        context
            Export context

        Returns
        -------
        dict
            Metadata with session info and CDCS URL if available
        """
        metadata = {
            "nexuslims_session_id": context.session_identifier,
            "instrument": context.instrument_pid,
            "start_time": context.dt_from.isoformat(),
            "end_time": context.dt_to.isoformat(),
        }

        if context.user:
            metadata["user"] = context.user

        # Add CDCS URL if available
        cdcs_result = context.get_result("cdcs")
        if cdcs_result and cdcs_result.success and cdcs_result.record_url:
            metadata["cdcs_url"] = cdcs_result.record_url

        return metadata
