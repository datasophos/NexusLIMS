## Welcome to version 2.6.1 of NexusLIMS!

### Highlights

This release brings a new `nexuslims extract` CLI command for quick single-file metadata extraction and preview generation, making it easier to inspect and debug microscopy files from the command line. The FEI TIFF extractor has been expanded to support both SEM and TEM TIFF formats, and the HyperSpy preview generator now handles EDAX `.msa` and `.spc` spectrum files. Several robustness fixes address edge cases in the DM3/DM4 extractor and blank 16-bit TIFF previews.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### New Features

**Expanded FEI TIFF extractor with TEM support** ([#95](https://github.com/datasophos/NexusLIMS/pull/95))
  - `QuantaTiffExtractor` has been renamed to `FeiTiffExtractor` and now supports both FEI SEM (INI-style) and FEI TEM (`<Root>` XML) TIFF metadata formats
  - The old `quanta_tif` module is retained as a backward-compatibility shim -- no changes required to existing configurations
  - Added test coverage for FEI TEM bright-field image and SAED diffraction extraction paths

**`nexuslims extract` CLI command** ([#96](https://github.com/datasophos/NexusLIMS/pull/96))
  - New command for single-file metadata extraction and preview generation directly from the terminal
  - Useful for inspecting files, debugging extractor behavior, and verifying instrument profiles without running a full record build

**HyperSpy preview support for spectrum files** ([#97](https://github.com/datasophos/NexusLIMS/pull/97))
  - The HyperSpy preview generator now produces thumbnail plots for `.msa` and `.spc` spectrum file formats (EDAX)

### Bug Fixes

- Fixed `KeyError` exceptions in the DM3/DM4 extractor for files missing a `Name` key, 24-hour timestamps, and EELS TagGroups without an `Operation` key. ([#98](https://github.com/datasophos/NexusLIMS/pull/98))
- Fixed blank preview thumbnails for 16-bit TIFF images by applying a 2nd--98th percentile contrast stretch before converting to 8-bit. ([#99](https://github.com/datasophos/NexusLIMS/pull/99))
- Moved `acceleration_voltage` and `stage_position` to the base `NexusMetadata` class; added `acquisition_device` and `horizontal_field_width` to `SpectrumMetadata`. ([#100](https://github.com/datasophos/NexusLIMS/pull/100))

### Documentation Improvements

- Added CLI reference and extractor documentation for the `nexuslims extract` command. ([#101](https://github.com/datasophos/NexusLIMS/pull/101))
- Documented the NexusLIMS-CDCS record annotator app with screenshots for the side panel, inline editing, and full-page editor entry points. ([#103](https://github.com/datasophos/NexusLIMS/pull/103))

### Internal / Miscellaneous

- Updated CDCS REST API endpoint URLs to include trailing slashes, required for compatibility with NexusLIMS-CDCS 3.20.x; added a [version compatibility reference page](https://datasophos.github.io/NexusLIMS/2.6.1/reference/compatibility.html). ([#91](https://github.com/datasophos/NexusLIMS/pull/91))
- Added support and CI coverage for Python 3.13 and 3.14. ([#93](https://github.com/datasophos/NexusLIMS/pull/93))

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.6.1

# or
pip install nexuslims==2.6.1

# or, if installed from source:
git fetch
git checkout v2.6.1
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.6.0...v2.6.1
