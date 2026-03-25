# AGENTS.md

This file provides guidance to coding agents working with code in this repository.

## Project Overview

NexusLIMS is an electron microscopy Laboratory Information Management System (LIMS) originally developed at NIST, now maintained by Datasophos. It automatically generates experimental records by extracting metadata from microscopy data files and harvesting information from reservation calendar systems like NEMO.

This is the backend repository. The frontend is at <https://github.com/datasophos/NexusLIMS-CDCS>.

## Development Commands

### Package Management

This project uses `uv` for package management.

```bash
# Install dependencies
uv sync

# Add a dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>
```

### Testing

Tests should always be run with MPL comparison enabled.

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
uv run ruff format . --check
uv run ruff check nexusLIMS tests

# Auto-format code
uv run ruff format .

# Type checking
pyright
```

### Documentation

Always use `--skip-tui-demos` when building docs locally. TUI demo generation is slow and unnecessary for checking content.

```bash
# Build documentation (local)
./scripts/build_docs.sh --skip-tui-demos

# Build with strict mode (used in CI)
./scripts/build_docs.sh --strict --skip-tui-demos

# Watch mode for auto-rebuild during development
./scripts/build_docs.sh --watch --skip-tui-demos
```

Documentation will be written to `./_build`.

### Running the Record Builder

```bash
# Run the record builder with full orchestration
nexuslims build-records

# Or using the module directly:
uv run python -m nexusLIMS.cli.process_records

# Run in dry-run mode
nexuslims build-records -n

# Run with verbose output
nexuslims build-records -vv

# Run the core record builder directly
uv run python -m nexusLIMS.builder.record_builder
```

## Architecture Overview

### Core Components

1. **Database Layer** (`nexusLIMS/db/`)
   - SQLite database tracks instruments and session logs through Alembic migrations
   - Main tables: `instruments` and `session_log`
   - `models.py` defines SQLModel ORM classes `Instrument` and `SessionLog`
   - `enums.py` defines enums `EventType` and `RecordStatus`
   - `session_handler.py` provides higher-level session utilities

2. **Harvesters** (`nexusLIMS/harvesters/`)
   - Extract reservation and usage data from external systems
   - Primary harvester is NEMO in `nemo/`
   - SharePoint calendar support is deprecated

3. **Extractors** (`nexusLIMS/extractors/`)
   - Plugin-based metadata extraction
   - Plugins live in `extractors/plugins/`
   - Instrument profiles live in `extractors/plugins/profiles/`
   - Preview generators live in `extractors/plugins/preview_generators/`
   - Extractors return a dict with an `nx_meta` key for NexusLIMS-specific metadata

4. **Record Builder** (`nexusLIMS/builder/record_builder.py`)
   - Main orchestration entry point is `process_new_records()`
   - `build_record()` creates XML records conforming to the Nexus Experiment schema

5. **Schemas** (`nexusLIMS/schemas/`)
   - `activity.py` contains `AcquisitionActivity` and file clustering logic
   - XML schema validation is performed against `nexus-experiment.xsd`

6. **CDCS Integration** (`cdcs.py`)
   - Uploads records to the NexusLIMS CDCS frontend
   - Uses credentials and configuration from environment-driven app config

### Key Workflows

**Record Building Process**
1. NEMO harvester polls for new or ended reservations
2. Harvester creates `session_log` entries
3. Record builder finds sessions that are ready to build
4. Files are found using GNU `find`
5. Files are clustered into Acquisition Activities
6. Metadata is extracted
7. XML is built and validated
8. Record is uploaded to CDCS

**File Finding Strategy**
- Controlled by `NX_FILE_STRATEGY`
- `exclusive`: only files with known extractors
- `inclusive`: all files, with basic metadata for unknowns

## Configuration

Environment variables are loaded from `.env` file data. See `.env.example`.

Critical paths:
- `NX_INSTRUMENT_DATA_PATH`: read-only mount of centralized instrument data
- `NX_DATA_PATH`: writable parallel directory for metadata and previews
- `NX_DB_PATH`: SQLite database path
- `NX_LOG_PATH`: optional directory for logs, defaults under `NX_DATA_PATH`
- `NX_RECORDS_PATH`: optional directory for XML records, defaults under `NX_DATA_PATH`
- `NX_LOCAL_PROFILES_PATH`: optional directory for site-specific instrument profiles

NEMO integration:
- Supports multiple NEMO instances via `NX_NEMO_ADDRESS_N` and `NX_NEMO_TOKEN_N`
- Optional timezone and datetime format overrides may be set per instance

CDCS authentication:
- `NX_CDCS_TOKEN`
- `NX_CDCS_URL`

## Important Implementation Details

### Database Session States

Sessions progress through `session_log.record_status`:
- `WAITING_FOR_END`
- `TO_BE_BUILT`
- `COMPLETED`
- `ERROR`
- `NO_FILES_FOUND`
- `NO_CONSENT`
- `NO_RESERVATION`

### File Delay Mechanism

`NX_FILE_DELAY_DAYS` controls the retry window for `NO_FILES_FOUND` sessions.

### Instrument Database Requirements

Each instrument in `instruments` must specify:
- `harvester`: `nemo` or `sharepoint`
- `filestore_path`: relative to `NX_INSTRUMENT_DATA_PATH`
- `timezone`
- For NEMO-backed instruments, `api_url` matching NEMO tool names

### Testing Infrastructure

- Uses `pytest` with `pytest-mpl` for image comparison tests
- Test fixtures set up mock databases and environments
- Many test files are `.tar.gz` archives extracted during test setup
- Coverage reports are generated in `tests/coverage/`

### Code Style

- Ruff is used for formatting and linting
- Pyright is configured for type checking
- NumPy-style docstrings are preferred

### Changelog Management

- Changelog content is managed by `towncrier`
- When adding a feature or making a significant change, create a changelog blurb in `docs/changes`
- Follow the instructions in `docs/changes/README.rst`
- When preparing or cutting a release in Codex, use the `nexuslims-release` skill

### Configuration Management Rule

Never use `os.getenv()` or `os.environ` directly for application configuration access outside `nexusLIMS/config.py`.

```python
# Wrong
import os
path = os.getenv("NX_DATA_PATH")

# Correct
from nexusLIMS import config
path = config.NX_DATA_PATH
```

Why this rule exists:
- centralizes configuration management
- provides validation and defaults
- makes testing easier
- keeps configuration access consistent

The only exception is `nexusLIMS/config.py`, which is responsible for reading environment variables and exposing validated module-level attributes.

## Technical Notes

- See `docs/reference/textual_testing_reference.md` for Textual testing patterns used in this repo
- See `.claude/notes/zeroing-compressed-tiff-files.md` for the TIFF zeroing workflow referenced by past work in this repo
- When creating archive files on macOS, use `COPYFILE_DISABLE=1` so macOS metadata files are not included

## Python Version Support

Supports Python 3.11 and 3.12 only, as defined in `pyproject.toml`.

## Development Notes

- This is a fork maintained by Datasophos, not affiliated with NIST
- Original NIST documentation may be outdated: <https://pages.nist.gov/NexusLIMS>
- When adding new file format support, create an extractor plugin in `nexusLIMS/extractors/plugins/`
- When customizing instrument behavior, create an `InstrumentProfile` in `extractors/plugins/profiles/` or in the directory pointed to by `NX_LOCAL_PROFILES_PATH`
- HyperSpy is used extensively for reading and processing microscopy data
- The project structure mirrors the data structure: `NX_DATA_PATH` parallels `NX_INSTRUMENT_DATA_PATH`

### Developing Extractor Plugins

See `docs/writing_extractor_plugins.md` for detailed guidance.

Quick reference:
1. Create a class in `nexusLIMS/extractors/plugins/` with:
   - `name`
   - `priority`
   - `supported_extensions`
   - `supports(context: ExtractionContext) -> bool`
   - `extract(context: ExtractionContext) -> dict[str, Any]`
2. Return a dict with an `nx_meta` key containing:
   - `DatasetType`
   - `Data Type`
   - `Creation Time`
3. The registry auto-discovers plugins on first use

Key patterns:
- use priority-based selection
- use `supports()` for content sniffing beyond extension checks
- check `context.instrument` for instrument-specific behavior
- handle missing or corrupted files gracefully
- add tests under `tests/unit/test_extractors/`
