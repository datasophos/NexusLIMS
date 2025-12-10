# Integration Testing Implementation TODO

This file tracks progress on implementing Docker-based integration testing for NexusLIMS.

**Plan Reference**: `.claude/plans/implement-integration-testing.md`

## Phase 1: Project Restructuring (Week 1) ⏸️ PENDING

- [ ] Relocate existing tests to `tests/unit/`
  - [ ] Move all test files from `tests/` to `tests/unit/`
  - [ ] Update import paths where necessary
  - [ ] Verify all unit tests still pass after relocation
- [ ] Create integration test directory structure
- [ ] Add pytest markers to `tests/conftest.py`
- [ ] Create shared fixture module `tests/fixtures/shared_data.py`
- [ ] Update `pyproject.toml`
  - [ ] Add testpaths configuration
  - [ ] Add markers configuration
  - [ ] Add optional integration test dependencies

## Phase 2: NEMO Docker Service (Week 2) ⏸️ PENDING

- [ ] Create `tests/integration/docker/nemo/Dockerfile`
- [ ] Create `tests/integration/docker/nemo/init_data.py`
- [ ] Create `tests/integration/docker/nemo/fixtures/seed_data.json`
- [ ] Create `tests/integration/docker/nemo/wait-for-it.sh`
- [ ] Add NEMO service to `docker-compose.yml`
- [ ] Test NEMO service manually

## Phase 3: CDCS Docker Service (Week 3) ⏸️ PENDING

- [ ] Research nexuslims-cdcs-docker repository
- [ ] Create `tests/integration/docker/cdcs/Dockerfile`
- [ ] Create `tests/integration/docker/cdcs/init_schema.sh`
- [ ] Copy schema to `tests/integration/docker/cdcs/fixtures/`
- [ ] Add CDCS services to `docker-compose.yml`
- [ ] Test CDCS service manually

## Phase 4: Integration Test Fixtures (Week 4) ⏸️ PENDING

- [ ] Create `tests/integration/conftest.py` with fixtures
- [ ] Create `tests/integration/env/.env.integration`
- [ ] Add fixture documentation to `tests/integration/README.md`

## Phase 5: Basic Integration Tests (Week 5) ⏸️ PENDING

- [ ] Create `tests/integration/test_nemo_integration.py`
- [ ] Create `tests/integration/test_cdcs_integration.py`
- [ ] Run tests locally to verify

## Phase 6: End-to-End Tests (Week 6) ⏸️ PENDING

- [ ] Create `tests/integration/test_end_to_end.py`
- [ ] Create `tests/integration/test_error_scenarios.py`
- [ ] Add test data files to `tests/integration/data/`

## Phase 7: Docker Image Registry (Week 7) ⏸️ PENDING

- [ ] Create `.github/workflows/build-test-images.yml`
- [ ] Update `tests/integration/docker/docker-compose.ci.yml`
- [ ] Make images public in GitHub package settings

## Phase 8: CI/CD Integration (Week 8) ⏸️ PENDING

- [ ] Create `.github/workflows/integration-tests.yml`
- [ ] Update `.gitlab-ci.yml`
- [ ] Update `pyproject.toml` pytest configuration
- [ ] Add CI status badges to README.md

## Phase 9: Documentation (Week 9) ⏸️ PENDING

- [ ] Create `tests/integration/README.md`
- [ ] Create `docs/testing/integration-tests.md`
- [ ] Update `CONTRIBUTING.md`
- [ ] Add docstrings to all integration test files
- [ ] Create troubleshooting guide

## Progress Summary

- **Completed Phases**: 1/9
- **Current Phase**: Phase 2 - NEMO Docker Service
- **Overall Progress**: 11%

### Phase 1 Summary (Completed 2025-12-01)

Successfully restructured the test suite with clear separation between unit and integration tests:

**Files Created:**
- `tests/__init__.py` - Root test package documentation
- `tests/conftest.py` - Root pytest configuration with markers
- `tests/integration/__init__.py` - Integration test package
- `tests/fixtures/__init__.py` - Shared fixtures package
- `tests/fixtures/shared_data.py` - Shared test data for unit and integration tests

**Files Modified:**
- `tests/unit/conftest.py` - Updated pytest_plugins import paths
- `tests/unit/test_harvesters/conftest.py` - Updated pytest_plugins and import paths
- `pyproject.toml` - Added testpaths, markers, and pytest configuration

**Files Relocated:**
All existing test files moved from `tests/` to `tests/unit/` including:
- All `test_*.py` files
- `cli/`, `test_harvesters/`, `test_record_builder/`, `test_extractors/` directories
- `fixtures/`, `files/`, `dev/`, `nemo_api_schemas/` directories
- `conftest.py`, `utils.py`

**Verification:**
- ✅ Unit tests pass after relocation
- ✅ Import paths corrected
- ✅ Pytest markers registered
- ✅ Shared test data module created

## Notes

- All existing unit tests must pass after relocation before proceeding
- Keep minimal test data for speed
- Use GHCR for pre-built images in CI
- Integration tests should run on every PR

---

**Last Updated**: 2025-12-01
