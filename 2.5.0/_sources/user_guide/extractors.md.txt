(extractors)=
# Extractors

NexusLIMS extracts metadata from various electron microscopy file formats
to create comprehensive experimental records. This page documents the
supported file types, extraction capabilities, and level of support for
each format.

## Quick Reference

| **Instrument/Software** | **Extension** | **Support** | **Data Types** | **Key Features** |
|-------------------------|---------------|-------------|----------------|------------------|
| [Gatan DigitalMicrograph](#digital-micrograph-files-dm3-dm4) | .dm3, .dm4 | ✅ Full | TEM/STEM Imaging, EELS, EDS, Diffraction, Spectrum Imaging | Comprehensive metadata, instrument-specific parsers, automatic type detection |
| [FEI/Thermo Fisher SEM/FIB](#feithermo-fisher-tif-files-tif) | .tif | ✅ Full | SEM Imaging | Beam settings, stage position, vacuum conditions, detector config |
| [Zeiss Orion HIM / Fibics HIM](#zeiss-orion-fibics-him-tif-files-tif) | .tif | ✅ Full | SEM/HIM Imaging | Helium ion beam settings, stage position, detector configuration, image metadata |
| [Tescan (P)FIB/SEM](#tescan-pfibsem-tif-files-tif) | .tif | ✅ Full | SEM Imaging | High-voltage settings, stage position, detector gain/offset, scan parameters, stigmator values |
| [FEI TIA Software](#fei-tia-files-ser-emi) | .ser, .emi | ✅ Full | TEM/STEM Imaging, Diffraction, EELS/EDS Spectra & SI | Multi-file support, experimental conditions, acquisition parameters |
| [EDAX (Genesis, TEAM)](#edax-eds-files-spc-msa) | .spc | ✅ Full | EDS Spectrum | Detector angles, energy calibration, element identification |
| [EDAX & others (standard)](#edax-eds-files-spc-msa) | .msa | ✅ Full | EDS Spectrum | EMSA/MAS standard format, vendor extensions supported |
| [Various (exported images)](#image-formats) | .png, .jpg, .tiff, .bmp, .gif | ⚠️ Preview | Unknown | Basic metadata, square thumbnail generation |
| [Various (logs, notes)](#text-files-txt) | .txt | ⚠️ Preview | Unknown | Basic metadata, text-to-image preview |
| [Unknown Files](#unknown-files) | *others* | ❌ Minimal | Unknown | Timestamp only, placeholder preview |

**Legend**: ✅ Full = Comprehensive metadata extraction<br/>⚠️ Preview = Basic metadata + custom preview<br/>❌ Minimal = Timestamp only

## Overview

The extraction system uses a **plugin-based architecture** for flexible and extensible metadata extraction. The system consists of three main components:

1. **Extractor Plugins**: Parse comprehensive metadata from supported file formats
2. **Preview Generator Plugins**: Create thumbnail images for visualization  
3. **Extractor Registry**: Manages plugin discovery, selection, and execution

### Plugin Architecture

The plugin system provides:

- **Auto-discovery**: Plugins are automatically discovered from `nexusLIMS/extractors/plugins/`
- **Priority-based selection**: Multiple extractors can support the same file type, with higher priority extractors preferred
- **Content sniffing**: Extractors can examine file contents beyond just extensions
- **Multi-signal support**: Files containing multiple datasets (e.g., DM3/DM4) are automatically expanded
- **Defensive design**: All extractors implement robust error handling with graceful fallbacks

Extraction is performed automatically during record building. Each file is processed by the best available extractor, and both metadata (saved as JSON) and preview images (saved as PNG thumbnails) are generated in parallel to the original data files.

## Fully Supported Formats

These formats have dedicated extractors that parse comprehensive metadata specific to their structure.

(digital-micrograph-files-dm3-dm4)=  
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

(feithermo-fisher-tif-files-tif)=  
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

(zeiss-orion-fibics-him-tif-files-tif)=  
### Zeiss Orion / Fibics HIM TIF Files (.tif)

**Support Level**: ✅ Full

**Description**: TIFF images saved by Zeiss Orion and Fibics helium ion microscope (HIM) systems with embedded XML metadata in custom TIFF tags.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.orion_HIM_tif`

**File Format Details**:

The extractor uses content sniffing to detect HIM TIFF files by checking for custom TIFF tags:
- **Zeiss Orion**: TIFF tag 65000 contains `<ImageTags>` XML metadata
- **Fibics**: TIFF tag 51023 contains `<Fibics>` XML metadata

This content-based detection allows proper identification even when files use `.tif` extension (used by multiple instruments).

**Key Metadata Extracted**:

**Zeiss Orion Variant**:
- Helium ion beam settings (energy, current, spot size, aperture)
- Beam positioning (shift, scan rotation)
- Stage position (X, Y, Z, R, tilt)
- Scan parameters (dwell time, frame time, pixel size, resolution)
- Detector configuration (type, brightness, contrast)
- System information (vacuum pressure, chamber type)
- Image acquisition parameters (line averaging, digital gain, overlay settings)
- Scan speed and resolution settings

**Fibics Variant**:
- Helium ion beam parameters (energy, current, spot settings)
- Stage coordinates and angles
- Scan configuration (pixel dwell, acquisition time, resolution)
- Detector settings and signal type
- Image optimization parameters (contrast, brightness)
- Data collection timestamps

**Data Types Detected**:

- HIM Imaging

**Special Features**:

- Content-based detection to differentiate from other TIFF formats (FEI, standard image files)
- Priority 150 - checked before generic TIFF extractors to properly identify HIM files
- Handles both Zeiss and Fibics XML metadata formats
- Robust error handling for malformed or missing XML metadata
- Supports .tif and .tiff extensions

**Preview Generation**:

- Converts image to square thumbnail (500×500 px default)
- Maintains aspect ratio with padding

**Notes**:

- The extractor uses content sniffing rather than extension alone, ensuring correct identification even if .tif files from multiple instruments are present
- If XML metadata is missing or corrupted, the extractor gracefully falls back to basic file information
- Both Zeiss Orion and Fibics HIM variants store metadata as embedded XML, making extraction reliable across different software versions

(tescan-pfibsem-tif-files-tif)=  
### Tescan PFIB/SEM TIF Files (.tif)

**Support Level**: ✅ Full

**Description**: TIFF images saved by Tescan PFIB (Focused Ion Beam) and SEM instruments (e.g., AMBER X) with embedded INI-style metadata in custom TIFF tags or sidecar .hdr files.

**Extractor Module**: {py:mod}`nexusLIMS.extractors.plugins.tescan_tif`

**File Format Details**:

The extractor uses a three-tier strategy for metadata extraction:

1. **Primary**: Extracts metadata from embedded TIFF tag 50431 (custom Tescan metadata tag) containing INI-style metadata
2. **Fallback**: If embedded metadata fails or is incomplete, looks for a sidecar `.hdr` file with full metadata in INI format (`[MAIN]` and `[SEM]` sections)
3. **Supplementary**: Always extracts basic TIFF tags (tag 271 for Make, tag 305 for Software, tag 315 for Artist) to supplement or override other metadata

This multi-tier approach ensures complete metadata is available whether metadata is embedded in the TIFF or stored in a sidecar `.hdr` file.

**Key Metadata Extracted**:

**From [MAIN] section**:
- Instrument identification (Device, Model, Serial Number)
- User information (Operator name)
- Acquisition timestamp (Date and Time)
- Magnification
- Software version

**From [SEM] section**:
- Beam parameters (High Voltage, Spot Size, Emission Current)
- Stage position (X, Y, Z coordinates and Rotation/Tilt angles)
- Scan settings (Dwell time, Scan mode, Rotation)
- Detector configuration (Name, Gain, Offset)
- Vacuum conditions (Chamber pressure)
- Stigmator values (X and Y corrections)
- Gun type configuration
- Working Distance
- Session ID for traceability

**Unit Conversions**:
- Magnification: Converted from raw values to kiloX (kX)
- Voltages: Converted from millivolts to kilovolts (kV)
- Distances: Converted from meters to millimeters (mm) or nanometers (nm) as appropriate
- Currents: Converted from amperes to microamperes (μA)
- Pressure: Converted to millipascals (mPa)
- Pixel sizes: Calculated from image dimensions and field of view, converted to nanometers (nm)

**Data Types Detected**:

- SEM Imaging

**Special Features**:

- Priority 150 - Checked before generic TIFF extractors to properly identify Tescan files
- Content-based detection via custom TIFF tags even if `.hdr` file is missing
- Comprehensive stage position tracking (X, Y, Z, Rotation, Tilt)
- Detector settings extraction (Gain and Offset values)
- Automatic conversion of physics units to display-friendly formats
- Empty field exclusion - Fields with empty values are not included in output
- Session tracking with unique Session ID

**Preview Generation**:

- Converts image to square thumbnail (500×500 px default)
- Maintains aspect ratio with padding

**Warnings**:

The extractor flags the following fields as potentially unreliable:
- **Operator**: May reflect a logged-in user rather than the actual operator who collected the data

**Compatibility Notes**:

- **Tescan AMBER X**: Fully tested and verified
- **Other Tescan SEM/PFIB Instruments**: Likely compatible due to consistent INI metadata format, but not yet tested
- Both `.tif` and `.tiff` extensions are supported

**Notes**:

- If `.hdr` file is present but cannot be read, the extractor falls back to embedded TIFF tag metadata
- If both sidecar and embedded metadata are available, the sidecar is preferred (more reliable)
- The extractor gracefully handles missing or incomplete metadata sections
- Pixel size is calculated from magnification and field width when not directly available

(fei-tia-files-ser-emi)=  
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

(edax-eds-files-spc-msa)=  
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

(image-formats)=  
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

(text-files-txt)=  
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

(unknown-files)=
## Unsupported Formats

**Support Level**: ❌ Minimal

Files with extensions not in the above lists receive minimal processing:

**Metadata Extracted**:

- File creation/modification time only
- Marked as `DatasetType: Unknown` and `Data Type: Unknown`

**Preview Generation**:

- A placeholder image is used indicating extraction failed

**Handling Strategy**:

The system's behavior for unsupported files depends on the `NX_FILE_STRATEGY` environment variable:

- `exclusive` (default): Only files with full extractors are included in records
- `inclusive`: All files are included, with basic metadata for unsupported types

## How Extraction Works

### File Discovery and Strategy

During record building, NexusLIMS finds files within the session time window using the configured strategy:

```bash
# Only include files with dedicated extractors
NX_FILE_STRATEGY=exclusive

# Include all files found
NX_FILE_STRATEGY=inclusive
```

### Extraction Process

For each discovered file:

1. **Plugin Discovery**: The extractor registry auto-discovers all available extractor plugins from `nexusLIMS/extractors/plugins/`

2. **Extractor Selection**:

   - The registry uses priority-based selection with content sniffing support
   - Extractors are tried in descending priority order (higher priority first)
   - Each extractor's `supports()` method is called to determine compatibility
   - If no specialized extractor matches, the `BasicFileInfoExtractor` fallback is used

3. **Metadata Parsing**: The selected extractor reads the file and returns a **list** of metadata dictionaries:

   - Each dictionary contains `nx_meta` with NexusLIMS-specific metadata (standardized keys)
   - Additional keys contain format-specific "raw" metadata
   - For multi-signal files, the list contains one entry per signal
   - For single-signal files, the list contains one entry for consistency

4. **Metadata Writing**: JSON file(s) are written to parallel path in `NX_DATA_PATH`

   - Path: `{NX_DATA_PATH}/{instrument}/{path/to/file}.json`
   - For multi-signal files: Multiple JSON files with `_signalN` suffixes

5. **Preview Generation**: Thumbnail PNG(s) are created

   - Path: `{NX_DATA_PATH}/{instrument}/{path/to/file}.thumb.png`
   - For multi-signal files: Multiple previews with `_signalN.thumb.png` suffixes
   - Size: 500×500 px (default)
   - Uses plugin-based preview generators with fallback to legacy methods

### Expected Metadata Structure

All extractors return a **list of metadata dictionaries**, with one entry per signal or dataset:

```python
[
    {
        "nx_meta": {
            "Creation Time": "ISO 8601 timestamp with timezone",
            "Data Type": "Category_Modality_Technique",  # e.g., "STEM_EDS"
            "DatasetType": "Image|Spectrum|SpectrumImage|Diffraction|Misc|Unknown",
            "Data Dimensions": "(height, width)" or "(channels,)",  # Optional
            "Instrument ID": "instrument-name",  # Optional
            "warnings": ["field1", ["field2"]],  # Optional, list of field names flagged as unreliable
            # ... format-specific keys ...
        },
        # Additional format-specific metadata sections
        "ImageList": { ... },  # Example: DM3/DM4 files
        "ObjectInfo": { ... },  # Example: FEI .ser/.emi files
        # etc.
    },
    # For multi-signal files, additional entries follow the same structure
    {
        "nx_meta": { ... },
        # ... additional signal ...
    }
]
```

**Return Format:**
- **Single-signal files**: Return a list with one element `[{...}]`
- **Multi-signal files**: Return a list with multiple elements, one per signal `[{...}, {...}]`

**Validation Using Pydantic Models (New in v2.2.0 - Work in Progress):**

The `nx_meta` section is validated against Pydantic schemas to improve data consistency and quality. Starting with v2.2.0, NexusLIMS provides basic metadata validation with EM Glossary integration and unit standardization. This validation system is still evolving as standardization efforts progress.

**Schema Selection by DatasetType:**

The validation schema is chosen automatically based on the `DatasetType` field:

| **DatasetType** | **Schema** | **Purpose** | **Type-Specific Fields** |
|-----------------|------------|-------------|--------------------------|
| `Image` | {py:class}`~nexusLIMS.schemas.metadata.ImageMetadata` | TEM/SEM/STEM images | `magnification`, `pixel_size`, `working_distance` |
| `Spectrum` | {py:class}`~nexusLIMS.schemas.metadata.SpectrumMetadata` | EELS/EDS spectra | `channel_size`, `starting_energy`, `live_time` |
| `SpectrumImage` | {py:class}`~nexusLIMS.schemas.metadata.SpectrumImageMetadata` | Spectrum imaging | `pixel_time`, `magnification`, `channel_size` |
| `Diffraction` | {py:class}`~nexusLIMS.schemas.metadata.DiffractionMetadata` | Diffraction patterns | `camera_length`, `exposure_time`, `convergence_angle` |
| `Misc` or `Unknown` | {py:class}`~nexusLIMS.schemas.metadata.NexusMetadata` | Other data | Base fields only |

**Common Core Fields (All Schemas):**

All schemas inherit these required fields from {py:class}`nexusLIMS.schemas.metadata.NexusMetadata`:

- **`creation_time`** (datetime with timezone): When the data was acquired
- **`data_type`** (str): Classification string (e.g., `"STEM_Imaging"`, `"TEM_EDS"`)
- **`dataset_type`** (DatasetType enum): One of `Image`, `Spectrum`, `SpectrumImage`, `Diffraction`, `Misc`, `Unknown`

**Optional Core Fields:**

- **`data_dimensions`** (str): Shape of the data (e.g., `"(1024, 1024)"`)
- **`instrument_id`** (str): Identifier of the instrument used
- **`warnings`** (list[str]): Field names flagged as potentially unreliable
- **`extensions`** (dict): Additional vendor/instrument-specific metadata

**EM Glossary Standardized Fields:**

Type-specific schemas include fields standardized against the Electron Microscopy Glossary v2.0 where available. Note that the EM Glossary vocabulary is also still developing, so not all fields have complete standardized definitions yet:

- **Beam parameters**: `acceleration_voltage`, `beam_current`, `emission_current`, `convergence_angle`
- **Stage/Sample**: `stage_x`, `stage_y`, `stage_z`, `tilt_alpha`, `tilt_beta`
- **Detector**: `detector_type`, `detector_angle`, `detector_distance`, `detector_binning`
- **Acquisition**: `dwell_time`, `acquisition_time`, `live_time`, `pixel_time`
- **Optical**: `magnification`, `working_distance`, `camera_length`, `pixel_size_x`, `pixel_size_y`
- **Spectrum**: `channel_size`, `starting_energy`, `takeoff_angle`

These fields are defined using the `emg_field()` helper function, which automatically injects EM Glossary metadata (display names, definitions, URIs) for standardization and interoperability where EMG terms are available.

See {doc}`../dev_guide/em_glossary_reference` for the complete field mapping and {doc}`../dev_guide/nexuslims_internal_schema` for details on the schema system.

**Validation Example:**

When an extractor returns metadata, NexusLIMS automatically validates it:

```python
from datetime import datetime, timezone
from nexusLIMS.schemas.metadata import ImageMetadata
from pint import Quantity

# Valid ImageMetadata that passes validation
nx_meta = {
    "creation_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    "data_type": "STEM_Imaging",
    "dataset_type": "Image",
    "data_dimensions": "(1024, 1024)",
    "instrument_id": "FEI-Titan-TEM-635816",
    "warnings": ["Operator"],  # Flag unreliable fields
    # EM Glossary standardized fields with Pint Quantities
    "acceleration_voltage": Quantity(200, "kV"),
    "magnification": Quantity(50000, "dimensionless"),
    "pixel_size_x": Quantity(2.5, "nm"),
    "working_distance": Quantity(5.2, "mm"),
    # Extensions for vendor-specific or non-standardized data
    "extensions": {
        "detector_brightness": 50.0,
        "scan_rotation": Quantity(45, "degree"),
    },
}
validated = ImageMetadata.model_validate(nx_meta)

# Invalid metadata raises ValidationError with details
bad_meta = {
    "creation_time": datetime(2024, 1, 15, 10, 30, 0),  # ❌ Missing timezone!
    "data_type": "STEM_Imaging",
    "dataset_type": "InvalidType",  # ❌ Not in allowed values!
}
ImageMetadata.model_validate(bad_meta)  # Raises pydantic.ValidationError
```

**Unit Handling:**

NexusLIMS automatically normalizes physical quantities to preferred units:

- Voltages → kilovolts (kV)
- Distances → nanometers (nm) or millimeters (mm) depending on scale
- Times → seconds (s)
- Energies → electron volts (eV)

You can provide quantities in any compatible unit, and validation will convert them automatically:

```python
# These are all equivalent after validation:
{"acceleration_voltage": Quantity(200, "kV")}
{"acceleration_voltage": Quantity(200000, "V")}
{"acceleration_voltage": Quantity(0.2, "MV")}
```

See {doc}`../dev_guide/nexuslims_internal_schema` for complete unit handling details.

The `nx_meta` section in each element contains standardized, human-readable metadata that is displayed in the experimental record. The additional sections contain the complete "raw" metadata tree for reference.

This consistent list-based approach combined with Pydantic validation ensures the Activity layer can automatically and safely expand multi-signal files into multiple datasets in the experimental record.

### Extension Fields in Practice

The `extensions` dictionary provides a flexible way to include vendor-specific or non-standardized metadata that doesn't fit into the core schema fields. Here are real-world examples from NexusLIMS extractors:

**FEI/Thermo Quanta TIF Extractor** ([nexusLIMS/extractors/plugins/quanta_tif.py:428](../../nexusLIMS/extractors/plugins/quanta_tif.py#L428-L447)):

```python
# Vendor-specific vacuum and detector settings
extensions = {
    "chamber_type": "LargeChamber",
    "column_type": "HighResolution",
    "vacuum_mode": "HighVacuum",
    "chamber_pressure": Quantity(5.2e-5, "Pa"),
    "detector_signal": "ETD",
    "detector_grid_voltage": Quantity(300, "V"),
    "drift_correction_enabled": True,
    "frame_integration": 4,
}
```

**Digital Micrograph DM3/DM4 Extractor** ([nexusLIMS/extractors/plugins/digital_micrograph.py:337](../../nexusLIMS/extractors/plugins/digital_micrograph.py#L337-L349)):

```python
# EELS-specific detector and acquisition settings
extensions = {
    "eels_dispersion": Quantity(0.5, "eV/channel"),
    "eels_energy_loss": Quantity(150, "eV"),
    "eels_slit_width": Quantity(2.5, "eV"),
    "eels_collection_angle": Quantity(15, "mrad"),
    "spectrometer_name": "GIF Quantum 965",
    "drift_correction_enabled": True,
}
```

**Tescan TIF Extractor** ([nexusLIMS/extractors/plugins/tescan_tif.py:285](../../nexusLIMS/extractors/plugins/tescan_tif.py#L285-L295)):

```python
# Instrument-specific settings not covered by EM Glossary
extensions = {
    "stigmator_x": Quantity(12.5, "percent"),
    "stigmator_y": Quantity(-8.3, "percent"),
    "gun_type": "Schottky",
    "scan_mode": "FrameIntegration",
    "session_id": "abc123xyz789",
}
```

**When to Use Extensions:**

Use the `extensions` dictionary when:

- **Vendor-specific features**: Settings unique to one manufacturer (e.g., FEI MultiGIS, Gatan GIF)
- **Non-standardized parameters**: Values not yet in EM Glossary (e.g., drift correction flags)
- **Instrument-specific calibrations**: Stigmator values, lens strengths, custom aperture settings
- **Session tracking**: Unique IDs or timestamps for instrument logging
- **Software-specific metadata**: Settings from acquisition software that don't map to standard fields

**Do NOT use extensions for:**

- Standard EM parameters covered by EM Glossary (voltage, magnification, stage position, etc.)
- Required fields (creation_time, data_type, dataset_type)
- Data that should be validated (use core fields for type safety)

See {ref}`Helper Functions <metadata-helper-functions>` for the `add_to_extensions()` helper function and {doc}`../dev_guide/writing_extractor_plugins` for complete guidance on using extensions in your own extractors.

(standalone-extractor-usage)=
## Standalone Library Usage

The NexusLIMS extractor system can be used as a **standalone Python library**
without a full NexusLIMS deployment.  No `.env` file, database, NEMO instance,
or CDCS server is required.  This is useful for:

- Quickly inspecting microscopy file metadata in a Jupyter notebook
- Batch-processing files on a workstation that isn't connected to a NexusLIMS deployment
- Prototyping new analysis workflows that read instrument metadata

### Installation

```bash
pip install nexusLIMS
# or, if using uv:
uv add nexusLIMS
```

No environment variables need to be set for basic extraction.

### Quickstart

```python
from pathlib import Path
from nexusLIMS.extractors import parse_metadata

# Works with no .env, no database, no NEMO / CDCS
metadata_list, _ = parse_metadata(
    Path("my_data.dm3"),
    write_output=False,     # don't try to write a JSON sidecar
    generate_preview=False, # don't try to generate a thumbnail
)

nx = metadata_list[0]["nx_meta"]
print(nx["Creation Time"])       # ISO-8601 timestamp
print(nx["DatasetType"])         # "Image", "Spectrum", etc.
print(nx["Data Type"])           # e.g., "STEM_Imaging"
```

### Default behaviour when called with `write_output=True`

`parse_metadata` defaults to `write_output=True` and `generate_preview=True`
so that the full record-building pipeline works without any code changes.
When NexusLIMS configuration is **not** available those two steps are silently
skipped and a warning is logged:

```
WARNING nexusLIMS.extractors: NexusLIMS config unavailable; skipping metadata
file write (pass write_output=False to suppress this warning)
```

Passing `write_output=False, generate_preview=False` suppresses the warnings
and makes the intent explicit.

### Low-level API

You can also use the extractor registry directly for more control:

```python
from pathlib import Path
from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.registry import get_registry

path = Path("my_data.dm3")
context = ExtractionContext(file_path=path, instrument=None)

registry = get_registry()
extractor = registry.get_extractor(context)

print(f"Selected extractor: {extractor.name}")

metadata_list = extractor.extract(context)
for i, m in enumerate(metadata_list):
    print(f"Signal {i}: {m['nx_meta']['DatasetType']}")
```

### What degrades gracefully

| Feature | Without config | With config |
|---------|---------------|-------------|
| Metadata extraction | ✅ Full | ✅ Full |
| Schema validation | ✅ Full | ✅ Full |
| Instrument identification from DB | ⚠️ Returns `None` | ✅ Looks up DB |
| JSON sidecar write (`write_output`) | ⚠️ Skipped + warning | ✅ Written |
| Preview generation (`generate_preview`) | ⚠️ Skipped + warning | ✅ Generated |
| Local instrument profiles | ⚠️ Skipped (built-in profiles active) | ✅ Loaded |

### Supported formats

All formats listed in the Quick Reference table at the top of this page work
in standalone mode.  The extractor registry auto-discovers plugins on first
use with no configuration needed.

### Example notebook

See {doc}`/notebooks/standalone_extractor_usage` for a complete, runnable
Jupyter notebook that downloads real microscopy test files from the project
repository and walks through both the high-level and low-level APIs, including
the graceful-degradation behaviour when no config is present.

## Adding Support for New Formats

See {doc}`../dev_guide/writing_extractor_plugins` for instructions on how to write a new extractor.

## API Reference

### Extractor Registry Properties

The {py:class}`nexusLIMS.extractors.registry.ExtractorRegistry` class provides convenient properties for querying registered extractors:

**`extractors` Property**
: Returns a dictionary mapping file extensions to lists of extractor classes, sorted by priority (descending). This property automatically triggers plugin discovery if not already performed.

```python
from nexusLIMS.extractors.registry import get_registry

registry = get_registry()
extractors_by_ext = registry.extractors
# Returns: {
#   'dm3': [<class digital_micrograph.DM3Extractor'>], 
#   'dm4': [<class 'digital_micrograph.DM3Extractor'>], 
#   'msa': [<class 'edax.MsaExtractor'>], 
#   'spc': [<class 'edax.SpcExtractor'>], 
#   ... 
# }
```

**`extractor_names` Property**
: Returns a deduplicated, alphabetically-sorted list of all registered extractor class names. Includes both extension-specific and wildcard extractors. This property also triggers auto-discovery if needed.

```python
registry = get_registry()
names = registry.extractor_names
# Returns: ["BasicFileInfoExtractor", "DM3Extractor", ..., "TescanTiffExtractor"]
```

### Extractor Modules

For complete API documentation of the extractor modules, see:

- {py:mod}`nexusLIMS.extractors` - Main extractor module
- {py:mod}`nexusLIMS.extractors.registry` - Extractor registry and auto-discovery
- {py:mod}`nexusLIMS.extractors.plugins.digital_micrograph` - DM3/DM4 file extractor
- {py:mod}`nexusLIMS.extractors.plugins.quanta_tif` - FEI/Thermo TIF file extractor
- {py:mod}`nexusLIMS.extractors.plugins.orion_HIM_tif` - Zeiss Orion / Fibics HIM TIF file extractor
- {py:mod}`nexusLIMS.extractors.plugins.tescan_tif` - Tescan PFIB/SEM TIF file extractor
- {py:mod}`nexusLIMS.extractors.plugins.fei_emi` - FEI TIA .ser/.emi file extractor
- {py:mod}`nexusLIMS.extractors.plugins.edax` - EDAX .spc/.msa file extractor
- {py:mod}`nexusLIMS.extractors.plugins.basic_metadata` - Basic metadata fallback extractor
- {py:mod}`nexusLIMS.extractors.plugins.preview_generators` - Preview image generation utilities

## Further Reading

- {ref}`record-building` - How extractors fit into the record building workflow
- {doc}`taxonomy` - Data type classification and taxonomy
- {py:mod}`nexusLIMS.extractors` - Complete API documentation
