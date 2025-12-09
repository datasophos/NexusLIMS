"""
Extract metadata from various electron microscopy file types.

Extractors should return a dictionary containing the values to be displayed
in NexusLIMS as a sub-dictionary under the key ``nx_meta``. The remaining keys
will be for the metadata as extracted. Under ``nx_meta``, a few keys are
expected (although not enforced):

* ``'Creation Time'`` - ISO format date and time as a string
* ``'Data Type'`` - a human-readable description of the data type separated by
  underscores - e.g "STEM_Imaging", "TEM_EDS", etc.
* ``'DatasetType'`` - determines the value of the Type attribute for the dataset
  (defined in the schema)
* ``'Data Dimensions'`` - dimensions of the dataset, surrounded by parentheses,
  separated by commas as a string- e.g. '(12, 1024, 1024)'
* ``'Instrument ID'`` - instrument PID pulled from the instrument database
"""

import base64
import inspect
import json
import logging
import shutil
from collections import abc
from datetime import datetime as dt
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

import hyperspy.api as hs
import numpy as np

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
from .registry import get_registry

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
    "thumbnail_generator",
    "unextracted_preview_map",
    "utils",
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
        if module is not None:  # pragma: no cover
            module_name = module.__name__  # pragma: no cover
        else:
            # Last resort - use "unknown"
            module_name = "unknown"

    nx_meta["nx_meta"]["NexusLIMS Extraction"] = {
        "Date": dt.now(tz=current_system_tz()).isoformat(),
        "Module": module_name,
        "Version": __version__,
    }

    return nx_meta


def parse_metadata(
    fname: Path,
    *,
    write_output: bool = True,
    generate_preview: bool = True,
    overwrite: bool = True,
) -> Tuple[Dict[str, Any] | None, Path | None]:
    """
    Parse metadata from a file and optionaly generate a preview image.

    Given an input filename, read the file, determine what "type" of file (i.e.
    what instrument it came from) it is, filter the metadata (if necessary) to
    what we are interested in, and return it as a dictionary (writing to the
    NexusLIMS directory as JSON by default). Also calls the preview
    generation method, if desired.

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
    nx_meta : dict or None
        The "relevant" metadata that is of use for NexusLIMS. If None,
        the file could not be opened
    preview_fname : Path or None
        The file path of the generated preview image, or `None` if it was not
        requested
    """
    from nexusLIMS.extractors.base import ExtractionContext

    extension = fname.suffix[1:]

    # Create extraction context
    instrument = get_instr_from_filepath(fname)
    context = ExtractionContext(file_path=fname, instrument=instrument)

    # Get extractor from registry
    registry = get_registry()
    extractor = registry.get_extractor(context)

    # Extract metadata using the selected extractor
    nx_meta = extractor.extract(context)

    # Create a pseudo-module for extraction details tracking
    class ExtractorMethod:
        """Pseudo-module for extraction details tracking."""

        def __init__(self, extractor_name: str):
            # Use the plugin module path for all extractors
            self.__module__ = f"nexusLIMS.extractors.plugins.{extractor_name}"
            self.__name__ = self.__module__

        def __call__(self, f: Path) -> dict:  # noqa: ARG002
            return nx_meta  # pragma: no cover

    extractor_method = ExtractorMethod(extractor.name)

    # Handle preview generation logic
    # If the extractor is the basic fallback and extension is not in unextracted_preview_map,
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

    nx_meta = _add_extraction_details(nx_meta, extractor_method)
    preview_fname = None

    # nx_meta should never be None, because the extractors are defensive and
    # will always return _something_
    if nx_meta is not None:
        # Set the dataset type to Misc if it was not set by the file reader
        if "DatasetType" not in nx_meta["nx_meta"]:
            nx_meta["nx_meta"]["DatasetType"] = "Misc"
            nx_meta["nx_meta"]["Data Type"] = "Miscellaneous"

        if write_output:
            out_fname = replace_instrument_data_path(fname, ".json")

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

    if generate_preview:
        preview_fname = create_preview(fname=fname, overwrite=overwrite)

    return nx_meta, preview_fname


def create_preview(fname: Path, *, overwrite: bool) -> Path | None:
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

    Returns
    -------
    preview_fname : Optional[pathlib.Path]
        The filename of the generated preview image; if None, a preview could not be
        successfully generated.
    """
    from nexusLIMS.extractors.base import ExtractionContext
    from nexusLIMS.extractors.registry import get_registry
    from nexusLIMS.instruments import get_instr_from_filepath

    preview_fname = replace_instrument_data_path(fname, ".thumb.png")

    # Skip if preview exists and overwrite is False
    if preview_fname.is_file() and not overwrite:
        logger.info("Preview already exists: %s", preview_fname)
        return preview_fname

    # Create context for preview generation
    instrument = get_instr_from_filepath(fname)
    context = ExtractionContext(file_path=fname, instrument=instrument)

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

    # If s is a list of signals, use just the first one for our purposes
    if isinstance(s, list):
        num_sigs = len(s)
        fname = s[0].metadata.General.original_filename
        s = s[0]
        s.metadata.General.title = (
            s.metadata.General.title
            + f' (1 of {num_sigs} total signals in file "{fname}")'
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


def flatten_dict(_dict, parent_key="", separator=" "):
    """
    Flatten a nested dictionary into a single level.

    Utility method to take a nested dictionary structure and flatten it into a
    single level, separating the levels by a string as specified by
    ``separator``.

    Cribbed from: https://stackoverflow.com/a/6027615/1435788

    Parameters
    ----------
    _dict : dict
        The dictionary to flatten
    parent_key : str
        The "root" key to add to the existing keys
    separator : str
        The string to use to separate values in the flattened keys (i.e.
        {'a': {'b': 'c'}} would become {'a' + sep + 'b': 'c'})

    Returns
    -------
    flattened_dict : str
        The dictionary with depth one, with nested dictionaries flattened
        into root-level keys
    """
    items = []
    for k, v in _dict.items():
        new_key = parent_key + separator + k if parent_key else k
        if isinstance(v, abc.MutableMapping):
            items.extend(flatten_dict(v, new_key, separator=separator).items())
        else:
            items.append((new_key, v))

    return dict(items)


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
