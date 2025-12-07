"""Digital Micrograph (.dm3/.dm4) extractor plugin."""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.digital_micrograph import get_dm3_metadata

logger = logging.getLogger(__name__)


class DM3Extractor:
    """
    Extractor for Gatan DigitalMicrograph files (.dm3 and .dm4).

    This extractor handles metadata extraction from files saved by Gatan's
    DigitalMicrograph software, commonly used on FEI/Thermo and JEOL TEMs.
    """

    name = "dm3_extractor"
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
            True if file extension is .dm3 or .dm4
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension in {"dm3", "dm4"}

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a DM3/DM4 file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        logger.debug("Extracting metadata from DM3/DM4 file: %s", context.file_path)
        return get_dm3_metadata(context.file_path)
