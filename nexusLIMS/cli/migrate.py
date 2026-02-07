# ruff: noqa: PLC0415
"""CLI wrapper around Alembic for NexusLIMS database migrations.

Automatically locates the migrations directory inside the installed package
so that migrations work correctly regardless of install method (pip, uv tool
install, editable installs, etc.).

Usage
-----
.. code-block:: bash

    nexuslims-migrate upgrade head        # apply all pending migrations
    nexuslims-migrate downgrade -1        # roll back one migration
    nexuslims-migrate current             # show current revision
    nexuslims-migrate history             # show migration history
    nexuslims-migrate revision --autogenerate -m "description"  # (dev only)

All standard Alembic sub-commands and flags are supported.

Examples
--------
Apply all pending migrations:

.. code-block:: bash

    nexuslims-migrate upgrade head

View current migration status:

.. code-block:: bash

    nexuslims-migrate current

See migration history:

.. code-block:: bash

    nexuslims-migrate history --verbose

Notes
-----
This command automatically configures the Alembic script location to point to
the migrations directory shipped with the installed package, so you never need
to manually specify paths or config files.
"""

import sys
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


def main() -> None:
    """Entry point for nexuslims-migrate.

    Constructs an Alembic Config pointed at the package-internal migrations
    directory, then delegates to Alembic's CLI dispatcher with whatever
    arguments the user passed.

    This function:
    1. Locates the migrations directory using importlib.resources
    2. Creates an Alembic Config with the correct script_location
    3. Creates a temporary config file in memory
    4. Delegates to Alembic's CommandLine with the config

    All Alembic sub-commands and options are passed through transparently.
    """
    import contextlib
    import tempfile

    from alembic.config import CommandLine

    migrations_dir = _get_migrations_dir()

    # Alembic's CommandLine expects a config file path. We create a minimal
    # temporary one that just points to our migrations directory.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ini", delete=False
    ) as tmp_config:
        tmp_config.write(f"[alembic]\nscript_location = {migrations_dir}\n")
        tmp_config_path = Path(tmp_config.name)

    try:
        # Modify sys.argv to inject the -c flag pointing to our temp config
        # CommandLine will parse this and use our config
        original_argv = sys.argv.copy()
        sys.argv = [
            "nexuslims-migrate",
            "-c",
            str(tmp_config_path),
            *sys.argv[1:],
        ]

        # Run Alembic's standard CLI
        CommandLine(prog="nexuslims-migrate").main()
    finally:
        sys.argv = original_argv
        # Clean up the temporary config file
        with contextlib.suppress(OSError):
            tmp_config_path.unlink()


if __name__ == "__main__":
    main()
