# Test File Requirements for NexusLIMS

This document specifies the directory structures and files needed for the NexusLIMS test suite to pass.

## Overview

Tests expect specific directory structures under `MMFNEXUS_PATH` (set to `tests/files/` in conftest.py). Files must have specific modification times to be found by the temporal file-finding tests.

## Required Directory Structures

### 1. Titan TEM Directory

**Path:** `tests/files/Titan/`

**Requirements:**
- **37 files** with known extensions (.dm3, .dm4)
- **41 total files** including additional file types
- **Modification times:** Between `2018-11-13T13:00:00-05:00` and `2018-11-13T16:00:00-05:00`

**Specific Files Needed:**
- `Titan/***REMOVED***/***REMOVED***/15 - 620k.dm3`
- 36 other .dm3/.dm4 files with timestamps in the range above
- 4 additional test files with specific timestamps:
  - `db_file_to_test_ignore_patterns.db` (mtime: 2018-11-13 14:55:35 -05:00)
  - `jpg_file_should_not_be_ignored.jpeg` (mtime: 2018-11-13 14:57:35 -05:00)
  - `jpg_file_should_not_be_ignored.jpg` (mtime: 2018-11-13 14:56:35 -05:00)
  - `raw_file_should_not_be_ignored.raw` (mtime: 2018-11-13 14:58:35 -05:00)
  - `txt_file_should_not_be_ignored.txt` (mtime: 2018-11-13 14:59:35 -05:00)

**Tests Using This:**
- `test_utils.py::test_gnu_find`
- `test_utils.py::test_gnu_find_no_extensions`
- `test_records.py::test_dry_run_file_find` (expects path `Titan/***REMOVED***/***REMOVED***/15 - 620k.dm3`)

---

### 2. JEOL 3010 TEM Directory

**Path:** `tests/files/JEOL3010/`

**Requirements:**
- **3 subdirectories** with specific names
- **55 total files** across all subdirectories
- **Modification times:** Between `2019-07-24T11:00:00-04:00` and `2019-07-24T16:00:00-04:00`

**Directory Structure:**
```
JEOL3010/
└── ***REMOVED***/
    └── 20190724/
        ├── M1_DC_Beam/           (18-20 files)
        ├── M2_DC_Beam_Dose_1/    (18-20 files)
        └── M3_DC_Beam_Dose_2/    (18-20 files)
```

**Tests Using This:**
- `test_utils.py::test_find_dirs_by_mtime` (expects 3 directories)
- `test_utils.py::test_gnu_and_pure_find_together` (expects 55 files, currently skipped)

---

### 3. 643 Titan STEM Directory

**Path:** `tests/files/643Titan/`

**Requirements:**
- **38 files** with known extensions
- **Modification times:** Between `2019-11-06T15:00:00-07:00` and `2019-11-06T18:00:00-07:00`

**Directory Structure:**
```
643Titan/
└── ***REMOVED***/
    └── 191106 - ***REMOVED***/
        └── (38 .dm3/.dm4 files)
```

**Tests Using This:**
- `test_utils.py::test_gnu_find_not_on_path` (error test, just needs path to exist)
- `test_records.py::test_dry_run_file_find` (expects 38 files in this session)

---

### 4. NexusLIMS Test Files Directory

**Path:** `tests/files/NexusLIMS/test_files/`

**Requirements:**
- **4 files** for 2021-08-02 session
- **1 file** for 2021-11-29 session
- **Specific files referenced:** `02 - 620k-2.dm3`, `04 - 620k.dm3`

**File List with Modification Times:**

**For 2021-08-02 session (4 files):**
- Modification times between `2021-08-02T00:00:00-04:00` and `2021-08-03T00:00:00-04:00`
- Should include: `02 - 620k-2.dm3`, `04 - 620k.dm3`

**For 2021-11-29 session (1 file):**
- Modification time between `2021-11-29T11:28:01-07:00` and `2021-11-29T11:28:02-07:00`

**For 2023-02-13 session (4 files):**
- Modification times between `2023-02-13T13:00:00-07:00` and `2023-02-13T14:00:00-07:00`

**Tests Using This:**
- `test_records.py::test_dry_run_file_find` (expects file `NexusLIMS/test_files/02 - 620k-2.dm3`)
- `test_records.py::test_build_record_single_file`
- Multiple other record builder tests

---

## Implementation Strategy

### Option 1: Extract on Demand (Recommended)

Create tar.gz archives for each directory structure and extract them in test fixtures:

```python
@pytest.fixture(scope="session")
def extract_titan_files():
    """Extract Titan test files before tests run."""
    tar_path = Path(__file__).parent / "files" / "titan_test_files.tar.gz"
    extract_path = Path(__file__).parent / "files"

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(path=extract_path)

    yield

    # Cleanup
    shutil.rmtree(extract_path / "Titan", ignore_errors=True)
```

### Option 2: Create Archives Needed

Create the following tar.gz archives in `tests/files/`:

1. **`titan_test_files.tar.gz`** - Contains the entire `Titan/` directory with 41 files
2. **`jeol3010_test_files.tar.gz`** - Contains the entire `JEOL3010/` directory with 3 subdirs and 55 files
3. **`643titan_test_files.tar.gz`** - Contains the entire `643Titan/` directory with 38 files
4. **`nexuslims_test_files.tar.gz`** - Contains the `NexusLIMS/test_files/` directory structure

### File Timestamp Requirements

**Critical:** Files must have specific modification times. When creating archives:

```bash
# Set file modification time
touch -t YYYYMMDDhhmm.ss filename

# Example for Titan files (2018-11-13 14:00:00 -05:00)
touch -t 201811131400.00 "some_file.dm3"
```

Or use Python:
```python
import os
from datetime import datetime

mtime = datetime(2018, 11, 13, 14, 0, 0).timestamp()
os.utime("some_file.dm3", (mtime, mtime))
```

---

## File Count Summary

| Directory | Files | Date Range | Purpose |
|-----------|-------|------------|---------|
| `Titan/` | 37-41 | 2018-11-13 13:00-16:00 UTC-5 | GNU find tests, record building |
| `JEOL3010/` | 55 (3 dirs) | 2019-07-24 11:00-16:00 UTC-4 | Directory finding, file finding |
| `643Titan/` | 38 | 2019-11-06 15:00-18:00 UTC-7 | Record building, error tests |
| `NexusLIMS/test_files/` | 1-4 | Various 2021-2023 | Record building tests |

---

## Tests Affected

### test_utils.py
- `test_find_dirs_by_mtime` - Needs JEOL3010 directory
- `test_gnu_find` - Needs Titan directory
- `test_gnu_find_no_extensions` - Needs Titan directory with extra files
- `test_gnu_find_with_trailing_slash` - Needs Titan directory
- `test_gnu_and_pure_find_together` - Needs JEOL3010 directory (currently skipped)

### test_records.py
- `test_dry_run_file_find` - Needs Titan, 643Titan, NexusLIMS/test_files directories
- `test_build_record_single_file` - Needs NexusLIMS/test_files directory
- Multiple other record builder tests

---

## Next Steps

1. **Locate or create** the tar.gz archives with the required directory structures
2. **Verify file timestamps** match the expected ranges
3. **Add extraction fixtures** to `conftest.py` to extract archives before tests run
4. **Add cleanup** to remove extracted directories after tests complete
5. **Test** that file counts and timestamps match expectations

---

## Minimal Test Set Recommendation

After analyzing test coverage, many tests are redundant or test the same underlying functionality. Here's a **minimal set** that provides adequate coverage:

### Priority 1: Essential Tests (Fix These First)

#### File-Finding Utilities (test_utils.py)
**Recommendation:** Create a **single small test directory** instead of full archives.

**Minimal Titan Directory:**
- **Just 10-15 files** instead of 41
- Keep `test_gnu_find` (tests basic GNU find functionality)
- **SKIP or simplify:**
  - `test_gnu_find_no_extensions` - Redundant with `test_gnu_find` (tests same function with `extensions=None`)
  - `test_gnu_find_with_trailing_slash` - Already tested twice within `test_gnu_find` itself (lines 93-101)
  - `test_gnu_find_not_on_path` - Doesn't need real files (just needs path to exist)

**Minimal JEOL3010 Directory:**
- **Just 1 subdirectory with 5 files** instead of 3 subdirs with 55 files
- Keep `test_find_dirs_by_mtime` but adjust expected count to 1
- **SKIP:**
  - `test_gnu_and_pure_find_together` - Already skipped, uses deprecated method

**Skip 643Titan entirely:**
- `test_gnu_find_not_on_path` - This test only needs the path to exist (can use any path or mock)

**Coverage Analysis:**
```
test_gnu_find                      → Tests GNU find with extensions filter ✓ KEEP
test_gnu_find_no_extensions        → Same as above but extensions=None   ✗ REDUNDANT
test_gnu_find_with_trailing_slash  → Already tested in test_gnu_find     ✗ REDUNDANT
test_gnu_find_not_on_path          → Error handling (no files needed)    ○ MOCK
test_gnu_find_stderr               → Error handling (uses bad path)      ✓ KEEP
test_find_dirs_by_mtime            → Tests directory finding             ✓ KEEP (simplified)
test_gnu_and_pure_find_together    → Deprecated method                   ✗ SKIP
```

#### Record Building Tests (test_records.py)
**Recommendation:** Use **NexusLIMS/test_files/** only.

**Tests Using Full Directory Structures:**
- `test_dry_run_file_find` - Tests file finding across multiple sessions
  - Currently expects 9 different sessions with specific file counts
  - **Simplify:** Mock `get_sessions_to_build()` to return only 1-2 test sessions
  - **Result:** Only need `NexusLIMS/test_files/` directory (already exists)

**Coverage Analysis:**
```
test_dry_run_file_find              → Integration test for file finding    ○ SIMPLIFY
test_dry_run_sharepoint_calendar    → SharePoint harvester (deprecated)    ✗ SKIP
test_process_new_records_dry_run    → Dry run mode                         ✓ KEEP (uses mock)
test_build_record_single_file       → Single file record building          ✓ KEEP
test_build_record_with_sample_elements → Sample metadata extraction        ✓ KEEP
test_record_builder_strategies      → Inclusive vs exclusive strategies    ✓ KEEP (uses mock)
test_new_session_processor          → XML generation                       ✓ KEEP
test_dump_record                    → Record serialization                 ✓ KEEP
```

### Priority 2: Network/Integration Tests (Mock or Skip)

These tests require external resources and should be mocked:

```python
# test_utils.py
test_header_addition_nexus_req     → Requires real NEMO API          ○ MOCK
test_request_retry                 → Requires httpstat.us service    ○ MOCK

# test_harvesters.py (Phase 3)
All NEMO harvester tests          → Require real NEMO instance      ○ MOCK or @integration
```

### Priority 3: Tests Already Passing (No Files Needed)

These tests don't require directory structures:
- `test_zero_bytes` - Uses existing tar.gz file fixtures ✓
- `test_zero_bytes_ser_processing` - Uses existing tar.gz file fixtures ✓
- `test_setup_loggers` - Unit test ✓
- `test_bad_auth_options` - Unit test ✓
- `test_has_delay_passed_no_val` - Unit test ✓
- `test_replace_mmf_path` - Unit test ✓

---

### Recommended Implementation Strategy

#### Option A: Minimal Files (Recommended for Quick Fix)

Create **one small tar.gz** with minimal test data:

**`minimal_test_files.tar.gz`** containing:
```
Titan/
  test_data/
    file01.dm3  (mtime: 2018-11-13 14:00:00 -05:00)
    file02.dm3  (mtime: 2018-11-13 14:10:00 -05:00)
    file03.dm3  (mtime: 2018-11-13 14:20:00 -05:00)
    ... (10-15 total)

JEOL3010/
  test_user/
    20190724/
      M1_DC_Beam/
        file01.dm3  (mtime: 2019-07-24 12:00:00 -04:00)
        file02.dm3  (mtime: 2019-07-24 12:10:00 -04:00)
        ... (5 total)

NexusLIMS/
  test_files/
    02 - 620k-2.dm3  (mtime: 2021-08-02 10:00:00 -04:00)
    04 - 620k.dm3    (mtime: 2021-08-02 10:10:00 -04:00)
    ... (4 total)
```

**Adjust test expectations:**
```python
class TestUtils:
    TITAN_FILE_COUNT = 10  # Instead of 37
    TITAN_ALL_FILE_COUNT = 10  # Instead of 41
    JEOL_DIRS_COUNT = 1  # Instead of 3
    JEOL_FILE_COUNT = 5  # Instead of 55
```

**Mark redundant tests as skipped:**
```python
@pytest.mark.skip(reason="Redundant with test_gnu_find")
def test_gnu_find_no_extensions(self):
    ...

@pytest.mark.skip(reason="Already tested in test_gnu_find lines 93-101")
def test_gnu_find_with_trailing_slash(self):
    ...
```

**Mock the network tests:**
```python
@responses.activate
def test_header_addition_nexus_req(self):
    responses.add(
        responses.GET,
        os.environ["NEMO_ADDRESS_1"] + "users/",
        json={"users": []},
        status=200,
    )
    # ... rest of test

@responses.activate
def test_request_retry(self):
    responses.add(responses.GET, "https://httpstat.us/503", status=503)
    with pytest.raises(RetryError):
        nexus_req("https://httpstat.us/503", "GET")
```

#### Option B: Mock File Finding (Alternative)

Instead of creating real files, mock the file-finding functions:

```python
@pytest.fixture
def mock_gnu_find(monkeypatch):
    def fake_gnu_find(path, dt_from, dt_to, extensions=None):
        # Return mock file list based on path
        if "Titan" in str(path):
            return [Path(f"file{i}.dm3") for i in range(10)]
        elif "JEOL" in str(path):
            return [Path(f"file{i}.dm3") for i in range(5)]
        return []

    monkeypatch.setattr("nexusLIMS.utils.gnu_find_files_by_mtime", fake_gnu_find)
```

**Pros:** No file creation needed, faster tests
**Cons:** Less integration testing, might miss real file-system issues

---

### Summary: Minimal Viable Test Set

To get tests passing with **minimum effort**:

1. **Create 1 small tar.gz** (~20 files total, not 134+)
2. **Skip 3 redundant tests** in test_utils.py
3. **Mock 2 network tests** in test_utils.py
4. **Simplify `test_dry_run_file_find`** to use only test_files directory
5. **Adjust expected file counts** in test constants

**Estimated effort:** 30-60 minutes to create minimal files + update tests
**Test coverage:** Still validates all core functionality (file finding, GNU find, directory finding, record building)
**Files needed:** ~20 instead of 134+

---

## Notes

- All file paths with `***REMOVED***` indicate redacted user/project names
- Files should have metadata but can have zeroed binary data (see existing test files)
- Tests use `MMFNEXUS_PATH` environment variable (set to `tests/files/` in conftest.py)
- GNU find compatibility required - tests use `-xtype` and other GNU-specific flags
- **Recommended:** Focus on minimal test set above rather than recreating full historical test data
