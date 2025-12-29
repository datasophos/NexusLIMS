"""Instrument profile for JEOL JEM TEM (642 Stroboscope)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import ExtractionContext

logger = logging.getLogger(__name__)


def detect_diffraction_from_filename(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Detect diffraction patterns using filename heuristics.

    The JEOL Stroboscope doesn't add metadata indicating diffraction mode,
    so we use common filename patterns (Diff, SAED, DP) to detect it.

    This is not perfect but better than nothing.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context containing file path

    Returns
    -------
    dict
        Modified metadata dictionary with updated dataset type if applicable
    """
    filename = str(context.file_path)

    # Check for common diffraction pattern naming conventions
    for pattern in ["Diff", "SAED", "DP"]:
        if (
            pattern.lower() in filename
            or pattern.upper() in filename
            or pattern in filename
        ):
            logger.info(
                'Detected file as Diffraction type based on "%s" in the filename',
                pattern,
            )
            metadata["nx_meta"]["DatasetType"] = "Diffraction"
            metadata["nx_meta"]["Data Type"] = "TEM_Diffraction"
            break

    # Add warnings since detection is unreliable
    warnings = metadata["nx_meta"].get("warnings", [])
    warnings.append(["DatasetType"])
    warnings.append(["Data Type"])
    metadata["nx_meta"]["warnings"] = warnings

    return metadata


# Register the profile
jeol_jem_642_profile = InstrumentProfile(
    instrument_id="JEOL-JEM-TEM",
    parsers={
        "diffraction_detection": detect_diffraction_from_filename,
    },
    transformations={},
    extension_fields={},
)

get_profile_registry().register(jeol_jem_642_profile)

logger.debug("Registered JEOL JEM TEM (642) instrument profile")
