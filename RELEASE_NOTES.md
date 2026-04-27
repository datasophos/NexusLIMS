## Welcome to version 2.6.2 of NexusLIMS!

### Highlights

This is a patch release fixing two bugs in the Tofwerk pFIB-ToF-SIMS preview generator that caused preview generation to fail for certain HDF5 acquisition files. Large pre-processed files (e.g. 500×256×256×259 float32 arrays ~32 GiB) would previously crash with an out-of-memory error; raw files whose `NbrWrites` attribute disagreed with the actual data shape by one would fail with a matplotlib `ValueError`. Both are now resolved.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Bug Fixes

- **Tofwerk pFIB-ToF-SIMS preview generator: OOM and depth-profile shape mismatch** ([#105](https://github.com/datasophos/NexusLIMS/pull/105))
  - Replaced the full `PeakData/PeakData[:]` load with a write-by-write chunked reader, reducing peak memory from ~32 GiB to ~135 MB for a 500×256×256×259 acquisition.
  - Fixed a `ValueError: x and y must have same first dimension` in raw-file depth plots by deriving the x-axis from the actual `EventList` shape rather than the `NbrWrites` root attribute, which can disagree by one.

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.6.2

# or
pip install nexuslims==2.6.2

# or, if installed from source:
git fetch
git checkout v2.6.2
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.6.1...v2.6.2
