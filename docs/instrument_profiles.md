# Instrument Profiles

## Overview

Instrument profiles provide a powerful mechanism for customizing metadata extraction behavior for specific microscopes without modifying core extractor code. This system is critical for NexusLIMS extensibility, as each installation has unique instruments with specific metadata quirks.

## What are Instrument Profiles?

An instrument profile is a collection of:

- **Parser functions**: Custom logic to process metadata for a specific instrument
- **Transformations**: Functions to modify extracted metadata values
- **Extractor overrides**: Force specific extractors for certain file types
- **Static metadata**: Pre-defined values to inject for all files from this instrument

Profiles are automatically discovered and registered when NexusLIMS starts, making it easy to add instrument-specific customizations without touching the core codebase.

## When to Use Instrument Profiles

Use instrument profiles when you need to:

1. **Handle instrument-specific metadata quirks**: Some microscopes store metadata in non-standard locations or formats
2. **Add warnings for unreliable metadata**: Flag fields known to be inaccurate on specific instruments
3. **Detect special modes**: Identify diffraction patterns, EELS spectra, etc. using instrument-specific heuristics
4. **Parse vendor-specific formats**: Process proprietary metadata formats unique to one microscope
5. **Override default extraction**: Use a specialized extractor for files from a specific instrument

**Don't use profiles for**:
- Generic file format parsing (belongs in extractors)
- One-time data fixes (use a script instead)
- Site-wide configuration (use environment variables or settings)

## Creating an Instrument Profile

### Step 1: Create a Profile Module

Create a new Python file in `nexusLIMS/extractors/plugins/profiles/`:

```python
"""Instrument profile for My Custom Microscope."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import ExtractionContext

logger = logging.getLogger(__name__)


def my_custom_parser(
    metadata: dict[str, Any],
    context: ExtractionContext,
) -> dict[str, Any]:
    """
    Add custom metadata processing for my instrument.

    Parameters
    ----------
    metadata
        Metadata dictionary with 'nx_meta' key
    context
        Extraction context with file path and instrument info

    Returns
    -------
    dict
        Modified metadata dictionary
    """
    # Your custom logic here
    if "Some Field" in metadata["nx_meta"]:
        # Process the field
        value = metadata["nx_meta"]["Some Field"]
        metadata["nx_meta"]["Processed Field"] = process_value(value)

    return metadata


# Register the profile
from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry

my_instrument_profile = InstrumentProfile(
    instrument_id="My-Microscope-ID",  # Must match instrument.name from database
    parsers={
        "custom_processing": my_custom_parser,
    },
    static_metadata={
        "nx_meta.Building": "Building 123",
        "nx_meta.Room": "Room 456",
    },
)

get_profile_registry().register(my_instrument_profile)

logger.debug("Registered My Custom Microscope instrument profile")
```

### Step 2: Match Instrument ID

The `instrument_id` in your profile must **exactly match** the instrument's `name` field in the NexusLIMS database. Check your database:

```python
from nexusLIMS.db import Session_Handler

db = Session_Handler()
instruments = db.get_all_instruments()
for instr in instruments:
    print(f"Instrument: {instr.name}")
```

### Step 3: Test Your Profile

Profiles are auto-discovered on import. Test by:

```python
from nexusLIMS.extractors.profiles import get_profile_registry
from nexusLIMS.instruments import get_all_instruments

# Check profile is registered
registry = get_profile_registry()
all_profiles = registry.get_all_profiles()
print(f"Registered profiles: {list(all_profiles.keys())}")

# Test with your instrument
instrument = next(i for i in get_all_instruments() if i.name == "My-Microscope-ID")
profile = registry.get_profile(instrument)
print(f"Found profile: {profile is not None}")
```

## Profile Components

### Parser Functions

Parser functions receive metadata and context, returning modified metadata:

```python
def add_warnings(metadata: dict[str, Any], context: ExtractionContext) -> dict[str, Any]:
    """Add warnings for unreliable fields."""
    warnings = metadata["nx_meta"].get("warnings", [])
    warnings.append(["Temperature"])  # Temperature readings are unreliable
    metadata["nx_meta"]["warnings"] = warnings
    return metadata
```

**Guidelines:**
- Always return the modified metadata dictionary
- Don't raise exceptions - log errors and return unchanged metadata
- Keep functions focused - one parser per logical operation
- Document what the parser does in the docstring

### Transformations

Transformations modify specific metadata values:

```python
def convert_to_meters(value: float) -> float:
    """Convert millimeters to meters."""
    return value / 1000.0

profile = InstrumentProfile(
    instrument_id="My-Microscope-ID",
    transformations={
        "nx_meta.Stage_X": convert_to_meters,
        "nx_meta.Stage_Y": convert_to_meters,
    },
)
```

The transformation is applied if the key exists in metadata.

### Static Metadata

Inject fixed values for all files from this instrument:

```python
profile = InstrumentProfile(
    instrument_id="My-Microscope-ID",
    static_metadata={
        "nx_meta.Facility": "My Lab",
        "nx_meta.Building": "Building A",
        "nx_meta.Department": "Materials Science",
    },
)
```

Use dot notation for nested keys. The values are injected after extraction completes.

### Extractor Overrides

Force specific extractors for certain file extensions:

```python
profile = InstrumentProfile(
    instrument_id="My-Zeiss-SEM",
    extractor_overrides={
        "tif": "zeiss_tif_extractor",  # Use Zeiss-specific TIF extractor
    },
)
```

This is useful when multiple extractors support the same extension but one works better for your instrument.

## Examples

### Example 1: Simple Warning Profile

Add warnings for fields known to be unreliable:

```python
"""Profile for FEI Quanta SEM with unreliable metadata."""

from nexusLIMS.extractors.base import InstrumentProfile
from nexusLIMS.extractors.profiles import get_profile_registry


def add_metadata_warnings(metadata, context):
    """Warn about unreliable detector and operator fields."""
    warnings = metadata["nx_meta"].get("warnings", [])
    warnings.extend([["Detector"], ["Operator"]])
    metadata["nx_meta"]["warnings"] = warnings
    return metadata


quanta_profile = InstrumentProfile(
    instrument_id="FEI-Quanta-12345",
    parsers={"warnings": add_metadata_warnings},
)

get_profile_registry().register(quanta_profile)
```

### Example 2: Diffraction Detection Profile

Detect diffraction patterns using filename heuristics:

```python
"""Profile for JEOL microscope with filename-based diffraction detection."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_diffraction_from_filename(metadata, context):
    """Detect diffraction patterns from common filename patterns."""
    filename = str(context.file_path)

    for pattern in ["Diff", "SAED", "DP"]:
        if pattern.lower() in filename.lower():
            logger.info(f"Detected diffraction pattern from '{pattern}' in filename")
            metadata["nx_meta"]["DatasetType"] = "Diffraction"
            metadata["nx_meta"]["Data Type"] = "TEM_Diffraction"
            break

    return metadata


jeol_profile = InstrumentProfile(
    instrument_id="JEOL-JEM-TEM-565989",
    parsers={"diffraction_detection": detect_diffraction_from_filename},
)

get_profile_registry().register(jeol_profile)
```

### Example 3: Complex Metadata Parsing

Parse vendor-specific metadata strings:

```python
"""Profile for FEI Titan TEM with Tecnai metadata parsing."""

from nexusLIMS.utils import (
    get_nested_dict_key,
    get_nested_dict_value_by_path,
    set_nested_dict_value,
)


def parse_tecnai_metadata(metadata, context):
    """Parse FEI Tecnai metadata from delimited string."""
    # Import processing function from DM3 extractor
    from nexusLIMS.extractors.plugins.digital_micrograph import (
        process_tecnai_microscope_info,
    )

    # Check if Tecnai metadata exists
    path_to_tecnai = get_nested_dict_key(metadata, "Tecnai")
    if path_to_tecnai is None:
        return metadata

    # Extract and process Tecnai microscope info
    tecnai_value = get_nested_dict_value_by_path(metadata, path_to_tecnai)
    microscope_info = tecnai_value["Microscope Info"]
    processed = process_tecnai_microscope_info(microscope_info)

    # Update metadata tree
    tecnai_value["Microscope Info"] = processed
    set_nested_dict_value(metadata, path_to_tecnai, tecnai_value)

    # Map to NexusLIMS metadata fields
    if "Gun_Name" in processed:
        metadata["nx_meta"]["Gun Name"] = processed["Gun_Name"]
    if "Spot" in processed:
        metadata["nx_meta"]["Spot"] = processed["Spot"]

    return metadata


titan_profile = InstrumentProfile(
    instrument_id="FEI-Titan-TEM-012345",
    parsers={"tecnai_metadata": parse_tecnai_metadata},
)

get_profile_registry().register(titan_profile)
```

## Built-in Profiles

NexusLIMS includes profiles for common instruments:

### FEI Titan STEM (643)

**Module:** `nexusLIMS.extractors.plugins.profiles.fei_titan_stem_643`

**Features:**
- Adds warnings for unreliable Detector, Operator, and Specimen fields
- Detects EFTEM diffraction patterns from "Imaging Mode" metadata

### FEI Titan TEM (642)

**Module:** `nexusLIMS.extractors.plugins.profiles.fei_titan_tem_642`

**Features:**
- Parses Tecnai-specific metadata (29+ fields)
- Detects diffraction mode from Tecnai Mode or Operation Mode
- Handles stage position, aperture settings, and filter parameters

### JEOL JEM TEM (642 Stroboscope)

**Module:** `nexusLIMS.extractors.plugins.profiles.jeol_jem_642`

**Features:**
- Detects diffraction patterns using filename heuristics (Diff, SAED, DP)
- Adds warnings for DatasetType and Data Type (unreliable detection)

## Troubleshooting

### Profile Not Loading

**Problem:** Your profile doesn't appear in `get_all_profiles()`

**Solutions:**
1. Check filename - must be a `.py` file in `nexusLIMS/extractors/plugins/profiles/`
2. Verify registration call at bottom of module:
   ```python
   get_profile_registry().register(my_profile)
   ```
3. Check for import errors in profile module
4. Ensure `instrument_id` exactly matches database instrument name

### Parser Not Running

**Problem:** Parser function isn't being called

**Solutions:**
1. Verify instrument ID matches: compare `profile.instrument_id` with `instrument.name`
2. Check extractor's `_apply_profile()` method is called
3. Add debug logging to verify profile lookup:
   ```python
   profile = get_profile_registry().get_profile(instrument)
   logger.debug(f"Found profile: {profile}")
   ```

### Metadata Not Changed

**Problem:** Parser runs but metadata unchanged

**Solutions:**
1. Ensure parser returns the modified metadata dictionary
2. Check for exceptions in parser (caught and logged as warnings)
3. Verify metadata keys exist before modification
4. Test parser function in isolation:
   ```python
   metadata = {"nx_meta": {...}}
   result = my_parser(metadata, mock_context)
   assert result["nx_meta"]["new_field"] == "expected_value"
   ```

## Best Practices

### 1. Keep Profiles Focused

One profile per instrument. Don't create "generic" profiles for multiple instruments unless they're truly identical.

### 2. Document Everything

Every parser function should have a clear docstring explaining:
- What it does
- Why it's needed (instrument quirk, vendor format, etc.)
- What metadata it modifies

### 3. Handle Missing Data Gracefully

Always check if keys exist before accessing:

```python
if "Field" in metadata["nx_meta"]:
    value = metadata["nx_meta"]["Field"]
    # process value
```

### 4. Log Important Decisions

Use structured logging to explain why metadata was changed:

```python
logger.info("Detected diffraction mode based on Tecnai Mode = %s", mode_value)
```

### 5. Write Tests

Create tests for your profile in `tests/test_extractors/test_instrument_profile_modules.py`:

```python
def test_my_profile_parser():
    """Test my custom parser function."""
    metadata = {"nx_meta": {"Input Field": "value"}}
    context = mock_context()

    result = my_parser(metadata, context)

    assert result["nx_meta"]["Output Field"] == "expected_value"
```

### 6. Reuse Helper Functions

If multiple profiles need similar logic, create helper functions in the extractor module and import them:

```python
from nexusLIMS.extractors.plugins.digital_micrograph import (
    process_tecnai_microscope_info,  # Reusable helper
)
```

## Advanced Topics

### Profile Inheritance

Profiles don't support inheritance, but you can share parser functions:

```python
# shared_parsers.py
def common_parser(metadata, context):
    """Common logic for multiple instruments."""
    return metadata

# profile_a.py
from .shared_parsers import common_parser

profile_a = InstrumentProfile(
    instrument_id="Instrument-A",
    parsers={"common": common_parser, "specific": specific_parser_a},
)

# profile_b.py
from .shared_parsers import common_parser

profile_b = InstrumentProfile(
    instrument_id="Instrument-B",
    parsers={"common": common_parser, "specific": specific_parser_b},
)
```

### Dynamic Profile Registration

For advanced use cases, you can register profiles programmatically:

```python
from nexusLIMS.extractors.profiles import get_profile_registry
from nexusLIMS.db import Session_Handler

# Register profiles for all FEI instruments
db = Session_Handler()
for instrument in db.get_all_instruments():
    if "FEI" in instrument.name:
        profile = create_fei_profile(instrument)  # Your custom function
        get_profile_registry().register(profile)
```

### Profile Priority

When multiple parsers are defined, they execute in dictionary order (Python 3.7+). If order matters, use an `OrderedDict`:

```python
from collections import OrderedDict

profile = InstrumentProfile(
    instrument_id="My-Instrument",
    parsers=OrderedDict([
        ("first", parser_1),
        ("second", parser_2),
        ("third", parser_3),
    ]),
)
```

## See Also

- [Writing Extractor Plugins](writing_extractor_plugins.md) - Learn to write new extractors
- [Extractors Overview](extractors.rst) - Understanding the extraction system
- API Reference: {class}`nexusLIMS.extractors.base.InstrumentProfile`
- API Reference: {class}`nexusLIMS.extractors.profiles.InstrumentProfileRegistry`
