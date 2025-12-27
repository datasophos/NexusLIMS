"""
Schema tools for NexusLIMS.

This module provides:
- Type-specific metadata schemas (Image, Spectrum, SpectrumImage, Diffraction)
- Pint Quantity integration for physical units
- EM Glossary field name mappings
- Stage position modeling
"""

from nexusLIMS.schemas.em_glossary import (
    get_all_emg_terms,
    get_all_mapped_fields,
    get_description,
    get_display_name,
    get_emg_id,
    get_emg_label,
    get_emg_uri,
    get_fields_with_emg_ids,
    has_emg_id,
)
from nexusLIMS.schemas.metadata import (
    DiffractionMetadata,
    ImageMetadata,
    NexusMetadata,
    SpectrumImageMetadata,
    SpectrumMetadata,
    StagePosition,
)
from nexusLIMS.schemas.pint_types import PintQuantity
from nexusLIMS.schemas.units import (
    PREFERRED_UNITS,
    get_qudt_uri,
    normalize_quantity,
    parse_quantity,
    quantity_to_xml_parts,
    ureg,
)

__all__ = [  # noqa: RUF022
    # Units and Pint integration
    "ureg",
    "PintQuantity",
    "PREFERRED_UNITS",
    "parse_quantity",
    "normalize_quantity",
    "quantity_to_xml_parts",
    "get_qudt_uri",
    # Metadata schemas
    "StagePosition",
    "NexusMetadata",
    "ImageMetadata",
    "SpectrumMetadata",
    "SpectrumImageMetadata",
    "DiffractionMetadata",
    # EM Glossary integration
    "get_emg_id",
    "get_emg_label",
    "get_emg_uri",
    "get_display_name",
    "get_description",
    "get_all_emg_terms",
    "get_all_mapped_fields",
    "get_fields_with_emg_ids",
    "has_emg_id",
]
