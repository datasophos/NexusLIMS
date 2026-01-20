(instrument-profiles)=
# Instrument Profiles

## Overview

Instrument profiles provide a powerful mechanism for customizing metadata extraction behavior for specific microscopes without modifying core extractor code. This system is critical for NexusLIMS extensibility, as each installation has unique instruments with specific metadata quirks.

NexusLIMS supports both **built-in profiles** (shipped with the codebase) and **local profiles** (stored outside the codebase). Local profiles are ideal for site-specific instruments, allowing you to maintain custom configurations independently of NexusLIMS updates.

## What are Instrument Profiles?

An instrument profile is a collection of:

- **Parser functions**: Custom logic to process metadata for a specific instrument
- **Transformations**: Functions to modify extracted metadata values
- **Extractor overrides**: Force specific extractors for certain file types
- **Extension fields**: Pre-defined values to inject into the extensions section for all files from this instrument

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

You have two options for creating instrument profiles:

1. **Built-in profiles**: Add to the NexusLIMS codebase at `nexusLIMS/extractors/plugins/profiles/`
2. **Local profiles**: Create in a separate directory outside the codebase (recommended for site-specific instruments)

### Local Profiles (Recommended for Site-Specific Instruments)

Local profiles are kept separate from the NexusLIMS codebase, making it easy to maintain site-specific customizations without worrying about git conflicts or merge issues when updating NexusLIMS.

#### Step 1a: Configure Local Profiles Directory

Add to your `.env` file:

```bash
NX_LOCAL_PROFILES_PATH=/opt/nexuslims/local_profiles
```

Create the directory:

```bash
mkdir -p /opt/nexuslims/local_profiles
```

#### Step 1b: Create a Local Profile Module

Create a Python file in your local profiles directory (e.g., `/opt/nexuslims/local_profiles/my_instrument.py`).

**TIP:** See [local_profile_example.py](examples/local_profile_example.py) for a complete, well-documented example you can copy and customize.

Basic example:

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
    extension_fields={
        "Building": "Building 123",
        "Room": "Room 456",
    },
)

get_profile_registry().register(my_instrument_profile)

logger.debug("Registered My Custom Microscope instrument profile")
```

**Note:** Local profiles work identically to built-in profiles - they use the same API and registration mechanism. The only difference is where the files are stored.

### Built-in Profiles (For Contributing to NexusLIMS)

If you're developing a profile that would benefit the broader NexusLIMS community (e.g., for a common commercial instrument), consider contributing it as a built-in profile.

Create a new Python file in `nexusLIMS/extractors/plugins/profiles/` following the same structure as shown above for local profiles.

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

Transformations modify top-level metadata keys returned by extractors. They're applied to `metadata[key]` where `metadata` is the dict returned by an extractor (typically containing `"nx_meta"`, `"hyperspy_metadata"`, etc.).

**Example: Converting stage positions**

```python
from typing import Any

def fix_stage_positions(nx_meta: dict[str, Any]) -> dict[str, Any]:
    """
    Convert stage positions from micrometers to millimeters.

    Some instruments report stage position in µm but should be in mm.
    """
    if "stage_x" in nx_meta:
        # Extract magnitude and convert
        old_x = nx_meta["stage_x"]
        if hasattr(old_x, "magnitude"):
            # It's a Pint Quantity
            from nexusLIMS.schemas.units import ureg
            from decimal import Decimal
            nx_meta["stage_x"] = ureg.Quantity(
                old_x.to("micrometer").magnitude / Decimal("1000"),
                "millimeter"
            )

    if "stage_y" in nx_meta:
        old_y = nx_meta["stage_y"]
        if hasattr(old_y, "magnitude"):
            from nexusLIMS.schemas.units import ureg
            from decimal import Decimal
            nx_meta["stage_y"] = ureg.Quantity(
                old_y.to("micrometer").magnitude / Decimal("1000"),
                "millimeter"
            )

    return nx_meta

profile = InstrumentProfile(
    instrument_id="My-Microscope-ID",
    transformations={
        "nx_meta": fix_stage_positions,  # Transforms the nx_meta dict
    },
)
```

**How transformations work:**
1. Extractor returns `{"nx_meta": {...}, "hyperspy_metadata": {...}, ...}`
2. For each `(key, func)` in `profile.transformations`:
   - If `key` exists in the metadata dict: `metadata[key] = func(metadata[key])`
3. The transformation function receives the **value** of that key and returns the modified value

**Common use cases:**
- Correcting unit conversions
- Fixing known instrument calibration issues
- Normalizing values from different file format versions
- Post-processing metadata that extractors can't handle generically

**Note:** Transformations are applied **after** parsers, so parsers can add fields that transformations then modify.

### Extension Fields

Inject fixed values into the `extensions` section for all files from this instrument:

```python
profile = InstrumentProfile(
    instrument_id="My-Microscope-ID",
    extension_fields={
        "Facility": "My Lab",
        "Building": "Building A",
        "Department": "Materials Science",
    },
)
```

**How it works:**
- Extension fields populate `nx_meta["extensions"]` automatically
- Use simple field names (not dot notation) - they're automatically placed in the extensions dict
- Values can be strings, numbers, or Pint Quantities
- These fields are added **after** extraction completes, so they override any conflicting extractor-provided extensions

**When to use extension fields:**
- Adding site-specific metadata (facility, building, room)
- Instrument calibration constants
- Fixed instrument configuration (detector type, camera model)
- Defaults that can be overridden by extractor logic

**Example with Pint Quantities:**
```python
from nexusLIMS.schemas.units import ureg

profile = InstrumentProfile(
    instrument_id="My-SEM",
    extension_fields={
        "Facility": "NIST Center for Nanoscale Science",
        "Building": "Bldg 217",
        "Room": "A206",
        # Physical quantities also supported
        "detector_solid_angle": ureg.Quantity(Decimal("0.2"), "steradian"),
        "nominal_detector_distance": ureg.Quantity(Decimal("50"), "millimeter"),
    },
)
```

For complex metadata injection logic or conditional behavior, use parser functions instead of extension_fields.

## Examples

**📄 Complete Example File:** For a comprehensive, production-ready example, see [local_profile_example.py](examples/local_profile_example.py). This file includes:
- Multiple parser functions with detailed comments
- Facility metadata injection
- Warning generation for unreliable fields
- Filename-based acquisition mode detection
- Best practices and common patterns

**🧪 Working Test Examples:** For additional examples showing profiles in action during extraction, see the test suite at `tests/unit/test_extractors/test_profiles.py::TestProfileApplicationDuringExtraction`. These tests demonstrate:
- How parsers are applied during metadata extraction
- How transformations modify extracted metadata
- How extension fields are injected
- Error handling when parsers/transformations fail

The examples below show specific use cases in isolation.

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
    instrument_id="JEOL-JEM-TEM",
    parsers={"diffraction_detection": detect_diffraction_from_filename},
)

get_profile_registry().register(jeol_profile)
```

### Example 3: Complex Metadata Parsing

Parse vendor-specific metadata strings:

```python
"""Profile for FEI Titan TEM with Tecnai metadata parsing."""

from benedict import benedict
from nexusLIMS.utils import set_nested_dict_value


def parse_tecnai_metadata(metadata, context):
    """Parse FEI Tecnai metadata from delimited string."""
    # Import processing function from DM3 extractor
    from nexusLIMS.extractors.plugins.digital_micrograph import (
        process_tecnai_microscope_info,
    )

    # Check if Tecnai metadata exists using benedict's keypaths method
    b = benedict(metadata)
    keypaths_list = b.keypaths()

    # Find the keypath that ends with "Tecnai"
    path_to_tecnai = None
    for keypath in keypaths_list:
        if keypath.endswith(".Tecnai") or keypath == "Tecnai":
            path_to_tecnai = keypath.split(".")
            break

    if path_to_tecnai is None:
        return metadata

    # Extract and process Tecnai microscope info
    tecnai_value = b[".".join(path_to_tecnai)]
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

NexusLIMS includes reference profiles developed for instruments
in the Nexus Electron Microscopy facility at NIST:

### FEI Titan STEM

**Module:** `nexusLIMS.extractors.plugins.profiles.fei_titan_stem_643`

**Features:**
- Adds warnings for unreliable Detector, Operator, and Specimen fields
- Detects EFTEM diffraction patterns from "Imaging Mode" metadata

### FEI Titan TEM

**Module:** `nexusLIMS.extractors.plugins.profiles.fei_titan_tem_642`

**Features:**
- Parses Tecnai-specific metadata (29+ fields)
- Detects diffraction mode from Tecnai Mode or Operation Mode
- Handles stage position, aperture settings, and filter parameters

### JEOL JEM TEM (Stroboscope)

**Module:** `nexusLIMS.extractors.plugins.profiles.jeol_jem_642`

**Features:**
- Detects diffraction patterns using filename heuristics (Diff, SAED, DP)
- Adds warnings for DatasetType and Data Type (unreliable detection)

## Troubleshooting

### Profile Not Loading

**Problem:** Your profile doesn't appear in `get_all_profiles()`

**Solutions:**

For **local profiles**:
1. Verify `NX_LOCAL_PROFILES_PATH` is set correctly in `.env`
2. Check the directory exists and is readable
3. Ensure profile file ends with `.py` and doesn't start with `_`
4. Look for error messages in logs during profile discovery
5. Verify registration call at bottom of module:
   ```python
   get_profile_registry().register(my_profile)
   ```
6. Check for import errors in profile module (e.g., missing dependencies)
7. Ensure `instrument_id` exactly matches database instrument name

For **built-in profiles**:
1. Check filename - must be a `.py` file in `nexusLIMS/extractors/plugins/profiles/`
2. Verify registration call at bottom of module
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

## Schema Validation in Profiles

```{versionadded} 2.2.0
All metadata is validated using Pydantic schemas before being included in records. This applies to metadata extracted by plugins and modified by instrument profiles.
```

### Key Concepts

When your profile modifies metadata:

1. **Core fields** (EM Glossary names like `acceleration_voltage`, `working_distance`) are validated by type-specific schemas
2. **Extension fields** (added via `extension_fields` or `add_to_extensions()`) are not validated
3. Validation happens **after** all profile processing (parsers → transformations → extensions)

### Quick Reference

**Adding validated core fields in parsers:**
```python
from nexusLIMS.schemas.units import ureg

def add_calibrated_voltage(metadata, context):
    # Core field - will be validated
    metadata["nx_meta"]["acceleration_voltage"] = ureg.Quantity(200, "kilovolt")
    return metadata
```

**Adding unvalidated extension fields:**
```python
from nexusLIMS.schemas.utils import add_to_extensions

def add_facility_metadata(metadata, context):
    # Extensions - not validated
    add_to_extensions(metadata, "facility", "NIST CNST")
    add_to_extensions(metadata, "room", "A206")
    return metadata
```

### For More Details

For comprehensive information on working with metadata in profiles, see:

- **Using Pint Quantities with units**: {ref}`Using Pint Quantities for Physical Values <using-pint-quantities>`
- **EM Glossary field names**: [EM Glossary Reference](em_glossary_reference.md)
- **Core vs. Extensions decision guide**: {ref}`Core Fields vs. Extensions <core-fields-vs-extensions>`
- **Schema validation details**: {ref}`Metadata Validation <metadata-validation>`
- **Common validation issues**: {ref}`Best Practices <best-practices>`
- **Metadata helper functions**: {ref}`Helper Functions <metadata-helper-functions>`

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
- [Extractors Overview](../user_guide/extractors.md) - Understanding the extraction system
- [NexusLIMS Internal Schema](nexuslims_internal_schema.md) - Understanding Pydantic schemas
- {ref}`Helper Functions <metadata-helper-functions>` - Using `add_to_extensions()` and `emg_field()`
- API Reference: {class}`nexusLIMS.extractors.base.InstrumentProfile`
- API Reference: {class}`nexusLIMS.extractors.profiles.InstrumentProfileRegistry`
