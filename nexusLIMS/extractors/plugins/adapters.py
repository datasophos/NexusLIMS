"""
Adapter extractors for backward compatibility.

These adapters wrap the legacy extraction functions to work with the new
plugin-based system. They will be removed in Phase 3 once all code is
migrated to use the registry directly.

DO NOT USE THESE DIRECTLY - they are internal compatibility shims.
"""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.basic_metadata import get_basic_metadata
from nexusLIMS.extractors.digital_micrograph import get_dm3_metadata
from nexusLIMS.extractors.edax import get_msa_metadata, get_spc_metadata
from nexusLIMS.extractors.fei_emi import get_ser_metadata
from nexusLIMS.extractors.quanta_tif import get_quanta_metadata

logger = logging.getLogger(__name__)


class DM3Adapter:
    """Adapter for legacy get_dm3_metadata function."""

    name = "dm3_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if file is .dm3 or .dm4."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext in {"dm3", "dm4"}

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using legacy function."""
        return get_dm3_metadata(context.file_path)


class QuantaTifAdapter:
    """Adapter for legacy get_quanta_metadata function."""

    name = "quanta_tif_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if file is .tif or .tiff."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext in {"tif", "tiff"}

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using legacy function."""
        return get_quanta_metadata(context.file_path)


class SerAdapter:
    """Adapter for legacy get_ser_metadata function."""

    name = "ser_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if file is .ser."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "ser"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using legacy function."""
        return get_ser_metadata(context.file_path)


class SpcAdapter:
    """Adapter for legacy get_spc_metadata function."""

    name = "spc_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if file is .spc."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "spc"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using legacy function."""
        return get_spc_metadata(context.file_path)


class MsaAdapter:
    """Adapter for legacy get_msa_metadata function."""

    name = "msa_adapter"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """Check if file is .msa."""
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "msa"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract metadata using legacy function."""
        return get_msa_metadata(context.file_path)


class BasicMetadataAdapter:
    """Adapter for legacy get_basic_metadata function (fallback)."""

    name = "basic_metadata_adapter"
    priority = 0  # Lowest priority - fallback only

    def supports(self, context: ExtractionContext) -> bool:
        """Always returns True - this is the fallback."""
        return True

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """Extract basic metadata using legacy function."""
        return get_basic_metadata(context.file_path)
