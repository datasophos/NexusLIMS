# ruff: noqa: PLC0415
"""CLI for NexusLIMS database migrations.

Provides simple commands for common database migration operations, while
still allowing advanced users to access the underlying Alembic functionality.

Usage
-----
.. code-block:: bash

    # Initialize a new database
    nexuslims-migrate init

    # Upgrade to latest schema version
    nexuslims-migrate upgrade

    # Show current database version
    nexuslims-migrate current

    # Check for pending migrations
    nexuslims-migrate check

    # Downgrade one migration
    nexuslims-migrate downgrade

    # Advanced: Run any Alembic command
    nexuslims-migrate alembic history --verbose

Examples
--------
Set up a new database:

.. code-block:: bash

    nexuslims-migrate init

Check database status:

.. code-block:: bash

    nexuslims-migrate current
    nexuslims-migrate check

Apply pending migrations:

.. code-block:: bash

    nexuslims-migrate upgrade

Notes
-----
This command automatically locates the migrations directory inside the
installed package, making it work correctly whether NexusLIMS is installed
via pip, uv, or run from source.
"""

from importlib.resources import files
from pathlib import Path


def _get_migrations_dir() -> Path:
    """Locate the migrations directory inside the installed package.

    Uses importlib.resources (Python 3.9+) to find nexusLIMS.migrations
    regardless of whether the package is installed normally, as an editable
    install, or run from source.

    Returns
    -------
    pathlib.Path
        Absolute path to the nexusLIMS/migrations/ directory.

    Raises
    ------
    ImportError
        If the nexusLIMS.migrations package cannot be found.
    """
    try:
        migrations_resource = files("nexusLIMS.migrations")
        return Path(str(migrations_resource))
    except (ImportError, TypeError) as e:
        msg = (
            "Could not locate nexusLIMS.migrations package. "
            "Ensure NexusLIMS is properly installed."
        )
        raise ImportError(msg) from e


def _get_alembic_config():
    """Create an Alembic Config object for the packaged migrations.

    Returns
    -------
    alembic.config.Config
        Configured Alembic Config object with script_location set.
    """
    from alembic.config import Config

    migrations_dir = _get_migrations_dir()
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    return cfg


def _run_alembic_command(command_name: str, *args, **kwargs):
    """Run an Alembic command programmatically.

    Parameters
    ----------
    command_name : str
        Name of the Alembic command function (e.g., 'upgrade', 'downgrade')
    *args
        Positional arguments to pass to the Alembic command
    **kwargs
        Keyword arguments to pass to the Alembic command
    """
    import alembic.command

    cfg = _get_alembic_config()
    command_func = getattr(alembic.command, command_name)
    command_func(cfg, *args, **kwargs)


def _cli():  # noqa: PLR0915
    """Create the Click CLI application.

    Lazy import of click to speed up --help for other entry points.
    """
    import click

    @click.group(invoke_without_command=True)
    @click.option("--version", is_flag=True, help="Show version and exit")
    @click.pass_context
    def cli(ctx, version):
        """Manage NexusLIMS database schema migrations.

        This tool provides simple commands for common database operations.
        For advanced usage, use 'nexuslims-migrate alembic [COMMAND]' to
        access the full Alembic CLI.
        """
        if version:
            from nexusLIMS import __version__

            click.echo(f"nexuslims-migrate (NexusLIMS {__version__})")
            ctx.exit()

        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @cli.command()
    @click.option(
        "--force",
        is_flag=True,
        help="Overwrite existing database file if it exists",
    )
    def init(force):
        """Initialize a new NexusLIMS database.

        Creates the database file at NX_DB_PATH, applies the schema,
        and marks it as migrated to the latest version.

        This is equivalent to running initialize_db.py followed by
        'nexuslims-migrate upgrade head'.
        """
        import subprocess
        import sys

        from nexusLIMS.config import settings

        db_path = settings.NX_DB_PATH

        if db_path.exists() and not force:
            click.secho(
                f"Error: Database already exists at {db_path}", fg="red", err=True
            )
            click.echo(
                "Use --force to overwrite, or remove the file manually.", err=True
            )
            sys.exit(1)

        click.echo(f"Initializing database at {db_path}...")

        # Initialize the database schema
        try:
            result = subprocess.run(
                [sys.executable, "-m", "nexusLIMS.db.dev.initialize_db"],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout:
                click.echo(result.stdout)
        except subprocess.CalledProcessError as e:
            click.secho(f"Error initializing database: {e.stderr}", fg="red", err=True)
            sys.exit(1)

        # Stamp the database with the current migration version
        click.echo("Marking database as current version...")
        try:
            _run_alembic_command("stamp", "head")
            click.secho("✓ Database initialized successfully", fg="green")
        except Exception as e:
            click.secho(f"Error stamping database: {e}", fg="red", err=True)
            sys.exit(1)

    @cli.command()
    @click.argument("revision", default="head")
    @click.option(
        "--sql", is_flag=True, help="Generate SQL script instead of applying changes"
    )
    def upgrade(revision, sql):
        r"""Upgrade database to a later version.

        REVISION is the target migration version (default: 'head' for latest).

        \b
        Examples:
          nexuslims-migrate upgrade          # Upgrade to latest
          nexuslims-migrate upgrade +1       # Upgrade one version
          nexuslims-migrate upgrade abc123   # Upgrade to specific revision
        """
        try:
            _run_alembic_command("upgrade", revision, sql=sql)
            if not sql:
                click.secho("✓ Database upgraded successfully", fg="green")
        except Exception as e:
            click.secho(f"Error upgrading database: {e}", fg="red", err=True)
            import sys

            sys.exit(1)

    @cli.command()
    @click.argument("revision", default="-1")
    @click.option(
        "--sql", is_flag=True, help="Generate SQL script instead of applying changes"
    )
    def downgrade(revision, sql):
        r"""Downgrade database to an earlier version.

        REVISION is the target migration version (default: '-1' for one step back).

        \b
        Examples:
          nexuslims-migrate downgrade        # Downgrade one version
          nexuslims-migrate downgrade -2     # Downgrade two versions
          nexuslims-migrate downgrade abc123 # Downgrade to specific revision
        """
        try:
            _run_alembic_command("downgrade", revision, sql=sql)
            if not sql:
                click.secho("✓ Database downgraded successfully", fg="green")
        except Exception as e:
            click.secho(f"Error downgrading database: {e}", fg="red", err=True)
            import sys

            sys.exit(1)

    @cli.command()
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
    def current(verbose):
        """Show the current database migration version.

        Displays the revision ID that the database is currently at.
        """
        try:
            _run_alembic_command("current", verbose=verbose)
        except Exception as e:
            click.secho(f"Error checking database version: {e}", fg="red", err=True)
            import sys

            sys.exit(1)

    @cli.command()
    def check():
        """Check if the database has pending migrations.

        Exits with code 0 if database is up-to-date, code 1 if migrations
        are pending, or code 2 on error.
        """
        import sys

        from alembic.script import ScriptDirectory

        try:
            cfg = _get_alembic_config()
            script = ScriptDirectory.from_config(cfg)

            # Get current database revision
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine

            from nexusLIMS.config import settings

            engine = create_engine(f"sqlite:///{settings.NX_DB_PATH}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()

            head_rev = script.get_current_head()

            if current_rev == head_rev:
                click.secho(
                    f"✓ Database is up-to-date (revision: {current_rev or 'none'})",
                    fg="green",
                )
                sys.exit(0)
            else:
                click.secho("⚠ Database has pending migrations", fg="yellow", err=True)
                click.echo(f"  Current revision: {current_rev or 'none'}", err=True)
                click.echo(f"  Latest revision:  {head_rev}", err=True)
                click.echo(
                    "\nRun 'nexuslims-migrate upgrade' to apply pending migrations.",
                    err=True,
                )
                sys.exit(1)
        except Exception as e:
            click.secho(f"Error checking migrations: {e}", fg="red", err=True)
            sys.exit(2)

    @cli.command()
    @click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
    @click.option(
        "--indicate-current",
        "-i",
        is_flag=True,
        help="Indicate current revision (Alembic default)",
    )
    def history(verbose, indicate_current):
        """Show migration history.

        Displays the revision history for the database migrations.
        """
        try:
            _run_alembic_command(
                "history", verbose=verbose, indicate_current=indicate_current
            )
        except Exception as e:
            click.secho(f"Error showing history: {e}", fg="red", err=True)
            import sys

            sys.exit(1)

    @cli.command(
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True}
    )
    @click.pass_context
    def alembic(ctx):
        r"""Run Alembic commands directly (advanced usage).

        This passes all arguments directly to Alembic's CLI, allowing
        access to the full range of Alembic commands and options.

        \b
        Examples:
          nexuslims-migrate alembic history --verbose
          nexuslims-migrate alembic revision --autogenerate -m "Add column"
          nexuslims-migrate alembic show head
        """
        import contextlib
        import sys
        import tempfile

        from alembic.config import CommandLine

        migrations_dir = _get_migrations_dir()

        # Create a temporary config file for Alembic
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False
        ) as tmp_config:
            tmp_config.write(f"[alembic]\nscript_location = {migrations_dir}\n")
            tmp_config_path = Path(tmp_config.name)

        try:
            # Inject config file and pass through remaining arguments
            original_argv = sys.argv.copy()
            sys.argv = [
                "nexuslims-migrate alembic",
                "-c",
                str(tmp_config_path),
                *ctx.args,
            ]

            # Run Alembic's CLI
            CommandLine(prog="nexuslims-migrate alembic").main()
        finally:
            sys.argv = original_argv
            # Clean up the temporary config file
            with contextlib.suppress(OSError):
                tmp_config_path.unlink()

    return cli


def main() -> None:
    """Entry point for nexuslims-migrate CLI."""
    cli = _cli()
    cli()


if __name__ == "__main__":
    main()
