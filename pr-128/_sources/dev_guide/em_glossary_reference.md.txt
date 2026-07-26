# EM Glossary Field Reference

```{versionadded} 2.2.0
```

This document provides a reference for standardized field names in NexusLIMS metadata, aligned with the **Electron Microscopy Glossary v2.0.0** community standard.

## Field Coverage Statistics

NexusLIMS v2.2.0 provides:
- **8 fields** with full EM Glossary ID mappings (✅)
- **33 fields** without EM Glossary ID mappings (🔷)
- **Additional fields** available in extensions section

**Coverage Note:** EM Glossary v2.0.0 provides basic coverage for core electron microscopy parameters. Fields without EMG IDs either represent vendor-specific concepts or areas where the EM Glossary is still expanding. NexusLIMS provides display names for all fields to ensure consistent XML output.

(field-mapping-quick-reference)=
## Common Fields by Category

The tables below show the 25 most commonly used metadata fields in NexusLIMS, organized by functional category.

### Beam Parameters

Fields describing the electron/ion beam characteristics:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `acceleration_voltage` | Acceleration Voltage | EMG_00000004 ✅ | kilovolt (kV) | Beam accelerating voltage | Image, Diffraction |
| `beam_current` | Beam Current | EMG_00000006 ✅ | picoampere (pA) | Probe current at sample | Image |
| `emission_current` | Emission Current | EMG_00000025 ✅ | microampere (µA) | Filament emission current | Image |
| `convergence_angle` | Convergence Angle | EMG_00000010 ✅ | milliradian (mrad) | Beam convergence angle | Diffraction, Image |

### Stage & Sample Position

Fields describing stage coordinates and orientation:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `stage_x` | Stage X | - 🔷 | micrometer (µm) | Stage X coordinate | Image, Spectrum |
| `stage_y` | Stage Y | - 🔷 | micrometer (µm) | Stage Y coordinate | Image, Spectrum |
| `stage_z` | Stage Z | - 🔷 | millimeter (mm) | Stage Z position (height) | Image, Spectrum |
| `tilt_alpha` | Stage Alpha | - 🔷 | degree (°) | Primary tilt angle | Image, Spectrum |
| `tilt_beta` | Stage Beta | - 🔷 | degree (°) | Secondary tilt (dual-tilt holders) | Image, Spectrum |

### Detector Parameters

Fields describing detector configuration:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `detector_type` | Detector | - 🔷 | N/A (string) | Detector name (e.g., "ETD", "HAADF") | Image, Spectrum |
| `working_distance` | Working Distance | EMG_00000050 ✅ | millimeter (mm) | Distance from lens to sample | Image |
| `detector_energy_resolution` | Energy Resolution | - 🔷 | electronvolt (eV) | EDS detector resolution | Spectrum |

### Acquisition Parameters

Fields describing data acquisition settings:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `dwell_time` | Pixel Dwell Time | EMG_00000015 ✅ | microsecond (µs) | Time per pixel (scanning) | Image |
| `acquisition_time` | Acquisition Time | EMG_00000055 ✅ | second (s) | Total acquisition time | Spectrum |
| `live_time` | Live Time | - 🔷 | second (s) | EDS live time (excludes dead time) | Spectrum |
| `pixel_time` | Pixel Time | - 🔷 | second (s) | Acquisition time per pixel (spectrum imaging) | SpectrumImage |

### Optical Parameters

Fields describing optical configuration and field of view:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `magnification` | Magnification | - 🔷 | dimensionless | Nominal magnification | Image |
| `camera_length` | Camera Length | EMG_00000008 ✅ | millimeter (mm) | Diffraction camera length | Diffraction |
| `horizontal_field_width` | Horizontal Field Width | - 🔷 | micrometer (µm) | Scan width | Image |
| `pixel_width` | Pixel Width | - 🔷 | nanometer (nm) | Physical pixel width | Image |
| `pixel_height` | Pixel Height | - 🔷 | nanometer (nm) | Physical pixel height | Image |

### Spectrum Parameters

Fields specific to spectral data acquisition:

| Field Name | Display Name | EMG ID | Preferred Unit | Typical Use | Schema |
|------------|--------------|--------|----------------|-------------|--------|
| `channel_size` | Channel Size | - 🔷 | electronvolt (eV) | Energy width per channel | Spectrum |
| `starting_energy` | Starting Energy | - 🔷 | kiloelectronvolt (keV) | Spectrum starting energy | Spectrum |
| `takeoff_angle` | Takeoff Angle | - 🔷 | degree (°) | EDS X-ray takeoff angle | Spectrum |

**Legend:**
- ✅ = Has EM Glossary v2.0.0 ID mapping (full semantic annotation)
- 🔷 = Has EM Glossary display name but no ID in v2.0.0 (may be added in future versions)
- **Schema** column shows which Pydantic schemas use this field

For the complete list of all mapped fields (40+), see the `NEXUSLIMS_TO_EMG_MAPPINGS` in `nexusLIMS/schemas/em_glossary.py`.

## Usage Examples

### Basic Usage in Extractors

```python
from nexusLIMS.schemas.units import ureg
from nexusLIMS.extractors.utils import add_to_extensions

# Using standardized field names with Pint Quantities
nx_meta = {
    "creation_time": "2024-01-15T10:30:00-05:00",
    "data_type": "SEM_Imaging",
    "dataset_type": "Image",
    "acceleration_voltage": ureg.Quantity(Decimal("15"), "kilovolt"),
    "working_distance": ureg.Quantity(Decimal("5.2"), "millimeter"),
    "beam_current": ureg.Quantity(Decimal("100"), "picoampere"),
    "dwell_time": ureg.Quantity(Decimal("2.5"), "microsecond"),
}

# Add vendor-specific fields
add_to_extensions(nx_meta, "quanta_spot_size", 3.5)
add_to_extensions(nx_meta, "facility", "Building 7 Lab 3")
```

### Programmatic Lookup Functions

The EM Glossary module provides functions for dynamically accessing field metadata:

```python
from nexusLIMS.schemas.em_glossary import (
    get_emg_id,
    get_emg_uri,
    get_emg_label,
    get_display_name,
    get_description,
    has_emg_id,
)

# Get EMG ID from field name
emg_id = get_emg_id("acceleration_voltage")
print(emg_id)  # "EMG_00000004"

# Get full PURL for semantic web
emg_uri = get_emg_uri("acceleration_voltage")
print(emg_uri)  # "https://purls.helmholtz-metadaten.de/emg/v2.0.0/EMG_00000004"

# Get label from EMG ID
label = get_emg_label("EMG_00000004")
print(label)  # "Acceleration Voltage"

# Get display name for XML
display = get_display_name("acceleration_voltage")
print(display)  # "Acceleration Voltage"

# Get field description
desc = get_description("acceleration_voltage")
print(desc)  # "Accelerating voltage of the electron/ion beam"

# Check if field has EMG mapping
if has_emg_id("acceleration_voltage"):
    print("Field has full EMG annotation")
```

### Using `emg_field()` Helper

The `emg_field()` helper automatically injects EM Glossary metadata when defining Pydantic schemas:

```python
from nexusLIMS.schemas.metadata import emg_field
from nexusLIMS.schemas.pint_types import PintQuantity
from pydantic import BaseModel

class MySEMSchema(BaseModel):
    # Automatically gets EM Glossary metadata
    acceleration_voltage: PintQuantity | None = emg_field("acceleration_voltage")
    beam_current: PintQuantity | None = emg_field("beam_current")
    working_distance: PintQuantity | None = emg_field("working_distance")

    # Custom field without EMG mapping goes in extensions
    # (Don't use emg_field for vendor-specific fields)

# The fields automatically have:
# - alias: "Acceleration Voltage", "Beam Current", "Working Distance"
# - description: From EM Glossary definitions
# - json_schema_extra: {"emg_id": "EMG_00000004", "emg_uri": "...", ...}
```

### Real-World Extractor Example

Complete example showing EM Glossary usage in an extractor:

```python
from nexusLIMS.schemas.units import ureg
from nexusLIMS.extractors.utils import add_to_extensions
from datetime import datetime, timezone

def extract_sem_metadata(file_path):
    """Extract metadata from SEM TIFF file."""
    # Read metadata from file (vendor-specific code)
    voltage_v = read_voltage_from_file(file_path)  # Returns 15000 (volts)
    wd_mm = read_working_distance(file_path)  # Returns 5.2 (mm)
    current_pa = read_beam_current(file_path)  # Returns 100 (pA)
    timestamp = read_timestamp(file_path)

    # Build metadata using EM Glossary field names
    nx_meta = {
        "creation_time": timestamp.isoformat(),
        "data_type": "SEM_Imaging",
        "dataset_type": "Image",

        # Standard EM Glossary fields with Pint Quantities
        "acceleration_voltage": ureg.Quantity(voltage_v, "volt"),  # Auto-converts to kV
        "working_distance": ureg.Quantity(wd_mm, "millimeter"),
        "beam_current": ureg.Quantity(current_pa, "picoampere"),
    }

    # Vendor-specific metadata goes in extensions
    spot_size = read_vendor_spot_size(file_path)
    if spot_size is not None:
        add_to_extensions(nx_meta, "quanta_spot_size", spot_size)

    return nx_meta
```

## XML Output

Fields with units serialize to clean XML using the `unit` attribute:

```xml
<meta name="Voltage" unit="kV">15</meta>
<meta name="Working Distance" unit="mm">5.2</meta>
<meta name="Beam Current" unit="pA">100</meta>
```

## EM Glossary Integration Architecture

NexusLIMS integrates with the EM Glossary through dynamic OWL ontology parsing using RDFLib.

### Architecture Components

1. **OWL Ontology File**: `nexusLIMS/schemas/references/em_glossary_2.0.owl`
   - Shipped with NexusLIMS (139 KB)
   - Parsed at runtime using RDFLib
   - Provides labels, definitions, and semantic structure
   - License: CC BY 4.0

2. **Mapping Dictionary**: `NEXUSLIMS_TO_EMG_MAPPINGS` in `em_glossary.py`
   - Maps internal field names to EM Glossary labels
   - Format: `{field_name: (display_name, emg_label, description)}`
   - Single source of truth for field metadata
   - ~50 fields mapped

3. **Lookup Functions**: Dynamic queries against parsed RDF graph
   - `get_emg_id()`: Field name → EMG ID via label matching
   - `get_emg_label()`: EMG ID → Label from ontology
   - `get_emg_definition()`: EMG ID → Formal definition (IAO_0000115)
   - `get_emg_uri()`: Field name → Full PURL

### Update Process

To update to a new EM Glossary version:

1. Download new OWL file from [EM Glossary project](https://purls.helmholtz-metadaten.de/emg/)
2. Replace `nexusLIMS/schemas/references/em_glossary_2.0.owl`
3. Update `EMG_VERSION` constant in `em_glossary.py`
4. Review `NEXUSLIMS_TO_EMG_MAPPINGS` for new terms
5. Run tests to verify parsing and mappings

### Contributing to EM Glossary

If you need a term that doesn't exist in EM Glossary v2.0.0:

1. **Check latest EM Glossary version**: New terms may have been added
2. **Propose new term**: Contact EM Glossary maintainers via [project page](https://owl.emglossary.helmholtz-metadaten.de/)
3. **Use extensions in the meantime**: Place custom fields in `nx_meta["extensions"]`

## Preferred Units Rationale

| Physical Quantity | Preferred Unit | Pint String | Rationale |
|-------------------|----------------|-------------|-----------|
| Voltage | kilovolt | `"kilovolt"` or `"kV"` | Standard EM range (1-300 kV); avoids large numbers |
| Distance (large) | millimeter | `"millimeter"` or `"mm"` | Common SEM/TEM working distances (1-50 mm) |
| Distance (small) | micrometer | `"micrometer"` or `"um"` | Field widths and stage coordinates (1-1000 µm) |
| Current (beam) | picoampere | `"picoampere"` or `"pA"` | Typical probe currents (10-1000 pA) |
| Current (emission) | microampere | `"microampere"` or `"uA"` | Filament emission range (100-300 µA) |
| Time | second | `"second"` or `"s"` | Acquisition times (1-1000 s) |
| Energy | electronvolt | `"electron_volt"` or `"eV"` | X-ray energies and detector resolution |
| Angle | degree | `"degree"` or `"deg"` | Stage tilt, detector angles |

Pint automatically converts to the preferred unit during XML serialization, ensuring consistency across instruments and vendors.

## Resources

- [EM Glossary Project](https://owl.emglossary.helmholtz-metadaten.de/) - Documentation and updates
- [QUDT Ontology](http://www.qudt.org/) - Units and quantities standard
- [Pint Documentation](https://pint.readthedocs.io/) - Python units library

## See Also

- [NexusLIMS Internal Schema](nexuslims_internal_schema.md) - Internal metadata schema architecture overview
- [Writing Extractor Plugins](writing_extractor_plugins.md) - Developer guide with examples
- {ref}`Helper Functions <metadata-helper-functions>` - `emg_field()` and `add_to_extensions()` documentation
- {py:mod}`nexusLIMS.schemas.em_glossary` - API reference for lookup functions
- {py:mod}`nexusLIMS.schemas.metadata` - Pydantic schema definitions
- {py:mod}`nexusLIMS.schemas.units` - Unit registry and preferred units
