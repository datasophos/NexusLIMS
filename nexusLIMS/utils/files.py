"""File finding and manipulation utilities for NexusLIMS."""

import logging
import os
import subprocess
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from shutil import copyfile
from typing import List

from nexusLIMS.config import settings

_logger = logging.getLogger(__name__)

# hours to add to datetime objects (hack for poole testing -- should be -2 if
# running tests from Mountain Time on files in Eastern Time)
_tz_offset = timedelta(hours=0)


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
