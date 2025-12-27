"""Methods (primarily intended to be private) that are used by the other extractors."""

import contextlib
import logging
import re
import shutil
import tarfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List

from rsciio.digitalmicrograph._api import (  # pylint: disable=import-error,no-name-in-module
    DigitalMicrographReader,
    ImageObject,
)

from nexusLIMS.instruments import Instrument, get_instr_from_filepath
from nexusLIMS.schemas.units import ureg
from nexusLIMS.utils import set_nested_dict_value, try_getting_dict_value

logger = logging.getLogger(__name__)


def _coerce_to_list(meta_key):
    if isinstance(meta_key, str):
        return [meta_key]
    return meta_key


def _get_mtime_iso(filename: Path, instrument: Instrument | None = None):
    return datetime.fromtimestamp(
        filename.stat().st_mtime,
        tz=instrument.timezone if instrument else UTC,
    ).isoformat()


def _set_instr_name_and_time(mdict: Dict, filename: Path):
    instr = get_instr_from_filepath(filename)
    # if we found the instrument, then store the name as string, else None
    instr_name = instr.name if instr is not None else None

    mdict["nx_meta"]["Instrument ID"] = instr_name
    mdict["nx_meta"]["Creation Time"] = _get_mtime_iso(filename, instr)
    mdict["nx_meta"]["warnings"] = []


def _set_acquisition_device_name(mdict: Dict, pre_path: List[str]):
    val = try_getting_dict_value(mdict, [*pre_path, "Acquisition", "Device", "Name"])
    if val is None:
        val = try_getting_dict_value(mdict, [*pre_path, "DataBar", "Device Name"])
    if val is not None:
        set_nested_dict_value(mdict, ["nx_meta", "Acquisition Device"], val)


def _set_exposure_time(mdict: Dict, pre_path: List[str]):
    val = try_getting_dict_value(
        mdict,
        [*pre_path, "Acquisition", "Parameters", "High Level", "Exposure (s)"],
    )
    if val is None:
        val = try_getting_dict_value(mdict, [*pre_path, "DataBar", "Exposure Time (s)"])
    if val is not None:
        # Convert to Pint Quantity with seconds unit
        with contextlib.suppress(ValueError, TypeError):
            val = ureg.Quantity(val, "second")
        set_nested_dict_value(mdict, ["nx_meta", "Exposure Time"], val)


def _set_gms_version(mdict: Dict, pre_path: List[str]):
    val = try_getting_dict_value(mdict, [*pre_path, "GMS Version", "Created"])
    if val is not None:
        set_nested_dict_value(mdict, ["nx_meta", "GMS Version"], val)


def _set_camera_binning(mdict: Dict, pre_path: List[str]):
    val = try_getting_dict_value(
        mdict,
        [*pre_path, "Acquisition", "Parameters", "High Level", "Binning"],
    )
    if val is not None:
        set_nested_dict_value(mdict, ["nx_meta", "Binning (Horizontal)"], val[0])
        set_nested_dict_value(mdict, ["nx_meta", "Binning (Vertical)"], val[1])


def _set_image_processing(mdict: Dict, pre_path: List[str]):
    #   ImageTags.Acquisition.Parameters["High Level"].Processing will be
    #   something like "Gain normalized" - not just for EELS so move this to
    #   general
    val = try_getting_dict_value(
        mdict,
        [*pre_path, "Acquisition", "Parameters", "High Level", "Processing"],
    )
    if val is not None:
        set_nested_dict_value(mdict, ["nx_meta", "Camera/Detector Processing"], val)


def _set_eels_meta(mdict, base, meta_key):
    val = try_getting_dict_value(mdict, base + meta_key)
    # only add the value to this list if we found it, and it's not
    # one of the "facility-wide" set values that do not have any meaning:
    if val is not None:
        field_name = meta_key[-1]
        # Convert to Pint Quantity if the field has units
        unit_map = {
            "Exposure (s)": "second",
            "Integration time (s)": "second",
            "Collection semi-angle (mrad)": "milliradian",
            "Convergence semi-angle (mrad)": "milliradian",
        }
        if field_name in unit_map:
            with contextlib.suppress(ValueError, TypeError):
                val = ureg.Quantity(val, unit_map[field_name])
                # Remove unit suffix from field name
                field_name = field_name.rsplit(" (", 1)[0]
        # add last value of each parameter to the "EELS" sub-tree of nx_meta
        set_nested_dict_value(mdict, ["nx_meta", "EELS", field_name], val)


def _set_eels_spectrometer_meta(mdict, base, meta_key):
    val = try_getting_dict_value(mdict, base + meta_key)
    if val is not None:
        field_name = meta_key[0]
        # Convert to Pint Quantity if the field has units
        unit_map = {
            "Energy loss (eV)": "electron_volt",
            "Drift tube voltage (V)": "volt",
            "Slit width (eV)": "electron_volt",
            "Prism offset (V)": "volt",
        }
        if field_name in unit_map:
            with contextlib.suppress(ValueError, TypeError):
                val = ureg.Quantity(val, unit_map[field_name])
                # Remove unit suffix from field name
                field_name = field_name.rsplit(" (", 1)[0]
        # add last value of each param to the "EELS" sub-tree of nx_meta
        set_nested_dict_value(
            mdict,
            ["nx_meta", "EELS", "Spectrometer " + field_name],
            val,
        )


def _set_eels_processing(mdict, pre_path):
    # Process known tags under "processing":
    #   ImageTags.Processing will be a list of things done (in multiple
    #   TagGroups) - things like Compute thickness, etc.
    val = try_getting_dict_value(mdict, [*pre_path, "Processing"])
    if val is not None and isinstance(val, dict):
        # if val is a dict, then there were processing steps applied
        eels_ops = []
        for _, v in val.items():
            # k will be TagGroup0, TagGroup1, etc.
            # v will be dictionaries specifying the process step
            # AlignSIByPeak, DataPicker, SpectrumCalibrate,
            # Compute Thickness, Background Removal, Signal Integration
            operation = v["Operation"]
            param = v["Parameters"]
            if operation == "AlignSIByPeak":
                eels_ops.append("Aligned parent SI By Peak")
            elif operation == "Background Removal":
                val = try_getting_dict_value(param, ["Model"])
                if val is not None:
                    set_nested_dict_value(
                        mdict,
                        ["nx_meta", "EELS", "Background Removal Model"],
                        val,
                    )
                eels_ops.append(operation)
            elif operation == "SpectrumCalibrate":
                eels_ops.append("Calibrated Post-acquisition")
            elif operation == "Compute Thickness":
                mdict = _process_thickness_metadata(mdict, [*pre_path, "EELS"])
                eels_ops.append(operation)
            elif operation == "DataPicker":
                eels_ops.append("Extracted from SI")
            elif operation == "Signal Integration":
                eels_ops.append(operation)
        if eels_ops:
            # remove duplicates (convert to set) and sort alphabetically:
            set_nested_dict_value(
                mdict,
                ["nx_meta", "EELS", "Processing Steps"],
                ", ".join(sorted(set(eels_ops))),
            )


def _process_thickness_metadata(mdict, base):
    abs_thick = try_getting_dict_value(
        mdict,
        [*base, "Thickness", "Absolute", "Measurement"],
    )
    abs_units = try_getting_dict_value(mdict, [*base, "Thickness", "Absolute", "Units"])
    abs_mfp = try_getting_dict_value(
        mdict,
        [*base, "Thickness", "Absolute", "Mean Free Path"],
    )
    rel_thick = try_getting_dict_value(
        mdict,
        [*base, "Thickness", "Relative", "Measurement"],
    )
    if abs_thick is not None:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "EELS", f"Thickness (absolute) [{abs_units}]"],
            abs_thick,
        )
    if abs_mfp is not None:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "EELS", "Thickness (absolute) mean free path"],
            abs_mfp[0],
        )
    if rel_thick is not None:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "EELS", "Thickness (relative) [t/λ]"],
            rel_thick,
        )

    return mdict


def _set_eds_meta(mdict, base, meta_key):
    val = try_getting_dict_value(mdict, base + meta_key)
    # only add the value to this list if we found it, and it's not
    # one of the "facility-wide" set values that do not have any meaning:
    if val is not None:
        field_name = meta_key[-1] if len(meta_key) > 1 else meta_key[0]
        # Convert to Pint Quantity if the field has units
        unit_map = {
            "Dispersion (eV)": "electron_volt",
            "Energy Cutoff (V)": "volt",
            "Exposure (s)": "second",
            "Azimuthal angle": "degree",
            "Elevation angle": "degree",
            "Incidence angle": "degree",
            "Stage tilt": "degree",
            "Live time": "second",
            "Real time": "second",
        }
        if field_name in unit_map:
            with contextlib.suppress(ValueError, TypeError):
                val = ureg.Quantity(val, unit_map[field_name])
                # Remove unit suffix from field name if present
                field_name = field_name.rsplit(" (", 1)[0]
        # add last value of each parameter to the "EDS" sub-tree of nx_meta
        set_nested_dict_value(
            mdict,
            ["nx_meta", "EDS", field_name],
            val,
        )


def _set_si_meta(mdict, pre_path, meta_key):
    val = try_getting_dict_value(mdict, [*pre_path, "SI", *meta_key])
    if val is not None:
        field_name = meta_key[-1]
        # Convert to Pint Quantity if the field has units
        unit_map = {
            "Dispersion (eV)": "electron_volt",
            "Energy Cutoff (V)": "volt",
            "Exposure (s)": "second",
        }
        if field_name in unit_map:
            with contextlib.suppress(ValueError, TypeError):
                val = ureg.Quantity(val, unit_map[field_name])
                # Remove unit suffix from field name
                field_name = field_name.rsplit(" (", 1)[0]
        # add last value of each parameter to the "EDS" sub-tree of
        # nx_meta
        set_nested_dict_value(mdict, ["nx_meta", "EDS", field_name], val)


def _try_decimal(val):
    try:
        val = Decimal(val)
        val = float(val)
    except (ValueError, InvalidOperation):
        pass
    return val


def _parse_filter_settings(info_dict, tecnai_info):
    try:
        info_dict["Filter_Settings"] = {}
        tecnai_filter_info = tecnai_info[
            tecnai_info.index("Filter related settings:") + 1 :
        ]
        # String
        info_dict["Filter_Settings"]["Mode"] = _find_val("Mode: ", tecnai_filter_info)
        # Decimal (eV/channel)  # noqa: ERA001
        tmp = _find_val("Selected dispersion: ", tecnai_filter_info)
        if tmp is not None:
            tmp = re.sub(r"\[eV/Channel\]", "", tmp)
            info_dict["Filter_Settings"]["Dispersion"] = _try_decimal(tmp)

        # Decimal (millimeter)  # noqa: ERA001
        tmp = _find_val("Selected aperture: ", tecnai_filter_info)
        if tmp is not None:
            tmp = tmp.strip("m")
            info_dict["Filter_Settings"]["Aperture"] = _try_decimal(tmp)

        # Decimal (eV)  # noqa: ERA001
        tmp = _find_val("Prism shift: ", tecnai_filter_info)
        if tmp is not None:
            tmp = re.sub(r"\[eV\]", "", tmp)
            info_dict["Filter_Settings"]["Prism_Shift"] = _try_decimal(tmp)

        # Decimal (eV)  # noqa: ERA001
        tmp = _find_val("Drift tube: ", tecnai_filter_info)
        if tmp is not None:
            tmp = re.sub(r"\[eV\]", "", tmp)
            info_dict["Filter_Settings"]["Drift_Tube"] = _try_decimal(tmp)

        # Decimal (eV)  # noqa: ERA001
        tmp = _find_val("Total energy loss: ", tecnai_filter_info)
        if tmp is not None:
            tmp = re.sub(r"\[eV\]", "", tmp)
            info_dict["Filter_Settings"]["Total_Energy_Loss"] = _try_decimal(tmp)
    except ValueError:
        logger.info("Filter settings not found in Tecnai microscope info")

    return info_dict


def _zero_data_in_dm3(
    filename: Path,
    out_filename: Path | None = None,
    *,
    compress=True,
) -> Path:
    """
    Zero out data in a DM3 file.

    Helper method that will overwrite the data in a dm3 image file  with
    zeros and save it as either another dm3, or as a compressed archive (used
    for creating files for the test suite that don't take up tons of space).
    Since the resulting file is just some text metadata and zeros, it should
    be highly compressible (initial tests allowed for a 16MB file to be
    compressed to ~100KB).

    Parameters
    ----------
    filename
        Path to file to be modified
    out_filename
        Name with which to save the output file. If None, it will be
        automatically generated from the ``filename``.
    compress
        Whether to compress the files into a tar.gz file

    Returns
    -------
    Path
        The path of the compressed (or zeroed) file
    """
    # zero out extent of data in DM3 file and compress to tar.gz:
    if not out_filename:
        mod_fname = filename.parent / (filename.stem + "_dataZeroed" + filename.suffix)
    else:
        mod_fname = out_filename

    shutil.copyfile(filename, mod_fname)

    # Do some lower-level reading on the .dm3 file to get the ImageObject refs
    with filename.open(mode="rb") as f:
        dm_reader = DigitalMicrographReader(f)
        dm_reader.parse_file()
        images = [
            ImageObject(im_dict, f) for im_dict in dm_reader.get_image_dictionaries()
        ]

    # write zeros to the file in the data block (offset + size in bytes
    # information is obtained from the ImageObject ref)
    # NB: currently this is just tested for single-image .dm3 files. Spectra
    # and image stacks will probably work differently.
    with mod_fname.open(mode="r+b") as f:
        f.seek(images[0].imdict.ImageData.Data.offset)
        f.write(b"\x00" * images[0].imdict.ImageData.Data.size_bytes)

    # compress the output, if requested
    if compress:
        tar_path = Path(f"{mod_fname}.tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(mod_fname)
        out_fpath = tar_path
        mod_fname.unlink()
    else:
        out_fpath = mod_fname

    return out_fpath


def _find_val(s_to_find, list_to_search):
    """
    Find a value in a list.

    Return the first value in list_to_search that contains s_to_find, or
    None if it is not found.

    Note: If needed, this could be improved to use regex instead, which
          would provide more control over the patterns to return
    """
    res = [x for x in list_to_search if s_to_find in x]
    if len(res) > 0:
        res = res[0]
        # remove the string we searched for from the beginning of the res
        return re.sub("^" + s_to_find, "", res)

    return None


# Field categorization helpers for schema-based metadata extraction


def classify_field(
    field_name: str,
    dataset_type: str,
) -> tuple[bool, str | None]:
    """
    Determine if a field belongs to the core schema or extensions.

    This function helps extractor plugins categorize metadata fields by checking
    if they are defined in the type-specific schema for a given dataset type.
    Fields not in the core schema should be placed in the 'extensions' section.

    Parameters
    ----------
    field_name : str
        The field name to classify. Should use EM Glossary naming conventions
        (snake_case) for core fields (e.g., 'acceleration_voltage',
        'working_distance').
    dataset_type : str
        The dataset type this field belongs to. Should be one of: 'Image',
        'Spectrum', 'SpectrumImage', 'Diffraction', 'Misc', or 'Unknown'.

    Returns
    -------
    is_core : bool
        True if the field is defined in the core schema for this dataset type,
        False if it should be placed in the extensions section.
    em_glossary_id : str or None
        The EM Glossary ID for the field if it's a standardized term
        (e.g., "EMG_00000004" for acceleration_voltage), or None if the field
        is not in the EM Glossary or is not a core field.

    Examples
    --------
    Check if a field is core or extension for an Image dataset:

    >>> classify_field("acceleration_voltage", "Image")
    (True, 'EMG_00000004')

    >>> classify_field("spot_size", "Image")
    (False, None)

    Check spectrum-specific fields:

    >>> classify_field("acquisition_time", "Spectrum")
    (True, 'EMG_00000055')

    >>> classify_field("detector_model", "Spectrum")
    (False, None)

    Notes
    -----
    This function uses the Pydantic model_fields attribute to determine if a
    field is part of the schema. For fields not in the core schema, extractors
    should use the extensions section:

    .. code-block:: python

        is_core, em_glossary_id = classify_field("custom_param", "Image")
        if is_core:
            nx_meta[field_name] = value
        else:
            add_to_extensions(nx_meta, field_name, value)

    See Also
    --------
    add_to_extensions : Helper to add fields to the extensions section
    get_schema_fields : Get all valid field names for a dataset type
    """
    from nexusLIMS.schemas import em_glossary
    from nexusLIMS.schemas.metadata import (
        DiffractionMetadata,
        ImageMetadata,
        NexusMetadata,
        SpectrumImageMetadata,
        SpectrumMetadata,
    )

    # Map dataset types to their schema classes
    schema_map: dict[str, type[Any]] = {
        "Image": ImageMetadata,
        "Spectrum": SpectrumMetadata,
        "SpectrumImage": SpectrumImageMetadata,
        "Diffraction": DiffractionMetadata,
        "Misc": NexusMetadata,
        "Unknown": NexusMetadata,
    }

    schema_class = schema_map.get(dataset_type)
    if schema_class is None:
        # Unknown dataset type - treat as extension
        return (False, None)

    # Check if field is in the schema using model_fields
    is_core = field_name in schema_class.model_fields

    # Try to get EM Glossary ID for core fields
    em_glossary_id = None
    if is_core:
        try:
            # Look up the EM Glossary ID using the em_glossary module
            em_glossary_id = em_glossary.FIELD_ID_MAP.get(field_name)
        except (AttributeError, KeyError):
            # Field doesn't have an EM Glossary ID, which is fine
            pass

    return (is_core, em_glossary_id)


def add_to_extensions(nx_meta: dict, field_name: str, value: Any) -> None:  # noqa: ANN401
    """
    Add a field to the extensions section of nx_meta.

    This is a convenience function that ensures the extensions dict exists
    before adding a field. Use this for vendor-specific, instrument-specific,
    or facility-specific metadata that doesn't fit the core schema.

    Parameters
    ----------
    nx_meta : dict
        The nx_meta dictionary being built by the extractor. Will be modified
        in place to add the field to the extensions section.
    field_name : str
        Name of the field to add. Use descriptive names that clearly indicate
        the field's meaning (e.g., 'quanta_spot_size', 'detector_contrast').
    value : Any
        The value to store. Can be any JSON-serializable type, including
        Pint Quantity objects which will be automatically serialized.

    Examples
    --------
    Add vendor-specific fields during metadata extraction:

    >>> nx_meta = {
    ...     "DatasetType": "Image",
    ...     "Data Type": "SEM_Imaging",
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ... }
    >>> add_to_extensions(nx_meta, "spot_size", 3.5)
    >>> add_to_extensions(nx_meta, "detector_contrast", 50.0)
    >>> nx_meta["extensions"]
    {'spot_size': 3.5, 'detector_contrast': 50.0}

    Works with Pint Quantities:

    >>> from nexusLIMS.schemas.units import ureg
    >>> add_to_extensions(nx_meta, "chamber_pressure", ureg.Quantity(79.8, "pascal"))

    Notes
    -----
    The extensions section preserves all metadata that doesn't fit the core
    schema, ensuring no data loss during extraction. Extensions are included
    in the XML output and preserved through the record building process.

    See Also
    --------
    classify_field : Determine if a field should be core or extension
    """
    # Ensure extensions dict exists
    if "extensions" not in nx_meta:
        nx_meta["extensions"] = {}

    # Add the field
    nx_meta["extensions"][field_name] = value


def get_schema_fields(dataset_type: str) -> set[str]:
    """
    Get all valid field names for a dataset type's schema.

    This function returns the complete set of field names defined in the
    type-specific schema, useful for bulk field categorization or validation.

    Parameters
    ----------
    dataset_type : str
        The dataset type ("Image", "Spectrum", "SpectrumImage", "Diffraction",
        "Misc", or "Unknown"). For "Misc" and "Unknown", returns the base
        NexusMetadata schema fields.

    Returns
    -------
    set of str
        Set of all valid field names in the schema. This includes both required
        and optional fields defined in the type-specific schema.

    Examples
    --------
    Get all valid fields for an Image dataset:

    >>> fields = get_schema_fields("Image")
    >>> "acceleration_voltage" in fields
    True
    >>> "working_distance" in fields
    True

    Get fields for a Spectrum dataset:

    >>> fields = get_schema_fields("Spectrum")
    >>> "acquisition_time" in fields
    True
    >>> "live_time" in fields
    True

    Use for bulk field processing:

    >>> dataset_type = "Image"
    >>> schema_fields = get_schema_fields(dataset_type)
    >>> for field_name, value in extracted_data.items():
    ...     if field_name in schema_fields:
    ...         nx_meta[field_name] = value
    ...     else:
    ...         add_to_extensions(nx_meta, field_name, value)

    Notes
    -----
    This function is particularly useful when migrating extractors to use the
    extensions system, or when building extractors that process many fields
    from vendor metadata dictionaries.

    See Also
    --------
    classify_field : Check if individual fields are core or extension
    """
    from nexusLIMS.schemas.metadata import (
        DiffractionMetadata,
        ImageMetadata,
        NexusMetadata,
        SpectrumImageMetadata,
        SpectrumMetadata,
    )

    schema_map: dict[str, type[Any]] = {
        "Image": ImageMetadata,
        "Spectrum": SpectrumMetadata,
        "SpectrumImage": SpectrumImageMetadata,
        "Diffraction": DiffractionMetadata,
        "Misc": NexusMetadata,
        "Unknown": NexusMetadata,
    }

    # Get the schema class, defaulting to base NexusMetadata
    schema_class = schema_map.get(dataset_type, NexusMetadata)

    # Return the set of all field names in the schema
    return set(schema_class.model_fields.keys())
