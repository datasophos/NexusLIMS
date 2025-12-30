"""
EM Glossary field name mappings for NexusLIMS metadata.

This module provides mappings between NexusLIMS internal field names, display names,
and EM Glossary (EMG) standardized terminology. The EM Glossary is a community-driven
ontology for electron microscopy metadata maintained by the Helmholtz Metadata
Collaboration.

The module uses RDFLib to parse the EM Glossary OWL ontology file, providing access
to term labels, definitions, and the full semantic structure.

**EM Glossary Version:** v2.0.0

**References:**
- EM Glossary v2.0.0: [https://purls.helmholtz-metadaten.de/emg/v2.0.0/](https://purls.helmholtz-metadaten.de/emg/v2.0.0/)
- OWL Ontology: Shipped with NexusLIMS at
  `nexusLIMS/schemas/references/em_glossary_2.0.owl`
- License: CC BY 4.0 [https://creativecommons.org/licenses/by/4.0/](https://creativecommons.org/licenses/by/4.0/)

The mappings in this module enable:
- Standardized field names across instruments and vendors
- Cross-reference to EM Glossary IDs for semantic interoperability
- Human-readable display names for XML output
- Dynamic loading from the OWL ontology using [RDFLib](https://rdflib.readthedocs.io/en/stable/index.html)

Examples
--------
Get EM Glossary ID for a field:

>>> from nexusLIMS.schemas.em_glossary import get_emg_id
>>> get_emg_id("acceleration_voltage")
'EMG_00000004'

Get display name for XML:

>>> from nexusLIMS.schemas.em_glossary import get_display_name
>>> get_display_name("acceleration_voltage")
'Voltage'

Get EMG label from ID:

>>> from nexusLIMS.schemas.em_glossary import get_emg_label
>>> get_emg_label("EMG_00000004")
'Acceleration Voltage'

Get EMG definition:

>>> from nexusLIMS.schemas.em_glossary import get_emg_definition
>>> defn = get_emg_definition("EMG_00000004")
>>> print(defn)
The potential difference between anode and cathode.

Check if field has EMG mapping:

>>> from nexusLIMS.schemas.em_glossary import has_emg_id
>>> has_emg_id("acceleration_voltage")
True
>>> has_emg_id("custom_vendor_field")
False
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict

from rdflib import RDF, RDFS, Graph, Namespace

_logger = logging.getLogger(__name__)

EMG_OWL_PATH = Path(__file__).parent / "references" / "em_glossary_2.0.owl"
"""Path to the EM Glossary OWL file shipped with NexusLIMS"""

EMG_VERSION = "v2.0.0"
"""Version of the packaged EM Glossary OWL file"""

EMG = Namespace("https://purls.helmholtz-metadaten.de/emg/")
"""RDF Namespace for the EM Glossary"""

OBO = Namespace("http://purl.obolibrary.org/obo/")
"""RDF Namespace for OBO"""


@lru_cache(maxsize=1)
def _load_emg_graph() -> Graph:
    """
    Load the EM Glossary ontology RDF graph.

    Parses the OWL/RDF file and returns an RDFLib Graph object.
    Results are cached for performance.

    Returns
    -------
    rdflib.Graph
        The parsed RDF graph

    Raises
    ------
    FileNotFoundError
        If the OWL file cannot be found
    ValueError
        If the OWL file cannot be parsed
    """
    if not EMG_OWL_PATH.exists():
        msg = f"EM Glossary OWL file not found at {EMG_OWL_PATH}"
        raise FileNotFoundError(msg)

    try:
        g = Graph()
        g.parse(EMG_OWL_PATH, format="xml")
        _logger.debug("Loaded EM Glossary ontology from %s", EMG_OWL_PATH)
        _logger.debug("Graph contains %s triples", len(g))
    except Exception as e:
        msg = f"Failed to parse EM Glossary OWL file: {e}"
        raise ValueError(msg) from e
    return g


@lru_cache(maxsize=1)
def _load_emg_terms() -> Dict[str, Dict[str, str]]:
    """
    Load EM Glossary terms with labels and definitions.

    Extracts all EMG terms from the ontology graph with their labels
    and definitions (if available).

    Returns
    -------
    dict[str, dict[str, str]]
        Mapping from EMG_ID -> {'label': str, 'definition': str | None}

    Examples
    --------
    >>> terms = _load_emg_terms()
    >>> terms['EMG_00000004']['label']
    'Acceleration Voltage'
    """
    g = _load_emg_graph()

    emg_terms = {}

    # Query for all EMG Class URIs with labels
    for s in g.subjects(RDF.type, None):
        uri_str = str(s)
        if not uri_str.startswith(str(EMG)):
            continue

        # Extract EMG ID from URI
        emg_id = uri_str.split("/")[-1]
        if not emg_id.startswith("EMG_"):
            continue

        # Get label
        label = None
        for o in g.objects(s, RDFS.label):
            label = str(o)
            break  # Take first label

        if label is None:
            continue

        # Get definition (IAO_0000115 is the standard definition property)
        definition = None
        for o in g.objects(s, OBO.IAO_0000115):
            definition = str(o)
            break  # Take first definition

        emg_terms[emg_id] = {
            "label": label,
            "definition": definition,
        }

    if not emg_terms:
        msg = "No EMG terms found in OWL file. File may be corrupted."
        raise ValueError(msg)

    _logger.debug("Loaded %s EMG terms from ontology", len(emg_terms))
    return emg_terms


# Mapping from NexusLIMS internal field names to EM Glossary terms
# Format: internal_field_name -> (display_name, emg_label or None, description)
# The emg_label is used to look up the EMG_ID from the OWL file
NEXUSLIMS_TO_EMG_MAPPINGS: Dict[str, tuple[str, str | None, str]] = {
    # Core acquisition parameters (common to all types)
    "creation_time": (
        "Creation Time",
        None,  # No specific EMG term for timestamp
        "ISO-8601 timestamp with timezone",
    ),
    "data_type": (
        "Data Type",
        None,  # Descriptive field, not in EMG
        "Human-readable data type description",
    ),
    "dataset_type": (
        "DatasetType",
        None,  # Schema-defined category
        "Schema-defined dataset category",
    ),
    # Image acquisition parameters (SEM/TEM/STEM)
    "acceleration_voltage": (
        "Acceleration Voltage",
        "Acceleration Voltage",  # EMG label
        "Accelerating voltage of the electron/ion beam",
    ),
    "working_distance": (
        "Working Distance",
        "Working Distance",  # EMG label
        "Distance between final lens and sample surface",
    ),
    "beam_current": (
        "Beam Current",
        "Beam Current",  # EMG label
        "Electron beam current",
    ),
    "emission_current": (
        "Emission Current",
        "Emission Current",  # EMG label
        "Emission current from electron source",
    ),
    "dwell_time": (
        "Pixel Dwell Time",
        "Dwell Time",  # EMG label
        "Time the beam dwells on each pixel during scanning",
    ),
    "magnification": (
        "Magnification",
        None,  # EMG has Magnification but it's complex
        "Nominal magnification",
    ),
    "horizontal_field_width": (
        "Horizontal Field Width",
        None,  # Not in EMG v2.0.0
        "Width of the scanned area",
    ),
    "vertical_field_width": (
        "Vertical Field Width",
        None,  # Not in EMG v2.0.0
        "Height of the scanned area",
    ),
    "pixel_width": (
        "Pixel Width",
        None,  # Not in EMG v2.0.0
        "Physical width of a single pixel",
    ),
    "pixel_height": (
        "Pixel Height",
        None,  # Not in EMG v2.0.0
        "Physical height of a single pixel",
    ),
    "scan_rotation": (
        "Scan Rotation",
        None,  # Not in EMG v2.0.0
        "Rotation angle of the scan frame",
    ),
    # Detector information
    "detector_type": (
        "Detector",
        None,  # EMG has detector concepts but not simple type field
        "Type or name of detector used",
    ),
    "acquisition_device": (
        "Acquisition Device",
        None,  # Similar to detector_type
        "Name of the acquisition device or camera",
    ),
    # Stage position (common to SEM/TEM)
    "stage_x": (
        "Stage X",
        None,  # Part of complex stage position concept
        "Stage X coordinate",
    ),
    "stage_y": (
        "Stage Y",
        None,  # Part of complex stage position concept
        "Stage Y coordinate",
    ),
    "stage_z": (
        "Stage Z",
        None,  # Part of complex stage position concept
        "Stage Z coordinate",
    ),
    "stage_tilt": (
        "Stage Tilt",
        None,  # Part of complex stage position concept
        "Stage tilt angle (alpha)",
    ),
    "stage_rotation": (
        "Stage Rotation",
        None,  # Part of complex stage position concept
        "Stage rotation angle",
    ),
    "stage_alpha": (
        "Stage Alpha",
        None,  # Part of complex stage position concept
        "Stage alpha tilt angle",
    ),
    "stage_beta": (
        "Stage Beta",
        None,  # Part of complex stage position concept
        "Stage beta tilt angle",
    ),
    # Spectrum acquisition parameters (EDS/EELS)
    "acquisition_time": (
        "Acquisition Time",
        "Acquisition Time",  # EMG label
        "Total time for spectrum acquisition",
    ),
    "live_time": (
        "Live Time",
        None,  # Not in EMG v2.0.0
        "Live time (excludes dead time) for spectrum acquisition",
    ),
    "detector_energy_resolution": (
        "Energy Resolution",
        None,  # Not in EMG v2.0.0
        "Energy resolution of the detector",
    ),
    "channel_size": (
        "Channel Size",
        None,  # Not in EMG v2.0.0
        "Energy width of each channel",
    ),
    "starting_energy": (
        "Starting Energy",
        None,  # Not in EMG v2.0.0
        "Starting energy of the spectrum",
    ),
    "azimuthal_angle": (
        "Azimuthal Angle",
        None,  # Not in EMG v2.0.0
        "Azimuthal angle of the detector",
    ),
    "elevation_angle": (
        "Elevation Angle",
        None,  # Not in EMG v2.0.0
        "Elevation angle of the detector",
    ),
    "takeoff_angle": (
        "Takeoff Angle",
        None,  # Not in EMG v2.0.0
        "X-ray takeoff angle",
    ),
    # Diffraction parameters (TEM)
    "camera_length": (
        "Camera Length",
        "Camera Length",  # EMG label
        "Camera length for diffraction pattern",
    ),
    "convergence_angle": (
        "Convergence Angle",
        "Convergence Angle",  # EMG label
        "Convergence angle of the electron beam",
    ),
    "illumination_mode": (
        "Illumination Mode",
        None,  # Not in EMG v2.0.0
        "TEM illumination mode (TEM, STEM, Diffraction, etc.)",
    ),
    # Sample/metadata
    "specimen": (
        "Specimen",
        None,  # EMG has Specimen but it's complex
        "Sample or specimen description",
    ),
    "operator": (
        "Operator",
        None,  # Not in EMG (user information)
        "User who acquired the data",
    ),
    # Environmental parameters
    "temperature": (
        "Temperature",
        None,  # Not in EMG v2.0.0
        "Sample or chamber temperature",
    ),
    "pressure": (
        "Pressure",
        None,  # Not in EMG v2.0.0
        "Chamber pressure",
    ),
    "chamber_pressure": (
        "Chamber Pressure",
        None,  # Not in EMG v2.0.0
        "Vacuum chamber pressure",
    ),
    # Data dimensions
    "data_dimensions": (
        "Data Dimensions",
        None,  # Not a measurement, structural metadata
        "String representation of data shape",
    ),
    # Instrument identification
    "instrument_id": (
        "Instrument ID",
        None,  # Not in EMG (internal NexusLIMS identifier)
        "NexusLIMS persistent instrument identifier",
    ),
}
"""Mapping from NexusLIMS internal field names to EM Glossary terms
Format: `internal_field_name -> (display_name, emg_label or None, description)`
The emg_label is used to look up the EMG_ID from the OWL file"""


def get_emg_label(emg_id: str) -> str | None:
    """
    Get the EM Glossary label for an EMG ID.

    Looks up the human-readable label from the OWL ontology file.

    Parameters
    ----------
    emg_id : str
        EM Glossary ID (e.g., "EMG_00000004")

    Returns
    -------
    str or None
        EMG label, or None if ID not found

    Examples
    --------
    >>> get_emg_label("EMG_00000004")
    'Acceleration Voltage'

    >>> get_emg_label("EMG_00000050")
    'Working Distance'

    >>> get_emg_label("EMG_99999999") is None
    True
    """
    try:
        emg_terms = _load_emg_terms()
        term_info = emg_terms.get(emg_id)
        return term_info["label"] if term_info else None
    except Exception as e:
        _logger.warning("Failed to load EMG ontology: %s", e)
        return None


def get_emg_definition(emg_id: str) -> str | None:
    """
    Get the EM Glossary definition for an EMG ID.

    Looks up the formal definition from the OWL ontology file.

    Parameters
    ----------
    emg_id : str
        EM Glossary ID (e.g., "EMG_00000004")

    Returns
    -------
    str or None
        EMG definition, or None if ID not found or no definition available

    Examples
    --------
    >>> defn = get_emg_definition("EMG_00000004")
    >>> print(defn)
    The potential difference between anode and cathode.

    >>> get_emg_definition("EMG_99999999") is None
    True
    """
    try:
        emg_terms = _load_emg_terms()
        term_info = emg_terms.get(emg_id)
        return term_info["definition"] if term_info else None
    except Exception as e:
        _logger.warning("Failed to load EMG ontology: %s", e)
        return None


def get_emg_id(field_name: str) -> str | None:
    """
    Get the EM Glossary ID for a NexusLIMS field name.

    Looks up the field in NEXUSLIMS_TO_EMG_MAPPINGS, then resolves the
    EMG label to an ID from the OWL ontology.

    Parameters
    ----------
    field_name : str
        Internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    str or None
        EM Glossary ID string (e.g., "EMG_00000004"), or None if not mapped

    Examples
    --------
    >>> get_emg_id("acceleration_voltage")
    'EMG_00000004'

    >>> get_emg_id("working_distance")
    'EMG_00000050'

    >>> get_emg_id("custom_field") is None
    True

    Notes
    -----
    Not all NexusLIMS fields have EM Glossary equivalents. This is expected
    as EMG is a growing ontology and some fields are vendor-specific or
    outside the scope of EMG's current coverage (v2.0.0).
    """
    mapping = NEXUSLIMS_TO_EMG_MAPPINGS.get(field_name)
    if mapping is None or mapping[1] is None:
        return None

    emg_label = mapping[1]

    # Look up the EMG ID from the label
    try:
        emg_terms = _load_emg_terms()
        # Reverse lookup: label -> ID
        for emg_id, term_info in emg_terms.items():
            if term_info["label"] == emg_label:
                return emg_id
    except Exception as e:
        _logger.warning("Failed to load EMG ontology: %s", e)
        return None

    _logger.debug("EMG label '%s' not found in ontology", emg_label)
    return None


def get_display_name(field_name: str) -> str:
    """
    Get the human-readable display name for a field.

    Returns the display name used in XML output and user-facing documentation.
    If the field is not in the mapping, returns a title-cased version of the
    field name with underscores replaced by spaces.

    Parameters
    ----------
    field_name : str
        Internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    str
        Display name for the field

    Examples
    --------
    >>> get_display_name("acceleration_voltage")
    'Voltage'

    >>> get_display_name("working_distance")
    'Working Distance'

    >>> get_display_name("custom_field")
    'Custom Field'

    Notes
    -----
    For unmapped fields, the function applies a simple transformation:
    replace underscores with spaces and title-case the result. This ensures
    all fields have reasonable display names even without explicit mappings.
    """
    mapping = NEXUSLIMS_TO_EMG_MAPPINGS.get(field_name)
    if mapping is not None:
        return mapping[0]  # Return display name (first element of tuple)

    # Fallback: convert field_name to Title Case
    return field_name.replace("_", " ").title()


def get_description(field_name: str) -> str | None:
    """
    Get the NexusLIMS description for a field.

    Returns a brief description of what the field represents from the
    NexusLIMS mappings. For EMG formal definitions, use get_emg_definition().

    Parameters
    ----------
    field_name : str
        Internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    str or None
        Field description, or None if not mapped

    Examples
    --------
    >>> desc = get_description("acceleration_voltage")
    >>> print(desc)
    Accelerating voltage of the electron/ion beam

    >>> get_description("unknown_field") is None
    True
    """
    mapping = NEXUSLIMS_TO_EMG_MAPPINGS.get(field_name)
    if mapping is None:
        return None
    return mapping[2]  # Return description (third element of tuple)


def has_emg_id(field_name: str) -> bool:
    """
    Check if a field has an EM Glossary ID mapping.

    Returns True if the field has a corresponding EMG ID in v2.0.0, False otherwise.
    This is useful for determining whether semantic annotations are available.

    Parameters
    ----------
    field_name : str
        Internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    bool
        True if field has EMG ID, False otherwise

    Examples
    --------
    >>> has_emg_id("acceleration_voltage")
    True

    >>> has_emg_id("magnification")
    False

    >>> has_emg_id("custom_field")
    False
    """
    emg_id = get_emg_id(field_name)
    return emg_id is not None


def get_emg_uri(field_name: str) -> str | None:
    """
    Get the full EM Glossary URI for a field.

    Returns the complete PURL (Persistent URL) for the field's EM Glossary
    v2.0.0 entry. This enables Tier 3 semantic web integration and linkage to
    the full EMG ontology.

    Parameters
    ----------
    field_name : str
        Internal field name (e.g., "acceleration_voltage")

    Returns
    -------
    str or None
        Full EMG PURL, or None if field has no EMG ID

    Examples
    --------
    >>> get_emg_uri("acceleration_voltage")
    'https://purls.helmholtz-metadaten.de/emg/v2.0.0/EMG_00000004'

    >>> get_emg_uri("working_distance")
    'https://purls.helmholtz-metadaten.de/emg/v2.0.0/EMG_00000050'

    >>> get_emg_uri("custom_field") is None
    True

    Notes
    -----
    The returned URI is a PURL that redirects to the canonical EMG ontology
    entry. These URIs are suitable for use in RDF/OWL ontologies and
    semantic web applications.
    """
    emg_id = get_emg_id(field_name)
    if emg_id is None:
        return None

    # Construct the full PURL with version
    return f"https://purls.helmholtz-metadaten.de/emg/{EMG_VERSION}/{emg_id}"


def get_all_mapped_fields() -> list[str]:
    """
    Get a list of all fields with NexusLIMS mappings.

    Returns a sorted list of all internal field names that have entries
    in the NEXUSLIMS_TO_EMG_MAPPINGS dictionary.

    Returns
    -------
    list[str]
        Sorted list of field names with mappings

    Examples
    --------
    >>> fields = get_all_mapped_fields()
    >>> "acceleration_voltage" in fields
    True
    >>> len(fields) > 0
    True
    """
    return sorted(NEXUSLIMS_TO_EMG_MAPPINGS.keys())


def get_fields_with_emg_ids() -> list[str]:
    """
    Get a list of fields that have EM Glossary ID mappings.

    Returns only fields with actual EMG IDs (non-None values), excluding
    fields that have display names but no EMG equivalents.

    Returns
    -------
    list[str]
        Sorted list of field names with EMG IDs

    Examples
    --------
    >>> fields = get_fields_with_emg_ids()
    >>> "acceleration_voltage" in fields
    True
    >>> "magnification" in fields  # Has display name but no EMG ID
    False
    """
    return sorted([field for field in NEXUSLIMS_TO_EMG_MAPPINGS if has_emg_id(field)])


def get_all_emg_terms() -> Dict[str, Dict[str, str]]:
    """
    Get all EM Glossary terms from the OWL file.

    Returns the complete mapping of EMG IDs to labels and definitions
    loaded from the ontology. Useful for discovering available EMG terms.

    Returns
    -------
    dict[str, dict[str, str]]
        Mapping from EMG_ID -> {'label': str, 'definition': str | None}

    Examples
    --------
    >>> terms = get_all_emg_terms()
    >>> "EMG_00000004" in terms
    True
    >>> terms["EMG_00000004"]["label"]
    'Acceleration Voltage'
    >>> print(terms["EMG_00000004"]["definition"])
    The potential difference between anode and cathode.
    """
    try:
        return _load_emg_terms()
    except Exception:
        _logger.exception("Failed to load EMG ontology")
        return {}
