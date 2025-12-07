"""FEI/Thermo Fisher TIFF extractor plugin."""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.quanta_tif import get_quanta_metadata

logger = logging.getLogger(__name__)


class QuantaTiffExtractor:
    """
    Extractor for FEI/Thermo Fisher TIFF files.

    This extractor handles metadata extraction from .tif files saved by
    FEI/Thermo Fisher FIBs and SEMs (e.g., Quanta, Helios, etc.).
    """

    name = "quanta_tif_extractor"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if file extension is .tif or .tiff
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension in {"tif", "tiff"}

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a FEI/Thermo TIFF file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        logger.debug("Extracting metadata from FEI TIFF file: %s", context.file_path)
        return get_quanta_metadata(context.file_path)
