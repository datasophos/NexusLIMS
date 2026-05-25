## Welcome to version 2.7.0 of NexusLIMS!

### Highlights

This release adds per-user CDCS record ownership: NexusLIMS can now automatically look up or create a CDCS user account that matches the NEMO session user and assign uploaded records to that account. A companion setting gives you independent control over whether records are placed in the global public workspace. Together, these settings allow deployments to give individual researchers ownership of their own experimental records in CDCS.

As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### New Features

**Per-user CDCS record ownership** ([#106](https://github.com/datasophos/NexusLIMS/pull/106))
- New `NX_CDCS_USER_OWNED_RECORDS` setting (default `false`): when enabled, each uploaded record is assigned to a CDCS user account that matches the NEMO session user
- NexusLIMS searches CDCS for an existing account by username, then by email, and creates one automatically if none exists
- New `NX_CDCS_ASSIGN_TO_PUBLIC_WORKSPACE` setting (default `true`): controls whether uploaded records are placed in the global public workspace, independently of ownership
- Both settings can be combined -- a record can be user-owned and publicly visible at the same time
- Requires `NX_CDCS_TOKEN` to belong to a superuser account when `NX_CDCS_USER_OWNED_RECORDS` is enabled; user management failures never block the export (record is uploaded as admin-owned with a warning)

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==2.7.0

# or
pip install nexuslims==2.7.0

# or, if installed from source:
git fetch
git checkout v2.7.0
uv sync
```

### Full changelog
https://github.com/datasophos/NexusLIMS/compare/v2.6.2...v2.7.0
