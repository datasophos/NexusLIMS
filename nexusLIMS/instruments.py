# pylint: disable=duplicate-code
"""
Methods and representations for instruments in a NexusLIMS system.

Attributes
----------
instrument_db : dict
    A dictionary of :py:class:`~nexusLIMS.db.models.Instrument` objects.

    Each object in this dictionary represents an instrument detected in the
    NexusLIMS remote database.
"""

import logging
from pathlib import Path

from sqlmodel import Session as DBSession
from sqlmodel import create_engine, select

from nexusLIMS.config import settings
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.models import Instrument
from nexusLIMS.utils.paths import is_subpath

logging.basicConfig()
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


def _get_instrument_db(db_path: Path | str | None = None):
    """
    Get dictionary of instruments from the NexusLIMS database.

    Parameters
    ----------
    db_path : Path | str | None, optional
        Path to the database file. If None, uses the path from settings.
        This parameter is primarily for testing purposes.

    Returns
    -------
    instrument_db : dict
        A dictionary of `Instrument` instances that describe all the
        instruments that were found in the ``instruments`` table of the
        NexusLIMS database
    """
    # Use provided path or fall back to settings
    _db_path = db_path if db_path is not None else settings.NX_DB_PATH

    # Create temporary engine if non-default path (for testing)
    if db_path is not None:
        temp_engine = create_engine(f"sqlite:///{_db_path}")
    else:
        temp_engine = get_engine()

    try:
        with DBSession(temp_engine) as session:
            instruments_list = session.exec(select(Instrument)).all()
            return {inst.instrument_pid: inst for inst in instruments_list}
    except Exception as e:
        _logger.warning(
            "Could not connect to database or retrieve instruments. "
            "Returning empty instrument dictionary.\n\n Details:\n %s",
            e,
        )
        return {}


# Lazy initialization for instrument_db to avoid triggering Settings validation
# during module import
_instrument_db_cache = None
_instrument_db_initialized = False


def _get_instrument_db_cached():
    """Get the instrument database with caching (lazy initialization)."""
    global _instrument_db_cache, _instrument_db_initialized  # noqa: PLW0603
    if not _instrument_db_initialized:
        _instrument_db_cache = _get_instrument_db()
        _instrument_db_initialized = True
    return _instrument_db_cache


# Backwards-compatible module attribute
# Will be populated on first access via __getattr__
instrument_db = None
"""dict[str, Instrument]: Module-level cache of all instruments from the database.

Keys are instrument PIDs (str), values are
:class:`~nexusLIMS.db.models.Instrument` instances.
Populated on first access from the NexusLIMS database.
"""


def get_instr_from_filepath(path: Path) -> Instrument | None:
    """
    Get an instrument object by a given path Using the NexusLIMS database.

    Parameters
    ----------
    path
        A path (relative or absolute) to a file saved in the central
        filestore that will be used to search for a matching instrument

    Returns
    -------
    instrument : Instrument or None
        An `Instrument` instance matching the path, or None if no match was
        found

    Examples
    --------
    >>> inst = get_instr_from_filepath('/path/to/file.dm3')
    >>> str(inst)
    'FEI-Titan-TEM-012345 in Bldg 1/Room A'
    """
    for _, v in instrument_db.items():
        if is_subpath(
            path,
            Path(settings.NX_INSTRUMENT_DATA_PATH) / v.filestore_path,
        ):
            return v

    return None


def get_instr_from_calendar_name(cal_name):
    """
    Get an instrument object from the NexusLIMS database by its calendar name.

    Parameters
    ----------
    cal_name : str
        A calendar name (e.g. "FEITitanTEMEvents") that will be used to search
        for a matching instrument in the ``api_url`` values

    Returns
    -------
    instrument : Instrument or None
        An `Instrument` instance matching the path, or None if no match was
        found

    Examples
    --------
    >>> inst = get_instr_from_calendar_name('FEITitanTEMEvents')
    >>> str(inst)
    'FEI-Titan-TEM-012345 in Bldg 1/Room A'
    """
    for _, v in instrument_db.items():
        if cal_name in v.api_url:
            return v

    return None


def get_instr_from_api_url(api_url: str) -> Instrument | None:
    """
    Get an instrument object from the NexusLIMS database by its ``api_url``.

    Parameters
    ----------
    api_url
        An api_url (e.g. "FEITitanTEMEvents") that will be used to search
        for a matching instrument in the ``api_url`` values

    Returns
    -------
    Instrument
        An ``Instrument`` instance matching the ``api_url``, or ``None`` if no
        match was found

    Examples
    --------
    >>> inst = get_instr_from_api_url('https://nemo.example.com/api/tools/?id=1')
    >>> str(inst)
    'FEI-Titan-STEM-012345 in Bldg 1/Room A'
    """
    for _, v in instrument_db.items():
        if api_url == v.api_url:
            return v

    return None


def __getattr__(name: str):
    """Provide lazy access to instrument_db module variable."""
    if name == "instrument_db":
        return _get_instrument_db_cached()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
