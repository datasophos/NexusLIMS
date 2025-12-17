# Implementation Plan: Zeiss Orion/Fibics TIFF Extractor Plugin

## Overview
Add support for extracting metadata from Zeiss Orion and Fibics helium ion microscope (HIM) TIFF files with embedded XML metadata.

## Metadata Format Analysis

### Fibics Format
- **TIFF Tag**: 51023 (custom tag)
- **XML Root**: `<Fibics>`
- **Software Tag** (305): "Fibics NPVE 4.5.0.664"
- **Structure**: Application, Image, Scan, Stage, BeamInfo, DetectorInfo sections
- **Key Fields**: Beam="Orion", Dwell time, FOV, Stage positions, Detector settings

### Zeiss Format
- **TIFF Tag**: 65000 (custom tag)
- **XML Root**: `<ImageTags>`
- **Structure**: Flat XML with Value/Units pairs for each parameter
- **Key Fields**: AccelerationVoltage, BeamCurrent, WorkingDistance, DwellTime, Stage positions
- **System**: Model="NanoFab", ColumnType="GFIS", IonGas="Helium"

## Implementation Strategy

### 1. File Structure
**Create**: `nexusLIMS/extractors/plugins/zeiss_orion_fibics_tif.py`

### 2. Plugin Class Design
```python
class OrionFibicsTiffExtractor:
    name = "orion_fibics_tif_extractor"
    priority = 150  # Higher than Quanta (100) to handle Orion TIFFs first

    def supports(self, context: ExtractionContext) -> bool:
        # Check file extension + content sniffing for Zeiss/Fibics markers

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        # Main extraction logic with error handling
```

**Priority Rationale**: Use 150 (high priority) to ensure this extractor is tried before the generic QuantaTiffExtractor for TIFF files. The `supports()` method will use content sniffing to only claim Zeiss/Fibics files.

### 3. Detection Strategy (`supports()` method)

Check three conditions:
1. File extension is `.tif` or `.tiff`
2. File can be opened as valid TIFF
3. Contains Zeiss OR Fibics markers:
   - Zeiss: TIFF tag 65000 contains XML starting with `<ImageTags>`
   - Fibics: TIFF tag 51023 contains XML starting with `<Fibics>`

### 4. Extraction Approach

**Use PIL/Pillow for TIFF tag extraction**:
```python
from PIL import Image
image = Image.open(file_path)
xml_data = image.tag_v2.get(65000) or image.tag_v2.get(51023)
```

**Parse XML metadata**:
```python
import xml.etree.ElementTree as ET
root = ET.fromstring(xml_data)
```

**Two parsing branches**:
- **Zeiss**: Parse `<ImageTags>` format (Value/Units structure)
- **Fibics**: Parse `<Fibics>` format (nested sections)

### 5. Metadata Mapping

#### Required nx_meta Fields:
- **DatasetType**: "Image" (all HIM images)
- **Data Type**: "HIM_Imaging" or "Helium_Ion_Imaging"
- **Creation Time**: From TIFF tag 306 or XML TimeStamp field
- **Instrument ID**: From context.instrument
- **Data Dimensions**: From image.size or XML ImageWidth/Height

#### Zeiss-Specific Mapping:
```
AccelerationVoltage → Voltage (kV)
GFIS.BeamCurrent → Beam Current (pA)
DwellTime → Pixel Dwell Time (μs)
ImageWidth/ImageHeight → Data Dimensions
WorkingDistance → Working Distance (mm)
StageX/Y/Z/Tilt/Rotate → Stage Position
DetectorName → Detector Name
Fov → Field of View (μm)
StigmationX/Y → Stigmator settings
TimeStamp → Acquisition Date/Time
```

#### Fibics-Specific Mapping:
```
BeamInfo[1] → Voltage (kV) [convert from V]
BeamInfo[0] → Beam Current (pA)
Scan.Dwell → Pixel Dwell Time (μs) [convert from ns if needed]
Image.Width/Height → Data Dimensions
Stage.X/Y/Z/Tilt/Rot → Stage Position
Detector → Detector Name
Scan.FOV_X → Field of View (μm)
Scan.StigX/StigY → Stigmator settings
Application.Date → Creation Time
```

### 6. Helper Functions

Create these internal functions:
- `_detect_variant(image)`: Returns "zeiss" or "fibics" or None
- `_extract_zeiss_metadata(xml_root, image, file_path)`: Parse Zeiss XML
- `_extract_fibics_metadata(xml_root, image, file_path)`: Parse Fibics XML
- `_parse_zeiss_value(value_text, units_text)`: Convert string values with units
- `_set_base_metadata(mdict, file_path, instrument)`: Set common nx_meta fields

### 7. Error Handling

**Defensive approach**:
- Wrap entire extract() in try/except
- On error, fall back to BasicFileInfoExtractor
- Add warning to nx_meta["warnings"]
- Never raise exceptions from extract()
- Log errors for debugging

### 8. Testing Strategy

**Create**: `tests/unit/test_extractors/test_zeiss_orion_fibics.py`

#### Test Files (already exist):
- `tests/unit/files/orion-zeiss_dataZeroed.tif`
- `tests/unit/files/orion-fibics_dataZeroed.tif` (needs to be compressed to .tar.gz)

#### Test Classes:
```python
class TestOrionFibicsTiffExtractor:
    # Plugin interface tests
    def test_supports_zeiss_tif()
    def test_supports_fibics_tif()
    def test_does_not_support_quanta_tif()
    def test_has_required_attributes()

    # Extraction tests
    def test_extract_zeiss_metadata()
    def test_extract_fibics_metadata()
    def test_zeiss_voltage_extraction()
    def test_fibics_beam_current()
    def test_stage_position_parsing()
    def test_handles_missing_fields_gracefully()

    # Error handling tests
    def test_handles_corrupted_xml()
    def test_falls_back_on_error()
```

#### Specific Assertions (based on sample files):
**Zeiss file**:
- Voltage: 29.997 kV (from 29997 V)
- Beam current: 0.938 pA
- Working distance: 11.977 mm
- Detector: "ETDetector"
- Dwell time: 0.5 μs
- Image size: 1024x1024
- Ion gas: "Helium"
- Data Type: "HIM_Imaging"

**Fibics file**:
- Beam: "Orion"
- Dwell: 10.0 μs (from 10000 ns)
- FOV: 2.5 μm
- Detector: "ET"
- Image size: 2048x2048
- Software: "NPVE v4.5"
- Data Type: "HIM_Imaging"

### 9. Changelog Entry

**Create**: `docs/changes/<pr-number>.feature.rst`

Content:
```rst
Added :py:class:`~nexusLIMS.extractors.plugins.zeiss_orion_fibics_tif.OrionFibicsTiffExtractor`
plugin to extract metadata from Zeiss Orion and Fibics helium ion microscope TIFF files.
```

## Implementation Steps

1. **Create extractor plugin file** (`zeiss_orion_fibics_tif.py`):
   - Import required libraries (PIL, xml.etree, logging, etc.)
   - Define OrionFibicsTiffExtractor class
   - Implement supports() with content sniffing
   - Implement extract() with variant detection
   - Create helper functions for parsing

2. **Implement Zeiss metadata parser**:
   - Parse `<ImageTags>` XML structure
   - Extract Value/Units pairs
   - Map to nx_meta fields
   - Handle unit conversions (V to kV, etc.)

3. **Implement Fibics metadata parser**:
   - Parse `<Fibics>` XML structure
   - Navigate nested sections
   - Extract BeamInfo array values
   - Map to nx_meta fields

4. **Add error handling**:
   - Try/except around all parsing
   - Fallback to BasicFileInfoExtractor
   - Logging for debugging

5. **Create comprehensive tests**:
   - Test file in `tests/unit/test_extractors/`
   - Use pytest fixtures for sample files
   - Test both variants thoroughly
   - Aim for 100% coverage

6. **Run linting and formatting**:
   ```bash
   ./scripts/run_lint.sh
   uv run ruff format .
   ```

7. **Run tests**:
   ```bash
   ./scripts/run_tests.sh
   # Or specific test:
   uv run pytest --mpl --mpl-baseline-path=tests/files/figs tests/unit/test_extractors/test_zeiss_orion_fibics.py -v
   ```

8. **Create changelog entry**:
   - Add feature note in `docs/changes/`

## Critical Files

### To Create:
- `nexusLIMS/extractors/plugins/zeiss_orion_fibics_tif.py` (main extractor)
- `tests/unit/test_extractors/test_zeiss_orion_fibics.py` (tests)
- `docs/changes/<pr-number>.feature.rst` (changelog)

### To Reference:
- `nexusLIMS/extractors/base.py` (interfaces)
- `nexusLIMS/extractors/plugins/quanta_tif.py` (pattern reference)
- `nexusLIMS/extractors/plugins/digital_micrograph.py` (parsing patterns)
- `tests/unit/test_extractors/test_plugins.py` (test patterns)

## Key Design Decisions

1. **Use PIL/Pillow for TIFF tag access** (not binary parsing like Quanta extractor)
   - Rationale: Metadata is in standard TIFF tags with XML, not appended text

2. **Priority 150** (higher than QuantaTiffExtractor's 100)
   - Rationale: Ensures Orion/Fibics files are checked first, with content sniffing preventing false matches

3. **Two separate parsing functions** for Zeiss vs Fibics
   - Rationale: XML structures are significantly different; cleaner to separate

4. **Common Data Type: "HIM_Imaging"**
   - Rationale: Both are helium ion microscopy imaging, consistent naming

5. **Defensive error handling throughout**
   - Rationale: Real-world files may have variations; graceful degradation better than crashes

## Success Criteria
- ✓ Plugin auto-discovered by registry
- ✓ Correctly identifies Zeiss and Fibics TIFF files
- ✓ Extracts all required metadata fields
- ✓ Handles both variants appropriately
- ✓ All tests pass with 100% coverage
- ✓ Passes linting checks
- ✓ NumPy-style docstrings throughout
- ✓ Comprehensive test coverage including error cases
