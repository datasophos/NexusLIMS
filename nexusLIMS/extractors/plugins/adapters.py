"""Adapter extractors that wrap existing extractor functions.

This module provides adapter classes that wrap the legacy extractor functions,
allowing them to work with the new plugin system while maintaining complete
backward compatibility.

These adapters will be used during Phase 1 and Phase 2 of the migration,
and will be removed in Phase 3 once all extractors are fully migrated to
the new plugin system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext

# Import existing extractor functions
from nexusLIMS.extractors.basic_metadata import get_basic_metadata
from nexusLIMS.extractors.digital_micrograph import get_dm3_metadata
from nexusLIMS.extractors.edax import get_msa_metadata, get_spc_metadata
from nexusLIMS.extractors.fei_emi import get_ser_metadata
from nexusLIMS.extractors.quanta_tif import get_quanta_metadata

logger = logging.getLogger(__name__)

__all__ = [
    "DM3Adapter",
    "SERAdapter",
    "QuantaTifAdapter",
    "SPCAdapter",
    "MSAAdapter",
    "BasicMetadataAdapter",
]


class DM3Adapter:
    """
    Adapter for DigitalMicrograph .dm3/.dm4 files.

    Wraps the existing get_dm3_metadata function.
    """

    name = "dm3_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if this is a .dm3 or .dm4 file."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext in ("dm3", "dm4")

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata using the legacy get_dm3_metadata function.

        This adapter ensures defensive error handling - if the legacy function
        returns None or raises an exception, we return minimal valid metadata.
        """
        try:
            metadata = get_dm3_metadata(context.file_path)

            # Legacy functions may return None on error
            if metadata is None:
                logger.warning(
                    "Legacy extractor returned None for %s, using fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using minimal metadata"],
            },
        }


class SERAdapter:
    """
    Adapter for FEI TIA .ser files.

    Wraps the existing get_ser_metadata function.
    """

    name = "ser_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if this is a .ser file."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "ser"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using the legacy get_ser_metadata function."""
        try:
            metadata = get_ser_metadata(context.file_path)

            if metadata is None:
                logger.warning(
                    "Legacy extractor returned None for %s, using fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using minimal metadata"],
            },
        }


class QuantaTifAdapter:
    """
    Adapter for FEI Quanta .tif files.

    Wraps the existing get_quanta_metadata function.
    """

    name = "quanta_tif_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if this is a .tif file."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "tif"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using the legacy get_quanta_metadata function."""
        try:
            metadata = get_quanta_metadata(context.file_path)

            if metadata is None:
                logger.warning(
                    "Legacy extractor returned None for %s, using fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using minimal metadata"],
            },
        }


class SPCAdapter:
    """
    Adapter for EDAX .spc files.

    Wraps the existing get_spc_metadata function.
    """

    name = "spc_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if this is a .spc file."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "spc"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using the legacy get_spc_metadata function."""
        try:
            metadata = get_spc_metadata(context.file_path)

            if metadata is None:
                logger.warning(
                    "Legacy extractor returned None for %s, using fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using minimal metadata"],
            },
        }


class MSAAdapter:
    """
    Adapter for EDAX .msa files.

    Wraps the existing get_msa_metadata function.
    """

    name = "msa_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if this is a .msa file."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "msa"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using the legacy get_msa_metadata function."""
        try:
            metadata = get_msa_metadata(context.file_path)

            if metadata is None:
                logger.warning(
                    "Legacy extractor returned None for %s, using fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using minimal metadata"],
            },
        }


class BasicMetadataAdapter:
    """
    Adapter for basic metadata extraction (fallback for unknown file types).

    Wraps the existing get_basic_metadata function.
    This is a wildcard extractor that supports any file extension.
    """

    name = "basic_metadata_adapter"
    priority = 0  # Lowest priority - this is the fallback

    def supports(self, context: ExtractionContext) -> bool:
        """Support any file type - this is the fallback extractor."""
        return True

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract basic metadata using the legacy get_basic_metadata function."""
        try:
            metadata = get_basic_metadata(context.file_path)

            if metadata is None:
                logger.warning(
                    "Legacy basic_metadata extractor returned None for %s, "
                    "using absolute fallback",
                    context.file_path,
                )
                return self._minimal_metadata(context)

            return metadata

        except Exception as e:  # noqa: BLE001
            logger.error(
                "Error extracting basic metadata from %s: %s",
                context.file_path,
                e,
                exc_info=True,
            )
            return self._minimal_metadata(context)

    def _minimal_metadata(self, context: ExtractionContext) -> dict[str, Any]:
        """Return minimal valid metadata on error."""
        from datetime import UTC
        from datetime import datetime as dt

        return {
            "nx_meta": {
                "DatasetType": "Unknown",
                "Data Type": "Unknown",
                "Creation Time": dt.fromtimestamp(
                    context.file_path.stat().st_mtime,
                    tz=UTC,
                ).isoformat(),
                "Instrument ID": (
                    context.instrument.name if context.instrument else None
                ),
                "warnings": ["Extraction failed - using absolute minimal metadata"],
            },
        }
