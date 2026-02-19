# ruff: noqa: FBT001
"""
CLI command to process new NexusLIMS records.

This module provides a command-line interface for running the NexusLIMS record
builder with file locking, timestamped logging, and email notifications.
It replaces the functionality previously provided by process_new_records.sh.

Usage
-----

.. code-block:: bash

    nexuslims build-records [OPTIONS]

Options
-------

.. code-block:: bash

    -n, --dry-run   : Dry run mode (find files without building records)
    -v, --verbose   : Increase verbosity (-v for INFO, -vv for DEBUG)
    --from <date>   : Start date for filtering (ISO format). Defaults to 1 week ago.
                      Use "none" to disable lower bound.
    --to <date>     : End date for filtering (ISO format). Omit to disable upper bound.
    --version       : Show version and exit
    --help          : Show help message and exit
"""

import json
import logging
import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import click
from filelock import FileLock, Timeout
from rich.console import Console
from rich.logging import RichHandler

from nexusLIMS.builder.preflight import PreflightError
from nexusLIMS.cli import _format_version

# Heavy NexusLIMS imports are lazy-loaded inside functions to speed up --help/--version
# See: setup_file_logging(), send_error_notification(), and main()

logger = logging.getLogger(__name__)
console = Console()


# Error patterns to search for in log files
ERROR_PATTERNS = [
    re.compile(r"\bcritical\b", re.IGNORECASE),
    re.compile(r"\berror\b", re.IGNORECASE),
    re.compile(r"\bfatal\b", re.IGNORECASE),
]

# Patterns to exclude from error detection (known non-critical errors)
EXCLUDE_PATTERNS = [
    "Temporary failure in name resolution",
    "NoDataConsentError",
    "NoMatchingReservationError",
]


def setup_file_logging(dry_run: bool = False) -> tuple[Path, logging.FileHandler]:  # noqa: FBT002
    """
    Set up file logging with timestamped log file.

    Creates a log directory structure based on the current date and adds a
    FileHandler to the root logger. Log files are named with timestamps
    in the format YYYYMMDD-HHMM.log (or YYYYMMDD-HHMM_dryrun.log for dry runs).

    Note: This function removes any existing FileHandlers from the root logger
    before adding the new handler to prevent handler accumulation across multiple
    invocations (important for testing scenarios where the same process runs
    multiple CLI commands).

    Parameters
    ----------
    dry_run : bool
        If True, append '_dryrun' to the log filename

    Returns
    -------
    tuple[pathlib.Path, logging.FileHandler]
        A tuple containing:
        - Path to the created log file
        - The FileHandler instance that was added to the root logger

    Raises
    ------
    OSError
        If log directory creation fails
    """
    from nexusLIMS.config import settings  # noqa: PLC0415

    # Remove any existing FileHandlers from root logger to prevent accumulation
    # This is critical when the function is called multiple times (e.g., in tests)
    # to ensure log messages go only to the current log file
    for handler in logging.root.handlers[
        :
    ]:  # Use slice to avoid modifying list during iteration
        if isinstance(handler, logging.FileHandler):
            logging.root.removeHandler(handler)
            handler.close()

    now = datetime.now().astimezone()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")
    # Include seconds in timestamp to prevent collisions when multiple runs
    # happen in same minute
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    # Create log directory structure: logs/YYYY/MM/DD/
    log_dir = settings.log_dir_path / year / month / day
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log filename
    suffix = "_dryrun" if dry_run else ""
    log_file = log_dir / f"{timestamp}{suffix}.log"

    # Add file handler to root logger
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
    )
    logging.root.addHandler(file_handler)

    logger.info("Logging to file: %s", log_file)

    return log_file, file_handler


def check_log_for_errors(log_path: Path) -> tuple[bool, list[str]]:
    """
    Check log file for error patterns.

    Reads the log file and searches for error patterns (critical, error, fatal)
    while excluding known non-critical error patterns.

    Parameters
    ----------
    log_path : pathlib.Path
        Path to the log file to check

    Returns
    -------
    tuple[bool, list[str]]
        A tuple containing:
        - bool: True if errors were found, False otherwise
        - list[str]: List of error pattern names that were found

    Raises
    ------
    FileNotFoundError
        If the log file doesn't exist
    """
    if not log_path.exists():
        logger.error("Log file not found: %s", log_path)
        return False, []

    try:
        log_contents = log_path.read_text()
    except OSError:
        logger.exception("Failed to read log file: %s", log_path)
        return False, []

    # Check if any exclude patterns are present
    for exclude_pattern in EXCLUDE_PATTERNS:
        if exclude_pattern in log_contents:
            logger.debug("Found excluded pattern: %s", exclude_pattern)
            # If we find an excluded pattern, don't send email
            return False, []

    # Check for error patterns
    found_patterns = []
    for pattern in ERROR_PATTERNS:
        if pattern.search(log_contents):
            pattern_name = pattern.pattern.strip("\\b").lower()
            found_patterns.append(pattern_name)
            logger.debug("Found error pattern: %s", pattern_name)

    has_errors = len(found_patterns) > 0
    return has_errors, found_patterns


def send_error_notification(log_path: Path, found_patterns: list[str]) -> None:
    """
    Send error notification email.

    Sends an email notification with the log file contents when errors are
    detected. Email sending is skipped if email configuration is not available.

    Parameters
    ----------
    log_path : pathlib.Path
        Path to the log file to include in the email
    found_patterns : list[str]
        List of error pattern names that were found in the log

    Returns
    -------
    None
        This function doesn't return anything. Errors are logged but not raised.

    Notes
    -----
    - Email sending is gracefully skipped if configuration is missing
    - Any email sending errors are logged but don't cause the function to fail
    - Uses SMTP with TLS encryption if configured
    """
    from nexusLIMS.config import settings  # noqa: PLC0415

    # Check if email is configured
    email_config = settings.email_config()
    if email_config is None:
        logger.info("Email not configured, skipping notification")
        return

    logger.info("Sending error notification email")

    try:
        # Read log file contents
        log_contents = log_path.read_text()

        # Build email message
        subject = "ERROR in NexusLIMS record builder"
        body = f"""There was an error (or unusual output) in the record builder.
Here is the output of {log_path}.
To help you debug, the following "bad" strings were found in the output:

{", ".join(found_patterns)}

{log_contents}"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_config.sender
        msg["To"] = ", ".join(email_config.recipients)

        # Send email via SMTP
        smtp_class = smtplib.SMTP
        with smtp_class(
            email_config.smtp_host, email_config.smtp_port, timeout=30
        ) as server:
            if email_config.use_tls:
                server.starttls()

            # Authenticate if credentials provided
            if email_config.smtp_username and email_config.smtp_password:
                server.login(email_config.smtp_username, email_config.smtp_password)

            # Send message
            server.send_message(msg)

        logger.info("Error notification email sent successfully")

    except smtplib.SMTPException:
        logger.exception("Failed to send error notification email")
    except OSError:
        logger.exception("Failed to read log file for email: %s", log_path)
    except Exception:
        logger.exception("Unexpected error while sending email")


def _get_log_level(verbose: int) -> int:
    """
    Convert verbose count to logging level.

    Parameters
    ----------
    verbose : int
        Verbosity level (0 = WARNING, 1 = INFO, 2+ = DEBUG)

    Returns
    -------
    int
        Logging level constant from the logging module
    """
    if verbose == 0:
        return logging.WARNING
    if verbose == 1:
        return logging.INFO
    return logging.DEBUG


def _setup_logging(log_level: int, dry_run: bool) -> tuple[Path, logging.FileHandler]:
    """
    Configure console and file logging.

    Parameters
    ----------
    log_level : int
        Logging level constant from the logging module
    dry_run : bool
        If True, append '_dryrun' to the log filename

    Returns
    -------
    tuple[Path, logging.FileHandler]
        Tuple of (log_file_path, file_handler)

    Raises
    ------
    OSError
        If file logging setup fails
    SystemExit
        If file logging setup fails (exits with code 1)
    """
    from nexusLIMS.utils.logging import setup_loggers  # noqa: PLC0415

    # Setup console logging with rich
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    # Setup all nexusLIMS loggers
    setup_loggers(log_level)

    # Setup file logging
    try:
        return setup_file_logging(dry_run)
    except OSError:
        logger.exception("Failed to setup file logging")
        console.print("[bold red]Failed to setup file logging[/bold red]")
        sys.exit(1)


def _run_with_lock(
    dry_run: bool, dt_from: datetime | None, dt_to: datetime | None
) -> None:
    """
    Run the record builder with file locking.

    Parameters
    ----------
    dry_run : bool
        If True, run in dry-run mode (find files without building records)
    dt_from : datetime | None
        The point in time after which sessions will be fetched
    dt_to : datetime | None
        The point in time before which sessions will be fetched

    Returns
    -------
    None

    Raises
    ------
    SystemExit
        If lock cannot be acquired (another instance is running)
    """
    from nexusLIMS.builder import record_builder  # noqa: PLC0415
    from nexusLIMS.config import settings  # noqa: PLC0415

    lock_file = settings.lock_file_path
    lock = FileLock(str(lock_file), timeout=0)

    try:
        logger.info("Attempting to acquire lock at %s", lock_file)
        with lock:
            logger.info("Lock acquired successfully")
            try:
                record_builder.process_new_records(
                    dry_run=dry_run, dt_from=dt_from, dt_to=dt_to
                )
                logger.info("Record processing completed")
            except PreflightError as e:
                logger.error(  # noqa: TRY400
                    "Preflight checks failed — record builder aborted"
                )
                for check in e.failed_checks:
                    logger.error("  [%s] %s", check.name, check.message)  # noqa: TRY400
            except Exception:
                logger.exception("Error during record processing")

    except Timeout:
        logger.warning(
            "Lock file already exists at %s - another instance is running",
            lock_file,
        )
        console.print(f"[yellow]Lock file already exists at {lock_file}[/yellow]")
        console.print("[yellow]Another instance is already running. Exiting.[/yellow]")
        sys.exit(0)


def _parse_date_argument(
    date_str: str | None, *, inclusive_end: bool = False
) -> datetime | None:
    """
    Parse a date string argument into a datetime object.

    Parameters
    ----------
    date_str : str | None
        Date string in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS),
        or special values "none"/"all" to disable filtering,
        or None to return None
    inclusive_end : bool
        If True and date_str has no time component, set time to 23:59:59
        to include the entire day. Used for --to parameter to make date
        ranges inclusive. Default is False (use midnight).

    Returns
    -------
    datetime | None
        Parsed datetime with system timezone, or None if date_str is None
        or a special value

    Raises
    ------
    click.BadParameter
        If date string cannot be parsed
    """
    if date_str is None:
        return None

    # Check for special values that disable filtering
    if date_str.lower() in ("none", "all"):
        return None

    # Parse ISO format date string
    try:
        # Try parsing with time component first
        if "T" in date_str:
            dt_obj = datetime.fromisoformat(date_str)
        # Parse date-only string
        elif inclusive_end:
            # For inclusive end dates, set time to end of day
            dt_obj = datetime.fromisoformat(date_str + "T23:59:59")
        else:
            # For start dates, set time to midnight
            dt_obj = datetime.fromisoformat(date_str + "T00:00:00")

        # Ensure timezone-aware datetime using system timezone
        if dt_obj.tzinfo is None:
            from nexusLIMS.utils.time import current_system_tz  # noqa: PLC0415

            dt_obj = dt_obj.replace(tzinfo=current_system_tz())
    except ValueError as e:
        msg = (
            f"Invalid date format: {date_str}. "
            f"Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) "
            f'or special value "none" to disable filtering.'
        )
        raise click.BadParameter(msg) from e
    else:
        return dt_obj


def _handle_error_notification(
    log_file: Path, file_handler: logging.FileHandler
) -> None:
    """
    Check log for errors and send notification if needed.

    Parameters
    ----------
    log_file : Path
        Path to the log file to check
    file_handler : logging.FileHandler
        File handler to flush before checking log

    Returns
    -------
    None
        This function doesn't return anything. All errors are caught and logged.
    """
    # Ensure file handler is flushed before checking log
    # This is important for error detection to work correctly
    file_handler.flush()

    logger.info("NexusLIMS record processor finished")

    try:
        has_errors, found_patterns = check_log_for_errors(log_file)
        if has_errors:
            logger.info("Errors detected in log, sending notification")
            send_error_notification(log_file, found_patterns)
        else:
            logger.info("No errors detected in log")
    except Exception:
        logger.exception("Error while checking log or sending notification")
    finally:
        # Clean up file handler after all logging is complete
        logging.root.removeHandler(file_handler)
        file_handler.close()


@click.command(
    epilog="""
Examples:

  \b
  # Normal run (process records from last week)
  $ nexuslims build-records

  \b
  # Process all sessions (no date filtering)
  $ nexuslims build-records --from=none

  \b
  # Process sessions since a specific date
  $ nexuslims build-records --from=2025-01-01

  \b
  # Process a specific date range
  $ nexuslims build-records --from=2025-01-01 --to=2025-01-31

  \b
  # Dry run (find files only)
  $ nexuslims build-records -n

  \b
  # Verbose output
  $ nexuslims build-records -vv
"""
)
@click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    help="Dry run: find files without building records",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for INFO, -vv for DEBUG)",
)
@click.option(
    "--from",
    "from_arg",
    type=str,
    default=None,
    help="Start date for session filtering (ISO format: YYYY-MM-DD). "
    'Defaults to 1 week ago. Use "none" to disable lower bound.',
)
@click.option(
    "--to",
    "to_arg",
    type=str,
    default=None,
    help="End date for session filtering (ISO format: YYYY-MM-DD). "
    "Omit to disable upper bound.",
)
@click.version_option(version=None, message=_format_version("nexuslims build-records"))
def main(
    *, dry_run: bool, verbose: int, from_arg: str | None, to_arg: str | None
) -> None:
    """
    Process new NexusLIMS records with logging and email notifications.

    This command runs the NexusLIMS record builder to process new experimental
    sessions and generate XML records. It provides file locking to prevent
    concurrent runs, timestamped logging, and email notifications on errors.

    By default, only sessions from the last week are processed. Use --from=none
    to process all sessions, or specify custom date ranges with --from and --to.
    """
    from nexusLIMS.cli import handle_config_error  # noqa: PLC0415

    with handle_config_error():
        # Setup logging (accesses settings for log directory path)
        log_level = _get_log_level(verbose)
        log_file, file_handler = _setup_logging(log_level, dry_run)

        # Parse date arguments from raw string parameters
        dt_from = _parse_date_argument(from_arg)
        dt_to = _parse_date_argument(to_arg, inclusive_end=True)

        # Apply default: fetch last week if no --from was provided
        # (Don't apply if user explicitly passed --from=none)
        if from_arg is None:
            from nexusLIMS.utils.time import current_system_tz  # noqa: PLC0415

            dt_from = datetime.now(tz=current_system_tz()) - timedelta(weeks=1)

        # Log startup information
        logger.info("Starting NexusLIMS record processor")
        logger.info("Dry run: %s", dry_run)
        if dt_from is not None:
            logger.info("Fetching sessions from: %s", dt_from.isoformat())
        else:
            logger.info("Fetching sessions from: (no lower bound)")
        if dt_to is not None:
            logger.info("Fetching sessions to: %s", dt_to.isoformat())
        else:
            logger.info("Fetching sessions to: (no upper bound)")

        # Dump sanitized effective configuration when verbose
        if verbose >= 1:
            from nexusLIMS.cli.config import (  # noqa: PLC0415
                _build_config_dict,
                _sanitize_config,
            )
            from nexusLIMS.config import settings  # noqa: PLC0415

            logger.info(
                "Effective configuration:\n%s",
                json.dumps(
                    _sanitize_config(_build_config_dict(settings)),
                    indent=2,
                    default=str,
                ),
            )

        # Run record builder with file locking
        _run_with_lock(dry_run, dt_from, dt_to)

        # Handle error notifications and cleanup
        _handle_error_notification(log_file, file_handler)


if __name__ == "__main__":  # pragma: no cover
    main()
