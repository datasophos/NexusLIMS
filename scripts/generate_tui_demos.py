#!/usr/bin/env python3
# ruff: noqa: PLC0415, T201
"""Generate TUI demonstration videos and screenshots for documentation.

This script generates:
1. VHS recordings (animated GIFs) of TUI workflows (if VHS is installed)
2. SVG screenshots using Textual's Pilot API (always generated)

The generated media is used in the documentation to show users how to
interact with the instrument manager TUI.

VHS Installation
----------------
VHS is optional but recommended for full functionality:

    macOS:   brew install vhs
    Linux:   Download from https://github.com/charmbracelet/vhs/releases
    Windows: Download from https://github.com/charmbracelet/vhs/releases

If VHS is not installed, the script will still generate SVG screenshots
and warn about missing VHS, but will not fail.

Usage
-----
Run directly (generates both VHS recordings and SVG screenshots):

    $ python scripts/generate_tui_demos.py

Or via documentation build script:

    $ ./scripts/build_docs.sh

Skip demo generation for fast local builds:

    $ ./scripts/build_docs.sh --skip-tui-demos
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def check_vhs_installed() -> bool:
    """Check if VHS (Video Home Simulator) is installed.

    Returns
    -------
    bool
        True if VHS is installed and available in PATH, False otherwise.
    """
    return shutil.which("vhs") is not None


def setup_demo_database() -> Path:
    """Create a temporary demo database with sample instruments.

    Returns
    -------
    Path
        Path to the created demo database file.
    """
    from nexusLIMS.tui.demo_helpers import create_demo_database

    # Create temporary database
    db_path = Path(tempfile.gettempdir()) / "nexuslims_demo.db"

    # Remove if exists (ensure fresh data)
    if db_path.exists():
        db_path.unlink()

    # Create demo database
    create_demo_database(db_path)

    return db_path


def generate_vhs_recordings(demo_db_path: Path) -> None:
    """Generate VHS recordings from tape scripts.

    Runs each .tape script in docs/images/tui/tapes/ to generate
    corresponding GIF recordings in docs/images/tui/recordings/.

    Skips generation with a warning if VHS is not installed.

    Parameters
    ----------
    demo_db_path : Path
        Path to the demo database to use for recordings.
    """
    if not check_vhs_installed():
        print("! VHS not installed - skipping video recordings")
        print("  (Install VHS for full demo generation: brew install vhs)")
        return

    # Find all tape scripts
    repo_root = Path(__file__).parent.parent
    tapes_dir = repo_root / "docs" / "images" / "tui" / "tapes"
    recordings_dir = repo_root / "docs" / "images" / "tui" / "recordings"

    # Ensure recordings directory exists
    recordings_dir.mkdir(parents=True, exist_ok=True)

    if not tapes_dir.exists():
        print(f"! Tapes directory not found: {tapes_dir}")
        return

    tape_files = sorted(tapes_dir.glob("*.tape"))

    if not tape_files:
        print(f"! No tape scripts found in {tapes_dir}")
        return

    print(f"Generating {len(tape_files)} VHS recordings...")

    for tape_file in tape_files:
        print(f"  • {tape_file.name}...", end=" ", flush=True)
        try:
            # Run VHS with NX_DB_PATH set to demo database
            env = os.environ.copy()
            env["NX_DB_PATH"] = str(demo_db_path)

            subprocess.run(
                ["vhs", str(tape_file)],  # noqa: S607
                check=True,
                env=env,
            )
            print(f"✓ Created {tape_file}")
        except subprocess.CalledProcessError as e:
            print(f"✗\n    Error: VHS command failed with exit code {e.returncode}")
            # Don't fail the whole build on single recording error
            continue


def generate_svg_screenshots(demo_db_path: Path) -> None:
    """Generate SVG screenshots using Textual Pilot API.

    Creates static SVG screenshots of key TUI screens:
    - Main instrument list screen
    - Add instrument form
    - Help screen

    These provide fallback documentation when VHS recordings are not available.

    Parameters
    ----------
    demo_db_path : Path
        Path to the demo database to use for screenshots.
    """
    from nexusLIMS.tui.apps.instruments import InstrumentManagerApp

    print("Generating SVG screenshots...")

    try:
        # Determine output directory
        repo_root = Path(__file__).parent.parent
        screenshots_dir = repo_root / "docs" / "images" / "tui" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Generate screenshots using run_test with demo database
        app = InstrumentManagerApp(db_path=demo_db_path)

        async def capture_screenshots():
            """Async function to capture screenshots."""
            async with app.run_test(size=(120, 40)) as pilot:
                # Wait for app to fully load
                await pilot.pause(0.5)

                # Screenshot 1: Main screen
                main_screenshot = screenshots_dir / "main_screen.svg"
                app.save_screenshot(main_screenshot)
                print(f"  ✓ {main_screenshot.name}")

                # Screenshot 2: Help screen
                await pilot.press("question_mark")
                await pilot.pause(0.2)
                help_screenshot = screenshots_dir / "help_screen.svg"
                app.save_screenshot(help_screenshot)
                print(f"  ✓ {help_screenshot.name}")

                # Close help screen
                await pilot.press("escape")
                await pilot.pause(0.2)

                # Screenshot 3: Add form (trigger add action)
                await pilot.press("a")
                await pilot.pause(0.2)
                add_screenshot = screenshots_dir / "add_form.svg"
                app.save_screenshot(add_screenshot)
                print(f"  ✓ {add_screenshot.name}")

        # Run the async screenshot capture
        import asyncio

        asyncio.run(capture_screenshots())

    except Exception as e:
        print(f"✗ Failed to generate screenshots: {e}")
        raise


def main() -> int:
    """Generate TUI demos.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure).
    """
    # Check if demo generation should be skipped
    if os.environ.get("NX_DOCS_SKIP_TUI_DEMOS"):
        print("Skipping TUI demo generation (NX_DOCS_SKIP_TUI_DEMOS is set)")
        return 0

    print("=" * 60)
    print("Generating TUI Demonstrations")
    print("=" * 60)
    print()

    # Set up demo database
    print("Setting up demo database...")
    try:
        db_path = setup_demo_database()
        print(f"✓ Demo database created at {db_path}")
        print()
    except Exception as e:
        print(f"✗ Failed to create demo database: {e}")
        return 1

    # Generate VHS recordings (warns if VHS not installed, doesn't fail)
    try:
        generate_vhs_recordings(db_path)
        print()
    except Exception as e:
        print(f"! Warning: VHS recording generation failed: {e}")
        import traceback

        traceback.print_exc()
        print()

    # Generate SVG screenshots (always runs)
    try:
        generate_svg_screenshots(db_path)
        print()
    except Exception as e:
        print(f"! Warning: SVG screenshot generation failed: {e}")
        import traceback

        traceback.print_exc()
        print()

    print("=" * 60)
    print("TUI demo generation complete")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
