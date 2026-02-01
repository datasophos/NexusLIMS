# eLabFTW API Client Implementation Plan

## Implementation Status

**Last Updated**: 2026-01-31

### Progress Overview

| Phase | Status | Files | Notes |
|-------|--------|-------|-------|
| 1. Configuration | ✅ **Complete** | `nexusLIMS/config.py`, `.env.example` | Added 4 eLabFTW settings with test defaults |
| 2. API Client | ✅ **Complete** | `nexusLIMS/utils/elabftw.py` | Low-level eLabFTW API wrapper with CRUD methods |
| 3. Export Plugin | ✅ **Complete** | `nexusLIMS/exporters/destinations/elabftw.py` | Export destination with markdown body and XML attachment |
| 4. Unit Tests | ✅ **Complete** | `tests/unit/test_exporters/test_elabftw.py` | 76 tests, 99% coverage |
| 5. Docker Stack | ✅ **Complete** | `tests/integration/docker/*` | MySQL + eLabFTW + Caddy configured |
| 6. Integration Tests | 🟡 In Progress | `tests/integration/test_elabftw_integration.py` | Skeleton with smoke tests |
| 7. Documentation | ❌ Not Started | User guide, changelog | Configuration docs needed |
| 8. Validation | ❌ Not Started | End-to-end testing | Awaits implementation |

### Completed Items ✅

- [x] Docker Compose configuration for eLabFTW + MySQL services
- [x] eLabFTW database initialization script (`init_elabftw.py`)
- [x] Caddy reverse proxy configuration for eLabFTW
- [x] Docker volumes and networking setup
- [x] Basic integration test file with smoke tests
- [x] eLabFTW setup documentation (`tests/integration/docker/elabftw/README.md`)
- [x] **Configuration settings** - Added `NX_ELABFTW_API_KEY`, `NX_ELABFTW_URL`, `NX_ELABFTW_EXPERIMENT_CATEGORY`, `NX_ELABFTW_EXPERIMENT_STATUS` to `config.py`
- [x] **Environment variable documentation** - Added eLabFTW configuration section to `.env.example`
- [x] **Pytest markers** - Verified existing `integration` marker is suitable for eLabFTW tests
- [x] **Configuration tests** - Added 8 comprehensive tests to `tests/unit/test_config.py` covering all config scenarios
- [x] **API Client** - Implemented `nexusLIMS/utils/elabftw.py` with full CRUD operations (create, read, list, update, delete experiments) and file upload functionality
- [x] **Export Plugin** - Implemented `nexusLIMS/exporters/destinations/elabftw.py` with markdown body generation, CDCS cross-linking, and XML attachment upload
- [x] **Unit Tests** - Implemented 76 comprehensive tests in `tests/unit/test_exporters/test_elabftw.py` with 99% code coverage (100% for API client, 97% for export plugin)

### Next Steps 🎯

1. ~~**Add Configuration**~~ ✅ - ~~Add `NX_ELABFTW_API_KEY`, `NX_ELABFTW_URL`, etc. to `nexusLIMS/config.py`~~
2. ~~**Implement API Client**~~ ✅ - ~~Create `nexusLIMS/utils/elabftw.py` with CRUD methods~~
3. ~~**Implement Export Plugin**~~ ✅ - ~~Create `nexusLIMS/exporters/destinations/elabftw.py`~~
4. ~~**Write Unit Tests**~~ ✅ - ~~76 tests with 99% coverage~~
5. **Complete Integration Tests** - Add full workflow tests to existing skeleton
6. **Update Documentation** - User guide, changelog fragments

### Estimated Remaining Work

- **Total planned**: 17-26 hours
- **Completed**: ~14.5-19.5 hours (Docker + config + API client + export plugin + unit tests)
- **Remaining**: ~2.5-6.5 hours (integration tests + documentation)

---

## Overview

Implement a basic eLabFTW API client for NexusLIMS that enables exporting microscopy session records to eLabFTW electronic lab notebooks. The implementation follows NexusLIMS's plugin-based export architecture with CRUD operations for experiments.

## Scope

- **Basic CRUD**: Create, read, update, delete experiments (not complete API coverage)
- **Export integration**: Plugin for the NexusLIMS record builder workflow
- **Configuration**: Environment variable-based for different eLabFTW installations
- **Initial focus**: Experiments only (Items support deferred to future work)

## Architecture

**Two-module approach** (mirrors existing CDCS pattern):

1. **Low-level API client** (`nexusLIMS/utils/elabftw.py`): Reusable eLabFTW API wrapper
2. **Export destination plugin** (`nexusLIMS/exporters/destinations/elabftw.py`): Integration with record builder

## Implementation Details

### 1. Low-Level API Client (`nexusLIMS/utils/elabftw.py`)

**Purpose**: Reusable client for eLabFTW API v2 operations (testing, maintenance, queries)

**Key Components**:

```python
class ELabFTWClient:
    """Low-level client for eLabFTW API v2."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize with instance URL and API key."""

    # Core CRUD methods
    def create_experiment(self, title, body, **kwargs) -> dict
    def get_experiment(self, experiment_id: int) -> dict
    def list_experiments(self, limit=15, offset=0, query=None) -> list[dict]
    def update_experiment(self, experiment_id: int, **kwargs) -> dict
    def delete_experiment(self, experiment_id: int) -> None

    # File operations
    def upload_file_to_experiment(self, experiment_id, file_path, comment) -> dict

# Helper function
def get_elabftw_client() -> ELabFTWClient:
    """Get configured client from settings."""
```

**Implementation notes**:
- Use `nexus_req()` from `nexusLIMS.utils.network` for all HTTP calls
- eLabFTW uses direct API key auth: `headers = {"Authorization": api_key}`
- Base endpoint: `{base_url}/api/v2/experiments`
- Custom exceptions: `ELabFTWError`, `ELabFTWAuthenticationError`, `ELabFTWNotFoundError`
- Handle status codes: 201 (created), 401 (auth failed), 404 (not found)

### 2. Export Destination Plugin (`nexusLIMS/exporters/destinations/elabftw.py`)

**Purpose**: Export NexusLIMS XML records to eLabFTW experiments

**Key Components**:

```python
class ELabFTWDestination:
    """eLabFTW export destination plugin."""

    name = "elabftw"
    priority = 85  # After CDCS (100), before LabArchives (90)

    @property
    def enabled(self) -> bool:
        """Check if configured (API key and URL present)."""

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate by testing API access (list experiments limit=1)."""

    def export(self, context: ExportContext) -> ExportResult:
        """Export record - NEVER raises exceptions."""
```

**Export workflow**:
1. Read XML file from `context.xml_file_path`
2. Check for CDCS result via `context.get_result("cdcs")` for cross-linking
3. Create experiment with:
   - **Title**: `NexusLIMS - {instrument_id} - {session_id}`
   - **Body**: Markdown summary with session details and CDCS link
   - **Tags**: `["NexusLIMS", "{instrument_id}", "{username}"]`
   - **Metadata**: JSON with session info
4. Upload XML file as attachment with comment "NexusLIMS XML record"
5. Return `ExportResult` with experiment ID and URL

**Markdown body template**:
```markdown
# NexusLIMS Microscopy Session

## Session Details
- **Session ID**: {session_id}
- **Instrument**: {instrument_pid}
- **User**: {user}
- **Start**: {dt_from}
- **End**: {dt_to}

## Related Records
- [View in CDCS]({cdcs_url})

## Files
The complete NexusLIMS XML record is attached to this experiment.
```

**Error handling**:
- All exceptions caught in `export()` method
- Return `ExportResult(success=False, error_message=str(e))`
- Log with `_logger.exception()` for debugging

### 3. Configuration (`nexusLIMS/config.py`)

Add settings:

```python
NX_ELABFTW_API_KEY: str | None = Field(
    "test_elabftw_key" if TEST_MODE else None,
    description="API key from eLabFTW user panel. If not configured, export disabled.",
)

NX_ELABFTW_URL: TestAwareHttpUrl | None = Field(
    "http://localhost:3148" if TEST_MODE else None,
    description="Root URL of eLabFTW instance. If not configured, export disabled.",
)

NX_ELABFTW_EXPERIMENT_CATEGORY: int | None = Field(
    None,
    description="Default category ID (optional - uses eLabFTW default if not set).",
)

NX_ELABFTW_EXPERIMENT_STATUS: int | None = Field(
    None,
    description="Default status ID (optional - uses eLabFTW default if not set).",
)
```

**Update `.env.example`**:
```bash
## eLabFTW API configuration (optional)
# NX_ELABFTW_API_KEY='your-api-key'
# NX_ELABFTW_URL='https://elabftw.example.com'
# NX_ELABFTW_EXPERIMENT_CATEGORY=1
# NX_ELABFTW_EXPERIMENT_STATUS=1
```

### 4. Unit Testing Strategy

**Test file**: `tests/unit/test_exporters/test_elabftw.py`

**Test coverage target**: 100%

#### 4.1 Unit Test Classes

**TestELabFTWClient** - Low-level API client tests (mocked HTTP)

```python
class TestELabFTWClient:
    """Test eLabFTW API client with mocked HTTP responses."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return ELabFTWClient(
            base_url="https://elab.example.com",
            api_key="test-api-key-12345"
        )

    @pytest.fixture
    def mock_nexus_req(self):
        """Mock nexus_req for HTTP isolation."""
        with patch("nexusLIMS.utils.elabftw.nexus_req") as mock:
            yield mock

    # CREATE tests
    def test_create_experiment_success(self, client, mock_nexus_req):
        """Test successful experiment creation returns dict with id."""

    def test_create_experiment_with_all_fields(self, client, mock_nexus_req):
        """Test creating experiment with title, body, tags, metadata."""

    def test_create_experiment_auth_failure(self, client, mock_nexus_req):
        """Test 401 response raises ELabFTWAuthenticationError."""

    def test_create_experiment_api_error(self, client, mock_nexus_req):
        """Test 500 response raises ELabFTWError."""

    # READ tests
    def test_get_experiment_success(self, client, mock_nexus_req):
        """Test retrieving experiment by ID returns full dict."""

    def test_get_experiment_not_found(self, client, mock_nexus_req):
        """Test 404 response raises ELabFTWNotFoundError."""

    def test_list_experiments_default_params(self, client, mock_nexus_req):
        """Test listing with default limit=15, offset=0."""

    def test_list_experiments_with_pagination(self, client, mock_nexus_req):
        """Test listing with custom limit and offset."""

    def test_list_experiments_with_query(self, client, mock_nexus_req):
        """Test full-text search parameter."""

    # UPDATE tests
    def test_update_experiment_success(self, client, mock_nexus_req):
        """Test PATCH request updates experiment."""

    def test_update_experiment_partial_fields(self, client, mock_nexus_req):
        """Test updating only title or body."""

    # DELETE tests
    def test_delete_experiment_success(self, client, mock_nexus_req):
        """Test DELETE returns None on 204 No Content."""

    def test_delete_experiment_not_found(self, client, mock_nexus_req):
        """Test deleting non-existent experiment."""

    # FILE UPLOAD tests
    def test_upload_file_success(self, client, mock_nexus_req, tmp_path):
        """Test file upload to experiment."""

    def test_upload_file_with_comment(self, client, mock_nexus_req, tmp_path):
        """Test upload includes comment field."""

    def test_upload_file_not_found(self, client, mock_nexus_req, tmp_path):
        """Test upload to non-existent experiment fails."""

    # HELPER FUNCTION tests
    def test_get_elabftw_client_success(self, mock_settings):
        """Test helper returns configured client."""

    def test_get_elabftw_client_missing_config(self):
        """Test helper raises ValueError when not configured."""

    # AUTHENTICATION tests
    def test_client_uses_correct_auth_header(self, client, mock_nexus_req):
        """Verify Authorization header format (not Bearer token)."""

    def test_client_constructs_correct_endpoints(self, client, mock_nexus_req):
        """Verify base_url/api/v2/experiments endpoint construction."""
```

**TestELabFTWDestinationConfiguration** - Plugin configuration tests

```python
class TestELabFTWDestinationConfiguration:
    """Test eLabFTW export destination configuration."""

    @pytest.fixture
    def destination(self):
        """Create destination instance."""
        return ELabFTWDestination()

    # BASIC PROPERTIES tests
    def test_name_is_elabftw(self, destination):
        """Verify name='elabftw'."""

    def test_priority_is_85(self, destination):
        """Verify priority=85 (after CDCS, before LabArchives)."""

    # ENABLED PROPERTY tests
    def test_enabled_with_full_config(self, destination, mock_settings):
        """Test enabled=True when API key and URL configured."""

    def test_enabled_without_api_key(self, destination, mock_settings):
        """Test enabled=False when NX_ELABFTW_API_KEY missing."""

    def test_enabled_without_url(self, destination, mock_settings):
        """Test enabled=False when NX_ELABFTW_URL missing."""

    def test_enabled_with_empty_api_key(self, destination, mock_settings):
        """Test enabled=False when API key is None."""

    def test_enabled_with_empty_url(self, destination, mock_settings):
        """Test enabled=False when URL is None."""

    # VALIDATE_CONFIG tests
    def test_validate_config_success(self, destination, mock_settings, mock_client):
        """Test validation succeeds with good config and API access."""

    def test_validate_config_missing_api_key(self, destination, mock_settings):
        """Test validation returns (False, 'NX_ELABFTW_API_KEY not configured')."""

    def test_validate_config_missing_url(self, destination, mock_settings):
        """Test validation returns (False, 'NX_ELABFTW_URL not configured')."""

    def test_validate_config_empty_api_key(self, destination, mock_settings):
        """Test validation returns (False, 'NX_ELABFTW_API_KEY is empty')."""

    def test_validate_config_auth_failure(self, destination, mock_settings, mock_client):
        """Test validation fails when API returns 401."""

    def test_validate_config_network_error(self, destination, mock_settings, mock_client):
        """Test validation fails on connection error."""
```

**TestELabFTWDestinationExport** - Export workflow tests

```python
class TestELabFTWDestinationExport:
    """Test eLabFTW export destination export workflow."""

    @pytest.fixture
    def destination(self):
        """Create destination instance."""
        return ELabFTWDestination()

    @pytest.fixture
    def export_context(self, tmp_path):
        """Create ExportContext with sample XML file."""
        xml_file = tmp_path / "test_record.xml"
        xml_file.write_text("<record><data>test</data></record>")

        return ExportContext(
            xml_file_path=xml_file,
            session_identifier="2025-01-27_10-30-15_abc123",
            instrument_pid="FEI-Titan-TEM-012345",
            dt_from=datetime(2025, 1, 27, 10, 30, 15),
            dt_to=datetime(2025, 1, 27, 14, 45, 0),
            user="jsmith",
        )

    # SUCCESSFUL EXPORT tests
    def test_export_success(self, destination, export_context, mock_client):
        """Test successful export returns ExportResult(success=True)."""

    def test_export_creates_experiment(self, destination, export_context, mock_client):
        """Verify experiment created with correct title."""

    def test_export_includes_markdown_body(self, destination, export_context, mock_client):
        """Verify body contains session metadata."""

    def test_export_attaches_xml_file(self, destination, export_context, mock_client):
        """Verify XML file uploaded as attachment."""

    def test_export_applies_tags(self, destination, export_context, mock_client):
        """Verify tags include NexusLIMS, instrument, user."""

    def test_export_includes_metadata_json(self, destination, export_context, mock_client):
        """Verify metadata dict includes session_id, instrument, timestamps."""

    def test_export_returns_experiment_url(self, destination, export_context, mock_client):
        """Verify record_url points to eLabFTW experiment."""

    # CDCS CROSS-LINKING tests
    def test_export_with_cdcs_result(self, destination, export_context, mock_client):
        """Test CDCS URL included in body when available."""

    def test_export_without_cdcs_result(self, destination, export_context, mock_client):
        """Test export succeeds without CDCS link."""

    def test_export_with_failed_cdcs_result(self, destination, export_context, mock_client):
        """Test no CDCS link when CDCS export failed."""

    # ERROR HANDLING tests (critical: export() NEVER raises)
    def test_export_catches_file_read_error(self, destination, export_context):
        """Test missing XML file returns ExportResult(success=False)."""

    def test_export_catches_api_errors(self, destination, export_context, mock_client):
        """Test API errors caught and returned as failure."""

    def test_export_catches_all_exceptions(self, destination, export_context):
        """Test unexpected exceptions caught and logged."""

    def test_export_logs_exceptions(self, destination, export_context, caplog):
        """Verify _logger.exception() called on errors."""

    # MARKDOWN GENERATION tests
    def test_markdown_body_structure(self, destination, export_context):
        """Test generated markdown has all required sections."""

    def test_markdown_includes_session_id(self, destination, export_context):
        """Test session_identifier in body."""

    def test_markdown_includes_timestamps(self, destination, export_context):
        """Test dt_from and dt_to formatted correctly."""

    def test_markdown_includes_user(self, destination, export_context):
        """Test username appears in body."""

    def test_markdown_with_none_user(self, destination, export_context):
        """Test handles None user gracefully."""

    # RESULT STRUCTURE tests
    def test_result_has_correct_destination_name(self, destination, export_context, mock_client):
        """Verify destination_name='elabftw'."""

    def test_result_includes_record_id(self, destination, export_context, mock_client):
        """Verify record_id is experiment ID as string."""

    def test_result_has_timestamp(self, destination, export_context, mock_client):
        """Verify timestamp field populated."""
```

#### 4.2 Test Execution

```bash
# Run all eLabFTW unit tests
uv run pytest tests/unit/test_exporters/test_elabftw.py -v

# Run with coverage
uv run pytest tests/unit/test_exporters/test_elabftw.py --cov=nexusLIMS.utils.elabftw --cov=nexusLIMS.exporters.destinations.elabftw --cov-report=html

# Run specific test class
uv run pytest tests/unit/test_exporters/test_elabftw.py::TestELabFTWClient -v
```

### 5. Integration Testing Strategy

Integration tests verify the complete workflow with a real eLabFTW instance running in Docker.

#### 5.1 Docker Stack Configuration

**Add to `tests/integration/docker/docker-compose.yml`:**

```yaml
  # MySQL for eLabFTW
  elabftw-mysql:
    image: mysql:8.4
    container_name: nexuslims-test-elabftw-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=nexuslims_elabftw_root
      - MYSQL_DATABASE=elabftw
      - MYSQL_USER=elabftw
      - MYSQL_PASSWORD=nexuslims_elabftw
    volumes:
      - elabftw-mysql-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "elabftw", "-pnexuslims_elabftw"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - nexuslims-test

  # eLabFTW database initialization (runs once, then exits)
  elabftw-init:
    image: python:3.12-slim
    container_name: nexuslims-test-elabftw-init
    depends_on:
      elabftw-mysql:
        condition: service_healthy
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./elabftw/init_elabftw.py:/init_elabftw.py:ro
      - elabftw-init-marker:/tmp
    command: >
      sh -c "
      pip install --quiet bcrypt mysql-connector-python &&
      python /init_elabftw.py
      "
    networks:
      - nexuslims-test

  # eLabFTW service
  elabftw:
    image: elabftw/elabimg:5.3.11
    container_name: nexuslims-test-elabftw
    ports:
      - "48148:443"
    depends_on:
      elabftw-mysql:
        condition: service_healthy
      elabftw-init:
        condition: service_completed_successfully
    environment:
      - DB_HOST=elabftw-mysql
      - DB_NAME=elabftw
      - DB_USER=elabftw
      - DB_PASSWORD=nexuslims_elabftw
      - SECRET_KEY=nexuslims-test-secret-key-do-not-use-in-production
      - SERVER_NAME=elabftw.localhost
      - SITE_URL=https://elabftw.localhost:48148
      - DISABLE_HTTPS=false
      - PHP_TIMEZONE=America/New_York
    volumes:
      - elabftw-uploads:/elabftw/uploads
      - elabftw-init-marker:/tmp
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
      - FOWNER
      - DAC_OVERRIDE
    security_opt:
      - no-new-privileges
    healthcheck:
      test: ["CMD", "curl", "-fk", "https://elabftw:443/login.php"]
      interval: 10s
      timeout: 5s
      retries: 15
      start_period: 60s
    networks:
      - nexuslims-test

volumes:
  elabftw-mysql-data:
  elabftw-uploads:
  elabftw-init-marker:
```

**Add to Caddyfile** (`tests/integration/docker/caddy/Caddyfile`):

```
elabftw.localhost {
    reverse_proxy https://elabftw:443 {
        transport http {
            tls_insecure_skip_verify
        }
    }
}
```

**Update caddy-proxy service** in `docker-compose.yml`:

```yaml
  caddy-proxy:
    # ... existing config ...
    extra_hosts:
      - "nemo.localhost:127.0.0.1"
      - "nemo2.localhost:127.0.0.1"
      - "cdcs.localhost:127.0.0.1"
      - "elabftw.localhost:127.0.0.1"  # ADD THIS LINE
      - "fileserver.localhost:127.0.0.1"
      - "mailpit.localhost:127.0.0.1"
      - "host.docker.internal:host-gateway"
    depends_on:
      - nemo
      - cdcs
      - elabftw  # ADD THIS LINE
      - mailpit
```

#### 5.2 Integration Test File

**Test file**: `tests/integration/test_elabftw_integration.py`

```python
"""Integration tests for eLabFTW export destination.

These tests run against a real eLabFTW instance in Docker and verify:
- API client CRUD operations
- Export destination workflow
- File uploads
- Cross-linking with CDCS
- Database logging

Requires: docker compose up -d (in tests/integration/docker/)
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.db.models import UploadLog
from nexusLIMS.exporters import export_records
from nexusLIMS.exporters.base import ExportContext
from nexusLIMS.utils.elabftw import ELabFTWClient, get_elabftw_client


# eLabFTW service URL (via Caddy proxy)
ELABFTW_URL = "https://elabftw.localhost:40080"

# Test credentials (need to be created in eLabFTW after startup)
# See setup instructions in tests/integration/docker/elabftw/README.md
ELABFTW_API_KEY = "test-api-key-from-elabftw-panel"


@pytest.fixture(scope="module")
def elabftw_client():
    """Create eLabFTW client for integration tests."""
    return ELabFTWClient(base_url=ELABFTW_URL, api_key=ELABFTW_API_KEY)


@pytest.fixture
def sample_xml_file(tmp_path):
    """Create sample XML record for testing."""
    xml_file = tmp_path / "integration_test_record.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<record>
    <session>integration-test-session</session>
    <instrument>FEI-Titan-TEM</instrument>
    <data>Integration test experiment data</data>
</record>"""
    xml_file.write_text(xml_content)
    return xml_file


class TestELabFTWClientIntegration:
    """Integration tests for ELabFTWClient with real API."""

    @pytest.mark.integration
    def test_create_and_get_experiment(self, elabftw_client):
        """Test creating experiment and retrieving it."""

    @pytest.mark.integration
    def test_list_experiments(self, elabftw_client):
        """Test listing experiments with pagination."""

    @pytest.mark.integration
    def test_update_experiment(self, elabftw_client):
        """Test updating experiment fields."""

    @pytest.mark.integration
    def test_delete_experiment(self, elabftw_client):
        """Test soft-deleting experiment."""

    @pytest.mark.integration
    def test_upload_file(self, elabftw_client, tmp_path):
        """Test uploading file to experiment."""

    @pytest.mark.integration
    def test_create_with_tags_and_metadata(self, elabftw_client):
        """Test creating experiment with tags and metadata."""


class TestELabFTWDestinationIntegration:
    """Integration tests for ELabFTWDestination export workflow."""

    @pytest.mark.integration
    def test_export_creates_experiment(self, sample_xml_file, mock_settings):
        """Test export workflow creates experiment in eLabFTW."""

    @pytest.mark.integration
    def test_export_uploads_xml_attachment(self, sample_xml_file, mock_settings):
        """Test XML file attached to experiment."""

    @pytest.mark.integration
    def test_export_with_cdcs_crosslink(self, sample_xml_file, mock_settings):
        """Test CDCS URL appears in experiment body."""

    @pytest.mark.integration
    def test_export_logs_to_database(self, sample_xml_file, db_session, mock_settings):
        """Test UploadLog entry created for export."""

    @pytest.mark.integration
    def test_multi_destination_export(self, sample_xml_file, sample_session, mock_settings):
        """Test exporting to both CDCS and eLabFTW."""


class TestELabFTWEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_record_builder_workflow(self, test_database, mock_settings):
        """Test complete workflow: build record → export to eLabFTW."""
```

#### 5.3 Automated eLabFTW Initialization

**File**: `tests/integration/docker/elabftw/init_elabftw.py`

```python
#!/usr/bin/env python3
"""Initialize eLabFTW test database with seed data.

This script seeds an eLabFTW MySQL database with test data for integration testing.
Unlike NEMO/CDCS which use Django/Python ORMs, eLabFTW is a PHP application, so we
directly manipulate the MySQL database to create test users and API keys.

The script creates:
- A default test team
- A test user with known credentials
- An API key with a predictable value for testing
- A marker file to prevent re-initialization

Password hashing: eLabFTW uses PHP's password_hash() with PASSWORD_BCRYPT
API key format: {id}-{84_char_hex_string}, stored as bcrypt hash
"""

import hashlib
import sys
import time
from pathlib import Path

import bcrypt
import mysql.connector
from mysql.connector import Error


# Test configuration
TEST_USER = {
    "email": "testuser@example.com",
    "firstname": "Test",
    "lastname": "User",
    "password": "testpass123",  # Will be bcrypt hashed
    "validated": 1,  # User is validated (can log in)
    "lang": "en_GB",
}

TEST_TEAM = {
    "name": "Test Team",
}

# Predictable API key for testing
# Format: {id}-{key}
# The key component is 84 hex characters (42 random bytes)
TEST_API_KEY_RAW = "1-" + "a" * 84  # ID will be 1, key is 84 'a's
TEST_API_KEY_NAME = "NexusLIMS Integration Test Key"

# Database connection settings (from docker-compose.yml)
DB_CONFIG = {
    "host": "elabftw-mysql",
    "user": "elabftw",
    "password": "nexuslims_elabftw",
    "database": "elabftw",
}

MARKER_FILE = Path("/tmp/elabftw_init_complete")


def wait_for_database(max_retries=30, delay=2):
    """Wait for MySQL database to be ready."""
    print("Waiting for MySQL database to be ready...")
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            conn.close()
            print("  ✓ Database is ready!")
            return True
        except Error as e:
            if attempt < max_retries - 1:
                print(f"  - Attempt {attempt + 1}/{max_retries}: {e}")
                time.sleep(delay)
            else:
                print(f"  ✗ Failed to connect after {max_retries} attempts", file=sys.stderr)
                return False
    return False


def hash_password(password):
    """Hash password using bcrypt (matching PHP's PASSWORD_BCRYPT)."""
    # Python bcrypt produces hashes compatible with PHP's password_hash()
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def hash_api_key(api_key):
    """Hash API key using bcrypt (matching PHP's password_hash()).

    API keys are formatted as {id}-{key}, but only the key portion is hashed.
    """
    # Extract key portion (everything after the first hyphen)
    key_portion = api_key.split('-', 1)[1] if '-' in api_key else api_key
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(key_portion.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_team(cursor):
    """Create test team and return its ID."""
    print("Creating test team...")

    # Check if team already exists
    cursor.execute("SELECT id FROM teams WHERE name = %s", (TEST_TEAM["name"],))
    existing = cursor.fetchone()

    if existing:
        team_id = existing[0]
        print(f"  - Team already exists with ID: {team_id}")
        return team_id

    # Create team with minimal required fields
    cursor.execute(
        """
        INSERT INTO teams (name, common_template, common_template_md)
        VALUES (%s, '', '')
        """,
        (TEST_TEAM["name"],)
    )
    team_id = cursor.lastrowid
    print(f"  ✓ Created team: {TEST_TEAM['name']} (ID: {team_id})")
    return team_id


def create_user(cursor, team_id):
    """Create test user and return user ID."""
    print("Creating test user...")

    # Check if user already exists
    cursor.execute("SELECT userid FROM users WHERE email = %s", (TEST_USER["email"],))
    existing = cursor.fetchone()

    if existing:
        user_id = existing[0]
        print(f"  - User already exists with ID: {user_id}")
        return user_id

    # Hash password
    password_hash = hash_password(TEST_USER["password"])

    # Create user with required fields
    # default_read and default_write are JSON fields with default permissions
    cursor.execute(
        """
        INSERT INTO users (
            email, firstname, lastname, password_hash, validated, lang,
            default_read, default_write
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            TEST_USER["email"],
            TEST_USER["firstname"],
            TEST_USER["lastname"],
            password_hash,
            TEST_USER["validated"],
            TEST_USER["lang"],
            '{"base": 20, "teams": [], "teamgroups": [], "users": []}',  # TeamBasePermissions
            '{"base": 10, "teams": [], "teamgroups": [], "users": []}',  # UserBasePermissions
        )
    )
    user_id = cursor.lastrowid
    print(f"  ✓ Created user: {TEST_USER['email']} (ID: {user_id})")
    return user_id


def add_user_to_team(cursor, user_id, team_id):
    """Add user to team (users2teams junction table)."""
    print("Adding user to team...")

    # Check if relationship already exists
    cursor.execute(
        "SELECT 1 FROM users2teams WHERE users_id = %s AND teams_id = %s",
        (user_id, team_id)
    )
    existing = cursor.fetchone()

    if existing:
        print("  - User already member of team")
        return

    # Add user to team (as team admin for testing convenience)
    cursor.execute(
        """
        INSERT INTO users2teams (users_id, teams_id, is_admin, is_owner)
        VALUES (%s, %s, 1, 1)
        """,
        (user_id, team_id)
    )
    print(f"  ✓ Added user {user_id} to team {team_id}")


def create_api_key(cursor, user_id, team_id):
    """Create API key for test user and return the key string."""
    print("Creating API key...")

    # Check if API key already exists
    cursor.execute(
        "SELECT id FROM api_keys WHERE userid = %s AND name = %s",
        (user_id, TEST_API_KEY_NAME)
    )
    existing = cursor.fetchone()

    if existing:
        api_key_id = existing[0]
        # Reconstruct the key in format {id}-{key}
        test_key = f"{api_key_id}-" + "a" * 84
        print(f"  - API key already exists with ID: {api_key_id}")
        print(f"  - Test API key: {test_key}")
        return test_key

    # Generate API key hash (only hash the key portion, not the ID)
    key_portion = "a" * 84
    key_hash = hash_api_key(key_portion)

    # Insert API key
    cursor.execute(
        """
        INSERT INTO api_keys (name, hash, userid, team, can_write)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (TEST_API_KEY_NAME, key_hash, user_id, team_id)
    )
    api_key_id = cursor.lastrowid

    # Construct full API key in format {id}-{key}
    full_api_key = f"{api_key_id}-{key_portion}"

    print(f"  ✓ Created API key: {TEST_API_KEY_NAME} (ID: {api_key_id})")
    print(f"  ✓ API Key: {full_api_key}")

    return full_api_key


def write_config_file(api_key):
    """Write API key to configuration file for test access."""
    config_file = Path("/tmp/elabftw_test_config.env")
    config_content = f"""# eLabFTW Test Configuration
# Auto-generated by init_elabftw.py
# DO NOT COMMIT THIS FILE

export NX_ELABFTW_URL="https://elabftw.localhost:40080"
export NX_ELABFTW_API_KEY="{api_key}"

# Test user credentials
export ELABFTW_TEST_USER="{TEST_USER['email']}"
export ELABFTW_TEST_PASSWORD="{TEST_USER['password']}"
"""
    config_file.write_text(config_content)
    print(f"  ✓ Wrote config to {config_file}")


def main():
    """Initialize eLabFTW test database."""
    print("=" * 60)
    print("Initializing eLabFTW test database")
    print("=" * 60)

    # Check marker file
    if MARKER_FILE.exists():
        print("Database already initialized (marker file exists)")
        print("To reinitialize, run: docker compose down -v")
        print("=" * 60)
        return

    # Wait for database
    if not wait_for_database():
        print("ERROR: Database not available", file=sys.stderr)
        sys.exit(1)

    try:
        # Connect to database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Create database objects
        team_id = create_team(cursor)
        user_id = create_user(cursor, team_id)
        add_user_to_team(cursor, user_id, team_id)
        api_key = create_api_key(cursor, user_id, team_id)

        # Commit changes
        conn.commit()

        # Write config file
        write_config_file(api_key)

        # Create marker file
        MARKER_FILE.touch()
        print(f"  ✓ Created initialization marker: {MARKER_FILE}")

        print("=" * 60)
        print("Initialization complete!")
        print(f"  - Team: {TEST_TEAM['name']} (ID: {team_id})")
        print(f"  - User: {TEST_USER['email']} (ID: {user_id})")
        print(f"  - Password: {TEST_USER['password']}")
        print(f"  - API Key: {api_key}")
        print("")
        print("To use in tests:")
        print(f"  export NX_ELABFTW_URL='https://elabftw.localhost:40080'")
        print(f"  export NX_ELABFTW_API_KEY='{api_key}'")
        print("=" * 60)

    except Error as e:
        print(f"ERROR: Database operation failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == "__main__":
    main()
```

**Dependencies**: Add to test requirements:

```txt
# tests/requirements-integration.txt
bcrypt>=4.0.0
mysql-connector-python>=8.0.0
```

#### 5.4 Docker Integration

**Update `docker-compose.yml`** to add init script:

```yaml
  # eLabFTW service
  elabftw:
    # ... existing config ...
    volumes:
      - elabftw-uploads:/elabftw/uploads
      - ./elabftw/init_elabftw.py:/docker-entrypoint-initdb.d/init_elabftw.py:ro  # ADD THIS
    command: >
      sh -c "
      python3 /docker-entrypoint-initdb.d/init_elabftw.py &&
      /entrypoint.sh
      "
```

**Update `tests/integration/conftest.py`** to add eLabFTW constants:

```python
# eLabFTW service URL (via Caddy proxy)
ELABFTW_URL = "https://elabftw.localhost:40080"

# API key (set by init script, can be overridden by env var)
ELABFTW_API_KEY = os.getenv("NX_ELABFTW_API_KEY", "1-" + "a" * 84)
```

#### 5.5 Setup Instructions

**File**: `tests/integration/docker/elabftw/README.md`

```markdown
# eLabFTW Integration Test Setup

## Automated Setup

The eLabFTW test database is automatically initialized with seed data on first startup.

### Start Docker Stack

```bash
cd tests/integration/docker
docker compose up -d
```

The init script will automatically:
1. Create a test team: "Test Team"
2. Create a test user: testuser@example.com / testpass123
3. Add user to team
4. Generate API key: `1-aaaa...` (84 'a' characters)
5. Write config to `/tmp/elabftw_test_config.env`

### Verify Initialization

```bash
# Check container logs
docker compose logs elabftw

# You should see:
# "Initialization complete!"
# with test credentials printed

# Source the test config
source /tmp/elabftw_test_config.env
```

### Access eLabFTW

- **URL**: https://elabftw.localhost:40080
- **Username**: testuser@example.com
- **Password**: testpass123
- **API Key**: Available in `/tmp/elabftw_test_config.env`

## Running Integration Tests

```bash
# Load test environment
source /tmp/elabftw_test_config.env

# Run all eLabFTW integration tests
uv run pytest tests/integration/test_elabftw_integration.py -v -m integration

# Run specific test
uv run pytest tests/integration/test_elabftw_integration.py::TestELabFTWClientIntegration::test_create_and_get_experiment -v
```

## Manual Reset

```bash
# Stop and remove volumes (full reset)
docker compose down -v

# Restart (will re-initialize)
docker compose up -d
```

## Troubleshooting

### Init script didn't run

Check if marker file exists:
```bash
docker compose exec elabftw ls -l /tmp/elabftw_init_complete
```

If it exists but setup seems wrong, remove it and restart:
```bash
docker compose exec elabftw rm /tmp/elabftw_init_complete
docker compose restart elabftw
```

### Database connection errors

Wait longer for MySQL to be ready:
```bash
docker compose logs elabftw-mysql
# Look for "ready for connections"
```

### API key not working

Verify the key in the database:
```bash
docker compose exec elabftw-mysql mysql -uelabftw -pnexuslims_elabftw elabftw \
  -e "SELECT id, name, can_write, userid FROM api_keys;"
```
```

#### 5.4 Pytest Configuration

**Update `pyproject.toml`:**

```toml
[tool.pytest.ini_options]
markers = [
    "integration: integration tests requiring Docker services",
    "slow: slow-running tests",
    # ... existing markers ...
]
```

#### 5.5 CI/CD Considerations

For GitHub Actions, add to `.github/workflows/test.yml`:

```yaml
integration-tests:
  runs-on: ubuntu-latest
  steps:
    - name: Start Docker services
      run: |
        cd tests/integration/docker
        docker compose -f docker-compose.ci.yml up -d

    - name: Wait for services
      run: |
        timeout 300 bash -c 'until docker compose ps | grep -q "healthy"; do sleep 5; done'

    - name: Run integration tests
      run: |
        uv run pytest tests/integration/test_elabftw_integration.py -v -m integration
```

### 6. Documentation

**User guide** (`docs/user_guide/configuration.md`):
- Add eLabFTW configuration section
- Explain required/optional settings
- Describe how records are exported (one experiment per session)

**Integration test guide** (`tests/integration/docker/elabftw/README.md`):
- Document eLabFTW Docker setup
- Explain API key generation process
- Provide test execution commands

**Changelog** (`docs/changes/`):
- Create towncrier fragment: `feature.elabftw-export.md`
- Describe new export destination

**API reference**: Auto-generated from docstrings (NumPy style)

## Data Mapping: Session → Experiment

**Strategy**: One NexusLIMS session = One eLabFTW experiment

**Rationale**:
- Simple 1:1 mapping (easy to understand)
- Preserves all data via XML attachment
- Human-readable markdown summary
- Machine-readable metadata field
- Cross-linked to CDCS for full web view

**Example experiment structure**:
- **Title**: `NexusLIMS - FEI-Titan-TEM - 2025-01-27_10-30-15_abc123`
- **Body**: Markdown with session details, CDCS link, file list
- **Tags**: `["NexusLIMS", "FEI-Titan-TEM", "jsmith"]`
- **Metadata**: `{"nexuslims_session_id": "...", "instrument": "...", "cdcs_url": "..."}`
- **Attachment**: XML record file

## Implementation Sequence

1. **Configuration** (30 min)
   - Add settings to `config.py`
   - Update `.env.example`
   - Add pytest markers to `pyproject.toml`

2. **API Client** (3-4 hours)
   - Create `nexusLIMS/utils/elabftw.py`
   - Implement CRUD methods
   - Add custom exceptions
   - Implement helper functions

3. **Export Plugin** (2-3 hours)
   - Create `nexusLIMS/exporters/destinations/elabftw.py`
   - Implement export workflow
   - Add markdown body generation
   - Add CDCS cross-linking

4. **Unit Tests** (4-6 hours)
   - Create `tests/unit/test_exporters/test_elabftw.py`
   - Write API client tests (all CRUD operations)
   - Write destination configuration tests
   - Write export workflow tests
   - Achieve 100% coverage

5. **Docker Stack** (2-3 hours)
   - Add eLabFTW + MySQL services to `docker-compose.yml` and `docker-compose.ci.yml`
   - Update Caddyfile with eLabFTW proxy
   - Add volumes configuration
   - Create `init_elabftw.py` database initialization script
   - Add bcrypt, mysql-connector-python to test requirements
   - Test stack startup and automated initialization
   - Verify test user creation and API key generation

6. **Integration Tests** (3-4 hours)
   - Create `tests/integration/test_elabftw_integration.py`
   - Write API client integration tests
   - Write export destination integration tests
   - Write end-to-end workflow tests
   - Create eLabFTW setup documentation

7. **Documentation** (1-2 hours)
   - Update user guide with eLabFTW configuration
   - Create integration test setup guide
   - Add changelog fragment
   - Update API reference

8. **Validation** (1-2 hours)
   - Run all unit tests (verify 100% coverage)
   - Run integration tests against Docker stack
   - Manual end-to-end workflow testing
   - Verify CDCS cross-linking
   - Check database logging

**Total estimate**: 17-26 hours

## Verification Steps

### Unit Test Verification

```bash
# Run all eLabFTW unit tests
uv run pytest tests/unit/test_exporters/test_elabftw.py -v

# Check coverage (should be 100%)
uv run pytest tests/unit/test_exporters/test_elabftw.py \
  --cov=nexusLIMS.utils.elabftw \
  --cov=nexusLIMS.exporters.destinations.elabftw \
  --cov-report=term-missing \
  --cov-report=html

# Verify all test classes pass
uv run pytest tests/unit/test_exporters/test_elabftw.py::TestELabFTWClient -v
uv run pytest tests/unit/test_exporters/test_elabftw.py::TestELabFTWDestinationConfiguration -v
uv run pytest tests/unit/test_exporters/test_elabftw.py::TestELabFTWDestinationExport -v
```

**Checklist**:
- [ ] All 50+ unit tests pass
- [ ] Code coverage 100%
- [ ] No test warnings or errors
- [ ] Mock patterns follow existing conventions

### Docker Stack Verification

```bash
# Start Docker services
cd tests/integration/docker
docker compose up -d

# Wait for initialization to complete (watch logs)
docker compose logs -f elabftw

# Look for: "Initialization complete!"

# Verify all services healthy
docker compose ps

# Check eLabFTW accessibility
curl -k https://elabftw.localhost:40080/login.php

# Verify test configuration file created
cat /tmp/elabftw_test_config.env

# Load test environment
source /tmp/elabftw_test_config.env

# Verify API key works
curl -k -H "Authorization: $NX_ELABFTW_API_KEY" \
  https://elabftw.localhost:40080/api/v2/experiments

# View logs if issues
docker compose logs elabftw
docker compose logs elabftw-mysql
```

**Checklist**:
- [ ] MySQL container starts and passes health check
- [ ] eLabFTW container starts and passes health check
- [ ] Init script runs successfully (check logs for "Initialization complete!")
- [ ] Test user created: testuser@example.com
- [ ] API key generated and written to `/tmp/elabftw_test_config.env`
- [ ] Can log in via web interface with test credentials
- [ ] API key works for API requests
- [ ] Marker file created at `/tmp/elabftw_init_complete`
- [ ] All services on `nexuslims-test` network
- [ ] eLabFTW accessible via Caddy proxy at https://elabftw.localhost:40080

### Integration Test Verification

```bash
# Set environment variables (using your generated API key)
export NX_ELABFTW_URL="https://elabftw.localhost:40080"
export NX_ELABFTW_API_KEY="your-generated-api-key"

# Run integration tests
uv run pytest tests/integration/test_elabftw_integration.py -v -m integration

# Run specific test classes
uv run pytest tests/integration/test_elabftw_integration.py::TestELabFTWClientIntegration -v
uv run pytest tests/integration/test_elabftw_integration.py::TestELabFTWDestinationIntegration -v
uv run pytest tests/integration/test_elabftw_integration.py::TestELabFTWEndToEnd -v
```

**Checklist**:
- [ ] API client creates experiments successfully
- [ ] Experiments retrievable by ID
- [ ] List/update/delete operations work
- [ ] File uploads succeed
- [ ] Tags and metadata preserved
- [ ] Export destination creates experiments
- [ ] XML files attached to experiments
- [ ] CDCS cross-linking works
- [ ] Database logging to `upload_log` works
- [ ] Multi-destination export succeeds

### Manual End-to-End Verification

1. **Configuration validation**:
   - [ ] Plugin enabled when API key and URL configured
   - [ ] Plugin disabled when credentials missing
   - [ ] `validate_config()` tests API authentication

2. **Export workflow**:
   - [ ] Export creates experiment in eLabFTW
   - [ ] Experiment has correct title format
   - [ ] Markdown body contains session metadata
   - [ ] XML file successfully attached
   - [ ] Tags applied correctly
   - [ ] Metadata JSON structured properly

3. **CDCS integration**:
   - [ ] CDCS link appears in body when available
   - [ ] Export succeeds even when CDCS unavailable
   - [ ] Priority ordering correct (CDCS runs first)

4. **Error handling**:
   - [ ] No exceptions raised from `export()`
   - [ ] Failed exports return `ExportResult(success=False)`
   - [ ] Errors logged with full traceback
   - [ ] Database records export attempts in `upload_log`

5. **Record builder integration**:
   - [ ] Sessions marked `COMPLETED` when exported
   - [ ] Sessions marked `BUILT_NOT_EXPORTED` when all exports fail
   - [ ] Multiple export destinations work together

6. **eLabFTW web interface**:
   - [ ] Can view created experiment in eLabFTW UI
   - [ ] Experiment shows correct title and body
   - [ ] XML attachment downloadable
   - [ ] Tags visible and correct
   - [ ] CDCS link clickable and working

## Docker Stack Files

### Files to create/modify:

1. **`tests/integration/docker/docker-compose.yml`** - Add eLabFTW + MySQL services
2. **`tests/integration/docker/docker-compose.ci.yml`** - Add eLabFTW + MySQL services for CI
3. **`tests/integration/docker/caddy/Caddyfile`** - Add eLabFTW reverse proxy config
4. **`tests/integration/docker/elabftw/init_elabftw.py`** - Database initialization script (NEW)
5. **`tests/integration/docker/elabftw/README.md`** - Setup instructions (NEW)
6. **`tests/integration/conftest.py`** - Add eLabFTW URL/API key constants
7. **`tests/requirements-integration.txt`** - Add bcrypt, mysql-connector-python

### New Docker volumes:
- `elabftw-mysql-data` - MySQL database persistence
- `elabftw-uploads` - eLabFTW file uploads

### Network configuration:
- Add `elabftw.localhost` to Caddy proxy `extra_hosts`
- Add `elabftw` to Caddy proxy `depends_on`
- Ensure all services on `nexuslims-test` bridge network

## Critical Files

### Reference implementations:
- `nexusLIMS/exporters/destinations/cdcs.py` - Complete export destination (gold standard)
- `nexusLIMS/exporters/destinations/labarchives.py` - Skeleton with TODOs (good template)
- `nexusLIMS/utils/cdcs.py` - API client utilities pattern

### Framework:
- `nexusLIMS/exporters/base.py` - Protocol definitions (ExportDestination, ExportContext, ExportResult)
- `nexusLIMS/exporters/registry.py` - Plugin discovery and registration
- `nexusLIMS/utils/network.py` - nexus_req() for HTTP calls

### Configuration:
- `nexusLIMS/config.py` - Centralized settings (MUST add eLabFTW settings here)
- `.env.example` - Environment variable template

### Database:
- `nexusLIMS/db/models.py` - UploadLog table for tracking exports
- `nexusLIMS/db/enums.py` - RecordStatus enum

### Testing:
- `tests/unit/test_exporters/test_cdcs.py` - Reference unit test patterns
- `tests/unit/test_exporters/test_labarchives.py` - Skeleton test coverage
- `tests/integration/test_export_framework_integration.py` - Export framework integration test patterns
- `tests/integration/test_cdcs_integration.py` - CDCS integration test reference
- `tests/integration/conftest.py` - Integration test fixtures and Docker service management
- `tests/integration/docker/docker-compose.yml` - Local development Docker stack
- `tests/integration/docker/docker-compose.ci.yml` - CI/CD Docker stack

### Integration:
- `nexusLIMS/builder/record_builder.py` - How exports are triggered

## Future Enhancements (Out of Scope)

- Items API support (catalog/materials database)
- Batch export operations
- Advanced querying (tags, status filters)
- Experiment templates/categories management
- Multi-file uploads beyond XML
- Experiment linking (related experiments)
