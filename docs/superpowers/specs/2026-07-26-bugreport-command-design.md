# NexusLIMS Support Bundle Command Design

## Purpose

Add a `nexuslims support-bundle` command that creates a single local diagnostic
archive a site administrator can send to Datasophos support when a NexusLIMS
deployment is misbehaving. The command does not submit the archive or create a
public bug report.

The command should answer the first round of support questions without requiring
full observability infrastructure: what version is installed, how it is
configured, whether configured services are reachable, what the database says
about recent sessions, which logs show failures, and which local paths appear
healthy.

## Command

The command is a top-level lazy-loaded CLI command:

```bash
nexuslims support-bundle
nexuslims support-bundle --output report.zip
nexuslims support-bundle --log-days 14
nexuslims support-bundle --max-log-files 25
nexuslims support-bundle --log /path/to/specific.log
nexuslims support-bundle --no-default-logs
nexuslims support-bundle --include-all-logs
```

Default output is `nexuslims-support-bundle-YYYYMMDD-HHMMSS.zip` in the current
directory. `--output` points to the zip file path to create.

## Archive Layout

The archive contains predictable, stable filenames:

```text
manifest.json
summary.html
environment.json
packages.txt
config.redacted.json
paths.json
preflight.json
preflight.txt
extractors.json
exporters.json
errors.json
database/
  schema.json
  session_log.csv
  session_log_summary.json
  instruments.csv
  upload_log.csv
  external_user_identifiers.csv
logs/
  selected recent logs
log_summary.json
recent_sessions.json
```

`upload_log.csv` and `external_user_identifiers.csv` are included when the
corresponding tables exist. Missing optional tables should be recorded in
`database/schema.json` or `errors.json` without failing the command.

## Collected Data

`manifest.json` is the stable machine-readable entry point for the archive. It
records the report schema version, generated timestamp, command options,
NexusLIMS version, and one artifact entry for every file included in the archive.
Each artifact entry should include the artifact path, media type, artifact schema
version when applicable, record count when applicable, collection status, and
any collector error summary.

`summary.html` is a self-contained static HTML entry point for human review. It
links to the archive artifacts and highlights failed preflight checks, unhealthy
paths, problematic recent sessions, database row-count summaries, and log warning
or error counts.

`environment.json` records OS/platform details, Python version, executable path,
NexusLIMS import path, current working directory, timezone, locale, and whether
the package appears to be running from a source checkout or installed package.

`packages.txt` records installed package versions using the standard library
where possible. The implementation should prefer `importlib.metadata` over
shelling out to package-manager-specific commands so it works in pip, uv, and
source-checkout environments.

`config.redacted.json` contains the effective NexusLIMS configuration using the
existing `nexusLIMS.cli.config._build_config_dict()` and
`nexusLIMS.cli.config._sanitize_config()` helpers.

`paths.json` reports each configured NexusLIMS path, the resolved absolute path,
whether it exists, whether it is a file or directory, readability, writability
where relevant, and filesystem free space when available. It must not recursively
list raw data directories.

`preflight.json` contains structured results from
`nexusLIMS.builder.preflight.run_preflight_checks(dry_run=False)`.
`preflight.txt` is a human-readable rendering of the same results.

`database/session_log.csv` contains a copy of the full `session_log` table.
Usernames are preserved. Session identifiers, instruments, timestamps, event
types, and record statuses are preserved because they are central to support
debugging.

`database/session_log_summary.json` contains counts by `record_status`,
`event_type`, and instrument, plus basic timestamp ranges.

`database/instruments.csv` contains instrument configuration rows from the
database. It should not contain API tokens because tokens live in the NexusLIMS
configuration, not the instrument table.

`database/schema.json` contains the SQLite database path, file size, table
names, Alembic revision when available, and row counts for key tables.

The v1 archive should not include a bundled SQLite database copy. A
`bundle.sqlite` artifact could be useful later for cross-table SQL analysis, but
it duplicates exported data and adds schema-versioning and privacy concerns.

`recent_sessions.json` contains a compact list of recent or problematic sessions,
especially `ERROR`, `NO_FILES_FOUND`, `NO_RESERVATION`, and `NO_CONSENT`, grouped
or sortable by status and instrument.

`extractors.json` records discovered extractor plugins, supported extensions,
priorities, and local profile search paths. This helps diagnose file discovery
and extractor-selection problems.

`exporters.json` records configured exporter destinations, enabled or disabled
state, export strategy, validation results where available, and relevant upload
counts if they can be gathered locally.

`logs/` contains selected log files. By default the command copies recent logs
from `settings.log_dir_path`, limited by `--log-days` and `--max-log-files`.
Administrators can add explicit files with repeated `--log` options. The
`--no-default-logs` option disables automatic log discovery, and
`--include-all-logs` removes the default recent-log limit.

`log_summary.json` reports counts of warnings, errors, tracebacks, and common
failure signatures across included logs.

`errors.json` records collector failures. A failed collector should not prevent
other collectors from running or the archive from being created.

## Redaction and Privacy

The command must never include the raw `.env` file, generated XML records, raw
microscope data, certificate bundle contents, or arbitrary recursive directory
listings by default.

Configuration secrets are redacted through the existing config sanitizer. Log
content copied into the archive should pass through a best-effort line-oriented
redactor that masks obvious credentials, including tokens, passwords,
authorization headers, API keys, and configured secret values available from the
sanitized configuration process.

Usernames in `session_log` are intentionally preserved by default because they
are useful when correlating NexusLIMS state with scheduler records during client
support.

## Failure Behavior

The command should be resilient. Each collector runs independently and records
exceptions in `errors.json`. The command exits successfully if it creates the
archive, even when some diagnostic sections could not be collected. It exits
nonzero only when the archive cannot be written.

The terminal output should be short and actionable: print the archive path,
summarize any collector failures, state that the archive was created locally and
was not sent anywhere, instruct the administrator to review it and email it to
`support@datasophos.co`, and remind them that secrets are redacted on a
best-effort basis.

## Implementation Notes

Create `nexusLIMS/cli/support_bundle.py` and lazy-load it as the
`support-bundle` command from
`nexusLIMS/cli/main.py`.

Keep the first implementation as simple collector functions rather than a
general plugin framework. Each collector should write one or more files into a
temporary report directory. After collection, create the zip archive from that
directory. This keeps v1 small while leaving a future path to a collector
registry if site-specific diagnostics become necessary.

Use standard library modules for archive creation, CSV writing, JSON writing,
platform information, package metadata, filesystem inspection, and temporary
directories.

## Testing

Add focused unit tests for:

- CLI registration and help output.
- Archive creation with the expected filenames.
- Sanitized config output.
- `session_log` and instrument CSV export.
- Optional table handling when `upload_log` or `external_user_identifiers` is
  absent.
- Log auto-discovery and explicit `--log` inclusion.
- Collector failure handling via `errors.json`.
- Preflight result serialization with mocked `run_preflight_checks()`.

Add documentation for the command in the CLI reference and include a Towncrier
feature fragment during implementation.
