"""FEI TIA (.ser/.emi) extractor plugin."""

import contextlib
import logging
from datetime import datetime as dt
from pathlib import Path
from typing import Any, ClassVar, List, Tuple

import numpy as np
from hyperspy.io import load as hs_load
from hyperspy.signal import BaseSignal

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.utils import add_to_extensions
from nexusLIMS.instruments import Instrument, get_instr_from_filepath
from nexusLIMS.schemas.units import ureg
from nexusLIMS.utils import (
    current_system_tz,
    set_nested_dict_value,
    sort_dict,
    try_getting_dict_value,
)

_logger = logging.getLogger(__name__)


class SerEmiExtractor:
    """
    Extractor for FEI TIA series files (.ser with accompanying .emi).

    This extractor handles metadata extraction from files saved by FEI's
    (now Thermo Fisher Scientific) TIA (Tecnai Imaging and Analysis) software.
    The .ser files contain the actual data, while .emi files contain metadata.
    """

    name = "ser_emi_extractor"
    priority = 100
    supported_extensions: ClassVar = {"ser"}

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if file extension is .ser
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "ser"

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:  # noqa: PLR0915
        """
        Extract metadata from a .ser file and its accompanying .emi file.

        Returns metadata (as a list of dicts) from an FEI .ser file +
        its associated .emi files, with some non-relevant information stripped.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        list[dict]
            List containing a single metadata dict with 'nx_meta' key.
            If files cannot be opened, at least basic metadata will be returned (
            creation time, etc.)
        """
        filename = context.file_path
        _logger.debug("Extracting metadata from SER/EMI file: %s", filename)

        # ObjectInfo present in emi; ser_header_parameters present in .ser
        # ObjectInfo should contain all the interesting metadata,
        # while ser_header_parameters is mostly technical stuff not really of
        # interest to anyone
        warning, emi_filename, ser_error = None, None, False

        # pylint: disable=broad-exception-caught
        try:
            emi_filename, ser_index = get_emi_from_ser(filename)
            s, emi_loaded = _load_ser(emi_filename, ser_index)

        except FileNotFoundError:
            # if emi wasn't found, specifically mention that
            warning = (
                "NexusLIMS could not find a corresponding .emi metadata "
                "file for this .ser file. Metadata extraction will be "
                "limited."
            )
            _logger.warning(warning)
            emi_loaded = False
            emi_filename = None

        except Exception:
            # otherwise, HyperSpy could not load the .emi, so give generic warning
            # that .emi could not be loaded for some reason:
            warning = (
                "The .emi metadata file associated with this "
                ".ser file could not be opened by NexusLIMS. "
                "Metadata extraction will be limited."
            )
            _logger.warning(warning)
            emi_loaded = False

        if not emi_loaded:
            # pylint: disable=broad-exception-caught

            # if we couldn't load the emi, lets at least open the .ser to pull
            # out the ser_header_info
            try:
                s = hs_load(filename, only_valid_data=True, lazy=True)
            except Exception:
                warning = (
                    "The .ser file could not be opened (perhaps file is "
                    "corrupted?); Metadata extraction is not possible."
                )
                _logger.warning(warning)
                # set s to an empty signal just so we can process some basic
                # metadata using same syntax as if we had read it correctly
                s = BaseSignal(np.zeros(1))
                ser_error = True

        metadata = s.original_metadata.as_dictionary()
        metadata["nx_meta"] = {}

        # if we've already encountered a warning, add that to the metadata,
        if warning:
            metadata["nx_meta"]["Extractor Warning"] = warning
        # otherwise check to ensure we actually have some metadata read from .emi
        elif "ObjectInfo" not in metadata or (
            "ExperimentalConditions" not in metadata["ObjectInfo"]
            and "ExperimentalDescription" not in metadata["ObjectInfo"]
        ):
            warning = (
                "No experimental metadata was found in the "
                "corresponding .emi file for this .ser. "
                "Metadata extraction will be limited."
            )
            _logger.warning(warning)
            metadata["nx_meta"]["Extractor Warning"] = warning

        # if we successfully found the .emi file, add it to the metadata
        if emi_filename:
            from nexusLIMS.config import settings  # noqa: PLC0415

            rel_emi_fname = (
                str(emi_filename).replace(
                    str(settings.NX_INSTRUMENT_DATA_PATH) + "/", ""
                )
                if emi_filename
                else None
            )
            metadata["nx_meta"]["emi Filename"] = rel_emi_fname
        else:
            metadata["nx_meta"]["emi Filename"] = None

        # Get the instrument object associated with this file
        instr = get_instr_from_filepath(filename)

        # if we found the instrument, then store the name as string, else None
        instr_name = instr.name if instr is not None else None
        metadata["nx_meta"]["fname"] = filename
        # get the modification time:
        # Use instrument timezone if available, otherwise fall back to system timezone
        mtime_naive_dt = dt.fromtimestamp(filename.stat().st_mtime)  # noqa: DTZ006
        tz = instr.timezone if instr is not None else None
        tz = tz if tz is not None else current_system_tz()
        mtime_aware_dt = tz.localize(mtime_naive_dt)
        metadata["nx_meta"]["Creation Time"] = mtime_aware_dt.isoformat()
        metadata["nx_meta"]["Instrument ID"] = instr_name

        # we could not read the signal, so add some basic metadata and return
        if ser_error:
            metadata = _handle_ser_error_metadata(metadata)
            # Migrate to schema-compliant format (move vendor meta to extensions)
            metadata = self._migrate_to_schema_compliant_metadata(metadata)
            return [metadata]

        metadata = parse_basic_info(metadata, s.data.shape, instr)
        metadata = parse_acquire_info(metadata)
        metadata = parse_experimental_conditions(metadata)
        metadata = parse_experimental_description(metadata)

        (
            metadata["nx_meta"]["Data Type"],
            metadata["nx_meta"]["DatasetType"],
        ) = parse_data_type(s, metadata)

        # we don't need to save the filename, it's just for internal processing
        del metadata["nx_meta"]["fname"]

        # Migrate metadata to schema-compliant format
        metadata = self._migrate_to_schema_compliant_metadata(metadata)

        # sort the nx_meta dictionary (recursively) for nicer display
        metadata["nx_meta"] = sort_dict(metadata["nx_meta"])

        return [metadata]

    def _migrate_to_schema_compliant_metadata(self, mdict: dict) -> dict:
        """
        Migrate metadata to schema-compliant format.

        Reorganizes metadata to conform to type-specific Pydantic schemas:
        - Extracts core EM Glossary fields to top level with standardized names
        - Moves vendor-specific nested dictionaries to extensions section
        - Preserves existing extensions from instrument profiles

        Parameters
        ----------
        mdict
            Metadata dictionary with nx_meta containing extracted fields

        Returns
        -------
        dict
            Metadata dictionary with schema-compliant nx_meta structure
        """
        nx_meta = mdict.get("nx_meta", {})
        dataset_type = nx_meta.get("DatasetType", "Image")

        # Preserve existing extensions from instrument profiles
        extensions = (
            nx_meta.get("extensions", {}).copy() if "extensions" in nx_meta else {}
        )

        # Field mappings from display names to EM Glossary names
        field_mappings = {
            "AccelerationVoltage": "acceleration_voltage",
            "Convergence Angle": "convergence_angle",
            "Acquisition Device": "acquisition_device",
        }

        # Camera Length is only core for Diffraction datasets
        if dataset_type == "Diffraction":
            field_mappings["Camera Length"] = "camera_length"

        # FEI TIA-specific top-level sections that go to extensions
        extension_top_level_keys = {
            "ObjectInfo",  # Main FEI metadata section
            "ser_header_parameters",  # SER file header
        }

        # Individual vendor-specific fields to move to extensions
        extension_field_names = {
            "emi Filename",
            "Extractor Warning",
            # Any other FEI-specific fields
        }

        # Build new nx_meta with proper field organization
        new_nx_meta = {}

        # Copy required fields
        for field in ["DatasetType", "Data Type", "Creation Time", "Data Dimensions"]:
            if field in nx_meta:
                new_nx_meta[field] = nx_meta[field]

        # Copy instrument identification
        if "Instrument ID" in nx_meta:
            new_nx_meta["Instrument ID"] = nx_meta["Instrument ID"]

        # Process all fields and categorize
        for old_name, value in nx_meta.items():
            # Skip fields we've already handled
            if old_name in [
                "DatasetType",
                "Data Type",
                "Creation Time",
                "Data Dimensions",
                "Instrument ID",
                "Extractor Warnings",
                "warnings",
                "extensions",
            ]:
                continue

            # Top-level vendor sections go to extensions
            if old_name in extension_top_level_keys:
                extensions[old_name] = value
                continue

            # Check if this is a core field that needs renaming
            if old_name in field_mappings:
                emg_name = field_mappings[old_name]
                new_nx_meta[emg_name] = value
                continue

            # Vendor-specific individual fields go to extensions
            if old_name in extension_field_names:
                extensions[old_name] = value
                continue

            # Everything else goes to extensions (FEI-specific fields)
            # This is safer since most FEI fields are vendor-specific
            extensions[old_name] = value

        # Copy warnings if present
        if "warnings" in nx_meta:
            new_nx_meta["warnings"] = nx_meta["warnings"]

        # Add extensions section if we have any
        for key, value in extensions.items():
            add_to_extensions(new_nx_meta, key, value)

        mdict["nx_meta"] = new_nx_meta
        return mdict


def _handle_ser_error_metadata(metadata):
    """Handle metadata when .ser file cannot be read."""
    metadata["nx_meta"]["DatasetType"] = "Misc"
    metadata["nx_meta"]["Data Type"] = "Unknown"
    metadata["nx_meta"]["warnings"] = []
    # sort the nx_meta dictionary (recursively) for nicer display
    metadata["nx_meta"] = sort_dict(metadata["nx_meta"])
    del metadata["nx_meta"]["fname"]
    return metadata


def _load_ser(emi_filename: Path, ser_index: int):
    """
    Load an data file given the .emi filename and an index of which signal to use.

    Parameters
    ----------
    emi_filename
        The path to an .emi file
    ser_index
        Which .ser file to load data from, given the .emi file above

    Returns
    -------
    hyperspy.signal.BaseSignal
        The signal loaded by HyperSpy
    bool
        Whether the emi file was successfully loaded (should be true if no Exceptions)
    """
    # approach here is for every .ser we want to examine, load the
    # metadata from the corresponding .emi file. If multiple .ser files
    # are related to this emi, HyperSpy returns a list, so we select out
    # the right signal from that list if that's what is returned

    # make sure to load with "only_valid_data" so data shape is correct
    # loading the emi with HS will try loading the .ser too, so this will
    # fail if there's an issue with the .ser file
    emi_s = hs_load(emi_filename, lazy=True, only_valid_data=True)

    # if there is more than one dataset, emi_s will be a list, so pick
    # out the matching signal from the list, which will be the "index"
    # from the filename minus 1:
    # if there is more than one dataset, emi_s will be a list, so pick
    # out the matching signal, otherwise use the signal as-is
    s = emi_s[ser_index - 1] if isinstance(emi_s, list) else emi_s

    return s, True


def parse_basic_info(metadata, shape, instrument: Instrument):
    """
    Parse basic metadata from file.

    Parse the metadata that is saved at specific places within
    the .emi tag structure into a consistent place in the metadata dictionary
    returned by :py:meth:`get_ser_metadata`. Specifically, this method handles
    the creation date, equipment manufacturer, and data shape/type.

    Parameters
    ----------
    metadata : dict
        A metadata dictionary as returned by :py:meth:`get_ser_metadata`
    shape
        The shape of the dataset
    instrument : Instrument
        The instrument this file was collected on

    Returns
    -------
    metadata : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    # try to set creation time to acquisition time from metadata
    acq_time = try_getting_dict_value(metadata, ["ObjectInfo", "AcquireDate"])
    if acq_time is not None:
        # Use instrument timezone if available, otherwise fall back to system timezone
        tz = instrument.timezone if instrument else current_system_tz()
        naive_dt = dt.strptime(acq_time, "%a %b %d %H:%M:%S %Y")  # noqa: DTZ007
        # Both instrument.timezone and current_system_tz() return pytz objects,
        # so use localize() for proper DST handling
        aware_dt = tz.localize(naive_dt)
        metadata["nx_meta"]["Creation Time"] = aware_dt.isoformat()

    # manufacturer is at high level, so parse it now
    manufacturer = try_getting_dict_value(metadata, ["ObjectInfo", "Manufacturer"])
    if manufacturer is not None:
        metadata["nx_meta"]["Manufacturer"] = manufacturer

    metadata["nx_meta"]["Data Dimensions"] = str(shape)
    metadata["nx_meta"]["warnings"] = []

    # set type to STEM Image by default (this seems to be most common)
    metadata["nx_meta"]["DatasetType"] = "Image"
    metadata["nx_meta"]["Data Type"] = "STEM_Imaging"

    return metadata


def parse_experimental_conditions(metadata):
    """
    Parse experimental conditions.

    Parse the metadata that is saved at specific places within
    the .emi tag structure into a consistent place in the metadata dictionary
    returned by :py:meth:`get_ser_metadata`. Specifically looks at the
    "ExperimentalConditions" node of the metadata structure.

    Parameters
    ----------
    metadata : dict
        A metadata dictionary as returned by :py:meth:`get_ser_metadata`

    Returns
    -------
    metadata : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    # Map input field names to (output_name, unit) tuples
    # If unit is None, value is stored as-is; otherwise, create Pint Quantity
    term_mapping = {
        ("DwellTimePath",): ("Dwell Time Path", "second"),
        ("FrameTime",): ("Frame Time", "second"),
        ("CameraNamePath",): ("Camera Name Path", None),
        ("Binning",): ("Binning", None),
        ("BeamPosition",): ("Beam Position", "micrometer"),
        ("EnergyResolution",): ("Energy Resolution", "electron_volt"),
        ("IntegrationTime",): ("Integration Time", "second"),
        ("NumberSpectra",): ("Number of Spectra", None),
        ("ShapingTime",): ("Shaping Time", "second"),
        ("ScanArea",): ("Scan Area", None),
    }
    base = ["ObjectInfo", "AcquireInfo"]

    if try_getting_dict_value(metadata, base) is not None:
        metadata = map_keys_with_units(term_mapping, base, metadata)

    return metadata


def parse_acquire_info(metadata):
    """
    Parse acquisition conditions.

    Parse the metadata that is saved at specific places within
    the .emi tag structure into a consistent place in the metadata dictionary
    returned by :py:meth:`get_ser_metadata`. Specifically looks at the
    "AcquireInfo" node of the metadata structure.

    Parameters
    ----------
    metadata : dict
        A metadata dictionary as returned by :py:meth:`get_ser_metadata`

    Returns
    -------
    metadata : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    # Map input field names to (output_name, unit) tuples
    term_mapping = {
        ("AcceleratingVoltage",): ("Microscope Accelerating Voltage", "volt"),
        ("Tilt1",): ("Microscope Tilt 1", None),
        ("Tilt2",): ("Microscope Tilt 2", None),
    }
    base = ["ObjectInfo", "ExperimentalConditions", "MicroscopeConditions"]

    if try_getting_dict_value(metadata, base) is not None:
        metadata = map_keys_with_units(term_mapping, base, metadata)

    return metadata


def parse_experimental_description(metadata):
    """
    Parse experimental description.

    Parse the metadata that is saved at specific places within
    the .emi tag structure into a consistent place in the metadata dictionary
    returned by :py:meth:`get_ser_metadata`. Specifically looks at the
    "ExperimentalDescription" node of the metadata structure.

    Parameters
    ----------
    metadata : dict
        A metadata dictionary as returned by :py:meth:`get_ser_metadata`

    Returns
    -------
    metadata : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key

    Notes
    -----
    The terms to extract in this section were
    """
    # These terms were captured by looping through a selection of
    # representative .ser/.emi datafiles and running something like the
    # following
    base = ["ObjectInfo", "ExperimentalDescription"]

    experimental_description = try_getting_dict_value(metadata, base)
    if experimental_description is not None and isinstance(
        experimental_description,
        dict,
    ):
        term_mapping = {}
        for k in metadata["ObjectInfo"]["ExperimentalDescription"]:
            term, fei_unit = split_fei_metadata_units(k)
            pint_unit = fei_unit_to_pint(fei_unit)

            # Determine output field name(s)
            if "Stage" in term:
                # Make stage position a nested list
                term = term.replace("Stage ", "")
                out_name = ["Stage Position", term]
            elif "Filter " in term:
                # Make filter settings a nested list
                term = term.replace("Filter ", "")
                out_name = ["Tecnai Filter", term.title()]
            else:
                out_name = term

            term_mapping[(k,)] = (out_name, pint_unit)

        metadata = map_keys_with_units(term_mapping, base, metadata)

        # Microscope Mode often has excess spaces, so fix that if needed:
        if "Mode" in metadata["nx_meta"]:
            metadata["nx_meta"]["Mode"] = metadata["nx_meta"]["Mode"].strip()

    return metadata


def get_emi_from_ser(ser_fname: Path) -> Path:
    """
    Get the accompanying `.emi` filename from an ser filename.

    This method assumes that the `.ser` file will be the same name as the `.emi` file,
    but with an underscore and a digit appended. i.e. ``file.emi`` would
    result in `.ser` files named ``file_1.ser``, ``file_2.ser``, etc.

    Parameters
    ----------
    ser_fname
        The absolute path of an FEI TIA `.ser` data file

    Returns
    -------
    emi_fname
        The absolute path of the accompanying `.emi` metadata file
    index : int
        The number of this .ser file (i.e. 1, 2, 3, etc.)

    Raises
    ------
    FileNotFoundError
        If the accompanying .emi file cannot be resolved to be a file
    """
    # separate filename from extension
    filename = ser_fname.parent / ser_fname.stem
    # remove everything after the last underscore and add the .emi extension
    emi_fname = Path("_".join(str(filename).split("_")[:-1]) + ".emi")
    index = int(str(filename).rsplit("_", maxsplit=1)[-1])

    if not emi_fname.is_file():
        msg = f"Could not find .emi file with expected name: {emi_fname}"
        raise FileNotFoundError(msg)
    return emi_fname, index


def fei_unit_to_pint(fei_unit):
    """
    Convert FEI unit string to Pint unit name.

    Parameters
    ----------
    fei_unit : str or None
        The unit string from FEI metadata (e.g., "kV", "uA", "um", "deg")

    Returns
    -------
    str or None
        The corresponding Pint unit name, or None if no unit or not recognized
    """
    if fei_unit is None:
        return None

    # Map FEI units to Pint unit names
    unit_map = {
        "kV": "kilovolt",
        "V": "volt",
        "uA": "microampere",
        "um": "micrometer",
        "deg": "degree",
        "s": "second",
        "eV": "electron_volt",
        "keV": "kiloelectron_volt",
        "mm": "millimeter",
        "nm": "nanometer",
        "mrad": "milliradian",
    }

    return unit_map.get(fei_unit)


def split_fei_metadata_units(metadata_term):
    """
    Split metadata into value and units.

    If present, separate a metadata term into its value and units.
    In the FEI metadata structure, units are indicated separated by an
    underscore at the end of the term. i.e. ``High tension_kV`` indicates that
    the `High tension` metadata value has units of `kV`.

    Parameters
    ----------
    metadata_term : str
        The metadata term read from the FEI tag structure

    Returns
    -------
    mdata_and_unit : :obj:`tuple` of :obj:`str`
        A length-2 tuple with the metadata value name as the first
        item and the unit (if present) as the second item
    """
    mdata_and_unit = tuple(metadata_term.split("_"))

    if len(mdata_and_unit) == 1:
        mdata_and_unit = (*mdata_and_unit, None)

    # capitalize any words in metadata term that are all lowercase:
    mdata_term = " ".join(
        [w.title() if w.islower() else w for w in mdata_and_unit[0].split()],
    )
    # replace weird "Stem" capitalization
    mdata_term = mdata_term.replace("Stem ", "STEM ")

    return (mdata_term, mdata_and_unit[1])


def map_keys_with_units(term_mapping, base, metadata):
    """
    Map keys into NexusLIMS metadata structure with unit support.

    Maps input metadata terms to NexusLIMS metadata structure, with support
    for (output_name, unit) tuples in the term_mapping values to create Pint
    Quantities.

    Parameters
    ----------
    term_mapping : dict
        Dictionary where keys are tuples of strings (the input terms),
        and values are tuples of (output_name, unit) where output_name
        is either a string or list of strings, and unit is either a string
        (Pint unit name) or None
    base : list
        The 'root' path within the metadata dictionary
    metadata : dict
        A metadata dictionary

    Returns
    -------
    metadata : dict
        The same metadata dictionary with values added to nx_meta
    """
    for in_term in term_mapping:
        out_spec, unit = term_mapping[in_term]
        if isinstance(in_term, tuple):
            in_term = list(in_term)  # noqa: PLW2901
        if isinstance(out_spec, str):
            out_spec = [out_spec]

        val = try_getting_dict_value(metadata, base + in_term)
        # only add the value to this list if we found it
        if val is not None:
            # Clean up string values (remove " um" etc.)
            if isinstance(val, str):
                val = val.replace(" um", "").strip()

            # Convert to numeric first (handles string numbers)
            val = _convert_to_numeric(val)

            # Create Quantity if unit specified and value is numeric
            if unit is not None and isinstance(val, (int, float)):
                with contextlib.suppress(ValueError, TypeError):
                    val = ureg.Quantity(val, unit)

            set_nested_dict_value(
                metadata,
                ["nx_meta", *out_spec],
                val,
            )
    return metadata


def parse_data_type(s, metadata):
    """
    Parse the data type from the signal's metadata.

    Determine `"Data Type"` and `"DatasetType"` for the given .ser file based
    off of metadata and signal characteristics. This method is used to
    determine whether the image is TEM or STEM, Image or Diffraction,
    Spectrum or Spectrum Image, etc.

    Due to lack of appropriate metadata written by the FEI software,
    a heuristic of axis limits and size is used to determine whether a
    spectrum's data type is EELS or EDS. This may not be a perfect
    determination.

    Parameters
    ----------
    s : :py:class:`hyperspy.signal.BaseSignal` (or subclass)
        The HyperSpy signal that contains the data of interest
    metadata : dict
        A metadata dictionary as returned by :py:meth:`get_ser_metadata`

    Returns
    -------
    data_type : str
        The string that should be stored at metadata['nx_meta']['Data Type']
    dataset_type : str
        The string that should be stored at metadata['nx_meta']['DatasetType']
    """
    # default value that will be overwritten if the conditions below are met
    dataset_type = "Misc"

    # instrument configuration
    instr_conf = []
    _set_instrument_type(instr_conf, metadata)

    # images have signal dimension of two:
    if s.axes_manager.signal_dimension == 2:  # noqa: PLR2004
        instr_mod, dataset_type = _signal_dim_2(metadata)

    # if signal dimension is 1, it's a spectrum and not an image
    elif s.axes_manager.signal_dimension == 1:
        instr_mod = ["Spectrum"]
        dataset_type = "Spectrum"
        if s.axes_manager.navigation_dimension > 0:
            instr_mod.append("Imaging")
            dataset_type = "SpectrumImage"
        # do some basic axis value analysis to guess signal type since we
        # don't have any indication of EELS vs. EDS; assume 5 keV and above
        # is EDS
        if s.axes_manager.signal_axes[0].high_value > 5000:  # noqa: PLR2004
            if "EDS" not in instr_conf:
                instr_conf.append("EDS")
        # EELS spectra are usually 2048 channels
        elif s.axes_manager.signal_axes[0].size == 2048:  # noqa: PLR2004
            instr_conf.append("EELS")

    data_type = "_".join(instr_conf + instr_mod)

    return data_type, dataset_type


def _set_instrument_type(instr_conf, metadata):
    # sometimes there is no metadata for follow-on signals in an .emi/.ser
    # bundle (i.e. .ser files after the first one)
    if "Mode" in metadata["nx_meta"]:
        if "STEM" in metadata["nx_meta"]["Mode"]:
            instr_conf.append("STEM")
        elif "TEM" in metadata["nx_meta"]["Mode"]:
            instr_conf.append("TEM")
    # if there is no metadata read from .emi, make determination
    # off of instrument (this is really a guess)
    elif metadata["nx_meta"]["Instrument ID"] is not None:
        if "STEM" in metadata["nx_meta"]["Instrument ID"]:
            instr_conf.append("STEM")
        else:
            instr_conf.append("TEM")
    else:
        # default to TEM, (since STEM is technically a sub-technique of TEM)
        instr_conf.append("TEM")


def _signal_dim_2(metadata) -> Tuple[List[str], str]:
    """
    Parse data type for a Signal with "signal dimension" of size 2.

    Parameters
    ----------
    metadata

    Returns
    -------
    list of str
        The instrument mode
    str
        The dataset type
    """
    # default to an image dataset type for 2 dimensional signal
    dataset_type = "Image"
    # instrument modality:
    instr_mod = ["Imaging"]
    if "Mode" in metadata["nx_meta"]:
        if "Image" in metadata["nx_meta"]["Mode"]:
            instr_mod = ["Imaging"]
            dataset_type = "Image"
        elif "Diffraction" in metadata["nx_meta"]["Mode"]:
            # Diffraction mode is only actually diffraction in TEM mode,
            # In STEM, imaging happens in diffraction mode
            if "STEM" in metadata["nx_meta"]["Mode"]:
                instr_mod = ["Imaging"]
                dataset_type = "Image"
            elif "TEM" in metadata["nx_meta"]["Mode"]:
                instr_mod = ["Diffraction"]
                dataset_type = "Diffraction"
    return instr_mod, dataset_type


def _convert_to_numeric(val):
    if isinstance(val, str):
        if "." in val:
            try:
                return float(val)
            except ValueError:
                return val
        else:
            try:
                return int(val)
            except ValueError:
                return val
    else:
        return val


# Backward compatibility function for tests
def get_ser_metadata(filename):
    """
    Get metadata from a .ser file and its accompanying .emi file.

    .. deprecated::
        This function is deprecated. Use SerEmiExtractor class instead.

    Parameters
    ----------
    filename : pathlib.Path
        path to a file saved in the harvested directory of the instrument

    Returns
    -------
    mdict : dict
        A description of the file's metadata.
    """
    context = ExtractionContext(
        file_path=filename, instrument=get_instr_from_filepath(filename)
    )
    extractor = SerEmiExtractor()
    return extractor.extract(context)
