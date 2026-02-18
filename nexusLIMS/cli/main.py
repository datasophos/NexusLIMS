"""Unified CLI entrypoint for NexusLIMS.

Provides the ``nexuslims`` command with subcommands for all NexusLIMS CLI
tools. Uses lazy loading so that ``nexuslims --help`` stays fast without
importing heavy modules.

Usage
-----

.. code-block:: bash

    nexuslims --help
    nexuslims --version
    nexuslims build-records [OPTIONS]
    nexuslims config [dump|load|edit]
    nexuslims db [init|upgrade|...]
    nexuslims instruments manage
"""

from __future__ import annotations

import click

# Maps command name -> (module_path, attr_name)
_LAZY_COMMANDS: dict[str, tuple[str, str]] = {
    "build-records": ("nexusLIMS.cli.process_records", "main"),
    "config": ("nexusLIMS.cli.config", "main"),
}


class LazyGroup(click.Group):
    """Click group that lazily loads subcommands on first use."""

    def __init__(self, *args, lazy_commands: dict[str, tuple[str, str]], **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_commands = lazy_commands

    def list_commands(self, ctx: click.Context) -> list[str]:
        """List all commands, including lazy ones."""
        base = super().list_commands(ctx)
        # Merge lazy command names that aren't already registered
        lazy_names = sorted(name for name in self._lazy_commands if name not in base)
        return sorted(set(base + lazy_names))

    def get_command(
        self, ctx: click.Context, cmd_name: str
    ) -> click.BaseCommand | None:
        """Get a command, lazily importing it if necessary."""
        # Check eagerly registered commands first
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd

        # Try lazy import
        if cmd_name in self._lazy_commands:
            module_path, attr_name = self._lazy_commands[cmd_name]
            return self._import_command(module_path, attr_name)

        return None

    @staticmethod
    def _import_command(module_path: str, attr_name: str) -> click.BaseCommand:
        """Import a command from a module path."""
        import importlib  # noqa: PLC0415

        module = importlib.import_module(module_path)
        return getattr(module, attr_name)


def _get_db_group() -> click.BaseCommand:
    """Lazily build and return the db CLI group."""
    from nexusLIMS.cli.migrate import _cli  # noqa: PLC0415

    return _cli()


def _build_instruments_group() -> click.Group:
    """Build the ``instruments`` group with its subcommands."""

    @click.group()
    def instruments() -> None:
        """Manage NexusLIMS instruments."""

    @instruments.command()
    @click.version_option(
        version=None,
        message=_format_version("nexuslims instruments manage"),
    )
    def manage() -> None:
        """Launch the interactive instrument management TUI.

        Opens a terminal UI for adding, editing, and deleting
        instruments in the NexusLIMS database.

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
        """  # noqa: D301
        from nexusLIMS.cli.manage_instruments import (  # noqa: PLC0415
            _ensure_database_initialized,
            _run_instrument_manager,
        )

        _ensure_database_initialized()
        _run_instrument_manager()

    return instruments


def _format_version(prog_name: str) -> str:
    """Format version string with release date if available."""
    from nexusLIMS.cli import _format_version as _fmt  # noqa: PLC0415

    return _fmt(prog_name)


@click.group(
    cls=LazyGroup,
    lazy_commands=_LAZY_COMMANDS,
)
@click.version_option(
    version=None,
    message=_format_version("nexuslims"),
)
def main() -> None:
    """NexusLIMS command-line interface.

    Manage records, configuration, database migrations, and instruments.
    """


# Register non-lazy subcommands
main.add_command(_build_instruments_group(), "instruments")


# Register db as a lazy command via a callback
_original_get_command = main.get_command


def _patched_get_command(ctx: click.Context, cmd_name: str) -> click.BaseCommand | None:
    if cmd_name == "db":
        return _get_db_group()
    return _original_get_command(ctx, cmd_name)


main.get_command = _patched_get_command  # type: ignore[method-assign]

# Ensure "db" shows up in help
if "db" not in main._lazy_commands:  # noqa: SLF001
    main._lazy_commands["db"] = ("nexusLIMS.cli.migrate", "_cli")  # noqa: SLF001


if __name__ == "__main__":  # pragma: no cover
    main()
