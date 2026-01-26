# Issue 35: Multi-Destination Export Framework Implementation Plan

## Overview

Build an extensible framework for exporting NexusLIMS records to multiple repository destinations (CDCS, LabArchives ELN, eLabFTW ELN). The framework uses a plugin-based architecture with protocol typing, following existing NexusLIMS patterns (extractors, harvesters).

**Package name:** `nexusLIMS.exporters`

**Key decisions:**
- Per-destination tracking via new `upload_log` database table
- Default strategy: `all` (succeed if any destination succeeds)
- Breaking change: Refactor `cdcs.py` immediately into new framework (no wrapper)
- **Inter-destination dependencies**: Destinations can access results from higher-priority destinations

## Architecture Summary

### Plugin System
- **Protocol-based** (like extractors): structural typing, no inheritance required
- **Auto-discovery**: Walk `exporters/destinations/` directory and register plugins
- **Priority-based selection**: 0-1000 scale, higher priority tried first
- **Registry singleton**: `ExporterRegistry` manages all destination plugins
- **Dependency support**: Destinations can access results from previously-run destinations via `ExportContext.previous_results`

### Core Components

```
nexusLIMS/
├── exporters/                       # NEW PACKAGE
│   ├── __init__.py                  # Public API: export_records()
│   ├── base.py                      # Protocols: ExportDestination, ExportContext, ExportResult
│   ├── registry.py                  # ExporterRegistry with auto-discovery
│   ├── strategies.py                # Strategy implementations (all, first_success, best_effort)
│   └── destinations/                # Plugin directory
│       ├── __init__.py              # Auto-discovery trigger
│       ├── cdcs.py                  # Migrated from cdcs.py
│       └── (future: labarchives_destination.py, elabftw_destination.py)
├── cdcs.py                          # DELETE (refactor into cdcs.py)
├── builder/record_builder.py        # MODIFY: Use export_records()
├── config.py                        # EXTEND: Add export configuration
└── db/
    ├── models.py                    # EXTEND: Add UploadLog model
    ├── enums.py                     # EXTEND: Add BUILT_NOT_EXPORTED status
    └── migrations/                  # NEW: Alembic migration for upload_log table
```

## Implementation Steps

### 1. Database Schema Extension

**File:** `nexusLIMS/db/models.py`

Add new `UploadLog` model for per-destination tracking:

```python
class UploadLog(SQLModel, table=True):
    __tablename__ = "upload_log"

    id: int | None = Field(default=None, primary_key=True)
    session_identifier: str = Field(foreign_key="session_log.session_identifier", index=True)
    destination_name: str = Field(index=True)
    success: bool
    record_id: str | None = None
    record_url: str | None = None
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata_json: str | None = None  # JSON-serialized metadata dict
```

**File:** `nexusLIMS/db/enums.py`

Add new status to `RecordStatus` enum:

```python
class RecordStatus(str, Enum):
    # ... existing statuses ...
    COMPLETED = "COMPLETED"              # Built and exported successfully
    BUILT_NOT_EXPORTED = "BUILT_NOT_EXPORTED"  # NEW: Built but all exports failed
```

**Create Alembic migration:**
- Run: `uv run alembic revision -m "Add upload_log table and BUILT_NOT_EXPORTED status"`
- Add upgrade/downgrade logic for new table and enum value

### 2. Core Framework Components

**File:** `nexusLIMS/exporters/base.py`

Define protocols and data structures:

```python
from pathlib import Path
from typing import Protocol, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ExportContext:
    """Context passed to export destination plugins."""
    xml_file_path: Path
    session_identifier: str
    instrument_pid: str
    dt_from: datetime
    dt_to: datetime
    user: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Inter-destination dependency support
    previous_results: dict[str, ExportResult] = field(default_factory=dict)

    def get_result(self, destination_name: str) -> ExportResult | None:
        """Get result from a specific destination, if it has already run."""
        return self.previous_results.get(destination_name)

    def has_successful_export(self, destination_name: str) -> bool:
        """Check if a destination successfully exported."""
        result = self.get_result(destination_name)
        return result is not None and result.success
```

**Inter-Destination Dependency Support:**

The `ExportContext` includes `previous_results` to enable destinations to reference
results from earlier exports. Destinations run sequentially in priority order
(highest first), so a destination can access results from any higher-priority
destination that has already completed.

**Example use case:** LabArchives export (priority 90) includes a link to the CDCS
record (priority 100) by reading `context.get_result("cdcs")`.

```python
@dataclass
class ExportResult:
    """Result of a single export attempt."""
    success: bool
    destination_name: str
    record_id: str | None = None
    record_url: str | None = None
    error_message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

class ExportDestination(Protocol):
    """Protocol for export destination plugins."""
    name: str
    priority: int

    @property
    def enabled(self) -> bool:
        """Whether this destination is enabled and configured."""
        ...

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate configuration. Returns (is_valid, error_message)."""
        ...

    def export(self, context: ExportContext) -> ExportResult:
        """Export record. MUST NOT raise exceptions."""
        ...
```

**File:** `nexusLIMS/exporters/registry.py`

Implement plugin registry with auto-discovery:

```python
from typing import Literal
import pkgutil
import inspect
from pathlib import Path

ExportStrategy = Literal["all", "first_success", "best_effort"]

class ExporterRegistry:
    """Singleton registry for export destination plugins."""

    def __init__(self):
        self._destinations: dict[str, ExportDestination] = {}
        self._discovered = False

    def discover_plugins(self) -> None:
        """Auto-discover plugins from exporters/destinations/."""
        if self._discovered:
            return

        # Walk destinations directory
        destinations_path = Path(__file__).parent / "destinations"
        for module_info in pkgutil.walk_packages([str(destinations_path)]):
            module = module_info.module_finder.find_module(module_info.name).load_module()

            # Find classes matching ExportDestination protocol
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._matches_protocol(obj):
                    instance = obj()
                    self._destinations[instance.name] = instance

        self._discovered = True

    def get_enabled_destinations(self) -> list[ExportDestination]:
        """Get enabled destinations sorted by priority (descending)."""
        self.discover_plugins()
        enabled = [d for d in self._destinations.values() if d.enabled]
        return sorted(enabled, key=lambda d: d.priority, reverse=True)

    def export_to_all(
        self,
        context: ExportContext,
        *,
        strategy: ExportStrategy = "all"
    ) -> list[ExportResult]:
        """Export to destinations according to strategy."""
        from nexusLIMS.exporters.strategies import execute_strategy
        return execute_strategy(strategy, self.get_enabled_destinations(), context)

# Singleton instance
_registry: ExporterRegistry | None = None

def get_registry() -> ExporterRegistry:
    global _registry
    if _registry is None:
        _registry = ExporterRegistry()
    return _registry
```

**File:** `nexusLIMS/exporters/strategies.py`

Implement export strategies:

```python
def execute_strategy(
    strategy: ExportStrategy,
    destinations: list[ExportDestination],
    context: ExportContext
) -> list[ExportResult]:
    """Execute export strategy."""

    if strategy == "all":
        return _strategy_all(destinations, context)
    elif strategy == "first_success":
        return _strategy_first_success(destinations, context)
    elif strategy == "best_effort":
        return _strategy_best_effort(destinations, context)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

def _strategy_all(destinations, context):
    """All destinations must succeed."""
    results = []
    for dest in destinations:
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.previous_results[dest.name] = result

        if not result.success:
            _logger.warning(f"Export to {dest.name} failed (all strategy)")
    return results

def _strategy_first_success(destinations, context):
    """Stop after first success."""
    results = []
    for dest in destinations:
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.previous_results[dest.name] = result

        if result.success:
            _logger.info(f"Export succeeded to {dest.name}, stopping (first_success strategy)")
            break
    return results

def _strategy_best_effort(destinations, context):
    """Try all, succeed if any succeed."""
    results = []
    for dest in destinations:
        result = dest.export(context)
        results.append(result)

        # Add result to context for subsequent destinations
        context.previous_results[dest.name] = result

        if result.success:
            _logger.info(f"Export succeeded to {dest.name}")
    return results
```

**File:** `nexusLIMS/exporters/__init__.py`

Public API and upload_log integration:

```python
from pathlib import Path
from nexusLIMS.db.session_handler import Session
from nexusLIMS.db.models import UploadLog
from nexusLIMS.exporters.registry import get_registry
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.config import settings
from sqlmodel import select
import json

def export_records(
    xml_files: list[Path],
    sessions: list[Session],
) -> dict[Path, list[ExportResult]]:
    """
    Main entry point for exporting records.
    Called by record_builder.py after validation.
    """
    registry = get_registry()
    strategy = settings.NX_EXPORT_STRATEGY

    results = {}
    for xml_file, session in zip(xml_files, sessions):
        context = ExportContext(
            xml_file_path=xml_file,
            session_identifier=session.session_identifier,
            instrument_pid=session.instrument.name,
            dt_from=session.dt_from,
            dt_to=session.dt_to,
            user=session.user,
        )

        export_results = registry.export_to_all(context, strategy=strategy)
        results[xml_file] = export_results

        # Write to upload_log table
        _log_to_database(session.session_identifier, export_results)

        # Log summary
        success_count = sum(1 for r in export_results if r.success)
        _logger.info(
            f"Exported {xml_file.name}: {success_count}/{len(export_results)} destinations succeeded"
        )

    return results

def _log_to_database(session_identifier: str, results: list[ExportResult]) -> None:
    """Write export results to upload_log table."""
    from nexusLIMS.db.session_handler import get_db_engine
    from sqlmodel import Session as DBSession

    with DBSession(get_db_engine()) as db:
        for result in results:
            log_entry = UploadLog(
                session_identifier=session_identifier,
                destination_name=result.destination_name,
                success=result.success,
                record_id=result.record_id,
                record_url=result.record_url,
                error_message=result.error_message,
                timestamp=result.timestamp,
                metadata_json=json.dumps(result.metadata) if result.metadata else None,
            )
            db.add(log_entry)
        db.commit()

def was_successfully_exported(xml_file: Path, results: dict[Path, list[ExportResult]]) -> bool:
    """Check if file was successfully exported to at least one destination."""
    if xml_file not in results:
        return False
    return any(r.success for r in results[xml_file])
```

### 3. CDCS Destination Plugin

**File:** `nexusLIMS/exporters/destinations/cdcs.py`

Migrate logic from `cdcs.py` into plugin:

```python
from nexusLIMS.exporters.base import ExportContext, ExportResult, ExportDestination
from nexusLIMS.config import settings
from nexusLIMS.utils import nexus_req, AuthenticationError
from urllib.parse import urljoin
from http import HTTPStatus
import logging

_logger = logging.getLogger(__name__)

class CDCSDestination:
    """CDCS export destination plugin."""

    name = "cdcs"
    priority = 100

    @property
    def enabled(self) -> bool:
        """Check if CDCS is configured and enabled."""
        return (
            hasattr(settings, 'NX_CDCS_TOKEN') and
            hasattr(settings, 'NX_CDCS_URL') and
            settings.NX_CDCS_TOKEN is not None and
            settings.NX_CDCS_URL is not None
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate CDCS configuration."""
        if not hasattr(settings, 'NX_CDCS_TOKEN'):
            return False, "NX_CDCS_TOKEN not configured"
        if not settings.NX_CDCS_TOKEN:
            return False, "NX_CDCS_TOKEN is empty"
        if not hasattr(settings, 'NX_CDCS_URL'):
            return False, "NX_CDCS_URL not configured"

        # Test authentication
        try:
            self._get_workspace_id()
        except AuthenticationError as e:
            return False, f"CDCS authentication failed: {e}"
        except Exception as e:
            return False, f"CDCS configuration error: {e}"

        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to CDCS. Never raises exceptions."""
        try:
            # Read XML content
            with context.xml_file_path.open(encoding="utf-8") as f:
                xml_content = f.read()

            # Upload to CDCS
            title = context.xml_file_path.stem
            record_id, record_url = self._upload_to_cdcs(xml_content, title)

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=str(record_id),
                record_url=record_url,
            )

        except Exception as e:
            _logger.exception(f"Failed to export to CDCS: {context.xml_file_path.name}")
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )

    def _upload_to_cdcs(self, xml_content: str, title: str) -> tuple[int, str]:
        """Upload XML to CDCS and return (record_id, record_url)."""
        endpoint = urljoin(str(settings.NX_CDCS_URL), "rest/data/")

        payload = {
            "template": self._get_template_id(),
            "title": title,
            "xml_content": xml_content,
        }

        post_r = nexus_req(
            endpoint, "POST", json=payload, token_auth=settings.NX_CDCS_TOKEN
        )

        if post_r.status_code != HTTPStatus.CREATED:
            raise RuntimeError(f"CDCS upload failed: {post_r.text}")

        record_id = post_r.json()["id"]

        # Assign to workspace
        wrk_endpoint = urljoin(
            str(settings.NX_CDCS_URL),
            f"rest/data/{record_id}/assign/{self._get_workspace_id()}",
        )
        _ = nexus_req(wrk_endpoint, "PATCH", token_auth=settings.NX_CDCS_TOKEN)

        record_url = urljoin(str(settings.NX_CDCS_URL), f"data?id={record_id}")
        _logger.info(f'Record "{title}" available at {record_url}')

        return record_id, record_url

    def _get_template_id(self) -> str:
        """Get current template ID from CDCS."""
        endpoint = urljoin(str(settings.NX_CDCS_URL), "rest/template-version-manager/global")
        r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)

        if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise AuthenticationError("Could not authenticate to CDCS")

        return r.json()[0]["current"]

    def _get_workspace_id(self) -> int:
        """Get workspace ID from CDCS."""
        endpoint = urljoin(str(settings.NX_CDCS_URL), "rest/workspace/read_access")
        r = nexus_req(endpoint, "GET", token_auth=settings.NX_CDCS_TOKEN)

        if r.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise AuthenticationError("Could not authenticate to CDCS")

        return r.json()[0]["id"]
```

**File:** `nexusLIMS/exporters/destinations/__init__.py`

Trigger auto-discovery:

```python
# This file triggers plugin discovery when the destinations package is imported
```

### 3a. Example: LabArchives Destination with CDCS Dependency

**File:** `nexusLIMS/exporters/destinations/labarchives_destination.py`

Example destination that references CDCS export results:

```python
from nexusLIMS.exporters.base import ExportContext, ExportResult
from nexusLIMS.config import settings
import logging

_logger = logging.getLogger(__name__)

class LabArchivesDestination:
    """LabArchives ELN export destination plugin."""

    name = "labarchives"
    priority = 90  # Lower than CDCS (100), so runs AFTER CDCS

    @property
    def enabled(self) -> bool:
        return (
            hasattr(settings, 'NX_LABARCHIVES_API_KEY') and
            settings.NX_LABARCHIVES_API_KEY is not None
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate LabArchives configuration."""
        if not hasattr(settings, 'NX_LABARCHIVES_API_KEY'):
            return False, "NX_LABARCHIVES_API_KEY not configured"
        if not settings.NX_LABARCHIVES_API_KEY:
            return False, "NX_LABARCHIVES_API_KEY is empty"
        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Export to LabArchives, including CDCS link if available."""
        try:
            # Read XML
            with context.xml_file_path.open(encoding="utf-8") as f:
                xml_content = f.read()

            # Build notebook entry content
            entry_html = self._build_entry_html(
                xml_content,
                context.session_identifier,
                context.instrument_pid,
            )

            # Check if CDCS export succeeded and include link
            if context.has_successful_export("cdcs"):
                cdcs_result = context.get_result("cdcs")
                entry_html += self._add_cdcs_link_section(cdcs_result)
                _logger.info(f"Including CDCS link in LabArchives: {cdcs_result.record_url}")
            else:
                _logger.info("CDCS export did not succeed, skipping link in LabArchives")

            # Upload to LabArchives API
            notebook_id = self._upload_to_labarchives(entry_html)

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=notebook_id,
                record_url=f"https://labarchives.com/notebook/{notebook_id}",
                metadata={"included_cdcs_link": context.has_successful_export("cdcs")},
            )

        except Exception as e:
            _logger.exception(f"Failed to export to LabArchives: {context.xml_file_path.name}")
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )

    def _add_cdcs_link_section(self, cdcs_result: ExportResult) -> str:
        """Generate HTML section with CDCS record link."""
        return f"""
        <div class="cdcs-reference">
            <h3>NexusLIMS Record</h3>
            <p>View the full structured record in the CDCS database:</p>
            <p><a href="{cdcs_result.record_url}">CDCS Record {cdcs_result.record_id}</a></p>
        </div>
        """

    def _build_entry_html(self, xml_content: str, session_id: str, instrument: str) -> str:
        """Build HTML content for notebook entry."""
        # Implementation here - convert XML to human-readable HTML
        return f"<h2>Session {session_id} on {instrument}</h2>..."

    def _upload_to_labarchives(self, html_content: str) -> str:
        """Upload to LabArchives and return notebook entry ID."""
        # Implementation here - call LabArchives API
        return "LA12345"
```

**Priority-Based Dependency Management:**

Destinations run in priority order (highest first):
- CDCS: priority 100 → Runs FIRST
- LabArchives: priority 90 → Runs SECOND, can see CDCS result
- eLabFTW: priority 85 → Runs THIRD, can see both CDCS and LabArchives
- LocalArchive: priority 80 → Runs LAST, can see all others

**Key principle:** If destination A needs data from destination B, give B a higher priority.

### 4. Configuration Extension

**File:** `nexusLIMS/config.py`

Add export configuration:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    NX_EXPORT_STRATEGY: Literal["all", "first_success", "best_effort"] = Field(
        "best_effort",
        description="Strategy for exporting records to multiple destinations",
    )

    # CDCS configuration (existing, keep as-is)
    NX_CDCS_URL: TestAwareHttpUrl | None = None
    NX_CDCS_TOKEN: str | None = None

    # LabArchives configuration (example - for future implementation)
    NX_LABARCHIVES_API_KEY: str | None = Field(
        None,
        description="API key for LabArchives ELN",
    )
    NX_LABARCHIVES_API_URL: AnyHttpUrl | None = Field(
        None,
        description="Base URL for LabArchives API",
    )
    NX_LABARCHIVES_NOTEBOOK_ID: str | None = Field(
        None,
        description="Default notebook ID for LabArchives exports",
    )

    # Future: Add eLabFTW configs here
    # NX_ELABFTW_API_KEY: str | None = None
    # NX_ELABFTW_URL: AnyHttpUrl | None = None
```

### 5. Record Builder Integration

**File:** `nexusLIMS/builder/record_builder.py`

**Changes required:**

1. **Import new exporter module** (top of file):
```python
from nexusLIMS.exporters import export_records, was_successfully_exported
```

2. **Remove old CDCS import** (line 28):
```python
# DELETE: from nexusLIMS.cdcs import upload_record_files
```

3. **Update `process_new_records()` function** (around line 593-605):

Replace:
```python
files_uploaded, _ = upload_record_files(xml_files)
```

With:
```python
# Build mapping of xml_files to their corresponding sessions
# (Need to track which session produced which XML file)
sessions_by_file = {xml_file: session for xml_file, session in zip(xml_files, built_sessions)}

# Export records to all configured destinations
export_results = export_records(xml_files, list(sessions_by_file.values()))

# Determine which files were successfully exported to at least one destination
files_exported = [
    f for f in xml_files
    if was_successfully_exported(f, export_results)
]
```

4. **Track sessions in `build_new_session_records()`** (around line 423-513):

Modify to return sessions along with XML files:
```python
def build_new_session_records() -> tuple[list[Path], list[Session]]:
    """Build records for all TO_BE_BUILT sessions.

    Returns
    -------
    xml_files : list[Path]
        Successfully built and validated XML files
    sessions : list[Session]
        Corresponding Session objects
    """
    xml_files = []
    sessions_built = []

    # ... existing logic ...

    # When successful:
    xml_files.append(xml_path)
    sessions_built.append(s)  # Track the session

    return xml_files, sessions_built
```

5. **Update session status logic** (around line 538):

Move `COMPLETED` status update to AFTER export succeeds:
```python
# In process_new_records(), after export_records() call:
for xml_file, session in sessions_by_file.items():
    results = export_results[xml_file]
    if any(r.success for r in results):
        session.update_session_status(RecordStatus.COMPLETED)
    else:
        session.update_session_status(RecordStatus.BUILT_NOT_EXPORTED)
        _logger.error(f"All exports failed for {xml_file.name}")
```

### 6. Delete Old CDCS Module

**File:** `nexusLIMS/cdcs.py`

DELETE this file entirely - all functionality migrated to `exporters/destinations/cdcs.py`.

Create a `CDCSUtils` class in the new file that contains CDCS helper methods not directly related to exporting:
- `search_records()` - Used for querying existing records
- `download_record()` - Used for retrieving record content
- `delete_record()` - Used for cleanup operations
- Helper type `CDCSDataRecord`

## Critical Files to Modify

1. **`nexusLIMS/builder/record_builder.py`** - Main integration point, replace upload call
2. **`nexusLIMS/cdcs.py`** - Remove upload functions (keep search/download/delete)
3. **`nexusLIMS/config.py`** - Add NX_EXPORT_STRATEGY setting
4. **`nexusLIMS/db/models.py`** - Add UploadLog model
5. **`nexusLIMS/db/enums.py`** - Add BUILT_NOT_EXPORTED status

## New Files to Create

1. `nexusLIMS/exporters/__init__.py` - Public API
2. `nexusLIMS/exporters/base.py` - Protocols and data structures (includes dependency support)
3. `nexusLIMS/exporters/registry.py` - Plugin registry
4. `nexusLIMS/exporters/strategies.py` - Export strategies (with result accumulation)
5. `nexusLIMS/exporters/destinations/__init__.py` - Trigger discovery
6. `nexusLIMS/exporters/destinations/cdcs.py` - CDCS plugin
7. `nexusLIMS/db/migrations/<timestamp>_add_upload_log.py` - Alembic migration
8. *(Optional)* `nexusLIMS/exporters/destinations/labarchives_destination.py` - Example with dependencies

## Verification Plan

### Unit Tests

Create `tests/unit/test_exporters/`:

1. **`test_registry.py`**
   - Test plugin discovery
   - Test enabled destination filtering
   - Test priority sorting

2. **`test_strategies.py`**
   - Test "all" strategy (all must succeed)
   - Test "first_success" strategy (stop after first)
   - Test "best_effort" strategy (try all)
   - **Test inter-destination dependencies (previous_results propagation)**

3. **`test_cdcs.py`**
   - Test CDCS export with mocked API
   - Test configuration validation
   - Test error handling (authentication failures, network errors)

4. **`test_export_context.py`**
   - Test context creation
   - Test result aggregation
   - **Test `get_result()` and `has_successful_export()` helper methods**
   - **Test dependency scenario: second destination accessing first destination's result**

### Integration Tests

Update `tests/integration/`:

1. **`test_record_builder_with_exporters.py`**
   - Test full record building + export workflow
   - Test with mock CDCS destination
   - Test upload_log table is populated
   - Test session status transitions (TO_BE_BUILT → COMPLETED)
   - Test session status on failure (TO_BE_BUILT → BUILT_NOT_EXPORTED)
   - **Test multi-destination export with dependencies (mock CDCS + mock LabArchives)**
   - **Verify second destination receives first destination's result in context**

### Manual Verification

1. **Run record builder with CDCS configured:**
   ```bash
   # Set up test environment
   export NX_CDCS_URL="https://cdcs-test.example.com"
   export NX_CDCS_TOKEN="test_token"
   export NX_EXPORT_STRATEGY="all"

   # Run record builder
   nexuslims-process-records -vv
   ```

2. **Verify database:**
   ```python
   from nexusLIMS.db.session_handler import get_db_engine
   from nexusLIMS.db.models import UploadLog
   from sqlmodel import Session, select

   with Session(get_db_engine()) as db:
       logs = db.exec(select(UploadLog)).all()
       for log in logs:
           print(f"{log.session_identifier} → {log.destination_name}: {log.success}")
   ```

3. **Check CDCS:**
   - Verify records appear in CDCS web interface
   - Verify record URLs in upload_log are accessible
   - Verify record_ids match CDCS database

4. **Test error scenarios:**
   - Invalid CDCS token → should mark BUILT_NOT_EXPORTED
   - CDCS server down → should mark BUILT_NOT_EXPORTED
   - Check upload_log contains error_message

### End-to-End Test

1. Configure test NEMO instance with usage events
2. Run `nexuslims-process-records`
3. Verify:
   - Sessions transition TO_BE_BUILT → COMPLETED
   - XML files generated in records directory
   - Records uploaded to CDCS
   - upload_log table populated
   - Records moved to records/uploaded/ directory
   - Session status reflects export success/failure

## Documentation Updates

Create `docs/writing_export_destinations.md`:
- Protocol requirements
- Configuration patterns
- Error handling guidelines
- Testing strategies
- Example implementation
- **Inter-destination dependencies** (new section)

**Add section on inter-destination dependencies:**

````markdown
## Inter-Destination Dependencies

Destinations may depend on results from other destinations (e.g., LabArchives
including a CDCS link). Handle this using:

1. **Priority ordering**: Give dependencies higher priority
   - CDCS: priority 100 (runs first)
   - LabArchives: priority 90 (runs second, can read CDCS result)

2. **Access previous results** via `context.previous_results`:
   ```python
   def export(self, context: ExportContext) -> ExportResult:
       if context.has_successful_export("cdcs"):
           cdcs_result = context.get_result("cdcs")
           record_url = cdcs_result.record_url
           # Include URL in your export
   ```

3. **Graceful degradation**: Check if dependency succeeded
   ```python
   if context.has_successful_export("cdcs"):
       # Include link
   else:
       # Skip link section, still complete export
   ```

4. **Available result fields**:
   - `record_id`: Destination-specific record identifier
   - `record_url`: Direct URL to view the record
   - `metadata`: Custom metadata dict from the destination
   - `success`: Whether the export succeeded

5. **Best practices**:
   - Dependencies should be optional (graceful degradation)
   - Log when dependency is missing or failed
   - Use `metadata` field to track what was included
   - Document priority requirements in destination docstring
````

Update `CLAUDE.md`:
- Document new exporters package
- Update architecture overview
- Add configuration examples
- **Add inter-destination dependency patterns**

## Changelog Entry

Create `docs/changes/35.feature.md`:
```
Implement extensible multi-destination export framework for NexusLIMS records. Records can now be exported to multiple repository systems (CDCS, LabArchives, eLabFTW) using a plugin-based architecture with protocol typing, auto-discovery, and configurable export strategies.
```

## Migration Notes

**Breaking Changes:**
- `nexusLIMS.cdcs.upload_record_files()` removed - use `nexusLIMS.exporters.export_records()`
- `nexusLIMS.cdcs.upload_record_content()` removed - implement `ExportDestination` plugin instead
- `RecordStatus.COMPLETED` semantics changed: now means "built AND exported" (previously just "built")

**Database Migration:**
- New `upload_log` table tracks per-destination export attempts
- New `BUILT_NOT_EXPORTED` status for failed exports
- Run `uv run alembic upgrade head` after updating

**Configuration:**
- Add `NX_EXPORT_STRATEGY=all` to `.env` (or use default)
- Existing CDCS configuration (`NX_CDCS_URL`, `NX_CDCS_TOKEN`) still works

## Future Enhancements

1. **LabArchives plugin** - Implement `LabArchivesDestination` in `exporters/destinations/`
2. **eLabFTW plugin** - Implement `eLabFTWDestination` in `exporters/destinations/`
3. **Retry logic** - Add automatic retry for transient failures
4. **Parallel exports** - Use `ThreadPoolExecutor` for concurrent uploads (careful with dependencies!)
5. **Export queue** - Add async task queue for background exports
6. **Web UI** - Dashboard to view export status across destinations
7. **Explicit dependency declaration** - Add optional `depends_on: list[str]` attribute to validate dependencies at startup
8. **Dependency graph validation** - Detect circular dependencies and priority mismatches
