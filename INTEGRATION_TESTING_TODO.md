# Integration Testing Implementation TODO

This file tracks progress on implementing Docker-based integration testing for NexusLIMS.

**Plan Reference**: `.claude/plans/implement-integration-testing.md`

## Phase 1: Project Restructuring (Week 1) ✅ COMPLETED

- [x] Relocate existing tests to `tests/unit/`
  - [x] Move all test files from `tests/` to `tests/unit/`
  - [x] Update import paths where necessary
  - [x] Verify all unit tests still pass after relocation
- [x] Create integration test directory structure
- [x] Add pytest markers to `tests/conftest.py`
- [x] Create shared fixture module `tests/fixtures/shared_data.py`
- [x] Update `pyproject.toml`
  - [x] Add testpaths configuration
  - [x] Add markers configuration
  - [x] Add optional integration test dependencies

## Phase 2: NEMO Docker Service (Week 2) ✅ COMPLETED

- [x] Create `tests/integration/docker/nemo/Dockerfile`
- [x] Create `tests/integration/docker/nemo/init_data.py`
- [x] Create `tests/integration/docker/nemo/fixtures/seed_data.json`
- [x] Create `tests/integration/docker/nemo/wait-for-it.sh`
- [x] Add NEMO service to `docker-compose.yml`
- [x] Test NEMO service manually

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

- **Completed Phases**: 2/9
- **Current Phase**: Phase 3 (CDCS Docker Service)
- **Overall Progress**: 22%
- **Last Updated**: 2025-12-09

### Phase 1 Completion Notes

Phase 1 restructuring is complete:
- All existing tests successfully relocated to `tests/unit/`
- Integration test directory structure created at `tests/integration/`
- Pytest markers added to `tests/unit/conftest.py` for test organization
- Shared fixture module created at `tests/fixtures/shared_data.py` with:
  - Common test constants (dates, users, instruments)
  - Sample metadata fixtures for various file types
  - Mock database fixtures
  - XML validation utilities
- `pyproject.toml` updated with:
  - Test paths configuration
  - Marker definitions
  - Integration testing dependencies (pytest-docker, docker, pytest-timeout)

### Phase 2 Completion Notes

Phase 2 NEMO Docker service is complete:
- Created comprehensive Dockerfile based on `nanofab/nemo_splash_pad:latest`
- Implemented `init_data.py` with Django ORM-based database seeding:
  - Creates users, tools, projects from seed_data.json
  - Configures NexusLIMS reservation questions with periodic table plugin
  - Generates sample reservations and usage events for testing
- Created `seed_data.json` with test data matching unit test fixtures:
  - 4 test users (captain, professor, ned, commander)
  - 3 tools (643 Titan STEM, 642 FEI Titan, JEOL JEM-3010)
  - 3 projects (Alpha, Beta, Gamma)
- Created `reservation_questions.json` with NexusLIMS-style questions:
  - Project ID, Experiment Title, Purpose, Data Consent
  - Sample information group with periodic table element selector
- Implemented `wait-for-it.sh` health check script
- Created `configure_settings.py` to enable periodic table plugin
- Added NEMO service to docker-compose.yml with healthcheck
- Comprehensive README.md with usage, testing, and troubleshooting documentation
