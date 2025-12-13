# NexusLIMS Integration Tests

This directory contains integration tests for NexusLIMS that use real Docker services (NEMO, CDCS) instead of mocks. These tests validate end-to-end workflows including NEMO harvesting, record building, and CDCS uploads.

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- `uv` package manager installed
- At least 4GB of available RAM for Docker services
- Ports 8000, 8080, and 8081 available

### Running Integration Tests

1. **Start Docker services:**
   ```bash
   cd tests/integration/docker
   docker compose up -d
   ```

2. **Wait for services to be ready (check health):**
   ```bash
   # NEMO should respond
   curl http://localhost:8000/

   # CDCS should respond
   curl http://localhost:8080/
   ```

3. **Run integration tests:**
   ```bash
   # From repository root
   uv run pytest tests/integration/ -v -m integration

   # Run specific test file
   uv run pytest tests/integration/test_nemo_integration.py -v

   # Run with coverage
   uv run pytest tests/integration/ -v -m integration --cov=nexusLIMS
   ```

4. **Clean up when done:**
   ```bash
   cd tests/integration/docker
   docker compose down -v
   ```

## Architecture

### Service Stack

The integration test environment consists of the following Docker services:

```
┌─────────────────────────────────────────────────────┐
│  Integration Test Runner (pytest)                   │
│  - Manages service lifecycle                        │
│  - Runs tests against real services                 │
└───────────────┬─────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
┌───────▼──────┐  ┌──────▼───────┐  ┌──────────────┐
│ NEMO Service │  │ CDCS Service │  │  Fileserver  │
│ - Django API │  │ - REST API   │  │  (Caddy)     │
│ - SQLite DB  │  │ - MongoDB    │  │              │
│ - Test data  │  │ - PostgreSQL │  │              │
│              │  │ - Redis      │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

#### Services

- **NEMO** (port 8000): Lab management system with test users, tools, and reservations
- **CDCS** (port 8080): Curator/Django application for XML record storage
  - **MongoDB** (internal): Document storage for CDCS records
  - **PostgreSQL** (internal): Django database for CDCS metadata
  - **Redis** (internal): Celery task queue for background jobs
- **Fileserver** (port 8081): Caddy fileserver for serving instrument data and previews

### Test Data Flow

```
NEMO Usage Events → Harvester → Session Log → Record Builder → CDCS
                                                    ↓
                                            Microscopy Files
                                            (from fileserver)
```

## Fixtures

### Service Management Fixtures

#### `docker_services` (session scope)

Starts all Docker services once per test session and tears them down after all tests complete.

**Usage:**
```python
def test_something(docker_services):
    # Services are running and healthy
    response = requests.get("http://localhost:8000/")
    assert response.status_code == 200
```

**Lifecycle:**
- Starts: `docker compose up -d`
- Waits: Up to 180 seconds for health checks
- Tears down: `docker compose down -v` (removes volumes)

#### `docker_services_running` (session scope)

Convenience fixture that provides service URLs and status.

**Usage:**
```python
def test_services(docker_services_running):
    nemo_url = docker_services_running["nemo_url"]
    assert nemo_url == "http://localhost:8000"
```

### NEMO Fixtures

#### `nemo_url`

Provides NEMO base URL (`http://localhost:8000`).

#### `nemo_api_url`

Provides NEMO API base URL (`http://localhost:8000/api/`).

#### `nemo_client`

Configures NexusLIMS to use the test NEMO instance by patching `nexusLIMS.config` variables.

**Usage:**
```python
def test_nemo_harvester(nemo_client):
    # Config is already patched to use test NEMO
    from nexusLIMS.harvesters.nemo import connector

    # This will connect to http://localhost:8000/api/
    conn = connector.NemoConnector(
        base_url=nemo_client["url"],
        token=nemo_client["token"],
        timezone=nemo_client["timezone"]
    )
```

#### `nemo_test_users`

Provides list of test users seeded in NEMO:
- `captain` (superuser, facility manager)
- `professor` (staff)
- `ned` (regular user)
- `commander` (accounting officer)

#### `nemo_test_tools`

Provides list of test instruments seeded in NEMO:
- `643 Titan (S)TEM` (id=1)
- `642 FEI Titan` (id=3)
- `JEOL JEM-3010` (id=5)

### CDCS Fixtures

#### `cdcs_url`

Provides CDCS base URL (`http://localhost:8080`).

#### `cdcs_credentials`

Provides CDCS credentials:
```python
{"username": "admin", "password": "admin"}
```

#### `cdcs_client`

Configures NexusLIMS to use the test CDCS instance and provides record tracking for cleanup.

**Usage:**
```python
def test_cdcs_upload(cdcs_client):
    import nexusLIMS.cdcs as cdcs

    # Upload a record
    record_id = cdcs.upload_record_content(xml_file, "Test Record")

    # Register for automatic cleanup
    cdcs_client["register_record"](record_id)

    # Record will be automatically deleted after test
```

**Automatic Cleanup:**
All records registered via `register_record()` are automatically deleted after the test completes.

### Database Fixtures

#### `test_database`

Creates a fresh temporary SQLite database with initialized schema.

**Usage:**
```python
def test_sessions(test_database):
    from nexusLIMS.db.session_handler import Session

    # Database is ready to use
    session = Session(...)
```

**Notes:**
- Database is isolated per test
- Schema is automatically initialized
- Automatically cleaned up after test

#### `populated_test_database`

Extends `test_database` with sample instruments that match the NEMO test tools.

**Usage:**
```python
def test_with_instruments(populated_test_database):
    from nexusLIMS.db.session_handler import Session

    # Database has instruments pre-loaded
    # Instruments match NEMO tools (643 Titan, 642 Titan)
```

### Test Data Fixtures

#### `test_data_dirs`

Creates test data directories for instrument data and NexusLIMS data.

**Usage:**
```python
def test_file_discovery(test_data_dirs):
    instrument_dir = test_data_dirs["instrument_data"]
    nexuslims_dir = test_data_dirs["nexuslims_data"]

    # Create test files in these directories
```

**Directories:**
- `instrument_data`: `/tmp/nexuslims-test-instrument-data` (mounted in Docker fileserver)
- `nexuslims_data`: `/tmp/nexuslims-test-data` (mounted in Docker fileserver)

#### `sample_microscopy_files`

Creates minimal sample microscopy files for testing.

**Usage:**
```python
def test_metadata_extraction(sample_microscopy_files):
    # Files are created in instrument_data/643_Titan/
    for file_path in sample_microscopy_files:
        # Extract metadata, etc.
```

### Utility Fixtures

#### `wait_for_service`

Provides a utility function to wait for service availability.

**Usage:**
```python
def test_custom_service(wait_for_service):
    # Wait up to 30 seconds for service
    is_ready = wait_for_service("http://localhost:9000/health", timeout=30)
    assert is_ready
```

#### `integration_test_marker`

Verifies test is properly marked as an integration test.

**Usage:**
```python
@pytest.mark.integration
def test_something(integration_test_marker):
    # This fixture ensures the test is marked correctly
    pass
```

## Writing Integration Tests

### Test Structure

Integration tests should follow this structure:

```python
import pytest

@pytest.mark.integration
class TestFeatureName:
    """Integration tests for feature X."""

    def test_basic_functionality(self, docker_services, nemo_client):
        """Test basic feature with NEMO integration."""
        # Arrange
        # ... setup ...

        # Act
        # ... execute feature ...

        # Assert
        # ... verify results ...

    def test_error_handling(self, docker_services):
        """Test error handling in integration scenario."""
        # Test error cases
```

### Best Practices

1. **Mark all integration tests:**
   ```python
   @pytest.mark.integration
   def test_something(docker_services):
       pass
   ```

2. **Use descriptive test names:**
   - Good: `test_nemo_harvester_creates_session_in_database`
   - Bad: `test_harvester`

3. **Test one thing per test:**
   Each test should verify a single behavior or workflow.

4. **Clean up resources:**
   Use fixtures that automatically clean up (like `cdcs_client`).

5. **Handle timing issues:**
   Services may take time to process. Use `time.sleep()` or retry logic when needed.

6. **Avoid hardcoded waits:**
   Use the `wait_for_service` fixture instead of `time.sleep()`.

### Example Tests

#### Basic NEMO Integration Test

```python
import pytest
import requests

@pytest.mark.integration
def test_nemo_api_users(nemo_api_url, nemo_test_users):
    """Test retrieving users from NEMO API."""
    response = requests.get(f"{nemo_api_url}users/")
    assert response.status_code == 200

    users = response.json()
    assert len(users) >= len(nemo_test_users)

    usernames = [u["username"] for u in users]
    assert "captain" in usernames
```

#### Basic CDCS Integration Test

```python
import pytest
from pathlib import Path

@pytest.mark.integration
def test_cdcs_upload_record(cdcs_client, tmp_path):
    """Test uploading XML record to CDCS."""
    import nexusLIMS.cdcs as cdcs

    # Create test record
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <Experiment>
        <title>Test Record</title>
    </Experiment>'''

    xml_file = tmp_path / "test.xml"
    xml_file.write_text(xml_content)

    # Upload
    record_id = cdcs.upload_record_content(str(xml_file), "Test")
    cdcs_client["register_record"](record_id)

    assert record_id is not None
```

#### End-to-End Test

```python
import pytest
from datetime import datetime, timedelta

@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
def test_full_record_building_workflow(
    nemo_client,
    cdcs_client,
    populated_test_database,
    sample_microscopy_files,
):
    """Test complete workflow from NEMO to CDCS."""
    # 1. Harvest from NEMO
    from nexusLIMS.harvesters.nemo import utils as nemo_utils
    nemo_utils.add_all_usage_events_to_db()

    # 2. Build records
    from nexusLIMS.builder import record_builder
    record_builder.process_new_records()

    # 3. Verify records in CDCS
    # ... verification logic ...
```

## Test Markers

Integration tests use pytest markers for organization:

- `@pytest.mark.integration`: All integration tests (required)
- `@pytest.mark.e2e`: End-to-end tests covering full workflows
- `@pytest.mark.slow`: Tests that take >5 seconds

**Running specific markers:**
```bash
# Only integration tests
pytest tests/integration/ -m integration

# Only E2E tests
pytest tests/integration/ -m "integration and e2e"

# Exclude slow tests
pytest tests/integration/ -m "integration and not slow"
```

## Environment Variables

Integration tests use environment variables defined in `env/.env.integration`:

- `NX_NEMO_ADDRESS_1`: NEMO API URL
- `NX_NEMO_TOKEN_1`: NEMO API token
- `NX_CDCS_URL`: CDCS URL
- `NX_CDCS_USER`: CDCS username
- `NX_CDCS_PASS`: CDCS password
- `NX_INSTRUMENT_DATA_PATH`: Instrument data directory
- `NX_DATA_PATH`: NexusLIMS data directory
- `NX_DB_PATH`: Database path

**Note:** Fixtures automatically patch these variables through `nexusLIMS.config`, so you typically don't need to set them manually.

## Debugging Tools

### Standalone Fileserver

The integration tests include a standalone fileserver for debugging HTTP file serving and testing file access patterns without running the full test suite.

**Location:** `tests/integration/debug_fileserver.py`

**Usage:**
```bash
# From repository root
python tests/integration/debug_fileserver.py

# Or run directly (executable)
./tests/integration/debug_fileserver.py
```

**What it does:**
- Runs the same fileserver used in integration tests on port 8081
- Serves files from test data directories:
  - `http://localhost:8081/instrument-data/` → `/tmp/nexuslims-test-instrument-data/`
  - `http://localhost:8081/data/` → `/tmp/nexuslims-test-data/`
- Shows directory contents and diagnostics on startup
- Runs until stopped with Ctrl+C

**Security:**
- Only serves files from the two designated test directories
- Rejects all other paths (returns 404)
- Includes CORS headers for cross-origin testing
- No caching headers for development convenience

**Example session:**
```bash
$ python tests/integration/debug_fileserver.py
[*] Checking test data directories...
[+] Directory exists: /tmp/nexuslims-test-instrument-data
    Contents (4 items):
      - JEOL_TEM
      - Titan_TEM
      - test_proxy.txt
      - Nexus_Test_Instrument
[+] Directory exists: /tmp/nexuslims-test-data
    Contents (2 items):
      - records
      - Titan_TEM

======================================================================
[+] Starting fileserver on port 8081
[+] Serving instrument data from: /tmp/nexuslims-test-instrument-data
[+] Serving NexusLIMS data from: /tmp/nexuslims-test-data
======================================================================

Access URLs:
  - http://localhost:8081/instrument-data/
  - http://localhost:8081/data/

Press Ctrl+C to stop the server...
======================================================================

# Test access
$ curl http://localhost:8081/instrument-data/
# Returns directory listing

$ curl http://localhost:8081/some-other-path
# Returns 404
```

**Use cases:**
- Testing file access patterns during development
- Debugging fileserver configuration issues
- Manual verification of file serving before running tests
- Testing client applications that need to fetch files

**Implementation:**
The script imports the `start_fileserver()` function from `conftest.py`, ensuring no code duplication. The same HTTP handler logic is used in both the standalone script and the pytest fixture.

## Troubleshooting

### Services Fail to Start

**Check Docker logs:**
```bash
cd tests/integration/docker
docker compose logs nemo
docker compose logs cdcs
```

**Common issues:**
- Ports already in use (8000, 8080, 8081)
- Insufficient Docker resources (increase RAM/CPU in Docker settings)
- Previous containers not cleaned up (run `docker compose down -v`)

### Health Checks Timeout

If services take too long to start:

1. Check Docker resource allocation
2. Verify no other services are using the same ports
3. Check the service logs for errors
4. Try pulling latest images: `docker compose pull`

### Tests Fail Intermittently

**Timing issues:**
- Services may need more time to process requests
- Add explicit waits or use the `wait_for_service` fixture

**State issues:**
- Ensure each test is isolated (use fixtures properly)
- Verify cleanup is working (check `docker compose down -v` is called)

### Database Connection Errors

**Make sure:**
- `test_database` fixture is used
- Database path is in a writable location
- Previous test cleaned up properly

### CDCS Upload Failures

**Check:**
- CDCS service is healthy: `curl http://localhost:8080/`
- Credentials are correct (admin/admin)
- XML record is valid against schema
- Network connectivity to CDCS container

### Cleanup Issues

If cleanup fails:

```bash
# Manual cleanup
cd tests/integration/docker
docker compose down -v

# Remove test data
rm -rf /tmp/nexuslims-test-*

# Reset everything
docker system prune -a --volumes
```

## Performance Optimization

### Use Session-Scoped Fixtures

Services start once per session, not per test:
```python
# Good - uses existing services
def test_something(docker_services):
    pass

# Avoid - don't start services per test
```

### Parallel Test Execution

Integration tests can run in parallel using `pytest-xdist`:
```bash
pytest tests/integration/ -n 4
```

**Note:** Be careful with shared resources (database, CDCS records).

### Skip Services Not Needed

If only testing NEMO:
```bash
cd tests/integration/docker
docker compose up -d nemo
```

## CI/CD Integration

Integration tests are designed to run in CI/CD pipelines:

- Pre-built Docker images (future: GitHub Container Registry)
- Automatic service orchestration
- Log collection on failure
- Test result reporting

**GitHub Actions example:**
```yaml
- name: Run integration tests
  run: |
    cd tests/integration/docker
    docker compose up -d
    cd ../../..
    uv run pytest tests/integration/ -v -m integration
```

## Further Reading

- [Integration Testing Plan](../../.claude/plans/implement-integration-testing.md)
- [Docker Service Documentation](docker/README.md)
- [NEMO Service Documentation](docker/nemo/README.md)
- [CDCS Service Documentation](docker/cdcs/README.md)
- [Shared Test Fixtures](../fixtures/shared_data.py)

## Contributing

When adding new integration tests:

1. Mark with `@pytest.mark.integration`
2. Use existing fixtures when possible
3. Document any new fixtures in this README
4. Add cleanup logic for any resources created
5. Test locally before committing
6. Update this README if adding new patterns or best practices
