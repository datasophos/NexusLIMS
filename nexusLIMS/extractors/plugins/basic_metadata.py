"""Basic metadata extractor plugin (fallback for unknown file types)."""

import logging
from datetime import datetime as dt
from typing import Any, ClassVar

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.instruments import get_instr_from_filepath

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
    supported_extensions: ClassVar = None  # Wildcard extractor - supports all files

    def supports(self, context: ExtractionContext) -> bool:  # noqa: ARG002
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

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
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
        list[dict]
            List containing a single metadata dict with 'nx_meta' key
        """
        logger.debug(
            "Extracting basic metadata from file (no specialized extractor): %s",
            context.file_path,
        )

        mdict = {"nx_meta": {}}
        mdict["nx_meta"]["DatasetType"] = "Unknown"
        mdict["nx_meta"]["Data Type"] = "Unknown"

        # get the modification time (as ISO format):
        mtime = context.file_path.stat().st_mtime
        mtime_iso = dt.fromtimestamp(
            mtime,
            tz=context.instrument.timezone if context.instrument else None,
        ).isoformat()
        mdict["nx_meta"]["Creation Time"] = mtime_iso

        return [mdict]


# Backward compatibility function for tests
def get_basic_metadata(filename):
    """
    Get basic metadata from a file.

    Returns basic metadata from a file that's not currently interpretable by NexusLIMS.

    .. deprecated::
        This function is deprecated. Use BasicFileInfoExtractor class instead.

    Parameters
    ----------
    filename : pathlib.Path
        path to a file saved in the harvested directory of the instrument

    Returns
    -------
    mdict : dict
        A description of the file in lieu of any metadata extracted from it.
    """
    context = ExtractionContext(
        file_path=filename, instrument=get_instr_from_filepath(filename)
    )
    extractor = BasicFileInfoExtractor()
    return extractor.extract(context)
