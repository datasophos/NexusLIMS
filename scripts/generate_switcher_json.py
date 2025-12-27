#!/usr/bin/env python3
# ruff: noqa: S607, T201
"""
Auto-generate switcher.json for PyData Sphinx Theme version switcher.

This script lists all deployed documentation versions in the gh-pages branch
and generates docs/_static/switcher.json with correct URLs for each version.

The switcher will show:
- "v2.1.0 (stable)" for the latest release (in stable/ directory)
- "abc1234 (latest)" for the main branch (in latest/ directory)
- "v2.0.0", "v1.9.0", etc. for older releases

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


def get_current_dev_version():
    """
    Get the current development version from pyproject.toml.

    Returns the version string (e.g., "2.1.2.dev0") if found, otherwise None.
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    try:
        with pyproject_path.open() as f:
            for line in f:
                if line.startswith('version = "'):
                    return line.split('"')[1]
    except Exception as e:
        print(
            f"Warning: Could not read version from {pyproject_path}: {e}",
            file=sys.stderr,
        )
    return None


def get_short_commit_hash():
    """Get the short commit hash of the current HEAD."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def parse_version(version_str):
    """
    Parse a version string into a tuple of integers for comparison.

    Parameters
    ----------
    version_str : str
        Version string (e.g., "2.1.0").

    Returns
    -------
    tuple
        Tuple of integers (e.g., (2, 1, 0)).
    """
    return tuple(map(int, version_str.split(".")))


def filter_latest_patch_versions(version_dirs):
    """
    Filter version directories to only include the latest patch for each minor version.

    For example, if we have ["2.1.0", "2.1.1", "2.1.2", "2.0.0", "2.0.1"],
    return ["2.1.2", "2.0.1"].

    Parameters
    ----------
    version_dirs : list
        List of version directory names (e.g., ["2.1.0", "2.1.1", "2.0.0"]).

    Returns
    -------
    list
        Filtered list with only the latest patch version for each minor version.
    """
    # Group versions by major.minor
    from collections import defaultdict  # noqa: PLC0415

    version_groups = defaultdict(list)
    for v in version_dirs:
        parts = v.split(".")
        if len(parts) >= 2:  # noqa: PLR2004
            minor_key = f"{parts[0]}.{parts[1]}"
            version_groups[minor_key].append(v)

    # Keep only the latest patch version for each minor version
    latest_versions = []
    for _, versions in version_groups.items():
        # Sort by full version tuple and take the last (highest)
        versions_sorted = sorted(versions, key=parse_version)
        latest_versions.append(versions_sorted[-1])

    # Sort final list by version in descending order
    return sorted(latest_versions, key=parse_version, reverse=True)


def get_gh_pages_dirs():
    """
    List top-level directories in the gh-pages branch.

    Returns a list of directory names (e.g., ['latest', 'stable', '2.0', ...]).
    """
    # Fetch latest gh-pages branch if not present
    try:
        subprocess.run(
            ["git", "fetch", "origin", "gh-pages"],
            check=True,
            capture_output=True,
        )
    except Exception as e:
        print(f"Warning: Could not fetch gh-pages branch: {e}", file=sys.stderr)

    # List directories in gh-pages branch root
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "-d", "origin/gh-pages"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [d.strip() for d in result.stdout.splitlines()]


def get_latest_release_version():
    """
    Get the version string of the latest release tag.

    Returns
    -------
    str or None
        Version string (e.g., "2.1.0") or None if no tags found.
    """
    try:
        # Get all tags sorted by version
        result = subprocess.run(
            ["git", "tag", "-l", "v*", "--sort=-version:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = result.stdout.strip().split("\n")
        if tags and tags[0]:
            # Remove 'v' prefix
            return tags[0].lstrip("v")
    except Exception as e:
        print(f"Warning: Could not fetch latest release tag: {e}", file=sys.stderr)
    return None


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

    # Add versioned releases (e.g., 2.1.0, 2.0.1, etc.)
    # Filter to only show latest patch version for each minor release
    version_dirs = [d for d in dirs if re.match(r"^\d+\.\d+\.\d+$", d)]
    filtered_versions = filter_latest_patch_versions(version_dirs)

    # Add stable link at the top (if it exists)
    if "stable" in dirs:
        # Get the version number of the latest release
        latest_version = filtered_versions[0] if filtered_versions else "stable"
        entries.append(
            {
                "name": f"v{latest_version} (stable)",
                "version": "stable",
                "url": f"{BASE_URL}/stable/",
                "preferred": True,
            }
        )

    for v in filtered_versions:
        # Add numbered version entries without marking any as stable/preferred
        # since we now have a dedicated stable/ directory
        entries.append(
            {
                "name": f"v{v}",
                "version": v,
                "url": f"{BASE_URL}/{v}/",
            }
        )

    # Add current PR first (if in PR context)
    if current_pr_num:
        current_pr_name = f"pr-{current_pr_num}"
        entries.insert(
            0,
            {
                "name": f"PR #{current_pr_num} (current)",
                "version": current_pr_name,
                "url": f"{BASE_URL}/{current_pr_name}/",
                "preferred": True,
            },
        )

    # Add other PR previews from gh-pages
    pr_dirs = [d for d in dirs if d.startswith("pr-")]
    for d in sorted(pr_dirs, reverse=True):  # Most recent PRs first
        pr_num = d.split("-")[1]
        # Skip current PR if already added
        if current_pr_num and pr_num == current_pr_num:
            continue
        entries.append(
            {"name": f"PR #{pr_num}", "version": d, "url": f"{BASE_URL}/{d}/"}
        )

    # Add latest dev build at the top (if it exists)
    if "latest" in dirs:
        dev_version = get_current_dev_version()
        label = f"v{dev_version}" if dev_version else f"({get_short_commit_hash()})"
        entries.insert(
            0,
            {
                "name": f"{label} (latest)",
                "version": "dev",
                "url": f"{BASE_URL}/latest/",
            },
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
        # First deployment case: no versions exist yet
        print(
            "No deployed documentation versions found in gh-pages branch.",
            file=sys.stderr,
        )
        print(
            "This appears to be the first deployment. Creating minimal switcher.json."
        )
        # Create minimal switcher with just latest
        commit_hash = get_short_commit_hash()
        switcher = [
            {
                "name": f"{commit_hash} (latest)",
                "version": "dev",
                "url": f"{BASE_URL}/latest/",
                "preferred": True,
            },
            {
                "name": "Upstream NIST docs",
                "version": "upstream",
                "url": "https://pages.nist.gov/NexusLIMS/",
            },
        ]
    else:
        if not dirs and current_pr:
            print(
                "No deployed versions found, generating switcher for current PR only."
            )
        switcher = build_switcher_json(dirs, current_pr_num=current_pr)

    static_path = Path("docs/_static")
    static_path.mkdir(exist_ok=True, parents=True)
    out_path = static_path / "switcher.json"
    with out_path.open("w") as f:
        json.dump(switcher, f, indent=2)
    print(f"Generated {out_path} with {len(switcher)} entries.")
    print("\nSwitcher content:")
    for entry in switcher:
        preferred = " [PREFERRED]" if entry.get("preferred") else ""
        print(f"  - {entry['name']} (version={entry['version']}){preferred}")


if __name__ == "__main__":
    main()
