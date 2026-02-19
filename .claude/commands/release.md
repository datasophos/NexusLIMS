---
allowed-tools: Bash(git:*), Bash(uv:*), Bash(./scripts/release.sh:*)
argument-hint: [version] [--dry-run] [--no-push]
description: Prepare a NexusLIMS release with changelog review and upgrade instructions
---

# NexusLIMS Release Preparation

## Current State

Use your tools to gather the following information before proceeding:

1. **Current version:** Read `pyproject.toml` and extract the `version = "..."` line.
2. **Current branch:** Run `git branch --show-current`.
3. **Pending changelog fragments:** Use Glob to find all `docs/changes/*.md` files (exclude `README.md`), then Read each one and display its filename and contents.
4. **Changelog draft:** Run `uv run towncrier build --version=PREVIEW --draft` to preview the assembled changelog.

Gather all four pieces of information before moving on to Step 1.

---

## Instructions

The user wants to cut a release. Work through the following steps in order.

### Step 1: Identify Breaking Changes

Scan the fragment contents you gathered. Look for:
- Fragments with `.removal.md` in the filename
- Any text mentioning "Breaking change", removed commands, renamed config keys, changed CLI behavior, or API removals

For **each breaking change**, draft a dedicated **Upgrade Instructions** subsection covering:
- What was removed or changed
- Exactly what the user must do (specific commands to run, config keys to rename, scripts to update)
- Any migration path or backwards-compatible shim, if one exists

If there are no breaking changes, state that explicitly and skip the Upgrade Instructions section.

### Step 2: Draft Release Notes

Write the complete release notes for this version using this structure:

```markdown
## vX.Y.Z (YYYY-MM-DD)

### Highlights
(2–4 sentence plain-English summary of the most important changes)

### Upgrade Instructions
(Only include this section if there are breaking changes)

#### [Title of breaking change]
[Concrete steps users must take — commands, file edits, etc.]

### What's New
(User-focused bullet list of features and enhancements)

### Bug Fixes
(Bullet list of bug fixes, if any)

### Documentation Improvements
(Doc fragments, condensed, if any)

### Internal / Miscellaneous
(Misc fragments, one line each, if any)
```

Base the content strictly on the fragments shown above — do not invent changes that are not in the fragments.

### Step 3: Confirm the Version Number

If the user supplied a version as an argument (e.g., `/release 2.5.0`), use it.

Otherwise, suggest stripping `.dev0` from the current version and ask the user to confirm or change it. Remind them:
- **Major bump** — for breaking changes (removal fragments that require user action)
- **Minor bump** — for new features with no breaking changes
- **Patch bump** — for bug-fix-only releases

### Step 4: User Review

Present the drafted release notes and the version number. Ask the user to:
1. Review and approve the release notes (especially the Upgrade Instructions if any)
2. Confirm the version is correct

Do not proceed to Step 5 until the user explicitly approves.

### Step 5: Write Release Notes File and Run the Release Script

Once the user approves:

1. Write the approved release notes to `RELEASE_NOTES.md` at the project root. This file will be committed with the release and used by the GitHub Actions workflow to populate the GitHub Release body.

2. Run the release script:

```bash
./scripts/release.sh <VERSION> [flags]
```

Pass through any flags the user provided (e.g., `--dry-run`, `--no-push`). If neither `--yes` nor `--dry-run` was provided, the script will prompt interactively — that is expected.

**Default:** push to remote unless the user passed `--no-push`.

**Dry-run:** If `--dry-run` was passed, skip writing `RELEASE_NOTES.md` (no files should be touched in dry-run mode).

### Step 6: Post-Release Checklist

After the script completes:

- The GitHub Actions workflow will pick up `RELEASE_NOTES.md` from the tag commit and use it as the GitHub Release body automatically
- Remind the user to check the workflow: https://github.com/datasophos/NexusLIMS/actions
- Verify the package appears on PyPI
- Confirm versioned docs are deployed at https://datasophos.github.io/NexusLIMS/

---

## Quick Reference: Release Script Options

```
./scripts/release.sh VERSION [OPTIONS]

  -d, --dry-run    Preview only — no files changed, no commits, no tags
  -y, --yes        Skip confirmation prompts
  --no-push        Create commits and tag locally but don't push to remote
  --draft          Show towncrier draft changelog and exit
```
