## Welcome to version 2.7.3 of NexusLIMS!

### Highlights

This release adds the XML schema elements needed to support the dataset curation features introduced in NexusLIMS-CDCS `3.21.0-nx1`. The Nexus Experiment schema now includes an optional `<curation>` block on each dataset for storing curator-assigned ratings and featured status, which the new public gallery uses to select and prioritize preview images. All existing records remain valid with no migration required on the backend side; run `admin-upgrade-schema` on the frontend after deploying `3.21.0-nx1`.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### New Features

**Dataset curation schema elements** ([#116](https://github.com/datasophos/NexusLIMS/pull/116))
  - Added optional `<curation>` complex type to the `Dataset` element in `nexus-experiment.xsd`
  - `<rating>` child element (xs:integer, 1-5) stores curator-assigned quality scores
  - `<featured>` child element (xs:boolean) marks datasets for prominent display in the public gallery
  - Change is fully backward-compatible; the block is absent when neither value is set

### Documentation Improvements

**3.21.0-nx1 frontend release documentation** ([#116](https://github.com/datasophos/NexusLIMS/pull/116))
  - Documented the public dataset gallery at `/gallery/` including slide selection logic, keyboard navigation, and full-screen mode
  - Documented per-dataset rating and featured-status controls in the annotation panel and dataset tables
  - Expanded the production upgrade guide with a new `admin-upgrade-schema` step (including expected output), a manual web-UI fallback procedure, and a `cdcs-production-upgrading` anchor for cross-page linking
  - Updated administration docs with `admin-update-xslt` and `admin-upgrade-schema` command reference entries
  - Added Gallery Configuration section documenting `NX_ENABLE_GALLERY`, `NX_GALLERY_FACILITY_NAME`, `NX_GALLERY_ROTATION_INTERVAL`, and `NX_GALLERY_LOGO` environment variables
  - Updated compatibility matrix: `3.21.0-nx1` requires NexusLIMS backend 2.7.3+

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.7.3

# or
pip install nexuslims==2.7.3

# or, if installed from source:
git fetch
git checkout v2.7.3
uv sync
```

### Full changelog

https://github.com/datasophos/NexusLIMS/compare/v2.7.2...v2.7.3
