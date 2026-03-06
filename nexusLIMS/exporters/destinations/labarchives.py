"""LabArchives export destination plugin.

Exports NexusLIMS XML records to a LabArchives electronic lab notebook by
creating a page per session with an HTML summary entry and the full XML record
attached as a file.
"""

from __future__ import annotations

import base64
import logging
import re
import traceback
from collections import Counter
from pathlib import Path

from nexusLIMS.config import settings
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.utils.labarchives import (
    LabArchivesAuthenticationError,
    LabArchivesClient,
    LabArchivesError,
    get_labarchives_client,
)

_logger = logging.getLogger(__name__)


class LabArchivesDestination:
    """LabArchives export destination plugin.

    Uploads NexusLIMS XML records to a LabArchives instance. For each session,
    creates a page under ``NexusLIMS Records/{instrument}/`` in the configured
    notebook (or the user's Inbox if no notebook is configured) with:

    - An HTML-formatted session summary as a text entry
    - The full XML record attached as a file

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
            True if ``NX_LABARCHIVES_ACCESS_KEY_ID``,
            ``NX_LABARCHIVES_ACCESS_PASSWORD``, ``NX_LABARCHIVES_USER_ID``,
            and ``NX_LABARCHIVES_URL`` are all configured.
        """
        return all(
            [
                settings.NX_LABARCHIVES_ACCESS_KEY_ID,
                settings.NX_LABARCHIVES_ACCESS_PASSWORD,
                settings.NX_LABARCHIVES_USER_ID,
                settings.NX_LABARCHIVES_URL,
            ]
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate LabArchives configuration.

        Checks that required fields are present and tests authentication by
        making a lightweight API call.

        Returns
        -------
        tuple[bool, str | None]
            ``(is_valid, error_message)`` — ``error_message`` is ``None`` on success.
        """
        for attr, label in [
            ("NX_LABARCHIVES_ACCESS_KEY_ID", "NX_LABARCHIVES_ACCESS_KEY_ID"),
            ("NX_LABARCHIVES_ACCESS_PASSWORD", "NX_LABARCHIVES_ACCESS_PASSWORD"),
            ("NX_LABARCHIVES_USER_ID", "NX_LABARCHIVES_USER_ID"),
            ("NX_LABARCHIVES_URL", "NX_LABARCHIVES_URL"),
        ]:
            if not getattr(settings, attr, None):
                return False, f"{label} not configured"

        # Test authentication by making a live API call
        try:  # pragma: no cover
            client = get_labarchives_client()
            nbid = settings.NX_LABARCHIVES_NOTEBOOK_ID
            if nbid:
                # Verify notebook is accessible
                client.get_tree_level(nbid, "0")
            else:
                # No notebook configured — just verify credentials with a minimal call
                client.get_tree_level("0", "0")
        except LabArchivesAuthenticationError as e:  # pragma: no cover
            return False, f"LabArchives authentication failed: {e}"
        except LabArchivesError as e:  # pragma: no cover
            # Non-auth errors (e.g. notebook not found) still mean config is usable
            _logger.debug("LabArchives validate_config non-fatal error: %s", e)
        except Exception as e:  # pragma: no cover
            return False, f"LabArchives configuration error: {e}"

        return True, None  # pragma: no cover

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to LabArchives.

        Creates a notebook page with an HTML summary entry and attaches the
        XML record file. Never raises exceptions — all errors are caught and
        returned as :class:`~nexusLIMS.exporters.base.ExportResult` with
        ``success=False``.

        Parameters
        ----------
        context : ExportContext
            Export context with file path, session metadata, and results from
            higher-priority destinations (e.g., CDCS).

        Returns
        -------
        ExportResult
            Result of the export attempt.
        """
        try:
            client = get_labarchives_client()

            # Find or create target page
            nbid, page_tree_id = self._find_or_create_page(client, context)

            # Collect preview images from activities
            previews = self._collect_previews(context)

            # Build and upload HTML summary entry
            html_summary = self._build_html_summary(context, previews=previews)
            entry_id = client.add_entry(nbid, page_tree_id, html_summary)
            _logger.info(
                "Created LabArchives entry %s on page %s", entry_id, page_tree_id
            )

            # Upload XML file as attachment
            xml_bytes = context.xml_file_path.read_bytes()
            filename = context.xml_file_path.name
            client.add_attachment(
                nbid,
                page_tree_id,
                filename,
                xml_bytes,
                caption="NexusLIMS XML record",
            )
            _logger.info("Uploaded XML attachment %s to LabArchives", filename)

            # Build a best-effort entry URL
            entry_url = _build_entry_url(
                base_url=str(settings.NX_LABARCHIVES_URL),
                nbid=nbid,
                page_tree_id=page_tree_id,
            )

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=entry_id,
                record_url=entry_url,
            )

        except Exception:
            _logger.exception(
                "Failed to export to LabArchives: %s",
                context.xml_file_path.name,
            )
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=traceback.format_exc(),
            )

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _find_or_create_page(
        self,
        client: LabArchivesClient,
        context: ExportContext,
    ) -> tuple[str, str]:
        """Find or create the target notebook page for this session.

        When ``NX_LABARCHIVES_NOTEBOOK_ID`` is configured, navigates to (or
        creates) the path ``NexusLIMS Records/{instrument_pid}/`` and creates
        a new page named ``{YYYY-MM-DD} — {session_identifier}``.

        When no notebook ID is configured, returns ``("0", "0")`` which causes
        the API calls to target the user's Inbox.

        Parameters
        ----------
        client : LabArchivesClient
            Authenticated API client
        context : ExportContext
            Export context with session metadata

        Returns
        -------
        tuple[str, str]
            ``(nbid, page_tree_id)``
        """
        nbid = settings.NX_LABARCHIVES_NOTEBOOK_ID
        if not nbid:
            # No notebook configured — upload to Inbox
            return ("0", "0")

        # Find or create "NexusLIMS Records" folder at root
        root_nodes = client.get_tree_level(nbid, "0")
        nexuslims_folder_id = _find_node_by_text(root_nodes, "NexusLIMS Records")
        if nexuslims_folder_id is None:
            nexuslims_folder_id = client.insert_folder(nbid, "0", "NexusLIMS Records")
            _logger.info("Created 'NexusLIMS Records' folder in notebook %s", nbid)

        # Find or create instrument sub-folder
        instrument_nodes = client.get_tree_level(nbid, nexuslims_folder_id)
        instrument_folder_id = _find_node_by_text(
            instrument_nodes, context.instrument_pid
        )
        if instrument_folder_id is None:
            instrument_folder_id = client.insert_folder(
                nbid, nexuslims_folder_id, context.instrument_pid
            )
            _logger.info(
                "Created instrument folder '%s' in LabArchives",
                context.instrument_pid,
            )

        # Create a new page for this session
        page_name = f"{context.dt_from:%Y-%m-%d} \u2014 {context.session_identifier}"
        page_tree_id = client.insert_page(nbid, instrument_folder_id, page_name)
        _logger.info("Created page '%s' (tree_id=%s)", page_name, page_tree_id)

        return (nbid, page_tree_id)

    def _collect_previews(self, context: ExportContext) -> list[tuple[str, bytes]]:
        """Collect (name, image_bytes) pairs from context activities.

        Iterates over all activities and their preview paths, reading image
        bytes for each available preview. Multi-signal files that appear more
        than once in an activity's file list are labelled ``"(N of M)"``.

        Parameters
        ----------
        context : ExportContext
            Export context with activities

        Returns
        -------
        list[tuple[str, bytes]]
            List of ``(caption_name, image_bytes)`` pairs, one per available preview.
        """
        previews: list[tuple[str, bytes]] = []
        for act in context.activities:
            file_counts: Counter = Counter(act.files)
            file_seen: Counter = Counter()
            for fname, preview_path in zip(act.files, act.previews):
                file_seen[fname] += 1
                if not preview_path or not Path(preview_path).exists():
                    continue
                name = Path(fname).name
                if file_counts[fname] > 1:
                    name = f"{name} ({file_seen[fname]} of {file_counts[fname]})"
                try:
                    previews.append((name, Path(preview_path).read_bytes()))
                except Exception:
                    _logger.debug("Could not read preview: %s", preview_path)
        return previews

    def _build_html_summary(
        self,
        context: ExportContext,
        previews: list[tuple[str, bytes]] | None = None,
    ) -> str:
        """Build HTML summary content for the notebook entry.

        Parameters
        ----------
        context : ExportContext
            Export context with session metadata
        previews : list[tuple[str, bytes]] | None
            Optional list of ``(caption, image_bytes)`` pairs to embed as a
            preview gallery (4 images per row, base64 data URIs).

        Returns
        -------
        str
            HTML-formatted session summary
        """
        lines = [
            "<h1>NexusLIMS Microscopy Session</h1>",
            "<h2>Session Details</h2>",
            "<ul>",
            f"<li><strong>Session ID</strong>: {context.session_identifier}</li>",
            f"<li><strong>Instrument</strong>: {context.instrument_pid}</li>",
        ]

        if context.user:
            lines.append(f"<li><strong>User</strong>: {context.user}</li>")

        lines.extend(
            [
                f"<li><strong>Start</strong>: {context.dt_from.isoformat()}</li>",
                f"<li><strong>End</strong>: {context.dt_to.isoformat()}</li>",
                "</ul>",
            ]
        )

        # Add CDCS link if available
        cdcs_result = context.get_result("cdcs")
        if cdcs_result and cdcs_result.success and cdcs_result.record_url:
            lines.extend(
                [
                    "<h2>Related Records</h2>",
                    "<ul>",
                    f'<li><a href="{cdcs_result.record_url}">View in CDCS</a></li>',
                    "</ul>",
                ]
            )

        if previews:
            lines.append("<h2>Preview Images</h2>")
            lines.append('<table style="border-collapse:collapse;">')
            for i, (name, img_bytes) in enumerate(previews):
                if i % 4 == 0:
                    if i > 0:
                        lines.append("</tr>")
                    lines.append("<tr>")
                b64 = base64.b64encode(img_bytes).decode()
                lines.append(
                    f'<td style="padding:8px;text-align:center;vertical-align:top;">'
                    f'<img src="data:image/png;base64,{b64}" alt="{name}" '
                    f'style="max-width:250px;max-height:250px;border:1px solid #ccc;">'
                    f"<br><small>{name}</small></td>"
                )
            lines.append("</tr></table>")

        lines.append("<h2>Files</h2>")
        lines.append("<p>The following data files are referenced in this record:</p>")

        # Collect unique file locations across all activities, preserving order.
        # Strip NX_INSTRUMENT_DATA_PATH prefix so paths match the XML <location>
        # element (relative to the instrument storage root).
        instr_root = str(settings.NX_INSTRUMENT_DATA_PATH)
        seen: set[str] = set()
        file_names: list[str] = []
        for act in context.activities:
            for fname in act.files:
                if fname not in seen:
                    seen.add(fname)
                    rel = fname.replace(instr_root, "")
                    file_names.append(rel)

        if file_names:
            lines.append("<ul>")
            for name in file_names:
                lines.append(f"<li>{name}</li>")
            lines.append("</ul>")

        return "\n".join(lines)


# ------------------------------------------------------------------ #
# Module-level helpers                                                 #
# ------------------------------------------------------------------ #


def _find_node_by_text(
    nodes: list[dict],
    display_text: str,
) -> str | None:
    """Return tree_id of the first node matching display_text, or None."""
    for node in nodes:
        if node.get("display_text") == display_text:
            return node["tree_id"]
    return None


_LA_API_HOST = "api.labarchives.com"
_LA_WEB_HOST = "mynotebook.labarchives.com"


def _build_entry_url(base_url: str, nbid: str, page_tree_id: str) -> str:
    """Build a best-effort URL to the LabArchives notebook page.

    Parameters
    ----------
    base_url : str
        API base URL (e.g. ``"https://api.labarchives.com/api"``).  For the
        cloud LabArchives service, ``api.labarchives.com`` is replaced with
        ``mynotebook.labarchives.com`` so the link opens in the web interface.
        For other hosts, the ``/api`` path suffix is stripped.
    nbid : str
        Notebook ID
    page_tree_id : str
        Tree ID of the page

    Returns
    -------
    str
        URL pointing to the page in the LabArchives web interface (best effort)
    """
    # For cloud LabArchives: swap API host → web host and drop the /api path.
    # For self-hosted instances: just strip the /api suffix.
    base = re.sub(r"/api/?$", "", base_url.rstrip("/"))
    base = base.replace(_LA_API_HOST, _LA_WEB_HOST)
    if nbid and nbid != "0":
        return f"{base}/#/{nbid}/{page_tree_id}"
    return base
