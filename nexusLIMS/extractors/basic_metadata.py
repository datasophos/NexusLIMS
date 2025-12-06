"""Handle basic metadata extraction from files that do not have an extractor defined."""

import logging
from datetime import datetime as dt

from nexusLIMS.instruments import get_instr_from_filepath

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_basic_metadata(filename):
    """
    Get basic metadata from a file.

    Returns basic metadata from a file that's not currently interpretable by NexusLIMS.

    Parameters
    ----------
    filename : str
        path to a file saved in the harvested directory of the instrument

    Returns
    -------
    mdict : dict
        A description of the file in lieu of any metadata extracted from it.
    """
    mdict = {"nx_meta": {}}
    mdict["nx_meta"]["DatasetType"] = "Unknown"
    mdict["nx_meta"]["Data Type"] = "Unknown"

    # get the modification time (as ISO format):
    mtime = filename.stat().st_mtime
    instr = get_instr_from_filepath(filename)
    mtime_iso = dt.fromtimestamp(
        mtime,
        tz=instr.timezone if instr else None,
    ).isoformat()
    mdict["nx_meta"]["Creation Time"] = mtime_iso

    return mdict
