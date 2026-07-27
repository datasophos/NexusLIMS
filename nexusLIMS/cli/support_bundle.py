"""Create local NexusLIMS diagnostic support bundles."""

from __future__ import annotations

import csv
import html
import json
import locale
import platform
import re
import shutil
import sqlite3
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import click

from nexusLIMS import __version__
from nexusLIMS.builder.preflight import run_preflight_checks
from nexusLIMS.cli import _format_version
from nexusLIMS.cli.config import _build_config_dict, _sanitize_config
from nexusLIMS.config import settings

SCHEMA_VERSION = 1
REDACTED = "***"
SUPPORT_EMAIL = "support@datasophos.co"
MIN_SECRET_LENGTH = 4
PROBLEM_STATUSES = {"ERROR", "NO_FILES_FOUND", "NO_RESERVATION", "NO_CONSENT"}
SECRET_PATTERN = re.compile(
    r"(?i)\b(token|password|api[_-]?key|authorization)\b\s*[:=]\s*([^\s,;]+)"
)
BEARER_PATTERN = re.compile(r"(?i)(Authorization:\s*Bearer\s+)[^\s,;]+")


@dataclass
class ArtifactMeta:
    """Manifest metadata for one artifact."""

    media_type: str
    schema_version: int | None = None
    record_count: int | None = None
    status: str = "collected"
    error: str | None = None


@dataclass
class BundleContext:
    """State shared across support-bundle collectors."""

    report_dir: Path
    output: Path
    log_days: int
    max_log_files: int
    explicit_logs: tuple[Path, ...]
    no_default_logs: bool
    include_all_logs: bool
    generated_at: datetime
    errors: list[dict[str, str]]
    included_logs: list[Path]
    artifact_metadata: dict[str, ArtifactMeta]

    @property
    def options(self) -> dict[str, Any]:
        """Return command options for ``manifest.json``."""
        return {
            "output": str(self.output),
            "log_days": self.log_days,
            "max_log_files": self.max_log_files,
            "log": [str(p) for p in self.explicit_logs],
            "no_default_logs": self.no_default_logs,
            "include_all_logs": self.include_all_logs,
        }


def _json_default(value: Any) -> str | int | float | bool | None:
    """Convert common non-JSON values to strings."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _write_json(
    report_dir: Path,
    relative_path: str,
    data: Any,
    *,
    artifact_metadata: dict[str, Any] | None = None,
) -> None:
    path = report_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=_json_default) + "\n",
    )
    if artifact_metadata is not None:
        artifact_metadata.setdefault("media_type", "application/json")


def _record_artifact(
    ctx: BundleContext,
    relative_path: str,
    meta: ArtifactMeta,
) -> None:
    ctx.artifact_metadata[relative_path] = meta


def _write_text(
    ctx: BundleContext,
    relative_path: str,
    text: str,
    *,
    media_type: str = "text/plain",
    record_count: int | None = None,
) -> None:
    path = ctx.report_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    _record_artifact(
        ctx,
        relative_path,
        ArtifactMeta(media_type=media_type, record_count=record_count),
    )


def _write_json_artifact(
    ctx: BundleContext,
    relative_path: str,
    data: Any,
    *,
    schema_version: int | None = SCHEMA_VERSION,
    record_count: int | None = None,
) -> None:
    _write_json(ctx.report_dir, relative_path, data)
    _record_artifact(
        ctx,
        relative_path,
        ArtifactMeta(
            media_type="application/json",
            schema_version=schema_version,
            record_count=record_count,
        ),
    )


def _sqlite_rows(query: str) -> list[dict[str, Any]]:
    with sqlite3.connect(settings.NX_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query)]


def _table_exists(table_name: str) -> bool:
    with sqlite3.connect(settings.NX_DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
    return row is not None


def _write_table_csv(ctx: BundleContext, table_name: str, relative_path: str) -> int:
    rows = _sqlite_rows(f"SELECT * FROM {table_name}")  # noqa: S608
    path = ctx.report_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else _table_columns(table_name)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _record_artifact(
        ctx,
        relative_path,
        ArtifactMeta(media_type="text/csv", record_count=len(rows)),
    )
    return len(rows)


def _table_columns(table_name: str) -> list[str]:
    with sqlite3.connect(settings.NX_DB_PATH) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]


def _row_count(table_name: str) -> int | None:
    if not _table_exists(table_name):
        return None
    with sqlite3.connect(settings.NX_DB_PATH) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])  # noqa: S608


def _collect_environment(ctx: BundleContext) -> None:
    """Collect Python, platform, and runtime environment details."""
    data = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "nexuslims_import_path": str(Path(__file__).parents[1]),
        "current_working_directory": str(Path.cwd()),
        "timezone": time.tzname,
        "locale": locale.getlocale(),
        "source_checkout": (Path(__file__).parents[2] / ".git").exists(),
    }
    _write_json_artifact(ctx, "environment.json", data)


def _collect_packages(ctx: BundleContext) -> None:
    """Collect installed Python packages using importlib.metadata."""
    packages = sorted(
        f"{dist.metadata['Name']}=={dist.version}" for dist in metadata.distributions()
    )
    _write_text(
        ctx, "packages.txt", "\n".join(packages) + "\n", record_count=len(packages)
    )


def _collect_config(ctx: BundleContext) -> None:
    """Collect sanitized effective NexusLIMS configuration."""
    config_dict = _build_config_dict(settings)
    sanitized = _sanitize_config(config_dict)
    _write_json_artifact(ctx, "config.redacted.json", sanitized)


def _path_info(path: Path, *, check_write: bool) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=False)
    info: dict[str, Any] = {
        "path": str(path),
        "resolved": str(resolved),
        "exists": resolved.exists(),
        "is_file": resolved.is_file(),
        "is_dir": resolved.is_dir(),
        "readable": resolved.exists() and _can_read(resolved),
        "writable": None,
        "free_bytes": None,
    }
    if check_write:
        info["writable"] = _can_write(resolved)
    try:
        usage_target = resolved if resolved.exists() else resolved.parent
        if usage_target.exists():
            info["free_bytes"] = shutil.disk_usage(usage_target).free
    except OSError as exc:
        info["free_space_error"] = str(exc)
    return info


def _can_read(path: Path) -> bool:
    try:
        if path.is_dir():
            next(path.iterdir(), None)
        else:
            with path.open("rb"):
                pass
    except OSError:
        return False
    return True


def _can_write(path: Path) -> bool:
    target_dir = path if path.is_dir() else path.parent
    try:
        with NamedTemporaryFile(
            prefix=".nexuslims-support-bundle-write-test-",
            dir=target_dir,
        ):
            pass
    except OSError:
        return False
    return True


def _collect_paths(ctx: BundleContext) -> None:
    """Collect health details for configured NexusLIMS paths."""
    paths = {
        "NX_INSTRUMENT_DATA_PATH": _path_info(
            settings.NX_INSTRUMENT_DATA_PATH, check_write=False
        ),
        "NX_DATA_PATH": _path_info(settings.NX_DATA_PATH, check_write=True),
        "NX_DB_PATH": _path_info(settings.NX_DB_PATH, check_write=False),
        "NX_LOG_PATH": _path_info(settings.log_dir_path, check_write=True),
        "NX_RECORDS_PATH": _path_info(settings.records_dir_path, check_write=True),
    }
    if settings.NX_LOCAL_PROFILES_PATH is not None:
        paths["NX_LOCAL_PROFILES_PATH"] = _path_info(
            settings.NX_LOCAL_PROFILES_PATH,
            check_write=False,
        )
    _write_json_artifact(ctx, "paths.json", paths)


def _collect_preflight(ctx: BundleContext) -> None:
    """Run preflight checks and serialize structured and text output."""
    checks = run_preflight_checks(dry_run=False)
    serialized = [_serialize_preflight_result(check) for check in checks]
    _write_json_artifact(
        ctx,
        "preflight.json",
        {"checks": serialized},
        record_count=len(serialized),
    )
    lines = [
        (
            f"[{'PASS' if c['passed'] else 'FAIL'}] "
            f"{c['severity']} {c['name']}: {c['message']}"
        )
        for c in serialized
    ]
    _write_text(ctx, "preflight.txt", "\n".join(lines) + ("\n" if lines else ""))


def _serialize_preflight_result(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        return asdict(result)
    return {
        "name": result.name,
        "passed": result.passed,
        "severity": result.severity,
        "message": result.message,
    }


def _collect_database(ctx: BundleContext) -> None:
    """Export database schema details and support-relevant tables."""
    schema = _database_schema()
    _write_json_artifact(ctx, "database/schema.json", schema)

    if _table_exists("session_log"):
        _write_table_csv(ctx, "session_log", "database/session_log.csv")
        summary = _session_log_summary()
        _write_json_artifact(ctx, "database/session_log_summary.json", summary)
        _write_json_artifact(
            ctx,
            "recent_sessions.json",
            _recent_sessions(),
            record_count=len(_recent_sessions()),
        )
    if _table_exists("instruments"):
        _write_table_csv(ctx, "instruments", "database/instruments.csv")

    for table in ("upload_log", "external_user_identifiers"):
        if _table_exists(table):
            _write_table_csv(ctx, table, f"database/{table}.csv")


def _database_schema() -> dict[str, Any]:
    db_path = Path(settings.NX_DB_PATH)
    with sqlite3.connect(db_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        alembic_revision = None
        if "alembic_version" in tables:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            alembic_revision = row[0] if row else None
    key_tables = [
        "session_log",
        "instruments",
        "upload_log",
        "external_user_identifiers",
    ]
    return {
        "database_path": str(db_path),
        "file_size_bytes": db_path.stat().st_size if db_path.exists() else None,
        "tables": tables,
        "alembic_revision": alembic_revision,
        "row_counts": {table: _row_count(table) for table in key_tables},
        "optional_tables": {
            table: {"present": _table_exists(table)}
            for table in ("upload_log", "external_user_identifiers")
        },
    }


def _session_log_summary() -> dict[str, Any]:
    rows = _sqlite_rows("SELECT * FROM session_log")
    summary: dict[str, Any] = {
        "record_status": {},
        "event_type": {},
        "instrument": {},
        "timestamp_min": None,
        "timestamp_max": None,
    }
    timestamps = []
    for row in rows:
        for key, field in (
            ("record_status", "record_status"),
            ("event_type", "event_type"),
            ("instrument", "instrument"),
        ):
            value = row[field]
            summary[key][value] = summary[key].get(value, 0) + 1
        if row.get("timestamp"):
            timestamps.append(row["timestamp"])
    if timestamps:
        summary["timestamp_min"] = min(timestamps)
        summary["timestamp_max"] = max(timestamps)
    return summary


def _recent_sessions(limit: int = 100) -> list[dict[str, Any]]:
    rows = _sqlite_rows(
        "SELECT * FROM session_log ORDER BY timestamp DESC, id_session_log DESC"
    )
    problem = [row for row in rows if row.get("record_status") in PROBLEM_STATUSES]
    ordered = problem + [row for row in rows if row not in problem]
    return ordered[:limit]


def _collect_extractors(ctx: BundleContext) -> None:
    """Collect discovered extractor plugin details."""
    from nexusLIMS.extractors.registry import get_registry  # noqa: PLC0415

    registry = get_registry()
    extractors = []
    for extractor in registry.all_extractors:
        supported_extensions = extractor.supported_extensions or []
        extractors.append(
            {
                "name": extractor.name,
                "class": extractor.__class__.__name__,
                "priority": extractor.priority,
                "supported_extensions": sorted(supported_extensions),
            }
        )
    profile_paths = [
        str(settings.NX_LOCAL_PROFILES_PATH)
        if settings.NX_LOCAL_PROFILES_PATH
        else None,
        str(Path(__file__).parents[1] / "extractors" / "plugins" / "profiles"),
    ]
    _write_json_artifact(
        ctx,
        "extractors.json",
        {
            "extractors": extractors,
            "profile_search_paths": [p for p in profile_paths if p],
        },
        record_count=len(extractors),
    )


def _collect_exporters(ctx: BundleContext) -> None:
    """Collect export destination configuration diagnostics."""
    from nexusLIMS.exporters.registry import get_registry  # noqa: PLC0415

    registry = get_registry()
    registry.discover_plugins()
    destinations = []
    for destination in sorted(
        registry._destinations.values(),  # noqa: SLF001
        key=lambda d: d.priority,
        reverse=True,
    ):
        destinations.append(
            {
                "name": destination.name,
                "priority": destination.priority,
                "enabled": destination.enabled,
                "validation_status": "not_run",
                "validation_note": "Preflight runs live connectivity checks.",
            }
        )
    upload_counts = []
    if _table_exists("upload_log"):
        upload_counts = _sqlite_rows(
            "SELECT destination_name, success, COUNT(*) AS count "
            "FROM upload_log GROUP BY destination_name, success"
        )
    _write_json_artifact(
        ctx,
        "exporters.json",
        {
            "export_strategy": settings.NX_EXPORT_STRATEGY,
            "destinations": destinations,
            "upload_counts": upload_counts,
        },
        record_count=len(destinations),
    )


def _collect_logs(ctx: BundleContext) -> None:
    """Copy selected logs into the archive after line-oriented redaction."""
    logs_dir = ctx.report_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    selected_logs = _select_logs(ctx)
    summary = {"files": {}, "totals": {"warnings": 0, "errors": 0, "tracebacks": 0}}
    used_artifact_paths: set[str] = set()

    for source in selected_logs:
        artifact_path = _log_artifact_path(source, used_artifact_paths)
        target = ctx.report_dir / artifact_path
        target.parent.mkdir(parents=True, exist_ok=True)
        text = _redact_text(source.read_text(errors="replace"))
        target.write_text(text)
        stats = _summarize_log(text)
        summary["files"][artifact_path] = stats
        for key in summary["totals"]:
            summary["totals"][key] += stats[key]
        _record_artifact(ctx, artifact_path, ArtifactMeta(media_type="text/plain"))

    ctx.included_logs = selected_logs
    _write_json_artifact(
        ctx, "log_summary.json", summary, record_count=len(selected_logs)
    )


def _select_logs(ctx: BundleContext) -> list[Path]:
    selected: dict[Path, Path] = {}
    if not ctx.no_default_logs and settings.log_dir_path.exists():
        candidates = [p for p in settings.log_dir_path.rglob("*") if p.is_file()]
        if not ctx.include_all_logs:
            cutoff = time.time() - (ctx.log_days * 24 * 60 * 60)
            candidates = [p for p in candidates if p.stat().st_mtime >= cutoff]
            candidates = sorted(
                candidates,
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[: ctx.max_log_files]
        for path in candidates:
            selected[path.resolve()] = path
    for path in ctx.explicit_logs:
        if path.exists() and path.is_file():
            selected[path.resolve()] = path
    return list(selected.values())


def _log_artifact_path(source: Path, used_artifact_paths: set[str]) -> str:
    try:
        relative = source.resolve().relative_to(settings.log_dir_path.resolve())
        candidate = Path("logs") / relative
    except ValueError:
        candidate = Path("logs") / source.name
    candidate = Path(*_safe_path_parts(candidate.parts))

    artifact_path = candidate.as_posix()
    counter = 1
    while artifact_path in used_artifact_paths:
        suffix = candidate.suffix
        stem = candidate.stem
        parent = candidate.parent
        artifact_path = (parent / f"{stem}-{counter}{suffix}").as_posix()
        counter += 1
    used_artifact_paths.add(artifact_path)
    return artifact_path


def _safe_path_parts(parts: tuple[str, ...]) -> list[str]:
    return [
        re.sub(r"[^A-Za-z0-9._-]", "_", part)
        for part in parts
        if part not in {"", ".", ".."}
    ]


def _redact_text(text: str) -> str:
    text = BEARER_PATTERN.sub(r"\1***", text)
    text = SECRET_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    for secret in _configured_secret_values():
        text = text.replace(secret, REDACTED)
    return text


def _configured_secret_values() -> set[str]:
    raw_config = _build_config_dict(settings)
    sanitized_config = _sanitize_config(raw_config)
    return {
        value
        for value in _walk_redacted_values(raw_config, sanitized_config)
        if len(value) >= MIN_SECRET_LENGTH
    }


def _walk_redacted_values(raw_value: Any, sanitized_value: Any) -> set[str]:
    if sanitized_value == REDACTED and raw_value not in {None, ""}:
        return {str(raw_value)}
    if isinstance(raw_value, dict) and isinstance(sanitized_value, dict):
        values: set[str] = set()
        for key, nested_raw_value in raw_value.items():
            values.update(
                _walk_redacted_values(
                    nested_raw_value,
                    sanitized_value.get(key),
                )
            )
        return values
    return set()


def _summarize_log(text: str) -> dict[str, int]:
    lines = text.splitlines()
    return {
        "warnings": sum(1 for line in lines if "WARNING" in line.upper()),
        "errors": sum(1 for line in lines if "ERROR" in line.upper()),
        "tracebacks": sum(1 for line in lines if "TRACEBACK" in line.upper()),
    }


def _collect_summary_html(ctx: BundleContext) -> None:
    """Write a compact static HTML summary."""
    errors = json.loads((ctx.report_dir / "errors.json").read_text())
    preflight_path = ctx.report_dir / "preflight.json"
    preflight = (
        json.loads(preflight_path.read_text()) if preflight_path.exists() else {}
    )
    paths = _load_artifact_json(ctx, "paths.json", {})
    schema = _load_artifact_json(ctx, "database/schema.json", {})
    recent_sessions = _load_artifact_json(ctx, "recent_sessions.json", [])
    log_summary = _load_artifact_json(ctx, "log_summary.json", {})
    failed_checks = [
        check for check in preflight.get("checks", []) if not check.get("passed", True)
    ]
    unhealthy_paths = _unhealthy_paths(paths)
    problematic_sessions = [
        session
        for session in recent_sessions
        if session.get("record_status") in PROBLEM_STATUSES
    ]
    artifacts = sorted(ctx.artifact_metadata)
    content = "\n".join(
        [
            "<!doctype html>",
            (
                "<html><head><meta charset='utf-8'>"
                "<title>NexusLIMS Support Bundle</title></head>"
            ),
            "<body>",
            "<h1>NexusLIMS Support Bundle</h1>",
            f"<p>Generated: {html.escape(ctx.generated_at.isoformat())}</p>",
            f"<p>NexusLIMS version: {html.escape(__version__)}</p>",
            f"<h2>Failed Preflight Checks ({len(failed_checks)})</h2>",
            "<ul>",
            *[
                (
                    f"<li>{html.escape(check['name'])}: "
                    f"{html.escape(check['message'])}</li>"
                )
                for check in failed_checks
            ],
            "</ul>",
            f"<h2>Unhealthy Paths ({len(unhealthy_paths)})</h2>",
            "<ul>",
            *[
                (f"<li>{html.escape(name)}: {html.escape(', '.join(problems))}</li>")
                for name, problems in unhealthy_paths
            ],
            "</ul>",
            f"<h2>Problematic Recent Sessions ({len(problematic_sessions)})</h2>",
            "<ul>",
            *[
                (
                    f"<li>{html.escape(str(session.get('session_identifier')))}: "
                    f"{html.escape(str(session.get('record_status')))} "
                    f"on {html.escape(str(session.get('instrument')))}</li>"
                )
                for session in problematic_sessions[:20]
            ],
            "</ul>",
            "<h2>Database Row Counts</h2>",
            "<ul>",
            *[
                f"<li>{html.escape(table)}: {count}</li>"
                for table, count in schema.get("row_counts", {}).items()
            ],
            "</ul>",
            "<h2>Log Warnings And Errors</h2>",
            "<ul>",
            f"<li>Warnings: {log_summary.get('totals', {}).get('warnings', 0)}</li>",
            f"<li>Errors: {log_summary.get('totals', {}).get('errors', 0)}</li>",
            (
                f"<li>Tracebacks: "
                f"{log_summary.get('totals', {}).get('tracebacks', 0)}</li>"
            ),
            "</ul>",
            f"<h2>Collector Errors ({len(errors)})</h2>",
            "<ul>",
            *[
                (
                    f"<li>{html.escape(error['collector'])}: "
                    f"{html.escape(error['error'])}</li>"
                )
                for error in errors
            ],
            "</ul>",
            "<h2>Artifacts</h2>",
            "<ul>",
            *[
                f"<li><a href='{html.escape(path)}'>{html.escape(path)}</a></li>"
                for path in artifacts
            ],
            "</ul>",
            "</body></html>",
        ]
    )
    _write_text(ctx, "summary.html", content, media_type="text/html")


def _load_artifact_json(ctx: BundleContext, relative_path: str, default: Any) -> Any:
    path = ctx.report_dir / relative_path
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _unhealthy_paths(paths: dict[str, dict[str, Any]]) -> list[tuple[str, list[str]]]:
    unhealthy = []
    for name, info in paths.items():
        problems = []
        if not info.get("exists"):
            problems.append("missing")
        if info.get("exists") and not info.get("readable"):
            problems.append("not readable")
        if info.get("writable") is False:
            problems.append("not writable")
        if problems:
            unhealthy.append((name, problems))
    return unhealthy


def _collect_manifest(ctx: BundleContext) -> None:
    """Write the stable artifact index."""
    ctx.artifact_metadata["manifest.json"] = ArtifactMeta(
        media_type="application/json",
        schema_version=SCHEMA_VERSION,
    )
    artifacts = []
    for path in sorted(ctx.artifact_metadata):
        meta = asdict(ctx.artifact_metadata[path])
        artifacts.append({"path": path, **meta})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ctx.generated_at.isoformat(),
        "options": ctx.options,
        "nexuslims_version": __version__,
        "artifacts": artifacts,
    }
    _write_json(ctx.report_dir, "manifest.json", manifest)


def _run_collector(ctx: BundleContext, name: str, collector) -> None:
    try:
        collector(ctx)
    except Exception as exc:
        ctx.errors.append({"collector": name, "error": str(exc)})


def _create_zip(report_dir: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(p for p in report_dir.rglob("*") if p.is_file()):
            bundle.write(path, path.relative_to(report_dir).as_posix())


def _default_output_path() -> Path:
    timestamp = datetime.now(tz=UTC).astimezone().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / f"nexuslims-support-bundle-{timestamp}.zip"


@click.command()
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Zip file path to create.",
)
@click.option("--log-days", type=click.IntRange(min=0), default=14, show_default=True)
@click.option(
    "--max-log-files",
    type=click.IntRange(min=0),
    default=25,
    show_default=True,
)
@click.option(
    "--log",
    "explicit_logs",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Specific log file to include. Can be repeated.",
)
@click.option(
    "--no-default-logs",
    is_flag=True,
    help="Disable automatic log discovery from the configured log directory.",
)
@click.option(
    "--include-all-logs",
    is_flag=True,
    help="Include all discovered default logs, ignoring recency and count limits.",
)
@click.version_option(version=None, message=_format_version("nexuslims support-bundle"))
def main(**kwargs: Any) -> None:
    """Create a local diagnostic archive for Datasophos support."""
    output = kwargs["output"]
    output_path = (output or _default_output_path()).expanduser().resolve()
    with TemporaryDirectory(prefix="nexuslims-support-bundle-") as temp_dir:
        ctx = BundleContext(
            report_dir=Path(temp_dir),
            output=output_path,
            log_days=kwargs["log_days"],
            max_log_files=kwargs["max_log_files"],
            explicit_logs=tuple(Path(p) for p in kwargs["explicit_logs"]),
            no_default_logs=kwargs["no_default_logs"],
            include_all_logs=kwargs["include_all_logs"],
            generated_at=datetime.now().astimezone(),
            errors=[],
            included_logs=[],
            artifact_metadata={},
        )
        collectors = [
            ("environment", _collect_environment),
            ("packages", _collect_packages),
            ("config", _collect_config),
            ("paths", _collect_paths),
            ("preflight", _collect_preflight),
            ("database", _collect_database),
            ("extractors", _collect_extractors),
            ("exporters", _collect_exporters),
            ("logs", _collect_logs),
        ]
        for name, collector in collectors:
            _run_collector(ctx, name, collector)

        _write_json_artifact(
            ctx,
            "errors.json",
            ctx.errors,
            record_count=len(ctx.errors),
        )
        if ctx.errors:
            ctx.artifact_metadata["errors.json"].status = "completed_with_errors"
            ctx.artifact_metadata["errors.json"].error = ", ".join(
                error["collector"] for error in ctx.errors
            )
        _collect_summary_html(ctx)
        _collect_manifest(ctx)
        try:
            _create_zip(ctx.report_dir, output_path)
        except OSError as exc:
            msg = f"Could not write support bundle: {exc}"
            raise click.ClickException(msg) from exc

    click.echo(f"Support bundle written to: {output_path}")
    click.echo("The archive was created locally and was not sent anywhere.")
    if ctx.errors:
        click.echo(f"Collector failures: {len(ctx.errors)}. See errors.json.")
    click.echo(f"Review the archive and email it to {SUPPORT_EMAIL}.")
    click.echo("Secrets are redacted on a best-effort basis; review before sending.")
