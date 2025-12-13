# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NexusLIMS is an electron microscopy Laboratory Information Management System (LIMS) originally developed at NIST, now maintained by Datasophos. It automatically generates experimental records by extracting metadata from microscopy data files and harvesting information from reservation calendar systems (like NEMO).

This is the **backend** repository. The frontend is at [NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS).

## Development Commands

### Package Management
This project uses **uv** for package management (recently migrated from Poetry):

```bash
# Install dependencies
uv sync

# Add a dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>
```

### Testing

Tests should always be run with mpl comparison:

```bash
# Run all tests with coverage (recommended)
./scripts/run_tests.sh

# Run a specific test file
uv run pytest --mpl --mpl-baseline-path=tests/files/figs tests/test_extractors.py

# Run a specific test
uv run pytest --mpl --mpl-baseline-path=tests/files/figs tests/test_extractors.py::TestClassName::test_method_name

# Generate matplotlib baseline figures for image comparison tests
./scripts/generate_mpl_baseline.sh
```

### Linting and Formatting

```bash
# Run all linting and formatting checks (recommended)
./scripts/run_lint.sh

# Or run individually:
uv run ruff format . --check  # Check formatting
uv run ruff check nexusLIMS tests  # Run linting

# Auto-format code
uv run ruff format .

# Type checking (Pyright is configured)
pyright
```

### Documentation

```bash
# Build documentation
./scripts/build_docs.sh

# Documentation will be in ./_build directory
```

### Running the Record Builder

```bash
# Run the record builder with full orchestration (recommended for production)
# Includes file locking, timestamped logging, and email notifications
nexuslims-process-records

# Or using the module directly:
uv run python -m nexusLIMS.cli.process_records

# Run in dry-run mode (find files without building records)
nexuslims-process-records -n

# Run with verbose output
nexuslims-process-records -vv

# Run the core record builder directly (minimal logging, no locking)
uv run python -m nexusLIMS.builder.record_builder
```

## Architecture Overview

### Core Components

1. **Database Layer** (`nexusLIMS/db/`)
   - SQLite database tracks instruments and session logs
   - Two main tables: `instruments` (instrument config) and `session_log` (session tracking)
   - `session_handler.py` provides ORM-like Session objects
   - Sessions have states: WAITING_FOR_END, TO_BE_BUILT, COMPLETED, ERROR, NO_FILES_FOUND

2. **Harvesters** (`nexusLIMS/harvesters/`)
   - Extract reservation/usage data from external systems
   - **NEMO harvester** (`nemo/`): Primary harvester for NEMO lab management system
   - **SharePoint harvester** (`sharepoint_calendar.py`): Deprecated
   - Harvesters create `ReservationEvent` objects with session metadata

3. **Extractors** (`nexusLIMS/extractors/`)
   - Extract metadata from microscopy file formats using a **plugin-based architecture**
   - **Plugin system** (`extractors/plugins/`):
     - `basic_metadata.py`: Extracts file system metadata (size, timestamps, etc.)
     - `quanta_tif.py`: FEI/Thermo `.tif` format extractor
     - `digital_micrograph.py`: Gatan `.dm3/.dm4` format extractor
     - `edax_spc_map.py`: EDAX `.spc/.msa` spectrum format extractor
     - `fei_emi.py`: FEI TIA `.ser/.emi` format extractor
     - Plugins auto-discovered via `discover_plugins()` function
   - **Instrument profiles** (`extractors/plugins/profiles/`):
     - Customize metadata extraction for specific instruments without modifying core extractors
     - Supports both built-in profiles (shipped with codebase) and local profiles (external directory)
     - Local profiles loaded from `NX_LOCAL_PROFILES_PATH` environment variable
     - Profiles can add static metadata, parse/transform fields, add warnings, override extractors
   - **Preview generators** (`extractors/plugins/preview_generators/`):
     - Generate thumbnail images from microscopy data files
     - Plugin-based system with image and text preview generators
   - Each extractor returns dict with `nx_meta` key containing NexusLIMS-specific metadata
   - `base.py` defines base classes: `ExtractorPlugin`, `InstrumentProfile`, `PreviewGeneratorPlugin`

4. **Record Builder** (`nexusLIMS/builder/record_builder.py`)
   - Main orchestrator: `process_new_records()` is the entry point
   - `build_record()` creates XML records conforming to Nexus Experiment schema
   - Workflow:
     1. Query database for sessions TO_BE_BUILT
     2. Find files by modification time within session window
     3. Cluster files into Acquisition Activities using KDE
     4. Extract metadata from each file
     5. Build XML record
     6. Upload to CDCS frontend

5. **Schemas** (`nexusLIMS/schemas/`)
   - `activity.py`: AcquisitionActivity class and file clustering logic
   - `cluster_filelist_mtimes()`: Uses scikit-learn KDE to find temporal gaps in file creation
   - XML schema validation against `nexus-experiment.xsd`

6. **CDCS Integration** (`cdcs.py`)
   - Uploads records to NexusLIMS CDCS frontend
   - Uses credentials from environment variables
   - **CDCS REST API Query Endpoint** (`rest/data/query/`):
     - Defined in `core_main_app` repository
     - POST request parameters:
       - `query` (required): MongoDB-style query object (e.g., `{}` for all, `{"root.element.value": 2}` for filtering)
       - `templates`: List of template objects `[{"id": "template_id"}]`
       - `workspaces`: List of workspace objects `[{"id": "workspace_id"}]` (use `[{"id": "None"}]` for private)
       - `title`: Filter by document title string
       - `all`: Boolean (`"true"`/`"false"`) to disable pagination
       - `xpath`: XPath expression to extract specific content (e.g., `"/ns:root/@element"`)
       - `namespaces`: Namespace mappings for XPath (e.g., `{"ns": "http://example.com/ns"}`)
       - `options`: Query options dict (can include `VISIBILITY_OPTION`)
       - `order_by_field`: Comma-separated field names for sorting
     - URL parameter: `page` for pagination (e.g., `?page=2`)
     - Multiple filters can be combined in a single query

### Key Workflows

**Record Building Process:**
1. NEMO harvester polls API for new/ended reservations
2. Harvester creates session_log entries with START/END events
3. Record builder finds sessions TO_BE_BUILT
4. Files are found using GNU find (via `gnu_find_files_by_mtime`)
5. Files clustered into Acquisition Activities by temporal analysis
6. Metadata extracted from each file
7. XML record built and validated
8. Record uploaded to CDCS

**File Finding Strategy:**
- Controlled by `NEXUSLIMS_FILE_STRATEGY` env var
- `exclusive`: Only files with known extractors
- `inclusive`: All files (with basic metadata for unknowns)

### Configuration

Environment variables are loaded from `.env` file (see `.env.example`):

**Critical paths:**
- `NX_INSTRUMENT_DATA_PATH`: Read-only mount of centralized instrument data
- `NX_DATA_PATH`: Writable parallel directory for metadata/previews
- `NX_DB_PATH`: SQLite database path
- `NX_LOG_PATH` (optional): Directory for application logs (defaults to `NX_DATA_PATH/logs/`)
- `NX_RECORDS_PATH` (optional): Directory for generated XML records (defaults to `NX_DATA_PATH/records/`)
- `NX_LOCAL_PROFILES_PATH` (optional): Directory for site-specific instrument profiles (loaded in addition to built-in profiles)

**NEMO integration:**
- Supports multiple NEMO instances via `NX_NEMO_ADDRESS_N`, `NX_NEMO_TOKEN_N` pattern
- Optional timezone/datetime format overrides per instance

**CDCS authentication:**
- `NX_CDCS_USER` / `NX_CDCS_PASS`: Credentials for CDCS uploads
- `NX_CDCS_URL`: Target CDCS instance URL

## Important Implementation Details

### Database Session States
Sessions progress through states in `session_log.record_status`:
- `WAITING_FOR_END`: Session started but not ended
- `TO_BE_BUILT`: Session ended, needs record generation
- `COMPLETED`: Record successfully built and uploaded
- `ERROR`: Record building failed
- `NO_FILES_FOUND`: No files found (may retry if within delay window)
- `NO_CONSENT`: A user did not consent to have their data harvested for the session
- `NO_RESERVATION`: There was no matching reservation found for this session

### File Delay Mechanism
`NX_FILE_DELAY_DAYS` controls retry window for NO_FILES_FOUND sessions. Record builder continues searching until delay expires.

### Instrument Database Requirements
Each instrument in `instruments` table must specify:
- `harvester`: "nemo" or "sharepoint"
- `filestore_path`: Relative to `NX_INSTRUMENT_DATA_PATH`
- `timezone`: For proper datetime handling
- NEMO-specific: `api_url`, `calendar_name` matching NEMO tool names

### Testing Infrastructure
- Uses `pytest` with `pytest-mpl` for image comparison tests
- Test fixtures in `tests/conftest.py` set up mock database/environments
- Many test data files are `.tar.gz` archives (extracted during test setup)
- Coverage reports generated in `tests/coverage/`

### Code Style
- Black formatting (88 char line length)
- isort for import sorting (Black profile)
- Ruff for linting (extensive rule set in pyproject.toml)
- Pylint with custom configuration
- NumPy-style docstrings

### Changelog management
- Changelog content is managed by the `towncrier` package
- Whenever adding a feature or making a significant change, create a corresponding changelog blurb in docs/changes at commit time
- When creating these blurbs, follow the instructions in `docs/changes/README.rst`

### Configuration Management (CRITICAL RULE)

**NEVER use `os.getenv()` or `os.environ` directly for configuration.**

All environment variable access MUST go through the `nexusLIMS.config` module:

```python
# ❌ WRONG - Do not do this
import os
path = os.getenv("NX_DATA_PATH")

# ✅ CORRECT - Always do this
from nexusLIMS import config
path = config.NX_DATA_PATH
```

**Why this rule exists:**
- Centralizes configuration management in one place
- Provides type safety and validation
- Enables proper default values and error handling
- Makes testing easier (can mock `config` module)
- Ensures consistent behavior across the codebase

**The only exception:** The `nexusLIMS/config.py` module itself, which is responsible for reading environment variables and exposing them as module-level attributes.

## Python Version Support

Supports Python 3.11 and 3.12 only (as specified in `pyproject.toml`).

## Development Notes

- This is a **fork** maintained by Datasophos, not affiliated with NIST
- Original NIST documentation may be outdated: https://pages.nist.gov/NexusLIMS
- **When adding new file format support**: Create an `ExtractorPlugin` subclass in `extractors/plugins/` - it will be auto-discovered
- **When customizing instrument behavior**: Create an `InstrumentProfile` in `extractors/plugins/profiles/` (built-in) or in the directory specified by `NX_LOCAL_PROFILES_PATH` (local/site-specific)
- HyperSpy is used extensively for reading/processing microscopy data
- The project structure mirrors the data structure: `NX_DATA_PATH` parallels `NX_INSTRUMENT_DATA_PATH`
