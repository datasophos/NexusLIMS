# Metadata reference

This folder contains plain-text/JSON dumps of the raw metadata for each of the test files for easy reference, such as the `original_metadata` attribute for HyperSpy signals, etc.

## Contents

The JSON files in this directory contain the `original_metadata` field extracted from HyperSpy-readable test files. Each file is formatted with:
- 2-space indentation
- Sorted keys for consistent comparison
- String representation for non-JSON-serializable types

## File Naming Convention

- Single-signal files: `{original_filename}_original_metadata.json`
- Multi-signal files: `{original_filename}_signal_{index}_original_metadata.json`

## Regenerating These Files

To regenerate the metadata reference files, run the extraction script from this directory:

```bash
cd tests/unit/files/metadata_references
uv run python extract_original_metadata.py
```

Or from the project root:

```bash
uv run python tests/unit/files/metadata_references/extract_original_metadata.py
```

This script:
1. Iterates through all test file archives in `tests/unit/files/*.tar.gz`
2. Extracts files readable by HyperSpy
3. Dumps their `original_metadata` as formatted JSON
4. Saves them to this directory

The script automatically sets up a test environment (mimicking `tests/unit/conftest.py`) to ensure proper access to test files.
