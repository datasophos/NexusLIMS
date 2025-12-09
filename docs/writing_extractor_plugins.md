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
    
    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from an XYZ file.
        
        Parameters
        ----------
        context : ExtractionContext
            Contains file_path and instrument information
            
        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key
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
        
        return metadata
    
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

#### `extract(context: ExtractionContext) -> dict[str, Any]`
Extract metadata from the file.

**Parameters:**
- `context`: Contains `file_path` (Path) and `instrument` (Instrument or None)

**Returns:** Dictionary with at minimum an `"nx_meta"` key containing NexusLIMS metadata

**Required `nx_meta` fields:**
- `"DatasetType"`: One of "Image", "Spectrum", "SpectrumImage", "Diffraction", "Misc"
- `"Data Type"`: Descriptive string (e.g., "STEM_Imaging", "TEM_EDS")
- `"Creation Time"`: ISO-8601 formatted timestamp

**Example:**
```python
def extract(self, context: ExtractionContext) -> dict[str, Any]:
    metadata = {"nx_meta": {}}
    metadata["nx_meta"]["DatasetType"] = "Image"
    metadata["nx_meta"]["Data Type"] = "SEM_Imaging"
    # ... extraction logic
    return metadata
```

## Advanced Patterns

### Content-Based Detection

For formats where extension alone isn't sufficient:

```python
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

### Instrument-Specific Extractors

Use the instrument information for instrument-specific handling:

```python
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

class MyFormatExtractor:
    name = "my_format_extractor"
    priority = 100
    
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
        metadata = extractor.extract(context)
        
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
def extract(self, context: ExtractionContext) -> dict[str, Any]:
    """Extract metadata with defensive error handling."""
    try:
        # Primary extraction logic
        return self._extract_full_metadata(context)
    except Exception as e:
        logger.warning(
            "Error extracting full metadata from %s: %s",
            context.file_path,
            e,
            exc_info=True
        )
        # Return basic metadata as fallback
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
    
    def supports(self, context: ExtractionContext) -> bool:
        ext = context.file_path.suffix.lower().lstrip(".")
        return ext == "myformat"
    
    def extract(self, context: ExtractionContext) -> dict:
        return get_my_format_metadata(context.file_path)
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
2. Class has all required attributes (`name`, `priority`) and methods (`supports`, `extract`)
3. Class name doesn't start with underscore
4. No import errors (check logs)

### My extractor isn't being selected

Check that:
1. `supports()` returns `True` for your test file
2. Priority is high enough (higher priority extractors are tried first)
3. No higher-priority extractor is matching first

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

- [Extractor Overview](extractors.rst)
- [Instrument Profiles](instrument_profiles.md)
- [API Documentation](api/nexusLIMS/nexusLIMS.extractors.md)
