"""
Pint unit registry and utilities for NexusLIMS metadata.

This module provides a centralized Pint unit registry for handling physical quantities
with units in NexusLIMS metadata. It defines preferred units for different measurement
types and provides utilities for normalizing quantities to these preferred units.

The module supports three-tiered unit serialization:
- **Tier 1 (Internal)**: Pint Quantity objects with QUDT/EMG mappings
- **Tier 2 (XML)**: Clean name/value/unit separation using XSD unit attribute
- **Tier 3 (Future)**: Optional QUDT/EMG URIs for semantic web integration

Examples
--------
Create and normalize quantities:

>>> from nexusLIMS.schemas.units import ureg, normalize_quantity
>>> voltage = ureg.Quantity(10000, "volt")
>>> normalized = normalize_quantity("acceleration_voltage", voltage)
>>> print(normalized)
10.0 kilovolt

Parse from strings:

>>> from nexusLIMS.schemas.units import parse_quantity
>>> voltage = parse_quantity("acceleration_voltage", "10 kV")
>>> print(voltage)
10.0 kilovolt

Serialize for XML:

>>> from nexusLIMS.schemas.units import quantity_to_xml_parts
>>> name, value, unit = quantity_to_xml_parts("acceleration_voltage", voltage)
>>> print(f"<meta name='{name}' unit='{unit}'>{value}</meta>")
<meta name='Voltage' unit='kV'>10.0</meta>
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pint import UnitRegistry
from rdflib import RDFS, Graph, Namespace

logger = logging.getLogger(__name__)

# Singleton Pint unit registry for the entire application
# Using this ensures consistent unit definitions across all modules
ureg = UnitRegistry()

# Path to QUDT unit vocabulary file
QUDT_UNIT_TTL_PATH = Path(__file__).parent / "references" / "qudt_unit.ttl"
QUDT_VERSION = "3.1.9"

# RDF namespace for QUDT
QUDT_UNIT = Namespace("http://qudt.org/vocab/unit/")

# Define common abbreviations and aliases
ureg.define("ppm = 1e-6 = ppm")  # Ensure ppm is defined
ureg.define("percent = 0.01 = pct = %")  # Define percent

# Magic values for scientific notation formatting
_MIN_MAGNITUDE_FOR_NORMAL_NOTATION = 1e-3
_MAX_MAGNITUDE_FOR_NORMAL_NOTATION = 1e6

# Preferred units for each field type
# These define the canonical units that quantities should be normalized to
# before serialization to XML or storage
PREFERRED_UNITS = {
    # Image acquisition parameters
    "acceleration_voltage": ureg.kilovolt,
    "working_distance": ureg.millimeter,
    "beam_current": ureg.picoampere,
    "emission_current": ureg.microampere,
    "dwell_time": ureg.microsecond,
    "magnification": ureg.dimensionless,  # Magnification has no units
    "field_of_view": ureg.micrometer,
    "pixel_width": ureg.nanometer,
    "pixel_height": ureg.nanometer,
    "scan_rotation": ureg.degree,
    # Stage position components
    "stage_x": ureg.micrometer,
    "stage_y": ureg.micrometer,
    "stage_z": ureg.millimeter,
    "stage_tilt": ureg.degree,
    "stage_rotation": ureg.degree,
    "stage_alpha": ureg.degree,
    "stage_beta": ureg.degree,
    # Spectrum acquisition parameters
    "acquisition_time": ureg.second,
    "live_time": ureg.second,
    "detector_energy_resolution": ureg.eV,
    "channel_size": ureg.eV,
    "starting_energy": ureg.keV,
    "azimuthal_angle": ureg.degree,
    "elevation_angle": ureg.degree,
    "takeoff_angle": ureg.degree,
    # Diffraction parameters
    "camera_length": ureg.millimeter,
    "convergence_angle": ureg.milliradian,
    # Environmental parameters
    "temperature": ureg.kelvin,
    "pressure": ureg.pascal,
    "chamber_pressure": ureg.pascal,
}


@lru_cache(maxsize=1)
def _load_qudt_units() -> dict[str, str]:
    """
    Load QUDT unit URIs from the Turtle file.

    Parses the QUDT unit vocabulary to extract unit labels and their URIs.
    This provides a mapping from Pint unit names to QUDT ontology URIs.

    Returns
    -------
    dict[str, str]
        Mapping from unit_name -> QUDT URI

    Examples
    --------
    >>> units = _load_qudt_units()
    >>> units.get("kilovolt")
    'http://qudt.org/vocab/unit/KiloV'

    Notes
    -----
    Results are cached for performance. The mapping uses rdfs:label to match
    Pint unit names (e.g., "kilovolt") to QUDT URIs.
    """
    if not QUDT_UNIT_TTL_PATH.exists():
        logger.warning("QUDT unit file not found at %s", QUDT_UNIT_TTL_PATH)
        return {}

    try:
        g = Graph()
        g.parse(QUDT_UNIT_TTL_PATH, format="turtle")
        logger.debug("Loaded QUDT unit vocabulary from %s", QUDT_UNIT_TTL_PATH)
    except Exception:
        logger.exception("Failed to parse QUDT unit file.")
        return {}

    # Build mapping from label -> URI
    unit_map = {}

    # Iterate over all QUDT unit instances
    for unit_uri in g.subjects(predicate=RDFS.label):
        if not str(unit_uri).startswith(str(QUDT_UNIT)):
            continue

        # Get the label(s) for this unit
        for label_obj in g.objects(unit_uri, RDFS.label):
            label = str(label_obj).lower().replace(" ", "")

            # Map label to URI
            unit_map[label] = str(unit_uri)

    logger.debug("Loaded %s QUDT unit mappings", len(unit_map))
    return unit_map


# Lazy-loaded QUDT unit URI mappings via lru_cache
@lru_cache(maxsize=1)
def _get_qudt_uri_mapping() -> dict[str, str]:
    """Get the QUDT unit URI mapping, loading if necessary."""
    return _load_qudt_units()


def normalize_quantity(field_name: str, quantity: Any) -> Any:
    """
    Normalize a quantity to its preferred unit for the given field.

    Takes a Pint Quantity and converts it to the canonical unit defined
    in PREFERRED_UNITS for that field. If no preferred unit is defined,
    returns the quantity unchanged. Non-Quantity values are passed through.

    Parameters
    ----------
    field_name : str
        The metadata field name (e.g., "acceleration_voltage", "working_distance")
    quantity : Any
        The quantity to normalize. Can be:
        - Pint Quantity object (will be converted)
        - String (returned unchanged - use parse_quantity first)
        - Numeric value (returned unchanged)
        - None (returned unchanged)

    Returns
    -------
    Any
        The normalized quantity in preferred units, or the original value
        if not a Quantity or no preferred unit is defined

    Examples
    --------
    >>> voltage = ureg.Quantity(10000, "volt")
    >>> normalized = normalize_quantity("acceleration_voltage", voltage)
    >>> print(normalized)
    10.0 kilovolt

    >>> current = ureg.Quantity(0.1, "nanoampere")
    >>> normalized = normalize_quantity("beam_current", current)
    >>> print(normalized)
    100.0 picoampere

    >>> # Non-Quantity values pass through
    >>> normalize_quantity("unknown_field", "some string")
    'some string'

    >>> # Fields without preferred units return unchanged
    >>> qty = ureg.Quantity(5.0, "furlong")
    >>> normalize_quantity("custom_field", qty) == qty
    True
    """
    # Only process Pint Quantity objects
    if not isinstance(quantity, ureg.Quantity):
        return quantity

    # Get preferred unit for this field
    preferred_unit = PREFERRED_UNITS.get(field_name)

    if preferred_unit is None:
        # No preferred unit defined, return as-is
        return quantity

    try:
        # Convert to preferred unit
        return quantity.to(preferred_unit)
    except Exception as e:
        # Log conversion error but don't fail - return original
        logger.warning(
            "Could not convert %s from %s to %s: %s. Returning original value.",
            field_name,
            quantity.units,
            preferred_unit,
            e,
        )
        return quantity


def parse_quantity(field_name: str, value: Any) -> Any:
    """
    Parse a value into a Pint Quantity and normalize to preferred units.

    Accepts multiple input types:
    - Pint Quantity: Normalized to preferred units
    - String: Parsed as quantity (e.g., "10 kV", "5.2 mm")
    - Numeric: Assumed to be in preferred units for field
    - None: Passed through unchanged

    Parameters
    ----------
    field_name : str
        The metadata field name (e.g., "acceleration_voltage")
    value : Any
        The value to parse. Can be Quantity, string, numeric, or None

    Returns
    -------
    Any
        Pint Quantity in preferred units, or original value if unparseable

    Examples
    --------
    >>> qty = parse_quantity("acceleration_voltage", "10 kV")
    >>> print(qty)
    10.0 kilovolt

    >>> qty = parse_quantity("working_distance", 5.2)  # Assumes mm
    >>> print(qty)
    5.2 millimeter

    >>> qty = parse_quantity("beam_current", ureg.Quantity(0.1, "nA"))
    >>> print(qty)
    100.0 picoampere

    >>> parse_quantity("operator", None) is None
    True
    """
    # Pass through None
    if value is None:
        return value

    # If already a Quantity, normalize it
    if isinstance(value, ureg.Quantity):
        return normalize_quantity(field_name, value)

    # Try parsing string as quantity
    if isinstance(value, str):
        try:
            qty = ureg.Quantity(value)
            return normalize_quantity(field_name, qty)
        except Exception as e:
            logger.debug(
                "Could not parse '%s' as quantity for %s: %s", value, field_name, e
            )

    # For numeric values, assume they're in the preferred unit
    if isinstance(value, (int, float)):
        preferred_unit = PREFERRED_UNITS.get(field_name)
        if preferred_unit is not None:
            return ureg.Quantity(value, preferred_unit)

    # All other cases (unparseable strings, unknown types, or no preferred unit)
    return value


def quantity_to_xml_parts(
    field_name: str, quantity: Any
) -> tuple[str, str, str | None]:
    """
    Convert a field name and quantity to XML serialization parts.

    Extracts the display name, numeric value, and unit string for XML
    serialization. This enables clean XML output like:
    ``<meta name="Voltage" unit="kV">10.0</meta>``

    Parameters
    ----------
    field_name : str
        The internal field name (e.g., "acceleration_voltage")
    quantity : Any
        The quantity value (Pint Quantity, string, or numeric)

    Returns
    -------
    tuple[str, str, str | None]
        A 3-tuple of (display_name, value_string, unit_string)
        - display_name: Human-readable field name for XML
        - value_string: Numeric value as string
        - unit_string: Unit abbreviation, or None if dimensionless/non-quantity

    Examples
    --------
    >>> qty = ureg.Quantity(10.0, "kilovolt")
    >>> name, value, unit = quantity_to_xml_parts("acceleration_voltage", qty)
    >>> print(f"<meta name='{name}' unit='{unit}'>{value}</meta>")
    <meta name='Voltage' unit='kV'>10.0</meta>

    >>> qty = ureg.Quantity(5000, "dimensionless")
    >>> name, value, unit = quantity_to_xml_parts("magnification", qty)
    >>> print(f"<meta name='{name}'>{value}</meta>")  # No unit attr
    <meta name='Magnification'>5000</meta>

    Notes
    -----
    For non-Quantity values, the value is converted to string and unit is None.
    Display name mapping is handled by separate EM Glossary utilities.
    """
    from nexusLIMS.schemas.em_glossary import (  # noqa: PLC0415
        get_display_name,
    )  # Import here to avoid circular imports

    display_name = get_display_name(field_name)

    if isinstance(quantity, ureg.Quantity):
        # Format magnitude (use scientific notation for very small/large)
        magnitude = quantity.magnitude
        if (
            abs(magnitude) < _MIN_MAGNITUDE_FOR_NORMAL_NOTATION
            or abs(magnitude) > _MAX_MAGNITUDE_FOR_NORMAL_NOTATION
        ):
            value_str = f"{magnitude:.6e}"
        else:
            value_str = f"{magnitude:.6g}"

        # Get unit string (use compact format)
        unit_str = f"{quantity.units:~}"  # Compact format (kV instead of kilovolt)

        # Handle dimensionless
        if quantity.dimensionless:
            unit_str = None

        return display_name, value_str, unit_str

    # Non-Quantity value
    return display_name, str(quantity), None


def get_qudt_uri(quantity: Any) -> str | None:
    """
    Get the QUDT URI for a Pint Quantity's unit.

    Returns the QUDT (Quantities, Units, Dimensions and Data Types) ontology
    URI for the quantity's unit. This enables Tier 3 semantic web integration.

    The mapping is loaded dynamically from the QUDT unit vocabulary file
    (qudt_unit.ttl) using RDFLib.

    Parameters
    ----------
    quantity : Any
        A Pint Quantity object

    Returns
    -------
    str or None
        QUDT URI string, or None if not a Quantity or URI not found

    Examples
    --------
    >>> qty = ureg.Quantity(10, "kilovolt")
    >>> get_qudt_uri(qty)
    'http://qudt.org/vocab/unit/KiloV'

    >>> qty = ureg.Quantity(5.2, "millimeter")
    >>> get_qudt_uri(qty)
    'http://qudt.org/vocab/unit/MilliM'

    >>> get_qudt_uri("not a quantity")
    # Returns None
    """
    if not isinstance(quantity, ureg.Quantity):
        return None

    # Get unit string (full name, lowercase, no spaces for matching)
    unit_str = str(quantity.units).lower().replace(" ", "")

    # Look up in QUDT mapping (loaded from TTL file)
    qudt_map = _get_qudt_uri_mapping()
    return qudt_map.get(unit_str)


def serialize_quantity(quantity: Any) -> dict[str, Any]:
    """
    Serialize a Pint Quantity to a JSON-compatible dictionary.

    Converts a Quantity to a dict with 'value' and 'units' keys.
    Used for internal storage or JSON export. For XML serialization,
    use :func:`quantity_to_xml_parts` instead.

    Parameters
    ----------
    quantity : Any
        A Pint Quantity object, or other value to serialize

    Returns
    -------
    dict[str, Any]
        Dictionary with 'value' and 'units' keys if Quantity,
        or {'value': quantity} for non-Quantity values

    Examples
    --------
    >>> qty = ureg.Quantity(10, "kilovolt")
    >>> serialize_quantity(qty)
    {'value': 10.0, 'units': 'kilovolt'}

    >>> serialize_quantity("some string")
    {'value': 'some string'}
    """
    if isinstance(quantity, ureg.Quantity):
        return {
            "value": quantity.magnitude,
            "units": str(quantity.units),
        }
    return {"value": quantity}


def deserialize_quantity(data: dict[str, Any]) -> Any:
    """
    Deserialize a dictionary back to a Pint Quantity.

    Reverses the operation of :func:`serialize_quantity`. Takes a dict
    with 'value' and 'units' keys and reconstructs the Quantity.

    Parameters
    ----------
    data : dict[str, Any]
        Dictionary with 'value' and 'units' keys, or just 'value' key

    Returns
    -------
    Any
        Pint Quantity if dict has value/units, otherwise the 'value' field

    Examples
    --------
    >>> data = {'value': 10.0, 'units': 'kilovolt'}
    >>> qty = deserialize_quantity(data)
    >>> print(qty)
    10.0 kilovolt

    >>> data = {'value': 'some string'}
    >>> deserialize_quantity(data)
    'some string'
    """
    if "units" in data:
        return ureg.Quantity(data["value"], data["units"])
    return data.get("value")
