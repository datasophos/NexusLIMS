#!/usr/bin/env python3
"""Check that version in pyproject.toml is not a previously released version."""

# ruff: noqa: T201, S607

import subprocess
import sys
from pathlib import Path


def get_released_versions():
    """Get all released versions from git tags."""
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "v*.*.*"], capture_output=True, text=True, check=True
        )
        # Strip 'v' prefix from tags to get versions
        return {tag.lstrip("v") for tag in result.stdout.strip().split("\n") if tag}
    except subprocess.CalledProcessError:
        return set()


def get_current_version():
    """Extract version from pyproject.toml."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        print("Error: pyproject.toml not found")
        return None

    with pyproject.open() as f:
        for line in f:
            if line.startswith('version = "'):
                # Extract version from: version = "2.1.2.dev0"
                return line.split('"')[1]

    print("Error: Could not find version in pyproject.toml")
    return None


def increment_version(version):
    """Increment patch version (2.1.1 -> 2.1.2)."""
    parts = version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def update_version_in_file(new_version):
    """Update version in pyproject.toml."""
    pyproject = Path("pyproject.toml")
    with pyproject.open() as f:
        content = f.read()

    # Replace version line
    updated_content = ""
    for line in content.split("\n"):
        if line.startswith('version = "'):
            updated_content += f'version = "{new_version}"\n'
        else:
            updated_content += line + "\n"

    # Remove the extra newline at the end that we added
    updated_content = updated_content.rstrip("\n") + "\n"

    with pyproject.open("w") as f:
        f.write(updated_content)


def main():
    """Check that the current version hasn't been released."""
    current_version = get_current_version()
    if not current_version:
        return 1

    released_versions = get_released_versions()

    # Check if current version matches a released version
    # (ignore dev/alpha/rc suffixes for comparison)
    current_base = current_version.split(".dev")[0].split("a")[0].split("rc")[0]

    if current_base in released_versions:
        next_version = increment_version(current_base)
        dev_version = f"{next_version}.dev0"
        print(
            f"⚠️  Version '{current_base}' has already been released.\n"
            f"   Current version in pyproject.toml: {current_version}\n"
            f"   Automatically bumping to: {dev_version}"
        )
        update_version_in_file(dev_version)
        return 1

    print(f"✅ Version check passed: {current_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
