"""CLI commands for NexusLIMS."""

from __future__ import annotations

import contextlib
import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def _format_version(prog_name: str) -> str:
    """Format version string with release date if available."""
    from nexusLIMS.version import __release_date__, __version__  # noqa: PLC0415

    version_str = f"{prog_name} (NexusLIMS {__version__}"
    if __release_date__:
        version_str += f", released {__release_date__}"
    version_str += ")"
    return version_str


@contextlib.contextmanager
def handle_config_error() -> Iterator[None]:
    """Context manager that catches config ``ValidationError`` and exits cleanly.

    Instead of dumping a raw Pydantic traceback, this prints a short,
    actionable message directing the user to ``nexuslims config edit``
    and the online documentation.

    Usage
    -----
    ::

        with handle_config_error():
            from nexusLIMS.config import settings
            settings.NX_DATA_PATH  # may raise ValidationError
    """
    import click  # noqa: PLC0415
    from pydantic import ValidationError  # noqa: PLC0415

    try:
        yield
    except ValidationError as exc:
        from nexusLIMS.version import __version__  # noqa: PLC0415

        doc_version = re.sub(r"\.dev.*$", "", __version__)

        # Collect the missing / invalid field names from the Pydantic errors
        fields = [e.get("loc", ("?",))[-1] for e in exc.errors()]
        field_list = ", ".join(str(f) for f in fields)

        # Build a compact, user-friendly message
        lines = [
            "Error: NexusLIMS configuration is incomplete or invalid.",
            "",
            f"  Missing/invalid fields: {field_list}",
            "",
            "To fix this, either:",
            "",
            "  1. Run the interactive configurator:",
            "",
            "       nexuslims config edit",
            "",
            "  2. Create a .env file manually (see documentation):",
            "",
            f"       https://datasophos.github.io/NexusLIMS/{doc_version}"
            "/user_guide/configuration.html",
            "",
        ]

        click.echo("\n".join(lines), err=True)
        sys.exit(1)
