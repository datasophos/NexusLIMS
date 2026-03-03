# LabArchives Multi-User Notebook Ownership

## The Problem

LabArchives explicitly warns against using a single admin user to own all notebooks:

> "Do not use a single 'admin' user account to permanently own all notebooks at an institution. LabArchives is not designed or optimized for ownership of thousands of notebooks by a single user; API performance can degrade, severely in some cases. (A single 'admin' user account can be used to create and manage all notebooks for an institution, if the notebooks are owned by other users.)"

The current NexusLIMS implementation uses a single `NX_LABARCHIVES_USER_ID` to own all records. This is acceptable for small deployments but may degrade at scale.

## Current Decision (v2.6.0)

**Proceed with single admin ownership.** The performance concern targets institutions with thousands of notebooks. Most NexusLIMS deployments are unlikely to hit that scale in the near term. Revisit if LabArchives performance degrades or if a better registration mechanism becomes available.

## How LabArchives Ownership Works

The `uid` parameter in API calls controls record **ownership**, independent of authentication. Admin AKID + ACCESS_PASSWORD signs every request; the `uid` determines which user's notebook receives the record. This means it is architecturally possible for one admin account to create notebooks owned by individual researchers — the infrastructure problem is getting each researcher's `uid`.

## Existing Infrastructure (Already Implemented)

NexusLIMS already has a DB table designed for this:

```python
# nexusLIMS/db/models.py
class ExternalUserIdentifier(SQLModel, table=True):
    nexuslims_username: str        # canonical NexusLIMS/NEMO username
    external_system: str           # ExternalSystem.LABARCHIVES_ELN
    external_id: str               # LabArchives uid (e.g. "285489257Ho")
    email: str | None

# Helper functions already exist:
get_external_id(nexuslims_username, ExternalSystem.LABARCHIVES_ELN)  # → uid or None
store_external_id(nexuslims_username, ExternalSystem.LABARCHIVES_ELN, uid)
```

The `ExternalSystem.LABARCHIVES_ELN` enum value is already defined. Wiring this into the exporter requires:
1. Making `LabArchivesClient` accept a per-call `uid` override
2. Looking up `context.user` → LabArchives uid in `export()`, falling back to the config UID

## Why Per-User Registration Is Hard

Getting a researcher's LabArchives `uid` requires one of:
- **`users/user_access_info`** — requires the user's own email + app token (the app token is only visible while the user is logged into LabArchives UI). Not feasible for an admin to collect at scale.
- **OAuth flow** — requires user interaction and a redirect URI, not available in a non-interactive backend.
- **Admin user-lookup by email** — the LabArchives API does **not** expose an endpoint for this.

## Potential Future Approaches

### Option A: Build per-user UID registration with manual admin step
- Admin asks each researcher to generate a LabArchives app token once and share it briefly
- Admin runs: `nexuslims labarchives register-user --username jsmith --email jsmith@institution.edu --la-password <token>`
- CLI calls `users/user_access_info` to resolve the uid and stores it via `store_external_id()`
- From then on, records for `jsmith` go into their own notebook automatically
- App token can be revoked immediately after

**Effort:** Medium — CLI command + `LabArchivesClient` uid-per-call support + exporter lookup logic
**Ops burden:** One-time per-user setup

### Option B: Notebook sharing via `notebooks/add_user_to_notebook`
- Admin creates and owns all notebooks (current design)
- After creation, admin calls `notebooks/add_user_to_notebook` to grant the researcher access to their own folder
- Researcher can then view/edit their records in LabArchives
- Ownership stays with admin (doesn't solve the scaling concern), but researchers have access

**Effort:** Low — add one API call per page creation in `_find_or_create_page()`
**Ops burden:** Requires knowing the researcher's email (available from NEMO) or LabArchives username
**Note:** Check whether `add_user_to_notebook` accepts an email address or requires a uid; if email works, this is automatable without per-user registration

### Option C: Multiple admin accounts (spread the load)
- Create one admin LabArchives account per instrument, group, or year
- Each account has its own `NX_LABARCHIVES_*` credentials in config
- Configure per-instrument credential sets (requires config system extension)
- No per-user registration problem; load is distributed

**Effort:** Medium — config system needs to support per-instrument LA credentials
**Ops burden:** Managing multiple LabArchives admin accounts

### Option D: Accept limitation, revisit at scale
- Document the single-admin limitation
- Monitor notebook count; if a single admin account accumulates >500 notebooks, create a second admin and split
- No code changes needed

---

## Recommended Next Steps (Priority Order)

1. **Investigate Option B first** — check if `notebooks/add_user_to_notebook` accepts an email address. If so, it's a low-effort win: researchers get access to their records without any special registration. The API endpoint exists; just needs verification of the parameter format.

2. **Implement Option A** when the deployment grows — the `ExternalUserIdentifier` table is already there. When an institution has enough users to make registration worthwhile, add the CLI command and per-call uid support to `LabArchivesClient`.

3. **Option C** is the nuclear option if LabArchives performance actually degrades.

## API Reference

- `GET notebooks/tree_level` — list children at a tree level (signing method: `tree_level`)
- `POST notebooks/insert_node` — create folder or page (signing method: `insert_node`)
- `POST notebooks/add_user_to_notebook` — share notebook with a user (signing method: `add_user_to_notebook`) — **investigate parameter format**
- `GET users/user_access_info` — exchange email + app token for uid (signing method: `user_access_info`)
- Signing: `HMAC-SHA-512(ACCESS_PASSWORD, AKID + method_name_only + expires_ms)`
