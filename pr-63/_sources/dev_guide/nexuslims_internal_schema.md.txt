# Internal Metadata Schema System

```{versionadded} 2.2.0
This document describes the metadata schema system introduced in NexusLIMS v2.2.0, which replaces the unstructured v1 metadata handling approach with a system featuring type safety, physical units, and standardized terminology.
```

## Overview

The schema system provides:

1. **Type-specific validation** - Different schemas for Image, Spectrum, SpectrumImage, and Diffraction datasets
2. **Physical units with Pint** - Machine-actionable quantities with automatic unit conversion
3. **EM Glossary alignment** - Standardized field names from the Electron Microscopy community
4. **Clean XML serialization** - Separate value and unit attributes in XML output
5. **Flexible extensions** - Support for instrument-specific metadata without polluting core fields

## Key Changes from NexusLIMS version 1.X metadata handling

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
from decimal import Decimal
from nexusLIMS.schemas.units import ureg

nx_meta = {
    # Pint Quantities
    "acceleration_voltage": ureg.Quantity(Decimal("15"), "kilovolt"),
    "working_distance": ureg.Quantity(Decimal("5.2"), "millimeter"),
}
```

**Benefits:**
- Type safety: Invalid units caught at creation time
- Automatic conversion: Units normalized during serialization
- Machine-readable: Units separated from values in XML
- Programmatic: Can convert between units in code

### 2. Centralized Field Names with EM Glossary links

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
    "acceleration_voltage": ureg.Quantity(Decimal("15"), "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),

    # Extensions (flexible, instrument-specific)
    "extensions": {
        "facility": "Nexus Microscopy Lab",
        "detector_brightness": 50.0,
        "quanta_spot_size": 3.5,
    }
}
```

**Extensions Best Practices:**

1. **Core vs. Extensions Decision Guide:**
   - ✅ **Use core fields** for: Standard EM parameters with EM Glossary equivalents
   - ✅ **Use extensions** for: Vendor-specific settings, facility metadata, experimental parameters

2. **Naming Conventions:**
   - Use snake_case for extension keys: `detector_brightness`, not `DetectorBrightness`
   - Be descriptive: `fei_quanta_spot_size` instead of `spot_size` (avoids conflicts)
   - Prefix vendor-specific fields with vendor name: `zeiss_eht_mode`, `jeol_probe_mode`

3. **When to Use Extensions:**
   ```python
   # ✅ GOOD: Vendor-specific feature
   add_to_extensions(nx_meta, "quanta_stage_tilt_correction", True)

   # ✅ GOOD: Facility metadata
   add_to_extensions(nx_meta, "facility", "Building 7 Lab 3")
   add_to_extensions(nx_meta, "operator_notes", "Sample slightly contaminated")

   # ❌ BAD: Standard parameter with EM Glossary equivalent
   add_to_extensions(nx_meta, "voltage", ureg.Quantity(Decimal("15"), "kV"))  # Use acceleration_voltage instead!
   ```

4. **Use Helper Function:**
   ```python
   # ✅ GOOD: Using add_to_extensions() helper
   add_to_extensions(nx_meta, "facility", "Nexus Lab")
   add_to_extensions(nx_meta, "custom_field", value)

   # ❌ BAD: Directly manipulating dict (can overwrite)
   nx_meta["extensions"] = {"facility": "Nexus Lab"}  # Replaces existing extensions!
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

**XML Serialization Pipeline:**

The complete transformation from extractor to XML follows these steps:

1. **Extractor creates Pint Quantity:**
   ```python
   voltage = ureg.Quantity(Decimal("15000"), "volt")
   ```

2. **Add to nx_meta dict:**
   ```python
   nx_meta["acceleration_voltage"] = voltage
   ```

3. **Pydantic schema validates:**
   ```python
   meta = ImageMetadata.model_validate(nx_meta)
   # Validates type, timezone, units, etc.
   ```

4. **XML serialization converts to preferred unit:**
   ```python
   from nexusLIMS.schemas.units import quantity_to_xml_parts
   name, value, unit = quantity_to_xml_parts("acceleration_voltage", voltage)
   # Returns: ("Acceleration Voltage", "15.0", "kV")
   ```

5. **XML output uses unit attribute:**
   ```xml
   <meta name="Acceleration Voltage" unit="kV">15.0</meta>
   ```

**Code Example:**

```python
from nexusLIMS.schemas.units import ureg, quantity_to_xml_parts

# Create quantity in any compatible unit
voltage = ureg.Quantity(Decimal("15000"), "volt")  # 15 kV
distance = ureg.Quantity(Decimal("0.0052"), "meter")  # 5.2 mm

# Convert to XML parts
v_name, v_value, v_unit = quantity_to_xml_parts("acceleration_voltage", voltage)
d_name, d_value, d_unit = quantity_to_xml_parts("working_distance", distance)

# Output:
# v_name="Acceleration Voltage", v_value="15.0", v_unit="kV"
# d_name="Working Distance", d_value="5.2", d_unit="mm"

# XML result:
# <meta name="Acceleration Voltage" unit="kV">15.0</meta>
# <meta name="Working Distance" unit="mm">5.2</meta>
```

This pipeline ensures:
- **Type safety** at creation time (Pydantic validation)
- **Unit consistency** across all metadata (preferred units)
- **Clean XML** with proper structure (name/value/unit separation)
- **No data loss** (original values preserved through conversion)

(metadata-helper-functions)=
## Helper Functions

NexusLIMS provides helper functions to simplify working with schemas and extensions.

### `emg_field()` - Create Fields with EM Glossary Metadata

The `emg_field()` helper automatically adds EM Glossary metadata to Pydantic field definitions when creating new schemas:

```python
from nexusLIMS.schemas.metadata import emg_field
from nexusLIMS.schemas.pint_types import PintQuantity
from pydantic import BaseModel

class MySchema(BaseModel):
    dwell_time: PintQuantity | None = emg_field("dwell_time")
    beam_current: PintQuantity | None = emg_field("beam_current")
```

**What it does:**
- Automatically looks up display name from EM Glossary ("Pixel Dwell Time", "Beam Current")
- Adds EM Glossary ID, URI, and label to JSON schema metadata
- Pulls description from EM Glossary ontology
- Supports custom descriptions and additional Pydantic validators

**Signature:**
```python
emg_field(
    field_name: str,
    default: Any = None,
    *,
    description: str | None = None,
    **kwargs: Any
) -> Field
```

**Parameters:**
- `field_name`: Internal field name (e.g., "acceleration_voltage")
- `default`: Default value (use `...` for required, `None` for optional)
- `description`: Custom description (overrides EM Glossary description)
- `**kwargs`: Additional Pydantic Field arguments (gt, ge, examples, etc.)

**Examples:**

Basic usage:
```python
acceleration_voltage: PintQuantity | None = emg_field("acceleration_voltage")
# Automatically gets: alias="Acceleration Voltage", description="Accelerating voltage...", emg_id="EMG_00000004"
```

With custom description:
```python
beam_current: PintQuantity | None = emg_field(
    "beam_current",
    description="Probe current measured at the sample",
)
```

With Pydantic validators:
```python
from pydantic import field_validator

class MySchema(BaseModel):
    acceleration_voltage: PintQuantity | None = emg_field(
        "acceleration_voltage",
        gt=0,  # Must be positive
        examples=[ureg.Quantity(Decimal("10"), "kV"), ureg.Quantity(Decimal("200"), "kV")],
    )
```

See the complete documentation in the {ref}`Helper Functions <metadata-helper-functions>` section below.

### `add_to_extensions()` - Safely Add Extension Fields

The `add_to_extensions()` helper safely adds fields to the extensions dict without replacing existing content:

```python
from nexusLIMS.extractors.utils import add_to_extensions

nx_meta = {"acceleration_voltage": ureg.Quantity(Decimal("15"), "kV")}

# Safely add extension field
add_to_extensions(nx_meta, "facility", "Nexus Lab")
add_to_extensions(nx_meta, "detector_brightness", 50.0)

# Result: nx_meta["extensions"] = {"facility": "Nexus Lab", "detector_brightness": 50.0}
```

**Why use it:**
- Prevents accidentally replacing the entire extensions dict
- Creates extensions dict if it doesn't exist
- Clear intent in code

**When to use:**
- In extractors when adding instrument-specific metadata
- In instrument profiles when adding static fields
- Any time you need to add to extensions

See the {ref}`Helper Functions <metadata-helper-functions>` section below for more examples.

## Metadata Field Reference

The table below shows the 25 most common metadata fields
in NexusLIMS, organized by category. Some of these have
matching EMG identifiers, but not all (the EM Glossary is
an emerging standard that is not yet exhaustive).

The core common metadata parameters used throughout NexusLIMS are defined in the `NEXUSLIMS_TO_EMG_MAPPINGS` attribute of {py:mod}`nexusLIMS.schemas.em_glossary` module.

### Beam Parameters

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `acceleration_voltage` | Acceleration Voltage | EMG_00000004 | kilovolt (kV) | Electron beam accelerating voltage |
| `beam_current` | Beam Current | EMG_00000006 | picoampere (pA) | Probe current at sample |
| `emission_current` | Emission Current | EMG_00000025 | microampere (µA) | Filament emission current |
| `convergence_angle` | Convergence Angle | EMG_00000010 | milliradian (mrad) | Beam convergence angle |

### Stage & Sample

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `stage_x` | Stage X | - | micrometer (µm) | Stage X position |
| `stage_y` | Stage Y | - | micrometer (µm) | Stage Y position |
| `stage_z` | Stage Z | - | millimeter (mm) | Stage Z position (height) |
| `tilt_alpha` | Stage Alpha | - | degree (°) | Primary tilt angle |
| `tilt_beta` | Stage Beta | - | degree (°) | Secondary tilt angle (dual-tilt holders) |

### Detector Parameters

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `detector_type` | Detector | - | - (string) | Detector name (e.g., "ETD", "HAADF") |
| `working_distance` | Working Distance | EMG_00000050 | millimeter (mm) | Distance from lens to sample |
| `detector_energy_resolution` | Energy Resolution | - | electronvolt (eV) | EDS detector resolution |

### Acquisition Parameters

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `dwell_time` | Pixel Dwell Time | EMG_00000015 | microsecond (µs) | Time per pixel (scanning) |
| `acquisition_time` | Acquisition Time | EMG_00000055 | second (s) | Total acquisition time |
| `live_time` | Live Time | - | second (s) | EDS live time (excludes dead time) |
| `pixel_time` | Pixel Time | - | second (s) | Time per pixel (spectrum imaging) |

### Optical Parameters

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `magnification` | Magnification | - | - (dimensionless) | Nominal magnification |
| `camera_length` | Camera Length | EMG_00000008 | millimeter (mm) | Diffraction camera length |
| `horizontal_field_width` | Horizontal Field Width | - | micrometer (µm) | Scan width |
| `pixel_width` | Pixel Width | - | nanometer (nm) | Physical pixel width |
| `pixel_height` | Pixel Height | - | nanometer (nm) | Physical pixel height |

### Spectrum Parameters

| Internal Name | Display Name | EMG ID | Preferred Unit | Typical Use |
|--------------|--------------|--------|----------------|-------------|
| `channel_size` | Channel Size | - | electronvolt (eV) | Energy width per channel |
| `starting_energy` | Starting Energy | - | kiloelectronvolt (keV) | Spectrum starting energy |
| `takeoff_angle` | Takeoff Angle | - | degree (°) | EDS X-ray takeoff angle |

**Notes:**
- Fields with "-" in EMG ID column have display names but no EM Glossary v2.0.0 equivalent
- See [EM Glossary Reference](em_glossary_reference.md) for complete list of all fields
- Preferred units and conversion to the human-friendly display alias are automatically applied during XML serialization
- Use `emg_field()` helper to automatically populate EMG metadata

## Using the schema values

### For Extractor Plugin Developers

If you maintain a custom extractor plugin, it should use Pint Quantities with `Decimal` values:

**Step 1: Import the unit registry**
```python
from nexusLIMS.schemas.units import ureg
```

**Step 2: Create Quantities for fields with units**
```python
# Old approach (v1)
nx_meta["Voltage (kV)"] = float(voltage_v) / 1000

# New approach (v2.2.0)
nx_meta["acceleration_voltage"] = ureg.Quantity(Decimal(str(voltage_v)), "volt")
# Pint handles the conversion automatically
```

**Step 3: Use NexusLIMS field names**

Replace vendor-specific field names with NexusLIMS standard equivalents where available:
- `HV` or `Voltage` → `acceleration_voltage`
- `WD` → `working_distance`
- `Beam Current` → `beam_current`
- `Pixel Dwell Time` → `dwell_time`

**Step 4: Use helper functions**
```python
from nexusLIMS.extractors.utils import add_to_extensions

nx_meta = {
    "acceleration_voltage": ureg.Quantity(Decimal("15"), "kilovolt"),
}

# Add vendor-specific fields using helper
add_to_extensions(nx_meta, "vendor_specific_field", value)
add_to_extensions(nx_meta, "facility", "Nexus Lab")
```

See [Writing Extractor Plugins](writing_extractor_plugins.md) for detailed guidance.

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

NexusLIMS defines preferred units for each field to ensure consistency across instruments, easier comparison of data, and alignment with scientific conventions.

| Field | Preferred Unit | Rationale |
|-------|----------------|-----------|
| `acceleration_voltage` | kilovolt (kV) | Standard EM range (1-300 kV); avoids large numbers |
| `working_distance` | millimeter (mm) | Common SEM/TEM range (1-50 mm) |
| `beam_current` | picoampere (pA) | Typical probe currents (10-1000 pA) |
| `emission_current` | microampere (µA) | Filament emission range (100-300 µA) |
| `dwell_time` | microsecond (µs) | Typical scan speeds (0.1-100 µs/pixel) |
| `field_of_view` | micrometer (µm) | Microscopy field widths (1-1000 µm) |
| `camera_length` | millimeter (mm) | TEM diffraction range (100-1000 mm) |
| `acquisition_time` | second (s) | Spectrum collection times (1-1000 s) |
| `detector_energy_resolution` | electronvolt (eV) | EDS resolution spec (130-150 eV) |

**Automatic Normalization:**

When you create a Quantity in any unit, it will be automatically converted to the preferred unit during XML serialization:

```python
from nexusLIMS.schemas.units import ureg, normalize_quantity

# Create voltage in any unit
voltage = ureg.Quantity(Decimal("15000"), "volt")  # Created in volts

# Normalize to preferred unit (kV)
normalized = normalize_quantity("acceleration_voltage", voltage)
print(normalized)  # Output: 15.0 kilovolt

# XML output will be: <meta name="Voltage" unit="kV">15.0</meta>
```

This ensures all metadata uses consistent units in the final XML records, regardless of the units used in the source file or during extraction.

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
from pydantic import ValidationError

# Validate manually
try:
    validated = ImageMetadata.model_validate(nx_meta)
    logger.info("Validation successful!")
except ValidationError as e:
    logger.error("Validation failed: %s", e)
```

### Common Validation Errors

#### Missing Timezone in Timestamp

```python
# ❌ WRONG - Missing timezone
nx_meta = {
    "creation_time": "2024-01-15T10:30:00",  # No timezone!
    "data_type": "SEM_Imaging",
    "dataset_type": "Image",
}

# ValidationError: Timestamp must include timezone: 2024-01-15T10:30:00
```

```python
# ✅ CORRECT - Include timezone
nx_meta = {
    "creation_time": "2024-01-15T10:30:00-05:00",  # EST timezone
    # OR
    "creation_time": "2024-01-15T15:30:00Z",  # UTC timezone
    "data_type": "SEM_Imaging",
    "dataset_type": "Image",
}
```

#### Wrong DatasetType

```python
# ❌ WRONG - DatasetType doesn't match schema
try:
    meta = ImageMetadata.model_validate({
        "creation_time": "2024-01-15T10:30:00Z",
        "data_type": "SEM_Imaging",
        "dataset_type": "Spectrum",  # Wrong! Should be "Image"
    })
except ValidationError as e:
    print(e)
    # ValidationError: Input should be 'Image'
```

#### Invalid Quantity Units

```python
# ❌ WRONG - Incompatible units
voltage = ureg.Quantity(Decimal("10"), "meter")  # Meters instead of volts!

try:
    meta = ImageMetadata(
        creation_time="2024-01-15T10:30:00Z",
        data_type="SEM_Imaging",
        dataset_type="Image",
        acceleration_voltage=voltage,
    )
except Exception as e:
    # Pint will raise error: Cannot convert from 'meter' to 'kilovolt'
    print(f"Unit error: {e}")
```

### Validation Best Practices

1. **Always include timezone**: Use ISO-8601 format with timezone offset
2. **Use correct DatasetType**: Match the schema to your data type
3. **Test validation early**: Validate in your extractor during development
4. **Check unit compatibility**: Ensure units are dimensionally correct (voltage in volts, distance in meters, etc.)
5. **Use emg_field()**: Automatically handles field metadata and descriptions

## Backward Compatibility

**Important:** The v2.2.0 schema is **not backward compatible** with the experimental v1 schema. This is intentional:

- v1 was experimental and not used in production
- Clean break enables better design
- No legacy compatibility burden
- All built-in extractors updated together

If you have custom extractors or local instrument profiles, you must update them to use the new schema system.

(faq)=
## FAQ

### Q: Do I need to update existing XML records to use the new schema?

No. The schema described here is totally internal to NexusLIMS and existing records in CDCS are not affected. The schema changes only apply to newly generated records.

### Q: Can I still use plain numeric values?

Yes, for dimensionless quantities (magnification, brightness, gain, etc.). Only use Pint Quantities (with `Decimal` values) for fields with physical units.

### Q: What if my field doesn't have an EM Glossary equivalent?

Use a descriptive name and place it in the `extensions` section. We encourage contributing new terms to the EM Glossary project.

### Q: How do I know what units to use?

Use the preferred units defined in `nexusLIMS.schemas.units.PREFERRED_UNITS`. Pint will automatically convert to the preferred unit during XML serialization.

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

NexusLIMS internally maps Pint units to QUDT (Quantities, Units, Dimensions and Types) URIs for future semantic web integration (not currently visible in XML output). This mapping is implemented by {py:func}`nexusLIMS.schemas.units.get_qudt_uri`, which loads unit mappings from the QUDT ontology vocabulary file.

| Pint Unit | QUDT URI |
|-----------|----------|
| `kilovolt` | `http://qudt.org/vocab/unit/KiloV` |
| `millimeter` | `http://qudt.org/vocab/unit/MilliM` |
| `picoampere` | `http://qudt.org/vocab/unit/PicoA` |
| `second` | `http://qudt.org/vocab/unit/SEC` |

This mapping will enable future Tier 3 implementation with full semantic web support.

**Tier 3 Conceptual Example (Future):**

When Tier 3 is implemented, XML output will optionally include QUDT and EM Glossary URIs for full semantic web integration:

```xml
<!-- Current Tier 2 output -->
<meta name="Acceleration Voltage" unit="kV">15.0</meta>

<!-- Future Tier 3 output (conceptual) -->
<meta name="Acceleration Voltage"
      unit="kV"
      qudt:unit="http://qudt.org/vocab/unit/KiloV"
      emg:term="https://purls.helmholtz-metadaten.de/emg/v2.0.0/EMG_00000004"
      emg:label="Acceleration Voltage">
  15.0
</meta>
```

**Benefits of Tier 3:**
- Full semantic web compatibility for linked data applications
- Direct linkage to QUDT and EM Glossary ontologies
- Machine-readable term definitions
- Interoperability with other metadata standards

**Status:** Tier 3 requires XSD schema updates and is planned for a future NexusLIMS release.

### EM Glossary Integration

The EM Glossary is parsed directly from the OWL ontology file using [RDFLib](https://rdflib.readthedocs.io/en/stable/index.html):

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
- Check the {ref}`FAQ <faq>` above
- Review [Writing Extractor Plugins](writing_extractor_plugins.md)
- Report issues at [GitHub Issues](https://github.com/datasophos/NexusLIMS/issues)
