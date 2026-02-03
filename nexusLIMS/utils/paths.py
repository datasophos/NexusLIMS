"""Path manipulation utilities for NexusLIMS."""

import logging
from pathlib import Path
from typing import List, Union

from nexusLIMS.config import settings

_logger = logging.getLogger(__name__)


def is_subpath(path: Path, of_paths: Union[Path, List[Path]]):
    """
    Return if this path is a subpath of other paths.

    Helper function to determine if a given path is a "subpath" of a set of
    paths. Useful to help determine which instrument a given file comes from,
    given the instruments ``filestore_path`` and the path of the file to test.

    Parameters
    ----------
    path
        The path of the file (or directory) to test. This will usually be the
        absolute path to a file on the local filesystem (to be compared using
        the host-specific ``nx_instrument_data_path``.
    of_paths
        The "higher-level" path to test against (or list thereof). In typical
        use, this will be a path joined of an instruments ``filestore_path``
        with the root-level ``nx_instrument_data_path``

    Returns
    -------
    result : bool
        Whether or not path is a subpath of one of the directories in of_paths

    Examples
    --------
    >>> is_subpath(Path('/path/to/file.dm3'),
    ...            settings.NX_INSTRUMENT_DATA_PATH /
    ...                titan.filestore_path))
    True
    """
    if isinstance(of_paths, Path):
        of_paths = [of_paths]

    return any(subpath in path.parents for subpath in of_paths)


def join_instrument_filestore_path(filestore_path: str) -> Path:
    """
    Safely join NX_INSTRUMENT_DATA_PATH with an instrument's filestore_path.

    This helper handles filestore_path values with leading slashes gracefully.
    If filestore_path starts with '/', the leading slash is stripped before joining
    to ensure the path remains relative to NX_INSTRUMENT_DATA_PATH.

    Parameters
    ----------
    filestore_path
        The instrument's filestore_path (may contain leading '/')

    Returns
    -------
    pathlib.Path
        A resolved Path object: NX_INSTRUMENT_DATA_PATH / filestore_path

    Examples
    --------
    >>> join_instrument_filestore_path("./Titan_STEM")
    PosixPath('/mnt/data/Titan_STEM')

    >>> join_instrument_filestore_path("/Titan_STEM")  # Leading slash stripped
    PosixPath('/mnt/data/Titan_STEM')

    >>> join_instrument_filestore_path("Titan_STEM")
    PosixPath('/mnt/data/Titan_STEM')
    """
    # Strip leading slash to ensure relative path behavior
    # pathlib treats absolute paths specially - they override the base path
    normalized_path = filestore_path.lstrip("/")

    return Path(settings.NX_INSTRUMENT_DATA_PATH) / normalized_path


def replace_instrument_data_path(path: Path, suffix: str) -> Path:
    """
    Given an "NX_INSTRUMENT_DATA_PATH" path, generate equivalent"NX_DATA_PATH" path.

    If the given path is not a subpath of "NX_INSTRUMENT_DATA_PATH", a warning will
    be logged and the suffix will just be added at the end.

    Parameters
    ----------
    path
        The input path, which is expected to be a subpath of the
        NX_INSTRUMENT_DATA_PATH directory
    suffix
        Any added suffix to add to the path (useful for appending with a new extension,
        such as ``.json``)

    Returns
    -------
    pathlib.Path
        A resolved pathlib.Path object pointing to the new path
    """
    instr_data_path = Path(str(settings.NX_INSTRUMENT_DATA_PATH))
    nexuslims_path = Path(str(settings.NX_DATA_PATH))

    if instr_data_path not in path.parents:
        _logger.warning(
            "%s is not a sub-path of %s", path, str(settings.NX_INSTRUMENT_DATA_PATH)
        )
    return Path(str(path).replace(str(instr_data_path), str(nexuslims_path)) + suffix)
