# Test File Structure

This document describes the sanitized, minimal test file structure for NexusLIMS.

## Overview

Test files have been aggressively pruned and sanitized to:
- **Reduce repository size** from ~1.4GB to ~400MB (72% reduction)
- **Remove sensitive information** (usernames, people's names, sample IDs)
- **Maintain test coverage** for file-finding and record building functionality

## Directory Structure

```
tests/files/
├── Titan_TEM/
│   └── researcher_a/
│       └── project_alpha/
│           └── 20181113/
│               ├── image_001.dm3 through image_008.dm3 (8 .dm3 files)
│               ├── scan_001.emi (1 .emi file)
│               ├── scan_001_1.ser, scan_001_2.ser (2 .ser files)
│               └── test_ignore.db, test_include.{jpg,jpeg,raw,txt} (5 test files)
│               Total: 16 files (~165MB)
│
├── JEOL3010/
│   └── JEOL3010/
│       └── researcher_b/
│           └── project_beta/
│               └── 20190724/
│                   ├── beam_study_1/ (2 files)
│                   ├── beam_study_2/ (3 files)
│                   └── beam_study_3/ (3 files)
│                   Total: 8 files (~164MB)
│
├── NexusLIMS/
│   └── test_files/
│       ├── sample_001.dm3 through sample_004.dm3 (4 files)
│       Total: 4 files (~66MB)
│
└── *.tar.gz (33 archive files for specific extractor tests)
```

## File Counts Summary

| Directory | Files | Extractable | Size | Purpose |
|-----------|-------|-------------|------|---------|
| Titan_TEM | 16 | 10 (.dm3, .ser) | 165MB | GNU find tests, clustering |
| JEOL3010 | 8 | 8 | 164MB | Directory finding |
| NexusLIMS/test_files | 4 | 4 | 66MB | Basic record building |
| **Total** | **28** | **22** | **~400MB** | |

**Previous structure:** 93 files, ~1.4GB

## Temporal Clustering

The Titan_TEM files are organized into temporal clusters for testing acquisition activity detection:

- **Cluster 1** (11:01-11:19): 3 files - Early morning imaging session
- **Cluster 2** (12:02-12:55): 5 files - Midday imaging session  
- **Cluster 3** (13:10-13:22): 1 file - Scanning/analysis session (.emi)
- **Cluster 4** (13:27:18): 2 files - Serial data acquisition (.ser pair)

## Sanitization

### Removed Information

- **Usernames:** `mbk1` → `researcher_a`, `hnc24` → `researcher_b`
- **Names:** `Eric Lass` → removed from path
- **Sample IDs:** `AM 17-4 - 1050C` → `project_alpha`, `C36_Paraffin` → `project_beta`
- **Directory names:** `M1_DC_Beam` → `beam_study_1`, etc.

### File Naming

- Titan images: `image_001.dm3` through `image_008.dm3` (sequential, generic)
- Scans: `scan_001.emi`, `scan_001_1.ser`, `scan_001_2.ser` (descriptive, generic)
- Test files: `test_ignore.db`, `test_include.{ext}` (explicit purpose)
- JEOL files: Original filenames preserved (already generic)
- NexusLIMS: `sample_001.dm3` through `sample_004.dm3` (generic)

## Modification Times

All file and directory modification times are preserved from original test data:

- **Titan_TEM:** 2018-11-13 11:00-13:30 (EST, UTC-5)
- **JEOL3010 directories:** 2019-07-24 12:00-12:30 (EDT, UTC-4)
- **NexusLIMS:** Multiple dates (2021-08-02, 2021-11-29, 2023-02-13)

These timestamps are critical for temporal file-finding tests.

## Test Coverage

### Passing Tests (test_utils.py)

- ✅ `test_gnu_find` - Tests finding 10 extractable files in Titan_TEM
- ✅ `test_find_dirs_by_mtime` - Tests finding 3 JEOL subdirectories
- ✅ All other utility tests (19/22 passing, 3 skipped)

### Expected Test Modifications

Some record building tests (e.g., `test_activity_repr`) may need assertion updates due to:
- Reduced file counts changing cluster timestamps
- Different activity boundaries with minimal file set
- Timezone differences in extracted metadata

## Maintenance

### Adding Test Files

To add new test files:
1. Place file in appropriate instrument directory
2. Set modification time: `touch -t YYYYMMDDhhmm filename`
3. Update test constants in `tests/test_utils.py` if count changes
4. Ensure filenames follow sanitized naming convention

### Updating Test Constants

Current test constants in `tests/test_utils.py`:
```python
TITAN_FILE_COUNT = 10  # Files with known extensions (.dm3, .ser) - excludes .emi
TITAN_ALL_FILE_COUNT = 16  # All files including .db, .jpg, .jpeg, .raw, .txt, .emi
JEOL_DIRS_COUNT = 3  # beam_study_1, beam_study_2, beam_study_3
JEOL_FILE_COUNT = 8  # Total files across all JEOL3010 subdirectories
```

## Archive Files

The 33 `.tar.gz` archive files contain:
- Test database (`test_db.sqlite.tar.gz`)
- Specific file format examples for extractor tests
- EELS, EDS, FFT, and other specialized data files

These archives are extracted during test setup and remain compressed in the repository.

## Implementation Date

File structure created: 2025-11-18

Original structure removed: 2025-11-18

## Related Documentation

- `TEST_SUITE_FIXES.md` - Overall test suite status and fixes
- `TEST_FILE_REQUIREMENTS.md` - Original file requirements analysis
- `tests/conftest.py` - Test fixtures and database setup
- `tests/test_instrument_factory.py` - Instrument factory for tests
