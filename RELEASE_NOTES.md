## Welcome to version 2.7.4 of NexusLIMS!

### Highlights
This release fixes record builder failures that could occur when scheduler usage events were revised and duplicate session `END` rows were present. It also tightens the pull request release process by requiring Towncrier changelog fragments before expensive CI jobs run, while allowing the `no-changelog-required` label for changes that do not need release notes.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Bug Fixes

**Handle duplicate session end rows after scheduler revisions** ([#117](https://github.com/datasophos/NexusLIMS/issues/117))
  - Fixed record builder failures caused by duplicate session `END` rows after scheduler usage events are revised.

### Internal / Miscellaneous

- Added a pull request check requiring a Towncrier changelog fragment and documented the fragment expectations for future agent work.
- Gated expensive pull request test jobs behind the Towncrier changelog fragment check, with a `no-changelog-required` label override for changes that do not need a release note. Adding or removing that label reruns the gate.

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.7.4

# or
pip install nexuslims==2.7.4

# or, if installed from source:
git fetch
git checkout v2.7.4
uv sync
```

### Full changelog

https://github.com/datasophos/NexusLIMS/compare/v2.7.3...v2.7.4
