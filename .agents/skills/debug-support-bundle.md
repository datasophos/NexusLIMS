# NexusLIMS Support Bundle Debugging Workflow

Use this workflow when a user provides a `nexuslims support-bundle` archive, an
unpacked support-bundle directory, or asks for help diagnosing NexusLIMS from
support-bundle artifacts.

## Safety

- Treat bundle contents as potentially sensitive even though NexusLIMS redacts
  secrets on a best-effort basis.
- Do not paste full logs, full config files, or large XML/CSV contents back to
  the user. Quote only the minimum lines needed to explain a finding.
- Do not run code from inside a bundle. Inspect it as data.
- Prefer reading files directly from an unpacked copy. If given a zip, unpack it
  to `/private/tmp` or another scratch directory outside the repo.

## First Pass

1. Locate the bundle root. It should contain `manifest.json`, `summary.html`,
   and `errors.json`.
2. Read `manifest.json` first. Use it as the artifact index and to confirm the
   command options used to create the bundle.
3. Read `errors.json` next. If it is non-empty, explain which diagnostic
   sections are missing before drawing conclusions from absent artifacts.
4. Read `summary.html` as a triage overview, not as the source of truth. Follow
   links or matching artifact paths for exact data.

Useful commands:

```bash
unzip -l /path/to/nexuslims-support-bundle-*.zip
unzip /path/to/nexuslims-support-bundle-*.zip -d /private/tmp/nexuslims-support-bundle
uv run python -m json.tool /private/tmp/nexuslims-support-bundle/manifest.json
uv run python -m json.tool /private/tmp/nexuslims-support-bundle/errors.json
```

## Artifact Reading Order

For configuration and path problems:

1. `config.redacted.json`
2. `paths.json`
3. `preflight.json`
4. `environment.json`

For record-building problems:

1. `preflight.json`
2. `recent_sessions.json`
3. `database/session_log_summary.json`
4. `database/session_log.csv`
5. `logs/*`

For upload/export problems:

1. `exporters.json`
2. `database/upload_log.csv`
3. `config.redacted.json`
4. `logs/*`

For extractor/file metadata problems:

1. `extractors.json`
2. `paths.json`
3. `recent_sessions.json`
4. `logs/*`

## Interpretation Notes

- `config.redacted.json` intentionally masks secret values. A missing or
  redacted credential means "configured value unknown," not necessarily "unset."
- `paths.json` reports effective paths. Optional `NX_LOG_PATH` and
  `NX_RECORDS_PATH` may show `source: default` and `defaulted_from:
  NX_DATA_PATH`; that is valid when the effective parent path is writable.
- `errors.json` describes failures while creating the bundle, not necessarily
  NexusLIMS application failures.
- `database/*.csv` files are exports and summaries, not a live database. Avoid
  assuming cross-table consistency beyond the captured rows.
- `log_summary.json` gives counts only. Read the referenced `logs/*` artifacts
  for timing, stack traces, and exact messages.
- `recent_sessions.json` is biased toward problematic statuses first. It is for
  triage, not a chronological full session history.

## Reporting Back

Lead with the most likely root cause and the evidence paths used, for example:

```text
The likely issue is an unwritable records directory. Evidence:
paths.json shows NX_RECORDS_PATH resolved to ... with writable=false, and
preflight.json reports the records path check failed.
```

When evidence is incomplete, say which bundle section is missing and ask for a
new bundle only if the missing artifact blocks diagnosis.
