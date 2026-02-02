"""eLabFTW export destination plugin.

Exports NexusLIMS XML records to eLabFTW electronic lab notebook by creating
experiments with markdown summaries and attaching the full XML record.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from nexusLIMS.config import settings
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.utils.elabftw import (
    ContentType,
    ELabFTWAuthenticationError,
    get_elabftw_client,
)

_logger = logging.getLogger(__name__)


# ============================================================================
# eLabFTW Extra Fields Schema Models
# ============================================================================


class ExtraFieldsGroup(BaseModel):
    """eLabFTW extra fields group definition.

    Groups are used to organize related fields in the eLabFTW UI.
    """

    id: int = Field(..., description="Unique group ID")
    name: str = Field(..., description="Display name of the group")


class ExtraField(BaseModel):
    """eLabFTW extra field definition.

    Represents a single structured metadata field with type validation.
    See: https://doc.elabftw.net/metadata.html#schema-description
    """

    type: Literal[
        "text",
        "date",
        "datetime-local",
        "email",
        "number",
        "select",
        "radio",
        "checkbox",
        "url",
        "time",
    ] = Field(..., description="Field type for validation and UI rendering")
    value: str | int | float | bool = Field(..., description="Field value")
    description: str | None = Field(None, description="Help text for the field")
    position: int | None = Field(None, description="Display order (lower first)")
    group_id: int | None = Field(
        None, description="ID of the group this field belongs to"
    )
    required: bool | None = Field(None, description="Whether field is required")
    blank_value_on_duplicate: bool | None = Field(
        None, description="Clear value when entity is duplicated"
    )

    model_config = {"extra": "allow"}  # Allow additional eLabFTW-specific fields


class ELabFTWConfig(BaseModel):
    """eLabFTW configuration object for extra fields metadata."""

    display_main_text: bool = Field(
        default=True, description="Whether to display the main text/body"
    )
    extra_fields_groups: list[ExtraFieldsGroup] = Field(
        default_factory=list, description="Group definitions for organizing fields"
    )


class ExtraFieldsMetadata(BaseModel):
    """Complete eLabFTW extra fields metadata structure.

    This is the top-level object sent to eLabFTW's metadata field.
    """

    extra_fields: dict[str, ExtraField] = Field(
        ..., description="Field definitions keyed by field name"
    )
    elabftw: ELabFTWConfig = Field(..., description="eLabFTW-specific configuration")


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

        Creates an experiment with an HTML summary of the session,
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
            body = self._build_html_body(context)
            tags = self._build_tags(context)
            metadata = self._build_metadata(context)

            # Create experiment
            # Note: Using HTML instead of Markdown due to eLabFTW API bug
            # https://github.com/elabftw/elabftw/issues/6416
            experiment = client.create_experiment(
                title=title,
                body=body,
                tags=tags,
                metadata=metadata,
                category=settings.NX_ELABFTW_EXPERIMENT_CATEGORY,
                status=settings.NX_ELABFTW_EXPERIMENT_STATUS,
                content_type=ContentType.HTML,
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

    def _build_html_body(self, context: ExportContext) -> str:
        """Build HTML body for experiment.

        Note: We use HTML instead of Markdown due to an eLabFTW API bug that
        prevents setting content_type via the API.
        See: https://github.com/elabftw/elabftw/issues/6416

        Parameters
        ----------
        context
            Export context

        Returns
        -------
        str
            HTML-formatted body with session details and CDCS link
        """
        lines = [
            "<h1>NexusLIMS Microscopy Session</h1>",
            "<h2>Session Details</h2>",
            "<ul>",
            f"<li><strong>Session ID</strong>: {context.session_identifier}</li>",
            f"<li><strong>Instrument</strong>: {context.instrument_pid}</li>",
        ]

        # Add user if available
        if context.user:
            lines.append(f"<li><strong>User</strong>: {context.user}</li>")

        # Add timestamps
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

        # Add note about XML attachment
        lines.extend(
            [
                "<h2>Files</h2>",
                (
                    "<p>The complete NexusLIMS XML record is attached to "
                    "this experiment.</p>"
                ),
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
        """Build metadata using eLabFTW extra_fields schema.

        This method creates a structured metadata object following eLabFTW's
        extra_fields format, which provides type validation, field descriptions,
        grouping, and ordering.

        Parameters
        ----------
        context
            Export context with session information

        Returns
        -------
        dict
            Metadata dict with 'extra_fields' and 'elabftw' keys conforming to
            eLabFTW's extra_fields schema. See:
            https://doc.elabftw.net/metadata.html#schema-description

        Notes
        -----
        The extra_fields schema provides several benefits over flat metadata:
        - Type validation (datetime-local, url, text, etc.)
        - Field descriptions for documentation
        - Logical grouping of related fields
        - Controlled ordering via position attribute
        - Better UI/UX in eLabFTW interface
        """
        # Build extra fields using Pydantic models for type safety
        extra_fields: dict[str, ExtraField] = {
            "Session ID": ExtraField(
                type="text",
                value=context.session_identifier,
                description="NexusLIMS session identifier",
                position=1,
                group_id=1,
            ),
            "Instrument": ExtraField(
                type="text",
                value=context.instrument_pid,
                description="Instrument persistent identifier",
                position=2,
                group_id=1,
            ),
            "Start Time": ExtraField(
                type="datetime-local",
                value=context.dt_from.strftime("%Y-%m-%dT%H:%M"),
                description="Session start time",
                position=3,
                group_id=1,
            ),
            "End Time": ExtraField(
                type="datetime-local",
                value=context.dt_to.strftime("%Y-%m-%dT%H:%M"),
                description="Session end time",
                position=4,
                group_id=1,
            ),
        }

        # Add optional user field
        if context.user:
            extra_fields["User"] = ExtraField(
                type="text",
                value=context.user,
                description="User who performed the session",
                position=5,
                group_id=1,
            )

        # Define groups
        groups = [ExtraFieldsGroup(id=1, name="Session Information")]

        # Add CDCS cross-link if available
        cdcs_result = context.get_result("cdcs")
        if cdcs_result and cdcs_result.success and cdcs_result.record_url:
            extra_fields["CDCS Record"] = ExtraField(
                type="url",
                value=cdcs_result.record_url,
                description="Link to CDCS record",
                position=10,  # Leave gap for potential future fields
                group_id=2,
            )
            groups.append(ExtraFieldsGroup(id=2, name="Related Records"))

        # Create and validate the complete metadata structure
        metadata = ExtraFieldsMetadata(
            extra_fields=extra_fields,
            elabftw=ELabFTWConfig(
                display_main_text=True,
                extra_fields_groups=groups,
            ),
        )

        # Return as dict for API compatibility
        return metadata.model_dump(exclude_none=True)

    def _validate_extra_field(self, field_name: str, field_def: dict) -> bool:
        """Validate an extra_field definition.

        Checks that the field has required keys (type, value) and that
        the value matches the declared type format.

        Parameters
        ----------
        field_name
            Name of the field
        field_def
            Field definition dict with type, value, and optional metadata

        Returns
        -------
        bool
            True if valid, False otherwise

        Notes
        -----
        Validation rules by type:
        - datetime-local: YYYY-MM-DDTHH:MM format
        - date: YYYY-MM-DD format
        - url: must start with http:// or https://
        - Other types: no format validation
        """
        required_keys = {"type", "value"}
        if not all(key in field_def for key in required_keys):
            _logger.warning(
                "Extra field '%s' missing required keys: %s",
                field_name,
                required_keys,
            )
            return False

        field_type = field_def["type"]
        value = field_def["value"]

        # Type-specific validation
        if field_type == "datetime-local":
            # Value should be in format YYYY-MM-DDTHH:MM
            if not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", str(value)):
                _logger.warning(
                    "Extra field '%s' has invalid datetime-local format: %s",
                    field_name,
                    value,
                )
                return False
        elif field_type == "date":
            # Value should be in format YYYY-MM-DD
            if not re.match(r"\d{4}-\d{2}-\d{2}", str(value)):
                _logger.warning(
                    "Extra field '%s' has invalid date format: %s",
                    field_name,
                    value,
                )
                return False
        elif field_type == "url" and not str(value).startswith(("http://", "https://")):
            # Basic URL validation
            _logger.warning(
                "Extra field '%s' has invalid URL: %s",
                field_name,
                value,
            )
            return False

        return True
