(dev_guide)=
# Dev Guide

This guide helps developers understand, extend, and contribute to NexusLIMS. Whether you're adding support for a new file format, customizing extraction for your instruments, or contributing to the core codebase, this guide provides the roadmap you need.

## Overview

NexusLIMS is an **automated Laboratory Information Management System** for electron microscopy facilities. It transforms raw microscopy data files and calendar reservations into structured, searchable experimental records.

**Key capabilities:**
- **Automated record generation** - No manual data entry required
- **Multi-instrument support** - Works across different microscope vendors and types
- **Extensible metadata extraction** - Plugin-based system for adding new file formats
- **Standardized metadata** - Uses EM Glossary ontology for interoperability
- **Flexible deployment** - Runs as a daemon, cron job, or on-demand

---

## 🆕 What's New in v2.2.0

**Major schema system upgrade** with Pydantic v2, EM Glossary integration, and improved validation:

### Key Changes

1. **Pydantic Metadata Schemas**
   - All metadata validated using type-specific Pydantic schemas
   - Schema selection based on `DatasetType` (Image, Spectrum, SpectrumImage, Diffraction)
   - Strict validation catches errors before record building
   - See [NexusLIMS Internal Schema](dev_guide/nexuslims_internal_schema.md) for details

2. **EM Glossary v2.0 Integration**
   - 50+ standardized field names from community ontology
   - Automatic display name and EMG ID annotation
   - Preferred units for each physical quantity
   - See [EM Glossary Reference](dev_guide/em_glossary_reference.md) for field mappings

3. **Formal Unit Integration**
   - All physical quantities use Pint with QUDT ontology
   - Automatic unit conversion and validation
   - Machine-readable unit information in XML output
   - Type-safe quantity handling

4. **Schema Module Reorganization**
   - Modular design: `metadata.py`, `em_glossary.py`, `units.py`, `pint_types.py`
   - Clear separation between core, type-specific, and extension fields
   - Better extensibility for future enhancements

### Migration Impact

If you maintain custom extractors or instrument profiles:
- **Extractors:** Use Pint Quantities for fields with units
- **Profiles:** Use `extension_fields` for custom metadata that does not fit within the schemas
- **Tests:** Use new schema class names (e.g., `ImageMetadata`)

See migration guides in [NexusLIMS Internal Schema](dev_guide/nexuslims_internal_schema.md) and [Instrument Profiles](dev_guide/instrument_profiles.md).

---

## Architecture Overview

NexusLIMS follows a pipeline architecture with six main components:

### Component Descriptions

1. **Harvesters** (`nexusLIMS/harvesters/`)
   - Poll NEMO API for instrument reservations and usage events
   - Create session start/end events in database
   - Support multiple NEMO instances via configuration
   - **Extension point:** Add new harvesters for other calendar systems

2. **Database** (`nexusLIMS/db/`)
   - SQLite database tracking instrument sessions
   - Two tables: `instruments` (config), `session_log` (events)
   - Session states: WAITING_FOR_END → TO_BE_BUILT → COMPLETED/ERROR
   - ORM-like `Session` objects via `session_handler.py`

3. **Record Builder** (`nexusLIMS/builder/record_builder.py`)
   - Orchestrates complete record generation workflow:
     1. Query for sessions ready to build
     2. Find files modified during session window
     3. Cluster files into Acquisition Activities (temporal analysis)
     4. Extract and validate metadata from each file
     5. Build XML record conforming to Nexus Experiment schema
     6. Upload to CDCS instance
   - **Entry point:** `process_new_records()` function

4. **Extractors** (`nexusLIMS/extractors/`)
   - Plugin-based system for format-specific metadata extraction
   - Auto-discovery from `plugins/` directory
   - Priority-based selection (higher priority tried first)
   - Returns `nx_meta` dict validated by Pydantic schemas
   - **Extension point:** Add plugins for new file formats

5. **Schemas** (`nexusLIMS/schemas/`)
   - Pydantic models for metadata validation
   - Type-specific schemas: `ImageMetadata`, `SpectrumMetadata`, `SpectrumImageMetadata`, `DiffractionMetadata`
   - EM Glossary integration for standardized field names
   - Unit handling with Pint and QUDT
   - **Extension point:** Add new fields to schemas

6. **CDCS Integration** (`cdcs.py`)
   - Uploads XML records to NexusLIMS CDCS frontend
   - REST API communication with token authentication
   - Workspace and template management
   - **Configuration:** `NX_CDCS_URL`, `NX_CDCS_TOKEN`

### Data Flow

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e3f2fd', 'primaryTextColor': '#000', 'primaryBorderColor': '#1976d2', 'lineColor': '#1976d2'}}}%%
flowchart TD
    Start([User creates Reservation in NEMO]) --> Experiment[User performs experiment]
    Experiment --> UsageEvent[NEMO creates Usage Event<br/>start & end times]
    UsageEvent --> Poll[Harvester polls Usage Events API]
    Poll --> StartEvent[Session START event → Database]
    StartEvent --> EndEvent[Session END event → Database]
    EndEvent --> ToBuild[Session state = TO_BE_BUILT]
    ToBuild --> FindSession[Record Builder finds session]
    FindSession --> FindFiles[Find files by modification time]
    FindFiles --> Cluster[Cluster files into Activities<br/>using KDE]
    Cluster --> ProcessFiles{For each file}

    ProcessFiles --> SelectExtractor["Select extractor<br/>via <code>priority</code> + <code>supports()</code>"]
    SelectExtractor --> ExtractMeta["Extract metadata → <code>nx_meta</code> dict"]
    ExtractMeta --> ValidateSchema[Validate with Pydantic schema]
    ValidateSchema --> MoreFiles{More files?}
    MoreFiles -->|Yes| ProcessFiles
    MoreFiles -->|No| BuildXML[Build XML record<br/>Nexus Experiment schema]

    BuildXML --> Upload[Upload to CDCS]
    Upload --> Complete[Session state = COMPLETED]
    Complete --> End([End])

    classDef userAction fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef dbAction fill:#e1f5ff,stroke:#1976d2,stroke-width:2px
    classDef processing fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px

    class Start,Experiment userAction
    class StartEvent,EndEvent,ToBuild,Complete dbAction
    class FindSession,FindFiles,Cluster,SelectExtractor,ExtractMeta,ValidateSchema,BuildXML,Upload processing
```

---

## Common Development Tasks

Quick links to guides for common tasks:

### Adding File Format Support
- **Guide:** [Writing Extractor Plugins](dev_guide/writing_extractor_plugins.md)
- **Example:** See `plugins/quanta_tif.py` for TIFF format
- **Steps:** Create plugin class, implement `supports()` and `extract()`, test with sample files

### Customizing Instrument Behavior
- **Guide:** [Instrument Profiles](dev_guide/instrument_profiles.md)
- **Example:** See `profiles/fei_titan_tem_642.py`
- **Steps:** Create profile with parsers/transformations, register with registry

### Understanding Metadata Schemas
- **Guide:** [NexusLIMS Internal Schema](dev_guide/nexuslims_internal_schema.md)
- **Reference:** [EM Glossary Reference](dev_guide/em_glossary_reference.md)
- **Helper Functions:** {ref}`Helper Functions <metadata-helper-functions>`

### Running Tests
- **Guide:** {ref}`Testing <testing>`
- **Command:** `./scripts/run_tests.sh` (with mpl comparison)
- **Coverage:** Reports generated in `tests/coverage/`

### Building Documentation
- **Guide:** {ref}`Documentation <documentation>`
- **Command:** `./scripts/build_docs.sh`
- **Output:** `./_build/html/index.html`

### Debugging Extraction
- **Enable debug logging:**
  ```python
  import logging
  logging.getLogger("nexusLIMS.extractors").setLevel(logging.DEBUG)
  logging.getLogger("nexusLIMS.schemas").setLevel(logging.DEBUG)
  ```
- **Test extraction directly:**
  ```python
  from pathlib import Path
  from nexusLIMS.extractors import get_full_meta
  metadata = get_full_meta(Path("/path/to/file.dm3"), instrument=None)
  ```

---

(creating-sanitized-test-files)=
## Creating Sanitized Test Files

When adding test fixtures for new file formats, it's critical to sanitize files to remove sensitive data while preserving the metadata structure needed for testing. This section explains how to create highly-compressed test archives for the repository.

### Why Sanitize Test Files?

1. **Privacy**: Remove proprietary or sensitive image data
2. **Size**: Zeroed data compresses extremely well (1000:1 or better)
3. **Repository health**: Keep the git repository small and fast
4. **Complete metadata**: Preserve all metadata structure for realistic testing

### General Approach

The goal is to **zero out image/spectral data** while **preserving all metadata** and file structure:

1. Start with a real microscopy file from your target format
2. Parse the file structure to locate image/spectral data regions
3. Replace data bytes with zeros while keeping all metadata intact
4. Compress into a `.tar.gz` archive for the test suite

### Format-Specific Methods

#### TIFF Files (Compressed)

For LZW-compressed TIFF files (common in FEI/Thermo, Zeiss, TESCAN instruments), use the binary patching method:

**Key insight**: You cannot simply write zeros to the file - the compressed data size changes, which requires rebuilding the entire file structure.

**Process**:
1. Read entire file as binary
2. Parse TIFF structure (header → IFD → tag data)
3. Locate and decompress image strips (using `imagecodecs.lzw_decode`)
4. Create zeroed array with same dimensions
5. Recompress zeros (using `imagecodecs.lzw_encode`)
6. Binary patch: write new header + compressed data + updated IFD

**Reference implementation**: See `.claude/notes/zeroing-compressed-tiff-files.md` for detailed algorithm

**Example script skeleton**:
```python
import imagecodecs
from pathlib import Path

def zero_lzw_tiff(input_path: Path, output_path: Path):
    """Zero image data in LZW-compressed TIFF while preserving metadata."""
    # 1. Read file
    data = bytearray(input_path.read_bytes())

    # 2. Parse TIFF structure to find StripOffsets and StripByteCounts
    # (implement TIFF parsing - read IFD entries, find tags 273 and 279)

    # 3. Extract and decompress strips
    compressed = data[strip_offset:strip_offset + strip_bytes]
    uncompressed = imagecodecs.lzw_decode(compressed)

    # 4. Zero and recompress
    zeroed = bytes(len(uncompressed))
    new_compressed = imagecodecs.lzw_encode(zeroed)

    # 5. Rebuild file (header + new_compressed + updated IFD)
    # (implement binary patching logic)

    output_path.write_bytes(new_data)
```

**Result**: Files shrink from ~2MB to ~10KB (99%+ reduction)

#### TIFF Files (Uncompressed)

For uncompressed TIFF files, you can directly write zeros to the image data region:

```python
import tifffile

def zero_uncompressed_tiff(input_path: Path, output_path: Path):
    """Zero uncompressed TIFF image data."""
    # Read TIFF pages
    with tifffile.TiffFile(input_path) as tif:
        # Get first page
        page = tif.pages[0]

        # Create zeroed array with same shape
        data = np.zeros(page.shape, dtype=page.dtype)

        # Write with original metadata tags
        tifffile.imwrite(
            output_path,
            data,
            metadata=page.tags  # Preserves original tags
        )
```

**Warning**: This recreates the file structure, which may lose some vendor-specific tags. For maximum fidelity, use the binary patching method.

#### Digital Micrograph (.dm3/.dm4)

DM files use a tagged data structure. Use HyperSpy to read and zero:

```python
import hyperspy.api as hs
import numpy as np

def zero_dm_file(input_path: Path, output_path: Path):
    """Zero DM3/DM4 image/spectral data while preserving metadata."""
    # Load file
    s = hs.load(input_path)

    # Handle multiple signals (may return list)
    if isinstance(s, list):
        for signal in s:
            signal.data = np.zeros_like(signal.data)
    else:
        s.data = np.zeros_like(s.data)

    # Save with all metadata preserved
    s.save(output_path)
```

**Result**: Excellent compression since DM format already uses compression on zero data.

#### Other Binary Formats

For proprietary binary formats:

1. **Use hex editor** to locate image data regions (often contiguous blocks)
2. **Write zeros** to those byte ranges
3. **Verify** the file still opens and metadata is readable
4. **Test** that your extractor still works on the zeroed file

### Creating the Archive

Once you have sanitized file(s), create a tar.gz archive:

**CRITICAL**: On macOS, use `COPYFILE_DISABLE=1` to prevent including `.DS_Store` and resource forks:

```bash
# Create archive (from tests/unit/files/ directory)
COPYFILE_DISABLE=1 tar -czf xyz_format_dataZeroed.tar.gz test_file.xyz

# Verify contents (should only show your test file)
tar -tzf xyz_format_dataZeroed.tar.gz
```

**Naming convention**: Use `*_dataZeroed.tar.gz` suffix to indicate sanitized files.

### Adding to Test Suite

1. **Place archive** in `tests/unit/files/`
2. **Register in `tests/unit/utils.py`**:
   ```python
   tars = {
       # ... existing entries ...
       "XYZ_FORMAT": "xyz_format_test_dataZeroed.tar.gz",
   }
   ```
3. **Create fixture** in your test file (see {doc}`dev_guide/writing_extractor_plugins`)

### Verification Checklist

Before committing your sanitized test file:

- [ ] File still opens with intended software/library
- [ ] All metadata fields are present and correct
- [ ] Image/spectral data is zeroed
- [ ] File size is significantly reduced (check compression ratio)
- [ ] Archive contains no macOS hidden files (`.DS_Store`, `._*`)
- [ ] Your extractor tests pass using the sanitized file
- [ ] Archive is in `tests/unit/files/` directory
- [ ] Archive is registered in `tests/unit/utils.py`

### Example: Complete Workflow

```bash
# 1. Create sanitized file using your script
uv run python scripts/zero_my_format.py input.xyz output_dataZeroed.xyz

# 2. Verify it's sanitized
ls -lh output_dataZeroed.xyz  # Should be much smaller

# 3. Create archive (from tests/unit/files/)
cd tests/unit/files
COPYFILE_DISABLE=1 tar -czf my_format_dataZeroed.tar.gz output_dataZeroed.xyz

# 4. Verify archive contents
tar -tzf my_format_dataZeroed.tar.gz

# 5. Add to registry
# Edit tests/unit/utils.py and add entry to tars dict

# 6. Write tests using your new fixture
# See writing_extractor_plugins.md
```

---

## Contributing Guidelines

We welcome contributions! Here's how to get started:

### Development Setup

1. **Clone repository:**
   ```bash
   git clone https://github.com/datasophos/NexusLIMS.git
   cd NexusLIMS
   ```

2. **Install dependencies:**
   ```bash
   uv sync  # Installs all dependencies including dev tools
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run tests:**
   ```bash
   ./scripts/run_tests.sh
   ```

### Code Standards

- **Formatting:** Ruff (88 char line length)
- **Linting:** Ruff with extensive rule set
- **Type hints:** Use type annotations where possible
- **Docstrings:** NumPy-style docstrings for all public functions/classes
- **Testing:** Write tests for new features (pytest with mpl comparison)
- **Pre-commit:** Git hooks automatically run formatters and linters before commits

#### Setting Up Pre-commit

Pre-commit hooks are configured to automatically format and lint your code:

```bash
# Install pre-commit hooks (one-time setup)
uv run pre-commit install

# Pre-commit will now run automatically on `git commit`
# It will format code and run linters, blocking commits if issues are found
```

To run checks manually:
```bash
# Run on all files
uv run pre-commit run --all-files

# Or use the convenience script (includes type checking)
./scripts/run_lint.sh
```

### Submitting Changes

1. **Create feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test:**
   ```bash
   # Edit code
   ./scripts/run_lint.sh  # Check code quality
   ./scripts/run_tests.sh  # Run test suite
   ```

3. **Create changelog blurb:**
   ```bash
   # Add file to docs/changes/ following instructions in docs/changes/README.rst
   ```

4. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: Add support for XYZ format"
   ```

5. **Push and create PR:**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Contribution Areas

We especially welcome contributions in these areas:

- **New file format support** - Extractor plugins for additional microscopy formats
- **Instrument profiles** - Profiles for commercial instruments
- **Documentation improvements** - Clarifications, examples, guides
- **Test coverage** - Additional test cases and fixtures
- **Bug fixes** - Issues labeled "good first issue"

---

## Additional Resources

```{toctree}
:maxdepth: 1

dev_guide/development
dev_guide/writing_extractor_plugins
dev_guide/writing_export_destinations
dev_guide/instrument_profiles
dev_guide/nexuslims_internal_schema
dev_guide/em_glossary_reference
dev_guide/examples
dev_guide/uv_migration
dev_guide/database
dev_guide/schema_documentation
dev_guide/testing/integration-tests
```

---

## Getting Help

- **GitHub Issues:** Report bugs or request features at [https://github.com/datasophos/NexusLIMS/issues](https://github.com/datasophos/NexusLIMS/issues)
- **Documentation:** Comprehensive guides in this developer documentation
