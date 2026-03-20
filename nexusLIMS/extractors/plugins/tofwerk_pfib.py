"""Tofwerk fibTOF pFIB-ToF-SIMS HDF5 extractor plugin."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

import h5py
import numpy as np

from nexusLIMS.extractors.utils import _get_mtime_iso, add_to_extensions
from nexusLIMS.instruments import get_instr_from_filepath
from nexusLIMS.schemas.units import ureg

if TYPE_CHECKING:
    from nexusLIMS.extractors.base import ExtractionContext

_logger = logging.getLogger(__name__)


class TofwerkPfibExtractor:
    """
    Extractor for Tofwerk fibTOF pFIB-ToF-SIMS HDF5 files.

    Handles both raw files (no ``PeakData/PeakData``) and opened/processed files
    (has ``PeakData/PeakData`` with integrated peak intensities). Performs content
    sniffing to confirm the file is a Tofwerk fibTOF FIB-SIMS acquisition before
    attempting extraction.
    """

    name = "tofwerk_pfib_extractor"
    priority = 150
    supported_extensions: ClassVar = {"h5"}

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Performs content sniffing to verify this is a Tofwerk fibTOF FIB-SIMS HDF5
        file by checking for the presence of ``FullSpectra/SumSpectrum``,
        ``FIBParams``, ``FIBImages``, and the ``TofDAQ Version`` root attribute.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if this appears to be a Tofwerk fibTOF FIB-SIMS HDF5 file
        """
        if context.file_path.suffix.lower() != ".h5":
            return False
        try:
            with h5py.File(context.file_path, "r") as f:
                return (
                    "FullSpectra/SumSpectrum" in f
                    and "FIBParams" in f
                    and "FIBImages" in f
                    and "TofDAQ Version" in f.attrs
                )
        except Exception:
            return False

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from a Tofwerk fibTOF pFIB-ToF-SIMS HDF5 file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        list[dict]
            List containing one metadata dict with ``nx_meta`` key
        """
        nx_meta: dict[str, Any] = {
            "DatasetType": "SpectrumImage",
            "Data Type": "PFIB_TOFSIMS",
        }
        try:
            with h5py.File(context.file_path, "r") as f:
                nx_meta["Creation Time"] = _parse_creation_time(f, context.file_path)
                instr = get_instr_from_filepath(context.file_path)
                nx_meta["Instrument ID"] = instr.name if instr is not None else None

                _extract_fib_params(f, nx_meta)
                _extract_spatial_dims(f, nx_meta)
                _extract_spectral_params(f, nx_meta)
                _extract_acquisition_params(f, nx_meta)

                variant = "pre-processed" if "PeakData/PeakData" in f else "raw"
                add_to_extensions(nx_meta, "File Variant", variant)

        except Exception:
            _logger.exception("Failed to extract metadata from %s", context.file_path)
            if "Creation Time" not in nx_meta:
                nx_meta["Creation Time"] = _get_mtime_iso(context.file_path)

        return [{"nx_meta": nx_meta}]


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------


def _read_attr_scalar(obj, key: str, default=None):
    """Return a scalar attribute value, decoding bytes if needed."""
    if key not in obj.attrs:
        return default
    val = np.asarray(obj.attrs[key]).flat[0]
    if isinstance(val, (bytes, np.bytes_)):
        val = val.decode()
    return val


def _parse_creation_time(f: h5py.File, filepath) -> str:
    """
    Return ISO-8601 creation time string with timezone.

    Tries ``AcquisitionLog/Log[0]['timestring']`` first (preferred, includes
    timezone), then falls back to the ``HDF5 File Creation Time`` root attribute
    (no timezone, treated as UTC), then falls back to file mtime.
    """
    with contextlib.suppress(Exception):
        timestring = f["AcquisitionLog/Log"][0]["timestring"]
        if isinstance(timestring, (bytes, np.bytes_)):
            timestring = timestring.decode()
        dt = datetime.fromisoformat(timestring)
        return dt.isoformat()

    with contextlib.suppress(Exception):
        raw = f.attrs.get("HDF5 File Creation Time", b"")
        if isinstance(raw, (bytes, np.bytes_)):
            raw = raw.decode()
        dt = datetime.strptime(raw, "%d.%m.%Y %H:%M:%S").replace(tzinfo=UTC)
        return dt.isoformat()

    return _get_mtime_iso(filepath)


def _extract_fib_params(f: h5py.File, nx_meta: dict) -> None:
    """Extract FIB column parameters from FIBParams group attributes."""
    try:
        fibparams = f["FIBParams"]
    except KeyError:
        return

    fib_hw = _read_attr_scalar(fibparams, "FibHardware")
    if fib_hw is not None:
        add_to_extensions(nx_meta, "FIB Hardware", fib_hw)

    voltage = _read_attr_scalar(fibparams, "Voltage")
    if voltage is not None:
        with contextlib.suppress(Exception):
            add_to_extensions(
                nx_meta,
                "accelerating_voltage",
                ureg.Quantity(float(voltage) / 1000.0, "kilovolt"),
            )

    current = _read_attr_scalar(fibparams, "Current")
    if current is not None:
        with contextlib.suppress(Exception):
            add_to_extensions(
                nx_meta,
                "beam_current",
                ureg.Quantity(float(current), "ampere"),
            )

    view_field = _read_attr_scalar(fibparams, "ViewField")
    if view_field is not None:
        with contextlib.suppress(Exception):
            # ViewField is stored in mm
            add_to_extensions(
                nx_meta,
                "field_of_view",
                ureg.Quantity(float(view_field), "millimeter"),
            )


def _extract_spatial_dims(f: h5py.File, nx_meta: dict) -> None:
    """Extract spatial dimensions and derive pixel size."""
    nwrites = _read_attr_scalar(f, "NbrWrites")
    nsegs = _read_attr_scalar(f, "NbrSegments")
    nbr_peaks = _read_attr_scalar(f, "NbrPeaks")

    # Determine NX from EventList or PeakData shape
    nx = None
    if "FullSpectra/EventList" in f:
        with contextlib.suppress(Exception):
            nx = f["FullSpectra/EventList"].shape[2]
    if nx is None and "PeakData/PeakData" in f:
        with contextlib.suppress(Exception):
            nx = f["PeakData/PeakData"].shape[2]
    if nx is None:
        nx = nsegs  # fallback: assume square scan

    if nwrites is not None and nsegs is not None and nx is not None:
        add_to_extensions(
            nx_meta,
            "data_dimensions",
            f"({int(nwrites)}, {int(nsegs)}, {int(nx)})",
        )
        nx_meta["Data Dimensions"] = f"({int(nwrites)}, {int(nsegs)}, {int(nx)})"

    if nbr_peaks is not None:
        add_to_extensions(nx_meta, "Number of Peaks", int(nbr_peaks))

    # Pixel size from FIBParams.ViewField (mm) / nx
    with contextlib.suppress(Exception):
        view_field_mm = float(np.asarray(f["FIBParams"].attrs["ViewField"]).flat[0])
        if nx is not None and nx > 0:
            pixel_size_um = (view_field_mm * 1e3) / int(nx)
            add_to_extensions(
                nx_meta,
                "Pixel Size",
                ureg.Quantity(pixel_size_um, "micrometer"),
            )


def _extract_spectral_params(f: h5py.File, nx_meta: dict) -> None:
    """Extract spectral (mass axis) parameters."""
    with contextlib.suppress(Exception):
        mass_axis = f["FullSpectra/MassAxis"][:]
        add_to_extensions(
            nx_meta,
            "Mass Range Minimum",
            ureg.Quantity(float(mass_axis.min()), "dalton"),
        )
        add_to_extensions(
            nx_meta,
            "Mass Range Maximum",
            ureg.Quantity(float(mass_axis.max()), "dalton"),
        )


def _extract_acquisition_params(f: h5py.File, nx_meta: dict) -> None:
    """Extract acquisition-wide parameters from root attributes and FibParams."""
    ion_mode = _read_attr_scalar(f, "IonMode")
    if ion_mode is not None:
        add_to_extensions(nx_meta, "Ion Mode", ion_mode)

    gui_version = _read_attr_scalar(f, "FiblysGUIVersion")
    if gui_version is not None:
        add_to_extensions(nx_meta, "FibLys GUI Version", gui_version)

    daq_version = _read_attr_scalar(f, "TofDAQ Version")
    if daq_version is not None:
        add_to_extensions(nx_meta, "TofDAQ Version", str(daq_version))

    # Chamber pressure — mean over all writes
    with contextlib.suppress(Exception):
        pressure_data = f["FibParams/FibPressure/TwData"][:]
        add_to_extensions(
            nx_meta,
            "Chamber Pressure",
            ureg.Quantity(float(pressure_data.mean()), "pascal"),
        )
