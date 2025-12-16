#!/usr/bin/env python3
# ruff: noqa: T201
"""Configure NEMO settings to include periodic table plugin.

This script modifies the splash_pad_settings.py file to add the
NEMO_periodic_table_question plugin to INSTALLED_APPS.
"""

import sys
from pathlib import Path


def configure_periodic_table_plugin():
    """Add periodic table plugin to INSTALLED_APPS in settings."""
    settings_file = Path("/nemo/splash_pad_settings.py")

    try:
        content = settings_file.read_text()

        # Check if already configured
        if "NEMO_periodic_table_question" in content:
            print("Periodic table plugin already configured in settings")
            return

        # Find INSTALLED_APPS and add the plugin
        if "INSTALLED_APPS" in content:
            # Add after INSTALLED_APPS definition
            # We'll add it right after the INSTALLED_APPS = [ line
            lines = content.split("\n")
            new_lines = []
            found_installed_apps = False

            for line in lines:
                new_lines.append(line)
                # Look for INSTALLED_APPS = [ or INSTALLED_APPS=[
                if (
                    not found_installed_apps
                    and "INSTALLED_APPS" in line
                    and "[" in line
                ):
                    # Add the plugin on the next line
                    found_installed_apps = True
                    indent = "    "  # Standard Django indent
                    new_lines.append(f"{indent}'NEMO_periodic_table_question',")

            if found_installed_apps:
                settings_file.write_text("\n".join(new_lines))
                print("Successfully added periodic table plugin to INSTALLED_APPS")
            else:
                print("WARNING: Could not find INSTALLED_APPS in settings file")
        else:
            print("WARNING: INSTALLED_APPS not found in settings")

    except FileNotFoundError:
        print(f"ERROR: Settings file not found: {settings_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to configure settings: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    configure_periodic_table_plugin()
