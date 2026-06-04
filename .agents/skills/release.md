# NexusLIMS Release Workflow

This shared workflow describes how an agent should prepare and run a NexusLIMS release. Claude, Codex, and other repo agents should use this file as the source of truth for release behavior.

## Invocation Arguments

The release command may receive:

- An optional version, such as `2.5.0`
- Optional release script flags, such as `--dry-run`, `--no-push`, or `--yes`

Pass supported flags through to `./scripts/release.sh` when the release script is run.

## Pre-flight: Branch Guard

Before doing anything else, run:

```bash
git branch --show-current
```

If the result is not `main`, stop immediately and tell the user:

```text
Cannot release from branch `<branch>`. Releases must be cut from `main`. Merge all feature branches into main first, then run the release workflow again.
```

Do not proceed past this point until the branch is `main`.

## Current State

Gather the following information before drafting release notes:

1. Current version: read `pyproject.toml` and extract the `version = "..."` line.
2. Current branch: run `git branch --show-current`; this should already have been confirmed as `main`.
3. Pending changelog fragments: find all `docs/changes/*.md` files, excluding `README.md`, then read each one and display its filename and contents.
4. Changelog draft: run `uv run towncrier build --version=PREVIEW --draft` to preview the assembled changelog.

Gather all four pieces of information before moving on.

## Step 1: Identify Breaking Changes

Scan the fragment contents. Look for:

- Fragments with `.removal.md` in the filename
- Any text mentioning "Breaking change", removed commands, renamed config keys, changed CLI behavior, or API removals

For each breaking change, draft a dedicated Upgrade Instructions subsection covering:

- What was removed or changed
- Exactly what the user must do, including specific commands to run, config keys to rename, or scripts to update
- Any migration path or backwards-compatible shim, if one exists

If there are no breaking changes, state that explicitly and skip the Upgrade Instructions section.

## Step 2: Draft Release Notes

Write complete release notes for the version using this structure. Do not hard wrap long lines; let GitHub's markdown formatter wrap paragraphs naturally.

````markdown
## Welcome to version X.Y.Z of NexusLIMS!

### Highlights
(2-4 sentence plain-English summary of the most important changes)

(Include the following text in every release:) As always, if you are looking for assistance with configuration or deployment of NexusLIMS, please contact [Datasophos](https://datasophos.co/#contact) to discuss your needs!

### Upgrade Instructions
(Only include this section if there are breaking changes)

#### [Title of breaking change]
[Concrete steps users must take, including commands, file edits, etc.]

### New Features
(User-focused bullet list of features and enhancements. Reference the pull request in the header line. Use a format such as the following:

**Feature title** ([#00](https://github.com/datasophos/NexusLIMS/pull/00))
  - Feature detail 1
  - Feature detail 2
  - Feature detail 3
  - Feature detail 4
)

### Bug Fixes
(Bullet list of bug fixes, if any; include relevant PR link)

### Documentation Improvements
(Doc fragments, condensed, if any; include relevant PR link)

### Internal / Miscellaneous
(Misc fragments, one line each, if any; include relevant PR link)

### Installation

```bash
# if upgrading an existing uv tool install, run:
uv tool upgrade nexuslims

# for a new installation:
uv tool install nexuslims==x.y.z

# or
pip install nexuslims==x.y.z

# or, if installed from source:
git fetch
git checkout vx.y.z
uv sync
```

### Full changelog
(include the GitHub changelog link between this tag and the last one, such as: https://github.com/datasophos/NexusLIMS/compare/v2.4.0...v2.4.1)
````

Base the content strictly on the changelog fragments. Do not invent changes that are not in the fragments.

## Step 3: Confirm the Version Number

If the user supplied a version as an argument, use it.

Otherwise, suggest stripping `.dev0` from the current version and ask the user to confirm or change it. Remind them:

- Major bump: for breaking changes, especially removal fragments that require user action
- Minor bump: for new features with no breaking changes
- Patch bump: for bug-fix-only releases

## Step 4: User Review

Present the drafted release notes and the version number. Ask the user to:

1. Review and approve the release notes, especially the Upgrade Instructions if any
2. Confirm the version is correct

Do not proceed to Step 5 until the user explicitly approves.

## Step 5: Write Release Notes File and Run the Release Script

Once the user approves:

1. Write the approved release notes to `RELEASE_NOTES.md` at the project root. This file will be committed with the release and used by the GitHub Actions workflow to populate the GitHub Release body.
2. Run the release script:

```bash
./scripts/release.sh <VERSION> [flags]
```

Pass through any flags the user provided, such as `--dry-run`, `--no-push`, or `--yes`. If neither `--yes` nor `--dry-run` was provided, the script will prompt interactively; that is expected.

Default behavior: push to remote unless the user passed `--no-push`.

Dry-run behavior: if `--dry-run` was passed, skip writing `RELEASE_NOTES.md`; no files should be touched in dry-run mode.

## Step 6: Post-Release Checklist

After the script completes:

- The GitHub Actions workflow will pick up `RELEASE_NOTES.md` from the tag commit and use it as the GitHub Release body automatically
- Remind the user to check the workflow at https://github.com/datasophos/NexusLIMS/actions
- Verify the package appears on PyPI
- Confirm versioned docs are deployed at https://datasophos.github.io/NexusLIMS/

## Quick Reference: Release Script Options

```text
./scripts/release.sh VERSION [OPTIONS]

  -d, --dry-run    Preview only; no files changed, no commits, no tags
  -y, --yes        Skip confirmation prompts
  --no-push        Create commits and tag locally but do not push to remote
  --draft          Show towncrier draft changelog and exit
```
