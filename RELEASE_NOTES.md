## Welcome to version 2.8.0 of NexusLIMS!

### Highlights
This release adds a new diagnostic support bundle command to help collect redacted configuration, environment, database, path health, preflight, log, extractor, and exporter details for Datasophos support. It also improves CDCS preflight error reporting and tightens export status handling so failed or partial exports are reported more accurately.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### New Features
**Support bundle diagnostics command** ([#129](https://github.com/datasophos/NexusLIMS/issues/129))
  - Added a `nexuslims support-bundle` command that creates a local diagnostic archive for Datasophos support.
  - The archive includes a styled HTML summary, redacted effective configuration, path health, preflight results, database summaries, selected logs, package and environment details, and extractor/exporter diagnostics.

### Bug Fixes
- Improved CDCS preflight error reporting so transient workspace API failures report the HTTP status and endpoint instead of a misleading JSON parsing configuration error. ([#123](https://github.com/datasophos/NexusLIMS/issues/123))
- Aligned export destination preflight and final session status handling with `NX_EXPORT_STRATEGY` so unavailable destinations now stop builds when the configured strategy cannot succeed, and partial exports under the default `all` strategy are no longer marked completed. ([#124](https://github.com/datasophos/NexusLIMS/issues/124))

### Internal / Miscellaneous
- Updated contributor guidance to require including `uv.lock` changes whenever dependencies or project metadata are updated.

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.8.0

# or
pip install nexuslims==2.8.0

# or, if installed from source:
git fetch
git checkout v2.8.0
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.7.4...v2.8.0
