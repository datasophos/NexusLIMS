# Integration Testing Guide

This guide provides comprehensive documentation for NexusLIMS integration tests, which validate end-to-end workflows using real Docker services instead of mocks.

## Overview

NexusLIMS integration tests verify that the complete system works together correctly, from NEMO reservation harvesting through record building to CDCS upload. These tests use Docker Compose to orchestrate a complete service stack that mirrors the production environment.

### Why Integration Testing?

Integration tests provide:
- **End-to-End Validation**: Verify workflows work across multiple components
- **Real Service Integration**: Test actual NEMO API, CDCS REST API, and file operations
- **Regression Detection**: Catch breaking changes in component interactions
- **Production Confidence**: High assurance that deployments will work

### When to Use Integration Tests vs Unit Tests

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|-------------------|
| **Speed** | Very fast (seconds) | Slower (minutes) |
| **Isolation** | Mocked dependencies | Real services |
| **Coverage** | Internal logic | External interactions |
| **Frequency** | Run on every commit | Run nightly or before merge |
| **Environment** | Local without Docker | Requires Docker |

**Rule of Thumb**: Unit tests for logic, integration tests for interactions.

## Architecture

### Service Stack

The integration test environment includes:

```{mermaid}
graph TB
    subgraph "Test Runner"
        A["pytest<br/>Integration Tests"]
    end
    
    subgraph "Reverse Proxy"
        B["Caddy<br/>port 80<br/>nemo.localhost<br/>cdcs.localhost<br/>mailpit.localhost<br/>fileserver.localhost"]
    end
    
    subgraph "NEMO"
        C["NEMO Service<br/>port 8000<br/>Django + SQLite"]
    end
    
    subgraph "CDCS"
        D["CDCS<br/>port 8080<br/>Django + uWSGI"]
        E["PostgreSQL<br/>Django DB"]
        F["MongoDB<br/>Record Storage"]
        G["Redis<br/>Celery Queue"]
    end
    
    subgraph "File Serving"
        H["Fileserver<br/>port 8081<br/>pytest HTTP server fixture"]
    end
    
    subgraph "Email Capture"
        I["MailPit SMTP<br/>port 1025<br/>Web UI: 8025"]
    end
    
    A --> B
    B --> C
    B --> D
    B --> H
    B --> I
    D --> E
    D --> F
    D --> G
    
    style A fill:#e3f2fd
    style B fill:#fff9c4
    style C fill:#f3e5f5
    style D fill:#f3e5f5
    style E fill:#ede7f6
    style F fill:#ede7f6
    style G fill:#ede7f6
    style H fill:#e8f5e9
    style I fill:#fce4ec
```

### Data Flow

```{mermaid}
graph TD
    A["NEMO Reservation"] --> B["NEMO Harvester"]
    B --> C["Session Log"]
    C --> D["Record Builder"]
    D --> E["File Discovery"]
    F["Microscopy Files<br/>via Fileserver"] --> E
    E --> G["Metadata Extraction"]
    G --> H["XML Generation"]
    H --> I["CDCS Upload"]
    I --> J["Queryable Records"]
    
    style A fill:#e1f5ff
    style D fill:#fff3e0
    style I fill:#f3e5f5
    style J fill:#e8f5e9
```

## Setup and Configuration

### Prerequisites

- Docker and Docker Compose 2.0+
- `uv` package manager or Python 3.11+
- At least 4GB available RAM for Docker
- Ports 8000, 8025, 8080, 8081, 1025 available

### First Time Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/datasophos/NexusLIMS.git
   cd NexusLIMS
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Start Docker services:**
   ```bash
   cd tests/integration/docker
   docker compose up -d
   
   # Wait for services to be healthy
   docker compose ps  # Check STATUS column
   ```

4. **Verify service connectivity:**
   ```bash
   # NEMO
   curl http://localhost:8000/  # Should return HTML

   # CDCS
   curl http://localhost:8080/  # Should return HTML

   # Fileserver
   curl http://localhost:8081/  # Should return directory listing
   ```

### Environment Configuration

Integration tests automatically configure environment variables via the `env/.env.integration` file:

```bash
# NEMO Configuration
NX_NEMO_ADDRESS_1=http://nemo.localhost/api/
NX_NEMO_TOKEN_1=test_token_12345

# CDCS Configuration
NX_CDCS_URL=http://cdcs.localhost/
NX_CDCS_USER=admin
NX_CDCS_PASS=admin

# Test Data Paths
NX_INSTRUMENT_DATA_PATH=/tmp/nexuslims-test-instrument-data
NX_DATA_PATH=/tmp/nexuslims-test-data
NX_DB_PATH=/tmp/nexuslims-test.db
```

**Note:** Fixtures automatically patch these through the `nexusLIMS.config` module, so manual configuration is rarely needed.

## Running Integration Tests

### Docker Service Management

Integration tests automatically manage Docker services through pytest fixtures. The `docker_services` fixture handles the complete lifecycle:

1. **Startup**: Services start automatically when first integration test runs
2. **Health Checks**: Waits for services to be healthy (NEMO, CDCS, MailPit, etc.)
3. **Teardown**: Services automatically stop and cleanup after all tests complete

**By default**, Docker services are:
- Started once per test session (session-scoped fixture)
- Automatically cleaned up after tests finish
- Have volumes removed to prevent state carryover

### Keeping Docker Services Running (Development)

For development and debugging, you can keep Docker services running between test runs by setting an environment variable. This speeds up the setup phase of the tests so you don't have to wait for the Docker stack to start and stop for every test run:

```bash
# Set this before running tests to keep services up after test completion
export NX_TESTS_KEEP_DOCKER_RUNNING=1

# Run tests - services will stay running after completion
uv run pytest tests/integration/ -v -m integration

# Services now available for manual testing/inspection
docker compose -f tests/integration/docker/docker-compose.yml ps

# Manually stop when done
docker compose -f tests/integration/docker/docker-compose.yml down -v
```

**Benefits of keeping services running:**
- Faster iteration during development (no startup overhead)
- Inspect service logs and state between runs
- Manually test APIs with curl or Postman
- Reproduce issues without full test overhead

### Configure via .env.test (Optional)

You can optionally configure integration test behavior via a `.env.test` file in the repository root. See `.env.test.example` for available configuration options.

### Quick Start

```bash
# From repository root
uv run pytest tests/integration/ -v -m integration
```

### Common Commands

```bash
# Run all integration tests with coverage
uv run pytest tests/integration/ -v -m integration --cov=nexusLIMS

# Run specific test file
uv run pytest tests/integration/test_nemo_integration.py -v

# Run with print statements visible
uv run pytest tests/integration/ -v -m integration -s
```

### Running Without Docker

If you only want to run unit tests (which don't require Docker):

```bash
# Unit tests only (default)
uv run pytest

# Or explicitly
uv run pytest tests/unit/ -v
```

## Test Organization

### Test Files

| File | Purpose | Test Count |
|------|---------|-----------|
| `test_nemo_integration.py` | NEMO API and harvester | 35+ |
| `test_cdcs_integration.py` | CDCS upload and retrieval | 20+ |
| `test_end_to_end_workflow.py` | Complete workflows | 3+ |
| `test_partial_failure_recovery.py` | Error handling | 6+ |
| `test_cli.py` | CLI script testing | 8+ |
| `test_nemo_multi_instance.py` | Multi-NEMO support | 16+ |
| `test_fixtures_smoke.py` | Fixture validation | 20+ |
| `test_fileserver.py` | File serving | 2+ |

### Test Markers

```python
@pytest.mark.integration          # All integration tests (required)
```

**Usage:**
```bash
# Only integration tests
uv run pytest -m "integration" tests/integration/

# Exclude slow tests
uv run pytest -m "integration" tests/integration/
```

## Key Integration Test Patterns

### 1. NEMO Integration Tests

```python
@pytest.mark.integration
def test_nemo_connector_fetches_users(nemo_client):
    """Test fetching users from NEMO API."""
    from nexusLIMS.harvesters.nemo.connector import NemoConnector

    connector = NemoConnector(
        base_url=nemo_client["url"],
        token=nemo_client["token"],
        timezone=nemo_client["timezone"]
    )
    
    users = connector.get_all_users()
    assert len(users) > 0
    assert any(u["username"] == "captain" for u in users)
```

### 2. CDCS Integration Tests

```python
@pytest.mark.integration
def test_cdcs_record_upload(cdcs_client):
    """Test uploading and retrieving records from CDCS."""
    import nexusLIMS.cdcs as cdcs
    
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <Experiment>...</Experiment>'''
    
    record_id = cdcs.upload_record_content(xml_content, "Test Record")
    cdcs_client["register_record"](record_id)
    
    assert record_id is not None
```

### 3. End-to-End Workflow Tests

```python
@pytest.mark.integration
def test_complete_record_building(test_environment_setup):
    """Test complete NEMO → Record Builder → CDCS workflow."""
    from nexusLIMS.harvesters.nemo.utils import add_all_usage_events_to_db
    from nexusLIMS.builder.record_builder import process_new_records
    
    # Harvest from NEMO
    add_all_usage_events_to_db()
    
    # Build and upload records
    process_new_records()
    
    # Verify records in CDCS
    # ... verification ...
```

### 4. Error Handling Tests

```python
@pytest.mark.integration
def test_nemo_connection_failure(nemo_connector, monkeypatch):
    """Test graceful handling of NEMO connection failures."""
    from nexusLIMS.harvesters.nemo.utils import add_all_usage_events_to_db
    
    # Simulate network error
    monkeypatch.setattr(
        "requests.get",
        side_effect=requests.ConnectionError("Network error")
    )
    
    # Should handle gracefully
    with pytest.raises(requests.ConnectionError):
        add_all_usage_events_to_db()
```

## Debugging Integration Tests

### View Service Logs

```bash
cd tests/integration/docker

# View logs from all services
docker compose logs

# View logs from specific service
docker compose logs nemo
docker compose logs cdcs
docker compose logs mailpit

# Follow logs in real-time
docker compose logs -f nemo

# Show last 100 lines
docker compose logs --tail=100
```

### Access Service Web UIs

- **NEMO**: http://nemo.localhost (or http://localhost:8000)
- **CDCS**: http://cdcs.localhost (or http://localhost:8080)
- **MailPit**: http://mailpit.localhost (or http://localhost:8025)
- **Fileserver**: http://fileserver.localhost/data (or http://localhost:8081/data)

### Use Standalone Fileserver

For debugging file serving issues:

```bash
python tests/integration/debug_fileserver.py
```

This starts the same fileserver used in tests on port 8081 for manual testing.

## Troubleshooting

### Services Fail to Start

**Check Docker daemon:**
```bash
docker ps  # Should list running containers
```

**Check service logs:**
```bash
cd tests/integration/docker
docker compose logs nemo
docker compose logs cdcs
```

**Common causes:**
- Ports already in use: `lsof -i :8000`
- Insufficient Docker resources (Docker Desktop settings)
- Previous containers not cleaned: `docker compose down -v`

### Health Checks Timeout

**Increase timeout in `conftest.py`:**
```python
# Change this value (in seconds)
HEALTH_CHECK_TIMEOUT = 300  # Increased from 180
```

**Or skip health checks in development:**
```bash
docker compose up -d --no-health  # Not recommended for CI
```

### Tests Fail with "Connection Refused"

**Ensure services are running:**
```bash
docker compose ps
# STATUS should show "healthy" or "running"
```

**If not healthy, restart:**
```bash
docker compose down -v
docker compose up -d
# Wait for health checks to pass
```

### Database Locks

**If tests hang on database operations:**

1. Stop all tests: `Ctrl+C`
2. Clean up: `rm /tmp/nexuslims-test.db*`
3. Restart services: `docker compose down -v && docker compose up -d`

### CDCS Upload Failures

**Check credentials:**
```bash
# Should return 200
curl -u admin:admin http://localhost:8080/api/v2/templates/
```

**Check XML validity:**
- Use `xmllint`: `xmllint --schema schema.xsd record.xml`
- Validate in CDCS web UI

### Cleanup Issues

**Manual cleanup:**
```bash
# Stop all services
docker compose down

# Remove volumes
docker volume prune -f

# Remove test data
rm -rf /tmp/nexuslims-test-*

# Clean Docker system
docker system prune -a --volumes
```

## Best Practices

### 1. Always Use Fixtures

```python
# Good - uses fixtures
def test_something(nemo_client, cdcs_client):
    # ...

# Bad - hardcoded URLs
def test_something():
    requests.get("http://localhost:8000/")  # Don't do this
```

### 2. Mark Tests Properly

```python
# Good
@pytest.mark.integration
def test_complete_workflow(test_environment_setup):
    # ...

# Bad - missing integration marker
def test_something():
    # ...
```

### 3. Use Descriptive Names

```python
# Good
def test_nemo_harvester_creates_session_for_usage_event():
    # ...

# Bad
def test_harvester():
    # ...
```

### 4. Clean Up Resources

```python
# Good - use cdcs_client fixture
def test_upload(cdcs_client):
    record_id = cdcs.upload_record_content(xml, "Test")
    cdcs_client["register_record"](record_id)  # Auto-cleanup

# Bad - manual cleanup required
def test_upload():
    record_id = cdcs.upload_record_content(xml, "Test")
    # No cleanup = test pollution
```

### 5. Test One Thing Per Test

```python
# Good - tests single behavior
def test_nemo_connector_retrieves_users():
    # Only test user retrieval

# Bad - tests multiple behaviors
def test_nemo_connector_everything():
    # Tests users, tools, projects, and reservations
```

## Performance Optimization

### Session-Scoped Fixtures

Services start once per test session (not per test):

```python
# conftest.py
@pytest.fixture(scope="session")
def docker_services():
    # Starts once, runs for entire session
    # ...
```

This means services stay running across all tests, greatly improving performance.

### Selective Service Startup

If only testing specific components:

```bash
cd tests/integration/docker
docker compose up -d nemo  # Only start NEMO
```

## CI/CD Integration

Integration tests run automatically in GitHub Actions:

- **Trigger**: Every push to `main` or feature branches
- **Schedule**: Nightly at 3 AM UTC
- **Environment**: Ubuntu latest with Docker
- **Timeout**: 600 seconds per test
- **Coverage**: Reported to Codecov with `integration` flag

### Running in GitHub Actions

Tests use pre-built images from GitHub Container Registry when available, falling back to local builds.

**Workflow file:** `.github/workflows/integration-tests.yml`

## Adding New Integration Tests

### Template

```python
"""
Integration tests for [feature].

This module tests [what functionality] by interacting with real
Docker services instead of mocks.
"""

import pytest


@pytest.mark.integration
class Test[FeatureName]:
    """Integration tests for [feature]."""

    def test_[specific_behavior](self, [required_fixtures]):
        """
        Test [what you're testing].

        This test verifies that:
        1. [Behavior one]
        2. [Behavior two]
        3. [Expected outcome]

        Parameters
        ----------
        [fixture_name] : [type]
            Description of fixture
        """
        # Arrange
        # ... setup ...

        # Act
        # ... execute feature ...

        # Assert
        # ... verify results ...
```

### Checklist

```{rst-class} checklist
- ☐ Module docstring explains what's being tested
- ☐ Class docstring summarizes test scope
- ☐ Each test has clear docstring with Parameters section
- ☐ Test is marked with `@pytest.mark.integration`
- ☐ Test name is descriptive (not just "test_something")
- ☐ Test follows Arrange-Act-Assert pattern
- ☐ Test cleans up resources (use fixtures for this)
- ☐ Test is independent (no order dependencies)
- ☐ Test uses fixtures instead of hardcoded values
```

## Further Reading

- **Tests Integration README**: Quick reference guide (see `tests/integration/README.md`)
- **Docker Services Documentation**: Service details (see `tests/integration/docker/README.md`)
- **Shared Test Fixtures**: Available fixtures (see `tests/fixtures/shared_data.py`)

## Support

For issues or questions:

1. Check the readme in `tests/integration/README.md`
2. Review test logs: `docker compose logs`
3. Search [GitHub Issues](https://github.com/datasophos/NexusLIMS/issues)
4. Open a new issue with logs and reproduction steps
