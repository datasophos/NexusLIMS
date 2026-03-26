(cdcs-changelog)=
# Frontend Changelog

This [changelog](https://keepachangelog.com/) tracks NexusLIMS-specific changes to the CDCS frontend.
It documents only the customizations made on top of the upstream CDCS/MDCS base. 
Upstream CDCS release notes are available from the 
[MDCS project](https://github.com/usnistgov/MDCS).

Version numbers for NexusLIMS-CDCS use the format `{CDCS base version}-nx{N}`
(e.g., `3.18.0-nx1`), where the base version reflects the upstream CDCS release
and `nx{N}` is an incrementing counter for NexusLIMS-specific releases on that base.

---

## 3.20.0-pre -- 2026-03-28

This version is intended to be used with NexusLIMS backend versions 2.6.1+.

### Added

- **Annotator app** (`nexuslims_annotate`): Added a new Django app for reviewing and
  annotating NexusLIMS experiment records directly in the browser
  - Annotation panel accessible from any detail-view record page allows users
    (with edit rights) to add plain-text descriptions to any dataset
  - Dedicated full-width annotator page for a focused editing experience that
    also allows moving/reassigning datasets between acquisition activities
  - Help text and tutorials for all the new annotator features
- **GitHub Actions CI**: unit test workflow that runs the Django test suite on
  every push and pull request (also added basic Django tests for certain functions)

### Changed

- XSLT translator received some updates to better display dataset descriptions
  in the record view
- CDCS base upgraded to **MDCS 3.20.0** (core packages `2.20.*`, Django 5.2)

---

## 3.18.0-nx1 -- 2026-01-31

### Added

- Automatic local TLS certificate provisioning via Caddy, eliminating manual
  certificate setup for development deployments
- Improved documentation for local HTTPS deployment workflow

### Changed

- Simplified `docker-compose` configuration for local development with HTTPS

---

## 3.18.0-nx0 -- 2026-01-19

Initial tagged release of NexusLIMS customizations on the CDCS 3.18.0 base,
incorporating a major refactor and a large set of frontend improvements.
This version is intended to be used with NexusLIMS backend versions 2.0 through
2.6.0.

### Added

- **Guided tour system**: Shepherd.js-based tours for the home, explore, and
  detail pages; tours can be enabled/disabled per user; mobile-responsive
- **Token authentication**: API token support in deployment configurations,
  enabling programmatic record submission from the NexusLIMS harvester
- **JSON/XML export**: one-click export of experiment records from the detail
  view in both formats
- **XSLT debug mode**: configurable flag to expose raw XSLT transformation
  errors in the browser for easier troubleshooting
- **Configurable instrument badge colors**: map instrument names to Bootstrap
  color classes via `INSTRUMENT_BADGE_COLORS` setting
- **Configurable dataset display threshold**: hide the dataset file list for
  records with more than `DATASET_DISPLAY_THRESHOLD` files
- Bandwidth limit on the Caddy file server image

### Changed

- Migrated Python dependency management from pip/requirements files to
  [uv](https://github.com/astral-sh/uv) with a committed lockfile
  (`uv.lock`) for reproducible builds
- Modernized detail page styling with Bootstrap 5 throughout
- Upgraded DataTables to 2.3.6 with Bootstrap 5 integration; DataTables
  initialization extracted into a dedicated JS module
- Detail view navigation and layout consistency improvements
- File list modal rebuilt with Bootstrap 5 and improved tooltip styling;
  fixed header for large file lists
- Improved responsive layout on the home page
- Replaced browser-detection guards with feature detection
- Modernized NexusLIMS logos throughout the UI
