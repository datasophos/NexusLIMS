---
allowed-tools: Read, Glob, Write, Bash(git:*), Bash(uv:*), Bash(./scripts/release.sh:*)
argument-hint: [version] [--dry-run] [--no-push]
description: Prepare a NexusLIMS release with changelog review and upgrade instructions
---

# NexusLIMS Release Preparation

Follow the shared release workflow in `.agents/skills/release.md`.

Treat any arguments passed to this command as the workflow's invocation arguments.
