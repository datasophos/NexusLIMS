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
- [x] Test CDCS service manually (requires Docker daemon)

## Phase 4: Integration Test Fixtures (Week 4) ✅ COMPLETED

- [x] Create `tests/integration/conftest.py` with fixtures
- [x] Create `tests/integration/env/.env.integration`
- [x] Add fixture documentation to `tests/integration/README.md`

## Phase 5: Basic Integration Tests (Week 5) ✅ COMPLETED

- [x] Create `tests/integration/test_nemo_integration.py` (883 lines, comprehensive)
- [x] Create `tests/integration/test_cdcs_integration.py` (478 lines, 100% coverage)
- [x] Create `tests/integration/test_fixtures_smoke.py` (98 lines)
- [x] Run tests locally to verify
- [x] **Enhancement**: Add Caddy fileserver for serving test instrument data
- [x] **Enhancement**: Add Caddy reverse proxy for friendly URLs (nemo.localhost, cdcs.localhost)

## Phase 6: End-to-End Tests (Week 6) 🚧 IN PROGRESS

**Status**: Coverage gap analysis completed, implementation pending

### Critical Missing Tests (High Priority)
- [x] **End-to-End Workflow Test** (CRITICAL)
  - [x] Test complete `process_new_records()` workflow: NEMO → Record Builder → CDCS
  - [x] Verify NEMO usage event → Session → Record → CDCS upload
  - [x] Verify session_log.record_status transitions (TO_BE_BUILT → COMPLETED)
  - [x] Test file clustering into Acquisition Activities
  - [x] Test metadata extraction and XML generation

- [ ] **Partial Failure Recovery** (CRITICAL)
  - [ ] Test NEMO succeeds but CDCS fails → verify database rollback
  - [ ] Test database transaction handling on external service failures
  - [ ] Test session state after partial failures
  - [ ] Test error propagation and logging

- [ ] **Network Resilience** (HIGH)
  - [ ] Test retry logic on 502/503/504 errors (currently untested)
  - [ ] Test timeout handling (no timeout parameter currently)
  - [ ] Test connection failures mid-request
  - [ ] Test rate limiting (429) handling
  
- [ ] **Default entrypoint handling** (HIGH)
  - [ ] Add test SMTP to docker integration stack to test email sending behavior
  - [ ] Fully exercise behavior of the nexuslims-process-records script

### Medium Priority Tests
- [ ] **Multi-Instance Support**
  - [ ] Test multiple NEMO instances (NX_NEMO_ADDRESS_1, NX_NEMO_ADDRESS_2)
  - [ ] Test `get_connector_for_session()` instance selection
  - [ ] Test instance-specific timezone/datetime formats

- [ ] **Large Dataset Handling**
  - [ ] Test pagination for >1000 reservations/events
  - [ ] Test bulk record operations (100+ records)
  - [ ] Test performance with large file sets

- [ ] **Authentication Edge Cases**
  - [ ] Test NTLM authentication for CDCS (Windows-integrated auth)
  - [ ] Test NEMO token expiration/refresh
  - [ ] Test credential validation at startup

### Coverage Gaps Identified
- [x] Create `tests/integration/test_end_to_end_workflow.py`
- [ ] Create `tests/integration/test_error_scenarios.py`
- [ ] Create `tests/integration/test_network_resilience.py`
- [x] Add mock instrument files for record building tests

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

- **Completed Phases**: 5/9
- **Current Phase**: Phase 6 (End-to-End Tests) - In Progress
- **Overall Progress**: 58%
- **Last Updated**: 2025-12-12
- **Test Files**: 3 (1,459 total lines)
- **Docker Services**: 7 (NEMO, CDCS, Postgres, MongoDB, Redis, Fileserver, Caddy Proxy)

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

### Phase 4 Completion Notes

Phase 4 integration test fixtures are complete:
- Created comprehensive `tests/integration/conftest.py` with session-scoped fixtures:
  - `docker_services`: Manages Docker Compose lifecycle (start/health check/teardown)
  - `docker_services_running`: Provides service URLs and status
  - NEMO fixtures: `nemo_url`, `nemo_api_url`, `nemo_client`, `nemo_test_users`, `nemo_test_tools`
  - CDCS fixtures: `cdcs_url`, `cdcs_credentials`, `cdcs_client` (with automatic record cleanup)
  - Database fixtures: `test_database`, `populated_test_database` (with sample instruments)
  - Test data fixtures: `test_data_dirs`, `sample_microscopy_files`
  - Utility fixtures: `wait_for_service`, `integration_test_marker`
- Created `tests/integration/env/.env.integration` with comprehensive environment configuration:
  - NEMO connection settings (URL, token, timezone)
  - CDCS connection settings (URL, credentials)
  - Test data paths (instrument data, NexusLIMS data, database, logs, records)
  - File strategy configuration
  - Fileserver URLs for XSLT rendering
  - Optional settings (profiles, SSL, email, debug)
- Created comprehensive `tests/integration/README.md` with:
  - Quick start guide
  - Architecture diagrams and service descriptions
  - Complete fixture documentation with usage examples
  - Writing integration tests best practices
  - Test markers (integration, e2e, slow)
  - Environment variables reference
  - Troubleshooting guide
  - Performance optimization tips
  - CI/CD integration notes
- Created `tests/integration/test_fixtures_smoke.py` for validating fixtures:
  - Tests for all Docker service fixtures
  - Tests for all NEMO fixtures
  - Tests for all CDCS fixtures
  - Tests for all database fixtures
  - Tests for all data fixtures
  - Tests for all utility fixtures
- All fixtures use proper dependency injection and cleanup mechanisms
- Fixtures patch `nexusLIMS.config` module instead of environment variables directly
- Session-scoped fixtures minimize Docker service startup overhead
- Automatic cleanup ensures test isolation and prevents resource leaks

### Phase 5 Completion Notes

Phase 5 basic integration tests are complete with significant enhancements:

#### NEMO Integration Tests (`test_nemo_integration.py` - 883 lines)
- **TestNemoConnector**: Complete NEMO API connector functionality tests
  - Service accessibility tests (NEMO web UI and API endpoints)
  - NemoConnector instantiation and configuration
  - Full API method coverage for users, tools, projects, reservations, usage events
  - Date-range filtered queries and pagination handling
  - Caching mechanisms for tools, users, projects
  - Date formatting and timezone handling
- **TestNemoHarvester**: Reservation event harvesting tests
  - `add_all_usage_events_to_db()` integration
  - Database session creation and state management
  - ReservationEvent creation from usage events
- **TestNemoReservationQuestions**: Reservation question parsing tests
  - Sample information extraction
  - Project metadata parsing
  - Data consent handling
- **TestNemoErrorHandling**: Comprehensive error condition tests
  - Invalid authentication token handling (401, 403)
  - Network error handling and retries
  - Invalid tool ID handling (400, 404)
  - Edge cases (empty reservations, no overlap scenarios)
- **Coverage Achievement**: ~92% for `__init__.py`, targeting remaining gaps

#### CDCS Integration Tests (`test_cdcs_integration.py` - 478 lines, 100% coverage)
- **TestCdcsServiceAccess**: Basic service accessibility tests
- **TestCdcsAuthentication**: Complete authentication test coverage
  - Valid credentials test (workspace ID retrieval)
  - Invalid credentials test (AuthenticationError raised)
  - Template ID retrieval tests
- **TestCdcsRecordOperations**: Full record lifecycle tests
  - Schema-compliant XML record upload
  - Special characters in title handling
  - Invalid XML rejection
  - Record deletion and cleanup
  - Batch uploads (multiple records)
- **TestCdcsRecordRetrieval**: Record retrieval via REST API
- **TestCdcsWorkspaceAssignment**: Workspace assignment verification
- **TestCdcsErrorHandling**: Error condition tests
- **TestCdcsUrlConfiguration**: URL configuration and validation tests
- **Helper functions**: `_handle_upload_result()` for consistent API response handling
- **Achievement**: 100% code coverage for CDCS integration module

#### Infrastructure Enhancements
- **Caddy Fileserver** (port 8081):
  - Serves test instrument data from `/tmp/nexuslims-test-instrument-data`
  - Serves generated previews from `/tmp/nexuslims-test-data`
  - Enables XSLT rendering in CDCS with proper file URLs
- **Caddy Reverse Proxy** (port 80):
  - Friendly URLs: `nemo.localhost`, `cdcs.localhost`, `fileserver.localhost`
  - Cross-container URL resolution via extra_hosts
  - Simplifies test configuration
- **XSLT Rendering Support**:
  - Environment variables: `FILESERVER_DATASET_URL`, `FILESERVER_PREVIEW_URL`
  - Enables full XML record visualization in CDCS UI
- **Fixture Smoke Tests** (`test_fixtures_smoke.py` - 98 lines):
  - Validates all Docker service fixtures
  - Validates NEMO, CDCS, database, and data fixtures
  - Ensures fixture health before running integration tests

#### Analysis and Documentation
- **Coverage Gap Analysis** (`tests/integration/COVERAGE_GAPS_ANALYSIS.md`):
  - Identified 32 untested code pathways with file paths and line numbers
  - Prioritized missing tests (CRITICAL, HIGH, MEDIUM severity)
  - Detailed recommendations for Phase 6
  - Test stubs created for all identified gaps
- **Test Status Report** (`2025-12-12_integration_test_status.md`):
  - Executive summary of test coverage
  - Statistical breakdown by category (0-100% by area)
  - Top priority recommendations for next phase
  - Impact analysis for each missing test category

## Current State Assessment (2025-12-12)

### What's Working Well ✅
1. **Comprehensive NEMO Testing**: 883 lines covering all major API endpoints, error handling, and data harvesting
2. **Complete CDCS Coverage**: 100% coverage of CDCS integration with robust error handling
3. **Solid Infrastructure**: Docker services are production-ready with health checks, idempotent initialization, and proper networking
4. **Developer Experience**: Friendly URLs via Caddy proxy, extensive documentation, fixture smoke tests
5. **XSLT Rendering**: Full support for viewing XML records in CDCS UI with fileserver integration

### Critical Gaps ⚠️
1. **No End-to-End Workflow Tests**: The most important production code path (NEMO → Record Builder → CDCS) is never tested end-to-end
2. **Network Resilience Untested**: Retry logic exists but is never verified; timeout handling missing
3. **Partial Failure Recovery**: Unknown behavior when NEMO succeeds but CDCS fails
4. **Multi-Instance Support**: Production deployments likely use multiple NEMO instances, but this is untested
5. **Scale Testing**: Large datasets, pagination, and bulk operations never validated

### Coverage Statistics
| Category              | Coverage | Test Count | Status       |
|-----------------------|----------|------------|--------------|
| Basic Connectivity    | 100%     | 15+        | ✅ Excellent |
| Happy Path Operations | 85%      | 40+        | ✅ Good      |
| Error Handling        | 60%      | 20+        | ⚠️ Fair      |
| Network Resilience    | 20%      | 5          | ❌ Poor      |
| End-to-End Workflows  | 0%       | 0          | ❌ Missing   |

### Immediate Next Steps
1. **Implement End-to-End Workflow Test** (1-2 days)
   - Create mock instrument files in test data directory
   - Test complete record building workflow with real services
   - Verify all database state transitions

2. **Add Network Resilience Tests** (1 day)
   - Mock server errors (502, 503, 504)
   - Test retry behavior
   - Add timeout parameter to nexus_req()

3. **Add Partial Failure Tests** (1 day)
   - Test database rollback scenarios
   - Verify error propagation
   - Test session cleanup after failures

### Blockers and Dependencies
- **No blockers**: All Docker services are functional and well-documented
- **Test data needed**: Mock microscopy files for record building tests (can use existing test files from unit tests)
- **Time estimate**: Phase 6 critical tests can be completed in 3-4 days of focused work

### Phase 6 Success Criteria
- [ ] At least one complete end-to-end workflow test passing
- [ ] Network error handling verified with tests
- [ ] Partial failure recovery tested and working correctly
- [ ] Code coverage for record_builder.py integration points >80%
- [ ] All CRITICAL and HIGH priority gaps from analysis addressed
