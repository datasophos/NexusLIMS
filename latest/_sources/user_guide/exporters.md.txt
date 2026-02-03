---
tocdepth: 2
---

(exporters)=
# Export Destinations

NexusLIMS uses a plugin-based export framework to publish experimental records to multiple repository systems. After building XML records from microscopy data, the system can export them to one or more configured destinations.

## Overview

The export framework supports:

- **Multiple destinations** running in parallel or sequence
- **Configurable strategies** for handling export failures
- **Inter-destination dependencies** (e.g., cross-linking between systems)
- **Per-destination tracking** in the database
- **Automatic retry** for transient failures

Records are exported immediately after successful building, with results logged to the {py:class}`~nexusLIMS.db.models.UploadLog` table for tracking and debugging.

## Available Export Destinations

### CDCS (Primary)

```{versionadded} 1.0.0
```

The **Configurable Data Curation System (CDCS)** is the primary and default export destination for NexusLIMS. CDCS provides:

- Web-based record viewing and search
- Schema validation and versioning
- Access control and permissions
- RESTful API for programmatic access
- Public/private workspace management

**Configuration:** See {ref}`CDCS Integration <config-cdcs-url>` for required settings:

- `NX_CDCS_URL` - CDCS instance URL
- `NX_CDCS_TOKEN` - API authentication token

CDCS exports have **priority 100** (highest) and run first to ensure records are available for cross-linking by other destinations.

**What gets exported:**
- Complete XML record
- XML file uploaded to CDCS document storage
- Record indexed and searchable via CDCS interface
- Unique record ID assigned for cross-referencing

**Frontend repository:** [NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS/)

(elabftw-exporter)=
### eLabFTW

```{versionadded} 2.4.0
```

[**eLabFTW**](https://www.elabftw.net/) is an open-source electronic lab notebook system. NexusLIMS supports creating eLabFTW experiment records that correspond to individual microscopy sessions with:

- HTML-formatted session summary
- Structured metadata using eLabFTW's `extra_fields` schema
- Automatic tagging (instrument, user, NexusLIMS)
- Full XML record attached as file
- Cross-link to CDCS record (if CDCS export enabled)

**Configuration:** See {ref}`eLabFTW Integration <config-elabftw>` for settings:
- `NX_ELABFTW_URL` - eLabFTW instance URL
- `NX_ELABFTW_API_KEY` - API authentication key
- `NX_ELABFTW_EXPERIMENT_CATEGORY` - Optional category assignment
- `NX_ELABFTW_EXPERIMENT_STATUS` - Optional status assignment

eLabFTW exports have **priority 85** and run after CDCS to enable cross-linking.

**What gets exported:**
- **Experiment title:** "NexusLIMS Experiment - {session_id}"
- **Body:** HTML with session details and CDCS link
- **Tags:** NexusLIMS, instrument name, username
- **Metadata:** Structured extra_fields (session times, instrument, user, CDCS URL)
- **Attachment:** Complete XML record file

**Example experiment view:**

```html
<h1>NexusLIMS Microscopy Session</h1>

<h2>Session Details</h2>
<ul>
  <li><strong>Session ID</strong>: 2025-01-27_10-30-15_abc123</li>
  <li><strong>Instrument</strong>: FEI-Titan-TEM-012345</li>
  <li><strong>User</strong>: jsmith</li>
  <li><strong>Start</strong>: 2025-01-27T10:30:15+00:00</li>
  <li><strong>End</strong>: 2025-01-27T14:45:00+00:00</li>
</ul>

<h2>Related Records</h2>
<ul>
  <li><a href="https://cdcs.example.com/data/123">View in CDCS</a></li>
</ul>
```

## Export Workflow

The export process runs automatically as part of {py:func}`~nexusLIMS.builder.record_builder.process_new_records` workflow:

1. **Build record:** The experimental record is generated from session data and validated against the {ref}`NexusLIMS experiment schema <schema_documentation>`
2. **Export to destinations:** {py:func}`~nexusLIMS.exporters.export_records` determines which exporters should be run, depending on system configuration
3. **Execute by priority:** Individual destination export routines are run in priority order (highest first)
4. **Track results:** Export outcomes are logged to the {py:class}`~nexusLIMS.db.models.UploadLog` table
5. **Update session status:**
   - `COMPLETED` if exports succeed
   - `BUILT_NOT_EXPORTED` if exporting fails
6. **Archive successfully exported files:** Move to `uploaded/` directory

### Export Strategies

Multi-destination behavior can be configured with the `NX_EXPORT_STRATEGY` setting, depending on your deployment's needs:

| Strategy | Behavior |
|----------|----------|
| **`all`** (default) | Export to all enabled destinations. Fails if any destination fails. |
| **`first_success`** | Stop after first successful export. Remaining destinations skipped. |
| **`best_effort`** | Attempt all destinations. Succeeds if at least one succeeds. |

**Example configuration:**
```bash
NX_EXPORT_STRATEGY=best_effort  # Continue even if some destinations fail
```

## Inter-Destination Dependencies

Export destinations can access results from higher-priority destinations to create cross-links:

```python
# In eLabFTW export destination
def export(self, context: ExportContext) -> ExportResult:
    # Get CDCS result (priority 100, runs first)
    cdcs_result = context.get_result("cdcs")
    
    if cdcs_result and cdcs_result.success:
        # Include CDCS URL in eLabFTW metadata
        cdcs_url = cdcs_result.record_url
        # Add to experiment body and metadata...
```

This enables:
- **Cross-linking:** eLabFTW experiments link to CDCS records
- **Cascading updates:** Downstream destinations use upstream IDs
- **Conditional behavior:** Skip exports if upstream dependencies fail

See {ref}`Inter-Destination Dependencies <inter-destination-dependencies>` in the developer guide for implementation details.

## Monitoring Exports

### Database Tracking

All export attempts are logged to the `upload_log` table:

```sql
SELECT destination_name, success, timestamp, error_message
FROM upload_log
WHERE session_identifier = 'your-session-id'
ORDER BY timestamp DESC;
```

**Schema:** {py:class}`~nexusLIMS.db.models.UploadLog`

### Session Status

Session records track overall export status in `session_log.record_status`:

| Status | Meaning |
|--------|---------|
| `TO_BE_BUILT` | Session needs record generation |
| `COMPLETED` | Record built and exported successfully |
| `BUILT_NOT_EXPORTED` | Record built but all exports failed |
| `ERROR` | Record building failed |
| `NO_FILES_FOUND` | No files found for session |

Check session status:
```sql
SELECT instrument, record_status, timestamp
FROM session_log
WHERE session_identifier = 'your-session-id';
```

### Export Logs

Detailed export logs are written to `NX_LOG_PATH` (or `NX_DATA_PATH/logs/`):
- `nexuslims_record_builder.log` - Main processing log with export results
- Individual destination errors logged with context

## Troubleshooting

### Export Failures

**Common issues:**

| Problem | Solution |
|---------|----------|
| **CDCS authentication failed** | Verify `NX_CDCS_TOKEN` is valid and user has write permissions |
| **eLabFTW API errors** | Check `NX_ELABFTW_API_KEY` and network connectivity |
| **All exports failed** | Check logs in `NX_LOG_PATH` for detailed error messages |
| **Session marked `BUILT_NOT_EXPORTED`** | Review `upload_log` table for per-destination failures |

**Debug export issues:**

1. Check configuration:
   ```python
   from nexusLIMS.config import settings
   print(f"CDCS URL: {settings.NX_CDCS_URL}")
   print(f"eLabFTW URL: {settings.NX_ELABFTW_URL}")
   ```

2. Query upload logs:
   ```sql
   SELECT * FROM upload_log 
   WHERE success = 0 
   ORDER BY timestamp DESC 
   LIMIT 10;
   ```

3. Review main log file for detailed errors

### Validation

Test export destination configuration:
```python
from nexusLIMS.exporters.registry import get_enabled_destinations

for dest in get_enabled_destinations():
    is_valid, error = dest.validate_config()
    print(f"{dest.name}: {'✓' if is_valid else '✗'} {error or ''}")
```

## Developing Custom Destinations

NexusLIMS's plugin architecture makes it easy to add new export destinations. No core modifications needed—just drop a Python file in `nexusLIMS/exporters/destinations/`.

**Common use cases:**
- Export to institutional repositories (Zenodo, Figshare, Dataverse)
- Push to cloud storage (S3, Azure, Google Cloud)
- Integrate with other LIMS systems
- Custom archival workflows

See {doc}`../dev_guide/writing_export_destinations` for:
- Complete implementation guide
- Protocol requirements and testing strategies
- Example implementations
- Inter-destination dependency patterns

**Quick start:** Copy an existing destination (e.g., `elabftw.py`) and customize for your target system.

## API Reference

Key modules for export functionality:

- {py:mod}`nexusLIMS.exporters` - Main export framework
- {py:mod}`nexusLIMS.exporters.base` - Base classes and protocols
- {py:mod}`nexusLIMS.exporters.registry` - Plugin discovery and management
- {py:mod}`nexusLIMS.exporters.destinations.cdcs` - CDCS export implementation
- {py:mod}`nexusLIMS.exporters.destinations.elabftw` - eLabFTW export implementation
- {py:mod}`nexusLIMS.db.models` - Database models (UploadLog, SessionLog)

## Summary

The export framework provides:

- Multiple repository support (CDCS, eLabFTW, custom destinations)
- Automatic export after record building
- Configurable failure handling strategies
- Inter-destination cross-linking
- Complete tracking and logging
- Plugin-based extensibility

Export destinations are configured via environment variables and automatically activated when credentials are provided. No additional setup required beyond configuration.
