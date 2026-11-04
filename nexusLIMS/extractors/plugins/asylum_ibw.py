"""Metadata extraction for Asylum Research Igor binary waves."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from igor2 import binarywave

from nexusLIMS.extractors.utils import _set_instr_name_and_time, add_to_extensions
from nexusLIMS.schemas.units import ureg

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.extractors.base import ExtractionContext

_logger = logging.getLogger(__name__)
# igor2.struct logs raw file bytes at DEBUG, including private metadata and data.
logging.getLogger("igor2.struct").setLevel(logging.INFO)
IMAGE_DIMS = 3
CURVE_DIMS = 2


def read_wave(path: Path) -> tuple[dict, dict[str, str], list[str]]:
    """Read an Igor wave, its note, and its last-dimension channel labels."""
    wave = binarywave.load(str(path))["wave"]
    note = wave["note"].decode("latin-1")
    fields = {}
    for line in note.replace("\r", "\n").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    dimension = wave["wData"].ndim - 1
    labels = [label.decode("latin-1") for label in wave["labels"][dimension][1:]]
    return wave, fields, labels


def is_asylum(path: Path) -> bool:
    """Recognize supported Asylum image and force-curve waves."""
    if path.suffix.lower() != ".ibw":
        return False
    try:
        wave, note, labels = read_wave(path)
        data = wave["wData"]
        return bool(note.get("MicroscopeModel")) and (
            (
                data.ndim == IMAGE_DIMS
                and len(labels) == data.shape[-1]
                and any(x.startswith("Height") for x in labels)
            )
            or (
                data.ndim == CURVE_DIMS
                and len(labels) == data.shape[-1]
                and "ZSnsr" in labels
                and "Amp" in labels
            )
        )
    except Exception:
        return False


class AsylumIbwExtractor:
    """Extract acquisition metadata from Asylum AFM binary waves."""

    name = "asylum_ibw_extractor"
    priority = 150
    supported_extensions: ClassVar = {"ibw"}

    def supports(self, context: ExtractionContext) -> bool:
        """Return whether the context contains a supported Asylum wave.

        Parameters
        ----------
        context
            File and instrument information supplied by the registry.
        """
        return is_asylum(context.file_path)

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """Extract recorded AFM acquisition parameters.

        Parameters
        ----------
        context
            File and instrument information supplied by the registry.

        Returns
        -------
        list[dict]
            One metadata dictionary, with the original note and NexusLIMS fields.
        """
        result: dict[str, Any] = {"nx_meta": {}}
        nx = result["nx_meta"]
        try:
            _set_instr_name_and_time(result, context.file_path)
            wave, note, labels = read_wave(context.file_path)
            image = wave["wData"].ndim == IMAGE_DIMS
            nx["DatasetType"] = "Image" if image else "Spectrum"
            nx["Data Type"] = "AFM Image" if image else "AFM Force Curve"
            nx["Data Dimensions"] = str(wave["wData"].shape)
            add_to_extensions(nx, "Channels", ", ".join(labels))
            for key in (
                "MicroscopeModel",
                "ImagingMode",
                "ScanMode",
                "Date",
                "Time",
                "TriggerChannel",
            ):
                if key in note:
                    add_to_extensions(nx, key, note[key])
            for key, (name, unit) in {
                "ScanSize": ("Scan Size", "meter"),
                "FastScanSize": ("Fast Scan Size", "meter"),
                "SlowScanSize": ("Slow Scan Size", "meter"),
                "ScanRate": ("Scan Rate", "hertz"),
                "ScanAngle": ("Scan Angle", "degree"),
                "SpringConstant": ("Spring Constant", "newton / meter"),
                "InvOLS": ("Inverse Optical Lever Sensitivity", "meter / volt"),
                "ForceDist": ("Force Distance", "meter"),
                "NumPtsPerSec": ("Sampling Rate", "hertz"),
            }.items():
                if key in note:
                    try:
                        quantity = ureg.Quantity(float(note[key]), unit)
                        if key in {"ScanSize", "FastScanSize", "SlowScanSize"}:
                            quantity = quantity.to("micrometer")
                        add_to_extensions(nx, name, quantity)
                    except (TypeError, ValueError):
                        _logger.warning(
                            "Invalid %s value in %s", key, context.file_path
                        )
            result["original_metadata"] = {
                **note,
                "Raw Wave Note": wave["note"].decode("latin-1"),
            }
        except Exception:
            _logger.exception(
                "Could not extract Asylum IBW metadata from %s", context.file_path
            )
            if "Creation Time" not in nx:
                nx["Creation Time"] = datetime.now().astimezone().isoformat()
                nx.setdefault("warnings", []).append("Creation Time")
            nx.setdefault("Instrument ID", None)
            nx.setdefault("warnings", []).append("AFM metadata extraction failed")
            nx.setdefault("DatasetType", "Misc")
            nx.setdefault("Data Type", "Unknown")
        return [result]
