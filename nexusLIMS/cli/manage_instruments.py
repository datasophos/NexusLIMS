"""
CLI entry point for the NexusLIMS instrument management TUI.

Provides the ``nexuslims instruments manage`` and ``nexuslims instruments list``
commands for interactive and scriptable database management.

Usage
-----

.. code-block:: bash

    # Launch the instrument management TUI
    nexuslims instruments manage

    # List instruments in a table
    nexuslims instruments list

    # List instruments as JSON
    nexuslims instruments list --format json

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

import json
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


def _truncate_url_middle(url: str, max_width: int = 22) -> str:
    """Truncate a URL in the middle to fit within max_width characters.

    Preserves the beginning (scheme + host) and the end (query string / path
    tail) so that both the server and the tool ID remain readable.

    Parameters
    ----------
    url
        The URL string to truncate.
    max_width
        Maximum character width of the result.

    Returns
    -------
    str
        The original URL if it fits, otherwise a middle-truncated version
        with ``…`` in the middle.
    """
    if len(url) <= max_width:
        return url
    # Reserve 1 char for the ellipsis
    half = (max_width - 1) // 2
    return url[:half] + "…" + url[-(max_width - half - 1) :]


def _list_instruments(output_format: str = "table") -> None:
    """Print a summary of all instruments in the database.

    Parameters
    ----------
    output_format
        Either ``"table"`` (default, Rich formatted) or ``"json"``.
    """
    from sqlalchemy import func  # noqa: PLC0415
    from sqlmodel import Session as DBSession  # noqa: PLC0415
    from sqlmodel import select  # noqa: PLC0415

    from nexusLIMS.db.engine import get_engine  # noqa: PLC0415
    from nexusLIMS.db.enums import EventType  # noqa: PLC0415
    from nexusLIMS.db.models import Instrument, SessionLog  # noqa: PLC0415

    with DBSession(get_engine()) as session:
        instruments = session.exec(select(Instrument)).all()

        if not instruments:
            click.echo(
                "No instruments found. Use 'nexuslims instruments manage' to add "
                "instruments."
            )
            return

        # Build per-instrument stats: (total_sessions, last_session_dt)
        stats: dict[str, tuple[int, object]] = {}
        for inst in instruments:
            row = session.exec(
                select(
                    func.count(func.distinct(SessionLog.session_identifier)),
                    func.max(SessionLog.timestamp),
                ).where(
                    SessionLog.instrument == inst.instrument_pid,
                    SessionLog.event_type == EventType.END,
                )
            ).one()
            total_sessions, last_ts = row
            stats[inst.instrument_pid] = (total_sessions or 0, last_ts)

    if output_format == "json":
        records = []
        for inst in instruments:
            total_sessions, last_ts = stats[inst.instrument_pid]
            last_session_str: str | None = None
            if last_ts is not None:
                localized = inst.localize_datetime(last_ts)
                last_session_str = localized.isoformat()
            records.append(
                {
                    "instrument_pid": inst.instrument_pid,
                    "display_name": inst.display_name,
                    "location": inst.location,
                    "api_url": inst.api_url,
                    "harvester": inst.harvester,
                    "sessions_total": total_sessions,
                    "last_session": last_session_str,
                }
            )
        click.echo(json.dumps(records, indent=2))
        return

    # Rich table output
    from rich.console import Console  # noqa: PLC0415
    from rich.table import Table  # noqa: PLC0415

    n = len(instruments)
    table = Table(
        title=f"NexusLIMS Instruments ({n} total)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("ID", no_wrap=True)
    table.add_column("Display Name")
    table.add_column("Location")
    table.add_column("API URL", no_wrap=True)
    table.add_column("Sessions", justify="right")
    table.add_column("Last Session", no_wrap=True)

    for inst in instruments:
        total_sessions, last_ts = stats[inst.instrument_pid]
        if last_ts is not None:
            localized = inst.localize_datetime(last_ts)
            last_session_str = localized.strftime("%Y-%m-%d %H:%M %Z")
        else:
            last_session_str = "—"
        table.add_row(
            inst.instrument_pid,
            inst.display_name,
            inst.location,
            _truncate_url_middle(inst.api_url),
            str(total_sessions),
            last_session_str,
        )

    console = Console()
    console.print(table)


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
