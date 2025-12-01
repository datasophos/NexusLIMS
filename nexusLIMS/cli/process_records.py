"""
CLI command to process new NexusLIMS records.

This module provides a command-line interface for running the NexusLIMS record
builder with file locking, timestamped logging, and email notifications.
It replaces the functionality previously provided by process_new_records.sh.

Usage
-----

.. code-block:: bash

    uv run python -m nexusLIMS.cli.process_records [OPTIONS]

or

.. code-block:: bash

    uv run nexuslims-process-records [OPTIONS]

Options
-------

.. code-block:: bash

    -n, --dry-run   : Dry run mode (find files without building records)
    -v, --verbose   : Increase verbosity (-v for INFO, -vv for DEBUG)
    --version       : Show version and exit
    --help          : Show help message and exit
"""

import logging
import re
import smtplib
import sys
from datetime import UTC, datetime
from email.mime.text import MIMEText
from pathlib import Path

import click
from filelock import FileLock, Timeout
from rich.console import Console
from rich.logging import RichHandler

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


def setup_file_logging(dry_run: bool = False) -> Path:  # noqa: FBT001, FBT002
    """
    Set up file logging with timestamped log file.

    Creates a log directory structure based on the current date and adds a
    FileHandler to the root logger. Log files are named with timestamps
    in the format YYYYMMDD-HHMM.log (or YYYYMMDD-HHMM_dryrun.log for dry runs).

    Parameters
    ----------
    dry_run : bool
        If True, append '_dryrun' to the log filename

    Returns
    -------
    log_file: pathlib.Path
        Path to the created log file

    Raises
    ------
    OSError
        If log directory creation fails
    """
    from nexusLIMS.config import settings  # noqa: PLC0415

    now = datetime.now(tz=UTC)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")
    timestamp = now.strftime("%Y%m%d-%H%M")

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

    return log_file


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
    email_config = settings.email_config
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


@click.command(
    epilog="""
Examples:

  \b
  # Normal run (process records)
  $ nexuslims-process-records

  \b
  # Dry run (find files only)
  $ nexuslims-process-records -n

  \b
  # Verbose output
  $ nexuslims-process-records -vv
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
@click.version_option(package_name="nexusLIMS", prog_name="nexusLIMS")
def main(*, dry_run: bool, verbose: int) -> None:
    """
    Process new NexusLIMS records with logging and email notifications.

    This command runs the NexusLIMS record builder to process new experimental
    sessions and generate XML records. It provides file locking to prevent
    concurrent runs, timestamped logging, and email notifications on errors.
    """
    from nexusLIMS.builder.record_builder import process_new_records  # noqa: PLC0415
    from nexusLIMS.config import settings  # noqa: PLC0415
    from nexusLIMS.utils import setup_loggers  # noqa: PLC0415

    # Determine log level from verbose count
    # 0 = WARNING, 1 = INFO, 2+ = DEBUG
    if verbose == 0:
        log_level = logging.WARNING
    elif verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    # Setup console logging with rich
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    # Setup all nexusLIMS loggers
    setup_loggers(log_level)

    logger.info("Starting NexusLIMS record processor")
    logger.info("Dry run: %s", dry_run)

    # Setup file logging
    try:
        log_file = setup_file_logging(dry_run)
    except OSError:
        logger.exception("Failed to setup file logging")
        console.print("[bold red]Failed to setup file logging[/bold red]")
        sys.exit(1)

    # Acquire file lock
    lock_file = settings.lock_file_path
    lock = FileLock(str(lock_file), timeout=0)

    try:
        logger.info("Attempting to acquire lock at %s", lock_file)
        with lock:
            logger.info("Lock acquired successfully")

            # Run the record builder
            try:
                process_new_records(dry_run=dry_run)
                logger.info("Record processing completed")
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

    # Check log for errors and send email if needed
    try:
        has_errors, found_patterns = check_log_for_errors(log_file)
        if has_errors:
            logger.info("Errors detected in log, sending notification")
            send_error_notification(log_file, found_patterns)
        else:
            logger.info("No errors detected in log")
    except Exception:
        logger.exception("Error while checking log or sending notification")

    logger.info("NexusLIMS record processor finished")


if __name__ == "__main__":  # pragma: no cover
    main()
