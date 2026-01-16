"""Utility functions used in potentially multiple places by NexusLIMS."""

import logging
import os
import subprocess
import tempfile
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from shutil import copyfile
from typing import Any, Dict, List, Tuple, Union

import certifi
import pytz
import tzlocal
from benedict import benedict
from requests import Session
from requests.adapters import HTTPAdapter

from .config import settings
from .harvesters import CA_BUNDLE_CONTENT

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)

# hours to add to datetime objects (hack for poole testing -- should be -2 if
# running tests from Mountain Time on files in Eastern Time)
_tz_offset = timedelta(hours=0)


def setup_loggers(log_level):
    """
    Set logging level of all NexusLIMS loggers.

    Parameters
    ----------
    log_level : int
        The level of logging, such as ``logging.DEBUG``
    """
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        level=log_level,
    )
    loggers = [
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict  # pylint: disable=no-member
        if "nexusLIMS" in name
    ]
    for _logger in loggers:
        _logger.setLevel(log_level)


def nexus_req(
    url: str,
    function: str,
    *,
    retries: int = 5,
    token_auth: str | None = None,
    **kwargs: dict | None,
):
    """
    Make a request from NexusLIMS.

    A helper method that wraps a function from :py:mod:`requests`, but adds a
    local certificate authority chain to validate any custom certificates.
    Will automatically retry on transient server errors (502, 503, 504) with
    exponential backoff.

    Parameters
    ----------
    url
        The URL to fetch
    function
        The function from the ``requests`` library to use (e.g.
        ``'GET'``, ``'POST'``, ``'PATCH'``, etc.)
    retries
        The maximum number of retry attempts (total attempts = retries + 1)
    token_auth
        If a value is provided, it will be used as a token for authentication
    **kwargs :
        Other keyword arguments are passed along to the ``fn``

    Returns
    -------
    r : :py:class:`requests.Response`
        A requests response object
    """
    # if token_auth is desired, add it to any existing headers passed along
    # with the request
    if token_auth:
        if "headers" in kwargs:
            kwargs["headers"]["Authorization"] = f"Token {token_auth}"
        else:
            kwargs["headers"] = {"Authorization": f"Token {token_auth}"}

    # Status codes that should trigger a retry (transient server errors)
    retry_status_codes = {502, 503, 504}

    # Set up a session (without urllib3 retry logic - we'll handle it ourselves)
    s = Session()
    s.mount("https://", HTTPAdapter())
    s.mount("http://", HTTPAdapter())

    verify_arg = True
    response = None

    with tempfile.NamedTemporaryFile() as tmp:
        if CA_BUNDLE_CONTENT:
            with Path(certifi.where()).open(mode="rb") as sys_cert:
                lines = sys_cert.readlines()
            tmp.writelines(lines)
            tmp.writelines(CA_BUNDLE_CONTENT)
            tmp.seek(0)
            verify_arg = tmp.name

        # Retry loop with exponential backoff
        for attempt in range(retries + 1):
            response = s.request(function, url, verify=verify_arg, **kwargs)

            # If we got a successful response or non-retryable error, return it
            if response.status_code not in retry_status_codes:
                return response

            # If this is our last attempt, return the failed response
            if attempt == retries:
                _logger.warning(
                    "Request to %s failed with %s after %s attempts",
                    url,
                    response.status_code,
                    retries + 1,
                )
                return response

            # Calculate backoff delay: 1s, 2s, 4s, 8s, etc.
            delay = 2**attempt
            _logger.debug(
                "Request to %s returned %s, retrying in %ss (attempt %s/%s)",
                url,
                response.status_code,
                delay,
                attempt + 1,
                retries + 1,
            )
            time.sleep(delay)

    # This should never be reached in normal execution, but provides a fallback
    # if the retry loop somehow doesn't execute (e.g., invalid retries parameter)
    return response  # pragma: no cover


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


def get_nested_dict_value_by_path(nest_dict, path):
    """
    Get a nested dictionary value by path.

    Get the value from within a nested dictionary structure by traversing into
    the dictionary as deep as that path found and returning that value.

    Uses python-benedict for robust nested dictionary operations.

    Parameters
    ----------
    nest_dict : dict
        A dictionary of dictionaries that is to be queried
    path : tuple
        A tuple (or other iterable type) that specifies the subsequent keys
        needed to get to a a value within `nest_dict`

    Returns
    -------
    value : object or None
        The value at the path within the nested dictionary; if there's no
        value there, return None
    """
    # Disable keypath_separator to avoid conflicts with keys containing special chars
    return benedict(nest_dict, keypath_separator=None).get(list(path))


def set_nested_dict_value(nest_dict, path, value):
    """
    Set a nested dictionary value by path.

    Set a value within a nested dictionary structure by traversing into
    the dictionary as deep as that path found and changing it to `value`.

    Uses python-benedict for robust nested dictionary operations.

    Parameters
    ----------
    nest_dict : dict
        A dictionary of dictionaries that is to be queried
    path : tuple
        A tuple (or other iterable type) that specifies the subsequent keys
        needed to get to a a value within `nest_dict`
    value : object
        The value which will be given to the path in the nested dictionary

    Returns
    -------
    value : object
        The value at the path within the nested dictionary
    """
    # Disable keypath_separator to avoid conflicts with keys containing special chars
    b = benedict(nest_dict, keypath_separator=None)
    b[list(path)] = value  # Updates in-place (benedict is dict subclass)


def try_getting_dict_value(dict_, key):
    """
    Try to get a nested dictionary value.

    This method will try to get a value from a dictionary (potentially
    nested) and fail silently if the value is not found, returning None.

    Parameters
    ----------
    dict_ : dict
        The dictionary from which to get a value
    key : str or tuple
        The key to query, or if an iterable container type (tuple, list,
        etc.) is given, the path into a nested dictionary to follow

    Returns
    -------
    val : object or None
        The value of the dictionary specified by `key`. If the dictionary
        does not have a key, returns None without raising an error
    """
    try:
        if isinstance(key, str):
            return dict_[key]
        if hasattr(key, "__iter__"):
            return get_nested_dict_value_by_path(dict_, key)
    except (KeyError, TypeError):
        return None
    else:
        # we shouldn't reach this line, but always good to return a consistent
        # value just in case
        return None  # pragma: no cover


def find_dirs_by_mtime(
    path: str,
    dt_from: datetime,
    dt_to: datetime,
    *,
    followlinks: bool = True,
) -> List[str]:
    """
    Find directories modified between two times.

    Given two timestamps, find the directories under a path that were
    last modified between the two.

    .. deprecated:: 0.0.9
          `find_dirs_by_mtime` is not recommended for use to find files for
          record inclusion, because subsequent modifications to a directory
          (e.g. the user wrote a text file or did some analysis afterwards)
          means no files will be returned from that directory (because it is
          not searched)

    Parameters
    ----------
    path
        The root path from which to start the search
    dt_from
        The "starting" point of the search timeframe
    dt_to
        The "ending" point of the search timeframe
    followlinks
        Argument passed on to py:func:`os.walk` to control whether
        symbolic links are followed

    Returns
    -------
    dirs : list
        A list of the directories that have modification times within the
        time range provided
    """
    dirs = []

    # adjust the datetime objects with the tz_offset (usually should be 0) if
    # they are naive
    if dt_from.tzinfo is None:
        dt_from += _tz_offset  # pragma: no cover
    if dt_to.tzinfo is None:
        dt_to += _tz_offset  # pragma: no cover

    # use os.walk and only inspect the directories for mtime (much fewer
    # comparisons than looking at every file):
    _logger.info(
        "Finding directories modified between %s and %s",
        dt_from.isoformat(),
        dt_to.isoformat(),
    )
    for dirpath, _, _ in os.walk(path, followlinks=followlinks):
        if dt_from.timestamp() < Path(dirpath).stat().st_mtime < dt_to.timestamp():
            dirs.append(dirpath)
    return dirs


def find_files_by_mtime(path: Path, dt_from, dt_to) -> List[Path]:  # pragma: no cover
    """
    Find files motified between two times.

    Given two timestamps, find files under a path that were
    last modified between the two.

    Parameters
    ----------
    path
        The root path from which to start the search
    dt_from : datetime.datetime
        The "starting" point of the search timeframe
    dt_to : datetime.datetime
        The "ending" point of the search timeframe

    Returns
    -------
    files : list
        A list of the files that have modification times within the
        time range provided (sorted by modification time)
    """
    warnings.warn(
        "find_files_by_mtime has been deprecated in v1.2.0 and is "
        "no longer tested or supported. Please use "
        "gnu_find_files_by_mtime() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    # find only the directories that have been modified between these two
    # timestamps (should be much faster than inspecting all files)
    # Note: this doesn't work reliably, so just look in entire path...

    dirs = [path]

    # adjust the datetime objects with the tz_offset (usually should be 0) if
    # they are naive
    if dt_from.tzinfo is None:
        dt_from += _tz_offset
    if dt_to.tzinfo is None:
        dt_to += _tz_offset

    files = set()  # use a set here (faster and we won't have duplicates)
    # for each of those directories, walk the file tree and inspect the
    # actual files:
    for directory in dirs:
        for dirpath, _, filenames in os.walk(directory, followlinks=True):
            for f in filenames:
                fname = Path(dirpath) / f
                if dt_from.timestamp() < fname.stat().st_mtime < dt_to.timestamp():
                    files.add(fname)

    # convert the set to a list and sort my mtime
    files = list(files)
    files.sort(key=lambda f: f.stat().st_mtime)

    return files


def _get_find_command():
    """
    Get the appropriate GNU find command for the system.

    Returns
    -------
    str
        The find command to use ('find' or 'gfind')

    Raises
    ------
    RuntimeError
        If find command is not available or GNU find is required but not found
    """

    def _which(fname):
        def _is_exec(f):
            return Path(f).is_file() and os.access(f, os.X_OK)

        for exe in os.environ["PATH"].split(os.pathsep):
            exe_file = str(Path(exe) / fname)
            if _is_exec(exe_file):
                return exe_file
        return False

    def _is_gnu_find(find_cmd):
        """Check if the find command is GNU find (supports -xtype)."""
        try:
            result = subprocess.run(
                [find_cmd, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
        else:
            return "GNU findutils" in result.stdout

    find_command = "find"
    if not _which(find_command):
        msg = "find command was not found on the system PATH"
        raise RuntimeError(msg)

    if not _is_gnu_find(find_command):
        import platform  # noqa: PLC0415

        if platform.system() == "Darwin":  # pragma: no cover
            # macOS
            if _which("gfind"):
                find_command = "gfind"
                _logger.info("BSD find detected, using gfind (GNU find) instead")
            else:
                msg = (
                    "BSD find detected on macOS, but GNU find is required.\n"
                    "The 'find' command on macOS does not support the '-xtype' option "
                    "needed for NexusLIMS.\n\n"
                    "Please install GNU find via Homebrew:\n"
                    "  brew install findutils\n\n"
                    "This will install GNU find as 'gfind', which NexusLIMS will use "
                    "automatically."
                )
                raise RuntimeError(msg)
        else:
            _logger.warning(
                "Non-GNU find detected. If you encounter errors, "
                "please install GNU findutils.",
            )

    return find_command


def _find_symlink_dirs(find_command, path):
    """
    Find symbolic links pointing to directories.

    Parameters
    ----------
    find_command : str
        The find command to use
    path : Path
        The root path to search

    Returns
    -------
    list
        List of symbolic link paths, or [path] if none found
    """
    find_path = Path(str(settings.NX_INSTRUMENT_DATA_PATH)) / path
    cmd = [find_command, str(find_path), "-type", "l", "-xtype", "d", "-print0"]
    _logger.info('Running followlinks find via subprocess.run: "%s"', cmd)
    out = subprocess.run(cmd, capture_output=True, check=True)
    paths = [f.decode() for f in out.stdout.split(b"\x00") if len(f) > 0]
    _logger.info('Found the following symlinks: "%s"', paths)

    if paths:
        _logger.info("find_path is: '%s'", paths)
        return paths
    return [find_path]


def _build_find_command(  # noqa: PLR0913
    find_command,
    find_paths,
    dt_from,
    dt_to,
    extensions,
    followlinks,
):
    """
    Build the find command with all arguments.

    Parameters
    ----------
    find_command : str
        The find command to use
    find_paths : list
        Paths to search
    dt_from : datetime
        Start time
    dt_to : datetime
        End time
    extensions : list or None
        File extensions to search for
    followlinks : bool
        Whether to follow symlinks

    Returns
    -------
    list
        Complete find command as list of arguments
    """
    cmd = [find_command] + (["-H"] if followlinks else [])
    cmd += [str(p) for p in find_paths]
    cmd += [
        "-type",
        "f",
        "-newermt",
        dt_from.isoformat(),
        "-not",
        "-newermt",
        dt_to.isoformat(),
    ]

    # Add extension patterns
    if extensions is not None:
        cmd += ["("]
        for ext in extensions:
            cmd += ["-iname", f"*.{ext}", "-o"]
        cmd.pop()
        cmd += [")"]

    # Add ignore patterns (settings already provides a list)
    ignore_patterns = settings.NX_IGNORE_PATTERNS
    if ignore_patterns:
        cmd += ["-and", "("]
        for i in ignore_patterns:
            cmd += ["-not", "-iname", i, "-and"]
        cmd.pop()
        cmd += [")"]

    cmd += ["-print0"]
    return cmd


def gnu_find_files_by_mtime(
    path: Path,
    dt_from: datetime,
    dt_to: datetime,
    extensions: List[str] | None = None,
    *,
    followlinks: bool = True,
) -> List[Path]:
    """
    Find files modified between two times.

    Given two timestamps, find files under a path that were
    last modified between the two. Uses the system-provided GNU ``find``
    command. In basic testing, this method was found to be approximately 3 times
    faster than using :py:meth:`find_files_by_mtime` (which is implemented in
    pure Python).

    Parameters
    ----------
    path
        The root path from which to start the search, relative to
        the :ref:`NX_INSTRUMENT_DATA_PATH <config-instrument-data-path>`
        environment setting.
    dt_from
        The "starting" point of the search timeframe
    dt_to
        The "ending" point of the search timeframe
    extensions
        A list of strings representing the extensions to find. If None,
        all files between are found between the two times.
    followlinks
        Whether to follow symlinks using the ``find`` command via
        the ``-H`` command line flag. This is useful when the
        :ref:`NX_INSTRUMENT_DATA_PATH <config-instrument-data-path>` is actually a
        directory
        of symlinks. If this is the case and ``followlinks`` is
        ``False``, no files will ever be found because the ``find``
        command will not "dereference" the symbolic links it finds.
        See comments in the code for more comments on implementation
        of this feature.

    Returns
    -------
    List[str]
        A list of the files that have modification times within the
        time range provided (sorted by modification time)

    Raises
    ------
    RuntimeError
        If the find command cannot be found, or running it results in output
        to `stderr`
    """
    _logger.info("Using GNU `find` to search for files")

    # Get appropriate find command
    find_command = _get_find_command()

    # Adjust datetime objects with tz_offset if naive
    dt_from += _tz_offset if dt_from.tzinfo is None else timedelta(0)
    dt_to += _tz_offset if dt_to.tzinfo is None else timedelta(0)

    # Find symlink directories if following links
    if followlinks:
        find_paths = _find_symlink_dirs(find_command, path)
    else:
        find_paths = [Path(str(settings.NX_INSTRUMENT_DATA_PATH)) / path]

    # Build and execute find command
    cmd = _build_find_command(
        find_command,
        find_paths,
        dt_from,
        dt_to,
        extensions,
        followlinks,
    )
    _logger.info('Running via subprocess.run: "%s"', cmd)
    _logger.info('Running via subprocess.run (as string): "%s"', " ".join(cmd))
    out = subprocess.run(cmd, capture_output=True, check=True)

    # Process results
    files = out.stdout.split(b"\x00")
    files = [Path(f.decode()) for f in files if len(f) > 0]
    files = list(set(files))
    files.sort(key=lambda f: f.stat().st_mtime)
    _logger.info("Found %i files", len(files))

    return files


def sort_dict(item):
    """Recursively sort a dictionary by keys."""
    return {
        k: sort_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(item.items(), key=lambda i: i[0].lower())
    }


def remove_dtb_element(tree, path):
    """
    Remove an element from a DictionaryTreeBrowser by setting it to None.

    Helper method that sets a specific leaf of a DictionaryTreeBrowser to None.
    Use with :py:meth:`remove_dict_nones` to fully remove the desired DTB element after
    setting it to None (after converting DTB to dictionary).

    Parameters
    ----------
    tree : :py:class:`~hyperspy.misc.utils.DictionaryTreeBrowser`
        the ``DictionaryTreeBrowser`` object to remove the object from
    path : str
        period-delimited path to a DTB element

    Returns
    -------
    tree : :py:class:`~hyperspy.misc.utils.DictionaryTreeBrowser`
    """
    tree.set_item(path, None)

    return tree


def remove_dict_nones(dictionary: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Delete keys with a value of ``None`` in a dictionary, recursively.

    Taken from https://stackoverflow.com/a/4256027.

    Parameters
    ----------
    dictionary
        The dictionary, with keys that have None values removed

    Returns
    -------
    dict
        The same dictionary, but with "Nones" removed
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, dict):
            remove_dict_nones(value)
    return dictionary


def _zero_bytes(fname: Path, bytes_from, bytes_to) -> Path:
    """
    Set certain byte locations within a file to zero.

    This method helps creating highly-compressible test files.

    Parameters
    ----------
    fname
    bytes_from : int or :obj:`list` of str
        The position of the file (in decimal) at which to start zeroing
    bytes_to : int or :obj:`list` of str
        The position of the file (in decimal) at which to stop zeroing. If
        list, must be the same length as list given in ``bytes_from``

    Returns
    -------
    new_fname
        The modified file that has it's bytes zeroed
    """
    filename, ext = fname.stem, fname.suffix
    if ext == ".ser":
        index = int(filename.split("_")[-1])
        basename = "_".join(filename.split("_")[:-1])
        new_fname = fname.parent / f"{basename}_dataZeroed_{index}{ext}"
    else:
        new_fname = fname.parent / f"{filename}_dataZeroed{ext}"
    copyfile(fname, new_fname)

    if isinstance(bytes_from, int):
        bytes_from = [bytes_from]
        bytes_to = [bytes_to]

    with Path(new_fname).open(mode="r+b") as f:
        for from_byte, to_byte in zip(bytes_from, bytes_to):
            f.seek(from_byte)
            f.write(b"\0" * (to_byte - from_byte))

    return new_fname


def get_timespan_overlap(
    range_1: Tuple[datetime, datetime],
    range_2: Tuple[datetime, datetime],
) -> timedelta:
    """
    Find the amount of overlap between two time spans.

    Adapted from https://stackoverflow.com/a/9044111.

    Parameters
    ----------
    range_1
        Tuple of length 2 of datetime objects: first is the start of the time
        range and the second is the end of the time range
    range_2
        Tuple of length 2 of datetime objects: first is the start of the time
        range and the second is the end of the time range

    Returns
    -------
    datetime.timedelta
        The amount of overlap between the time ranges
    """
    latest_start = max(range_1[0], range_2[0])
    earliest_end = min(range_1[1], range_2[1])
    delta = earliest_end - latest_start

    return max(timedelta(0), delta)


def has_delay_passed(date: datetime) -> bool:
    """
    Check if the current time is greater than the configured delay.

    Check if the current time is greater than the configured (or default) record
    building delay configured in the ``NX_FILE_DELAY_DAYS`` environment variable.
    If the date given is timezone-aware, the current time in that timezone will be
    compared.

    Parameters
    ----------
    date
        The datetime to check; can be either timezone aware or naive

    Returns
    -------
    bool
        Whether the current time is greater than the given date plus the
        configurable delay.
    """
    # get record builder delay from settings (already validated as float > 0)
    delay = timedelta(days=settings.NX_FILE_DELAY_DAYS)

    # Match timezone awareness of input date
    now = (
        datetime.now()  # noqa: DTZ005
        if date.tzinfo is None
        else datetime.now(date.tzinfo)
    )

    delta = now - date

    return delta > delay


def current_system_tz_name() -> str:
    """
    Get the system's timezone name.

    Returns the IANA timezone database name for the system's current timezone
    (e.g., 'America/New_York'), never a simple UTC offset.

    Returns
    -------
    str
        The IANA timezone name (e.g., 'America/New_York', 'Europe/London')

    Examples
    --------
    >>> current_system_tz_name()
    'America/New_York'
    """
    # Get the system's local timezone using tzlocal
    return tzlocal.get_localzone_name()


def current_system_tz() -> pytz.tzinfo.DstTzInfo:
    """
    Get the system's timezone as a pytz timezone object.

    Returns the system's current timezone as a pytz timezone object with a
    named timezone (e.g., 'America/New_York'), never a simple UTC offset.

    Returns
    -------
    pytz.tzinfo.DstTzInfo
        A pytz timezone object representing the system's timezone

    Examples
    --------
    >>> tz = get_system_tz()
    >>> tz.zone
    'America/New_York'
    """
    # Return the corresponding pytz timezone object
    return pytz.timezone(current_system_tz_name())


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


class AuthenticationError(Exception):
    """Class for showing an exception having to do with authentication."""

    def __init__(self, message):
        self.message = message
