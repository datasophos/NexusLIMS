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

## Phase 3: CDCS Docker Service (Week 3) ✅ COMPLETED

- [x] Research nexuslims-cdcs-docker repository
- [x] Create `tests/integration/docker/cdcs/Dockerfile`
- [x] Create `tests/integration/docker/cdcs/docker-entrypoint.sh`
- [x] Create `tests/integration/docker/cdcs/init_schema.py`
- [x] Mount schema from source (no duplication via volume mount)
- [x] Add CDCS services to `docker-compose.yml`
- [x] Create `tests/integration/docker/cdcs/README.md`
- [ ] Test CDCS service manually (requires Docker daemon)

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

- **Completed Phases**: 3/9
- **Current Phase**: Phase 4 (Integration Test Fixtures)
- **Overall Progress**: 33%
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

### Phase 3 Completion Notes

Phase 3 CDCS Docker service is complete:
- Researched NexusLIMS-CDCS-Docker repository for architecture patterns
- Created comprehensive Dockerfile based on `datasophos/NexusLIMS-CDCS`:
  - Python 3.11-slim base image
  - Clones NexusLIMS-CDCS repository and installs dependencies
  - Runs as unprivileged `cdcs` user for security
- Implemented `docker-entrypoint.sh` initialization script:
  - Waits for PostgreSQL and MongoDB to be ready
  - Runs Django migrations and collects static files
  - Creates default superuser (admin/admin)
  - Runs schema initialization
  - Starts Celery worker and beat for background tasks
  - Starts uWSGI server on port 8080
- Created `init_schema.py` for automated schema loading:
  - Uploads Nexus Experiment XSD schema as CDCS template
  - Creates "NexusLIMS Test Workspace" for testing
  - Uses Django ORM for database operations
- Added four services to docker-compose.yml:
  - `cdcs-mongo`: MongoDB 7 for record storage
  - `cdcs-postgres`: PostgreSQL 16 for Django data
  - `cdcs-redis`: Redis 7 for Celery task queue
  - `cdcs`: Main Django/Curator application
- Schema file mounted as volume (no duplication):
  - Volume mount: `../../../nexusLIMS/schemas/nexus-experiment.xsd:/fixtures/nexus-experiment.xsd:ro`
  - Single source of truth for schema
  - Changes immediately reflected in tests
- Comprehensive health checks for all services:
  - MongoDB: mongosh ping check (5s interval)
  - PostgreSQL: pg_isready check (5s interval)
  - Redis: redis-cli ping check (5s interval)
  - CDCS: HTTP curl check (10s interval, 60s start period)
- Created extensive README.md documentation:
  - Architecture overview and service descriptions
  - Configuration and environment variables
  - Usage instructions and API endpoints
  - Health check details and initialization process
  - Troubleshooting guide with common issues
  - Development notes for schema updates and debugging
- **Enhancement to Phase 2**: Added idempotent initialization to both NEMO and CDCS:
  - NEMO uses `/nemo/.init_complete` marker file
  - CDCS uses `/srv/curator/.init_complete` marker file
  - Prevents duplicate data creation on container restart
  - Safe to run `docker compose restart` without `down -v`
  - Forces clean slate only when explicitly requested via `docker compose down -v`
