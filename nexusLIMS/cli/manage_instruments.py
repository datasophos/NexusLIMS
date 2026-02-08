"""
CLI entry point for the NexusLIMS instrument management TUI.

Provides the ``nexuslims-manage-instruments`` command for interactive
database management.

Usage
-----

```bash
# Launch the instrument management TUI
nexuslims-manage-instruments

# Show version information
nexuslims-manage-instruments --version
```

Features
--------
- List all instruments in a searchable table
- Add new instruments with form validation
- Edit existing instruments
- Delete instruments with confirmation prompts
- Theme switching (dark/light mode)
- Built-in help screen
"""

import logging

import click

# Heavy imports are lazy-loaded inside the main function to keep
# --help / --version fast (same pattern as other CLI tools).

logger = logging.getLogger(__name__)


def _format_version(prog_name: str) -> str:
    """Format version string with release date if available."""
    from nexusLIMS.version import __release_date__, __version__  # noqa: PLC0415

    version_str = f"{prog_name} (NexusLIMS {__version__}"
    if __release_date__:
        version_str += f", released {__release_date__}"
    version_str += ")"
    return version_str


@click.command()
@click.version_option(
    version=None, message=_format_version("nexuslims-manage-instruments")
)
def main():
    """
    Manage NexusLIMS instruments database.

    Launch an interactive terminal UI for adding, editing, and deleting
    instruments in the NexusLIMS database. Provides form validation,
    uniqueness checks, and confirmation prompts for destructive actions.

    Keybindings
    -----------
    - a: Add new instrument
    - e: Edit selected instrument
    - d: Delete selected instrument
    - r: Refresh list
    - Ctrl+T: Toggle theme (dark/light)
    - ?: Show help
    - Ctrl+Q / q: Quit

    Examples
    --------
    Launch the TUI::

        $ nexuslims-manage-instruments

    The TUI will display a table of all instruments. Use arrow keys to
    navigate and press Enter or 'e' to edit the selected instrument.
    """
    # Import here to keep --help fast
    from nexusLIMS.tui.apps.instruments import InstrumentManagerApp  # noqa: PLC0415

    # Configure logging (quiet for TUI mode)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Launch the TUI app
    try:
        app = InstrumentManagerApp()
        app.run()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        click.echo("\nExiting...", err=True)
    except Exception as e:
        # Show error and exit
        click.echo(f"Error: {e}", err=True)
        logger.exception("Failed to run instrument manager")
        raise click.Abort from e


if __name__ == "__main__":
    main()
