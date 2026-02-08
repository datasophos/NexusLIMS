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
- Automatic database initialization (if NX_DB_PATH doesn't exist yet)
"""

import logging
import os
from pathlib import Path

import click

# Heavy imports are lazy-loaded inside the main function to keep
# --help / --version fast (same pattern as other CLI tools).

logger = logging.getLogger(__name__)


def _ensure_database_initialized() -> None:
    """
    Ensure the NexusLIMS database exists and is initialized.

    If NX_DB_PATH is not set or the database file doesn't exist,
    automatically initializes it using the migration system.
    """
    # Load .env file if it exists (before checking environment variables)
    from dotenv import load_dotenv  # noqa: PLC0415

    load_dotenv()

    # Get DB path from environment variable
    db_path_str = os.getenv("NX_DB_PATH")
    if not db_path_str:
        click.secho(
            "Error: NX_DB_PATH environment variable is not set",
            fg="red",
            err=True,
        )
        click.echo("Set it to the desired database location, e.g.:", err=True)
        click.echo("  export NX_DB_PATH=/path/to/database.db", err=True)
        raise click.Abort

    db_path = Path(db_path_str)

    # If database doesn't exist, initialize it
    if not db_path.exists():
        click.echo(f"Database not found at {db_path}")
        click.echo("Initializing new database...")

        # Create parent directory if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create empty database file
        db_path.touch()

        # Import migration utilities
        from nexusLIMS.cli.migrate import (  # noqa: PLC0415
            _get_current_revision,
            _run_alembic_command,
        )

        # Run all migrations to create the schema
        try:
            _run_alembic_command("upgrade", "head")
            click.secho("✓ Database initialized successfully", fg="green")
            click.echo(f"  Current version: {_get_current_revision()}\n")
        except Exception as e:
            click.secho(f"Error initializing database: {e}", fg="red", err=True)
            # Clean up the empty database file on failure
            if db_path.exists():
                db_path.unlink()
            raise click.Abort from e


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
    # Configure logging (quiet for TUI mode)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Ensure database is initialized BEFORE importing TUI app
    # (imports trigger config validation which requires database to exist)
    _ensure_database_initialized()

    # Import here after database initialization
    from nexusLIMS.tui.apps.instruments import InstrumentManagerApp  # noqa: PLC0415

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
