# Ship Alembic Migrations Inside the Installed Package

## Status: TODO

## Overview

The `migrations/` directory currently lives at the repository root and is not
included in the wheel built by hatchling (`packages = ["nexusLIMS"]` in
`pyproject.toml`).  This means users who install via `pip install nexusLIMS` or
`uv tool install nexusLIMS` have no migrations directory at all, and no
`pyproject.toml` for Alembic to resolve `script_location` against.  Running
`alembic upgrade head` after such an install simply fails.

Two things need to happen:

1. The migration scripts need to be **inside the package** so they are included
   in the wheel and installed alongside the rest of the code.
2. A **CLI entry point** (`nexuslims-migrate`) needs to exist so users never
   have to think about `alembic` directly — it sets up the correct paths
   automatically regardless of how the package was installed.

## Current State

| File / setting | What it does today |
|---|---|
| `pyproject.toml` `[tool.hatch.build.targets.wheel]` | `packages = ["nexusLIMS"]` — only the `nexusLIMS/` tree goes in the wheel |
| `pyproject.toml` `[tool.alembic]` | `script_location = "migrations"` — relative to repo root / cwd |
| `migrations/env.py` | Reads `NX_DB_PATH` from `nexusLIMS.config.settings`; no path self-awareness |
| `migrations/versions/` | Three migrations: baseline (`57f0798d`), upload_log (`0ea2bc3d`), check constraints (`2e1408e5`) |
| `nexusLIMS/cli/process_records.py` | Existing click-based entry point; lazy-imports heavy modules; pattern to follow |
| `pyproject.toml` `[project.scripts]` | Single entry point: `nexuslims-process-records` |

### Migration revision chain (unchanged by this work)

```
57f0798d  (baseline, no-op)
    └── 0ea2bc3d  (upload_log table + BUILT_NOT_EXPORTED)
            └── 2e1408e5  (CHECK constraints on session_log)
```

## Implementation Plan

### Phase 1 — Move migrations into the package

**Goal:** `migrations/` becomes `nexusLIMS/migrations/` so hatchling picks it up
automatically (it is already under the `nexusLIMS` package tree).

**Files touched:**

* `nexusLIMS/migrations/` — new location (move from repo root)
* `nexusLIMS/migrations/__init__.py` — new, empty, makes it a proper package
* `nexusLIMS/migrations/versions/__init__.py` — already exists, keep as-is
* `pyproject.toml` — update `[tool.alembic] script_location`

**Steps:**

1. `git mv migrations nexusLIMS/migrations`
2. Add an empty `nexusLIMS/migrations/__init__.py` (the `versions/` subdir
   already has one).
3. In `pyproject.toml`, change:
   ```toml
   [tool.alembic]
   script_location = "nexusLIMS/migrations"
   ```
   This keeps `uv run alembic` working from the repo root during development.

### Phase 2 — Make `env.py` self-locating

**Goal:** `env.py` must find itself whether it is in the source tree or inside a
`site-packages` install.  The only reliable anchor is `__file__`.

**File:** `nexusLIMS/migrations/env.py`

**Changes:**

Replace the implicit assumption that Alembic was invoked from the repo root
with an explicit derivation of the script directory from `__file__`:

```python
# At the top of env.py, after the existing imports:
from pathlib import Path

# Derive the migrations directory from this file's own location.
# Works regardless of whether the package is installed or run from source.
_MIGRATIONS_DIR = Path(__file__).resolve().parent
```

Nothing else in `env.py` needs to change — Alembic already receives
`script_location` from the config and uses `env.py` from that directory.  The
`__file__`-based derivation is only needed by the CLI entry point (Phase 3)
to hand Alembic the right path programmatically.

### Phase 3 — Add the `nexuslims-migrate` CLI entry point

**Goal:** A single command that wraps Alembic, sets up the correct
`script_location` automatically, and passes all remaining arguments through.
Users run `nexuslims-migrate upgrade head` the same way they would run
`alembic upgrade head`, but it just works after a pip/uv install.

**New file:** `nexusLIMS/cli/migrate.py`

```python
"""
CLI wrapper around Alembic for NexusLIMS database migrations.

Automatically locates the migrations directory inside the installed package
so that migrations work correctly regardless of install method (pip, uv tool
install, editable installs, etc.).

Usage
-----

```bash
nexuslims-migrate upgrade head        # apply all pending migrations
nexuslims-migrate downgrade -1        # roll back one migration
nexuslims-migrate current             # show current revision
nexuslims-migrate history             # show migration history
nexuslims-migrate revision --autogenerate -m "description"  # (dev only)
```

All standard Alembic sub-commands and flags are supported.
"""

import sys
from importlib.resources import files
from pathlib import Path

from alembic.config import Config
from alembic.scripts import ScriptDirectory  # noqa: F401 — ensures alembic.ini not required
from alembic import command as alembic_command


def _get_migrations_dir() -> Path:
    """Locate the migrations directory inside the installed package.

    Uses importlib.resources (Python 3.9+) to find nexusLIMS.migrations
    regardless of whether the package is installed normally, as an editable
    install, or run from source.

    Returns
    -------
    pathlib.Path
        Absolute path to the nexusLIMS/migrations/ directory.
    """
    return Path(str(files("nexusLIMS.migrations")))


def main() -> None:
    """Entry point for nexuslims-migrate.

    Constructs an Alembic Config pointed at the package-internal migrations
    directory, then delegates to Alembic's CLI dispatcher with whatever
    arguments the user passed.
    """
    migrations_dir = _get_migrations_dir()

    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))

    # Alembic's command-line tool parses sys.argv[1:] when you call
    # alembic.config.CommandLine().run().  We replace argv[0] so that
    # help text says "nexuslims-migrate" instead of the script path.
    sys.argv[0] = "nexuslims-migrate"

    from alembic.config import CommandLine  # noqa: PLC0415
    program = CommandLine()
    program.config = cfg
    program.run(sys.argv[1:])
```

**Register the entry point in `pyproject.toml`:**

```toml
[project.scripts]
nexuslims-process-records = "nexusLIMS.cli.process_records:main"
nexuslims-migrate        = "nexusLIMS.cli.migrate:main"
```

### Phase 4 — Verify and test

1. **Development workflow (repo checkout):**
   - `uv run nexuslims-migrate current` should print the current revision.
   - `uv run nexuslims-migrate upgrade head` should apply any pending migrations.
   - `uv run alembic upgrade head` should still work (for devs who prefer it).
   - `uv run alembic revision --autogenerate -m "..."` should still work from
     the repo root and put new migrations in `nexusLIMS/migrations/versions/`.

2. **Installed-package workflow (simulate what a user sees):**
   - Build the wheel: `uv build`
   - Install it in a fresh venv: `uv pip install dist/nexusLIMS-*.whl`
   - Confirm `nexuslims-migrate --help` prints usage.
   - Confirm `nexuslims-migrate current` works against a real or empty DB
     (set `NX_DB_PATH` first).
   - Confirm `nexuslims-migrate upgrade head` applies migrations to a fresh DB.

3. **Unit test:** Add a test in `tests/unit/` that imports
   `nexusLIMS.cli.migrate` and asserts `_get_migrations_dir()` returns a
   directory that contains `env.py` and the `versions/` subdirectory.

4. **Ruff / lint:** Run `./scripts/run_lint.sh` — the new file must pass with
   zero issues.

5. **Update `ruff` exclude if needed:** `migrations/env.py` currently has a
   `# ruff: noqa: INP001` pragma because it was outside any package.  After the
   move it *is* inside a package, so `INP001` will no longer fire.  Remove the
   pragma (or keep it harmlessly) and confirm lint is clean.

## What this does NOT change

* The migration revision chain and the content of individual migration files.
  Those are unchanged; only their on-disk location moves.
* The `script.py.mako` template used when generating new migrations.
* How `env.py` connects to the database — it still reads `NX_DB_PATH` via
  `nexusLIMS.config.settings`.
* The `migrations/README.md` file (moved along with everything else).
* Any existing user databases.  `upgrade head` is idempotent; if the DB is
  already at `head` it does nothing.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `uv run alembic` breaks for devs after the move | `script_location` in `pyproject.toml` is updated to the new relative path; tested in Phase 4 step 1 |
| `importlib.resources` returns a non-existent or temporary path for namespace packages | `nexusLIMS.migrations` is a regular package (has `__init__.py`); `files()` returns the real directory |
| New migrations generated during development land in the wrong place | `script_location` points to the new location; `alembic revision` follows it |
| Users on older installs have `alembic` stamped against the old path | Alembic tracks revisions by revision ID in the `alembic_version` table, not by file path.  Moving the files has no effect on an existing stamped DB |
