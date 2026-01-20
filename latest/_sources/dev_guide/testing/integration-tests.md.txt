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
| **Speed** | Very fast (seconds) | Slower (potentially minutes) |
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
   # NEMO (via Caddy reverse proxy)
   curl http://nemo.localhost/  # Should return HTML

   # CDCS (via Caddy reverse proxy)
   curl http://cdcs.localhost/  # Should return HTML

   # Mailpit (via Caddy reverse proxy)
   curl http://mailpit.localhost/  # Should return directory listing

   # Fileserver (via Caddy reverse proxy)
   # the fileserver only runs while the tests are actually running,
   # so the URL below will not be available unless tests are running
   curl http://fileserver.localhost/
   ```

### Environment Configuration

Fixtures automatically patch configuration variables through `nexusLIMS.config`, so there's no envrionment configuration necessary.

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
uv run pytest tests/integration/ -v

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

You can optionally configure integration test behavior via a
`.env.test` file in the repository root. See `.env.test.example`
for available configuration options. Currently the only option
is the `NX_TESTS_KEEP_DOCKER_RUNNING` setting.

### Quick Start

```bash
# From repository root
uv run pytest tests/integration/ -v
```

### Common Commands

```bash
# Run all integration tests with coverage
uv run pytest tests/integration/ -v --cov=nexusLIMS

# Run specific test file
uv run pytest tests/integration/test_nemo_integration.py -v

# Run with print statements visible
uv run pytest tests/integration/ -v -s
```

### Running Without Docker

If you only want to run unit tests (which don't require Docker):

```bash
# Unit tests only (default)
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

## Key Integration Test Patterns

### 1. NEMO Integration Tests

The `nemo_client` fixture provides connection information for the NEMO Docker instance:
- `nemo_client["url"]`: NEMO API base URL (e.g., `http://nemo.localhost/api/`)
- `nemo_client["token"]`: Authentication token for API requests
- `nemo_client["timezone"]`: Timezone string for datetime handling (e.g., `"America/New_York"`)

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

#### Testing NEMO Usage Event Questions

NEMO usage events can contain experiment metadata in two JSON-encoded fields:
- **`run_data`**: Questions answered at the **end** of instrument usage (highest priority)
- **`pre_run_data`**: Questions answered at the **start** of instrument usage (medium priority)

The harvester implements a three-tier fallback strategy (run_data → pre_run_data → reservation matching) to obtain the most accurate metadata. Integration tests verify this behavior using test usage events (IDs 100-106) seeded in the NEMO Docker instance.

**Test usage events in `seed_data.json`:**

| Event ID | `run_data` | `pre_run_data` | Test Purpose |
|----------|------------|----------------|--------------|
| 100 | Valid questions | Empty | Tests Priority 1: run_data |
| 101 | Empty | Valid questions | Tests Priority 2: pre_run_data |
| 102 | Valid questions | Valid questions | Tests run_data priority over pre_run_data |
| 103 | Empty | "Disagree" consent | Tests consent validation and fallback |
| 104 | Missing user_input fields | Empty | Tests graceful handling of incomplete data |
| 105 | Empty strings | Empty strings | Tests fallback to reservation matching |
| 106 | Malformed JSON | Malformed JSON | Tests JSON parsing error handling |

**Example test:**

```python
@pytest.mark.integration
def test_usage_event_with_run_data(test_instrument, nemo_connector):
    """Verify run_data is used when populated."""
    from nexusLIMS.db.session_handler import Session
    from nexusLIMS.harvesters.nemo import res_event_from_session

    # Create session for usage event 100 (has run_data)
    session = Session(
        instrument=test_instrument,
        session_identifier="http://nemo.localhost/api/usage_events/100/",
        dt_from=datetime(2024, 7, 1, 10, 0, tzinfo=timezone.utc),
        dt_to=datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc),
        user="captain",
    )

    res_event = res_event_from_session(session, nemo_connector)

    # Verify metadata came from run_data (not reservation)
    assert res_event.experiment_title == "Au-TiO2 characterization"
    assert res_event.experiment_purpose == "Measuring particle size distribution"
    assert "http://nemo.localhost/event_details/usage/100/" in res_event.url
```

**Test coverage includes:**
- Three-tier priority ordering (run_data > pre_run_data > reservation)
- Data consent validation and rejection
- JSON parsing error handling
- Empty/missing field fallback behavior
- Operator vs. user field handling
- Helper function validation (`has_valid_question_data()`)

See `TestNemoUsageEventQuestions` class in `tests/integration/test_nemo_integration.py` for complete test suite.

### 2. CDCS Integration Tests

The `cdcs_client` fixture provides connection information and utilities for the CDCS Docker instance:
- `cdcs_client["url"]`: CDCS base URL (e.g., `http://cdcs.localhost/`)
- `cdcs_client["username"]`: Authentication username for CDCS API
- `cdcs_client["password"]`: Authentication password for CDCS API
- `cdcs_client["register_record"](record_id)`: Register a record ID for automatic cleanup after test
- `cdcs_client["created_records"]`: List of all registered record IDs

```python
@pytest.mark.integration
def test_cdcs_record_upload(cdcs_client):
    """Test uploading and retrieving records from CDCS."""
    import nexusLIMS.cdcs as cdcs

    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <Experiment>...</Experiment>'''

    record_id = cdcs.upload_record_content(xml_content, "Test Record")
    cdcs_client["register_record"](record_id)  # Auto-cleanup after test

    assert record_id is not None
```

### 3. End-to-End Workflow Tests

The `test_environment_setup` fixture configures a complete end-to-end test environment with all services and test data:
- `test_environment_setup["instrument_pid"]`: Test instrument ID (e.g., `"FEI-Titan-TEM"`)
- `test_environment_setup["dt_from"]`: Expected session start datetime
- `test_environment_setup["dt_to"]`: Expected session end datetime
- `test_environment_setup["user"]`: Expected username for test session
- `test_environment_setup["instrument_db"]`: Configured test instrument database
- `test_environment_setup["cdcs_client"]`: CDCS client configuration

This fixture automatically:
- Starts all Docker services (NEMO, CDCS, MailPit, fileserver)
- Configures NEMO harvester with test data
- Sets up test database with instruments
- Extracts test microscopy files
- Configures CDCS client for uploads

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

The `nemo_connector` fixture provides a pre-configured `NemoConnector` instance for testing. It differs from `nemo_client` in that:
- **`nemo_client`**: Returns a dict with connection information (URL, token, timezone) - use when you need to manually create a connector or test connection parameters
- **`nemo_connector`**: Returns a ready-to-use `NemoConnector` instance configured with test database and NEMO client settings - use when you just need a working connector

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

- **NEMO**: [http://nemo.localhost](http://nemo.localhost) (or [http://localhost:8000](http://localhost:8000))
- **CDCS**: [http://cdcs.localhost](http://cdcs.localhost) (or [http://localhost:8080](http://localhost:8080)) -- this can be useful to inspect records during/after tests
- **MailPit**: [http://mailpit.localhost](http://mailpit.localhost) (or [http://localhost:8025](http://localhost:8025))
- **Fileserver**: [http://fileserver.localhost/data](http://fileserver.localhost/data) (or [http://localhost:8081/data](http://localhost:8081/data))

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
# Should return 200 status with some workspace data
curl -u admin:admin http://cdcs.localhost/rest/workspace/
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

- **Tests Integration README**: Quick reference guide in `tests/integration/README.md`
- **Docker Services Documentation**: Service details in `tests/integration/docker/README.md`
- **Shared Test Fixtures**: Available fixtures (see [`tests/fixtures/shared_data.py`](../../../tests/fixtures/shared_data.py))

## Support

For issues or questions:

1. Check the readme in `tests/integration/README.md`
2. Review test logs: `docker compose logs`
3. Search [GitHub Issues](https://github.com/datasophos/NexusLIMS/issues)
4. Open a new issue with logs and reproduction steps
