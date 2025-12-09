"""Instrument profile for FEI Titan STEM (643 microscope)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexusLIMS.extractors import ExtractionContext

logger = logging.getLogger(__name__)


def add_metadata_warnings(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Add warnings for potentially inaccurate metadata fields.

    The 643 Titan STEM has known issues with detector, operator, and specimen
    metadata accuracy.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context (unused but required by profile signature)

    Returns
    -------
    dict
        Modified metadata dictionary with warnings added
    """
    warnings = metadata["nx_meta"].get("warnings", [])

    warning_fields = ["Detector", "Operator", "Specimen"]
    for field in warning_fields:
        if field in metadata["nx_meta"]:
            warnings.append([field])

    if warnings:
        metadata["nx_meta"]["warnings"] = warnings

    return metadata


def detect_eftem_diffraction(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Detect and flag EFTEM diffraction patterns.

    When Imaging Mode is "EFTEM DIFFRACTION", change DatasetType to Diffraction.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context (unused but required by profile signature)

    Returns
    -------
    dict
        Modified metadata dictionary with updated dataset type if applicable
    """
    imaging_mode = metadata["nx_meta"].get("Imaging Mode", "")

    if "EFTEM DIFFRACTION" in imaging_mode.upper():
        logger.info(
            'Detected file as Diffraction type based on "Imaging Mode" == "%s"',
            imaging_mode,
        )
        metadata["nx_meta"]["DatasetType"] = "Diffraction"
        metadata["nx_meta"]["Data Type"] = "TEM_EFTEM_Diffraction"

    return metadata


# Register the profile
from nexusLIMS.extractors import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

fei_titan_stem_643_profile = InstrumentProfile(
    instrument_id="FEI-Titan-STEM",
    parsers={
        "metadata_warnings": add_metadata_warnings,
        "eftem_diffraction": detect_eftem_diffraction,
    },
    transformations={},
    extractor_overrides={},
    static_metadata={},
)

get_profile_registry().register(fei_titan_stem_643_profile)

logger.debug("Registered FEI Titan STEM (643) instrument profile")
