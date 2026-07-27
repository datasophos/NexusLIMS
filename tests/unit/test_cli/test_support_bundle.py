"""Tests for the ``nexuslims support-bundle`` command."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import zipfile
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from nexusLIMS import config
from nexusLIMS.cli.main import main
from nexusLIMS.db.enums import EventType, RecordStatus
from tests.unit.fixtures.database import INSTRUMENT_CONFIGS

if TYPE_CHECKING:
    from pathlib import Path


def _read_json(bundle_path: Path, artifact: str) -> dict | list:
    with zipfile.ZipFile(bundle_path) as bundle:
        return json.loads(bundle.read(artifact))


def _read_text(bundle_path: Path, artifact: str) -> str:
    with zipfile.ZipFile(bundle_path) as bundle:
        return bundle.read(artifact).decode()


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
    assert "created locally" in result.output
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
        "session-2",
        "session-1",
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
    assert "collector failure" in result.output.lower()

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
