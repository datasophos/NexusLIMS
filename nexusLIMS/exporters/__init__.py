"""Multi-destination export framework for NexusLIMS records.

This package provides a plugin-based architecture for exporting NexusLIMS
XML records to multiple repository destinations (CDCS, LabArchives, eLabFTW, etc.).

The main entry point is export_records(), which:
1. Exports XML files to all enabled destinations using the configured strategy
2. Logs results to the upload_log database table
3. Returns success/failure results for each file

Example
-------
>>> from nexusLIMS.exporters import export_records
>>> results = export_records([xml_file], [session])
>>> if was_successfully_exported(xml_file, results):
...     print("Exported successfully!")
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from sqlmodel import Session as DBSession

from nexusLIMS.config import settings
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.models import UploadLog
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.exporters.registry import get_registry

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.db.session_handler import Session

_logger = logging.getLogger(__name__)


def export_records(
    xml_files: list[Path],
    sessions: list[Session],
) -> dict[Path, list[ExportResult]]:
    """Export NexusLIMS records to all enabled destinations.

    Main entry point for exporting records. Called by record_builder.py
    after XML records are built and validated. Exports each record to all
    enabled destinations using the configured strategy, logs results to
    the database, and returns success/failure information.

    Parameters
    ----------
    xml_files
        List of XML record file paths to export
    sessions
        Corresponding Session objects (same length and order as xml_files)

    Returns
    -------
    dict[Path, list[ExportResult]]
        Mapping of XML file path to list of export results (one per destination)
    """
    if len(xml_files) != len(sessions):
        msg = (
            f"xml_files ({len(xml_files)}) and sessions ({len(sessions)}) "
            f"must have the same length"
        )
        raise ValueError(msg)

    registry = get_registry()
    strategy = settings.NX_EXPORT_STRATEGY

    _logger.info(
        "Exporting %d record(s) using strategy: %s",
        len(xml_files),
        strategy,
    )

    results = {}
    for xml_file, session in zip(xml_files, sessions, strict=True):
        # Build export context
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier=session.session_identifier,
            instrument_pid=session.instrument.name,
            dt_from=session.dt_from,
            dt_to=session.dt_to,
            user=session.user,
        )

        # Export to all destinations
        _logger.info("Exporting record: %s", xml_file.name)
        export_results = registry.export_to_all(context, strategy=strategy)
        results[xml_file] = export_results

        # Write to upload_log table
        _log_to_database(session.session_identifier, export_results)

        # Log summary
        success_count = sum(1 for r in export_results if r.success)
        total_count = len(export_results)
        if success_count > 0:
            _logger.info(
                "Exported %s: %d/%d destination(s) succeeded",
                xml_file.name,
                success_count,
                total_count,
            )
        else:
            _logger.error(
                "Export failed for %s: all %d destination(s) failed",
                xml_file.name,
                total_count,
            )

    return results


def _log_to_database(
    session_identifier: str,
    results: list[ExportResult],
) -> None:
    """Write export results to upload_log table.

    Parameters
    ----------
    session_identifier
        Session identifier for this export
    results
        List of export results to log
    """
    with DBSession(get_engine()) as db:
        for result in results:
            log_entry = UploadLog(
                session_identifier=session_identifier,
                destination_name=result.destination_name,
                success=result.success,
                record_id=result.record_id,
                record_url=result.record_url,
                error_message=result.error_message,
                timestamp=result.timestamp,
                metadata_json=(
                    json.dumps(result.metadata) if result.metadata else None
                ),
            )
            db.add(log_entry)
        db.commit()


def was_successfully_exported(
    xml_file: Path,
    results: dict[Path, list[ExportResult]],
) -> bool:
    """Check if a file was successfully exported to at least one destination.

    Parameters
    ----------
    xml_file
        XML file path to check
    results
        Export results from export_records()

    Returns
    -------
    bool
        True if at least one destination succeeded, False otherwise
    """
    if xml_file not in results:
        return False
    return any(r.success for r in results[xml_file])


# Public API
__all__ = [
    "ExportContext",
    "ExportDestination",
    "ExportResult",
    "export_records",
    "was_successfully_exported",
]
