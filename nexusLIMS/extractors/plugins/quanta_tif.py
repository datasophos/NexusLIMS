"""Backward-compatibility shim for the renamed fei_tif extractor module.

.. deprecated::
    Import from :mod:`nexusLIMS.extractors.plugins.fei_tif` instead.
"""

from nexusLIMS.extractors.plugins.fei_tif import (  # noqa: F401
    FEI_TIFF_TAG,
    FEI_XML_TIFF_TAG,
    FeiTiffExtractor,
    get_fei_metadata,
)

# Backward-compat aliases
QuantaTiffExtractor = FeiTiffExtractor
get_quanta_metadata = get_fei_metadata
