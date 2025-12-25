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
        return extension == "xyz"
    
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

#### Metadata Validation

The `nx_meta` section is automatically validated using Pydantic schemas. NexusLIMS provides built-in validation schemas:

- **{py:class}`nexusLIMS.schemas.metadata.NexusMetadata`** - Base schema validating all extractors
  - Validates required fields and ISO-8601 timestamp format with timezone
  - Allows arbitrary additional fields for instrument-specific metadata
  - Supports `extensions` section for instrument-specific or custom fields

- **Type-specific schemas** - Dataset-type-specific validation:
  - **{py:class}`nexusLIMS.schemas.metadata.ImageMetadata`** - For Image datasets
  - **{py:class}`nexusLIMS.schemas.metadata.SpectrumMetadata`** - For Spectrum datasets
  - **{py:class}`nexusLIMS.schemas.metadata.SpectrumImageMetadata`** - For SpectrumImage datasets
  - **{py:class}`nexusLIMS.schemas.metadata.DiffractionMetadata`** - For Diffraction datasets
  - These schemas use **EM Glossary** field names for standardization
  - Support **Pint Quantity** objects for fields with units

The base `NexusMetadata` schema validation is **automatically performed** during record building, ensuring metadata consistency across all extractors.

#### Using Pint Quantities for Physical Values

**Since v2.2.0**, NexusLIMS uses **Pint Quantities** for all fields with physical units. This provides:
- Type safety and automatic unit validation
- Programmatic unit conversion
- Machine-readable unit information
- Standardized field names using EM Glossary terminology

**Example with Pint Quantities:**
```python
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

**Using FieldDefinition for automatic Quantity creation:**

For TIFF-based formats with key-value metadata, use the `FieldDefinition` pattern:

```python
from nexusLIMS.extractors.base import FieldDefinition

# Define fields with their target units
FIELD_DEFINITIONS = [
    FieldDefinition(
        source_key="HV",  # Key in source metadata
        target_key="acceleration_voltage",  # EM Glossary field name
        conversion_factor=1e-3,  # Convert from V to kV
        unit="kilovolt"  # Target unit as Pint unit string
    ),
    FieldDefinition(
        source_key="WD", 
        target_key="working_distance",
        unit="millimeter"  # No conversion if already in target units
    ),
]

# In your extract() method, iterate over field definitions:
for field in FIELD_DEFINITIONS:
    if field.source_key in source_metadata:
        raw_value = source_metadata[field.source_key]
        
        # Apply conversion factor if specified
        if field.conversion_factor:
            value = float(raw_value) * field.conversion_factor
        else:
            value = float(raw_value)
        
        # Create Pint Quantity if unit is specified
        if field.unit:
            nx_meta[field.target_key] = ureg.Quantity(value, field.unit)
        else:
            nx_meta[field.target_key] = value
```

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

**Common EM Glossary Fields:**

| Field Name | EM Glossary ID | Preferred Unit | Description |
|------------|----------------|----------------|-------------|
| `acceleration_voltage` | EMG_00000004 | kilovolt (kV) | Electron beam acceleration voltage |
| `working_distance` | EMG_00000050 | millimeter (mm) | Distance from pole piece to sample |
| `beam_current` | EMG_00000006 | picoampere (pA) | Electron beam current |
| `dwell_time` | EMG_00000015 | microsecond (µs) | Pixel dwell time for scanning |
| `camera_length` | EMG_00000008 | millimeter (mm) | Camera length for diffraction |
| `acquisition_time` | EMG_00000055 | second (s) | Spectrum acquisition time |

For a complete mapping of field names to EM Glossary IDs and preferred units, see the [EM Glossary Reference](em_glossary_reference.md).

**When to use EM Glossary names:**
- Use EM Glossary names for **core metadata fields** that have standardized meanings
- For vendor-specific or instrument-specific fields without EM Glossary equivalents, use descriptive names and place them in the `extensions` section

**Example with core fields and extensions:**
```python
nx_meta = {
    # Core fields (EM Glossary names)
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),
    "working_distance": ureg.Quantity(5.2, "millimeter"),
    
    # Vendor-specific fields go in extensions
    "extensions": {
        "detector_brightness": 50.0,  # No EM Glossary equivalent
        "facility": "Nexus Facility",
        "quanta_spot_size": 3.5,
    }
}
```

## Advanced Patterns

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

### Using Existing Extraction Functions

If you have existing extraction code, wrap it in a plugin:

```python
from nexusLIMS.extractors.my_format import get_my_format_metadata
from nexusLIMS.extractors.base import ExtractionContext

class MyFormatExtractor:
    name = "my_format_extractor"
    priority = 100
    supported_extensions = {"myformat"}
    
    def supports(self, context: ExtractionContext) -> bool:
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "myformat"
    
    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        # Delegate to existing function
        return get_my_format_metadata(context.file_path)
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

Create a test file in `tests/test_extractors/`:

```python
"""Tests for XYZ extractor."""

import pytest
from pathlib import Path
from nexusLIMS.extractors.plugins.xyz import XYZExtractor
from nexusLIMS.extractors.base import ExtractionContext


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
    
    def test_extraction(self, tmp_path):
        """Test metadata extraction from XYZ file."""
        # Create test file
        test_file = tmp_path / "test.xyz"
        test_file.write_text("XYZ test data")

        extractor = XYZExtractor()
        context = ExtractionContext(test_file, instrument=None)
        metadata_list = extractor.extract(context)

        # Extract returns a list, get the first element
        assert isinstance(metadata_list, list)
        assert len(metadata_list) == 1
        metadata = metadata_list[0]

        # Verify required fields
        assert "nx_meta" in metadata
        assert "DatasetType" in metadata["nx_meta"]
        assert "Data Type" in metadata["nx_meta"]
        assert "Creation Time" in metadata["nx_meta"]
```

## Best Practices

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

- `nexusLIMS/extractors/plugins/digital_micrograph.py` - Simple extension-based matching
- `nexusLIMS/extractors/plugins/quanta_tif.py` - TIFF format for specific instruments
- `nexusLIMS/extractors/plugins/basic_metadata.py` - Fallback extractor with priority 0
- `nexusLIMS/extractors/plugins/edax.py` - Multiple extractors in one file

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

## Further Reading

- [Extractor Overview](extractors.md)
- [Instrument Profiles](instrument_profiles.md)
- [API Documentation](api/nexusLIMS/nexusLIMS.extractors.md)
