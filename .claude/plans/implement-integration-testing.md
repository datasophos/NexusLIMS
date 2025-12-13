# Integration Testing Implementation Plan for NexusLIMS

## Overview

This plan implements Docker-based integration testing for NexusLIMS with real NEMO and CDCS service instances. The strategy enables end-to-end testing of the complete workflow: NEMO harvesting → record building → CDCS upload.

## Design Principles

1. **Clear Separation**: Unit tests in `tests/unit/`, integration tests in `tests/integration/`
2. **Real Services**: Use actual NEMO and CDCS Docker containers, not mocks
3. **Minimal Test Data**: Reuse existing mock data structure for consistency and speed
4. **CI/CD Integration**: Run on PRs using GitHub Container Registry for efficiency
5. **Error Coverage**: Test both happy path and error scenarios (network failures, auth errors, malformed data)

## Architecture

### Service Stack

```
┌─────────────────────────────────────────────────────┐
│  Integration Test Runner (pytest)                   │
│  - Orchestrates test execution                      │
│  - Manages service lifecycle                        │
└───────────────┬─────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
┌───────▼──────┐  ┌──────▼───────┐
│ NEMO Service │  │ CDCS Service │
│ - Django API │  │ - REST API   │
│ - PostgreSQL │  │ - MongoDB    │
│ - Test data  │  │ - Schema     │
└──────────────┘  └──────────────┘
```

### Directory Structure

```
tests/
├── unit/                           # Existing tests (relocated)
│   ├── conftest.py
│   ├── test_cdcs.py
│   ├── test_config.py
│   ├── test_sessions.py
│   ├── test_harvesters/
│   ├── test_record_builder/
│   ├── test_extractors/
│   └── cli/
├── integration/                    # New integration tests
│   ├── __init__.py
│   ├── conftest.py                # Integration fixtures
│   ├── README.md                  # Quick start guide
│   ├── test_nemo_integration.py   # NEMO API tests
│   ├── test_cdcs_integration.py   # CDCS API tests
│   ├── test_end_to_end.py        # Full workflow tests
│   ├── test_error_scenarios.py    # Error handling tests
│   ├── docker/
│   │   ├── docker-compose.yml     # Main orchestration
│   │   ├── docker-compose.ci.yml  # CI-specific overrides
│   │   ├── nemo/
│   │   │   ├── Dockerfile
│   │   │   ├── init_data.py      # Seed test data
│   │   │   ├── wait-for-it.sh    # Health check script
│   │   │   └── fixtures/
│   │   │       └── seed_data.json # Test data (from unit test mocks)
│   │   ├── cdcs/
│   │   │   ├── Dockerfile
│   │   │   ├── init_schema.sh    # Upload Nexus schema
│   │   │   ├── wait-for-it.sh
│   │   │   └── fixtures/
│   │   │       └── nexus-experiment.xsd
│   │   └── nexuslims/
│   │       ├── Dockerfile         # Test runner container
│   │       └── entrypoint.sh
│   └── env/
│       ├── .env.integration       # Integration test env vars
│       └── .env.ci                # CI-specific overrides
├── fixtures/                      # Shared fixtures
│   ├── nemo_mock_data.py         # Used by unit tests
│   ├── cdcs_mock_data.py         # Used by unit tests
│   └── shared_data.py            # NEW: Shared test data
└── conftest.py                    # Root conftest (markers)
```

## Implementation Phases

### Phase 1: Project Restructuring (Week 1)

**Goal**: Reorganize test structure and add integration test markers

**Tasks**:

1. **Relocate existing tests to `tests/unit/`**
   - Move all current test files from `tests/` to `tests/unit/`
   - Update import paths where necessary
   - Verify all unit tests still pass after relocation

2. **Create integration test directory structure**
   ```bash
   mkdir -p tests/integration/{docker/{nemo,cdcs,nexuslims}/{fixtures,},env}
   touch tests/integration/{__init__.py,conftest.py,README.md}
   ```

3. **Add pytest markers to `tests/conftest.py`**
   ```python
   def pytest_configure(config):
       config.addinivalue_line(
           "markers",
           "integration: Integration tests requiring Docker services"
       )
       config.addinivalue_line(
           "markers",
           "e2e: End-to-end tests covering full record building workflow"
       )
       config.addinivalue_line(
           "markers",
           "slow: Tests that take >5 seconds to run"
       )
   ```

4. **Create shared fixture module `tests/fixtures/shared_data.py`**
   - Extract test data from `nemo_mock_data.py` and `cdcs_mock_data.py`
   - Provide single source of truth for test data
   - Update unit tests to import from shared module

5. **Update `pyproject.toml`**
   - Add testpaths configuration
   - Add markers configuration
   - Add optional integration test dependencies

**Deliverables**:
- All existing tests relocated and passing
- Clear test organization structure in place
- Pytest markers configured

### Phase 2: NEMO Docker Service (Week 2)

**Goal**: Create working NEMO service container with test data

**Tasks**:

1. **Create `tests/integration/docker/nemo/Dockerfile`**
   - Base image: `nanofab/nemo_splash_pad:latest`
   - Customize to include reservation questions
   - Install dependencies for data seeding script
   - Set up for test environment

2. **Create `tests/integration/docker/nemo/init_data.py`**
   - Python script using Django ORM or NEMO API
   - Seed database with test users (captain, professor, ned, commander)
   - Create test tools (643 Titan, 642 FEI Titan, JEOL JEM-3010)
   - Create test projects
   - Generate usage events and reservations
   - Reuse data structure from `tests/fixtures/shared_data.py`

3. **Create `tests/integration/docker/nemo/fixtures/seed_data.json`**
   - Convert shared_data.py Python structures to JSON
   - Include users, tools, projects, reservations, usage_events
   - Match structure expected by init_data.py

4. **Create `tests/integration/docker/nemo/wait-for-it.sh`**
   - Health check script for NEMO service
   - Poll `/api/users/` endpoint until 200 response
   - Timeout after 120 seconds
   - Used by docker-compose health checks

5. **Add NEMO service to `docker-compose.yml`**
   ```yaml
   services:
     nemo-postgres:
       image: postgres:14
       environment:
         POSTGRES_DB: nemo_test
         POSTGRES_USER: nemo
         POSTGRES_PASSWORD: nemo_test_pass
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U nemo"]
         interval: 5s
         timeout: 5s
         retries: 5

     nemo:
       build:
         context: ./nemo
         dockerfile: Dockerfile
       ports:
         - "8000:8000"
       depends_on:
         nemo-postgres:
           condition: service_healthy
       environment:
         - DATABASE_HOST=nemo-postgres
         - DATABASE_NAME=nemo_test
         - DATABASE_USER=nemo
         - DATABASE_PASSWORD=nemo_test_pass
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8000/api/users/"]
         interval: 10s
         timeout: 5s
         retries: 10
       command: >
         sh -c "python manage.py migrate &&
                python /init_data.py &&
                python manage.py runserver 0.0.0.0:8000"
   ```

6. **Test NEMO service manually**
   ```bash
   cd tests/integration/docker
   docker-compose up nemo
   curl http://localhost:8000/api/users/
   ```

**Deliverables**:
- Working NEMO Docker service
- Test data seeded on startup
- Health checks passing
- API accessible at http://localhost:8000

### Phase 3: CDCS Docker Service (Week 3)

**Goal**: Create working CDCS service container with Nexus schema

**Tasks**:

1. **Research nexuslims-cdcs-docker repository**
   - Review docker-compose setup at https://github.com/datasophos/nexuslims-cdcs-docker
   - Identify minimal configuration for testing
   - Note required environment variables and volumes

2. **Create `tests/integration/docker/cdcs/Dockerfile`**
   - Build based on nexuslims-cdcs-docker patterns
   - Include MongoDB connection configuration
   - Set up Django settings for test environment
   - Include initialization scripts

3. **Create `tests/integration/docker/cdcs/init_schema.sh`**
   ```bash
   #!/bin/bash
   set -e

   CDCS_URL="http://cdcs:8080"
   ADMIN_USER="${CDCS_ADMIN_USER:-admin}"
   ADMIN_PASS="${CDCS_ADMIN_PASS:-admin}"

   # Wait for CDCS to be ready
   until curl -sf "$CDCS_URL/rest/workspace/read_access"; do
     echo "Waiting for CDCS..."
     sleep 2
   done

   # Upload Nexus Experiment schema
   curl -X POST "$CDCS_URL/rest/template/" \
     -u "$ADMIN_USER:$ADMIN_PASS" \
     -F "file=@/fixtures/nexus-experiment.xsd" \
     -F "title=Nexus Experiment Schema"

   # Create test workspace
   curl -X POST "$CDCS_URL/rest/workspace/" \
     -u "$ADMIN_USER:$ADMIN_PASS" \
     -H "Content-Type: application/json" \
     -d '{"title": "Test Workspace", "is_public": true}'
   ```

4. **Copy schema to `tests/integration/docker/cdcs/fixtures/`**
   - Copy `nexusLIMS/schemas/nexus-experiment.xsd` to fixtures
   - Ensure it's available in Docker build context

5. **Add CDCS services to `docker-compose.yml`**
   ```yaml
   services:
     cdcs-mongo:
       image: mongo:6
       healthcheck:
         test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
         interval: 5s
         timeout: 5s
         retries: 5

     cdcs:
       build:
         context: ./cdcs
         dockerfile: Dockerfile
       ports:
         - "8080:8080"
       depends_on:
         cdcs-mongo:
           condition: service_healthy
       environment:
         - MONGO_HOST=cdcs-mongo
         - MONGO_PORT=27017
         - DJANGO_SECRET_KEY=test-secret-key-not-for-production
         - SERVER_URI=http://localhost:8080
         - CDCS_ADMIN_USER=admin
         - CDCS_ADMIN_PASS=admin
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8080/rest/workspace/read_access"]
         interval: 10s
         timeout: 5s
         retries: 10
       volumes:
         - ./cdcs/init_schema.sh:/docker-entrypoint-initdb.d/init_schema.sh
   ```

6. **Test CDCS service manually**
   ```bash
   cd tests/integration/docker
   docker-compose up cdcs
   curl http://localhost:8080/rest/workspace/read_access
   ```

**Deliverables**:
- Working CDCS Docker service
- Nexus schema loaded on startup
- Test workspace created
- API accessible at http://localhost:8080

### Phase 4: Integration Test Fixtures (Week 4)

**Goal**: Create pytest fixtures for integration tests

**Tasks**:

1. **Create `tests/integration/conftest.py`** with fixtures:

   ```python
   import pytest
   import subprocess
   import time
   import requests
   from pathlib import Path

   DOCKER_DIR = Path(__file__).parent / "docker"

   @pytest.fixture(scope="session")
   def docker_services():
       """Start Docker services once per test session."""
       # Start services
       subprocess.run(
           ["docker-compose", "up", "-d"],
           cwd=DOCKER_DIR,
           check=True
       )

       # Wait for health checks
       max_wait = 120
       start_time = time.time()

       while time.time() - start_time < max_wait:
           try:
               nemo_ready = requests.get("http://localhost:8000/api/users/").ok
               cdcs_ready = requests.get("http://localhost:8080/rest/workspace/read_access").ok

               if nemo_ready and cdcs_ready:
                   break
           except requests.ConnectionError:
               pass

           time.sleep(2)
       else:
           raise RuntimeError("Services failed to start within timeout")

       yield

       # Cleanup
       subprocess.run(
           ["docker-compose", "down", "-v"],
           cwd=DOCKER_DIR
       )

   @pytest.fixture
   def nemo_client(docker_services, monkeypatch):
       """Authenticated NEMO connector for integration tests."""
       from nexusLIMS.harvesters.nemo.connector import NemoConnector

       # Configure for test environment
       monkeypatch.setenv("NX_NEMO_ADDRESS_1", "http://localhost:8000/api/")
       monkeypatch.setenv("NX_NEMO_TOKEN_1", "test-token-12345")
       monkeypatch.setenv("NX_NEMO_TZ_1", "America/Denver")

       return NemoConnector(
           base_url="http://localhost:8000/api/",
           token="test-token-12345",
           timezone="America/Denver"
       )

   @pytest.fixture
   def cdcs_client(docker_services, monkeypatch):
       """Configure CDCS client for integration tests."""
       monkeypatch.setenv("NX_CDCS_URL", "http://localhost:8080")
       monkeypatch.setenv("NX_CDCS_USER", "admin")
       monkeypatch.setenv("NX_CDCS_PASS", "admin")

       import nexusLIMS.cdcs
       return nexusLIMS.cdcs

   @pytest.fixture
   def test_database(tmp_path, monkeypatch) -> Path:
       """Create fresh test database for integration tests."""
       from nexusLIMS.db.session_handler import Session

       db_path = tmp_path / "test_integration.db"
       monkeypatch.setenv("NX_DB_PATH", str(db_path))

       # Initialize database schema
       # (reuse existing test database initialization logic)

       yield db_path

       # Cleanup handled by tmp_path fixture

   @pytest.fixture
   def cleanup_cdcs_records(cdcs_client):
       """Track and cleanup CDCS records created during tests."""
       created_records = []

       def register_record(record_id):
           created_records.append(record_id)

       yield register_record

       # Cleanup
       for record_id in created_records:
           try:
               cdcs_client.delete_record(record_id)
           except Exception as e:
               # Log but don't fail test on cleanup error
               print(f"Failed to cleanup record {record_id}: {e}")
   ```

2. **Create `tests/integration/env/.env.integration`**
   ```env
   # NEMO configuration
   NX_NEMO_ADDRESS_1=http://localhost:8000/api/
   NX_NEMO_TOKEN_1=test-token-12345
   NX_NEMO_TZ_1=America/Denver

   # CDCS configuration
   NX_CDCS_URL=http://localhost:8080
   NX_CDCS_USER=admin
   NX_CDCS_PASS=admin

   # Test data paths
   NX_INSTRUMENT_DATA_PATH=/tmp/integration_test_data/instruments
   NX_DATA_PATH=/tmp/integration_test_data/nexuslims
   NX_DB_PATH=/tmp/integration_test_data/nexuslims.db
   ```

3. **Add fixture documentation to `tests/integration/README.md`**

**Deliverables**:
- Reusable integration test fixtures
- Automatic service lifecycle management
- Environment configuration
- Cleanup automation

### Phase 5: Basic Integration Tests (Week 5)

**Goal**: Write first integration tests for NEMO and CDCS

**Tasks**:

1. **Create `tests/integration/test_nemo_integration.py`**
   ```python
   import pytest

   @pytest.mark.integration
   class TestNemoIntegration:
       def test_get_users(self, nemo_client):
           """Test retrieving users from NEMO API."""
           users = nemo_client.get_users()
           assert len(users) == 4  # captain, professor, ned, commander
           assert any(u['username'] == 'captain' for u in users)

       def test_get_tools(self, nemo_client):
           """Test retrieving tools from NEMO API."""
           tools = nemo_client.get_tools()
           assert len(tools) >= 3
           tool_names = [t['name'] for t in tools]
           assert '643 Titan (S)TEM' in tool_names

       def test_get_usage_events(self, nemo_client):
           """Test retrieving usage events from NEMO API."""
           from datetime import datetime, timedelta

           end = datetime.now()
           start = end - timedelta(days=7)

           events = nemo_client.get_usage_events(start=start, end=end)
           assert isinstance(events, list)

       def test_authentication_failure(self, docker_services):
           """Test NEMO authentication error handling."""
           from nexusLIMS.harvesters.nemo.connector import NemoConnector

           bad_client = NemoConnector(
               base_url="http://localhost:8000/api/",
               token="invalid-token",
               timezone="America/Denver"
           )

           with pytest.raises(Exception):  # Expect auth error
               bad_client.get_users()
   ```

2. **Create `tests/integration/test_cdcs_integration.py`**
   ```python
   import pytest
   from pathlib import Path

   @pytest.mark.integration
   class TestCdcsIntegration:
       def test_get_workspace(self, cdcs_client):
           """Test retrieving workspace ID from CDCS."""
           workspace_id = cdcs_client.get_workspace_id()
           assert workspace_id is not None

       def test_get_template(self, cdcs_client):
           """Test retrieving Nexus schema template ID."""
           template_id = cdcs_client.get_template_id()
           assert template_id is not None

       def test_upload_record(self, cdcs_client, cleanup_cdcs_records, tmp_path):
           """Test uploading XML record to CDCS."""
           # Create test XML record
           test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
           <Experiment>
               <title>Integration Test Record</title>
           </Experiment>'''

           xml_file = tmp_path / "test_record.xml"
           xml_file.write_text(test_xml)

           # Upload record
           record_id = cdcs_client.upload_record_content(
               str(xml_file),
               "Integration Test"
           )

           cleanup_cdcs_records(record_id)
           assert record_id is not None

       def test_delete_record(self, cdcs_client, tmp_path):
           """Test deleting record from CDCS."""
           # Create and upload test record
           test_xml = '''<?xml version="1.0" encoding="UTF-8"?>
           <Experiment><title>To Be Deleted</title></Experiment>'''

           xml_file = tmp_path / "delete_test.xml"
           xml_file.write_text(test_xml)

           record_id = cdcs_client.upload_record_content(
               str(xml_file),
               "Delete Test"
           )

           # Delete record
           result = cdcs_client.delete_record(record_id)
           assert result.status_code == 204

       def test_authentication_failure(self, docker_services, monkeypatch):
           """Test CDCS authentication error handling."""
           monkeypatch.setenv("NX_CDCS_USER", "invalid")
           monkeypatch.setenv("NX_CDCS_PASS", "invalid")

           import nexusLIMS.cdcs

           with pytest.raises(Exception):  # Expect auth error
               nexusLIMS.cdcs.get_workspace_id()
   ```

3. **Run tests locally to verify**
   ```bash
   cd tests/integration/docker
   docker-compose up -d
   cd ../../..
   uv run pytest tests/integration/ -v -m integration
   ```

**Deliverables**:
- 8-10 basic integration tests passing
- NEMO API integration validated
- CDCS API integration validated
- Authentication error handling tested

### Phase 6: End-to-End Tests (Week 6)

**Goal**: Test complete workflow from NEMO to CDCS

**Tasks**:

1. **Create `tests/integration/test_end_to_end.py`**
   ```python
   import pytest
   from datetime import datetime, timedelta
   from nexusLIMS.builder.record_builder import build_record
   from nexusLIMS.db.session_handler import Session

   @pytest.mark.integration
   @pytest.mark.e2e
   @pytest.mark.slow
   class TestEndToEnd:
       def test_full_record_building_workflow(
           self,
           nemo_client,
           cdcs_client,
           test_database,
           cleanup_cdcs_records,
           tmp_path
       ):
           """Test complete workflow: NEMO → Record Builder → CDCS."""

           # 1. Create usage event in NEMO
           # (This would use NEMO API to create a test usage event)

           # 2. Harvest from NEMO and create session
           from nexusLIMS.harvesters.nemo.utils import add_all_usage_events_to_db

           session_count_before = Session.get_sessions_to_build().count()
           add_all_usage_events_to_db()
           session_count_after = Session.get_sessions_to_build().count()

           assert session_count_after > session_count_before

           # 3. Build record from session
           sessions = Session.get_sessions_to_build()
           test_session = sessions[0]

           record_xml = build_record(test_session)
           assert record_xml is not None

           # 4. Upload to CDCS
           xml_file = tmp_path / f"record_{test_session.session_id}.xml"
           xml_file.write_text(record_xml)

           record_id = cdcs_client.upload_record_content(
               str(xml_file),
               f"E2E Test {test_session.session_id}"
           )

           cleanup_cdcs_records(record_id)
           assert record_id is not None

           # 5. Verify record in CDCS
           # (Query CDCS API to verify record exists and is valid)

       def test_no_files_found_workflow(self, nemo_client, test_database):
           """Test workflow when session has no files."""
           # Create session with no files
           # Verify status becomes NO_FILES_FOUND
           # Verify retry logic
           pass

       def test_multiple_activities_in_session(self, tmp_path):
           """Test session with multiple acquisition activities."""
           # Create test files with temporal gaps
           # Verify file clustering into activities
           # Verify XML structure has multiple activities
           pass
   ```

2. **Create `tests/integration/test_error_scenarios.py`**
   ```python
   import pytest

   @pytest.mark.integration
   class TestErrorScenarios:
       def test_nemo_network_timeout(self, monkeypatch):
           """Test handling of NEMO network timeout."""
           # Mock network timeout
           # Verify appropriate error handling and logging
           pass

       def test_cdcs_upload_failure(self, cdcs_client):
           """Test handling of CDCS upload failure."""
           # Upload malformed XML
           # Verify error is caught and logged
           pass

       def test_invalid_metadata_extraction(self):
           """Test handling of corrupted microscopy files."""
           # Attempt to extract metadata from corrupt file
           # Verify graceful degradation
           pass

       def test_session_build_retry_logic(self, test_database):
           """Test session retry logic for transient failures."""
           # Create session that fails once then succeeds
           # Verify retry mechanism works
           pass
   ```

3. **Add test data files to `tests/integration/data/`**
   - Copy sample microscopy files from existing unit test fixtures
   - Create file structure matching instrument filestore layout

**Deliverables**:
- 3-5 E2E tests covering complete workflow
- 4-6 error scenario tests
- Comprehensive workflow validation

### Phase 7: Docker Image Registry (Week 7)

**Goal**: Set up GitHub Container Registry for pre-built images

**Tasks**:

1. **Create `.github/workflows/build-test-images.yml`**
   ```yaml
   name: Build Test Docker Images

   on:
     push:
       branches: [main]
       paths:
         - 'tests/integration/docker/**'
     workflow_dispatch:

   jobs:
     build-nemo:
       name: Build NEMO Test Image
       runs-on: ubuntu-latest
       permissions:
         contents: read
         packages: write

       steps:
         - uses: actions/checkout@v4

         - name: Log in to GitHub Container Registry
           uses: docker/login-action@v3
           with:
             registry: ghcr.io
             username: ${{ github.actor }}
             password: ${{ secrets.GITHUB_TOKEN }}

         - name: Build and push NEMO image
           uses: docker/build-push-action@v5
           with:
             context: ./tests/integration/docker/nemo
             push: true
             tags: |
               ghcr.io/${{ github.repository }}/nemo-test:latest
               ghcr.io/${{ github.repository }}/nemo-test:${{ github.sha }}
             cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/nemo-test:latest
             cache-to: type=inline

     build-cdcs:
       name: Build CDCS Test Image
       runs-on: ubuntu-latest
       permissions:
         contents: read
         packages: write

       steps:
         - uses: actions/checkout@v4

         - name: Log in to GitHub Container Registry
           uses: docker/login-action@v3
           with:
             registry: ghcr.io
             username: ${{ github.actor }}
             password: ${{ secrets.GITHUB_TOKEN }}

         - name: Build and push CDCS image
           uses: docker/build-push-action@v5
           with:
             context: ./tests/integration/docker/cdcs
             push: true
             tags: |
               ghcr.io/${{ github.repository }}/cdcs-test:latest
               ghcr.io/${{ github.repository }}/cdcs-test:${{ github.sha }}
             cache-from: type=registry,ref=ghcr.io/${{ github.repository }}/cdcs-test:latest
             cache-to: type=inline
   ```

2. **Update `tests/integration/docker/docker-compose.ci.yml`**
   ```yaml
   # CI-specific overrides that use pre-built images from GHCR
   services:
     nemo:
       image: ghcr.io/${GITHUB_REPOSITORY}/nemo-test:latest
       build: null  # Don't rebuild, use pre-built image

     cdcs:
       image: ghcr.io/${GITHUB_REPOSITORY}/cdcs-test:latest
       build: null  # Don't rebuild, use pre-built image
   ```

3. **Make images public in GitHub package settings**
   - Navigate to repository packages
   - Set nemo-test and cdcs-test to public visibility
   - Allows pulling without authentication

**Deliverables**:
- Automated image building on changes
- Images published to GHCR
- CI can use pre-built images for speed

### Phase 8: CI/CD Integration (Week 8)

**Goal**: Add integration tests to GitHub Actions and GitLab CI

**Tasks**:

1. **Create `.github/workflows/integration-tests.yml`**
   ```yaml
   name: Integration Tests

   on:
     pull_request:
       branches: [main]
     push:
       branches: [main]
     workflow_dispatch:

   jobs:
     integration:
       name: Integration Tests
       runs-on: ubuntu-latest
       timeout-minutes: 30

       steps:
         - uses: actions/checkout@v4

         - name: Log in to GitHub Container Registry
           uses: docker/login-action@v3
           with:
             registry: ghcr.io
             username: ${{ github.actor }}
             password: ${{ secrets.GITHUB_TOKEN }}

         - name: Pull pre-built images
           run: |
             docker pull ghcr.io/${{ github.repository }}/nemo-test:latest
             docker pull ghcr.io/${{ github.repository }}/cdcs-test:latest

         - name: Start Docker services
           run: |
             cd tests/integration/docker
             GITHUB_REPOSITORY=${{ github.repository }} \
               docker-compose -f docker-compose.yml -f docker-compose.ci.yml up -d

         - name: Wait for services
           run: |
             timeout 120 bash -c 'until curl -sf http://localhost:8000/api/users/; do sleep 2; done'
             timeout 120 bash -c 'until curl -sf http://localhost:8080/rest/workspace/read_access; do sleep 2; done'

         - name: Set up uv
           uses: astral-sh/setup-uv@v4

         - name: Run integration tests
           run: |
             uv sync
             uv run pytest tests/integration/ -v -m integration \
               --junitxml=integration-results.xml \
               --cov=nexusLIMS \
               --cov-report=xml:integration-coverage.xml

         - name: Collect service logs on failure
           if: failure()
           run: |
             mkdir -p logs
             cd tests/integration/docker
             docker-compose logs > ../../logs/services.log

         - name: Upload logs
           if: failure()
           uses: actions/upload-artifact@v4
           with:
             name: integration-test-logs
             path: logs/
             retention-days: 7

         - name: Upload test results
           if: always()
           uses: actions/upload-artifact@v4
           with:
             name: integration-test-results
             path: integration-results.xml
             retention-days: 30

         - name: Upload coverage to Codecov
           uses: codecov/codecov-action@v5
           with:
             files: ./integration-coverage.xml
             flags: integration
             fail_ci_if_error: false

         - name: Cleanup
           if: always()
           run: |
             cd tests/integration/docker
             docker-compose down -v
   ```

2. **Update `.gitlab-ci.yml`**
   ```yaml
   integration_tests:
     stage: test
     image: docker:24.0.5
     services:
       - docker:24.0.5-dind
     variables:
       DOCKER_DRIVER: overlay2
       DOCKER_TLS_CERTDIR: "/certs"
     before_script:
       - apk add --no-cache curl bash python3 py3-pip
       - pip3 install uv
     script:
       - cd tests/integration/docker
       - docker-compose pull  # Pull pre-built images if available
       - docker-compose up -d
       - timeout 120 sh -c 'until curl -sf http://docker:8000/api/users/; do sleep 2; done'
       - timeout 120 sh -c 'until curl -sf http://docker:8080/rest/workspace/read_access; do sleep 2; done'
       - cd ../../..
       - uv sync
       - uv run pytest tests/integration/ -v -m integration --junitxml=integration-results.xml
     after_script:
       - cd tests/integration/docker && docker-compose logs > ../../logs/services.log || true
       - cd tests/integration/docker && docker-compose down -v || true
     artifacts:
       reports:
         junit: integration-results.xml
       paths:
         - logs/
       when: always
       expire_in: 7 days
     rules:
       - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
       - if: '$CI_COMMIT_BRANCH == "main"'
     needs: []
     timeout: 30 minutes
   ```

3. **Update `pyproject.toml` pytest configuration**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests/unit", "tests/integration"]
   markers = [
       "integration: Integration tests requiring Docker services",
       "e2e: End-to-end tests covering full workflows",
       "slow: Tests that take >5 seconds to run",
   ]
   # Run only unit tests by default
   addopts = "-v --strict-markers"
   ```

4. **Add CI status badges to README.md**

**Deliverables**:
- Integration tests running on every PR
- Automatic service orchestration in CI
- Test results and coverage reporting
- Log collection on failures

### Phase 9: Documentation (Week 9)

**Goal**: Comprehensive documentation for integration testing

**Tasks**:

1. **Create `tests/integration/README.md`**
   - Quick start guide
   - Prerequisites (Docker, docker-compose)
   - Running tests locally
   - Common troubleshooting
   - Test organization overview

2. **Create `docs/testing/integration-tests.md`**
   - Architecture overview with diagrams
   - Service configuration details
   - Writing new integration tests
   - Debugging guide
   - CI/CD integration details
   - Best practices

3. **Update `CONTRIBUTING.md`**
   - Add section on integration testing
   - When to write unit vs integration tests
   - How to run tests before PR submission
   - Integration test checklist

4. **Add docstrings to all integration test files**
   - Module-level documentation
   - Test function docstrings
   - Fixture documentation

5. **Create troubleshooting guide**
   - Common errors and solutions
   - How to access service logs
   - How to debug failing tests
   - How to reset services

**Deliverables**:
- Comprehensive documentation
- Quick reference guides
- Troubleshooting resources
- Updated contribution guidelines

## Critical Files to Create/Modify

### New Files (23 files)

**Directory Structure:**
1. `tests/integration/__init__.py`
2. `tests/integration/conftest.py`
3. `tests/integration/README.md`

**Test Files:**
4. `tests/integration/test_nemo_integration.py`
5. `tests/integration/test_cdcs_integration.py`
6. `tests/integration/test_end_to_end.py`
7. `tests/integration/test_error_scenarios.py`

**Docker Infrastructure:**
8. `tests/integration/docker/docker-compose.yml`
9. `tests/integration/docker/docker-compose.ci.yml`
10. `tests/integration/docker/nemo/Dockerfile`
11. `tests/integration/docker/nemo/init_data.py`
12. `tests/integration/docker/nemo/wait-for-it.sh`
13. `tests/integration/docker/nemo/fixtures/seed_data.json`
14. `tests/integration/docker/cdcs/Dockerfile`
15. `tests/integration/docker/cdcs/init_schema.sh`
16. `tests/integration/docker/cdcs/wait-for-it.sh`
17. `tests/integration/docker/cdcs/fixtures/nexus-experiment.xsd`

**Environment Configuration:**
18. `tests/integration/env/.env.integration`
19. `tests/integration/env/.env.ci`

**Shared Fixtures:**
20. `tests/fixtures/shared_data.py`

**CI/CD:**
21. `.github/workflows/build-test-images.yml`
22. `.github/workflows/integration-tests.yml`

**Documentation:**
23. `docs/testing/integration-tests.md`

### Modified Files (4 files)

1. `tests/conftest.py` - Add pytest markers
2. `.gitlab-ci.yml` - Add integration test job
3. `CONTRIBUTING.md` - Add testing guidelines
4. `pyproject.toml` - Update pytest configuration, add testpaths

### Relocated Files (entire tests/ directory)

All existing test files move from `tests/` to `tests/unit/`:
- `tests/test_*.py` → `tests/unit/test_*.py`
- `tests/test_harvesters/` → `tests/unit/test_harvesters/`
- `tests/test_record_builder/` → `tests/unit/test_record_builder/`
- `tests/test_extractors/` → `tests/unit/test_extractors/`
- `tests/cli/` → `tests/unit/cli/`

## Testing Strategy

### Unit Tests
- **Location**: `tests/unit/`
- **Execution**: Every commit, fast feedback
- **Coverage**: Individual functions and classes
- **Dependencies**: Mocked external services
- **Speed**: < 2 minutes total

### Integration Tests
- **Location**: `tests/integration/`
- **Execution**: Every PR, main branch pushes
- **Coverage**: Service interactions (NEMO, CDCS)
- **Dependencies**: Real Docker services
- **Speed**: 5-10 minutes total

### E2E Tests
- **Location**: `tests/integration/test_end_to_end.py`
- **Execution**: Every PR, nightly
- **Coverage**: Complete workflows
- **Dependencies**: All services + test data files
- **Speed**: 10-15 minutes total

## Success Criteria

### Phase Completion
- [ ] All existing unit tests passing in new location
- [ ] NEMO service starts and responds to API calls
- [ ] CDCS service starts and accepts record uploads
- [ ] Integration fixtures manage service lifecycle
- [ ] 15+ integration tests passing locally
- [ ] 5+ E2E tests validating workflows
- [ ] 5+ error scenario tests
- [ ] Docker images published to GHCR
- [ ] Integration tests running in GitHub Actions
- [ ] Integration tests running in GitLab CI
- [ ] Comprehensive documentation complete

### Quality Metrics
- Integration test coverage: >80% of NEMO/CDCS integration code
- E2E test coverage: All critical user workflows
- CI execution time: <15 minutes including service startup
- Test reliability: <5% flaky test rate
- Documentation completeness: All setup/debugging scenarios covered

## Risk Mitigation

### Technical Risks

1. **NEMO Docker customization complexity**
   - Mitigation: Start with base image as-is, iterate on customization
   - Fallback: Use simpler mock NEMO API if customization too complex

2. **CDCS build from scratch challenges**
   - Mitigation: Closely follow nexuslims-cdcs-docker patterns
   - Fallback: Contact CDCS maintainers for Docker guidance

3. **Service startup time in CI**
   - Mitigation: Use GHCR pre-built images with layer caching
   - Optimization: Parallel service startup in docker-compose

4. **Test flakiness due to service timing**
   - Mitigation: Robust health checks with exponential backoff
   - Solution: Configurable timeouts for different environments

5. **Integration test maintenance burden**
   - Mitigation: Share fixtures with unit tests via shared_data.py
   - Best practice: Keep test data minimal but representative

### Resource Risks

1. **GitHub Actions minutes consumption**
   - Mitigation: Only run on PRs and main branch (not every commit)
   - Optimization: Pre-built images reduce build time
   - Monitoring: Track minutes usage, adjust frequency if needed

2. **GHCR storage limits**
   - Mitigation: Use image retention policies
   - Cleanup: Delete old image versions automatically

## Next Steps After Implementation

1. **Add more integration test scenarios**
   - Multi-instrument sessions
   - Large file processing
   - Concurrent session handling

2. **Performance testing**
   - Add pytest-benchmark for performance regression testing
   - Test with realistic data volumes

3. **Nightly comprehensive test suite**
   - Longer-running tests
   - More extensive error scenarios
   - Load testing

4. **Local development improvements**
   - Docker Compose profiles for selective service startup
   - Integration test debugger configuration
   - Mock data generation tools

## Summary

This plan implements a production-ready integration testing infrastructure for NexusLIMS that:

- **Separates concerns**: Clear boundaries between unit and integration tests
- **Uses real services**: Docker-based NEMO and CDCS instead of mocks
- **Optimizes CI/CD**: Pre-built images in GHCR for fast execution
- **Covers critical paths**: End-to-end workflows and error scenarios
- **Maintains efficiency**: Minimal test data, parallel execution
- **Provides excellent DX**: Easy local setup, clear debugging, comprehensive docs

The phased 9-week implementation delivers incremental value, with basic integration tests working by week 5 and full CI/CD integration by week 8. The infrastructure is designed to be maintainable and extensible for future testing needs.
