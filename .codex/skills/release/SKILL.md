---
name: release
description: Prepare and run a NexusLIMS release using the shared repository release workflow, including changelog review, release notes drafting, version confirmation, and the release script.
---

# NexusLIMS Release

Use this skill when the user asks to prepare, preview, dry-run, or cut a NexusLIMS release.

Follow the shared workflow in `../../../.agents/skills/release.md`.

Treat any version or flags provided by the user, such as `2.5.0`, `--dry-run`, `--no-push`, or `--yes`, as the shared workflow's invocation arguments.
