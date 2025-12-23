"""
Extract metadata from various electron microscopy file types.

Extractors should return a list of dictionaries, where each dictionary contains
the extracted metadata under the key ``nx_meta``. The ``nx_meta`` structure is
validated against the :class:`~nexusLIMS.extractors.schemas.NexusMetadata` Pydantic
schema to ensure consistency across all extractors.

Required Fields
---------------
All extractors must include these fields in ``nx_meta``:

* ``'Creation Time'`` - ISO-8601 timestamp string **with timezone** (e.g.,
  ``"2024-01-15T10:30:00-05:00"`` or ``"2024-01-15T15:30:00Z"``)
* ``'Data Type'`` - Human-readable description using underscores (e.g.,
  ``"STEM_Imaging"``, ``"TEM_EDS"``, ``"SEM_Imaging"``)
* ``'DatasetType'`` - Schema-defined category, must be one of: ``"Image"``,
  ``"Spectrum"``, ``"SpectrumImage"``, ``"Diffraction"``, ``"Misc"``, or ``"Unknown"``

Optional Fields
---------------
Common optional fields include:

* ``'Data Dimensions'`` - Dataset shape as string (e.g., ``"(1024, 1024)"``)
* ``'Instrument ID'`` - Instrument PID from database (e.g., ``"FEI-Titan-TEM-635816"``)
* ``'warnings'`` - List of warning messages or [message, context] pairs

Additional instrument-specific fields are allowed beyond these standard fields.

Schema Validation
-----------------
The ``nx_meta`` structure is validated using Pydantic strict mode. Validation occurs
after default values are set (e.g., missing ``DatasetType`` defaults to ``"Misc"``).
If validation fails, a ``pydantic.ValidationError`` is raised with detailed information
about which fields are invalid.

For complete schema details, see :class:`~nexusLIMS.extractors.schemas.NexusMetadata`.
"""

import base64
import inspect
import json
import logging
import shutil
from datetime import datetime as dt
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import hyperspy.api as hs
import numpy as np
from benedict import benedict
from pydantic import ValidationError

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.registry import get_registry
from nexusLIMS.extractors.schemas import NexusMetadata
from nexusLIMS.instruments import get_instr_from_filepath
from nexusLIMS.utils import current_system_tz, replace_instrument_data_path
from nexusLIMS.version import __version__

from . import utils
from .plugins.preview_generators.hyperspy_preview import sig_to_thumbnail
from .plugins.preview_generators.image_preview import (
    down_sample_image,
    image_to_square_thumbnail,
)
from .plugins.preview_generators.text_preview import text_to_thumbnail

logger = logging.getLogger(__name__)
PLACEHOLDER_PREVIEW = Path(__file__).parent / "assets" / "extractor_error.png"

__all__ = [
    "PLACEHOLDER_PREVIEW",
    "create_preview",
    "down_sample_image",
    "flatten_dict",
    "get_instr_from_filepath",
    "get_registry",
    "image_to_square_thumbnail",
    "logger",
    "parse_metadata",
    "sig_to_thumbnail",
    "text_to_thumbnail",
    "unextracted_preview_map",
    "utils",
    "validate_nx_meta",
]

# filetypes that will only have basic metadata extracted but will nonetheless
# have a custom preview image generated
unextracted_preview_map = {
    "txt": text_to_thumbnail,
    "png": image_to_square_thumbnail,
    "tiff": image_to_square_thumbnail,
    "bmp": image_to_square_thumbnail,
    "gif": image_to_square_thumbnail,
    "jpg": image_to_square_thumbnail,
    "jpeg": image_to_square_thumbnail,
}


def _add_extraction_details(
    nx_meta: Dict,
    extractor_module: Callable,
) -> Dict[str, str]:
    """
    Add extraction details to the NexusLIMS metadata.

    Adds metadata about the extraction process, given an extractor module
    to the ``nx_meta`` metadata dictionary under the ``'NexusLIMS Extraction'``
    sub-key. The ``'Extractor Module'`` metadata key will contain the fully
    qualified path of a given extractor, e.g.
    ``nexusLIMS.extractors.basic_metadata``.

    Note
    ----
    If the ``'NexusLIMS Extraction'`` key already exists in the ``nx_meta``
    metadata dictionary, this method *will* overwrite its value.

    Parameters
    ----------
    nx_meta
        The metadata dictionary as returend by :py:meth:`parse_metadata`
    extractor_module
        The (callable) module for a specific metadata extractor from the
        :py:mod:`~nexusLIMS.extractors` module.

    Returns
    -------
    dict
        An updated ``nx_meta`` dictionary, containing extraction details

    """
    # PHASE 1 MIGRATION: Handle both old-style functions and new-style extractors
    # Try to get the module name in different ways for backward compatibility
    module_name = None

    # Try __module__ attribute first (works for new extractor system)
    if hasattr(extractor_module, "__module__"):
        module_name = extractor_module.__module__

    # Fallback to inspect.getmodule() for old-style functions
    if module_name is None:  # pragma: no cover
        module = inspect.getmodule(extractor_module)  # pragma: no cover
        # Last resort - use "unknown"
        module_name = (  # pragma: no cover
            module.__name__ if module is not None else "unknown"
        )

    nx_meta["nx_meta"]["NexusLIMS Extraction"] = {
        "Date": dt.now(tz=current_system_tz()).isoformat(),
        "Module": module_name,
        "Version": __version__,
    }

    return nx_meta


def validate_nx_meta(
    metadata_dict: dict[str, Any], *, filename: Path | None = None
) -> dict[str, Any]:
    """
    Validate the nx_meta structure against the NexusMetadata schema.

    This function ensures that metadata returned by extractor plugins conforms
    to the required structure defined in
    :class:`~nexusLIMS.extractors.schemas.NexusMetadata`. Validation is
    performed strictly - any schema violations will raise a ValidationError
    with detailed information about the failure.

    Parameters
    ----------
    metadata_dict : dict[str, Any]
        Dictionary containing an 'nx_meta' key with the metadata to validate.
        This is the format returned by all extractor plugins.
    filename : Path or None, optional
        The file path being processed. Used only for error message context.
        If None, error messages will not include file path information.

    Returns
    -------
    dict[str, Any]
        The original metadata_dict, unchanged. Validation does not modify data,
        it only checks conformance to the schema.

    Raises
    ------
    ValidationError
        If the nx_meta structure fails validation. The error message will include
        detailed information about which fields are invalid and why.

    Notes
    -----
    This function validates:

    - **Required fields**: 'Creation Time', 'Data Type', 'DatasetType' must be present
    - **ISO-8601 timestamps**: 'Creation Time' must be valid ISO-8601 with timezone
    - **Controlled vocabularies**: 'DatasetType' must be one of the allowed values
    - **Type constraints**: All fields must match their expected types

    Additional fields beyond the schema are allowed (for instrument-specific metadata).

    Examples
    --------
    Valid metadata passes without modification:

    >>> metadata = {
    ...     "nx_meta": {
    ...         "Creation Time": "2024-01-15T10:30:00-05:00",
    ...         "Data Type": "STEM_Imaging",
    ...         "DatasetType": "Image",
    ...     }
    ... }
    >>> result = validate_nx_meta(metadata)
    >>> result == metadata
    True

    Invalid metadata raises ValidationError:

    >>> bad_metadata = {
    ...     "nx_meta": {
    ...         "Creation Time": "invalid-timestamp",
    ...         "Data Type": "STEM_Imaging",
    ...         "DatasetType": "Image",
    ...     }
    ... }
    >>> validate_nx_meta(bad_metadata)  # doctest: +SKIP
    Traceback (most recent call last):
        ...
    pydantic.ValidationError: ...

    See Also
    --------
    NexusMetadata : The Pydantic schema model for nx_meta validation
    parse_metadata : Main extraction function that uses this validator
    """
    try:
        NexusMetadata.model_validate(metadata_dict["nx_meta"])
    except ValidationError as e:
        # Enhance error message with file context if available
        if filename:
            msg = f"Validation failed for {filename}: {e}"
        else:
            msg = f"Validation failed: {e}"
        logger.exception(msg)
        raise

    return metadata_dict


def parse_metadata(  # noqa: PLR0912
    fname: Path,
    *,
    write_output: bool = True,
    generate_preview: bool = True,
    overwrite: bool = True,
) -> Tuple[Dict[str, Any] | None, Path | list[Path] | None]:
    """
    Parse metadata from a file and optionaly generate a preview image.

    Given an input filename, read the file, determine what "type" of file (i.e.
    what instrument it came from) it is, filter the metadata (if necessary) to
    what we are interested in, and return it as a dictionary (writing to the
    NexusLIMS directory as JSON by default). Also calls the preview
    generation method, if desired.

    For files containing multiple signals (e.g., multi-signal DM3/DM4 files),
    generates one preview per signal and returns a list of preview paths.

    Parameters
    ----------
    fname
        The filename from which to read data
    write_output
        Whether to write the metadata dictionary as a json file in the NexusLIMS
        folder structure
    generate_preview
        Whether to generate the thumbnail preview of this dataset (that
        operation is not done in this method, it is just called from here so
        it can be done at the same time)
    overwrite
        Whether to overwrite the .json metadata file and thumbnail
        image if either exists

    Returns
    -------
    nx_meta : list[dict] or None
        A list of metadata dicts, one per signal in the file. If None,
        the file could not be opened. Single-signal files return a list
        with one dict, multi-signal files return a list with multiple dicts.
    preview_fname : list[Path] or None
        A list of file paths for the generated preview images, one per signal.
        For single-signal files, returns a list with one path. Returns `None`
        if preview generation was not requested.
    """
    extension = fname.suffix[1:]

    # Create extraction context
    instrument = get_instr_from_filepath(fname)
    context = ExtractionContext(file_path=fname, instrument=instrument)

    # Get extractor from registry
    registry = get_registry()
    extractor = registry.get_extractor(context)

    # Extract metadata using the selected extractor
    # All extractors now return a list of dicts (one per signal)
    nx_meta_list = extractor.extract(context)

    # Create a pseudo-module for extraction details tracking
    class ExtractorMethod:
        """Pseudo-module for extraction details tracking."""

        def __init__(self, extractor_name: str):
            # Use the plugin module path for all extractors
            self.__module__ = f"nexusLIMS.extractors.plugins.{extractor_name}"
            self.__name__ = self.__module__

        def __call__(self, f: Path) -> dict:  # noqa: ARG002
            return nx_meta_list  # pragma: no cover

    # Defensive check: extractors should always return a list but handle None gracefully
    if nx_meta_list is None:
        return None, None

    extractor_method = ExtractorMethod(extractor.name)

    # Handle preview generation logic if the extractor is
    # the basic fallback and extension is not in unextracted_preview_map,
    # don't generate a preview
    if extractor.name == "basic_file_info_extractor":
        if extension not in unextracted_preview_map:
            generate_preview = False
            logger.info(
                "No specialized extractor found for file extension; "
                "setting generate_preview to False",
            )
        else:
            generate_preview = True
            logger.info(
                "No specialized extractor found for file extension; "
                "but file extension was in unextracted_preview_map; "
                "setting generate_preview to True",
            )

    # Add extraction details to metadata
    nx_meta_list = [_add_extraction_details(m, extractor_method) for m in nx_meta_list]

    signal_count = len(nx_meta_list)
    preview_fnames = []

    # Set the dataset type to Misc if it was not set by the file reader
    for nx_meta in nx_meta_list:
        if "DatasetType" not in nx_meta["nx_meta"]:
            nx_meta["nx_meta"]["DatasetType"] = "Misc"
            nx_meta["nx_meta"]["Data Type"] = "Miscellaneous"

    # Validate each metadata dict against the schema (strict mode)
    # This happens AFTER setting defaults to allow extractors to omit optional fields
    for nx_meta in nx_meta_list:
        validate_nx_meta(nx_meta, filename=fname)

    # Write output for each signal (single and multi-signal files)
    if write_output:
        for i, nx_meta in enumerate(nx_meta_list):
            # For single-signal files, omit suffix for backward compatibility
            if signal_count == 1:
                out_fname = replace_instrument_data_path(fname, ".json")
            else:
                # For multi-signal files, append signal index to filename
                base_path = replace_instrument_data_path(fname, "")
                out_fname = Path(f"{base_path}_signal{i}.json")

            if not out_fname.exists() or overwrite:
                # Create the directory for the metadata file, if needed
                out_fname.parent.mkdir(parents=True, exist_ok=True)
                # Make sure that the nx_meta dict comes first in the json output
                out_dict = {"nx_meta": nx_meta["nx_meta"]}
                for k, v in nx_meta.items():
                    if k == "nx_meta":
                        pass
                    else:
                        out_dict[k] = v
                with out_fname.open(mode="w", encoding="utf-8") as f:
                    logger.debug("Dumping metadata to %s", out_fname)
                    json.dump(
                        out_dict,
                        f,
                        sort_keys=False,
                        indent=2,
                        cls=_CustomEncoder,
                    )

    # Generate previews for each signal
    if generate_preview:
        for i in range(signal_count):
            # For single-signal files, omit suffix for backward compatibility
            signal_idx = i if signal_count > 1 else None
            preview = create_preview(
                fname=fname,
                overwrite=overwrite,
                signal_index=signal_idx,
            )
            preview_fnames.append(preview)
    else:
        preview_fnames = [None] * signal_count

    return nx_meta_list, preview_fnames


def create_preview(  # noqa: PLR0911, PLR0912, PLR0915
    fname: Path, *, overwrite: bool, signal_index: int | None = None
) -> Path | None:
    """
    Generate a preview image for a given file using the plugin system.

    This method uses the preview generator plugin system to create thumbnail
    previews. It first tries to find a suitable preview generator plugin, and
    falls back to legacy methods if no plugin is found.

    Parameters
    ----------
    fname
        The filename from which to read data
    overwrite
        Whether to overwrite the .json metadata file and thumbnail
        image if either exists
    signal_index
        For files with multiple signals, the index of the signal to preview.
        If None, generates a single preview (legacy behavior). If an int,
        generates preview with _signalN suffix in filename.

    Returns
    -------
    preview_fname : Optional[pathlib.Path]
        The filename of the generated preview image; if None, a preview could not be
        successfully generated.
    """
    # Generate preview filename with signal index suffix if provided
    if signal_index is None:
        preview_fname = replace_instrument_data_path(fname, ".thumb.png")
    else:
        preview_fname = replace_instrument_data_path(
            fname, f"_signal{signal_index}.thumb.png"
        )

    # Skip if preview exists and overwrite is False
    if preview_fname.is_file() and not overwrite:
        logger.info("Preview already exists: %s", preview_fname)
        return preview_fname

    # Create context for preview generation
    instrument = get_instr_from_filepath(fname)
    context = ExtractionContext(
        file_path=fname, instrument=instrument, signal_index=signal_index
    )

    # Try to get a preview generator from the registry
    registry = get_registry()
    generator = registry.get_preview_generator(context)

    if generator:
        # Use plugin-based preview generation
        logger.info("Generating preview using %s: %s", generator.name, preview_fname)
        # Create the directory for the thumbnail, if needed
        preview_fname.parent.mkdir(parents=True, exist_ok=True)

        success = generator.generate(context, preview_fname)
        if success:
            return preview_fname

        logger.warning(
            "Preview generator %s failed for %s",
            generator.name,
            fname,
        )
        # Fall through to legacy methods

    # Legacy fallback for .tif files (special case with downsampling)
    extension = fname.suffix[1:]
    if extension == "tif":
        logger.info("Using legacy downsampling for .tif: %s", preview_fname)
        preview_fname.parent.mkdir(parents=True, exist_ok=True)
        factor = 2
        down_sample_image(fname, out_path=preview_fname, factor=factor)
        return preview_fname

    # Legacy fallback for files in unextracted_preview_map
    if extension in unextracted_preview_map:
        logger.info("Using legacy preview map for %s: %s", extension, preview_fname)
        preview_fname.parent.mkdir(parents=True, exist_ok=True)
        preview_return = unextracted_preview_map[extension](
            f=fname,
            out_path=preview_fname,
            output_size=500,
        )

        # handle the case where PIL cannot open an image
        if preview_return is False:
            return None

        return preview_fname

    # Legacy fallback for HyperSpy-loadable files
    logger.info("Trying legacy HyperSpy preview generation: %s", preview_fname)
    load_options = {"lazy": True}
    if extension == "ser":
        load_options["only_valid_data"] = True

    # noinspection PyBroadException
    try:
        s = hs.load(fname, **load_options)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Signal could not be loaded by HyperSpy. "
            "Using placeholder image for preview.",
        )
        preview_fname.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PLACEHOLDER_PREVIEW, preview_fname)
        return preview_fname

    # If s is a list of signals, select the appropriate one
    if isinstance(s, list):
        num_sigs = len(s)
        original_fname = s[0].metadata.General.original_filename
        if signal_index is not None:
            # Use specified signal index
            s = s[signal_index]
            s.metadata.General.title = (
                s.metadata.General.title
                + f" (signal {signal_index + 1} of "
                + f'{num_sigs} in file "{original_fname}")'
            )
        else:
            # Legacy: use first signal only
            s = s[0]
            s.metadata.General.title = (
                s.metadata.General.title
                + f' (1 of {num_sigs} total signals in file "{original_fname}")'
            )
    elif not s.metadata.General.title:
        s.metadata.General.title = s.metadata.General.original_filename.replace(
            extension,
            "",
        ).strip(".")

    # Generate the preview
    logger.info("Generating HyperSpy preview: %s", preview_fname)
    preview_fname.parent.mkdir(parents=True, exist_ok=True)
    s.compute(show_progressbar=False)
    sig_to_thumbnail(s, out_path=preview_fname)

    return preview_fname


def flatten_dict(_dict, parent_key="", separator=" "):  # noqa: ARG001
    """
    Flatten a nested dictionary into a single level.

    Utility method to take a nested dictionary structure and flatten it into a
    single level, separating the levels by a string as specified by
    ``separator``.

    Uses python-benedict for robust nested dictionary operations.

    Parameters
    ----------
    _dict : dict
        The dictionary to flatten
    parent_key : str
        The "root" key to add to the existing keys (unused in current implementation)
    separator : str
        The string to use to separate values in the flattened keys (i.e.
        {'a': {'b': 'c'}} would become {'a' + sep + 'b': 'c'})

    Returns
    -------
    flattened_dict : str
        The dictionary with depth one, with nested dictionaries flattened
        into root-level keys
    """
    # Disable keypath_separator to avoid conflicts with keys containing
    # dots or other special chars
    return benedict(_dict, keypath_separator=None).flatten(separator=separator)


class _CustomEncoder(json.JSONEncoder):
    """
    Allow non-serializable types to be written in a JSON format.

    A custom JSON Encoder class that will allow certain types to be serialized that are
    not able to be by default (taken from https://stackoverflow.com/a/27050186).
    """

    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bytes_):
            return o.decode()
        if isinstance(o, np.void):
            # np.void array may contain arbitary binary, so base64 encode it
            return base64.b64encode(o.tolist()).decode("utf-8")

        return super().default(o)
