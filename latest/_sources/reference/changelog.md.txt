---
tocdepth: 2
---

# Changelog

```{note}
This changelog documents development history including the original NIST project
up to version 1.4.3. The datasophos fork begins at version 2.0.
```

```{towncrier-draft-entries} [Unreleased]
```

<!-- towncrier release notes start -->

## 2.4.0 (2026-02-02)

### New features

- Added plugin-based export framework supporting multiple repository destinations (currently only CDCS and eLabFTW support, but other exporters planned in the future). Includes configurable export strategies (`all`, `first_success`, `best_effort` via `NX_EXPORT_STRATEGY`), per-destination upload tracking, and inter-destination dependencies. New `BUILT_NOT_EXPORTED` status for records that failed to export.

  **Breaking changes:** Database migration required (`uv run alembic upgrade head`). `nexusLIMS.cdcs.upload_record_files()` removed; use `nexusLIMS.exporters.export_records()` instead. ([#35](https://github.com/datasophos/NexusLIMS/issues/35))
- Added eLabFTW export destination plugin supporting automatic export of NexusLIMS session records to [eLabFTW](https://www.elabftw.net/) electronic lab notebook instances. Each session creates one eLabFTW experiment with an HTML summary, structured metadata using eLabFTW's `extra_fields` schema, automatic tagging, and the full XML record attached as a file. Cross-links to CDCS records are automatically included when both destinations are configured.

  Configure with environment variables:
  - `NX_ELABFTW_URL`: eLabFTW instance URL
  - `NX_ELABFTW_API_KEY`: API authentication key
  - `NX_ELABFTW_EXPERIMENT_CATEGORY`: Optional default category ID
  - `NX_ELABFTW_EXPERIMENT_STATUS`: Optional default status ID

  See {ref}`eLabFTW configuration <config-elabftw>` for details.

  ([#42](https://github.com/datasophos/NexusLIMS/issues/42))

### Bug fixes

- Fixed instrument filestore path handling to correctly resolve paths that start with a leading slash. Previously, `pathlib` would treat leading slashes as absolute paths and discard the `NX_INSTRUMENT_DATA_PATH` base directory entirely. A new `join_instrument_filestore_path()` helper function now strips leading slashes before joining paths. ([#43](https://github.com/datasophos/NexusLIMS/issues/43))

### Documentation improvements

- Updated [local deployment documentation](https://datasophos.github.io/NexusLIMS/stable/frontend_guide/local-test-deployment.html) to fix a few errors and be more complete. Also simplified local HTTPS configuration quite a bit in the [`3.18.0-nx1`](https://github.com/datasophos/NexusLIMS-CDCS/releases/tag/3.18.0-nx1) release of NexusLIMS-CDCS. ([#40](https://github.com/datasophos/NexusLIMS/issues/40))


## 2.3.0 (2026-01-19)

### New features

- Add `NX_CLUSTERING_SENSITIVITY` configuration option to control the sensitivity of file clustering into Acquisition Activities. Higher values make clustering more sensitive to time gaps (resulting in more activities), lower values make it less sensitive (fewer activities). Setting to `0` disables clustering entirely and groups all files into a single activity. (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#26](https://github.com/datasophos/NexusLIMS/issues/26))
- Add support for harvesting experiment metadata from NEMO usage event questions. The NEMO harvester now prioritizes data from usage events (what users actually did during their session) over reservation data (what they planned to do), using a three-tier fallback strategy that checks post-run questions, pre-run questions, and finally reservation questions to maximize record accuracy. (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#33](https://github.com/datasophos/NexusLIMS/issues/33))

### Documentation improvements

- Add comprehensive documentation about features, development, and deployment of the CDCS-based frontend. These docs are kept in this repository to have one common documentation site. ([#28](https://github.com/datasophos/NexusLIMS/issues/28))
- Refreshed the NexusLIMS logo to be more modern!

### Miscellaneous/Development changes

- Updated integration test infrastructure to use CDCS 3.18.0. Replaced username/password authentication with API token-based authentication throughout the codebase and test fixtures. Added `NX_TEST_MODE` environment variable to conditionally disable Pydantic validation during testing. (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#30](https://github.com/datasophos/NexusLIMS/issues/30))


## 2.2.0 (2026-01-09)

### New features

- Comprehensive refactor of internal metadata handling with [Pint Quantities](https://pint.readthedocs.io/en/stable/) for representation of physical units and [EM Glossary v2.0.0](https://emglossary.helmholtz-metadaten.de/) standardized field names. All extractor plugins now create Pint Quantity objects for fields with units, providing type safety and machine-readable XML with separate value/unit attributes. Added type-specific validation schemas ({py:class}`~nexusLIMS.schemas.metadata.ImageMetadata`, {py:class}`~nexusLIMS.schemas.metadata.SpectrumMetadata`, {py:class}`~nexusLIMS.schemas.metadata.SpectrumImageMetadata`, {py:class}`~nexusLIMS.schemas.metadata.DiffractionMetadata`) and infrastructure modules for unit handling, EM Glossary integration via [RDFLib](https://rdflib.readthedocs.io/en/stable/index.html), and XML serialization. See the [internal schema docs](../dev_guide/nexuslims_internal_schema.md) for detail.

  > **Note:** Correct display of units in CDCS requires updated stylesheet ([NexusLIMS-CDCS commit 30faa97](https://github.com/datasophos/NexusLIMS-CDCS/commit/30faa97aa380fecc6eb94e6a6abf1631c71a4a5a)). ([#13](https://github.com/datasophos/NexusLIMS/issues/13))
- Added Pydantic-based schema validation for the `nx_meta` data structure returned by extractor plugins. This provides early error detection with clear error messages when plugins return malformed/unexpected metadata. The base `NexusMetadata` schema validates required fields and common optional fields. This is not a user-facing feature, but should provide a base from which to extend more formalized metadata schema verification. ([#13](https://github.com/datasophos/NexusLIMS/issues/13))
- Added multi-signal file support to automatically expand files containing multiple signals or datasets (such as DM3/DM4 files with multiple images or spectra) into separate dataset entries in experimental records. Each signal receives its own metadata extraction, preview image, and XML dataset element with signal indices in the name (e.g., "filename.dm3 (1 of 4)").

  > **Note:** Proper display and download of multi-signal records in the CDCS frontend requires an updated XSLT stylesheet, available in [NexusLIMS-CDCS commit 240a7f9](https://github.com/datasophos/NexusLIMS-CDCS/commit/240a7f9a87c799950b5bbf94ca30eedaef7a1adc). ([#14](https://github.com/datasophos/NexusLIMS/issues/14))
- Enhanced Digital Micrograph extractor to capture additional metadata from JEOL NEOARM TEM images including signal name (e.g., ADF, BF), aperture settings (condenser, objective, and selected area), and pixel dwell time (sample time in microseconds). (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#14](https://github.com/datasophos/NexusLIMS/issues/14))
- Added support for Tescan PFIB (Plasma FIB) TIFF files. The new extractor automatically detects and parses metadata from Tescan microscopy TIFF files, including imaging parameters, stage position, detector settings, and FIB-specific information. (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#15](https://github.com/datasophos/NexusLIMS/issues/15))
- Added support for Zeiss Orion and Fibics helium ion microscope TIFF files. The new extractor automatically detects the variant and parses metadata including beam parameters, stage position, and detector settings. (*Sponsored by UPenn/[Singh Center for Nanotechnology](https://www.nano.upenn.edu/resources/nanoscale-characterization/), thank you!*) ([#16](https://github.com/datasophos/NexusLIMS/issues/16))

### Documentation improvements

- Comprehensive documentation overhaul: restructured sections for clearer layout, added [internal schema docs](../dev_guide/nexuslims_internal_schema.md), expanded [extractor plugin documentation](../user_guide/extractors.md) with schema validation examples, updated [integration tests guide](../dev_guide/testing/integration-tests.md), enhanced [EM Glossary reference](../dev_guide/em_glossary_reference.md) with RDF/SKOS concepts, reorganized [taxonomy documentation](../user_guide/taxonomy.md) with complete metadata field reference, improved [developer guides](../dev_guide/development.md) with unit handling patterns and schema extension examples, updated long-outdated [record building](../user_guide/record_building.md) documentation, and fixed fomatting in [API docs](api.md). ([#13](https://github.com/datasophos/NexusLIMS/issues/13))
- Fixed changelog build issues with towncrier integration and Sphinx documentation generation, along with warnings.

### Miscellaneous/Development changes

- Replaced custom nested dictionary utility functions with the well-maintained [python-benedict](https://github.com/fabiocaccamo/python-benedict) library. This improves code reliability and maintainability by using battle-tested implementations for nested dictionary operations ({func}`~nexusLIMS.utils.dicts.set_nested_dict_value`, {func}`~nexusLIMS.utils.dicts.get_nested_dict_value_by_path`, {func}`~nexusLIMS.extractors.flatten_dict`). Removed vestigial functions `get_nested_dict_key` and `get_nested_dict_value` that had minimal or no production usage. ([#18](https://github.com/datasophos/NexusLIMS/issues/18))
- Refactored TIFF-based extractors ({class}`~nexusLIMS.extractors.plugins.quanta_tif.QuantaTiffExtractor`, {class}`~nexusLIMS.extractors.plugins.tescan_tif.TescanTiffExtractor`, {class}`~nexusLIMS.extractors.plugins.orion_HIM_tif.OrionTiffExtractor`) to use a standardized {class}`~nexusLIMS.extractors.base.FieldDefinition` configuration approach. This reduces code duplication and improves maintainability while preserving extraction functionality and accuracy. ([#21](https://github.com/datasophos/NexusLIMS/issues/21))
- Added Alembic for database schema version control and migrations. Existing installations should run `uv run alembic stamp head` to mark the database as migrated. New schema changes can be tracked with `uv run alembic revision --autogenerate` and applied with `uv run alembic upgrade head`. Configuration lives in `pyproject.toml` under `[tool.alembic]`. ([#24](https://github.com/datasophos/NexusLIMS/issues/24))
- Migrated database layer from raw SQLite to SQLModel ORM with type-safe enums ({class}`~nexusLIMS.db.enums.EventType`, {class}`~nexusLIMS.db.enums.RecordStatus`). This provides type-safe database operations with compile-time checks, automatic datetime handling, and relationship navigation. Notable changes: manual `db_query()` function removed (use SQLModel queries instead), `EventType` and `RecordStatus` are now enums instead of strings, and {class}`~nexusLIMS.db.models.SessionLog` and {class}`~nexusLIMS.db.models.Instrument` are now SQLModel classes. See the [database documentation](../dev_guide/database.md) for migration details and more info. ([#24](https://github.com/datasophos/NexusLIMS/issues/24))
- Refactored test suite to use marker-based infrastructure with opt-in database/file resources via `@pytest.mark.needs_db` and `@pytest.mark.needs_files` markers. Replaced autouse fixtures with on-demand `DatabaseFactory` and `FileFactory` for resource allocation. This delivers large performance improvement for tests that don't need database access, while maintaining 100% backward compatibility with existing tests and preventing cross-test pollution issues. ([#24](https://github.com/datasophos/NexusLIMS/issues/24))
- Refactored {func}`~nexusLIMS.utils.dicts.try_getting_dict_value` to return `None` instead of the magic string `"not found"` as a sentinel value. This improves type safety, follows Python best practices, and prevents potential collisions with legitimate metadata values. All 58 call sites throughout the codebase were updated to use `is None` and `is not None` checks.


## 2.1.1 (2025-12-16)

### Documentation improvements

- Actually fixed documentation version switcher to use full semantic version numbers (e.g., ``2.1.0``) instead of major.minor versions (e.g., ``2.1``), and properly highlight the current version being viewed. The switcher now shows only the most recent patch version for each minor release and marks the highest version as stable. ([#5](https://github.com/datasophos/NexusLIMS/issues/5))

## 2.1.0 (2025-12-16)

### New features

- Implemented instrument profile system for site-specific metadata customization through profiles that can add static metadata, transform fields, and inject custom parsers. Profiles can be built-in (shipped with the package) or local (loaded from ``NX_LOCAL_PROFILES_PATH`` environment variable). ([#9](https://github.com/datasophos/NexusLIMS/issues/9))
- Preview generation has been migrated to a plugin-based system with separate image and text preview generators. ([#9](https://github.com/datasophos/NexusLIMS/issues/9))
- Addition of the plugin-based extractor system; All metadata extractors have been refactored into a plugin-based architecture with auto-discovery, enabling easier addition of new file format support without modifying core code. ([#9](https://github.com/datasophos/NexusLIMS/issues/9))
- Comprehensive Docker-based integration test suite providing end-to-end validation of NexusLIMS workflows. The new test suite includes NEMO and CDCS Docker services, tests for record building, file clustering, metadata extraction, CLI operations, email notifications, multi-instance NEMO support, and extensive error handling scenarios. Includes automated CI/CD integration with GitHub Actions and pre-built Docker images in GitHub Container Registry. ([#10](https://github.com/datasophos/NexusLIMS/issues/10))

### Bug fixes

- Fixed issue where mixed-case or upper-case extensions were not being properly assigned to the correct extractors. ([#4](https://github.com/datasophos/NexusLIMS/issues/4))
- Fixed version switcher to properly display released versions. The switcher now correctly extracts and displays versioned releases (e.g., 2.0, 1.5) from documentation directories and matches them with the proper major.minor version format. ([#5](https://github.com/datasophos/NexusLIMS/issues/5))

### Miscellaneous/Development changes

- Split documentation deployment into separate GitHub Actions workflows for improved modularity and independent execution of docs builds from test runs. ([#8](https://github.com/datasophos/NexusLIMS/issues/8))


## 2.0.0 (2025-12-06)

### New features

- Initial release of the [datasophos](https://datasophos.co) fork of NexusLIMS!
- Migrated record processing from a bash script (`process_new_records.sh`) to a new Python CLI script (`nexuslims-process-records`),
  offering improved error handling, structured logging, SMTP-based email notifications, file locking, and comprehensive
  unit tests.
- New helper script for initializing the database with test or real data (`scripts/initalize_db.py`).

### Enhancements

- Added the ability to customize the number of retries for the NEMO connector, improving flexibility and test performance.
- Enhanced module loading to allow successful import even if the database is not yet properly configured, improving flexibility for environments where the database setup is delayed.
- Migrated dependency management from Poetry to `uv`, streamlining the development environment and improving build performance. This included extensive code modernization, addressing all Ruff linting issues, implementing type stubs, enhancing the test suite for reliability and isolation, and updating configuration and documentation to reflect these significant changes.
- Migration from direct environment variable access to a settings-based configuration system (using [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)), enhancing configuration consistency and type safety throughout the codebase.
- Refactored settings management to support test isolation and improved maintainability, along with several bug fixes and general code quality enhancements.
- Refactored the test suite into hierarchical modules for better organization and maintainability.
- Updated dependencies (including hyperspy to 2.0+)

### Documentation improvements

- Add a comprehensive documentation page for the extractors within NexusLIMS.
- Added a migration guide to support users migrating from v1 to v2
- Added improved auto-generated documentation for XML schema with interactive visualization ({std:doc}`../dev_guide/schema_documentation`).
- Migrated documentation to the modern PyData Sphinx Theme, offering a refreshed look, improved mobile responsiveness, and dark mode support. This overhaul includes a complete restructuring into hierarchical sections, a comprehensive "Getting Started" guide, new logo branding, and streamlined configuration.

### Miscellaneous/Development changes

- Added highly-compressible test files for extractors and record building process so test suite can run isolated from a deployed environment.
- Implemented full Github actions for CI/CD, covering tests, documentation, and release deployment.
- Migrated test suite to unit test pattern that can run without any external services connected.

### Deprecations and/or Removals

- Removed the deprecated SharePoint harvester.
- Removed tox for test running and local development processes, with most functions going into the `./scripts/` directory.

```{note}
The following changelog for versions up to v1.4.3
is copied from the original NIST [NexusLIMS project](https://github.com/usnistgov/NexusLIMS).
```

## 1.4.3 (2024-06-07)

### Bug fixes

- Add ability to parse XML metadata included in some FEI/Thermo TIFF files that was
  causing the TIFF extractor to fail when it was present.

## 1.4.2 (2024-05-29)

### Bug fixes

- Added workaround for issue where duplicate section titles would cause error in
  `quanta_tif` extractor.

## 1.4.1 (2023-09-20)

### Bug fixes

- Resolved issue where text files that can't be opened with any encoding caused the record
  builder to crash

### Documentation improvements

- Documented internal release and deploy process on Wiki

## 1.4.0 (2023-09-19)

### New features

- Added ability to generate previews for "plain" image files (e.g. `.jpg`, `.png`,
  etc.) and plain text files.

### Bug fixes

- Fix problem arising from NEMO API change that removed `username` keyword.

## 1.3.1 (2023-05-19)

### Bug fixes

- Fixed issue where "process new records" script was emailing an error alert on conditions
  that were not errors.

### Miscellaneous/Development changes

- Fixed pipeline runner to not run tests when they're not needed.

## 1.3.0 (2023-04-14)

### New features

- Add support for reading `.spc` and `.msa` EDS spectrum files produced by EDAX
  acquisition softwares.

### Documentation improvements

- Add [towncrier](https://towncrier.readthedocs.io/) to manage documentation of
  changes in a semi-automated manner.

## 1.2.0 (2023-03-31)

### New features

- Added new "default" extractor for filetypes we don't know how to read
  that will add very basic file-based metadata otherwise
- Added a configuration environment variable for file finding
  (`NX_FILE_STRATEGY`). A value of `"inclusive"` will add all files found in
  the time range of a session to the record (even if we don't know how to parse it beyond
  basic metadata). A value of `"exclusive"` will exlcude files that do not have an
  explicit extractor defined (this was the previous behavior)
- Added a way to "ignore" files during the file finding routine via an environment
  variable named `NX_IGNORE_PATTERNS`. It should be a JSON-formatted list
  provided as a string. Each item of the list will be passed to the GNU find command
  as a pattern to ignore.

### Bug fixes

- Fixed Poetry not installing due to change in upstream installer location
- Fixed issue where record builder would not run (and we wouldn't even be alerted!)
  if the network shares for `NX_INSTRUMENT_DATA_PATH` and `NX_DATA_PATH` were not mounted.
- Fixed bug introduced by change to API response for reservation questions in NEMO 4.3.2
- Fix for development bug introduced by upgrade of tox package to 4.0.

### Enhancements

- Added support for `"NO_CONSENT"` and `"NO_RESERVATION"` statuses in the
  `session_log` table of the NexusLIMS database
- Harvesters (and other parts of the code that use network resources) will now retry
  their requests if they fail in order to make the record building process more resilient
- Harvester will now read periodic table element information from NEMO reservation
  questions and include them in the XML records. Also updated the schema and CDCS XSLT
  to allow for and display this information in the front end.
- File finding now works on a directory of symbolic links (in addition to a regular
  folder hierarchy).

### Documentation improvements

- Improved documentation to be public-facing and also set up structure for public
  repository at https://github.com/usnistgov/nexuslims,
  https://github.com/usnistgov/NexusLIMS-CDCS, and
  https://github.com/usnistgov/nexuslims-cdcs-docker
- Add NIST branding to documentation via header/footer script from pages.nist.gov

### Miscellaneous/Development changes

- If the record building delay has not passed and no files were found, a
  `RECORD_GENERATION` event will no longer be added to the `session_log` table
  in the database to avoid cluttering things up.
- Public facing branches are now excluded from CI/CD pipeline to prevent test failures
- Updated code to use various linters, including
  [isort](https://pycqa.github.io/isort/), [black](https://github.com/psf/black),
  [pylint](https://pylint.readthedocs.io/en/latest/), and
  [ruff](https://beta.ruff.rs/docs/).
- Add support for Python 3.10(.9)
- Moved URL configration to environment variables
- Updated third-party dependencies to recent latest versions

### Deprecations and/or Removals

- Remove support for Python 3.7.X
- Removed unused LDAP code

## 1.1.1 (2022-06-15)

### Bug fixes

- Fixed issue where record builder would crash if only one file was found during the
  activity (and added explicit test for this condition).
- Fix issue in NEMO harvester where not-yet-ended sessions would cause the harvester
  to try to insert rows that violated database constraints.
- Implemented a "lockfile" system so concurrent runs of the record builder will not
  be allowed, preventing extra entries in the `session_log` table that were causing
  errors.
- Fix reading reservation and usage event times from NEMO servers with differing datetime
  formats.
- The NEMO harvester no longer attempts to build records without explicit "data consent"
  supplied by the user during the reservation questions (previously, if no reservation
  was found, the harvester would return a generic event and a record would still be built).
- Fixed bug where null bytes in a TIFF file caused an error in metadata extraction

### Enhancements

- Add ability for record builder to insert a link to reservation information in the
  `summary` node (modified schema to hold this and record builder to insert it).
- Contributed a [PR](https://github.com/usnistgov/NEMO/pull/97) to the upstream NEMO
  project to allow for displaying of a single reservation, so that we may link to it
  and include it as a reference in records built by NexusLIMS.
- Made the default `data_consent` value for the NEMO harvester False, so we will not
  harvest data from sessions that do not have reservation questions defined (users
  now have to opt-in to have their data curated by NexusLIMS).
- NEMO harvester now limits its API requests to only tools defined in the NexusLIMS
  database, which is more efficient and greatly speeds up the harvesting process.
- The record builder will now retry for a configurable number of days if it does not find
  any files for a session (useful for machines that have a delay in data syncing to
  centralized file storage). Configured via the `NX_FILE_DELAY_DAYS` environment
  variable.
- Made datetime formats for NEMO API harvester configurable (both sending and receiving)
  so that it can work regardless of configuration on the NEMO server.
- Record generation events in the database now have timezone information for better
  specificity in multi-timezone setups.
- Add `pid` attribute to Experiment schema to allow for integration with CDCS's handle
  implementation.

### Miscellaneous/Development changes

- Configured tests to run on-premises, which speeds up various testing operations.
- Drastically restructured repository to look more like a proper Python library than just
  a collection of files and scripts.
- Migrated project organization and packaging from
  [pipenv](https://pipenv.pypa.io/en/latest/) to [poetry](https://python-poetry.org/).
- Fixed some tests that started failing due to tool ID changes on our local NEMO server.
- Improved logging from NEMO harvester making it easier to debug issues when they occur.
- Session processing script is now smarter about email alerts.
- CI/CD pipeline will now retry failed tests (should be more resilient against transient
  failures due to network issues).
- Made some changes to the codebase in preparation of making it public-facing on Github.

### Deprecations and/or Removals

- Removed a variety of associated files that were not important for the Python package
  (old presentations, diagrams, reports, etc.)
- The `nexusLIMS.harvesters.sharepoint_calendar` module was deprecated after
  the SharePoint calendaring system was decommissioned in the Nexus facility. All
  harvester development will center around NEMO for the foreseeable future.
- Removed enumeration restriction on PIDs from the schema so it is more general (and
  easier to add new instruments without having to do an XML schema migration).

## 1.1.0 (2021-12-12)

### New features

- Major new feature in this release is the implementation of a reservation and metadata
  harvester for the [NEMO](https://github.com/usnistgov/NEMO) facility management
  system. All planned future feature development will focus on this harvester, and the
  SharePoint calendar harvester will be deprecated in a future release. See the
  {std:doc}`../user_guide/record_building` docs and the {std:doc}`../api/nexusLIMS/nexusLIMS.harvesters.nemo` docs
  for more details.

### Enhancements

- Add support to NEMO harvester for multiple samples in a set of reservation questions.
  The required structure for reservation questions is documented in the
  {py:func}`nexusLIMS.harvesters.nemo.res_event_from_session` function.
- Added ability to specify timezone information for instruments in the NexusLIMS database,
  which helps fully qualify all dates and times so file finding works as expected when
  inspecting files stored on servers in different timezones.
- Updated detail XLST to display multiple samples for a record if present (since this
  is now possible using the NEMO reservation questions).

### Documentation improvements

- Documented new NEMO harvester and updated record generation documentation to describe
  how the process works with multiple harvesters.
- Fixed broken image paths in README.

### Miscellaneous/Development changes

- Migrated project structure from [pipenv](https://pipenv.pypa.io/en/latest/) to [poetry](https://python-poetry.org/) for better dependency
  resolution, easier and faster deployment, and configuration of project via
  `pyproject.toml`. Also implemented [tox](https://tox.wiki/en/latest/) for the running of tests, doc builds,
  and pipelines.
- Refactored some functions from the SharePoint harvester into the
  {py:mod}`nexusLIMS.utils` module for easier use throughout the rest of the codebase.

### Deprecations and/or Removals

- Removed the "Session Logger" application in favor of using NEMO and its usage events
  to track session timestamps.

## 1.0.1 (2021-09-15)

### New features

- Implemented a "file viewer" on the front-end NexusLIMS application which also allows
  for downloading single, multiple, or all data files from a particular record in
  `.zip` archives.
- Implemented a metadata extractor for `.ser` and `.emi` files produced by the TIA
  application on FEI TEMs.
- Added ability to export a record as XML in the front end NexusLIMS application.
- Added a "tutorial" feature to the front-end of the NexusLIMS application, which leads
  users through a tour describing what the various parts of the application do.
- Added new "dry run" mode and additional verbosity options to record builder that allow
  one to see what records `would` be built without actually doing anything.

### Bug fixes

- Fixed issue where Session Logger app was failing due to incompatibilities between
  the code and certain database states.
- Fixed issue where Session Logger app was leaving behind a temporary file on the
  microscope computers by making it clean up after itself.
- Fixed issue where multiple copies of the Session Logger app were able to be run at the
  same time, which shouldn't have been possible.
- Fixed the "back to previous" button in the front-end application that was broken.
- Fixed issue with SharePoint harvester where records were being assigned to the person
  who `created` a calendar event, not the person whose name was on the actual event.
- Fixed a deployment issue related to `pipenv` and how it specifies packages to be
  installed.
- Fixed issues with `.ser` file handling (and contributed various fixes upstream to the
  HyperSpy project: [1](https://github.com/hyperspy/hyperspy/pull/2533),
  [2](https://github.com/hyperspy/hyperspy/pull/2531),
  [3](https://github.com/hyperspy/hyperspy/pull/2529)).

### Enhancements

- Added customized loading text while the list of records is loading in the front-end
  NexusLIMS application.
- Tweaked heuristic in SharePoint harvester to better match sessions to calendar events
  (previously, if there were multiple reservations in one day, they may have been
  incorrectly attributed to a session).
- Added explicit support for Python 3.8.X versions.
- Implemented bash script to run record builder automatically, which can then be scheduled
  via a tool such as `cron`.
- Added version information to Session Logger app to make it easier for users to know
  if they are up to date or not.
- Small tweak to make acquisition activity links easier to click in record display.

### Documentation improvements

- Added "taxonomy" of terms used in the NexusLIMS project to the documentation (see
  {std:doc}`../user_guide/taxonomy` for details).
- Added XML Schema documentation for the Nexus `Experiment` schema to the documentation
  (see {std:doc}`../dev_guide/schema_documentation` for details).
- Added links to NexusLIMS documentation in the front-end NexusLIMS CDCS application.
- Added many documentation pages to more thoroughly explain how NexusLIMS works,
  including improvements to the project README, as well as the following pages:
  {std:doc}`../dev_guide/database`, session_logger_app, {std:doc}`../dev_guide/development`,
  and pages about data security.

### Miscellaneous/Development changes

- Improvement to logging to make it easier to debug records not being built correctly.
- Added new {py:class}`~nexusLIMS.harvesters.reservation_event.ReservationEvent` class
  to abstract the concept of a calendar reservation event. This reduces dependencies on
  the SharePoint-specific way things were written before and will help in the future
  implementation of the NEMO harvester.
- Fix some issues with tests not running correctly due to changes of paths in
      `NX_INSTRUMENT_DATA_PATH`.- Improvements to the CI/CD pipelines so multiple pipelines can run at once without error.

## 0.0.9 (2020-02-24) - First real working release

### New features

- Added extractor for TIFF image files produced by FEI SEM and FIB instruments.
- Record builder can now be run automatically and will do the whole process (probing
  database, finding files, extracting metadata, building record XML, and uploading to
  CDCS frontend).

### Enhancements

- Acquisition activities are now split up by clustering of file acquisition times, rather
  than inspecting when an instrument switches modes. This is more realistic to how
  microscopes are used in practice (see
  {ref}`Activity Clustering <build-activities>` for more details).
- Added "instrument specific" parsing for DigitalMicrograph files
- Added {py:mod}`nexusLIMS.utils.cdcs` module to handle interactions with the CDCS front-end.
- Added a "Data Type" to all metadata extractions that will attempt to classify what sort
  of data a file is ("STEM EELS", "TEM Image", "SEM EDS", etc.).
- Configuration of program options is now mostly done via environment variables rather
  than values hard-coded into the source code.
- Drastically improved file finding time by utilizing GNU `find` to identify files in
  a record rather than a pure Python implementation.
- Records now use a "dummy title" if no matching reservation is found for a session.
- Thumbnail previews of DigitalMicrograph files will now include image annotations.
- Updated SharePoint calendar harvester to be compatible with SharePoint 2016.
- Various XSLT enhancements for better display of record data.

### Documentation improvements

- Added record building documentation: {std:doc}`../user_guide/record_building`.

### Miscellaneous/Development changes

- Added helper script to update XLST on NexusLIMS front-end via API, making things easier
  for development.
- Fully implemented tests to ensure 100% of codebase is covered by test functions.
- Refactored record builder and harvester to use
  {py:class}`~nexusLIMS.db.models.Instrument` instances rather than string parsing.

## 0.0.2 (2020-01-08) - Pre-release version

### New features

- Added ability to use custom CA certificate for network communications (useful if
  communicating with servers with self-signed certificates).
- Added javascript-powered XLST for more interactive and fully-featured display of records
  in the CDCS front-end (T. Bina).
- Added session logging .exe application that can be deployed on individual microscope PCs
  to specify when a session starts and ends (used to get timestamps for file finding
  during record building).
- Finished implementation of building `AcquisitionActivity` representations of
  experiments, which are then translated into XML for the final record.
- Implemented prototype record builder script for automated record generation (T. Bina).
- Preview images are now generated for known dataset types during the creation of
  acquisition activities in record building.

### Bug fixes

- Updated endpoint for sharepoint calendar API that had broken due to a change in that service.
- Fixed issue where schema had duplicate "labels" for certain fields that was causing
  a confusing display in the CDCS "curate" page.

### Enhancements

- Added other Nexus instruments to the schema so we can have records from more than just
  a single `Instrument` (as it was in initial testing).
- Added a `unit` attribute to parameter values in the `Nexus Experiment` schema.
- Added a place to insert "project" information into `Nexus Experiment` schema
- Improved the implementation of the `Instrument` type within the `Nexus Experiment`
  schema.
- Added spiffy logo for NexusLIMS
- Formatted repository as a proper Python package that can be installed via `pip`.
- Generalized metadata extraction process in anticipation of implementing extractors for
  additional file types.
- Instrument configuration is now fully pulled from NexusLIMS DB, rather than hard-coded
  in the application code.
- XSLT now properly displays preview images rather than a placeholder for each dataset.

### Documentation improvements

- Fix links in README to point to new upstream project location.
- Added basic documentation for NexusLIMS package and link via a badge on the README.

### Miscellaneous/Development changes

- Moved project out of a personal account and into it's own NexusLIMS group on Gitlab.
- Added dedicated folder (separate form data storage location) for NexusLIMS to write
  dumps of extracted metadata and preview images.
- Added database initialization script to create correct NexusLIMS DB structure.
- Refactored record builder and calendar harvesting into separate submodules to better
  delineate functionality of the various parts of NexusLIMS

## 0.0.1 (2019-03-26) - Pre-release version

### New features

- Implemented SharePoint calendar metadata harvesting for equipment reservations.
- Added metadata extractor for FEI TIFF image files produced by SEMs and FIBs.
- Created repository to hold initial work on NexusLIMS.

### Enhancements

- Added a concept of "role" (experimental, calibration, etc.) to datasets in the
  `Nexus Experiment` schema

### Miscellaneous/Development changes

- Added CI/CD pipeline for backend tests.
