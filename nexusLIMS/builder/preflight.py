"""Preflight checks for the NexusLIMS record builder.

This module provides a ``run_preflight_checks()`` function that validates
the environment before the record builder starts any harvesting or record
building work. Misconfigurations are caught early and reported with
actionable messages.

Attributes
----------
CheckResult
    Dataclass representing the result of a single preflight check.
PreflightError
    Exception raised when one or more error-severity checks fail.
"""

import logging
import os
import time
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal

import pytz
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel, select

from nexusLIMS.config import settings
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.models import (  # noqa: F401 — imported to populate SQLModel.metadata
    ExternalUserIdentifier,
    Instrument,
    SessionLog,
    UploadLog,
)
from nexusLIMS.exporters.registry import get_registry
from nexusLIMS.harvesters.nemo.utils import get_harvesters_enabled
from nexusLIMS.utils.network import nexus_req

_logger = logging.getLogger(__name__)

# Absolute path to alembic.ini at the project root (CWD-independent)
_ALEMBIC_INI_PATH = Path(__file__).parents[2] / "alembic.ini"


@dataclass
class CheckResult:
    """Result of a single preflight check.

    Parameters
    ----------
    name
        Short label for the check (e.g. ``"db_tables"``).
    passed
        Whether the check passed.
    severity
        ``"error"`` if the check failure means the run cannot succeed;
        ``"warning"`` if suspicious but the run may still succeed.
    message
        Human-readable, actionable description of the result.
    """

    name: str
    passed: bool
    severity: Literal["error", "warning"]
    message: str


class PreflightError(Exception):
    """Raised when one or more preflight checks with severity='error' fail.

    Parameters
    ----------
    failed_checks
        The list of failed :class:`CheckResult` objects with
        ``severity="error"``.
    """

    def __init__(self, failed_checks: list[CheckResult]) -> None:
        self.failed_checks = failed_checks
        names = ", ".join(c.name for c in failed_checks)
        super().__init__(f"Preflight checks failed: {names}")


# ---------------------------------------------------------------------------
# Individual check helpers
# ---------------------------------------------------------------------------


def _check_db_reachable() -> CheckResult:
    """Check that the SQLite database file exists and is connectable."""
    name = "db_reachable"
    db_path = Path(settings.NX_DB_PATH)

    if not db_path.exists():
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=(
                f"Database file not found: {db_path}. "
                "Run 'nexuslims db init' to create the database."
            ),
        )

    try:
        with DBSession(get_engine()) as session:
            session.exec(text("SELECT 1"))  # type: ignore[call-overload]
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=(
                f"Cannot connect to database at {db_path}: {exc}. "
                "Ensure the file is a valid SQLite database."
            ),
        )

    return CheckResult(
        name=name,
        passed=True,
        severity="error",
        message=f"Database reachable at {db_path}.",
    )


def _check_db_tables() -> CheckResult:
    """Check that all expected ORM tables exist in the database."""
    name = "db_tables"

    # SQLModel.metadata.tables is populated by the model imports at module top
    expected = set(SQLModel.metadata.tables.keys())

    try:
        with DBSession(get_engine()) as session:
            rows = session.exec(
                text("SELECT name FROM sqlite_master WHERE type='table'")  # type: ignore[call-overload]
            ).all()
        actual = {row[0] for row in rows}
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=f"Could not query database tables: {exc}",
        )

    missing = expected - actual
    if missing:
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=(
                f"Missing tables: {', '.join(sorted(missing))}. "
                "Run 'nexuslims db upgrade' to apply migrations."
            ),
        )

    return CheckResult(
        name=name,
        passed=True,
        severity="error",
        message=f"All expected tables present: {', '.join(sorted(expected))}.",
    )


def _check_alembic_migration() -> CheckResult:
    """Check that the database schema is at the latest Alembic migration."""
    name = "alembic_migration"

    try:
        cfg = Config(str(_ALEMBIC_INI_PATH))
        # script_location in alembic.ini is a relative path; resolve it to an
        # absolute path so the check works regardless of CWD.
        cfg.set_main_option(
            "script_location",
            str(_ALEMBIC_INI_PATH.parent / "nexusLIMS" / "db" / "migrations"),
        )
        script = ScriptDirectory.from_config(cfg)
        head_rev = script.get_current_head()
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=f"Could not determine Alembic head revision: {exc}",
        )

    if head_rev is None:
        # No migrations defined yet — nothing to check
        return CheckResult(
            name=name,
            passed=True,
            severity="error",
            message="No Alembic revisions found; skipping migration check.",
        )

    # Query current revision from the database
    try:
        with DBSession(get_engine()) as session:
            # Check if alembic_version table exists first
            tables_result = session.exec(
                text(  # type: ignore[call-overload]
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='alembic_version'"
                )
            ).first()
            if tables_result is None:
                return CheckResult(
                    name=name,
                    passed=False,
                    severity="error",
                    message=(
                        "alembic_version table not found — database is not managed by "
                        "Alembic. Run 'nexuslims db upgrade' to initialise migrations."
                    ),
                )
            current_rev = session.exec(
                text("SELECT version_num FROM alembic_version")  # type: ignore[call-overload]
            ).first()
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=f"Could not query alembic_version: {exc}",
        )

    current = current_rev[0] if current_rev else None

    if current == head_rev:
        return CheckResult(
            name=name,
            passed=True,
            severity="error",
            message=f"Database schema is up to date (revision {current}).",
        )

    return CheckResult(
        name=name,
        passed=False,
        severity="error",
        message=(
            f"Database schema is out of date: current={current!r}, "
            f"head={head_rev!r}. Run 'nexuslims db upgrade' to apply pending "
            "migrations."
        ),
    )


def _check_instruments_exist() -> CheckResult:
    """Check that at least one instrument is registered in the database."""
    name = "instruments_exist"

    try:
        with DBSession(get_engine()) as session:
            count = session.exec(
                text("SELECT COUNT(*) FROM instruments")  # type: ignore[call-overload]
            ).first()
        n = count[0] if count else 0
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="warning",
            message=f"Could not query instruments table: {exc}",
        )

    if n == 0:
        return CheckResult(
            name=name,
            passed=False,
            severity="warning",
            message=(
                "No instruments found in the database. "
                "Add instruments with 'nexuslims instruments add' before building "
                "records."
            ),
        )

    return CheckResult(
        name=name,
        passed=True,
        severity="warning",
        message=f"Found {n} instrument(s) in the database.",
    )


def _check_instrument_filestore_paths() -> list[CheckResult]:
    """Check each instrument filestore path exists under NX_INSTRUMENT_DATA_PATH."""
    name = "instrument_filestore_paths"
    base = Path(settings.NX_INSTRUMENT_DATA_PATH)

    if not base.exists():
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="warning",
                message=(
                    f"NX_INSTRUMENT_DATA_PATH ({base}) does not exist or is not "
                    "mounted. Instrument file searches will fail."
                ),
            )
        ]

    try:
        with DBSession(get_engine()) as session:
            instruments = session.exec(select(Instrument)).all()
    except Exception as exc:
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="warning",
                message=f"Could not query instruments for filestore path check: {exc}",
            )
        ]

    if not instruments:
        return [
            CheckResult(
                name=name,
                passed=True,
                severity="warning",
                message="No instruments in DB; skipping filestore path check.",
            )
        ]

    results = []
    for instr in instruments:
        path = base / instr.filestore_path
        if not path.exists():
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    severity="warning",
                    message=(
                        f"Instrument '{instr.instrument_pid}': filestore path "
                        f"{path} does not exist."
                    ),
                )
            )

    if not results:
        return [
            CheckResult(
                name=name,
                passed=True,
                severity="warning",
                message=(
                    f"All {len(instruments)} instrument filestore path(s) exist "
                    f"under {base}."
                ),
            )
        ]

    return results


def _check_instrument_harvesters() -> list[CheckResult]:
    """Check that each instrument's harvester module is importable and complete."""
    name = "instrument_harvesters"

    try:
        with DBSession(get_engine()) as session:
            instruments = session.exec(select(Instrument)).all()
    except Exception as exc:
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="error",
                message=f"Could not query instruments for harvester check: {exc}",
            )
        ]

    if not instruments:
        return [
            CheckResult(
                name=name,
                passed=True,
                severity="error",
                message="No instruments in DB; skipping harvester check.",
            )
        ]

    # Group instruments by harvester name
    harvester_to_instruments: dict[str, list[str]] = {}
    for instr in instruments:
        harvester_to_instruments.setdefault(instr.harvester, []).append(
            instr.instrument_pid
        )

    results = []
    for harvester_name, pids in harvester_to_instruments.items():
        instrument_list = ", ".join(pids)
        try:
            module = import_module(f".{harvester_name}", "nexusLIMS.harvesters")
        except ImportError as exc:
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    severity="error",
                    message=(
                        f"Harvester module '{harvester_name}' cannot be imported: "
                        f"{exc}. Affected instruments: {instrument_list}."
                    ),
                )
            )
            continue

        if not hasattr(module, "res_event_from_session"):
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    severity="error",
                    message=(
                        f"Harvester '{harvester_name}' is missing required function "
                        f"'res_event_from_session'. Affected instruments: "
                        f"{instrument_list}."
                    ),
                )
            )
        else:
            results.append(
                CheckResult(
                    name=name,
                    passed=True,
                    severity="error",
                    message=(
                        f"Harvester '{harvester_name}' OK "
                        f"(instruments: {instrument_list})."
                    ),
                )
            )

    return results


def _check_instrument_timezones() -> list[CheckResult]:
    """Check that each instrument's timezone string is a valid IANA timezone."""
    name = "instrument_timezones"

    try:
        with DBSession(get_engine()) as session:
            instruments = session.exec(select(Instrument)).all()
    except Exception as exc:
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="warning",
                message=f"Could not query instruments for timezone check: {exc}",
            )
        ]

    if not instruments:
        return [
            CheckResult(
                name=name,
                passed=True,
                severity="warning",
                message="No instruments in DB; skipping timezone check.",
            )
        ]

    # Group instruments by timezone string
    tz_to_instruments: dict[str, list[str]] = {}
    for instr in instruments:
        tz_to_instruments.setdefault(instr.timezone_str, []).append(
            instr.instrument_pid
        )

    results = []
    for tz_str, pids in tz_to_instruments.items():
        instrument_list = ", ".join(pids)
        try:
            pytz.timezone(tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    severity="warning",
                    message=(
                        f"Unknown timezone '{tz_str}'. "
                        f"Affected instruments: {instrument_list}. "
                        "Use a valid IANA timezone (e.g., 'America/New_York')."
                    ),
                )
            )
        else:
            results.append(
                CheckResult(
                    name=name,
                    passed=True,
                    severity="warning",
                    message=(
                        f"Timezone '{tz_str}' is valid "
                        f"(instruments: {instrument_list})."
                    ),
                )
            )

    return results


def _check_data_path_writable() -> CheckResult:
    """Check that NX_DATA_PATH is writable by the current process."""
    name = "data_path_writable"
    data_path = Path(settings.NX_DATA_PATH)

    if not os.access(data_path, os.W_OK):
        return CheckResult(
            name=name,
            passed=False,
            severity="error",
            message=(
                f"NX_DATA_PATH ({data_path}) is not writable. "
                "Ensure the NexusLIMS process has write permission to this directory."
            ),
        )

    return CheckResult(
        name=name,
        passed=True,
        severity="error",
        message=f"NX_DATA_PATH ({data_path}) is writable.",
    )


def _check_export_destinations() -> CheckResult:
    """Check that at least one export destination is enabled and configured."""
    name = "export_destinations"

    try:
        registry = get_registry()
        enabled = registry.get_enabled_destinations()
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            severity="warning",
            message=f"Could not discover export destinations: {exc}",
        )

    if not enabled:
        return CheckResult(
            name=name,
            passed=False,
            severity="warning",
            message=(
                "No export destinations are enabled. Built records will not be "
                "uploaded anywhere. Configure at least one destination "
                "(e.g., NX_CDCS_URL and NX_CDCS_TOKEN for CDCS)."
            ),
        )

    failures = []
    for dest in enabled:
        try:
            valid, err_msg = dest.validate_config()
        except Exception as exc:
            failures.append(f"{dest.name}: unexpected error: {exc}")
            continue
        if not valid:
            failures.append(f"{dest.name}: {err_msg}")

    if failures:
        return CheckResult(
            name=name,
            passed=False,
            severity="warning",
            message=(
                "Some export destinations have configuration issues "
                "(transient network errors may be ignored): " + "; ".join(failures)
            ),
        )

    dest_names = ", ".join(d.name for d in enabled)
    return CheckResult(
        name=name,
        passed=True,
        severity="warning",
        message=f"Export destination(s) OK: {dest_names}.",
    )


def _check_nemo_harvester_config() -> list[CheckResult]:
    """Check NEMO harvester config is present and each instance is reachable."""
    name = "nemo_harvester_config"

    try:
        nemo_harvesters = settings.nemo_harvesters()
    except Exception as exc:
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="warning",
                message=f"Could not read NEMO harvester config: {exc}",
            )
        ]

    if not nemo_harvesters:
        # No harvesters configured — check if any instrument needs one
        try:
            with DBSession(get_engine()) as session:
                nemo_instruments = session.exec(
                    select(Instrument).where(Instrument.harvester == "nemo")
                ).all()
        except Exception as exc:
            return [
                CheckResult(
                    name=name,
                    passed=False,
                    severity="warning",
                    message=(
                        f"No NEMO harvester config found, and could not query "
                        f"instruments: {exc}"
                    ),
                )
            ]

        if not nemo_instruments:
            return [
                CheckResult(
                    name=name,
                    passed=True,
                    severity="warning",
                    message=(
                        "No NEMO harvester configured and no instruments use NEMO "
                        "harvester; skipping."
                    ),
                )
            ]

        pids = ", ".join(i.instrument_pid for i in nemo_instruments)
        return [
            CheckResult(
                name=name,
                passed=False,
                severity="warning",
                message=(
                    f"No NEMO harvester configuration found "
                    f"(NX_NEMO_ADDRESS_N / NX_NEMO_TOKEN_N not set), but the "
                    f"following instruments use the NEMO harvester: {pids}. "
                    "Set NX_NEMO_ADDRESS_1 and NX_NEMO_TOKEN_1 (and _2, _3, … "
                    "for additional instances)."
                ),
            )
        ]

    # Harvesters are configured — probe each instance for reachability.
    # Any HTTP response (including 4xx) counts as reachable; connection-level
    # exceptions (refused, timeout, DNS) are retried with exponential backoff.
    # After all retries are exhausted the check fails hard (severity="error").
    probe_retries = 3  # 4 total attempts: delays of 1s, 2s, 4s between them

    results = []
    connectors = get_harvesters_enabled()
    for i, connector in enumerate(connectors, start=1):
        base_url = connector.config["base_url"]
        token = connector.config["token"]
        last_exc: Exception | None = None

        for attempt in range(probe_retries + 1):
            try:
                resp = nexus_req(
                    base_url,
                    "GET",
                    token_auth=token,
                    retries=0,
                    timeout=10,
                )
                # Any HTTP response means the server is up
                results.append(
                    CheckResult(
                        name=name,
                        passed=True,
                        severity="error",
                        message=(
                            f"NEMO instance {i} ({base_url}) is reachable "
                            f"(HTTP {resp.status_code})."
                        ),
                    )
                )
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < probe_retries:
                    delay = 2**attempt  # 1s, 2s, 4s
                    _logger.debug(
                        "[preflight] NEMO instance %s unreachable (%s), "
                        "retrying in %ss (attempt %s/%s)",
                        i,
                        exc,
                        delay,
                        attempt + 1,
                        probe_retries + 1,
                    )
                    time.sleep(delay)

        if last_exc is not None:
            results.append(
                CheckResult(
                    name=name,
                    passed=False,
                    severity="error",
                    message=(
                        f"NEMO instance {i} ({base_url}) is not reachable after "
                        f"{probe_retries + 1} attempts: {last_exc}. "
                        "Harvesting will fail for all instruments using this instance."
                    ),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_preflight_checks(*, dry_run: bool = False) -> list[CheckResult]:
    """Run all preflight checks and return the results.

    Checks are grouped into three categories:

    * **Always-run single-result checks** — DB connectivity, table existence,
      Alembic migration status, and instrument count.
    * **Always-run multi-result checks** — per-instrument filestore paths,
      harvester imports, timezone validity, and NEMO config presence.
    * **Write-path checks (skipped in dry-run)** — data path writability and
      export destination validation.

    Every check is wrapped in ``try/except Exception`` so that an unexpected
    failure in one check never prevents the remaining checks from running.

    Parameters
    ----------
    dry_run
        When ``True``, skip checks that require write access (checks 8 and 9).

    Returns
    -------
    list[CheckResult]
        All check results in the order they were executed.
    """
    results: list[CheckResult] = []

    # --- Single-result checks (always run) ---
    single_checks = [
        (_check_db_reachable, "db_reachable", "error"),
        (_check_db_tables, "db_tables", "error"),
        (_check_alembic_migration, "alembic_migration", "error"),
        (_check_instruments_exist, "instruments_exist", "warning"),
    ]
    for fn, fallback_name, fallback_severity in single_checks:
        try:
            results.append(fn())
        except Exception as exc:
            results.append(
                CheckResult(
                    name=fallback_name,
                    passed=False,
                    severity=fallback_severity,  # type: ignore[arg-type]
                    message=f"Unexpected error in check: {exc}",
                )
            )

    # --- Multi-result checks (always run) ---
    multi_checks = [
        (_check_instrument_filestore_paths, "instrument_filestore_paths", "warning"),
        (_check_instrument_harvesters, "instrument_harvesters", "error"),
        (_check_instrument_timezones, "instrument_timezones", "warning"),
        (_check_nemo_harvester_config, "nemo_harvester_config", "warning"),
    ]
    for fn, fallback_name, fallback_severity in multi_checks:
        try:
            results.extend(fn())
        except Exception as exc:
            results.append(
                CheckResult(
                    name=fallback_name,
                    passed=False,
                    severity=fallback_severity,  # type: ignore[arg-type]
                    message=f"Unexpected error in check: {exc}",
                )
            )

    # --- Write-path checks (skipped in dry-run) ---
    if not dry_run:
        write_checks = [
            (_check_data_path_writable, "data_path_writable", "error"),
            (_check_export_destinations, "export_destinations", "warning"),
        ]
        for fn, fallback_name, fallback_severity in write_checks:
            try:
                results.append(fn())
            except Exception as exc:
                results.append(
                    CheckResult(
                        name=fallback_name,
                        passed=False,
                        severity=fallback_severity,  # type: ignore[arg-type]
                        message=f"Unexpected error in check: {exc}",
                    )
                )

    return results
