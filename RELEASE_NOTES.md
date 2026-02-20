## Welcome to version 2.5.1 of NexusLIMS!

### Highlights
This is a patch release focused on dependency compatibility and installation
improvements. The most notable fix allows NexusLIMS to install cleanly on
ARM-based devices (such as a Raspberry Pi) without requiring manual compilation
of native libraries. Several key dependencies have also been updated to their
latest major versions.

As always, if you are looking for assistance with configuration or deployment of
NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss
your needs!

### Bug Fixes

**Fix `lxml` dependency constraint blocking Raspberry Pi installs** ([#85](https://github.com/datasophos/NexusLIMS/issues/85))
  - Fixed issue where NexusLIMS could not install easily on a Raspberry Pi device
    without significant compilation effort due to an outdated pinned dependency on `lxml`.

### Internal / Miscellaneous

- Updated dependencies: bumped lxml to v6, requests to v2.32+, python-dotenv to v1,
  textual to v8, Sphinx to v9, and ruff to v0.9; removed deprecated `requests-ntlm`
  and `defusedxml` dependencies. ([#85](https://github.com/datasophos/NexusLIMS/issues/85))

### Installation

```bash
uv tool install nexuslims==2.5.1

# or
pip install nexuslims==2.5.1

# or, if installed from source:
git fetch
git checkout v2.5.1
uv sync
```

### Full Changelog
**Full Changelog**: https://github.com/datasophos/NexusLIMS/compare/v2.5.0...v2.5.1
