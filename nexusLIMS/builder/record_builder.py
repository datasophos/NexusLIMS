"""Build Nexus records from metadata and datasets.

Builds NexusLIMS records.

Attributes
----------
XSD_PATH
    A string containing the path to the Nexus Experiment schema file,
    which is used to validate XML records built by this module
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime as dt
from datetime import timedelta as td
from importlib import import_module, util
from io import BytesIO
from pathlib import Path
from timeit import default_timer
from typing import List
from uuid import uuid4

from lxml import etree
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS import version
from nexusLIMS.builder.preflight import PreflightError, run_preflight_checks
from nexusLIMS.config import settings
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import RecordStatus
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.session_handler import Session, get_sessions_to_build
from nexusLIMS.exporters import export_records, was_successfully_exported
from nexusLIMS.extractors import get_registry
from nexusLIMS.harvesters import nemo
from nexusLIMS.harvesters.nemo import utils as nemo_utils
from nexusLIMS.harvesters.reservation_event import ReservationEvent
from nexusLIMS.schemas import activity
from nexusLIMS.schemas.activity import AcquisitionActivity, cluster_filelist_mtimes
from nexusLIMS.utils.files import (
    find_files_by_mtime,
    gnu_find_files_by_mtime,
)
from nexusLIMS.utils.paths import join_instrument_filestore_path
from nexusLIMS.utils.time import (
    current_system_tz,
    has_delay_passed,
)

_logger = logging.getLogger(__name__)
XSD_PATH: Path = Path(activity.__file__).parent / "nexus-experiment.xsd"


def build_record(
    session: Session,
    sample_id: str | None = None,
    *,
    generate_previews: bool = True,
) -> str:
    """
    Build a NexusLIMS XML record of an Experiment.

    Construct an XML document conforming to the NexusLIMS schema from a
    directory containing microscopy data files. Accepts either a
    :py:class:`~nexusLIMS.db.session_handler.Session` object or an Instrument
    and date range (for backwards compatibility). For calendar parsing,
    currently no logic is implemented for a query that returns multiple records.

    Parameters
    ----------
    session
        A :py:class:`~nexusLIMS.db.session_handler.Session` or ``None``. If
        a value is provided, ``instrument``, ``dt_from``, ``dt_to`` and ``user``
        will be ignored, and the values from the Session object will be used
        instead
    sample_id
        A unique identifier pointing to a sample identifier for data
        collected in this record. If None, a UUIDv4 will be generated
    generate_previews
        Whether to create the preview thumbnail images

    Returns
    -------
    xml_record : str
        A formatted string containing a well-formed and valid XML document
        for the data contained in the provided path
    """
    if sample_id is None:
        sample_id = str(uuid4())

    # setup XML namespaces
    nx_namespace = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"
    xsi_namespace = "http://www.w3.org/2001/XMLSchema-instance"
    ns_map = {None: nx_namespace, "xsi": xsi_namespace, "nx": nx_namespace}
    xml = etree.Element("Experiment", nsmap=ns_map)

    _logger.info(
        "Getting calendar events with instrument: %s, from %s to %s, "
        "user: %s; using harvester: %s",
        session.instrument.name,
        session.dt_from.isoformat(),
        session.dt_to.isoformat(),
        session.user,
        session.instrument.harvester,
    )
    # this returns a nexusLIMS.harvesters.reservation_event.ReservationEvent
    res_event = get_reservation_event(session)

    output = res_event.as_xml()

    for child in output:
        xml.append(child)

    _logger.info(
        "Building acquisition activities for timespan from %s to %s",
        session.dt_from.isoformat(),
        session.dt_to.isoformat(),
    )
    activities = build_acq_activities(
        session.instrument,
        session.dt_from,
        session.dt_to,
        generate_previews,
    )
    for i, this_activity in enumerate(activities):
        a_xml = this_activity.as_xml(i, sample_id)
        xml.append(a_xml)

    return etree.tostring(
        xml,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    ).decode()


def get_reservation_event(session: Session) -> ReservationEvent:
    """
    Get a ReservationEvent representation of a Session.

    Handles the abstraction of choosing the right "version" of the
    ``res_event_from_session`` method from the harvester specified in the
    instrument database. This allows for one consistent function name to call
    a different method depending on which harvester is specified for each
    instrument (currently just NEMO).

    Parameters
    ----------
    session
        The :py:class:`~nexusLIMS.db.session_handler.Session` for which to
        fetch a matching
        :py:class:`~nexusLIMS.harvesters.reservation_event.ReservationEvent` from
        the relevant harvester

    Returns
    -------
    res_event : ~nexusLIMS.harvesters.reservation_event.ReservationEvent
        A :py:class:`~nexusLIMS.harvesters.reservation_event.ReservationEvent`
        representation of a reservation that matches the instrument and timespan
        specified in ``session``.
    """
    # try to find module and raise error if not found:
    if (
        util.find_spec(f".{session.instrument.harvester}", "nexusLIMS.harvesters")
        is None
    ):
        msg = (
            f"Harvester {session.instrument.harvester} not found in "
            "nexusLIMS.harvesters"
        )
        raise NotImplementedError(msg)

    # use import_module to choose the correct harvester based on the instrument
    harvester = import_module(
        f".{session.instrument.harvester}",
        "nexusLIMS.harvesters",
    )
    # for PyCharm typing, explicitly specify what modules may be in `harvester`
    # harvester: Union[nemo]  # noqa: ERA001
    if not hasattr(harvester, "res_event_from_session"):
        msg = (
            f"res_event_from_session has not been implemented for {harvester}, which "
            f"is required to use this method."
        )
        raise NotImplementedError(msg)

    return harvester.res_event_from_session(session)


def build_acq_activities(instrument, dt_from, dt_to, generate_previews):
    """
    Build an XML string representation of each AcquisitionActivity for a session.

    This includes setup parameters and metadata
    associated with each dataset obtained during a microscopy session. Unique
    AcquisitionActivities are delimited via clustering of file collection
    time to detect "long" breaks during a session.

    Parameters
    ----------
    instrument : :py:class:`~nexusLIMS.db.models.Instrument`
        One of the NexusLIMS instruments contained in the
        :py:attr:`~nexusLIMS.instruments.instrument_db` database.
        Controls what instrument calendar is used to get events.
    dt_from : datetime.datetime
        The starting timestamp that will be used to determine which files go
        in this record
    dt_to : datetime.datetime
        The ending timestamp used to determine the last point in time for
        which files should be associated with this record
    generate_previews : bool
        Whether or not to create the preview thumbnail images

    Returns
    -------
    activities : :obj:`list` of
    :obj:`~nexusLIMS.schemas.activity.AcquisitionActivity`:
        The list of :py:class:`~nexusLIMS.schemas.activity.AcquisitionActivity`
        objects generated for the record
    """
    logging.getLogger("hyperspy.io_plugins.digital_micrograph").setLevel(
        logging.WARNING,
    )

    start_timer = default_timer()
    path = join_instrument_filestore_path(instrument.filestore_path)
    # find the files to be included (list of Paths)
    files = get_files(path, dt_from, dt_to)

    _logger.info(
        "Found %i files in %.2f seconds",
        len(files),
        default_timer() - start_timer,
    )

    # raise error if no file found were found
    if len(files) == 0:
        msg = "No files found in this time range"
        raise FileNotFoundError(msg)

    # get the timestamp boundaries of acquisition activities
    aa_bounds = cluster_filelist_mtimes(files)

    # add the last file's modification time to the boundaries list to make
    # the loop below easier to process
    aa_bounds.append(files[-1].stat().st_mtime)

    activities: List[AcquisitionActivity | None] = [None] * len(aa_bounds)

    i = 0
    aa_idx = 0
    while i < len(files):
        f = files[i]
        mtime = f.stat().st_mtime

        # check this file's mtime, if it is less than this iteration's value
        # in the AA bounds, then it belongs to this iteration's AA
        # if not, then we should move to the next activity
        if mtime <= aa_bounds[aa_idx]:
            # if current activity index is None, we need to start a new AA:
            if activities[aa_idx] is None:
                activities[aa_idx] = AcquisitionActivity(
                    start=dt.fromtimestamp(mtime, tz=instrument.timezone),
                )

            # add this file to the AA
            _logger.info(
                "Adding file %i/%i %s to activity %i",
                i,
                len(files),
                str(f).replace(str(settings.NX_INSTRUMENT_DATA_PATH), "").strip("/"),
                aa_idx,
            )
            activities[aa_idx].add_file(fname=f, generate_preview=generate_previews)
            # assume this file is the last one in the activity (this will be
            # true on the last iteration where mtime is <= to the
            # aa_bounds value)
            activities[aa_idx].end = dt.fromtimestamp(mtime, tz=instrument.timezone)
            i += 1
        else:
            # this file's mtime is after the boundary and is thus part of the
            # next activity, so increment AA counter and reprocess file (do
            # not increment i)
            aa_idx += 1

    # Remove any "None" activities from list
    activities: List[AcquisitionActivity] = [a for a in activities if a is not None]

    _logger.info("Finished detecting activities")
    for i, this_activity in enumerate(activities):
        _logger.info("Activity %i: storing setup parameters", i)
        this_activity.store_setup_params()
        _logger.info("Activity %i: storing unique metadata values", i)
        this_activity.store_unique_metadata()

    return activities


def get_files(
    path: Path,
    dt_from: dt,
    dt_to: dt,
) -> List[Path]:
    """
    Get files under a path that were last modified between the two given timestamps.

    Parameters
    ----------
    path
        The file path in which to search for files
    dt_from : datetime.datetime
        The starting timestamp that will be used to determine which files go
        in this record
    dt_to : datetime.datetime
        The ending timestamp used to determine the last point in time for
        which files should be associated with this record

    Returns
    -------
    files : List[pathlib.Path]
        A list of the files that have modification times within the
        time range provided (sorted by modification time)
    """
    _logger.info("Starting new file-finding in %s", path)

    # read file finding strategy from settings
    strategy = settings.NX_FILE_STRATEGY.lower()
    if strategy not in ["inclusive", "exclusive"]:
        _logger.warning(
            'File finding strategy (setting "NX_FILE_STRATEGY") had '
            'an unexpected value: "%s". Setting value to "exclusive".',
            strategy,
        )
        strategy = "exclusive"

    # Get supported extensions from the registry
    # For exclusive strategy, only use extensions with specialized extractors
    # (exclude extensions that only have the fallback basic_file_info_extractor)
    registry = get_registry()
    supported_extensions = registry.get_supported_extensions(exclude_fallback=True)
    extension_arg = None if strategy == "inclusive" else supported_extensions

    try:
        files = gnu_find_files_by_mtime(path, dt_from, dt_to, extensions=extension_arg)

    # exclude following from coverage because find_files_by_mtime is deprecated as of
    # 1.2.0 and does not support extensions at all (like the above method)
    except (NotImplementedError, RuntimeError) as exception:  # pragma: no cover
        _logger.warning(
            "GNU find returned error: %s\nFalling back to pure Python implementation",
            exception,
        )
        files = find_files_by_mtime(path, dt_from, dt_to)
    return files


def dump_record(
    session: Session,
    filename: Path | None = None,
    *,
    generate_previews: bool = True,
) -> Path:
    """
    Dump a record to an XML file.

    Writes an XML record for a :py:class:`~nexusLIMS.db.session_handler.Session`
    composed of information pulled from the appropriate reservation system
    as well as metadata extracted from the microscope data (e.g. dm3 or
    other files).

    Parameters
    ----------
    session : nexusLIMS.db.session_handler.Session
        A :py:class:`~nexusLIMS.db.session_handler.Session` object
        representing a unit of time on one of the instruments known to NexusLIMS
    filename : typing.Optional[pathlib.Path]
        The filename of the dumped xml file to write. If None, a default name
        will be generated from the other parameters
    generate_previews : bool
        Whether or not to create the preview thumbnail images

    Returns
    -------
    filename : pathlib.Path
        The name of the created record that was returned
    """
    if filename is None:
        filename = Path(
            "compiled_record"
            + (f"_{session.instrument.name}" if session.instrument else "")
            + session.dt_from.strftime("_%Y-%m-%d")
            + (f"_{session.user}" if session.user else "")
            + ".xml",
        )
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open(mode="w", encoding="utf-8") as f:
        text = build_record(session=session, generate_previews=generate_previews)
        f.write(text)
    return filename


def validate_record(xml_filename):
    """
    Validate an .xml record against the Nexus schema.

    Parameters
    ----------
    xml_filename : str or io.StringIO or io.BytesIO
        The path to the xml file to be validated (can also be a file-like
        object like StringIO or BytesIO)

    Returns
    -------
    validates : bool
        Whether the record validates against the Nexus schema
    """
    xsd_doc = etree.parse(XSD_PATH)
    xml_schema = etree.XMLSchema(xsd_doc)
    xml_doc = etree.parse(xml_filename)

    return xml_schema.validate(xml_doc)


def build_new_session_records(
    generate_previews: bool = True,  # noqa: FBT002, FBT001
) -> tuple[List[Path], List[Session]]:
    """
    Build records for new sessions from the database.

    Uses :py:func:`~nexusLIMS.db.session_handler.get_sessions_to_build`) and builds
    those records using :py:func:`build_record` (saving to the NexusLIMS folder), and
    returns a list of resulting .xml files to be uploaded to CDCS.

    Returns
    -------
    xml_files : typing.List[pathlib.Path]
        A list of record files that were successfully built and saved to
        centralized storage
    sessions_built : typing.List[Session]
        Corresponding Session objects for each built XML file (same length and order)
    """
    # get the list of sessions with 'TO_BE_BUILT' status; does not fetch new
    # usage events from any NEMO instances;
    # nexusLIMS.harvesters.nemo.add_all_usage_events_to_db() must be used
    # first to do so
    sessions = get_sessions_to_build()
    if not sessions:
        sys.exit("No 'TO_BE_BUILT' sessions were found. Exiting.")
    xml_files = []
    sessions_built = []
    # loop through the sessions
    for s in sessions:
        try:
            db_row = s.insert_record_generation_event()
            record_text = build_record(session=s, generate_previews=generate_previews)
        except (  # pylint: disable=broad-exception-caught
            FileNotFoundError,
            Exception,
        ) as exception:
            if isinstance(exception, FileNotFoundError):
                # if no files were found for this session log, mark it as so in
                # the database
                path = join_instrument_filestore_path(s.instrument.filestore_path)
                _logger.warning(
                    "No files found in %s between %s and %s",
                    path,
                    s.dt_from.isoformat(),
                    s.dt_to.isoformat(),
                )

                if has_delay_passed(s.dt_to):
                    _logger.warning(
                        'Marking %s as "NO_FILES_FOUND"',
                        s.session_identifier,
                    )
                    s.update_session_status(RecordStatus.NO_FILES_FOUND)
                else:
                    # if the delay hasn't passed, log and delete the record
                    # generation event we inserted previously
                    _logger.warning(
                        "Configured record building delay has not passed; "
                        "Removing previously inserted RECORD_GENERATION row for %s",
                        s.session_identifier,
                    )
                    # Delete the RECORD_GENERATION log using SQLModel
                    with DBSession(get_engine()) as db_session:
                        statement = select(SessionLog).where(
                            SessionLog.id_session_log == db_row["id_session_log"]
                        )
                        log = db_session.exec(statement).first()
                        if log:
                            db_session.delete(log)
                            db_session.commit()
            elif isinstance(exception, nemo.exceptions.NoDataConsentError):
                _logger.warning(
                    "User requested this session not be harvested, "
                    "so no record was built. %s",
                    exception,
                )
                _logger.info('Marking %s as "NO_CONSENT"', s.session_identifier)
                s.update_session_status(RecordStatus.NO_CONSENT)
            elif isinstance(exception, nemo.exceptions.NoMatchingReservationError):
                _logger.warning(
                    "No matching reservation found for this session, "
                    "so assuming no consent was given. %s",
                    exception,
                )
                _logger.info('Marking %s as "NO_RESERVATION"', s.session_identifier)
                s.update_session_status(RecordStatus.NO_RESERVATION)
            else:
                _logger.exception("Could not generate record text")
                _logger.exception('Marking %s as "ERROR"', s.session_identifier)
                s.update_session_status(RecordStatus.ERROR)
        else:
            xml_files, sessions_built = _record_validation_flow(
                record_text, s, xml_files, sessions_built
            )

    return xml_files, sessions_built


def _record_validation_flow(
    record_text, s, xml_files, sessions_built
) -> tuple[List[Path], List[Session]]:
    if validate_record(BytesIO(bytes(record_text, "UTF-8"))):
        _logger.info("Validated newly generated record")
        # generate filename for saved record and make sure path exists
        if s.instrument.harvester == "nemo":
            # for NEMO session_identifier is a URL of usage_event
            unique_suffix = f"{nemo_utils.id_from_url(s.session_identifier)}"
        else:  # pragma: no cover
            # assume session_identifier is a UUID
            unique_suffix = f"{s.session_identifier.split('-')[0]}"
        basename = (
            f"{s.dt_from.strftime('%Y-%m-%d')}_{s.instrument.name}_{unique_suffix}.xml"
        )
        filename = settings.records_dir_path / basename
        filename.parent.mkdir(parents=True, exist_ok=True)
        # write the record to disk and append to list of files generated
        with filename.open(mode="w", encoding="utf-8") as f:
            f.write(record_text)
        _logger.info("Wrote record to %s", filename)
        xml_files.append(Path(filename))
        sessions_built.append(s)
        # Note: Session status will be updated after export attempt
        _logger.info(
            "Built record for %s, will export to destinations", s.session_identifier
        )
    else:
        _logger.error('Marking %s as "ERROR"', s.session_identifier)
        _logger.error("Could not validate record, did not write to disk")
        s.update_session_status(RecordStatus.ERROR)

    return xml_files, sessions_built


def process_new_records(  # noqa: PLR0912, PLR0915
    *,
    dry_run: bool = False,
    dt_from: dt | None = None,
    dt_to: dt | None = None,
):
    """
    Process new records (this is the main entrypoint to the record builder).

    Using :py:meth:`build_new_session_records()`, process new records,
    save them to disk, and upload them to the NexusLIMS CDCS instance.

    Parameters
    ----------
    dry_run
        Controls whether or not records will actually be built. If ``True``,
        session harvesting and file finding will be performed, but no preview
        images or records will be built. Can be used to see what _would_ happen
        if ``dry_run`` is set to ``False``.
    dt_from
        The point in time after which sessions will be fetched. If ``None``,
        no date filtering will be performed. This parameter currently only
        has an effect for the NEMO harvester.
    dt_to
        The point in time before which sessions will be fetched. If ``None``,
        no date filtering will be performed. This parameter currently only
        has an effect for the NEMO harvester.
    """
    results = run_preflight_checks(dry_run=dry_run)
    for r in results:
        if r.passed:
            level = logging.DEBUG
        else:
            level = logging.ERROR if r.severity == "error" else logging.WARNING
        status = "PASS" if r.passed else "FAIL"
        _logger.log(level, "[preflight] %s: %s — %s", r.name, status, r.message)

    failed_errors = [r for r in results if not r.passed and r.severity == "error"]
    if failed_errors:
        raise PreflightError(failed_errors)

    if dry_run:
        _logger.info("!!DRY RUN!! Only finding files, not building records")
        # get 'TO_BE_BUILT' sessions from the database
        sessions = get_sessions_to_build()
        # get Session objects for NEMO usage events without adding to DB
        # DONE: NEMO usage events fetched should take a time range;
        sessions += nemo_utils.get_usage_events_as_sessions(
            dt_from=dt_from,
            dt_to=dt_to,
        )
        if not sessions:
            _logger.warning("No 'TO_BE_BUILT' sessions were found. Exiting.")
            return
        for s in sessions:
            # at this point, sessions can be from any type of harvester
            _logger.info("")
            _logger.info("")
            try:
                get_reservation_event(s)
            except nemo.exceptions.NoDataConsentError as e:
                _logger.warning(
                    "User requested this session not be harvested, "
                    "skipping dry run for this session. %s",
                    e,
                )
                continue
            except nemo.exceptions.NoMatchingReservationError as e:
                _logger.warning(
                    "No matching reservation found for this session, "
                    "skipping dry run for this session. %s",
                    e,
                )
                continue
            dry_run_file_find(s)
    else:
        nemo_utils.add_all_usage_events_to_db(dt_from=dt_from, dt_to=dt_to)
        xml_files, sessions_built = build_new_session_records()
        if len(xml_files) == 0:
            _logger.warning("No XML files built, so no files exported")
        else:
            # Export records to all configured destinations
            export_results = export_records(xml_files, sessions_built)

            # Update session status based on export results
            sessions_by_file = dict(zip(xml_files, sessions_built, strict=True))
            for xml_file, session in sessions_by_file.items():
                if was_successfully_exported(xml_file, export_results):
                    session.update_session_status(RecordStatus.COMPLETED)
                    _logger.info(
                        'Marking %s as "COMPLETED"', session.session_identifier
                    )
                else:
                    session.update_session_status(RecordStatus.BUILT_NOT_EXPORTED)
                    _logger.error(
                        'All exports failed for %s, marking as "BUILT_NOT_EXPORTED"',
                        session.session_identifier,
                    )

            # Move successfully exported files to uploaded directory
            files_exported = [
                f for f in xml_files if was_successfully_exported(f, export_results)
            ]
            for f in files_exported:
                uploaded_dir = settings.records_dir_path / "uploaded"
                Path(uploaded_dir).mkdir(parents=True, exist_ok=True)

                shutil.copy2(f, uploaded_dir)
                Path(f).unlink()

            files_not_exported = [f for f in xml_files if f not in files_exported]
            if len(files_not_exported) > 0:
                _logger.error(
                    "Some record files were not exported: %s",
                    files_not_exported,
                )
    return


def dry_run_file_find(s: Session) -> List[Path]:
    """
    Get the files that *would* be included for a record built for the supplied session.

    Parameters
    ----------
    s : nexusLIMS.db.session_handler.Session
        A session read from the database

    Returns
    -------
    files : typing.List[pathlib.Path]
        A list of Paths containing the files that would be included for the
        record of this session (if it were not a dry run)
    """
    path = join_instrument_filestore_path(s.instrument.filestore_path)
    _logger.info(
        "Searching for files for %s in %s between %s and %s",
        s.instrument.name,
        path,
        s.dt_from.isoformat(),
        s.dt_to.isoformat(),
    )
    files = get_files(path, s.dt_from, s.dt_to)

    _logger.info("Results for %s on %s:", s.session_identifier, s.instrument)
    if len(files) == 0:
        _logger.warning("No files found for this session")
    else:
        _logger.info("Found %i files for this session", len(files))
    for f in files:
        mtime = dt.fromtimestamp(
            f.stat().st_mtime,
            tz=s.instrument.timezone,
        ).isoformat()
        _logger.info("*mtime* %s - %s", mtime, f)
    return files


if __name__ == "__main__":  # pragma: no cover
    # If running as a module, process new records (with some control flags)
    from nexusLIMS.utils import setup_loggers

    parser = argparse.ArgumentParser()

    # Optional argument flag which defaults to False
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        dest="dry_run",
        default=False,
    )

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity (-v, -vv); corresponds to python logging level. "
        "0 is WARN, 1 (-v) is INFO, 2 (-vv) is DEBUG. ERROR and "
        "CRITICAL are always shown.",
    )

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (version {version})",
    )

    args = parser.parse_args()

    # set up logging
    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}

    if args.dry_run and args.verbose <= 0:
        _logger.warning('Increasing verbosity so output of "dry-run" will be shown')
        args.verbose = 1

    setup_loggers(logging_levels[args.verbose])
    # when running as script, __name__ is "__main__", so we need to set level
    # explicitly since the setup_loggers function won't find it
    _logger.setLevel(logging_levels[args.verbose])

    # by default only fetch the last week's worth of data from the NEMO
    # harvesters to speed things up
    process_new_records(
        dry_run=args.dry_run,
        dt_from=dt.now(tz=current_system_tz()) - td(weeks=1),
    )
