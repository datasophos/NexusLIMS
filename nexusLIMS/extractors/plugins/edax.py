"""EDAX EDS spectrum (.spc/.msa) extractor plugin."""

import logging
from typing import Any

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.edax import get_msa_metadata, get_spc_metadata

logger = logging.getLogger(__name__)


class SpcExtractor:
    """
    Extractor for EDAX .spc files.

    This extractor handles metadata extraction from .spc files saved by
    EDAX EDS software (Genesis, TEAM, etc.).
    """

    name = "spc_extractor"
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
            True if file extension is .spc
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "spc"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a .spc file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        logger.debug("Extracting metadata from SPC file: %s", context.file_path)
        return get_spc_metadata(context.file_path)


class MsaExtractor:
    """
    Extractor for EMSA/MAS .msa spectrum files.

    This extractor handles metadata extraction from .msa files, which may be
    saved by various EDS acquisition software packages, most commonly as exports
    from EDAX or Oxford software.
    """

    name = "msa_extractor"
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
            True if file extension is .msa
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "msa"

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from an .msa file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        logger.debug("Extracting metadata from MSA file: %s", context.file_path)
        return get_msa_metadata(context.file_path)
