## Welcome to version 2.7.2 of NexusLIMS!

### Highlights
This release is maintenance-focused and does not include end-user feature changes or runtime bug fixes, so upgrading is optional unless you want the latest documentation and development workflow updates. It improves project maintenance and documentation around NexusLIMS frontend compatibility, fixes PR documentation preview deployment for closed pull requests, and speeds up local and CI test runs by running tests in parallel.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Bug Fixes

**Skip closed PR documentation previews**
  - Skipped PR documentation preview deployment when the pull request has already closed, avoiding failed `gh-pages` updates after merge.

### Documentation Improvements

**Update NexusLIMS-CDCS compatibility documentation** ([#111](https://github.com/datasophos/NexusLIMS/issues/111))
  - Updated the frontend changelog and screenshot gallery for NexusLIMS-CDCS v3.21.0-nx0.
  - Documented sample and activity management in the annotator, inline title editing, the pending-changes modal, and multi-sample Bootstrap cards.
  - Restored the missing 2.7.0 changelog entry.
  - Added the v3.21.0-nx0 row to the version compatibility matrix.

### Internal / Miscellaneous

**Parallel test execution** ([#110](https://github.com/datasophos/NexusLIMS/issues/110))
  - Test suite now runs in parallel using `pytest-xdist`, reducing local and CI test time significantly.

**Shared release workflow guidance**
  - Moved the release workflow guidance into shared agent skill files so release preparation stays consistent across supported agent tooling.

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.7.2

# or
pip install nexuslims==2.7.2

# or, if installed from source:
git fetch
git checkout v2.7.2
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.7.1...v2.7.2
