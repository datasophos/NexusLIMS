# ruff: noqa: INP001, ERA001
"""Example local instrument profile for a custom microscope.

This file demonstrates how to create a local instrument profile that can be
placed in a directory outside the NexusLIMS codebase and automatically loaded
at runtime.

To use this profile:
1. Copy the file to the local profiles directory (e.g., /opt/nexuslims/local_profiles/)
2. Set NX_LOCAL_PROFILES_PATH in your .env file to point to that directory
3. Update the instrument_id to match your instrument's name in the database
4. Customize the parser functions for your instrument's specific needs

The profile will be automatically discovered and loaded when NexusLIMS starts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import ExtractionContext

from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

logger = logging.getLogger(__name__)


def add_facility_metadata(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Add facility-specific metadata to all files from this instrument.

    This example shows how to inject consistent metadata values for all
    files acquired on a specific instrument.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context with file path and instrument info

    Returns
    -------
    dict
        Modified metadata dictionary
    """
    # Add your facility's information
    metadata["nx_meta"]["Facility"] = "My Lab Facility"
    metadata["nx_meta"]["Building"] = "Building 123"
    metadata["nx_meta"]["Room"] = "Lab 456"
    metadata["nx_meta"]["Contact"] = "lab-contact@example.com"

    logger.debug("Added facility metadata for %s", context.instrument.name)
    return metadata


def add_instrument_warnings(
    metadata: dict[str, Any],
    context: ExtractionContext,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Add warnings for metadata fields known to be unreliable on this instrument.

    This example shows how to flag specific metadata fields that may not be
    accurate due to instrument configuration or hardware issues.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context with file path and instrument info

    Returns
    -------
    dict
        Modified metadata dictionary with warnings added
    """
    warnings = metadata["nx_meta"].get("warnings", [])

    # Add warnings for unreliable fields
    # Note: warnings are stored as lists of field names, e.g., ["Operator"]
    unreliable_fields = ["Operator", "Specimen", "Temperature"]

    for field in unreliable_fields:
        if field in metadata["nx_meta"]:
            warnings.append([field])

    if warnings:
        metadata["nx_meta"]["warnings"] = warnings
        logger.warning(
            "Added warnings for unreliable metadata fields: %s",
            unreliable_fields,
        )

    return metadata


def detect_special_acquisition_mode(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Detect special acquisition modes from filename patterns.

    This example shows how to use filename heuristics to identify specific
    types of acquisitions when the metadata doesn't contain reliable indicators.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context with file path and instrument info

    Returns
    -------
    dict
        Modified metadata dictionary
    """
    filename = context.file_path.name.lower()

    # Example: Detect diffraction patterns from common filename patterns
    diffraction_patterns = ["diff", "saed", "dp", "diffraction"]
    if any(pattern in filename for pattern in diffraction_patterns):
        logger.info("Detected diffraction pattern from filename: %s", filename)
        metadata["nx_meta"]["DatasetType"] = "Diffraction"
        # Adjust Data Type if needed
        if "Data Type" in metadata["nx_meta"]:
            current_type = metadata["nx_meta"]["Data Type"]
            if "TEM" in current_type or "STEM" in current_type:
                base = current_type.split("_")[0]
                metadata["nx_meta"]["Data Type"] = f"{base}_Diffraction"

    # Example: Detect spectroscopy data
    spectroscopy_patterns = ["eels", "edx", "spectrum", "spec"]
    if any(pattern in filename for pattern in spectroscopy_patterns):
        logger.info("Detected spectroscopy data from filename: %s", filename)
        metadata["nx_meta"]["DatasetType"] = "Spectrum"

    return metadata


# Create the instrument profile
# IMPORTANT: Change this instrument_id to match your instrument's name in the database
my_instrument_profile = InstrumentProfile(
    instrument_id="My-Custom-Instrument-ID",  # ← CHANGE THIS
    parsers={
        # Parser functions are executed in order
        "facility": add_facility_metadata,
        "warnings": add_instrument_warnings,
        "acquisition_mode": detect_special_acquisition_mode,
    },
    static_metadata={
        # Static metadata is injected after all parsers run
        # Use dot notation for nested keys
        "nx_meta.Instrument_Owner": "My Research Group",
        "nx_meta.Funding_Agency": "NSF Grant #12345",
    },
    # Optional: override which extractor to use for specific file types
    # extractor_overrides={
    #     "tif": "custom_tif_extractor",  # Use custom TIF extractor
    # },
)

# Register the profile with the global registry
get_profile_registry().register(my_instrument_profile)

logger.info("Registered local profile for: %s", my_instrument_profile.instrument_id)
