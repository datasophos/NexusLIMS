"""FEI TIA (.ser/.emi) extractor plugin."""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.fei_emi import get_ser_metadata

logger = logging.getLogger(__name__)


class SerEmiExtractor:
    """
    Extractor for FEI TIA series files (.ser with accompanying .emi).

    This extractor handles metadata extraction from files saved by FEI's
    (now Thermo Fisher Scientific) TIA (Tecnai Imaging and Analysis) software.
    The .ser files contain the actual data, while .emi files contain metadata.
    """

    name = "ser_emi_extractor"
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
            True if file extension is .ser
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "ser"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a .ser file and its accompanying .emi file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        logger.debug("Extracting metadata from SER/EMI file: %s", context.file_path)
        return get_ser_metadata(context.file_path)
