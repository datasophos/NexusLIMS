## Welcome to version 2.7.1 of NexusLIMS!

### Highlights

This is a patch release that fixes a bug in XML record generation where the `<sample>` element was missing its required `id` attribute. Without this fix, all `<sampleID>` references within acquisition activities in built records were dangling and unresolvable per the NexusLIMS schema. All users building records are encouraged to upgrade.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Bug Fixes

- **Fixed missing `id` attribute on `<sample>` element in built XML records** ([#108](https://github.com/datasophos/NexusLIMS/pull/108)) -- `<sampleID>` references within every acquisition activity were dangling and unresolvable per the NexusLIMS schema.

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.7.1

# or
pip install nexuslims==2.7.1

# or, if installed from source:
git fetch
git checkout v2.7.1
uv sync
```

### Full changelog

https://github.com/datasophos/NexusLIMS/compare/v2.7.0...v2.7.1
