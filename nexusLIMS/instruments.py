# pylint: disable=duplicate-code
"""
Methods and representations for instruments in a NexusLIMS system.

Attributes
----------
instrument_db : dict
    A dictionary of :py:class:`~nexusLIMS.instruments.Instrument` objects.

    Each object in this dictionary represents an instrument detected in the
    NexusLIMS remote database.
"""

import contextlib
import datetime
import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import pytz
from pytz.tzinfo import BaseTzInfo

from nexusLIMS.config import settings
from nexusLIMS.utils import is_subpath

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _get_instrument_db(db_path: Path | str | None = None):
    """
    Get dictionary of instruments from the NexusLIMS database.

    Sort of like a very very basic ORM, but much worse.

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
    query = "SELECT * from instruments"
    instr_db = {}  # Initialize instr_db here

    # Use provided path or fall back to settings
    _db_path = db_path if db_path is not None else settings.NX_DB_PATH

    try:
        with (
            contextlib.closing(
                sqlite3.connect(str(_db_path)),
            ) as conn,
            conn,
            contextlib.closing(conn.cursor()) as cursor,
        ):  # auto-commits
            results = cursor.execute(query).fetchall()
            col_names = [x[0] for x in cursor.description]

        for line in results:
            this_dict = {}
            for key, val in zip(col_names, line):
                this_dict[key] = val

            key = this_dict.pop("instrument_pid")
            this_dict["name"] = key
            # remove keys from this_dict that we don't know about yet so we don't
            # crash and burn if a new column is added
            known_cols = [
                "api_url",
                "calendar_name",
                "calendar_url",
                "location",
                "name",
                "schema_name",
                "property_tag",
                "filestore_path",
                "computer_ip",
                "computer_name",
                "computer_mount",
                "harvester",
                "timezone",
            ]
            this_dict = {k: this_dict[k] for k in known_cols}
            instr_db[key] = Instrument(**this_dict)

    except (sqlite3.Error, KeyError) as e:
        logger.warning(
            "Could not connect to database or retrieve instruments. "
            "Returning empty instrument dictionary.\n\n Details:\n %s",
            e,
        )
        return {}

    return instr_db


@dataclass
class Instrument:
    """
    Representation of a NexusLIMS instrument.

    A simple object to hold information about an instrument in the Microscopy
    Nexus facility, fetched from the external NexusLIMS database.

    Parameters
    ----------
    api_url : str or None
        The calendar API endpoint url for this instrument's scheduler
    calendar_name : str or None
        The "user-friendly" name of the calendar for this instrument as displayed on the
        reservation system resource (e.g. "FEI Titan TEM")
    calendar_url : str or None
        The URL to this instrument's web-accessible calendar
    location : str or None
        The physical location of this instrument (building and room number)
    name : str or None
        The unique identifier for an instrument in the facility, currently
        (but not required to be) built from the make, model, and type of instrument,
        plus a unique numeric code (e.g. ``FEI-Titan-TEM-635816``)
    schema_name : str or None
        The human-readable name of instrument as defined in the Nexus Microscopy
        schema and displayed in the records
    property_tag : str or None
        A unique numeric identifier for this instrument (not used by NexusLIMS,
        but for reference and potential future use)
    filestore_path : str or None
        The path (relative to central storage location specified in
        :ref:`NX_INSTRUMENT_DATA_PATH <nexuslims-instrument-data-path>`) where
        this instrument stores its data (e.g. ``./Titan``)
    computer_name : str or None
        The hostname of the `support PC` connected to this instrument that runs
        the `Session Logger App`. If this is incorrect (or not included), the
        logger application will fail when attempting  to start a session from
        the microscope (only relevant if using the `Session Logger App`)
    computer_ip : str or None
        The IP address of the support PC connected to this instrument (not
        currently utilized)
    computer_mount : str or None
        The full path where the central file storage is mounted and files are
        saved on the 'support PC' for the instrument (e.g. 'M:/'; only relevant if
        using the `Session Logger App`)
    harvester : str or None
        The specific submodule within :py:mod:`nexusLIMS.harvesters` that should be
        used to harvest reservation information for this instrument. At the time of
        writing, the only possible value is ``nemo``.
    timezone : pytz.timezone, str, or None
        The timezone in which this instrument is located, in the format of the IANA
        timezone database (e.g. ``America/New_York``). This is used to properly localize
        dates and times when communicating with the harvester APIs.
    """

    api_url: str | None = None
    calendar_name: str | None = None
    calendar_url: str | None = None
    location: str | None = None
    name: str | None = None
    schema_name: str | None = None
    property_tag: str | None = None
    filestore_path: str | None = None
    computer_ip: str | None = None
    computer_name: str | None = None
    computer_mount: str | None = None
    harvester: str | None = None
    timezone: BaseTzInfo | str | None = None

    def __post_init__(self):
        """Post-initialization to convert timezone string to timezone object."""
        if isinstance(self.timezone, str):
            self.timezone = pytz.timezone(self.timezone)

    def __repr__(self):
        """Return custom representation of an Instrument."""
        return (
            f"Nexus Instrument: {self.name}\n"
            f"API url:          {self.api_url}\n"
            f"Calendar name:    {self.calendar_name}\n"
            f"Calendar url:     {self.calendar_url}\n"
            f"Schema name:      {self.schema_name}\n"
            f"Location:         {self.location}\n"
            f"Property tag:     {self.property_tag}\n"
            f"Filestore path:   {self.filestore_path}\n"
            f"Computer IP:      {self.computer_ip}\n"
            f"Computer name:    {self.computer_name}\n"
            f"Computer mount:   {self.computer_mount}\n"
            f"Harvester:        {self.harvester}\n"
            f"Timezone:         {self.timezone}"
        )

    def __str__(self):
        """Return custom string representation of an Instrument."""
        return f"{self.name} in {self.location}" if self.location else ""

    def localize_datetime(self, _dt: datetime.datetime) -> datetime.datetime:
        """
        Localize a datetime to an Instrument's timezone.

        Convert a date and time to the timezone of this instrument. If the
        supplied datetime is naive (i.e. does not have a timezone), it will be
        assumed to already be in the timezone of the instrument, and the
        displayed time will not change. If the timezone of the supplied
        datetime is different than the instrument's, the time will be
        adjusted to compensate for the timezone offset.

        Parameters
        ----------
        _dt
            The datetime object to localize

        Returns
        -------
        datetime.datetime
            A datetime object with the same timezone as the instrument
        """
        if self.timezone is None:
            logger.warning(
                "Tried to localize a datetime with instrument that does not have "
                "timezone information (%s)",
                self.name,
            )
            return _dt
        if _dt.tzinfo is None:
            # dt is timezone naive
            return self.timezone.localize(_dt)

        # dt has timezone info
        return _dt.astimezone(self.timezone)

    def localize_datetime_str(
        self,
        _dt: datetime.datetime,
        fmt: str = "%Y-%m-%d %H:%M:%S %Z",
    ) -> str:
        """
        Localize a datetime to an Instrument's timezone and return as string.

        Convert a date and time to the timezone of this instrument, returning
        a textual representation of the object, rather than the datetime
        itself. Uses :py:meth:`localize_datetime` for the actual conversion.

        Parameters
        ----------
        _dt
            The datetime object ot localize
        fmt
            The strftime format string to use to format the output

        Returns
        -------
        str
            The formatted textual representation of the localized datetime
        """
        return self.localize_datetime(_dt).strftime(fmt)

    def to_dict(self) -> dict:
        """
        Return a dictionary representation of the Instrument object.

        Handles special cases like renaming 'name' to 'instrument_pid' and
        converting timezone objects to strings.

        Returns
        -------
        dict
            A dictionary representation of the instrument, suitable for database
            insertion or JSON serialization.
        """
        instr_dict = asdict(self)

        # Rename 'name' to 'instrument_pid' for database compatibility
        if "name" in instr_dict:
            instr_dict["instrument_pid"] = instr_dict.pop("name")

        # Convert timezone object to string
        if isinstance(instr_dict.get("timezone"), BaseTzInfo):
            instr_dict["timezone"] = str(instr_dict["timezone"])

        return instr_dict

    def to_json(self, **kwargs) -> str:
        """
        Return a JSON string representation of the Instrument object.

        Parameters
        ----------
        **kwargs
            Additional keyword arguments to pass to `json.dumps`.

        Returns
        -------
        str
            A JSON string representation of the instrument.
        """
        return json.dumps(self.to_dict(), **kwargs)


instrument_db = _get_instrument_db()


def get_instr_from_filepath(path: Path):
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
    'FEI-Titan-TEM-635816 in xxx/xxxx'
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
    'FEI-Titan-TEM-635816 in ***REMOVED***'
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
    'FEI-Titan-STEM-630901_n in xxx/xxxx'
    """
    for _, v in instrument_db.items():
        if api_url == v.api_url:
            return v

    return None
