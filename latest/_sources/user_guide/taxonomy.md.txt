# NexusLIMS Taxonomy

This page defines the key terms and concepts used throughout NexusLIMS. Understanding this taxonomy is essential for working with the codebase and understanding how microscopy data is organized, classified, and transformed into experimental records.

## Data Organization Philosophy

NexusLIMS organizes microscopy data hierarchically:

1. **Sessions** - User reservations defining when an instrument was used
2. **Acquisition Activities** - Groups of files created in temporal proximity during a session
3. **Datasets** - Individual signals (images, spectra, etc.) with associated metadata. Typically corresponds to a single file on disk, but some files contain multiple signals and will result in multiple *datasets* in a record.
4. **Records** - XML documents describing complete experimental sessions

This structure mirrors typical microscopy workflows: users reserve instrument time (session), collect related data in bursts (activities), and each file represents a discrete measurement (one or more datasets).

---

## System Components

The following terms describe major architectural components:

- **Harvester:**

  - The harvesters (implemented in the {py:mod}`nexusLIMS.harvesters` package)
    are the portions of the code that connect to external data sources, such
    as the NEMO laboratory management system. The only harvester currenlty implemented is NEMO
    ({py:mod}`~nexusLIMS.harvesters.nemo`). A SharePoint calendar harvester was used in previous versions of NexusLIMS, but was removed in version 2.0.0.

- **Extractor:**

  - The extractors (implemented in the {py:mod}`nexusLIMS.extractors` package)
    are the modules that inspect the data files collected during an Experiment
    and pull out the relevant metadata contained within for inclusion in the
    record. The preview image generation is also considered an extractor.

- **Record Builder:**

  - The record builder (implemented in the
    {py:mod}`nexusLIMS.builder.record_builder` module) is the heart of the
    NexusLIMS back-end. It orchestrates the complete record creation workflow:

    1. Trigger harvesters to look for new sessions and add them to the session database
    2. Query database for sessions ready to build
    3. Find all data files modified during the session time window
    4. Cluster files into Acquisition Activities based on temporal gaps
    5. Extract and validate metadata from each file
    6. Build XML record conforming to Nexus Experiment schema
    7. Upload record to CDCS instance

    Further details are provided on the {doc}`record building <record_building>`
    documentation page.

- **Session Logger:**

  - The session logger (removed) was a portable Windows application that ran on
    individual microscope PCs to log experiment session information. This was removed in version 1.1.0 and has been
    replaced by the NEMO harvester approach.

---

## Dataset Types

**Dataset Type** (or `DatasetType`) classifies the fundamental nature of the data in a file. This is a **required field** in all NexusLIMS metadata and determines which Pydantic schema is used for validation.

### Available Dataset Types

| DatasetType | Description | Example Instruments | Dimensions |
|-------------|-------------|---------------------|------------|
| `"Image"` | 2D imaging data | SEM, TEM, STEM, Optical | 2D array (x, y) |
| `"Spectrum"` | 1D spectral data | EDS, EELS, CL | 1D array (energy/wavelength) |
| `"SpectrumImage"` | 2D image with spectrum at each pixel | EDS maps, EELS-SI | 3D array (x, y, spectrum) |
| `"Diffraction"` | Diffraction patterns | SAED, CBED, 4D-STEM | 2D or 4D array |
| `"Misc"` | Other structured data | Custom formats, line scans | Variable |
| `"Unknown"` | Unable to determine | Corrupted/unreadable files | N/A |

**Note**:

- A "line scan" is considered to be a special case of `"SpectrumImage"` with a *y* dimension of 1

### Schema Mapping

Each DatasetType maps to a specific Pydantic schema for metadata validation:

| DatasetType | Schema Class |
|-------------|--------------|
| `"Image"` | {py:obj}`~nexusLIMS.schemas.metadata.ImageMetadata` |
| `"Spectrum"` | {py:obj}`~nexusLIMS.schemas.metadata.SpectrumMetadata` |
| `"SpectrumImage"` | {py:obj}`~nexusLIMS.schemas.metadata.SpectrumImageMetadata` |
| `"Diffraction"` | {py:obj}`~nexusLIMS.schemas.metadata.DiffractionMetadata` |
| `"Misc"` | {py:obj}`~nexusLIMS.schemas.metadata.NexusMetadata` (base schema) |
| `"Unknown"` | {py:obj}`~nexusLIMS.schemas.metadata.NexusMetadata` (base schema) |

The schema selection happens automatically in `validate_nx_meta()` based on the `DatasetType` field. Different schemas validate different sets of optional fields:

- **`ImageMetadata`** - Validates imaging fields (acceleration_voltage, working_distance, magnification)
- **`SpectrumMetadata`** - Validates spectroscopy fields (acquisition_time, live_time, channel_size)
- **`SpectrumImageMetadata`** - Validates **both** imaging and spectroscopy fields
- **`DiffractionMetadata`** - Validates diffraction fields (camera_length, convergence_angle)

### Usage in Extractors

Extractors must set `DatasetType` based on file content:

```python
# Example: SEM image
nx_meta = {
    "DatasetType": "Image",
    "Data Type": "SEM_Imaging",
    # ... imaging-specific fields
}

# Example: EDS spectrum
nx_meta = {
    "DatasetType": "Spectrum",
    "Data Type": "SEM_EDS",
    # ... spectrum-specific fields
}

# Example: EDS map (spectrum at each pixel)
nx_meta = {
    "DatasetType": "SpectrumImage",
    "Data Type": "STEM_EDS",
    # ... both imaging AND spectrum fields
}
```

For more details on choosing the appropriate DatasetType, see {ref}`Schema Selection Logic <schema-selection-logic>`.

---

## Data Type Classification

**Data Type** is a descriptive string that provides more specific information about the acquisition technique and modality. While `DatasetType` is constrained to six values, `Data Type` can be any descriptive string.

### Naming Convention

NexusLIMS uses a structured format for `Data Type`:

```
Category_Modality_Technique
```

**Examples:**
- `SEM_Imaging` - Scanning Electron Microscopy imaging
- `TEM_Imaging` - Transmission Electron Microscopy imaging
- `STEM_Imaging` - Scanning Transmission Electron Microscopy imaging
- `STEM_EDS` - STEM with Energy Dispersive X-ray Spectroscopy
- `TEM_EELS` - TEM with Electron Energy Loss Spectroscopy
- `TEM_Diffraction` - TEM diffraction pattern
- `SEM_BSE` - SEM with Backscattered Electron detector
- `STEM_HAADF` - STEM with High-Angle Annular Dark Field detector

### Components

1. **Category** - Instrument family (SEM, TEM, STEM, FIB, Optical, etc.)
2. **Modality** - Detection/operation mode (Imaging, EDS, EELS, Diffraction, BSE, SE, etc.)
3. **Technique** - Specific variant (HAADF, BF, DF, SAED, CBED, etc.) - optional

### How Extractors Determine Data Type

Extractors typically determine `Data Type` by analyzing:

1. **File format** - Some formats are technique-specific (e.g., `.spc` files are always EDS spectra)
2. **Metadata fields** - Imaging mode, detector type, operation mode
3. **Data dimensions** - 2D = likely imaging, 1D = likely spectrum
4. **Detector information** - HAADF detector → STEM_HAADF
5. **Filename patterns** - Sometimes contains hints (Diff, SAED, etc.)

### Relationship to DatasetType

| Data Type | Typical DatasetType |
|-----------|-------------------|
| SEM_Imaging, TEM_Imaging, STEM_Imaging | `"Image"` |
| SEM_EDS, TEM_EELS (point spectra) | `"Spectrum"` |
| STEM_EDS, STEM_EELS (maps) | `"SpectrumImage"` |
| TEM_Diffraction, TEM_SAED, TEM_CBED | `"Diffraction"` |

The combination of `DatasetType` (for schema validation) and `Data Type` (for human description) provides both machine-readable classification and human-readable context.

---

## Metadata Schema Structure

**New in v2.2.0:** NexusLIMS uses a three-tier architecture for organizing metadata, balancing standardization with flexibility.

### Three-Tier Architecture

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e3f2fd', 'primaryTextColor': '#000', 'primaryBorderColor': '#1976d2', 'lineColor': '#1976d2', 'secondaryColor': '#fff3e0', 'tertiaryColor': '#f3e5f5'}}}%%
flowchart TD
    Tier1["<b>Tier 1: Core Fields</b><br/>(Required + Common EM Glossary fields)<br/><br/>• DatasetType, Data Type, Creation Time<br/>• acceleration_voltage, beam_current<br/>• magnification, working_distance"]

    Tier2["<b>Tier 2: Type-Specific Fields</b><br/>(Additional fields per DatasetType)<br/><br/>• ImageMetadata: detector_type, etc.<br/>• SpectrumMetadata: acquisition_time<br/>• DiffractionMetadata: camera_length"]

    Tier3["<b>Tier 3: Extensions</b><br/>(Vendor/instrument-specific fields)<br/><br/>• facility, building, room<br/>• vendor_metadata<br/>• instrument_serial"]

    Tier1 --> Tier2
    Tier2 --> Tier3

    classDef tier1Style fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#000
    classDef tier2Style fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#000
    classDef tier3Style fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,color:#000

    class Tier1 tier1Style
    class Tier2 tier2Style
    class Tier3 tier3Style
```

### Tier 1: Core Fields

**Always required** regardless of DatasetType:
- `DatasetType` - Classification for schema selection
- `Data Type` - Human-readable technique description
- `Creation Time` - ISO-8601 timestamp with timezone

**Common EM Glossary fields** (optional but standardized):
- `acceleration_voltage` - Electron beam energy
- `beam_current` - Probe current
- `working_distance` - Pole piece to sample distance
- `magnification` - Imaging magnification
- ... (50+ standardized fields available)

These fields use EM Glossary standardized names and are validated by all schema classes.

### Tier 2: Type-Specific Fields

Additional optional fields validated based on `DatasetType`:

**ImageMetadata** (for `DatasetType == "Image"`):
- `detector_type` - Detector name (SE, BSE, HAADF, etc.)
- `field_of_view_width` / `field_of_view_height` - Image dimensions in physical units
- `pixel_width` / `pixel_height` - Pixel size in physical units
- `dwell_time` - Pixel dwell time for scanning

**SpectrumMetadata** (for `DatasetType == "Spectrum"`):
- `acquisition_time` - Total acquisition duration
- `live_time` - Detector live time (EDS)
- `channel_size` - Energy/wavelength per channel
- `starting_energy` - Spectrum start energy
- `takeoff_angle` - EDS detector geometry

**SpectrumImageMetadata** (for `DatasetType == "SpectrumImage"`):
- Validates **both** ImageMetadata AND SpectrumMetadata fields
- Allows both imaging parameters and spectroscopy parameters

**DiffractionMetadata** (for `DatasetType == "Diffraction"`):
- `camera_length` - Diffraction camera length
- `convergence_angle` - Probe convergence angle (CBED)

### Tier 3: Extensions

The `extensions` dictionary holds fields that don't fit the core schema:

```python
nx_meta = {
    # Tier 1 & 2: Core and type-specific fields
    "DatasetType": "Image",
    "acceleration_voltage": ureg.Quantity(15, "kilovolt"),

    # Tier 3: Extensions
    "extensions": {
        "facility": "NIST Center for Nanoscale Science",
        "building": "Bldg 217",
        "room": "A206",
        "quanta_spot_size": 3.5,  # Vendor-specific
        "fei_detector_mode": "CBS",
        "detector_serial": "12345-ABC",
    }
}
```

**When to use extensions:**
- Vendor-specific fields without EM Glossary equivalents
- Site/facility metadata (building, room, PI name)
- Instrument calibration data
- Custom workflow parameters
- Anything that shouldn't be validated by schema

**Populating extensions:**
- In extractors: Use `add_to_extensions()` helper
- In instrument profiles: Use `extension_fields` parameter
- See {ref}`Helper Functions <metadata-helper-functions>` for details

### Benefits of Three-Tier Structure

1. **Standardization** - Core fields ensure interoperability across instruments
2. **Validation** - Type-specific fields are validated by appropriate schemas
3. **Flexibility** - Extensions accommodate vendor-specific or site-specific metadata
4. **Extensibility** - New fields can be added without breaking existing code
5. **Semantic clarity** - Clear separation between standardized and custom metadata

---

## Acquisition Activities

An **Acquisition Activity** is a group of files created in temporal proximity during an experimental session. Activities represent discrete experimental tasks (e.g., "Survey of sample region 1", "EDS line scan across interface").

### Motivation

Microscopy experiments typically consist of multiple distinct activities:
- Initial survey imaging at low magnification
- Higher magnification imaging of regions of interest
- Spectroscopy (EDS, EELS) at specific points
- Diffraction pattern collection
- Return to imaging at different locations

Each activity generates a burst of files. Temporal gaps between file creation indicate transitions between activities.

### File Clustering Algorithm

The record builder uses **Kernel Density Estimation (KDE)** to identify temporal gaps in file creation times:

```python
from nexusLIMS.schemas.activity import cluster_filelist_mtimes

# Input: List of file paths with modification times
files = [Path("file1.dm3"), Path("file2.dm3"), ...]

# Cluster into activities based on temporal gaps
activities = cluster_filelist_mtimes(files)
# → [[file1, file2], [file3, file4, file5], [file6]]
```

**Algorithm steps:**

1. Extract modification times from all files
2. Convert to minutes since session start
3. Apply Gaussian KDE to find probability density of file creation
4. Identify local minima in density → temporal gaps
5. Split file list at gap boundaries
6. Return list of file groups (activities)

**Example timeline:**

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e3f2fd', 'primaryTextColor': '#000', 'primaryBorderColor': '#1976d2'}}}%%
gantt
    title File Clustering into Acquisition Activities
    dateFormat mm
    axisFormat %M min

    section Activity 1
    Survey images (7 files)           :active, a1, 00, 5m

    section Gap
    10 min gap                        :crit, gap1, 05, 10m

    section Activity 2
    High-mag imaging (4 files)        :active, a2, 15, 5m

    section Gap
    15 min gap                        :crit, gap2, 20, 15m

    section Activity 3
    EDS point spectra (6 files)       :active, a3, 35, 5m

    section Gap
    5 min gap                         :crit, gap3, 40, 5m

    section Activity 4
    EDS map (8 files)                 :active, a4, 45, 5m
```

**Parameters:**
- Minimum gap duration to split activities (configurable)
- Bandwidth for KDE smoothing (adapts to data density)

### Activity Metadata

Each activity in a record includes:
- Start time (earliest file in group)
- End time (latest file in group)
- List of datasets (files) in the activity
- Activity-level summary information

### Relationship to Sessions

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e3f2fd', 'primaryTextColor': '#000', 'primaryBorderColor': '#1976d2'}}}%%
graph TD
    Session["Session<br/>(Microscopy Usage Event)"]

    Session --> Activity1["Activity 1<br/>(Survey Images)"]
    Session --> Activity2["Activity 2<br/>(High-Mag Imaging)"]
    Session --> Activity3["Activity 3<br/>(EDS Analysis)"]

    Activity1 --> Dataset1["Dataset 1<br/>(image001.tif)"]
    Activity1 --> Dataset2["Dataset 2<br/>(image002.tif)"]
    Activity1 --> Dataset3["Dataset 3<br/>(image003.tif)"]

    Activity2 --> Dataset4["Dataset 4<br/>(image004.tif)"]
    Activity2 --> Dataset5["Dataset 5<br/>(image005.tif)"]

    Activity3 --> Dataset6["Dataset 6<br/>(spectrum001.spc)"]

    classDef sessionStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    classDef activityStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef datasetStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1px

    class Session sessionStyle
    class Activity1,Activity2,Activity3 activityStyle
    class Dataset1,Dataset2,Dataset3,Dataset4,Dataset5,Dataset6 datasetStyle
```

A session can have one or more activities. The clustering algorithm automatically determines activity boundaries based on temporal gaps in file creation times.

### Implementation Details

- **Module:** {py:mod}`nexusLIMS.schemas.activity`
- **Class:** {py:class}`~nexusLIMS.schemas.activity.AcquisitionActivity`
- **Function:** {py:func}`~nexusLIMS.schemas.activity.cluster_filelist_mtimes`
- **Algorithm:** Scikit-learn `KernelDensity` with Gaussian kernel

For more details, see {ref}`Separating Acquisition Activities <build-activities>`.

---

## See Also

- [NexusLIMS Internal Schema](../dev_guide/nexuslims_internal_schema.md) - Detailed internal metadata schema documentation
- [EM Glossary Reference](../dev_guide/em_glossary_reference.md) - Complete field reference
- [Writing Extractor Plugins](../dev_guide/writing_extractor_plugins.md) - Using DatasetTypes in extractors
- [Record Building Process](record_building.md) - Complete workflow documentation
