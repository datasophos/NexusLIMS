# Writing Extractor Plugins

This guide explains how to create custom metadata extractors for NexusLIMS using the plugin-based system introduced in v2.1.0.

## Overview

NexusLIMS uses a plugin-based architecture for metadata extraction. Extractors are automatically discovered from the `nexusLIMS/extractors/plugins/` directory and registered based on their file type support and priority.

## Quick Start

To create a new extractor plugin:

1. Create a `.py` file in `nexusLIMS/extractors/plugins/`
2. Define a class with the required interface (see below)
3. That's it! The registry will automatically discover and use your extractor

## Minimal Example

Here's a minimal extractor for a hypothetical `.xyz` file format:

```python
"""XYZ file format extractor plugin."""

import logging
from typing import Any
from pathlib import Path

from nexusLIMS.extractors.base import ExtractionContext

logger = logging.getLogger(__name__)


class XYZExtractor:
    """Extractor for XYZ format files."""
    
    # Required class attributes
    name = "xyz_extractor"  # Unique identifier
    priority = 100  # Higher = preferred (0-1000)
    supported_extensions = {"xyz"}  # Extensions this extractor supports
    
    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Can check file extension and/or file contents (content-sniffing).

        Parameters
        ----------
        context : ExtractionContext
            Contains file_path and instrument information

        Returns
        -------
        bool
            True if this extractor can handle the file
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        if extension != "xyz":
            return False

        # Optional: Check file contents for format signature
        # with open(context.file_path, "rb") as f:
        #     header = f.read(8)
        #     return header.startswith(b"XYZDATA")

        return True
    
    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from an XYZ file.

        Parameters
        ----------
        context : ExtractionContext
            Contains file_path and instrument information

        Returns
        -------
        list[dict]
            List of metadata dictionaries, one per signal.
            Each dict has an 'nx_meta' key with NexusLIMS metadata.
        """
        logger.debug("Extracting metadata from XYZ file: %s", context.file_path)

        # Your extraction logic here
        metadata = {"nx_meta": {}}

        # Add required fields
        metadata["nx_meta"]["DatasetType"] = "Image"  # or "Spectrum", "SpectrumImage", etc.
        metadata["nx_meta"]["Data Type"] = "SEM_Imaging"
        metadata["nx_meta"]["Creation Time"] = self._get_creation_time(context.file_path)

        # Add format-specific metadata
        # ...

        # Always return a list (even for single-signal files)
        return [metadata]
    
    def _get_creation_time(self, file_path: Path) -> str:
        """Helper to get ISO-formatted creation time."""
        from datetime import datetime as dt
        from nexusLIMS.instruments import get_instr_from_filepath
        
        mtime = file_path.stat().st_mtime
        instr = get_instr_from_filepath(file_path)
        return dt.fromtimestamp(
            mtime,
            tz=instr.timezone if instr else None,
        ).isoformat()
```

## Required Interface

Every extractor plugin must define a class with these attributes and methods:

### Class Attributes

#### `name: str`
Unique identifier for this extractor. Use lowercase with underscores (e.g., `"dm3_extractor"`).

#### `priority: int`
Priority for extractor selection (0-1000). Higher values are preferred. Guidelines:
- `100`: Standard format-specific extractors
- `50`: Generic extractors with content sniffing
- `0`: Fallback extractors (like BasicFileInfoExtractor)

#### `supported_extensions: set[str] | None`
File extensions this extractor supports (without leading dot). Required attribute.

**Behavior:**
- If a `set` of extensions (e.g., `{"dm3", "dm4"}`): Extractor is registered only for those extensions. The registry will prioritize this extractor when files with these extensions are encountered.
- If `None`: Extractor becomes a "wildcard" extractor tried only after all extension-specific extractors fail.

**Note:** The registry uses this attribute to determine registration, so `supports()` should match the declared extensions. Mismatches can lead to unexpected behavior.

**Examples:**
```python
# Single extension
supported_extensions = {"xyz"}

# Multiple extensions
supported_extensions = {"dm3", "dm4"}

# Wildcard (fallback only)
supported_extensions = None
```

### Methods

#### `supports(context: ExtractionContext) -> bool`
Determine if this extractor can handle a given file.

**Parameters:**
- `context`: Contains `file_path` (Path) and `instrument` (Instrument or None)

**Returns:** `True` if this extractor supports the file

```{note}
**Content Sniffing**: While extension checks are fast, you can also inspect file contents to verify the format. This is useful when multiple formats share the same extension or when you need to distinguish file variants. See [Content-Based Detection](#content-based-detection) for advanced examples.
```

**Example:**
```python
def supports(self, context: ExtractionContext) -> bool:
    # Simple extension check
    ext = context.file_path.suffix.lower().lstrip(".")
    return ext in {"dm3", "dm4"}
```

#### `extract(context: ExtractionContext) -> list[dict[str, Any]]`
Extract metadata from the file.

**Parameters:**
- `context`: Contains `file_path` (Path) and `instrument` (Instrument or None)

**Returns:** A **list** of metadata dictionaries. Each dict must contain an `"nx_meta"` key with NexusLIMS metadata.

**Format:**
- Single-signal files: Return `[{...}]` - a list with one element
- Multi-signal files: Return `[{...}, {...}]` - a list with multiple elements

**Required `nx_meta` fields (in each dict):**
- `"DatasetType"`: One of "Image", "Spectrum", "SpectrumImage", "Diffraction", "Misc"
- `"Data Type"`: Descriptive string (e.g., "STEM_Imaging", "TEM_EDS")
- `"Creation Time"`: ISO-8601 formatted timestamp **with timezone** (e.g., `"2024-01-15T10:30:00-05:00"` or `"2024-01-15T10:30:00Z"`)

**Example:**
```python
def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
    metadata = {"nx_meta": {}}
    metadata["nx_meta"]["DatasetType"] = "Image"
    metadata["nx_meta"]["Data Type"] = "SEM_Imaging"
    metadata["nx_meta"]["Creation Time"] = "2024-01-15T10:30:00-05:00"
    # ... extraction logic
    # Always return a list
    return [metadata]
```

(metadata-validation)=
#### Metadata Validation

The `nx_meta` section is automatically validated using **type-specific** Pydantic schemas based on the `DatasetType` field. NexusLIMS provides schema classes for each dataset type:

- **{py:class}`nexusLIMS.schemas.metadata.ImageMetadata`** - For Image datasets
  - Validates imaging-specific fields (acceleration_voltage, working_distance, beam_current, etc.)
  - Used when `DatasetType == "Image"`

- **{py:class}`nexusLIMS.schemas.metadata.SpectrumMetadata`** - For Spectrum datasets
  - Validates spectrum-specific fields (acquisition_time, live_time, channel_size, etc.)
  - Used when `DatasetType == "Spectrum"`

- **{py:class}`nexusLIMS.schemas.metadata.SpectrumImageMetadata`** - For SpectrumImage datasets
  - Combines both Image and Spectrum field validation
  - Used when `DatasetType == "SpectrumImage"`

- **{py:class}`nexusLIMS.schemas.metadata.DiffractionMetadata`** - For Diffraction datasets
  - Validates diffraction-specific fields (camera_length, convergence_angle, etc.)
  - Used when `DatasetType == "Diffraction"`

- **{py:class}`nexusLIMS.schemas.metadata.NexusMetadata`** - Base schema
  - Used for `DatasetType == "Misc"` or `"Unknown"`
  - Validates only common required fields

**Validation Process:**
1. Extractor sets `DatasetType` field in `nx_meta`
2. `validate_nx_meta()` selects appropriate schema based on `DatasetType`
3. Schema validates both required fields and type-specific optional fields
4. Validation errors include detailed field-level diagnostics
5. **Strict validation** - invalid metadata causes extraction to fail

All schemas support the `extensions` section for instrument-specific metadata that doesn't fit the core schema (see "Core Fields vs. Extensions" below).

(schema-selection-logic)=
**Schema Selection Logic**

When writing an extractor, choose the appropriate `DatasetType` based on the data content:

| DatasetType | When to Use | Example Data | Schema Used |
|-------------|-------------|--------------|-------------|
| `"Image"` | 2D imaging data (SEM, TEM, STEM images) | Micrographs, detector images | `ImageMetadata` |
| `"Spectrum"` | 1D spectral data (EDS, EELS point spectra) | Single-point spectrum | `SpectrumMetadata` |
| `"SpectrumImage"` | 2D image with spectrum at each pixel | EDS maps, EELS spectrum images | `SpectrumImageMetadata` |
| `"Diffraction"` | Diffraction patterns (SAED, CBED, 4D-STEM) | Diffraction patterns, 4D datasets | `DiffractionMetadata` |
| `"Misc"` | Other data types | Proprietary formats, unusual data | `NexusMetadata` (base) |
| `"Unknown"` | Unable to determine type | Unreadable files, fallback | `NexusMetadata` (base) |

**Common extraction patterns:**

```python
# SEM image
nx_meta = {
    "DatasetType": "Image",  # → validates with ImageMetadata
    "Data Type": "SEM_Imaging",
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),
    # ... imaging-specific fields
}

# EDS spectrum
nx_meta = {
    "DatasetType": "Spectrum",  # → validates with SpectrumMetadata
    "Data Type": "SEM_EDS",
    "acquisition_time": ureg.Quantity(60, "second"),
    "live_time": ureg.Quantity(58.5, "second"),
    "channel_size": ureg.Quantity(10, "electronvolt"),
    # ... spectrum-specific fields
}

# EDS map (spectrum at each pixel)
nx_meta = {
    "DatasetType": "SpectrumImage",  # → validates with SpectrumImageMetadata
    "Data Type": "STEM_EDS",
    # Validates BOTH imaging and spectrum fields
    "acceleration_voltage": ureg.Quantity(200, "kilovolt"),
    "acquisition_time": ureg.Quantity(300, "second"),
    # ... combined fields
}
```

**Tip:** If unsure about `DatasetType`, examine the data shape:
- Single 2D array → likely `"Image"`
- Single 1D array with energy axis → likely `"Spectrum"`
- 3D array (x, y, spectrum) → likely `"SpectrumImage"`
- 2D array with reciprocal space metadata → likely `"Diffraction"`

For more details on validation and schema structure, see [NexusLIMS Internal Schema](nexuslims_internal_schema.md).

(using-pint-quantities)=
#### Using Pint Quantities for Physical Values

**Since v2.2.0**, NexusLIMS uses **Pint Quantities** for all fields with physical units. This provides:
- Type safety and automatic unit validation
- Programmatic unit conversion
- Machine-readable unit information
- Standardized field names using EM Glossary terminology

**Example with Pint Quantities:**
```python
# Import the NexusLIMS unit registry
from nexusLIMS.schemas.units import ureg

# Create Pint Quantity objects for fields with units
nx_meta = {
    "DatasetType": "Image",
    "Data Type": "SEM_Imaging",
    "Creation Time": "2024-01-15T10:30:00-05:00",

    # Physical quantities with units (using Pint)
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),  # or ureg("15 kV")
    "working_distance": ureg.Quantity(5.2, "millimeter"),  # or ureg("5.2 mm")
    "beam_current": ureg.Quantity(100, "picoampere"),  # or ureg("100 pA")
    "dwell_time": ureg.Quantity(10, "microsecond"),  # or ureg("10 us")
}
```

**Tip:** For a complete reference of standardized field names and their preferred units, see {ref}`EM Glossary Quick Reference <field-mapping-quick-reference>`. When defining Pydantic schemas (not extractors), you can use {ref}`emg_field() <metadata-helper-functions>` to automatically populate field metadata from EM Glossary.

**Converting from raw values:**
```python
from nexusLIMS.schemas.units import ureg

# If you have voltage in volts, create Quantity directly
voltage_v = 15000  # Volts from file
nx_meta["acceleration_voltage"] = ureg.Quantity(voltage_v, "volt")
# Pint will automatically handle unit conversion when needed

# Alternative: parse from string
nx_meta["working_distance"] = ureg("5.2 mm")
```

**Using FieldDefinition for bulk metadata extraction:**

The `FieldDefinition` pattern provides a declarative way to extract many metadata fields with minimal code repetition. This works for any file format with key-value metadata (TIFF tags, HDF5 attributes, JSON/XML metadata, etc.):

```python
from nexusLIMS.extractors.base import FieldDefinition

# Define fields with their target units
FIELD_DEFINITIONS = [
    FieldDefinition(
        source_key="HV",  # Key in source metadata
        target_key="acceleration_voltage",  # EM Glossary field name
        conversion_factor=1e-3,  # Convert from V to kV
        target_unit="kilovolt"  # Target unit as Pint unit string
    ),
    FieldDefinition(
        source_key="WD",
        target_key="working_distance",
        target_unit="millimeter"  # No conversion if already in target units
    ),
]

# In your extract() method, iterate over field definitions:
from decimal import Decimal

for field in FIELD_DEFINITIONS:
    if field.source_key in source_metadata:
        raw_value = source_metadata[field.source_key]

        # Apply conversion factor if specified
        if field.conversion_factor:
            value = Decimal(str(raw_value)) * Decimal(str(field.conversion_factor))
        else:
            value = Decimal(str(raw_value))

        # IMPORTANT: Quantities MUST use Decimal, not float
        # This ensures precision for unit conversions
        if field.target_unit:
            nx_meta[field.target_key] = ureg.Quantity(value, field.target_unit)
        else:
            nx_meta[field.target_key] = value
```

**Real-world examples:**
- [Quanta TIF extractor](../../nexusLIMS/extractors/plugins/quanta_tif.py) - Uses `FieldDefinition` for extracting TIFF metadata tags
- [Tescan TIF extractor](../../nexusLIMS/extractors/plugins/tescan_tif.py) - Uses `FieldDefinition` for SEM metadata extraction
- [Orion TIF extractor](../../nexusLIMS/extractors/plugins/orion_HIM_tif.py) - Uses `FieldDefinition` for HIM metadata extraction

**Benefits of Pint Quantities:**
1. **Type safety**: Invalid units are caught immediately
2. **Automatic conversion**: Units are normalized during XML generation
3. **Machine-readable**: Units are separate from values in XML output
4. **EM Glossary alignment**: Field names match community standards

**Important**: If a field has units, **always create a Pint Quantity**. If a field is dimensionless (like magnification, brightness, or gain), use a plain numeric value (int/float).

**XML Output:**
```xml
<!-- Pint Quantities serialize to clean XML with unit attributes -->
<meta name="Voltage" unit="kV">15</meta>
<meta name="Working Distance" unit="mm">5.2</meta>
<meta name="Beam Current" unit="pA">100</meta>
```

#### EM Glossary Field Names

NexusLIMS uses standardized field names from the **Electron Microscopy Glossary (EM Glossary)** for core metadata fields. This improves interoperability and aligns with community standards.

For the complete field mapping (50+ fields), see the [EM Glossary Reference](em_glossary_reference.md).

**When to use EM Glossary names:**
- Use EM Glossary names for **core metadata fields** that have standardized meanings
- For vendor-specific or instrument-specific fields, use EM Glossary names where possible, or for fields without EM Glossary equivalents, use descriptive names.

(core-fields-vs-extensions)=
#### Core Fields vs. Extensions

NexusLIMS metadata follows a two-tier structure:

1. **Core fields** - Standardized EM Glossary fields validated by Pydantic schemas
2. **Extensions** - Vendor/instrument-specific fields not in the core schema

**Decision guide:**

| Use Core Field When... | Use Extension When... |
|------------------------|----------------------|
| Field has EM Glossary equivalent | Field is vendor-specific (e.g., "fei_detector_mode") |
| Field is validated by schema | Field doesn't fit any schema |
| Field is common across instruments | Field is instrument-specific metadata |
| Field should be searchable/standardized | Field is informational only |

**Example with core fields and extensions:**
```python
from nexusLIMS.schemas.utils import add_to_extensions

nx_meta = {
    # Core fields (EM Glossary names) - validated by schema
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),
    "beam_current": ureg.Quantity(100, "picoampere"),
}

# Add vendor-specific fields to extensions using helper
add_to_extensions(nx_meta, "detector_brightness", 50.0)
add_to_extensions(nx_meta, "facility", "Nexus Facility")
add_to_extensions(nx_meta, "quanta_spot_size", 3.5)

# Result:
# nx_meta["extensions"] = {
#     "detector_brightness": 50.0,
#     "facility": "Nexus Facility",
#     "quanta_spot_size": 3.5,
# }
```

For detailed documentation, see {ref}`Helper Functions <metadata-helper-functions>`.

**Naming conventions for extensions:**
- Use `snake_case` for consistency with core fields
- Add vendor prefix for vendor-specific fields (e.g., `fei_`, `zeiss_`, `quanta_`)
- Use descriptive names (avoid abbreviations)
- Document units in comments if applicable

## Advanced Patterns

(content-based-detection)=
### Content-Based Detection

For formats where extension alone isn't sufficient:

```python
class MyFormatExtractor:
    name = "my_format_extractor"
    priority = 100
    supported_extensions = {"dat"}  # Register for .dat files
    
    def supports(self, context: ExtractionContext) -> bool:
        """Check file extension and validate file signature."""
        ext = context.file_path.suffix.lower().lstrip(".")
        if ext != "dat":
            return False
        
        # Check file signature (magic bytes)
        try:
            with context.file_path.open("rb") as f:
                header = f.read(4)
                return header == b"MYFT"  # Your format's signature
        except Exception:
            return False
```

**Important:** Keep `supported_extensions` synchronized with `supports()`. If your extractor is registered for `.dat` but `supports()` returns `False` for all `.dat` files, the registry will try other extractors.

### Instrument-Specific Extractors

Use the instrument information for instrument-specific handling:

```python
class QuantaTifExtractor:
    name = "quanta_tif_extractor"
    priority = 150  # Higher priority for specific instrument
    supported_extensions = {"tif"}  # Only .tif files
    
    def supports(self, context: ExtractionContext) -> bool:
        """Only support files from specific instruments."""
        ext = context.file_path.suffix.lower().lstrip(".")
        if ext != "tif":
            return False
        
        # Check instrument
        if context.instrument is None:
            return False
        
        # Only handle files from Quanta SEMs
        return "Quanta" in context.instrument.name
```

### Priority Guidelines

Set appropriate priorities for your extractor:

```python
class SpecificFormatExtractor:
    # High priority - handles specific format well
    priority = 150
    
class GenericFormatExtractor:
    # Medium priority - handles many formats adequately
    priority = 75
    
class FallbackExtractor:
    # Low/zero priority - only used when nothing else works
    priority = 0
```

## Testing Your Extractor

### Test Fixtures for Real File Formats

For testing with actual file formats (especially binary formats like microscopy data), NexusLIMS uses compressed tar archives to store sanitized test files efficiently.

**Setting up test fixtures:**

1. **Create sanitized test data** - Start with a real microscopy file from your target format, then remove/zero sensitive image data while preserving metadata structure. See {ref}`creating-sanitized-test-files` in the Developer Guide for detailed instructions.

2. **Add to test archive registry** in `tests/unit/utils.py`:
   ```python
   tars = {
       # ... existing entries ...
       "XYZ_FORMAT": "xyz_format_test_dataZeroed.tar.gz",
   }
   ```

3. **Place archive** in `tests/unit/files/`

The fixture system extracts files from `*.tar.gz` archives to a temporary test directory, makes them available during test execution, and automatically cleans up after tests complete. This keeps the repository small (compressed archives) while enabling tests with realistic file structures and metadata.

### Example Test File

Create a test file in `tests/unit/test_extractors/`:

```python
"""Tests for XYZ extractor."""

import pytest
from pathlib import Path
from nexusLIMS.extractors.plugins.xyz import XYZExtractor
from nexusLIMS.extractors.base import ExtractionContext
from tests.unit.utils import extract_files, delete_files


@pytest.fixture(scope="module")
def xyz_test_file():
    """Extract test XYZ file from archive."""
    files = extract_files("XYZ_FORMAT")
    yield files[0]  # Yield the extracted test file
    delete_files("XYZ_FORMAT")  # Clean up after tests


class TestXYZExtractor:
    """Test cases for XYZ format extractor."""

    def test_supports_xyz_files(self):
        """Test that extractor supports .xyz files."""
        extractor = XYZExtractor()
        context = ExtractionContext(Path("test.xyz"), instrument=None)
        assert extractor.supports(context) is True

    def test_rejects_other_files(self):
        """Test that extractor rejects non-.xyz files."""
        extractor = XYZExtractor()
        context = ExtractionContext(Path("test.dm3"), instrument=None)
        assert extractor.supports(context) is False

    def test_extraction_real_file(self, xyz_test_file):
        """
        Test metadata extraction from real XYZ file.
        
        Uses the "xyz_test_file" fixture to automatically extract,
        read, and then delete the real test file from the compressed
        archive.
        """
        from nexusLIMS.extractors import get_full_meta

        metadata = get_full_meta(xyz_test_file, instrument=None)

        # Verify extracted metadata
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        assert metadata["nx_meta"]["acceleration_voltage"].magnitude == 15.0
        # ... additional assertions
```

(best-practices)=
## Best Practices

### v2.2.0 Schema Patterns

**Use Pint Quantities consistently:**
```python
from decimal import Decimal
from nexusLIMS.schemas.units import ureg

# ✅ GOOD - Create Quantity for fields with units
nx_meta["acceleration_voltage"] = ureg.Quantity(15000, "volt")  # Auto-converts to kV
# For calculations/conversions, use Decimal explicitly:
nx_meta["acceleration_voltage"] = ureg.Quantity(Decimal("15000"), "volt")

# ❌ BAD - Don't use raw numbers for fields with units
nx_meta["acceleration_voltage"] = 15  # Missing unit information

# ✅ GOOD - Dimensionless values as plain numbers
nx_meta["magnification"] = 50000

# ❌ BAD - Don't create Quantities for dimensionless values
nx_meta["magnification"] = ureg.Quantity(50000, "dimensionless")
```

**Note on Decimal values:** The unit registry auto-converts numeric values to `Decimal` to avoid floating-point precision issues. While `ureg.Quantity(15, "kilovolt")` works, using `Decimal` explicitly is recommended when performing calculations or conversions (e.g., `Decimal(metadata["HV"]) * Decimal("1e-3")`) for clarity and to ensure precision.

**Use `add_to_extensions()` for vendor fields:**
```python
from nexusLIMS.schemas.utils import add_to_extensions

# ✅ GOOD - Use helper function
add_to_extensions(nx_meta, "fei_detector_mode", "CBS")
add_to_extensions(nx_meta, "facility", "Nexus Lab")

# ❌ BAD - Manual dict manipulation (doesn't keep implementation isolated)
if "extensions" not in nx_meta:
    nx_meta["extensions"] = {}
nx_meta["extensions"]["fei_detector_mode"] = "CBS"
```

**Set DatasetType early:**
```python
# ✅ GOOD - Set DatasetType first, then add type-specific fields
nx_meta = {
    "DatasetType": "Image",  # Schema selection happens based on this
    "Data Type": "SEM_Imaging",
    "Creation Time": creation_time_iso,
}
# Now add imaging-specific fields
nx_meta["acceleration_voltage"] = ureg.Quantity(15, "kilovolt")

# ❌ BAD - Adding fields before DatasetType
nx_meta = {}
nx_meta["acceleration_voltage"] = ureg.Quantity(15, "kilovolt")  # What schema validates this?
nx_meta["DatasetType"] = "Image"  # Too late
```

**Handle timezone in Creation Time:**
```python
from datetime import datetime as dt
from nexusLIMS.instruments import get_instr_from_filepath

# ✅ GOOD - Include timezone
instr = get_instr_from_filepath(context.file_path)
creation_time = dt.fromtimestamp(mtime, tz=instr.timezone if instr else None)
nx_meta["Creation Time"] = creation_time.isoformat()  # "2024-01-15T10:30:00-05:00"

# ❌ BAD - Naive datetime (no timezone)
creation_time = dt.fromtimestamp(mtime)
nx_meta["Creation Time"] = creation_time.isoformat()  # "2024-01-15T10:30:00" - FAILS validation
```

### Error Handling

Always handle errors gracefully:

```python
def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
    """Extract metadata with defensive error handling."""
    try:
        # Primary extraction logic (returns list)
        return self._extract_full_metadata(context)
    except Exception as e:
        logger.warning(
            "Error extracting full metadata from %s: %s",
            context.file_path,
            e,
            exc_info=True
        )
        # Return basic metadata as fallback (also as list)
        return self._extract_basic_metadata(context)
```

### Logging

Use appropriate log levels:

```python
logger.debug("Extracting metadata from %s", context.file_path)  # Routine operations
logger.info("Discovered unusual format variant in %s", context.file_path)  # Notable events
logger.warning("Missing expected metadata field in %s", context.file_path)  # Recoverable issues
logger.error("Failed to parse %s", context.file_path, exc_info=True)  # Serious errors
```

### Performance

For expensive operations, consider lazy evaluation:

```python
def extract(self, context: ExtractionContext) -> dict[str, Any]:
    """Extract metadata with lazy loading."""
    # Only load what's needed
    metadata = self._extract_header_metadata(context)

    # If using hyperspy, load the signal lazily:
    metadata = hs.load(context.filename, lazy=True).original_metadata

    # Don't load full data unless necessary
    if self._needs_full_data(metadata):
        metadata.update(self._extract_full_data(context))

    return metadata
```

## Migration from Legacy Extractors

If you have an existing extraction function (pre-v2.1.0), create a simple wrapper:

**Before (legacy):**
```python
# In nexusLIMS/extractors/my_format.py
def get_my_format_metadata(filename: Path) -> dict:
    # ... extraction logic
    return metadata
```

**After (plugin):**
```python
# In nexusLIMS/extractors/plugins/my_format.py
from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.my_format import get_my_format_metadata

class MyFormatExtractor:
    name = "my_format_extractor"
    priority = 100
    supported_extensions = {"myformat"}  # Declare supported extensions

    def supports(self, context: ExtractionContext) -> bool:
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "myformat"

    def extract(self, context: ExtractionContext) -> list[dict]:
        # Legacy function returns dict, wrap in list
        metadata = get_my_format_metadata(context.file_path)
        return [metadata]  # Always return a list
```

## Registry Behavior

The registry automatically:

1. **Discovers plugins** on first use by walking `nexusLIMS/extractors/plugins/`
2. **Sorts by priority** within each file extension
3. **Calls `supports()`** on each extractor in priority order
4. **Returns first match** where `supports()` returns `True`
5. **Falls back** to BasicFileInfoExtractor if nothing matches

You don't need to manually register your plugin - just create the file and it will be discovered automatically.

## Examples

See the built-in extractors for real-world examples:

- {py:mod}`nexusLIMS.extractors.plugins.digital_micrograph` - Simple extension-based matching
- {py:mod}`nexusLIMS.extractors.plugins.quanta_tif` - TIFF format for specific instruments
- {py:mod}`nexusLIMS.extractors.plugins.tescan_tif` - TIFF format with metadata content sniffing and parsing sidecar header file
- {py:mod}`nexusLIMS.extractors.plugins.basic_metadata` - Fallback extractor with priority 0
- {py:mod}`nexusLIMS.extractors.plugins.edax` - Multiple extractors in one file

## Troubleshooting

### My extractor isn't being discovered

Check that:
1. File is in `nexusLIMS/extractors/plugins/` (or subdirectory)
2. Class has all required attributes (`name`, `priority`, `supported_extensions`) and methods (`supports`, `extract`)
3. Class name doesn't start with underscore
4. No import errors (check logs)
5. `supported_extensions` is properly defined as a `set` or `None`

### My extractor isn't being selected

Check that:
1. `supported_extensions` includes the file's extension (without dot)
2. `supports()` returns `True` for your test file
3. Priority is high enough (higher priority extractors are tried first)
4. No higher-priority extractor is matching first
5. `supported_extensions` and `supports()` are synchronized (if registered for `.xyz`, `supports()` should return `True` for `.xyz` files)

Enable debug logging to see selection process:
```python
import logging
logging.getLogger("nexusLIMS.extractors.registry").setLevel(logging.DEBUG)
```

### Tests are failing

Ensure your extractor:
1. Returns a dictionary with `"nx_meta"` key
2. Includes required fields in `nx_meta`
3. Handles missing/corrupted files gracefully
4. Uses appropriate timezone for timestamps

## Metadata Reference Files

When developing extractor plugins, it's helpful to see examples of real metadata structures from different file formats. NexusLIMS maintains a collection of reference metadata files extracted from test data.

### Location

Reference metadata is stored in `tests/unit/files/metadata_references/` and includes:
- **127 JSON files** containing `original_metadata` from HyperSpy-readable test files
- **2 XML files** with raw TIFF metadata from Orion HIM instruments
- **README.md** documenting the reference files
- **extract_original_metadata.py** script to regenerate the references

### Contents

Each JSON file contains the complete `original_metadata` dictionary extracted from a test file using HyperSpy's `signal.original_metadata.as_dictionary()`. The files are named after their source files:

- Single-signal files: `{filename}_original_metadata.json`
- Multi-signal files: `{filename}_signal_{index}_original_metadata.json`

Format examples covered:
- Digital Micrograph (.dm3, .dm4) - Various TEM/STEM imaging and spectroscopy modes
- FEI TIA (.emi/.ser) - TEM/STEM images, spectra, and spectrum images
- FEI/Thermo Quanta (.tif) - SEM imaging with embedded metadata
- Zeiss Orion (.tif) - HIM imaging with Fibics or Zeiss metadata
- Tescan (.tif) - SEM/FIB imaging
- HyperSpy (.hspy) - 4D-STEM data

### Usage for Extractor Development

**1. Understanding metadata structure**

Before writing an extractor, examine the reference metadata to understand:
- What fields are available in the source format
- How the data is structured (nested dictionaries, lists, etc.)
- Which fields map to NexusLIMS required fields
- What vendor-specific fields exist

Example workflow:
```bash
# View metadata structure for a Quanta TIFF file
less tests/unit/files/metadata_references/quanta_image_original_metadata.json

# Search for specific fields
grep -r "acceleration" tests/unit/files/metadata_references/
```

**2. Mapping source fields to nx_meta**

Use the reference files to identify which source metadata keys should map to NexusLIMS fields:

```python
# Example: Mapping Quanta TIFF metadata to nx_meta
# Based on quanta_image_original_metadata.json:
# {
#   "User": {"HV": "15000.0", "WD": "5.2", ...},
#   "EScan": {"DwellTime": "1e-05", ...}
# }

# The NexusLIMS ureg requires the use of Decimal to ensure the source
# precision is retained when converting units
from decimal import Decimal

nx_meta["acceleration_voltage"] = ureg.Quantity(
    Decimal(metadata["User"]["HV"]) * Decimal("1e-3"),  # Convert V to kV
    "kilovolt"
)
nx_meta["working_distance"] = ureg.Quantity(
    Decimal(metadata["User"]["WD"]),
    "millimeter"
)
nx_meta["dwell_time"] = ureg.Quantity(
    Decimal(metadata["EScan"]["DwellTime"]) * Decimal("1e6"),  # Convert s to µs
    "microsecond"
)
```

**3. Testing against real metadata**

When writing tests, compare your extractor's output against the reference metadata to ensure you're handling all available fields correctly.

### Regenerating Reference Files

If test files are added or modified, regenerate the reference metadata:

```bash
cd tests/unit/files/metadata_references
uv run python extract_original_metadata.py
```

The script:
1. Extracts all files from test archives (`tests/unit/files/*.tar.gz`)
2. Loads each file with HyperSpy
3. Exports `original_metadata` as formatted JSON
4. Handles both single and multi-signal files automatically

This is particularly useful after:
- Adding new test files for a format
- Updating data-zeroing procedures
- Verifying metadata preservation after file modifications

### Benefits

Using metadata reference files helps you:
- **Write better extractors** - See real-world metadata structure before coding
- **Improve field coverage** - Identify fields you might have missed
- **Debug extraction issues** - Compare expected vs. actual metadata
- **Document metadata evolution** - Track changes in file format metadata over time
- **Onboard new developers** - Provide concrete examples of metadata structure

## Further Reading

- [Extractor Overview](../user_guide/extractors.md)
- [Instrument Profiles](instrument_profiles.md)
- [API Documentation](../api/nexusLIMS/nexusLIMS.extractors.md)
