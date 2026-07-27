"""Tests for the ``nexuslims support-bundle`` command."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from nexusLIMS import config
from nexusLIMS.cli.main import main
from nexusLIMS.db.enums import EventType, RecordStatus
from tests.unit.fixtures.database import INSTRUMENT_CONFIGS

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.cli.support_bundle import BundleContext


def _read_json(bundle_path: Path, artifact: str) -> dict | list:
    with zipfile.ZipFile(bundle_path) as bundle:
        return json.loads(bundle.read(artifact))


def _read_text(bundle_path: Path, artifact: str) -> str:
    with zipfile.ZipFile(bundle_path) as bundle:
        return bundle.read(artifact).decode()


def _bundle_context(tmp_path: Path) -> BundleContext:
    from nexusLIMS.cli.support_bundle import BundleContext

    return BundleContext(
        report_dir=tmp_path,
        output=tmp_path / "bundle.zip",
        log_days=14,
        max_log_files=25,
        explicit_logs=(),
        no_default_logs=False,
        include_all_logs=False,
        generated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        errors=[],
        included_logs=[],
        artifact_metadata={},
    )


@pytest.fixture
def support_bundle_db(db_factory, monkeypatch, tmp_path):
    """Create a database with support-bundle-relevant rows."""
    db_path = db_factory.create_db(
        instruments=[INSTRUMENT_CONFIGS["FEI-Titan-TEM"]],
        sessions=[
            {
                "session_identifier": "session-1",
                "instrument": "FEI-Titan-TEM",
                "timestamp": datetime(2026, 1, 2, 3, 4, 5),
                "event_type": EventType.START,
                "record_status": RecordStatus.ERROR,
                "user": "alice",
            },
            {
                "session_identifier": "session-2",
                "instrument": "FEI-Titan-TEM",
                "timestamp": datetime(2026, 1, 3, 3, 4, 5),
                "event_type": EventType.END,
                "record_status": RecordStatus.NO_FILES_FOUND,
                "user": "bob",
            },
        ],
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO upload_log (
                session_identifier, destination_name, success, timestamp,
                record_id, record_url, error_message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-1",
                "cdcs",
                0,
                "2026-01-02T04:05:06",
                None,
                None,
                "upload failed",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO external_user_identifiers (
                nexuslims_username, external_system, external_id, email,
                created_at, last_verified_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "alice",
                "nemo",
                "123",
                "alice@example.test",
                "2026-01-02T04:05:06",
                None,
                "test mapping",
            ),
        )

    data_path = tmp_path / "data"
    instr_path = tmp_path / "instrument-data"
    log_path = tmp_path / "logs"
    data_path.mkdir()
    instr_path.mkdir()
    log_path.mkdir()

    monkeypatch.setenv("NX_DB_PATH", str(db_path))
    monkeypatch.setenv("NX_DATA_PATH", str(data_path))
    monkeypatch.setenv("NX_INSTRUMENT_DATA_PATH", str(instr_path))
    monkeypatch.setenv("NX_LOG_PATH", str(log_path))
    config.refresh_settings()

    import nexusLIMS.db.engine

    old_engine = nexusLIMS.db.engine._engine
    nexusLIMS.db.engine._engine = None
    yield db_path

    if nexusLIMS.db.engine._engine is not None:
        nexusLIMS.db.engine._engine.dispose()
    nexusLIMS.db.engine._engine = old_engine
    config.clear_settings()


def test_support_bundle_help_is_registered():
    """Removing CLI registration should make support-bundle help unavailable."""
    result = CliRunner().invoke(main, ["support-bundle", "--help"])

    assert result.exit_code == 0
    assert "--output" in result.output
    assert "--log-days" in result.output
    assert "--include-all-logs" in result.output


def test_support_bundle_creates_expected_archive(
    support_bundle_db, monkeypatch, tmp_path
):
    """Dropping required collectors should remove expected archive artifacts."""
    log_path = config.settings.log_dir_path / "nexuslims.log"
    configured_token = config.settings.NX_CDCS_TOKEN
    log_path.write_text(
        "INFO ok\n"
        "ERROR token=abc123 password=swordfish Authorization: Bearer secret\n"
        f"ERROR configured {configured_token} leaked without a label\n"
    )
    output = tmp_path / "report.zip"

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [
            type(
                "Result",
                (),
                {
                    "name": "db_reachable",
                    "passed": True,
                    "severity": "error",
                    "message": "Database reachable.",
                },
            )()
        ],
    )

    result = CliRunner().invoke(main, ["support-bundle", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert "NexusLIMS support bundle created" in result.output
    assert f"Archive: {output}" in result.output
    assert "Status:" not in result.output
    assert "Issues:" not in result.output
    assert (
        "Secrets have been automatically redacted, but please review before "
        "sending for any sensitive content."
    ) in result.output
    assert result.output.rstrip().endswith(
        "Next step: Review the archive and email it to support@datasophos.co."
    )
    assert "support@datasophos.co" in result.output

    with zipfile.ZipFile(output) as bundle:
        names = set(bundle.namelist())

    assert {
        "manifest.json",
        "summary.html",
        "environment.json",
        "packages.txt",
        "config.redacted.json",
        "paths.json",
        "preflight.json",
        "preflight.txt",
        "extractors.json",
        "exporters.json",
        "errors.json",
        "database/schema.json",
        "database/session_log.csv",
        "database/session_log_summary.json",
        "database/instruments.csv",
        "database/upload_log.csv",
        "database/external_user_identifiers.csv",
        "logs/nexuslims.log",
        "log_summary.json",
        "recent_sessions.json",
    } <= names

    manifest = _read_json(output, "manifest.json")
    assert manifest["schema_version"] == 1
    assert manifest["options"]["output"] == str(output)
    assert any(a["path"] == "database/session_log.csv" for a in manifest["artifacts"])
    assert any(a["path"] == "manifest.json" for a in manifest["artifacts"])

    config_json = _read_json(output, "config.redacted.json")
    assert config_json["NX_CDCS_TOKEN"] == "***"

    copied_log = _read_text(output, "logs/nexuslims.log")
    assert "abc123" not in copied_log
    assert "swordfish" not in copied_log
    assert "Bearer secret" not in copied_log
    assert configured_token not in copied_log
    assert "***" in copied_log

    preflight = _read_json(output, "preflight.json")
    assert preflight["checks"][0]["name"] == "db_reachable"

    summary = _read_json(output, "database/session_log_summary.json")
    assert summary["record_status"]["ERROR"] == 1
    assert summary["record_status"]["NO_FILES_FOUND"] == 1
    assert summary["event_type"]["START"] == 1
    assert summary["instrument"]["FEI-Titan-TEM"] == 2

    recent_sessions = _read_json(output, "recent_sessions.json")
    assert [s["session_identifier"] for s in recent_sessions] == [
        "session-1",
        "session-2",
    ]

    with zipfile.ZipFile(output) as bundle:
        rows = list(
            csv.DictReader(
                bundle.read("database/session_log.csv").decode().splitlines()
            )
        )
    assert rows[0]["user"] == "alice"
    assert rows[0]["record_status"] == "ERROR"


def test_missing_optional_tables_are_reported(tmp_path, support_bundle_db, monkeypatch):
    """Removing optional DB tables should not abort archive creation."""
    with sqlite3.connect(support_bundle_db) as conn:
        conn.execute("DROP TABLE upload_log")
        conn.execute("DROP TABLE external_user_identifiers")
    output = tmp_path / "missing-optional.zip"

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )

    result = CliRunner().invoke(main, ["support-bundle", "--output", str(output)])

    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(output) as bundle:
        names = set(bundle.namelist())
    assert "database/upload_log.csv" not in names
    assert "database/external_user_identifiers.csv" not in names

    errors = _read_json(output, "errors.json")
    assert errors == []

    schema = _read_json(output, "database/schema.json")
    assert schema["optional_tables"]["upload_log"]["present"] is False
    assert schema["optional_tables"]["external_user_identifiers"]["present"] is False


def test_log_selection_honors_limits_and_explicit_logs(
    tmp_path, support_bundle_db, monkeypatch
):
    """Ignoring log limits should include the wrong default log files."""
    old_log = config.settings.log_dir_path / "old.log"
    recent_log = config.settings.log_dir_path / "recent.log"
    explicit_log = tmp_path / "explicit.log"
    old_log.write_text("ERROR old\n")
    recent_log.write_text("WARNING recent\n")
    explicit_log.write_text("ERROR api_key=secret-value\n")

    old_time = datetime(2020, 1, 1).timestamp()
    recent_time = datetime.now().timestamp()
    os.utime(old_log, (old_time, old_time))
    os.utime(recent_log, (recent_time, recent_time))

    output = tmp_path / "logs.zip"
    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )

    result = CliRunner().invoke(
        main,
        [
            "support-bundle",
            "--output",
            str(output),
            "--log-days",
            "1",
            "--log",
            str(explicit_log),
        ],
    )

    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(output) as bundle:
        names = set(bundle.namelist())
    assert "logs/recent.log" in names
    assert "logs/explicit.log" in names
    assert "logs/old.log" not in names

    log_summary = _read_json(output, "log_summary.json")
    assert log_summary["files"]["logs/recent.log"]["warnings"] == 1
    assert log_summary["files"]["logs/explicit.log"]["errors"] == 1
    assert "secret-value" not in _read_text(output, "logs/explicit.log")


def test_duplicate_log_basenames_are_preserved(
    tmp_path, support_bundle_db, monkeypatch
):
    """Colliding log basenames should not overwrite each other in the archive."""
    nested_dir = config.settings.log_dir_path / "nested"
    nested_dir.mkdir()
    default_log = nested_dir / "same.log"
    explicit_dir = tmp_path / "explicit"
    explicit_dir.mkdir()
    explicit_log = explicit_dir / "same.log"
    default_log.write_text("ERROR default\n")
    explicit_log.write_text("ERROR explicit\n")
    output = tmp_path / "duplicate-logs.zip"

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )

    result = CliRunner().invoke(
        main,
        ["support-bundle", "--output", str(output), "--log", str(explicit_log)],
    )

    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(output) as bundle:
        log_names = sorted(
            name for name in bundle.namelist() if name.endswith("same.log")
        )
        log_contents = [bundle.read(name).decode() for name in log_names]
    assert log_names == ["logs/nested/same.log", "logs/same.log"]
    assert any("default" in content for content in log_contents)
    assert any("explicit" in content for content in log_contents)


def test_collector_failures_are_captured(tmp_path, support_bundle_db, monkeypatch):
    """A failed collector should populate errors.json without failing the CLI."""
    output = tmp_path / "collector-error.zip"

    def _fail(_report_dir):
        raise RuntimeError("collector exploded")

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle._collect_environment",
        _fail,
    )
    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )

    result = CliRunner().invoke(main, ["support-bundle", "--output", str(output)])

    assert result.exit_code == 0, result.output
    errors = _read_json(output, "errors.json")
    assert errors[0]["collector"] == "environment"
    assert "collector exploded" in errors[0]["error"]
    assert (
        "Issues:  1 diagnostic section could not be included. See errors.json "
        "in the archive."
    ) in result.output

    manifest = _read_json(output, "manifest.json")
    errors_artifact = next(
        a for a in manifest["artifacts"] if a["path"] == "errors.json"
    )
    assert errors_artifact["status"] == "completed_with_errors"
    assert "environment" in errors_artifact["error"]


def test_summary_html_highlights_required_sections(
    tmp_path, support_bundle_db, monkeypatch
):
    """The human summary should expose the key support triage sections."""
    log_path = config.settings.log_dir_path / "nexuslims.log"
    log_path.write_text("WARNING warning\nERROR error\n")
    output = tmp_path / "summary.zip"

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )

    result = CliRunner().invoke(main, ["support-bundle", "--output", str(output)])

    assert result.exit_code == 0, result.output
    summary = _read_text(output, "summary.html")
    assert "<style>" in summary
    assert "font-family:ui-monospace" in summary
    assert "<main>" in summary
    assert "<section>" in summary
    assert "<ul class='mono'>" in summary
    assert "Unhealthy Paths" in summary
    assert "Problematic Recent Sessions" in summary
    assert "Database Row Counts" in summary
    assert "Log Warnings And Errors" in summary


def test_can_write_does_not_destroy_existing_probe_file(tmp_path):
    """The path writability probe should not overwrite an existing file."""
    from nexusLIMS.cli.support_bundle import _can_write

    existing_probe = tmp_path / ".nexuslims-support-bundle-write-test"
    existing_probe.write_text("keep me")

    assert _can_write(tmp_path) is True
    assert existing_probe.read_text() == "keep me"


def test_json_helpers_handle_fallback_types(tmp_path):
    """JSON helper fallback branches should keep support artifacts serializable."""
    from nexusLIMS.cli.support_bundle import _json_default, _write_json

    class Choice(Enum):
        VALUE = "enum-value"

    metadata = {}
    _write_json(
        tmp_path,
        "nested/value.json",
        {
            "path": tmp_path,
            "date": datetime(2026, 1, 2, 3, 4, 5),
            "enum": Choice.VALUE,
            "fallback": object(),
        },
        artifact_metadata=metadata,
    )

    data = json.loads((tmp_path / "nested/value.json").read_text())
    assert data["path"] == str(tmp_path)
    assert data["date"] == "2026-01-02T03:04:05"
    assert data["enum"] == "enum-value"
    assert data["fallback"].startswith("<object object at ")
    assert _json_default(Choice.VALUE) == "enum-value"
    assert metadata == {"media_type": "application/json"}


def test_path_helpers_report_io_failures(tmp_path, monkeypatch):
    """Path diagnostics should report read/write/free-space failures."""
    from nexusLIMS.cli import support_bundle

    monkeypatch.setattr(
        support_bundle.shutil,
        "disk_usage",
        lambda _path: (_ for _ in ()).throw(OSError("disk failed")),
    )

    missing_child = tmp_path / "missing-parent" / "child.txt"
    info = support_bundle._path_info(tmp_path, check_write=True)

    assert support_bundle._can_read(missing_child) is False
    assert support_bundle._can_write(missing_child) is False
    assert info["writable"] is True
    assert info["free_space_error"] == "disk failed"


def test_collect_paths_includes_local_profiles_path(
    tmp_path, support_bundle_db, monkeypatch
):
    """Configured local extractor profiles should appear in path diagnostics."""
    from nexusLIMS.cli.support_bundle import _collect_paths

    local_profiles = tmp_path / "profiles"
    local_profiles.mkdir()
    monkeypatch.setenv("NX_LOCAL_PROFILES_PATH", str(local_profiles))
    config.refresh_settings()

    ctx = _bundle_context(tmp_path)
    _collect_paths(ctx)

    paths = json.loads((tmp_path / "paths.json").read_text())
    assert paths["NX_LOCAL_PROFILES_PATH"]["path"] == str(local_profiles)


def test_unset_log_and_records_paths_use_data_path_defaults(
    tmp_path, support_bundle_db, monkeypatch
):
    """Missing default log/records directories should not be unhealthy paths."""
    from nexusLIMS.cli.support_bundle import _collect_paths, _unhealthy_paths

    monkeypatch.delenv("NX_LOG_PATH", raising=False)
    monkeypatch.delenv("NX_RECORDS_PATH", raising=False)
    config.refresh_settings()

    ctx = _bundle_context(tmp_path)
    _collect_paths(ctx)

    paths = json.loads((tmp_path / "paths.json").read_text())
    assert paths["NX_LOG_PATH"]["path"] == str(config.settings.NX_DATA_PATH / "logs")
    assert paths["NX_LOG_PATH"]["source"] == "default"
    assert paths["NX_LOG_PATH"]["defaulted_from"] == "NX_DATA_PATH"
    assert paths["NX_RECORDS_PATH"]["path"] == str(
        config.settings.NX_DATA_PATH / "records"
    )
    assert paths["NX_RECORDS_PATH"]["source"] == "default"
    assert paths["NX_RECORDS_PATH"]["defaulted_from"] == "NX_DATA_PATH"
    assert ("NX_LOG_PATH", ["missing"]) not in _unhealthy_paths(paths)
    assert ("NX_RECORDS_PATH", ["missing"]) not in _unhealthy_paths(paths)


def test_preflight_serializes_dataclass_results(
    tmp_path, support_bundle_db, monkeypatch
):
    """Dataclass preflight results should serialize via asdict."""
    from nexusLIMS.cli.support_bundle import _collect_preflight

    @dataclass
    class Result:
        name: str
        passed: bool
        severity: str
        message: str

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [
            Result(
                name="failed_check",
                passed=False,
                severity="error",
                message="broken",
            )
        ],
    )

    ctx = _bundle_context(tmp_path)
    _collect_preflight(ctx)

    preflight = json.loads((tmp_path / "preflight.json").read_text())
    assert preflight["checks"] == [
        {
            "name": "failed_check",
            "passed": False,
            "severity": "error",
            "message": "broken",
        }
    ]
    assert (
        "[FAIL] error failed_check: broken" in (tmp_path / "preflight.txt").read_text()
    )


def test_database_schema_reports_alembic_revision(support_bundle_db):
    """The schema summary should include an alembic revision when present."""
    from nexusLIMS.cli.support_bundle import _database_schema

    with sqlite3.connect(support_bundle_db) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        conn.execute("INSERT INTO alembic_version VALUES ('rev123')")

    schema = _database_schema()

    assert schema["alembic_revision"] == "rev123"


def test_empty_table_csv_uses_table_columns(tmp_path, support_bundle_db):
    """Empty table exports should still include a header row."""
    from nexusLIMS.cli.support_bundle import _write_table_csv

    with sqlite3.connect(support_bundle_db) as conn:
        conn.execute("CREATE TABLE empty_export (first TEXT, second INTEGER)")

    ctx = _bundle_context(tmp_path)
    row_count = _write_table_csv(ctx, "empty_export", "database/empty_export.csv")

    assert row_count == 0
    assert (tmp_path / "database/empty_export.csv").read_text() == "first,second\n"


def test_log_artifact_path_adds_suffix_for_collisions(tmp_path, support_bundle_db):
    """Duplicate log artifact paths should be made unique."""
    from nexusLIMS.cli.support_bundle import _log_artifact_path

    first = tmp_path / "a" / "same.log"
    second = tmp_path / "b" / "same.log"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first")
    second.write_text("second")

    used = set()

    assert _log_artifact_path(first, used) == "logs/same.log"
    assert _log_artifact_path(second, used) == "logs/same-1.log"


def test_load_artifact_json_returns_default_for_missing_or_invalid(tmp_path):
    """Summary helpers should tolerate missing or invalid JSON artifacts."""
    from nexusLIMS.cli.support_bundle import _load_artifact_json

    ctx = _bundle_context(tmp_path)
    (tmp_path / "invalid.json").write_text("{not-json")

    assert _load_artifact_json(ctx, "missing.json", {"fallback": True}) == {
        "fallback": True
    }
    assert _load_artifact_json(ctx, "invalid.json", []) == []


def test_unhealthy_paths_reports_readable_and_writable_problems():
    """Path summary should report unreadable and unwritable existing paths."""
    from nexusLIMS.cli.support_bundle import _unhealthy_paths

    paths = {
        "missing": {"exists": False, "readable": False, "writable": None},
        "unreadable": {"exists": True, "readable": False, "writable": None},
        "unwritable": {"exists": True, "readable": True, "writable": False},
    }

    assert _unhealthy_paths(paths) == [
        ("missing", ["missing"]),
        ("unreadable", ["not readable"]),
        ("unwritable", ["not writable"]),
    ]


def test_default_output_path_uses_timestamped_zip_name(tmp_path, monkeypatch):
    """Default output path should be created under the current working directory."""
    from nexusLIMS.cli.support_bundle import _default_output_path

    monkeypatch.chdir(tmp_path)

    output = _default_output_path()

    assert output.parent == tmp_path
    assert output.name.startswith("nexuslims-support-bundle-")
    assert output.suffix == ".zip"


def test_zip_write_error_is_reported_as_click_exception(
    tmp_path, support_bundle_db, monkeypatch
):
    """Zip creation errors should become user-facing Click exceptions."""
    output = tmp_path / "bundle.zip"

    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle.run_preflight_checks",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        "nexusLIMS.cli.support_bundle._create_zip",
        lambda *_args: (_ for _ in ()).throw(OSError("read-only output")),
    )

    result = CliRunner().invoke(main, ["support-bundle", "--output", str(output)])

    assert result.exit_code != 0
    assert "Could not write support bundle: read-only output" in result.output
