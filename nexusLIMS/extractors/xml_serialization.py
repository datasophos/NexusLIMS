"""
XML serialization utilities for NexusLIMS metadata schemas.

This module provides utilities for converting type-specific metadata schemas
(using Pint Quantities and EM Glossary terminology) into XML format compatible
with the Nexus Experiment schema.

Key Functions
-------------
- serialize_quantity_to_xml: Convert Pint Quantities to value/unit pairs for XML
- get_xml_field_name: Map EM Glossary field names to human-readable display names
- prepare_metadata_for_xml: Convert rich metadata to XML-compatible flat dict

Examples
--------
Convert a Pint Quantity to XML:

>>> from nexusLIMS.schemas.units import ureg
>>> qty = ureg.Quantity(10, "kilovolt")
>>> value, unit = serialize_quantity_to_xml(qty)
>>> value, unit
(10.0, 'kV')

Get human-readable field name for XML:

>>> get_xml_field_name("acceleration_voltage")
'Voltage'
>>> get_xml_field_name("working_distance")
'Working Distance'
"""

from typing import Any

from pint import Quantity

from nexusLIMS.schemas import em_glossary
from nexusLIMS.schemas.units import get_qudt_uri as _get_qudt_uri
from nexusLIMS.schemas.units import ureg

# Mapping from EM Glossary field names to human-readable XML display names
# This maintains backward compatibility with existing XML field names
EM_GLOSSARY_TO_XML_DISPLAY_NAMES = {
    # Imaging fields (common)
    "acceleration_voltage": "Voltage",
    "working_distance": "Working Distance",
    "beam_current": "Beam Current",
    "emission_current": "Emission Current",
    "magnification": "Magnification",
    "dwell_time": "Pixel Dwell Time",
    "horizontal_field_width": "Horizontal Field Width",
    "pixel_width": "Pixel Width",
    "scan_rotation": "Scan Rotation",
    "detector_type": "Detector",
    # Spectrum fields
    "acquisition_time": "Acquisition Time",
    "live_time": "Live Time",
    "detector_energy_resolution": "Energy Resolution",
    "channel_size": "Channel Size",
    "starting_energy": "Starting Energy",
    "azimuthal_angle": "Azimuthal Angle",
    "elevation_angle": "Elevation Angle",
    "elements": "Elements",
    # Diffraction fields
    "camera_length": "Camera Length",
    "convergence_angle": "Convergence Angle",
    "diffraction_mode": "Diffraction Mode",
    # Stage position fields
    "stage_position": "Stage Position",
    "stage_x": "Stage X",
    "stage_y": "Stage Y",
    "stage_z": "Stage Z",
    "stage_tilt": "Stage Tilt",
    "stage_tilt_alpha": "Stage Tilt",  # Primary tilt axis
    "stage_tilt_beta": "Stage Tilt Beta",  # Secondary tilt axis
    "stage_rotation": "Stage Rotation",
    # Data fields (core)
    "acquisition_timestamp": "Creation Time",
    "data_type": "Data Type",
    "dataset_type": "DatasetType",
    "data_dimensions": "Data Dimensions",
    "instrument_id": "Instrument ID",
    # Legacy/compatibility fields (old schema)
    "Voltage": "Voltage",
    "Working Distance": "Working Distance",
    "Beam Current": "Beam Current",
    "Magnification": "Magnification",
    "Detector": "Detector",
    "Creation Time": "Creation Time",
    "Data Type": "Data Type",
    "DatasetType": "DatasetType",
    "Data Dimensions": "Data Dimensions",
    "Instrument ID": "Instrument ID",
}


def serialize_quantity_to_xml(qty: Quantity) -> tuple[float, str]:
    """
    Convert a Pint Quantity to value and unit strings for XML serialization.

    This function extracts the magnitude and unit from a Pint Quantity object
    and formats them for use in XML meta elements with the `unit` attribute.

    Parameters
    ----------
    qty : Quantity
        The Pint Quantity object to serialize

    Returns
    -------
    value : float
        The numeric magnitude of the quantity
    unit : str
        The unit symbol in compact form (e.g., "kV", "mm", "pA")

    Examples
    --------
    >>> from nexusLIMS.schemas.units import ureg
    >>> qty = ureg.Quantity(10, "kilovolt")
    >>> value, unit = serialize_quantity_to_xml(qty)
    >>> value
    10.0
    >>> unit
    'kV'

    >>> qty = ureg.Quantity(5.2, "millimeter")
    >>> value, unit = serialize_quantity_to_xml(qty)
    >>> value
    5.2
    >>> unit
    'mm'

    Notes
    -----
    The unit is formatted using Pint's compact format (~) which produces
    short unit symbols suitable for display in XML attributes.
    """
    # Extract magnitude as float
    magnitude = float(qty.magnitude)

    # Format unit in compact form (e.g., "kV" instead of "kilovolt")
    unit_str = f"{qty.units:~}"

    return magnitude, unit_str


def get_xml_field_name(field_name: str) -> str:
    """
    Map an EM Glossary field name to a human-readable XML display name.

    This function provides the translation layer between EM Glossary terminology
    (used internally in metadata schemas) and the human-readable field names
    used in XML output. It maintains backward compatibility with existing XML
    field names.

    Parameters
    ----------
    field_name : str
        The internal EM Glossary field name (e.g., "acceleration_voltage")

    Returns
    -------
    display_name : str
        The human-readable display name for XML (e.g., "Voltage")

    Examples
    --------
    >>> get_xml_field_name("acceleration_voltage")
    'Voltage'
    >>> get_xml_field_name("working_distance")
    'Working Distance'
    >>> get_xml_field_name("detector_type")
    'Detector'

    For unknown fields, returns the field name with underscores replaced by spaces
    and title-cased:

    >>> get_xml_field_name("some_custom_field")
    'Some Custom Field'

    Notes
    -----
    This function prioritizes backward compatibility with existing XML field names.
    New fields should be added to EM_GLOSSARY_TO_XML_DISPLAY_NAMES to control
    their XML representation.
    """
    # Check if we have an explicit mapping
    if field_name in EM_GLOSSARY_TO_XML_DISPLAY_NAMES:
        return EM_GLOSSARY_TO_XML_DISPLAY_NAMES[field_name]

    # For unknown fields, convert snake_case to Title Case
    # This handles instrument-specific fields not in the mapping
    return field_name.replace("_", " ").title()


def prepare_metadata_for_xml(
    metadata: dict[str, Any],
) -> dict[str, str | float]:
    """
    Prepare rich metadata for XML serialization.

    Converts metadata from the new schema format (with Pint Quantities, nested
    structures, etc.) into a flat dictionary suitable for XML serialization.
    This includes:

    1. Converting Pint Quantity objects to separate value/unit entries
    2. Flattening nested structures (like StagePosition)
    3. Mapping EM Glossary field names to XML display names
    4. Preserving non-Quantity values as-is

    Parameters
    ----------
    metadata : dict[str, Any]
        Metadata dictionary from type-specific schema (ImageMetadata, etc.)
        May contain Pint Quantities, nested dicts, or simple values

    Returns
    -------
    xml_metadata : dict[str, str | float]
        Flat dictionary with XML-compatible field names and values.
        For Quantity fields, creates two entries:
        - "<field_name>": numeric value
        - "<field_name>_unit": unit string

    Examples
    --------
    >>> from nexusLIMS.schemas.units import ureg
    >>> metadata = {
    ...     "acceleration_voltage": ureg.Quantity(10, "kilovolt"),
    ...     "magnification": 50000,
    ...     "detector_type": "ETD",
    ... }
    >>> xml_dict = prepare_metadata_for_xml(metadata)
    >>> xml_dict["Voltage"]
    10.0
    >>> xml_dict["Voltage_unit"]
    'kV'
    >>> xml_dict["Magnification"]
    50000
    >>> xml_dict["Detector"]
    'ETD'

    Notes
    -----
    This function is designed to work with both the new schema format and
    legacy metadata dicts for backward compatibility during migration.
    """
    xml_dict = {}

    for field_name, value in metadata.items():
        # Skip None values and internal fields
        if value is None:
            continue
        if field_name in {"warnings", "schema_version", "extensions"}:
            continue

        # Get the XML display name for this field
        xml_name = get_xml_field_name(field_name)

        # Handle Pint Quantity objects
        if isinstance(value, Quantity):
            magnitude, unit = serialize_quantity_to_xml(value)
            xml_dict[xml_name] = magnitude
            xml_dict[f"{xml_name}_unit"] = unit

        # Handle nested StagePosition dict
        elif field_name == "stage_position" and isinstance(value, dict):
            for axis, axis_value in value.items():
                if axis_value is None:
                    continue
                axis_xml_name = get_xml_field_name(f"stage_{axis.lower()}")
                if isinstance(axis_value, Quantity):
                    mag, unit = serialize_quantity_to_xml(axis_value)
                    xml_dict[axis_xml_name] = mag
                    xml_dict[f"{axis_xml_name}_unit"] = unit
                else:
                    xml_dict[axis_xml_name] = axis_value

        # Handle list values (e.g., elements list)
        elif isinstance(value, list):
            # Convert list to comma-separated string
            xml_dict[xml_name] = ", ".join(str(v) for v in value)

        # Handle all other values (strings, numbers, etc.)
        else:
            xml_dict[xml_name] = value

    return xml_dict


def get_qudt_uri(field_name: str, unit: str) -> str | None:  # noqa: ARG001
    """
    Get the QUDT URI for a given field's unit.

    This function looks up the QUDT (Quantities, Units, Dimensions and Types)
    ontology URI for a given unit string. Used for Tier 3 semantic web
    integration (future enhancement).

    Parameters
    ----------
    field_name : str
        The field name (currently unused, reserved for future context-aware lookups)
    unit : str
        The unit string in compact form (e.g., "kV", "mm", "pA")

    Returns
    -------
    qudt_uri : str or None
        The QUDT URI for this unit, or None if no mapping exists

    Examples
    --------
    >>> get_qudt_uri("acceleration_voltage", "kV")  # doctest: +SKIP
    'http://qudt.org/vocab/unit/KiloV'
    >>> get_qudt_uri("working_distance", "mm")  # doctest: +SKIP
    'http://qudt.org/vocab/unit/MilliM'

    Notes
    -----
    This function is currently a placeholder for Tier 3 implementation.
    It will use the QUDT mapping system from `nexusLIMS.schemas.units`
    when Tier 3 semantic attributes are added to the XML schema.
    """
    # Parse unit string to Pint unit and create a Quantity
    try:
        # Create a quantity with magnitude 1 to get the unit object
        qty = ureg.Quantity(1, unit)
    except Exception:
        return None

    # Look up QUDT URI using the Quantity object
    return _get_qudt_uri(qty)


def get_emg_id(field_name: str) -> str | None:
    """
    Get the EM Glossary ID for a given field name.

    This function looks up the EM Glossary term ID for a field name,
    if one exists. Used for Tier 3 semantic web integration (future enhancement).

    Parameters
    ----------
    field_name : str
        The internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    emg_id : str or None
        The EM Glossary ID (e.g., "EMG_00000004"), or None if no mapping exists

    Examples
    --------
    >>> get_emg_id("acceleration_voltage")
    'EMG_00000004'
    >>> get_emg_id("working_distance")
    'EMG_00000050'
    >>> get_emg_id("some_custom_field")

    Notes
    -----
    This function is used for Tier 3 implementation where EM Glossary IDs
    are added as XML attributes for semantic traceability.
    """
    return em_glossary.get_emg_id(field_name)
