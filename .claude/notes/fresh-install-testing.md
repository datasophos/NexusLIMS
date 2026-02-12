# Fresh Install Testing

## Issue Discovered

You were absolutely right to ask about this! Our test suite was missing validation for the "fresh install" user experience - what happens when someone runs `pip install nexusLIMS` without any `.env` file or environment variables set up.

## What We Found

### Current Behavior (GOOD)

When a user installs NexusLIMS without configuration:

1. ✅ **Help commands work** - All `--help` flags work without requiring configuration:
   ```bash
   nexuslims-config --help      # Works
   nexuslims-migrate --help     # Works
   nexuslims-manage-instruments --help  # Works
   nexuslims-process-records --help     # Works
   ```

2. ✅ **Clear error messages** - Attempting to actually use the package fails with helpful errors:
   ```
   ValidationError: 5 validation errors for Settings
   NX_INSTRUMENT_DATA_PATH - Field required
   NX_DATA_PATH - Field required
   NX_DB_PATH - Field required
   NX_CDCS_TOKEN - Field required
   NX_CDCS_URL - Field required

   ================================================================================
   NexusLIMS configuration validation failed.
   See https://datasophos.github.io/NexusLIMS/2.4.2/user_guide/configuration.html
   for complete environment variable reference.
   ================================================================================
   ```

3. ✅ **Documentation link provided** - The error points users to the configuration documentation

### Potential Issue (MINOR)

`NX_DB_PATH` uses `FilePath` validation which requires the file to **already exist**. However, the documentation says "The database is created automatically on first run of `nexuslims-migrate init`". This creates a chicken-and-egg problem for fresh installs.

**Workaround:** Users can `touch` an empty file before first run, or run `nexuslims-migrate init` which likely handles this.

**Possible fix:** Change `NX_DB_PATH` type from `TestAwareFilePath` to `TestAwarePath` (no existence check). The database layer already handles creating the file if it doesn't exist.

## New Test Coverage

Created `tests/integration/test_fresh_install.py` with two tests:

### 1. `test_fresh_install_without_config`

Validates the fresh install experience:
- Installs package in clean venv without any environment variables
- Verifies `--help` commands work (no config needed)
- Verifies import fails with clear error when config missing
- Verifies import succeeds after setting minimal config

**Key insight:** Had to use a clean subprocess environment (no `NX_TEST_MODE`) to properly simulate production behavior. All our other tests run with `NX_TEST_MODE` enabled, which disables validation.

### 2. `test_smoke_test_script_with_built_wheel`

Meta-test that validates the smoke test script itself:
- Runs `scripts/smoke_test_package.sh` against built wheel
- Verifies all 6 smoke test sections pass
- Ensures the smoke test catches real packaging issues

## Key Differences

| Scenario | Environment | Purpose |
|----------|-------------|---------|
| **Unit/Integration Tests** | `NX_TEST_MODE=1` | Test code logic with mocked dependencies |
| **Fresh Install Test** | Clean env (no TEST_MODE) | Test first-time user experience |
| **Smoke Test** | Clean env + minimal config | Test installed package works correctly |

## Recommendations

1. ✅ **Keep the fresh install test** - It's the only test that validates production config validation
2. ✅ **Keep the smoke test** - It validates the installed package works end-to-end
3. ⚠️ **Consider relaxing `NX_DB_PATH` validation** - Change from `FilePath` to `Path` to allow non-existent paths (the DB layer creates it anyway)
4. ✅ **Current error messages are good** - Clear, actionable, with documentation links

## What This Means for Issue #58

The package installation smoke test (Issue #58) now has two layers of validation:

1. **CI Smoke Test** (`scripts/smoke_test_package.sh` in GitHub Actions)
   - Runs on every release tag
   - Tests 4 platform combinations (Python 3.11/3.12 × Ubuntu/macOS)
   - Validates installed package works with proper configuration

2. **Fresh Install Test** (`tests/integration/test_fresh_install.py`)
   - Runs in integration test suite
   - Validates user experience without configuration
   - Ensures error messages are helpful for new users

Both are important and complementary!
