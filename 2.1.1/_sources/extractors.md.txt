(extractors)=
# Extractors

NexusLIMS extracts metadata from various electron microscopy file formats
to create comprehensive experimental records. This page documents the
supported file types, extraction capabilities, and level of support for
each format.

## Quick Reference

| **Extension** | **Support** | **Instrument/Software** | **Data Types** | **Key Features** |
|---------------|-------------|-------------------------|----------------|------------------|
| .dm3, .dm4 | ✅ Full | Gatan DigitalMicrograph | TEM/STEM Imaging, EELS, EDS, Diffraction, Spectrum Imaging | Comprehensive metadata, instrument-specific parsers, automatic type detection |
| .tif | ✅ Full | FEI/Thermo Fisher SEM/FIB | SEM Imaging | Beam settings, stage position, vacuum conditions, detector config |
| .ser, .emi | ✅ Full | FEI TIA Software | TEM/STEM Imaging, Diffraction, EELS/EDS Spectra & SI | Multi-file support, experimental conditions, acquisition parameters |
| .spc | ✅ Full | EDAX (Genesis, TEAM) | EDS Spectrum | Detector angles, energy calibration, element identification |
| .msa | ✅ Full | EDAX & others (standard) | EDS Spectrum | EMSA/MAS standard format, vendor extensions supported |
| .png, .jpg, .tiff, .bmp, .gif | ⚠️ Preview | Various (exported images) | Unknown | Basic metadata, square thumbnail generation |
| .txt | ⚠️ Preview | Various (logs, notes) | Unknown | Basic metadata, text-to-image preview |
| *others* | ❌ Minimal | N/A | Unknown | Timestamp only, placeholder preview |

**Legend**: ✅ Full = Comprehensive metadata extraction<br/>⚠️ Preview = Basic metadata + custom preview<br/>❌ Minimal = Timestamp only

## Overview

The extraction system consists of two main components:

1. **Full Metadata Extractors**: Parse comprehensive metadata from supported file formats
2. **Preview Generators**: Create thumbnail images for visualization

Extraction is performed automatically during record building. Each file is identified by its extension, processed by the appropriate extractor, and both metadata (saved as JSON) and preview images (saved as PNG thumbnails) are generated in parallel to the original data files.

## Fully Supported Formats

These formats have dedicated extractors that parse comprehensive metadata specific to their structure.

### Digital Micrograph Files (.dm3, .dm4)

**Support Level**: ✅ Full

**Description**: Files saved by Gatan's DigitalMicrograph (GMS) software, commonly used for TEM/STEM imaging, EELS, and EDS data.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.digital_micrograph`

**Key Metadata Extracted**:

- Microscope information (voltage, magnification, mode, illumination mode)
- Stage position (X, Y, Z, α, β coordinates)
- Acquisition device and camera settings (binning, exposure time)
- Image processing settings
- EELS spectrometer settings (if applicable)

  - Acquisition parameters (exposure, integration time, number of frames)
  - Experimental conditions (collection/convergence angles)
  - Spectrometer configuration (dispersion, energy loss, slit settings)
  - Processing information

- EDS detector information (if applicable)

  - Acquisition settings (dwell time, dispersion, energy range)
  - Detector configuration (angles, window type, solid angle)
  - Live/real time and count rates

- Spectrum imaging parameters (if applicable)

  - Pixel time, scan mode, spatial sampling
  - Drift correction settings
  - Acquisition duration

**Instrument-Specific Parsing**:

The extractor includes specialized parsers for specific instruments:

- **FEI Titan STEM** (`FEI-Titan-STEM`): Custom handling for EFTEM diffraction mode detection
- **FEI Titan TEM** (`FEI-Titan-TEM`): Parses Tecnai metadata tags including gun settings, lens strengths, apertures, filter settings, and stage positions
- **JEOL JEM 3010** (`JEOL-JEM-TEM`): Basic parsing with filename-based diffraction pattern detection

**Data Types Detected**:

- TEM/STEM Imaging
- TEM/STEM Diffraction
- TEM/STEM EELS (Spectrum)
- TEM/STEM EDS (Spectrum)
- EELS/EDS Spectrum Imaging

**Notes**:

- Automatically detects dataset type based on metadata (Image, Spectrum, SpectrumImage, Diffraction)
- For stacked images, metadata is extracted from the first plane
- Session info (Operator, Specimen, Detector) may be unreliable and is flagged in warnings

### FEI/Thermo Fisher TIF Files (.tif)

**Support Level**: ✅ Full

**Description**: TIFF images saved by FEI/Thermo Fisher FIB and SEM instruments (Quanta, Helios, etc.) with embedded metadata.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.quanta_tif`

**Key Metadata Extracted**:

- Beam settings (voltage, emission current, spot size, field widths, working distance)
- Beam positioning (beam shift, tilt, scan rotation)
- Stage position (X, Y, Z, R, α, tilt angles)
- Scan parameters (dwell time, frame time, pixel size, field of view)
- Detector configuration (name, brightness, contrast, signal type, grid voltage)
- System information (software version, chamber type, column type, vacuum pump)
- Vacuum conditions (mode, chamber pressure)
- Image settings (drift correction, frame integration, magnification mode)
- Acquisition date and time
- Specimen temperature (if available)
- User/operator information

**Special Features**:

- Handles both config-style and XML metadata sections
- Supports MultiGIS gas injection system metadata
- Converts units to display-friendly formats (e.g., SI to μm, μA, etc.)
- Automatic detection and parsing of tilt correction settings

**Data Types Detected**:

- SEM Imaging

**Preview Generation**:

- Uses 2× downsampling for efficient thumbnail creation

**Notes**:

- User/operator metadata is flagged as potentially unreliable (users may remain logged in)
- Some instruments write duplicate metadata sections which are handled automatically
- Works with both older config-style metadata and newer XML-based metadata

### FEI TIA Files (.ser, .emi)

**Support Level**: ✅ Full

**Description**: Files saved by FEI's TIA (Tecnai Imaging and Analysis) software. Data is stored in `.ser` files with accompanying `.emi` metadata files.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.fei_emi`

**File Relationship**:

- Each `.emi` file can reference multiple `.ser` data files (named as `basename_1.ser`, `basename_2.ser`, etc.)
- Both files are required for complete metadata extraction
- The extractor automatically locates the corresponding `.emi` file for a given `.ser` file

**Key Metadata Extracted**:

- Manufacturer and acquisition date
- Microscope accelerating voltage and tilt settings
- Acquisition mode and beam position
- Camera settings (name, binning, dwell time, frame time)
- Detector configuration (energy resolution, integration time)
- Scan parameters (area, drift correction, spectra count)
- Experimental conditions from TIA software

**Data Types Detected**:

- TEM/STEM Imaging
- TEM/STEM Diffraction
- EELS/EDS Spectrum and Spectrum Imaging

**Type Detection Logic**:

- Uses `Mode` metadata field (if present) to distinguish TEM/STEM and Image/Diffraction
- Signal dimension determines Image vs. Spectrum
- Navigation dimension presence indicates Spectrum Imaging
- Heuristic analysis of axis values used to distinguish EELS vs. EDS when not explicitly labeled

**Notes**:

- If `.emi` file is missing, extractor falls back to `.ser` file only (limited metadata)
- Multiple signals in one `.emi` file are handled; metadata is extracted from the appropriate index
- Later signals in a multi-file series may have less metadata than the first

### EDAX EDS Files (.spc, .msa)

**Support Level**: ✅ Full

**Description**: EDS spectrum files saved by EDAX software (Genesis, TEAM, etc.) in proprietary (`.spc`) or standard EMSA (`.msa`) format.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.edax`

#### .spc Files

**Key Metadata Extracted**:

- Azimuthal and elevation angles
- Live time
- Detector energy resolution
- Accelerating voltage
- Channel size and energy range
- Number of spectrum channels
- Stage tilt
- Identified elements

**Data Types Detected**:

- EDS Spectrum

#### .msa Files

**Description**: MSA (EMSA/MAS) format is a standard spectral data format. See the [Microscopy Society of America specification](https://www.microscopy.org/resources/scientific_data/).

**Key Metadata Extracted**:

- All standard MSA fields (version, format, data dimensions)
- EDAX-specific extensions (angles, times, resolutions)
- Analyzer and detector configuration
- User-selected elements
- Amplifier settings
- FPGA version
- Originating file information
- Comments and title

**Data Types Detected**:

- EDS Spectrum

**Notes**:

- `.msa` files are vendor-agnostic and may be exported from various EDS software
- EDAX adds custom fields beyond the MSA standard
- Both formats are single-spectrum only (not spectrum images)

## Partially Supported Formats

These formats receive basic metadata extraction and custom preview generation, but do not have dedicated metadata parsers.

### Image Formats

**Support Level**: ⚠️ Preview Only

**Formats**: `.png`, `.tiff`, `.bmp`, `.gif`, `.jpg`, `.jpeg`

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.basic_metadata`

**Preview Generator**: {py:mod}`nexusLIMS.extractors.plugins.preview_generators.image_preview`

**Metadata Extracted**:

- File creation/modification time
- Instrument ID (inferred from file path)

**Preview Generation**:

- Converts image to square thumbnail (500×500 px default)
- Maintains aspect ratio with padding

**Notes**:

- These are typically auxiliary files (screenshots, exported images, etc.)
- Marked as `DatasetType: Unknown` in records

### Text Files (.txt)

**Support Level**: ⚠️ Preview Only

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.basic_metadata`

**Preview Generator**: {py:mod}`nexusLIMS.extractors.plugins.preview_generators.text_preview`

**Metadata Extracted**:

- File creation/modification time
- Instrument ID (inferred from file path)

**Preview Generation**:

- Renders first ~20 lines of text as image thumbnail
- Uses monospace font for readability

**Notes**:

- Common for log files, notes, and exported data
- Marked as `DatasetType: Unknown` in records

## Unsupported Formats

**Support Level**: ❌ Minimal

Files with extensions not in the above lists receive minimal processing:

**Metadata Extracted**:

- File creation/modification time only
- Marked as `DatasetType: Unknown` and `Data Type: Unknown`

**Preview Generation**:

- A placeholder image is used indicating extraction failed

**Handling Strategy**:

The system's behavior for unsupported files depends on the `NEXUSLIMS_FILE_STRATEGY` environment variable:

- `exclusive` (default): Only files with full extractors are included in records
- `inclusive`: All files are included, with basic metadata for unsupported types

## How Extraction Works

### File Discovery and Strategy

During record building, NexusLIMS finds files within the session time window using the configured strategy:

```bash
# Only include files with dedicated extractors
NEXUSLIMS_FILE_STRATEGY=exclusive

# Include all files found
NEXUSLIMS_FILE_STRATEGY=inclusive
```

### Extraction Process

For each discovered file:

1. **Extension Detection**: File extension is checked against `extension_reader_map`
2. **Extractor Selection**:

   - If extension is in `extension_reader_map`: Use dedicated extractor
   - If extension is in `unextracted_preview_map`: Use basic metadata + custom preview
   - Otherwise: Use basic metadata + placeholder preview (if `inclusive` mode)

3. **Metadata Parsing**: Extractor reads the file and returns a dictionary with:

   - `nx_meta`: NexusLIMS-specific metadata (standardized keys)
   - Additional keys: Format-specific "raw" metadata

4. **Metadata Writing**: JSON file is written to parallel path in `NX_DATA_PATH`

   - Path: `{NX_DATA_PATH}/{instrument}/{path/to/file}.json`

5. **Preview Generation**: Thumbnail PNG is created

   - Path: `{NX_DATA_PATH}/{instrument}/{path/to/file}.thumb.png`
   - Size: 500×500 px (default)

### Expected Metadata Structure

All extractors return a dictionary with this structure:

```python
{
    "nx_meta": {
        "Creation Time": "ISO 8601 timestamp",
        "Data Type": "Category_Modality_Technique",  # e.g., "STEM_EDS"
        "DatasetType": "Image|Spectrum|SpectrumImage|Diffraction|Misc|Unknown",
        "Data Dimensions": "(height, width)" or "(channels,)",
        "Instrument ID": "instrument-name",
        "warnings": [["field1"], ["field2", "subfield"]],  # Unreliable fields
        # ... format-specific keys ...
    },
    # Additional format-specific metadata sections
    "ImageList": { ... },  # Example: DM3/DM4 files
    "ObjectInfo": { ... },  # Example: FEI .ser/.emi files
    # etc.
}
```

The `nx_meta` section contains standardized, human-readable metadata that is displayed in the experimental record. The additional sections contain the complete "raw" metadata tree for reference.

## Adding Support for New Formats

See {doc}`writing_extractor_plugins` for instructions on how to write a new extractor.

## API Reference

For complete API documentation of the extractor modules, see:

- {py:mod}`nexusLIMS.extractors` - Main extractor module
- {py:mod}`nexusLIMS.extractors.plugins.digital_micrograph` - DM3/DM4 file extractor
- {py:mod}`nexusLIMS.extractors.plugins.quanta_tif` - FEI/Thermo TIF file extractor
- {py:mod}`nexusLIMS.extractors.plugins.fei_emi` - FEI TIA .ser/.emi file extractor
- {py:mod}`nexusLIMS.extractors.plugins.edax` - EDAX .spc/.msa file extractor
- {py:mod}`nexusLIMS.extractors.plugins.basic_metadata` - Basic metadata fallback extractor
- {py:mod}`nexusLIMS.extractors.plugins.preview_generators` - Preview image generation utilities

## Further Reading

- {ref}`record-building` - How extractors fit into the record building workflow
- {doc}`taxonomy` - Data type classification and taxonomy
- {py:mod}`nexusLIMS.extractors` - Complete API documentation
