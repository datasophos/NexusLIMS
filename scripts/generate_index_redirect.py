#!/usr/bin/env python3
# ruff: noqa: S607, T201
"""
Generate root index.html redirect to the latest stable documentation version.

This script determines the latest stable version from git tags and creates
an index.html file that redirects to that version's documentation directory.

For example, if the latest release is v2.1.0, it will create an index.html
that redirects to /NexusLIMS/2.1/ (using major.minor version).
"""

import subprocess
import sys
from pathlib import Path


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
        print(f"Error: Could not fetch latest release tag: {e}", file=sys.stderr)
    return None


def generate_index_html(target_version):
    """
    Generate index.html redirect to the target version directory.

    Parameters
    ----------
    target_version : str
        Target version for redirect (e.g., "2.1.0").

    Returns
    -------
    str
        HTML content for the redirect page.
    """
    return f"""<!doctype html>
<html>
    <head>
        <meta http-equiv="refresh" content="0; url={target_version}/" />
        <link rel="canonical" href="{target_version}/" />
        <title>Redirecting to NexusLIMS documentation</title>
    </head>
    <body>
        <p>Redirecting to <a href="{target_version}/">NexusLIMS
        v{target_version} documentation</a>...</p>
    </body>
</html>
"""


def main():
    """Generate root index.html redirect to latest stable version."""
    latest_version = get_latest_release_version()

    if not latest_version:
        print(
            "Error: No release tags found. Cannot generate index.html redirect.",
            file=sys.stderr,
        )
        sys.exit(1)

    html_content = generate_index_html(latest_version)

    output_path = Path("index.html")
    output_path.write_text(html_content)

    print(f"✅ Generated {output_path}")
    print(f"   Redirects to: {latest_version}/")


if __name__ == "__main__":
    main()
