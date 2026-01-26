# ruff: noqa: ARG001
"""Instrument profile for FEI Titan TEM (642 microscope)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from benedict import benedict

from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry
from nexusLIMS.utils.dicts import (
    set_nested_dict_value,
    try_getting_dict_value,
)

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import ExtractionContext

_logger = logging.getLogger(__name__)


def parse_tecnai_metadata(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Parse Tecnai-specific metadata from ImageTags.Tecnai.Microscope_Info.

    The 642 Titan TEM stores extensive microscope parameters in a delimited
    string format that needs special parsing.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context (unused but required by profile signature)

    Returns
    -------
    dict
        Modified metadata dictionary with parsed Tecnai metadata
    """
    # Import the processing function from the DM3 extractor
    from nexusLIMS.extractors.plugins.digital_micrograph import (  # noqa: PLC0415
        process_tecnai_microscope_info,
    )

    # Check if Tecnai metadata exists using benedict's keypaths method
    b = benedict(metadata)
    keypaths_list = b.keypaths()

    # Find the keypath that ends with "Tecnai"
    path_to_tecnai = None
    for keypath in keypaths_list:
        if keypath.endswith(".Tecnai") or keypath == "Tecnai":
            path_to_tecnai = keypath.split(".")
            break

    if path_to_tecnai is None:
        # For whatever reason, the expected Tecnai Tag is not present,
        # so return to prevent errors below
        return metadata

    tecnai_value = b[".".join(path_to_tecnai)]
    microscope_info = tecnai_value["Microscope Info"]
    tecnai_value["Microscope Info"] = process_tecnai_microscope_info(microscope_info)
    set_nested_dict_value(metadata, path_to_tecnai, tecnai_value)

    # Map Tecnai metadata fields to nx_meta fields
    term_mapping = {
        "Gun_Name": "Gun Name",
        "Extractor_Voltage": "Extractor Voltage (V)",
        "Camera_Length": "Camera Length (m)",
        "Gun_Lens_No": "Gun Lens #",
        "Emission_Current": "Emission Current (μA)",
        "Spot": "Spot",
        "Mode": "Tecnai Mode",
        "Defocus": "Defocus",
        "C2_Strength": "C2 Lens Strength (%)",
        "C3_Strength": "C3 Lens Strength (%)",
        "Obj_Strength": "Objective Lens Strength (%)",
        "Dif_Strength": "Diffraction Lens Strength (%)",
        "Microscope_Name": "Tecnai Microscope Name",
        "User": "Tecnai User",
        "Image_Shift_x": "Image Shift X (μm)",
        "Image_Shift_y": "Image Shift Y (μm)",
        "Stage_Position_x": ["Stage Position", "X (μm)"],
        "Stage_Position_y": ["Stage Position", "Y (μm)"],
        "Stage_Position_z": ["Stage Position", "Z (μm)"],
        "Stage_Position_theta": ["Stage Position", "θ (°)"],
        "Stage_Position_phi": ["Stage Position", "φ (°)"],
        "C1_Aperture": "C1 Aperture (μm)",
        "C2_Aperture": "C2 Aperture (μm)",
        "Obj_Aperture": "Objective Aperture (μm)",
        "SA_Aperture": "Selected Area Aperture (μm)",
        ("Filter_Settings", "Mode"): ["Tecnai Filter", "Mode"],
        ("Filter_Settings", "Dispersion"): ["Tecnai Filter", "Dispersion (eV/channel)"],
        ("Filter_Settings", "Aperture"): ["Tecnai Filter", "Aperture (mm)"],
        ("Filter_Settings", "Prism_Shift"): ["Tecnai Filter", "Prism Shift (eV)"],
        ("Filter_Settings", "Drift_Tube"): ["Tecnai Filter", "Drift Tube (eV)"],
        ("Filter_Settings", "Total_Energy_Loss"): [
            "Tecnai Filter",
            "Total Energy Loss (eV)",
        ],
    }

    for in_term, out_term in term_mapping.items():
        base = [*list(path_to_tecnai), "Microscope Info"]
        if isinstance(in_term, str):
            in_term = [in_term]  # noqa: PLW2901
        elif isinstance(in_term, tuple):
            in_term = list(in_term)  # noqa: PLW2901
        if isinstance(out_term, str):
            out_term = [out_term]  # noqa: PLW2901
        val = try_getting_dict_value(metadata, base + in_term)
        # only add the value to this list if we found it
        if val is not None and val not in ["DO NOT EDIT", "DO NOT ENTER"]:
            set_nested_dict_value(metadata, ["nx_meta", *out_term], val)

    # Parse specimen info
    path = [*list(path_to_tecnai), "Specimen Info"]
    val = try_getting_dict_value(metadata, path)
    if val is not None and val != "Specimen information is not available yet":
        set_nested_dict_value(metadata, ["nx_meta", "Specimen"], val)

    return metadata


def detect_diffraction_mode(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Detect diffraction patterns by Mode or Operation Mode values.

    The 642 TEM indicates diffraction via specific Mode strings.

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
    # Check Tecnai Mode
    if (
        "Tecnai Mode" in metadata["nx_meta"]
        and metadata["nx_meta"]["Tecnai Mode"] == "STEM nP SA Zoom Diffraction"
    ):
        _logger.info(
            'Detected file as Diffraction type based on "Tecnai '
            'Mode" == "STEM nP SA Zoom Diffraction"',
        )
        metadata["nx_meta"]["DatasetType"] = "Diffraction"
        metadata["nx_meta"]["Data Type"] = "STEM_Diffraction"

    # Check Operation Mode
    elif (
        "Operation Mode" in metadata["nx_meta"]
        and metadata["nx_meta"]["Operation Mode"] == "DIFFRACTION"
    ):
        _logger.info(
            'Detected file as Diffraction type based on "Operation '
            'Mode" == "DIFFRACTION"',
        )
        metadata["nx_meta"]["DatasetType"] = "Diffraction"
        metadata["nx_meta"]["Data Type"] = "TEM_Diffraction"

    return metadata


# Register the profile
fei_titan_tem_642_profile = InstrumentProfile(
    instrument_id="FEI-Titan-TEM",
    parsers={
        "tecnai_metadata": parse_tecnai_metadata,
        "diffraction_detection": detect_diffraction_mode,
    },
    transformations={},
    extension_fields={},
)
"""An instrument profile for the FEI Titan TEM"""

get_profile_registry().register(fei_titan_tem_642_profile)

_logger.debug("Registered FEI Titan TEM (642) instrument profile")
