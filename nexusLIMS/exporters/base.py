"""Base protocols and data structures for export destinations.

This module defines the core interfaces and data structures for the
NexusLIMS export framework, which allows records to be exported to
multiple repository destinations (CDCS, LabArchives, eLabFTW, etc.)
using a plugin-based architecture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of a single export attempt.

    Parameters
    ----------
    success
        Whether the export succeeded
    destination_name
        Name of the destination plugin (e.g., "cdcs")
    record_id
        Destination-specific record identifier (if successful)
    record_url
        Direct URL to view the exported record (if successful)
    error_message
        Error message if export failed
    timestamp
        When the export attempt occurred
    metadata
        Additional destination-specific metadata
    """

    success: bool
    destination_name: str
    record_id: str | None = None
    record_url: str | None = None
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        """Return string representation of ExportResult."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"ExportResult(destination={self.destination_name}, "
            f"status={status}, "
            f"record_id={self.record_id})"
        )


@dataclass
class ExportContext:
    """Context passed to export destination plugins.

    Provides all necessary information for a destination to export a record,
    including file path, session metadata, and results from previously-run
    higher-priority destinations (for inter-destination dependencies).

    Parameters
    ----------
    xml_file_path
        Path to the XML record file to export
    session_identifier
        Unique identifier for this session
    instrument_pid
        Instrument identifier (e.g., "FEI-Titan-TEM-012345")
    dt_from
        Session start datetime
    dt_to
        Session end datetime
    user
        Username associated with this session (if known)
    metadata
        Additional session metadata
    previous_results
        Results from higher-priority destinations that have already run.
        Destinations can access these to create inter-destination
        dependencies (e.g., LabArchives including a CDCS link).
    """

    xml_file_path: Path
    session_identifier: str
    instrument_pid: str
    dt_from: datetime
    dt_to: datetime
    user: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    previous_results: dict[str, ExportResult] = field(default_factory=dict)

    def get_result(self, destination_name: str) -> ExportResult | None:
        """Get result from a specific destination, if it has already run.

        Parameters
        ----------
        destination_name
            Name of the destination to query (e.g., "cdcs")

        Returns
        -------
        ExportResult | None
            The result if the destination has run, None otherwise
        """
        return self.previous_results.get(destination_name)

    def add_result(self, destination_name: str, result: ExportResult) -> None:
        """Add or update result from a destination.

        Parameters
        ----------
        destination_name
            Name of the destination (e.g., "cdcs", "elabftw")
        result
            The export result to store

        Examples
        --------
        >>> from nexusLIMS.exporters.base import ExportResult
        >>> result = ExportResult(success=True, message="Uploaded successfully")
        >>> context.add_result("cdcs", result)
        """
        self.previous_results[destination_name] = result

    def has_successful_export(self, destination_name: str) -> bool:
        """Check if a destination successfully exported.

        Parameters
        ----------
        destination_name
            Name of the destination to check (e.g., "cdcs")

        Returns
        -------
        bool
            True if the destination ran and succeeded, False otherwise
        """
        result = self.get_result(destination_name)
        return result is not None and result.success


class ExportDestination(Protocol):
    """Protocol for export destination plugins.

    Export destinations are discovered automatically by walking the
    exporters/destinations/ directory. Any class matching this protocol
    will be registered as an export destination.

    Attributes
    ----------
    name : str
        Unique identifier for this destination (e.g., "cdcs")
    priority : int
        Selection priority (0-1000, higher runs first).
        Use priority to manage inter-destination dependencies:
        higher-priority destinations run first and their results
        are available to lower-priority destinations.
    """

    name: str
    priority: int

    @property
    def enabled(self) -> bool:
        """Whether this destination is enabled and configured.

        Check if all required configuration is present (API keys,
        URLs, etc.) and the destination should be used for exports.

        Returns
        -------
        bool
            True if destination is ready to use, False otherwise
        """
        ...

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate configuration.

        Perform startup-time validation of configuration (API keys,
        connectivity, etc.) and return detailed error information.

        Returns
        -------
        tuple[bool, str | None]
            (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: None if valid, descriptive error if invalid
        """
        ...

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to this destination.

        CRITICAL: This method MUST NOT raise exceptions. All errors must
        be caught and returned as ExportResult with success=False and
        error_message set.

        Parameters
        ----------
        context
            Export context with file path, session metadata, and
            results from higher-priority destinations

        Returns
        -------
        ExportResult
            Result of the export attempt (success or failure)
        """
        ...
