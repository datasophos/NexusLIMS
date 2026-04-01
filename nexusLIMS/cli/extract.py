"""
CLI command for extracting metadata and generating previews from individual files.

Usage
-----

.. code-block:: bash

    # Extract metadata and print as JSON
    nexuslims extract /path/to/file.dm4

    # Extract metadata only (no preview)
    nexuslims extract --no-preview /path/to/file.dm4

    # Generate preview only
    nexuslims extract --no-metadata /path/to/file.dm4

    # Save preview to a specific path
    nexuslims extract --preview-path /tmp/preview.png /path/to/file.dm4

    # Write metadata JSON alongside the file (or to NX_DATA_PATH if the file
    # is under NX_INSTRUMENT_DATA_PATH)
    nexuslims extract --write /path/to/file.dm4
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

_logger = logging.getLogger(__name__)


@click.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--no-preview",
    is_flag=True,
    default=False,
    help="Skip preview image generation.",
)
@click.option(
    "--no-metadata",
    is_flag=True,
    default=False,
    help="Skip metadata extraction (only generate preview).",
)
@click.option(
    "--preview-path",
    "-p",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Path to write the preview image. If omitted, the preview is written "
        "alongside the input file as '<filename>.thumb.png'."
    ),
)
@click.option(
    "--write",
    "-w",
    is_flag=True,
    default=False,
    help=(
        "Write metadata JSON to disk alongside the input file as '<filename>.json'. "
        "If the file is under NX_INSTRUMENT_DATA_PATH, the JSON is written to the "
        "corresponding location under NX_DATA_PATH instead. "
        "By default, metadata is only printed to stdout."
    ),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing metadata JSON and preview files.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging output.",
)
def main(  # noqa: PLR0913
    file: Path,
    no_preview: bool,  # noqa: FBT001
    no_metadata: bool,  # noqa: FBT001
    preview_path: Path | None,
    write: bool,  # noqa: FBT001
    overwrite: bool,  # noqa: FBT001
    verbose: bool,  # noqa: FBT001
) -> None:
    """Extract metadata and/or generate a preview for a single FILE.

    Metadata is printed to stdout as JSON by default. Use --write to also
    persist it to the NexusLIMS data directory.

    \b
    Examples:
        nexuslims extract image.dm4
        nexuslims extract --no-preview spectrum.msa
        nexuslims extract --no-metadata --preview-path /tmp/thumb.png image.tif
        nexuslims extract --write --overwrite image.dm4
    """  # noqa: D301
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if no_metadata and no_preview:
        msg = "Cannot use both --no-metadata and --no-preview."
        raise click.UsageError(msg)

    if not no_metadata:
        _run_metadata(
            file,
            write=write,
            generate_preview=not no_preview,
            preview_path=preview_path,
            overwrite=overwrite,
        )
    elif not no_preview:
        _run_preview_only(file, preview_path=preview_path, overwrite=overwrite)


def _run_metadata(
    file: Path,
    *,
    write: bool,
    generate_preview: bool,
    preview_path: Path | None,
    overwrite: bool,
) -> None:
    """Extract metadata and optionally generate a preview."""
    from nexusLIMS.extractors import parse_metadata  # noqa: PLC0415

    # Always suppress preview generation inside parse_metadata -- we handle it
    # ourselves below so we can write to an explicit path without needing config.
    meta, _ = parse_metadata(
        file,
        write_output=write,
        generate_preview=False,
        overwrite=overwrite,
    )

    if meta is None:
        click.echo(
            f"No extractor found for {file.name} (unsupported format).",
            err=True,
        )
        sys.exit(1)

    # Pretty-print metadata to stdout
    click.echo(json.dumps(_make_serializable(meta), indent=2))

    if generate_preview:
        _generate_preview(file, preview_path=preview_path, overwrite=overwrite)


def _generate_preview(
    file: Path,
    *,
    preview_path: Path | None,
    overwrite: bool,
) -> None:
    """Generate a preview using the plugin registry directly (no config needed)."""
    from nexusLIMS.extractors.base import ExtractionContext  # noqa: PLC0415
    from nexusLIMS.extractors.registry import get_registry  # noqa: PLC0415
    from nexusLIMS.instruments import get_instr_from_filepath  # noqa: PLC0415

    if preview_path is None:
        preview_path = Path(str(file) + ".json").with_suffix(".thumb.png")

    if preview_path.exists() and not overwrite:
        click.echo(str(preview_path), err=True)
        return

    instrument = get_instr_from_filepath(file)
    registry = get_registry()
    ctx = ExtractionContext(file_path=file, instrument=instrument)
    generator = registry.get_preview_generator(ctx)

    if generator is None:
        click.echo(f"No preview generator found for {file.name}.", err=True)
        return

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    success = generator.generate(ctx, preview_path)
    if success:
        click.echo(f"Preview: {preview_path}", err=True)
    else:
        click.echo(f"Preview generation failed for {file.name}.", err=True)


def _run_preview_only(
    file: Path,
    *,
    preview_path: Path | None,
    overwrite: bool,
) -> None:
    """Generate a preview without running metadata extraction."""
    _generate_preview(file, preview_path=preview_path, overwrite=overwrite)


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    try:
        json.dumps(obj)
    except (TypeError, ValueError):
        return str(obj)
    else:
        return obj
