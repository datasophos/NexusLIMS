"""Basic metadata extractor plugin (fallback for unknown file types)."""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.basic_metadata import get_basic_metadata

logger = logging.getLogger(__name__)


class BasicFileInfoExtractor:
    """
    Fallback extractor for files without a specific format handler.

    This extractor provides basic metadata (creation time, file size, etc.)
    for files that don't have a specialized extractor. It has the lowest
    priority and will only be used if no other extractor supports the file.
    """

    name = "basic_file_info_extractor"
    priority = 0  # Lowest priority - only used as fallback

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        This extractor always returns True since it's the fallback for all files.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            Always True (this is the fallback extractor)
        """
        return True

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract basic metadata from any file.

        Provides minimal metadata such as modification time and instrument ID
        for files that don't have a specialized extractor.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing basic file information
        """
        logger.debug(
            "Extracting basic metadata from file (no specialized extractor): %s",
            context.file_path,
        )
        return get_basic_metadata(context.file_path)
