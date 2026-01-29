# Writing Export Destination Plugins

```{versionadded} 2.4.0
```

This guide explains how to create custom export destination plugins for the NexusLIMS multi-destination export framework.

## Overview

Export destinations are plugins that receive built NexusLIMS XML records and export them to external repository systems (CDCS, LabArchives, eLabFTW, etc.). The framework uses protocol-based typing for automatic plugin discovery—no inheritance or registration required.

## Quick Start

1. Create a Python file in `nexusLIMS/exporters/destinations/`
2. Define a class matching the `ExportDestination` protocol
3. The plugin will be auto-discovered when the exporters package is imported

## Protocol Requirements

Your export destination class must implement the `ExportDestination` protocol:

```python
from nexusLIMS.exporters.base import ExportContext, ExportResult

class MyDestination:
    """My custom export destination."""

    # Required class attributes
    name = "my_destination"  # Unique identifier
    priority = 80  # Export priority (0-1000, higher runs first)

    @property
    def enabled(self) -> bool:
        """Return True if this destination is configured and ready."""
        # Check if required configuration is present
        ...

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate configuration at startup.

        Returns
        -------
        tuple[bool, str | None]
            (is_valid, error_message)
            - is_valid: True if configuration is valid
            - error_message: None if valid, descriptive error if invalid
        """
        ...

    def export(self, context: ExportContext) -> ExportResult:
        """Export record to this destination.

        CRITICAL: Must never raise exceptions. All errors must be caught
        and returned as ExportResult with success=False.

        Parameters
        ----------
        context : ExportContext
            Contains xml_file_path, session_identifier, instrument_pid,
            dt_from, dt_to, user, and previous_results from other destinations

        Returns
        -------
        ExportResult
            Result of the export attempt (success or failure)
        """
        ...
```

### Required Attributes

- **`name`** (str): Unique identifier for this destination (lowercase, alphanumeric + underscores)
- **`priority`** (int): Export priority (0-1000). Higher priority destinations run first. Use this to manage inter-destination dependencies.

### Required Methods

#### `enabled` property

Returns `bool` indicating whether the destination is configured and ready to use. Typically checks for required environment variables (API keys, URLs, etc.).

```python
@property
def enabled(self) -> bool:
    from nexusLIMS import config
    return (
        hasattr(config, 'MY_API_KEY') and
        config.MY_API_KEY is not None
    )
```

#### `validate_config()` method

Performs startup-time configuration validation. Called during initialization to provide detailed error feedback. Should test authentication, connectivity, etc.

Returns `(is_valid, error_message)` tuple.

```python
def validate_config(self) -> tuple[bool, str | None]:
    from nexusLIMS import config

    if not hasattr(config, 'MY_API_KEY'):
        return False, "MY_API_KEY not configured"

    if not config.MY_API_KEY:
        return False, "MY_API_KEY is empty"

    # Test authentication
    try:
        self._test_connection()
    except Exception as e:
        return False, f"Connection test failed: {e}"

    return True, None
```

#### `export()` method

Performs the actual export. **Must never raise exceptions**—all errors must be caught and returned as `ExportResult` with `success=False` and `error_message` set.

```python
def export(self, context: ExportContext) -> ExportResult:
    try:
        # Read XML content
        with context.xml_file_path.open(encoding="utf-8") as f:
            xml_content = f.read()

        # Upload to destination
        record_id, record_url = self._upload(xml_content, context.session_identifier)

        return ExportResult(
            success=True,
            destination_name=self.name,
            record_id=record_id,
            record_url=record_url,
        )

    except Exception as e:
        _logger.exception(f"Failed to export to {self.name}: {context.xml_file_path.name}")
        return ExportResult(
            success=False,
            destination_name=self.name,
            error_message=str(e),
        )
```

## Configuration Patterns

### Reading Configuration

Always use the `nexusLIMS.config` module, never `os.getenv()` directly:

```python
from nexusLIMS import config

# Good
api_key = config.MY_API_KEY

# Bad - do not use
import os
api_key = os.getenv("MY_API_KEY")
```

### Adding New Configuration Variables

Add new environment variables to `nexusLIMS/config.py`:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    MY_DESTINATION_API_KEY: str | None = Field(
        None,
        description="API key for MyDestination service",
    )

    MY_DESTINATION_URL: AnyHttpUrl | None = Field(
        None,
        description="Base URL for MyDestination API",
    )
```

Document the new variables in `.env.example`:

```bash
# MyDestination Configuration
MY_DESTINATION_API_KEY=your_api_key_here
MY_DESTINATION_URL=https://api.mydestination.com
```

### Optional vs Required Configuration

Use `Field(None, ...)` for optional configuration (destination won't be enabled if missing). Use `Field(..., ...)` for required configuration (will cause validation error if missing—only use this if the variable is needed for NexusLIMS core functionality).

## Error Handling

### Never Raise Exceptions from `export()`

The `export()` method is called in a loop across all destinations. If it raises an exception, it will break the entire export process. **Always catch exceptions and return ExportResult**.

```python
def export(self, context: ExportContext) -> ExportResult:
    try:
        # Do export work
        ...
        return ExportResult(success=True, ...)
    except SpecificError as e:
        # Log specific errors at appropriate level
        _logger.warning(f"Specific error: {e}")
        return ExportResult(success=False, error_message=str(e), ...)
    except Exception as e:
        # Catch-all for unexpected errors
        _logger.exception(f"Unexpected error in {self.name}")
        return ExportResult(success=False, error_message=str(e), ...)
```

### Logging Best Practices

- Use `_logger.info()` for successful exports
- Use `_logger.warning()` for expected errors (e.g., network timeout, invalid credentials)
- Use `_logger.exception()` for unexpected errors (includes traceback)
- Include context in log messages (file name, session identifier, etc.)

```python
import logging

_logger = logging.getLogger(__name__)

def export(self, context: ExportContext) -> ExportResult:
    try:
        # ... export logic ...
        _logger.info(
            f"Successfully exported {context.xml_file_path.name} to {self.name}: {record_url}"
        )
        return ExportResult(success=True, ...)
    except Exception as e:
        _logger.exception(
            f"Failed to export {context.xml_file_path.name} to {self.name}"
        )
        return ExportResult(success=False, error_message=str(e), ...)
```

## Inter-Destination Dependencies

Destinations may depend on results from other destinations (e.g., LabArchives including a CDCS link). Handle this using priority ordering and `context.previous_results`.

### How It Works

1. **Priority ordering**: Destinations run in priority order (highest first)
2. **Result accumulation**: Each destination's result is added to `context.previous_results` before the next destination runs
3. **Access previous results**: Lower-priority destinations can access results from higher-priority destinations

### Priority Management

If destination A needs data from destination B, give B a **higher priority**:

- CDCS: priority 100 (runs FIRST)
- LabArchives: priority 90 (runs SECOND, can see CDCS result)
- eLabFTW: priority 85 (runs THIRD, can see both CDCS and LabArchives)
- LocalArchive: priority 80 (runs LAST, can see all others)

### Accessing Previous Results

Use `context.get_result(destination_name)` or `context.has_successful_export(destination_name)`:

```python
class LabArchivesDestination:
    name = "labarchives"
    priority = 90  # Lower than CDCS (100), so runs AFTER CDCS

    def export(self, context: ExportContext) -> ExportResult:
        try:
            # Build base content
            content = self._build_entry(context)

            # Check if CDCS export succeeded and include link
            if context.has_successful_export("cdcs"):
                cdcs_result = context.get_result("cdcs")
                content += f"<p>CDCS Record: <a href='{cdcs_result.record_url}'>{cdcs_result.record_id}</a></p>"
                _logger.info(f"Including CDCS link in LabArchives: {cdcs_result.record_url}")
            else:
                _logger.info("CDCS export did not succeed, skipping link in LabArchives")

            # Upload to LabArchives
            notebook_id = self._upload(content)

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=notebook_id,
                metadata={"included_cdcs_link": context.has_successful_export("cdcs")},
            )
        except Exception as e:
            ...
```

### Graceful Degradation

Dependencies should be **optional**. If the dependency failed, gracefully degrade rather than failing:

```python
if context.has_successful_export("cdcs"):
    # Include enhanced content with CDCS link
    content += cdcs_link_section
else:
    # Still complete export, just without CDCS link
    _logger.info("CDCS not available, proceeding without link")
```

### Available Result Fields

The `ExportResult` object includes:

- `record_id`: Destination-specific record identifier (str)
- `record_url`: Direct URL to view the record (str)
- `metadata`: Custom metadata dict with destination-specific details (dict)
- `success`: Whether the export succeeded (bool)
- `timestamp`: When the export occurred (datetime)
- `error_message`: Error message if failed (str | None)

### Best Practices

1. **Document dependencies**: Add a docstring comment noting priority requirements
2. **Optional dependencies**: Always handle the case where the dependency failed
3. **Log decisions**: Log when including/excluding dependent content
4. **Use metadata**: Track what was included in the `metadata` field for debugging

```python
class LabArchivesDestination:
    """LabArchives ELN export destination.

    Priority: 90 (must run after CDCS at priority 100 to include CDCS links)

    Dependencies:
    - CDCS (optional): Includes CDCS record link if available
    """

    name = "labarchives"
    priority = 90
    ...
```

## Testing Strategies

### Unit Tests

Test your destination in isolation using mocks:

```python
# tests/unit/test_exporters/test_my_destination.py

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from nexusLIMS.exporters.destinations.my_destination import MyDestination
from nexusLIMS.exporters.base import ExportContext

@pytest.fixture
def mock_config():
    with patch("nexusLIMS.exporters.destinations.my_destination.config") as mock_cfg:
        mock_cfg.MY_API_KEY = "test_key"
        mock_cfg.MY_API_URL = "http://localhost:8000"
        yield mock_cfg

def test_enabled_with_config(mock_config):
    dest = MyDestination()
    assert dest.enabled is True

def test_enabled_without_config():
    with patch("nexusLIMS.exporters.destinations.my_destination.config") as mock_cfg:
        mock_cfg.MY_API_KEY = None
        dest = MyDestination()
        assert dest.enabled is False

def test_export_success(mock_config, tmp_path):
    # Create test XML file
    xml_file = tmp_path / "test_record.xml"
    xml_file.write_text("<record>test</record>")

    # Create export context
    context = ExportContext(
        xml_file_path=xml_file,
        session_identifier="test-session-123",
        instrument_pid="test-instrument",
        dt_from=datetime.now(),
        dt_to=datetime.now(),
    )

    # Mock API calls
    with patch("nexusLIMS.exporters.destinations.my_destination.nexus_req") as mock_req:
        mock_req.return_value.status_code = 201
        mock_req.return_value.json.return_value = {"id": "record-123"}

        dest = MyDestination()
        result = dest.export(context)

        assert result.success is True
        assert result.record_id == "record-123"
        assert result.error_message is None

def test_export_failure(mock_config, tmp_path):
    xml_file = tmp_path / "test_record.xml"
    xml_file.write_text("<record>test</record>")

    context = ExportContext(
        xml_file_path=xml_file,
        session_identifier="test-session-123",
        instrument_pid="test-instrument",
        dt_from=datetime.now(),
        dt_to=datetime.now(),
    )

    # Mock API failure
    with patch("nexusLIMS.exporters.destinations.my_destination.nexus_req") as mock_req:
        mock_req.side_effect = Exception("Connection failed")

        dest = MyDestination()
        result = dest.export(context)

        assert result.success is False
        assert "Connection failed" in result.error_message
```

### Integration Tests

Test with a real or mock destination server:

```python
# tests/integration/test_my_destination_integration.py

import pytest
from nexusLIMS.exporters import export_records
from nexusLIMS.exporters.destinations.my_destination import MyDestination

@pytest.mark.integration
def test_full_export_workflow(db_session, sample_session, sample_xml_file):
    """Test complete export workflow with MyDestination."""
    # Ensure destination is enabled
    dest = MyDestination()
    assert dest.enabled is True

    # Export record
    results = export_records([sample_xml_file], [sample_session])

    # Verify results
    assert sample_xml_file in results
    my_dest_results = [r for r in results[sample_xml_file] if r.destination_name == "my_destination"]
    assert len(my_dest_results) == 1
    assert my_dest_results[0].success is True

    # Verify upload_log entry
    from nexusLIMS.db.models import UploadLog
    logs = db_session.query(UploadLog).filter_by(
        session_identifier=sample_session.session_identifier,
        destination_name="my_destination"
    ).all()
    assert len(logs) == 1
    assert logs[0].success is True
```

### Test Dependencies

Test inter-destination dependencies:

```python
def test_dependency_on_cdcs(tmp_path):
    """Test that LabArchives correctly handles CDCS dependency."""
    xml_file = tmp_path / "test.xml"
    xml_file.write_text("<record>test</record>")

    context = ExportContext(
        xml_file_path=xml_file,
        session_identifier="test-123",
        instrument_pid="test-instrument",
        dt_from=datetime.now(),
        dt_to=datetime.now(),
    )

    # Simulate CDCS result
    from nexusLIMS.exporters.base import ExportResult
    cdcs_result = ExportResult(
        success=True,
        destination_name="cdcs",
        record_id="cdcs-456",
        record_url="http://cdcs.example.com/data?id=cdcs-456",
    )
    context.previous_results["cdcs"] = cdcs_result

    # Export to LabArchives
    dest = LabArchivesDestination()
    result = dest.export(context)

    assert result.success is True
    assert result.metadata["included_cdcs_link"] is True
```

## Example Implementation

Here's a complete example implementing a simple local file archive destination:

```python
# nexusLIMS/exporters/destinations/local_archive.py

"""Local file archive export destination."""

import logging
import shutil
from pathlib import Path

from nexusLIMS import config
from nexusLIMS.exporters.base import ExportContext, ExportResult

_logger = logging.getLogger(__name__)


class LocalArchiveDestination:
    """Local filesystem archive export destination.

    Copies exported records to a local directory for archival purposes.
    Priority: 50 (runs after primary destinations like CDCS)
    """

    name = "local_archive"
    priority = 50

    @property
    def enabled(self) -> bool:
        """Check if local archive directory is configured."""
        return (
            hasattr(config, "NX_LOCAL_ARCHIVE_PATH") and
            config.NX_LOCAL_ARCHIVE_PATH is not None
        )

    def validate_config(self) -> tuple[bool, str | None]:
        """Validate that archive directory exists and is writable."""
        if not hasattr(config, "NX_LOCAL_ARCHIVE_PATH"):
            return False, "NX_LOCAL_ARCHIVE_PATH not configured"

        archive_path = Path(config.NX_LOCAL_ARCHIVE_PATH)

        if not archive_path.exists():
            return False, f"Archive directory does not exist: {archive_path}"

        if not archive_path.is_dir():
            return False, f"Archive path is not a directory: {archive_path}"

        # Test write permissions
        test_file = archive_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            return False, f"Archive directory is not writable: {e}"

        return True, None

    def export(self, context: ExportContext) -> ExportResult:
        """Copy XML file to archive directory.

        File will be named: YYYY-MM-DD_INSTRUMENT_SESSION.xml
        """
        try:
            # Build archive filename
            archive_dir = Path(config.NX_LOCAL_ARCHIVE_PATH)
            archive_filename = (
                f"{context.dt_from.strftime('%Y-%m-%d')}_"
                f"{context.instrument_pid}_"
                f"{context.session_identifier.split('-')[0]}.xml"
            )
            archive_path = archive_dir / archive_filename

            # Copy file to archive
            shutil.copy2(context.xml_file_path, archive_path)

            _logger.info(
                f"Archived {context.xml_file_path.name} to {archive_path}"
            )

            return ExportResult(
                success=True,
                destination_name=self.name,
                record_id=archive_filename,
                record_url=f"file://{archive_path.absolute()}",
                metadata={"archive_path": str(archive_path)},
            )

        except Exception as e:
            _logger.exception(
                f"Failed to archive {context.xml_file_path.name} to local filesystem"
            )
            return ExportResult(
                success=False,
                destination_name=self.name,
                error_message=str(e),
            )
```

## Summary Checklist

When creating a new export destination, ensure you:

- [ ] Create a class matching the `ExportDestination` protocol
- [ ] Set `name` and `priority` class attributes
- [ ] Implement `enabled` property to check configuration
- [ ] Implement `validate_config()` for startup validation
- [ ] Implement `export()` that never raises exceptions
- [ ] Use `nexusLIMS.config` for all configuration access
- [ ] Add new config variables to `nexusLIMS/config.py`
- [ ] Document new config variables in `.env.example`
- [ ] Handle errors gracefully with appropriate logging
- [ ] Consider inter-destination dependencies (use priority)
- [ ] Write unit tests for your destination
- [ ] Test integration with the full export workflow
- [ ] Document any special requirements or dependencies

For more examples, see the CDCS destination implementation at {py:mod}`nexusLIMS.exporters.destinations.cdcs`.
