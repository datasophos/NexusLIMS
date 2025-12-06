#!/usr/bin/env python3
# ruff: noqa: S607, T201
"""
Auto-generate switcher.json for PyData Sphinx Theme version switcher.

This script lists all deployed documentation versions in the gh-pages branch
and generates docs/_static/switcher.json with correct URLs for each version.

Intended to be run in CI before copying docs/_static/switcher.json to the build.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = "datasophos/NexusLIMS"
BASE_URL = "https://datasophos.github.io/NexusLIMS"


def get_current_pr_number():
    """
    Detect if running in a PR context and return the PR number.

    Checks GitHub Actions environment variables:
    - GITHUB_EVENT_NAME: Should be 'pull_request' or 'pull_request_target'
    - GITHUB_REF: Contains PR number for pull_request events (refs/pull/123/merge)

    Returns PR number as string or None if not in PR context.
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    github_ref = os.environ.get("GITHUB_REF", "")

    # Check if we're in a pull request event
    if event_name in ("pull_request", "pull_request_target"):
        # Extract PR number from GITHUB_REF (format: refs/pull/123/merge)
        match = re.match(r"refs/pull/(\d+)/", github_ref)
        if match:
            return match.group(1)

    return None


def get_gh_pages_dirs():
    """
    List top-level directories in the gh-pages branch.

    Returns a list of directory names (e.g., ['latest', 'stable', ...]).
    Excludes pr-X branches.
    """
    # Fetch latest gh-pages branch if not present
    try:
        subprocess.run(["git", "fetch", "origin", "gh-pages"], check=True)
    except Exception as e:
        print(f"Warning: Could not fetch gh-pages branch: {e}", file=sys.stderr)

    # List directories in gh-pages branch root
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "origin/gh-pages"],
        capture_output=True,
        text=True,
        check=True,
    )
    dirs = [d.strip() for d in result.stdout.splitlines()]
    # Only keep directories that match expected patterns
    return [d for d in dirs if d in ("latest", "stable") or re.match(r"^\d+\.\d+", d)]


def build_switcher_json(dirs, current_pr_num=None):
    """
    Build the switcher.json structure from a list of version directories.

    Parameters
    ----------
    dirs : list
        List of version directory names from gh-pages branch.
    current_pr_num : str, optional
        Current PR number if building in PR context.

    Returns
    -------
    list
        List of version entries for switcher.json.
    """
    entries = []
    # Add stable and latest first, if present
    for v in ["stable", "latest"]:
        if v in dirs:
            entries.append(
                {
                    "name": v.capitalize(),
                    "version": v,
                    "url": f"{BASE_URL}/{v}/",
                    "preferred": v == "stable",
                }
            )

    # Add current PR first (if in PR context)
    if current_pr_num:
        current_pr_name = f"pr-{current_pr_num}"
        entries.append(
            {
                "name": f"PR #{current_pr_num} (current)",
                "version": current_pr_name,
                "url": f"{BASE_URL}/{current_pr_name}/",
                "preferred": True,
            }
        )

    # Add other PR previews from gh-pages
    for d in dirs:
        if d.startswith("pr-"):
            pr_num = d.split("-")[1]
            # Skip current PR if already added
            if current_pr_num and pr_num == current_pr_num:
                continue
            entries.append(
                {"name": f"PR #{pr_num}", "version": d, "url": f"{BASE_URL}/{d}/"}
            )

    # Add link to upstream NIST project documentation
    entries.append(
        {
            "name": "Upstream NIST docs",
            "version": "upstream",
            "url": "https://pages.nist.gov/NexusLIMS/",
        }
    )

    return entries


def main():
    """Generate the switcher.json file for the documentation website."""
    # Check if we're building in a PR context
    current_pr = get_current_pr_number()
    if current_pr:
        print(f"Building in PR context: PR #{current_pr}")

    dirs = get_gh_pages_dirs()
    if not dirs and not current_pr:
        # Only error if we have no dirs AND we're not in a PR context
        print(
            "No deployed documentation versions found in gh-pages branch.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not dirs:
        print("No deployed versions found, generating switcher for current PR only.")

    switcher = build_switcher_json(dirs, current_pr_num=current_pr)
    static_path = Path("docs/_static")
    static_path.mkdir(exist_ok=True, parents=True)
    out_path = static_path / "switcher.json"
    with out_path.open("w") as f:
        json.dump(switcher, f, indent=2)
    print(f"Generated {out_path} with {len(switcher)} entries.")


if __name__ == "__main__":
    main()
