# Metadata Schema System (v2.2.0)

This document describes the metadata schema system introduced in NexusLIMS v2.2.0, which replaces the v1 schema with a system featuring type safety, physical units, and standardized terminology.

## Overview

The v2.2.0 schema system provides:

1. **Type-specific validation** - Different schemas for Image, Spectrum, SpectrumImage, and Diffraction datasets
2. **Physical units with Pint** - Machine-actionable quantities with automatic unit conversion
3. **EM Glossary alignment** - Standardized field names from the Electron Microscopy community
4. **Clean XML serialization** - Separate value and unit attributes in XML output
5. **Flexible extensions** - Support for instrument-specific metadata without polluting core fields

## Key Changes from v1 Schema

### 1. Pint Quantities for Physical Values

**Before (v1):**
```python
nx_meta = {
    "Voltage (kV)": 15,  # Unit embedded in field name
    "Working Distance (mm)": 5.2,
}
```

**After (v2.2.0):**
```python
from nexusLIMS.schemas.units import ureg

nx_meta = {
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),  # Pint Quantity
    "working_distance": ureg.Quantity(5.2, "millimeter"),
}
```

**Benefits:**
- Type safety: Invalid units caught at creation time
- Automatic conversion: Units normalized during serialization
- Machine-readable: Units separated from values in XML
- Programmatic: Can convert between units in code

### 2. EM Glossary Field Names

Field names now follow the **Electron Microscopy Glossary** (EM Glossary) for standardization:

| Old Field Name (v1) | New Field Name (v2.2.0) | EM Glossary ID |
|---------------------|-------------------------|----------------|
| `Voltage (kV)` | `acceleration_voltage` | EMG_00000004 |
| `Working Distance (mm)` | `working_distance` | EMG_00000050 |
| `Beam Current (pA)` | `beam_current` | EMG_00000006 |
| `Pixel Dwell Time (µs)` | `dwell_time` | EMG_00000015 |
| `Camera Length (mm)` | `camera_length` | EMG_00000008 |

See [EM Glossary Reference](em_glossary_reference.md) for complete mappings.

### 3. Type-Specific Schemas

Metadata is validated against dataset-type-specific schemas:

- `ImageMetadata` - For SEM/TEM/STEM images
- `SpectrumMetadata` - For EDS/EELS/CL spectra
- `SpectrumImageMetadata` - For spectrum imaging (STEM-EDS, STEM-EELS)
- `DiffractionMetadata` - For electron diffraction patterns

Each schema enforces appropriate fields for its dataset type while allowing additional fields via the `extensions` section.

### 4. Extensions Section

Instrument-specific or vendor-specific metadata goes in the `extensions` section:

```python
nx_meta = {
    # Core fields (EM Glossary names, type-validated)
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),
    
    # Extensions (flexible, instrument-specific)
    "extensions": {
        "facility": "Nexus Microscopy Lab",
        "detector_brightness": 50.0,
        "quanta_spot_size": 3.5,
    }
}
```

This keeps core metadata clean and standardized while allowing flexibility for unique instrument features.

### 5. Improved XML Serialization

**Before (v1):**
```xml
<meta name="Voltage (kV)">15</meta>
```

**After (v2.2.0):**
```xml
<meta name="Voltage" unit="kV">15</meta>
```

The new format:
- Separates value from unit using existing XSD `unit` attribute
- Uses cleaner field names (no units in names)
- Is more machine-readable (structured attributes vs. text parsing)
- Leverages existing XSD infrastructure (no schema changes required)

## Migration Guide

### For Extractor Plugin Developers

If you maintain a custom extractor plugin, update it to use Pint Quantities:

**Step 1: Import the unit registry**
```python
from nexusLIMS.schemas.units import ureg
```

**Step 2: Create Quantities for fields with units**
```python
# Old approach (v1)
nx_meta["Voltage (kV)"] = float(voltage_v) / 1000

# New approach (v2.2.0)
nx_meta["acceleration_voltage"] = ureg.Quantity(voltage_v, "volt")
# Pint handles the conversion automatically
```

**Step 3: Use EM Glossary field names**

Replace vendor-specific field names with EM Glossary equivalents where available:
- `HV` or `Voltage` → `acceleration_voltage`
- `WD` → `working_distance`
- `Beam Current` → `beam_current`
- `Pixel Dwell Time` → `dwell_time`

**Step 4: Put vendor-specific fields in extensions**
```python
nx_meta = {
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "extensions": {
        "vendor_specific_field": value,
    }
}
```

See [Writing Extractor Plugins](writing_extractor_plugins.md) for detailed guidance.

### For Instrument Profile Developers

Instrument profiles now use `extension_fields` instead of `static_metadata`:

**Before (v1):**
```python
from nexusLIMS.extractors.base import InstrumentProfile

profile = InstrumentProfile(
    instrument_names=["FEI Titan"],
    static_metadata={
        "Facility": "Nexus Lab",
    }
)
```

**After (v2.2.0):**
```python
from nexusLIMS.extractors.base import InstrumentProfile

profile = InstrumentProfile(
    instrument_names=["FEI Titan"],
    extension_fields={  # Changed from static_metadata
        "facility": "Nexus Lab",
    }
)
```

Extension fields are automatically injected into `nx_meta["extensions"]` during extraction.

## Schema Structure

### Base Schema (NexusMetadata)

All datasets must include these core fields:

```python
{
    "DatasetType": str,  # "Image" | "Spectrum" | "SpectrumImage" | "Diffraction" | "Misc"
    "Data Type": str,  # Descriptive string (e.g., "SEM_Imaging", "TEM_EDS")
    "Creation Time": str,  # ISO-8601 with timezone
    "extensions": dict,  # Optional: instrument-specific fields
}
```

### Type-Specific Schemas

#### ImageMetadata

Typical fields (all optional unless specified):
- `acceleration_voltage` - Quantity (kilovolt)
- `working_distance` - Quantity (millimeter)
- `beam_current` - Quantity (picoampere)
- `emission_current` - Quantity (microampere)
- `magnification` - float (dimensionless)
- `dwell_time` - Quantity (microsecond)
- `field_of_view` - Quantity (micrometer)
- `scan_rotation` - Quantity (degree)
- `stage_position` - StagePosition object with X, Y, Z, tilt, rotation
- `detector_type` - str

#### SpectrumMetadata

Typical fields:
- `acquisition_time` - Quantity (second)
- `live_time` - Quantity (second)
- `detector_energy_resolution` - Quantity (electronvolt)
- `channel_size` - Quantity (electronvolt)
- `starting_energy` - Quantity (kiloelectronvolt)
- `azimuthal_angle` - Quantity (degree)
- `elevation_angle` - Quantity (degree)
- `elements` - list[str]

#### SpectrumImageMetadata

Combines fields from both Image and Spectrum, plus:
- `pixel_time` - Quantity (microsecond)
- `scan_mode` - str

#### DiffractionMetadata

Typical fields:
- `camera_length` - Quantity (millimeter)
- `convergence_angle` - Quantity (milliradian)
- `diffraction_mode` - str

See API documentation for complete field lists.

## Preferred Units

NexusLIMS defines preferred units for each field to ensure consistency:

| Field | Preferred Unit |
|-------|----------------|
| `acceleration_voltage` | kilovolt (kV) |
| `working_distance` | millimeter (mm) |
| `beam_current` | picoampere (pA) |
| `emission_current` | microampere (µA) |
| `dwell_time` | microsecond (µs) |
| `field_of_view` | micrometer (µm) |
| `camera_length` | millimeter (mm) |
| `acquisition_time` | second (s) |
| `detector_energy_resolution` | electronvolt (eV) |

When you create a Quantity in any unit, it will be automatically converted to the preferred unit during XML serialization.

## Validation Behavior

### Automatic Validation

Metadata is validated automatically during record building:

1. Extractor returns `nx_meta` dict
2. `validate_nx_meta()` checks against appropriate schema based on `DatasetType`
3. Validation errors are logged with filename context
4. Invalid metadata prevents record generation

### Manual Validation

You can validate metadata manually in your extractor:

```python
from nexusLIMS.schemas.metadata import ImageMetadata

# Validate manually
try:
    validated = ImageMetadata.model_validate(nx_meta)
except ValidationError as e:
    logger.error("Validation failed: %s", e)
```

## Backward Compatibility

**Important:** The v2.2.0 schema is **not backward compatible** with the experimental v1 schema. This is intentional:

- v1 was experimental and not used in production
- Clean break enables better design
- No legacy compatibility burden
- All built-in extractors updated together

If you have custom extractors or local instrument profiles, you must update them to use the new schema system.

## FAQ

### Q: Do I need to update existing XML records?

No. Existing records in CDCS are not affected. The schema changes only apply to newly generated records.

### Q: Can I still use plain numeric values?

Yes, for dimensionless quantities (magnification, brightness, gain, etc.). Only use Pint Quantities for fields with physical units.

### Q: What if my field doesn't have an EM Glossary equivalent?

Use a descriptive name and place it in the `extensions` section. We encourage contributing new terms to the EM Glossary project.

### Q: How do I know what units to use?

Use the preferred units defined in `nexusLIMS.schemas.units.PREFERRED_UNITS`. Pint will automatically convert to the preferred unit during XML serialization.

### Q: Can I validate against the old schema?

No. The old schema system has been removed in v2.2.0.

### Q: Will this break my existing code?

Only if you have custom extractors or instrument profiles. Built-in extractors have been updated. Update your custom code following the migration guide above.

## Implementation Details

### Three-Tier Architecture

NexusLIMS uses a three-tier approach to metadata serialization:

**Tier 1: Internal (Pint + QUDT/EMG mappings)**
- Pint Quantity objects with full unit information
- Internal QUDT URI and EM Glossary ID mappings
- Type safety and validation

**Tier 2: XML with `unit` attribute (current)**
- Clean separation: `<meta name="Voltage" unit="kV">15</meta>`
- Uses existing XSD attribute (no schema changes)
- Machine-readable structure

**Tier 3: Semantic Web integration (future)**
- Optional QUDT and EM Glossary URI attributes
- Full semantic web compatibility
- Requires XSD update (planned for future release)

### QUDT Unit Ontology

NexusLIMS internally maps Pint units to QUDT (Quantities, Units, Dimensions and Types) URIs:

```text
Internal mapping (not visible in current XML output):
"kilovolt" -> "http://qudt.org/vocab/unit/KiloV"
"millimeter" -> "http://qudt.org/vocab/unit/MilliM"
```

This enables future Tier 3 implementation with full semantic web support.

### EM Glossary Integration

The EM Glossary is parsed directly from the OWL ontology file using RDFLib:

- Single source of truth (OWL file)
- Auto-updates when EM Glossary is updated
- Provides access to labels, definitions, and semantic structure

## Resources

- [EM Glossary Reference](em_glossary_reference.md) - Complete field mapping table
- [Writing Extractor Plugins](writing_extractor_plugins.md) - Developer guide with examples
- [EM Glossary Project](https://owl.emglossary.helmholtz-metadaten.de/) - Community ontology
- [QUDT Ontology](http://www.qudt.org/) - Units and quantities standard
- [Pint Documentation](https://pint.readthedocs.io/) - Python units library

## Support

For questions or issues:
- Check the [FAQ](#faq) above
- Review [Writing Extractor Plugins](writing_extractor_plugins.md)
- Report issues at [GitHub Issues](https://github.com/datasophos/NexusLIMS/issues)
