"""
CLI entry point for the NexusLIMS instrument management TUI.

Provides the ``nexuslims instruments manage`` command for interactive
database management.

Usage
-----

.. code-block:: bash

    # Launch the instrument management TUI
    nexuslims instruments manage

    # Show version information
    nexuslims instruments manage --version

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
    from dotenv import find_dotenv, load_dotenv  # noqa: PLC0415

    load_dotenv(find_dotenv(usecwd=True))

    # Get DB path from environment variable
    db_path_str = os.getenv("NX_DB_PATH")
    if not db_path_str:
        click.secho(
            "Error: NX_DB_PATH environment variable is not set.",
            fg="red",
            err=True,
        )
        click.echo("\nSet it via the interactive configurator:\n", err=True)
        click.echo("    nexuslims config edit\n", err=True)
        click.echo("Or set it directly, e.g.:\n", err=True)
        click.echo("    export NX_DB_PATH=/path/to/database.db", err=True)
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


def _run_instrument_manager() -> None:
    """Launch the instrument management TUI.

    This is separated from the Click command so it can be called from
    both the standalone ``main()`` command and the unified CLI's
    ``nexuslims instruments manage`` subcommand.
    """
    from nexusLIMS.tui.apps.instruments import InstrumentManagerApp  # noqa: PLC0415

    # Configure logging (quiet for TUI mode)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Pass db_path explicitly so the TUI app doesn't need to access
    # config.settings (which would require all settings to be valid)
    db_path = Path(os.getenv("NX_DB_PATH"))

    # Launch the TUI app
    try:
        app = InstrumentManagerApp(db_path=db_path)
        app.run()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        click.echo("\nExiting...", err=True)
    except Exception as e:
        # Show error and exit
        click.echo(f"Error: {e}", err=True)
        logger.exception("Failed to run instrument manager")
        raise click.Abort from e


@click.command()
@click.version_option(
    version=None,
    message="This standalone command is deprecated. Use: nexuslims instruments manage",
)
def main():
    """
    Manage NexusLIMS instruments database.

    Launch an interactive terminal UI for adding, editing, and deleting
    instruments in the NexusLIMS database. Provides form validation,
    uniqueness checks, and confirmation prompts for destructive actions.

    \b
    Keybindings:
    ------------
      - a         Add new instrument
      - e         Edit selected instrument
      - d         Delete selected instrument
      - r         Refresh list
      - Ctrl+T    Toggle theme (dark/light)
      - ?         Show help
      - Ctrl+Q    Quit

    \b
    Example:
    --------
      $ nexuslims instruments manage

    The TUI will display a table of all instruments. Use arrow keys to
    navigate and press Enter or 'e' to edit the selected instrument.
    """  # noqa: D301
    _ensure_database_initialized()
    _run_instrument_manager()


if __name__ == "__main__":  # pragma: no cover
    main()
