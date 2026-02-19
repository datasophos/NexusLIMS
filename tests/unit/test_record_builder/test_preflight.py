# ruff: noqa: FBT003
"""Unit tests for nexusLIMS.builder.preflight module."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nexusLIMS.builder.preflight import (
    CheckResult,
    PreflightError,
    _check_alembic_migration,
    _check_data_path_writable,
    _check_db_reachable,
    _check_db_tables,
    _check_export_destinations,
    _check_instrument_filestore_paths,
    _check_instrument_harvesters,
    _check_instrument_timezones,
    _check_instruments_exist,
    _check_nemo_harvester_config,
    run_preflight_checks,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_db(path: Path) -> None:
    """Create an empty SQLite DB with no NexusLIMS tables."""
    conn = sqlite3.connect(str(path))
    conn.close()


def _make_full_db(path: Path) -> None:
    """Create a SQLite DB with all NexusLIMS tables (no migration tracking)."""
    from sqlmodel import SQLModel, create_engine

    # Ensure all model classes are registered in SQLModel.metadata
    from nexusLIMS.db.models import (  # noqa: F401
        ExternalUserIdentifier,
        Instrument,
        SessionLog,
        UploadLog,
    )

    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()


def _get_engine_for(path: Path):
    """Return a fresh SQLAlchemy engine for the given DB path."""
    from sqlmodel import create_engine

    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


# ---------------------------------------------------------------------------
# CheckResult and PreflightError
# ---------------------------------------------------------------------------


class TestCheckResult:
    """Tests for the CheckResult dataclass."""

    def test_fields(self):
        r = CheckResult(
            name="test", passed=True, severity="warning", message="all good"
        )
        assert r.name == "test"
        assert r.passed is True
        assert r.severity == "warning"
        assert r.message == "all good"


class TestPreflightError:
    """Tests for the PreflightError exception."""

    def test_message_lists_check_names(self):
        checks = [
            CheckResult(
                name="db_reachable", passed=False, severity="error", message="x"
            ),
            CheckResult(name="db_tables", passed=False, severity="error", message="y"),
        ]
        err = PreflightError(checks)
        assert "db_reachable" in str(err)
        assert "db_tables" in str(err)
        assert err.failed_checks is checks


# ---------------------------------------------------------------------------
# _check_db_reachable
# ---------------------------------------------------------------------------


class TestCheckDbReachable:
    """Tests for _check_db_reachable."""

    def test_pass_when_db_exists(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        monkeypatch.setattr("nexusLIMS.builder.preflight.settings.NX_DB_PATH", db_path)
        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            result = _check_db_reachable()

        assert result.passed is True
        assert result.name == "db_reachable"

    def test_fail_when_file_missing(self, tmp_path, monkeypatch):
        missing = tmp_path / "no_such.db"
        monkeypatch.setattr("nexusLIMS.builder.preflight.settings.NX_DB_PATH", missing)
        result = _check_db_reachable()

        assert result.passed is False
        assert result.severity == "error"
        assert "not found" in result.message.lower() or "not" in result.message.lower()

    def test_fail_when_connection_raises(self, tmp_path, monkeypatch):
        db_path = tmp_path / "bad.db"
        db_path.write_bytes(b"not a sqlite database content")
        monkeypatch.setattr("nexusLIMS.builder.preflight.settings.NX_DB_PATH", db_path)

        bad_engine = MagicMock()
        bad_engine.__enter__ = MagicMock(side_effect=Exception("connection refused"))

        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("cannot connect"),
        ):
            result = _check_db_reachable()

        assert result.passed is False
        assert result.severity == "error"


# ---------------------------------------------------------------------------
# _check_db_tables
# ---------------------------------------------------------------------------


class TestCheckDbTables:
    """Tests for _check_db_tables."""

    def test_pass_when_all_tables_present(self, tmp_path):
        db_path = tmp_path / "full.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            result = _check_db_tables()

        assert result.passed is True
        assert result.name == "db_tables"

    def test_fail_when_table_missing(self, tmp_path):
        db_path = tmp_path / "empty.db"
        _make_minimal_db(db_path)  # No NexusLIMS tables
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            result = _check_db_tables()

        assert result.passed is False
        assert result.severity == "error"
        assert "missing" in result.message.lower()

    def test_fail_when_engine_raises(self):
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("engine error"),
        ):
            result = _check_db_tables()

        assert result.passed is False
        assert result.severity == "error"
        assert "could not query" in result.message.lower()


# ---------------------------------------------------------------------------
# _check_alembic_migration
# ---------------------------------------------------------------------------


class TestCheckAlembicMigration:
    """Tests for _check_alembic_migration."""

    def test_pass_when_at_head(self, tmp_path):
        db_path = tmp_path / "alembic.db"
        _make_full_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO alembic_version VALUES ('v2_5_0b')")
        conn.commit()
        conn.close()

        engine = _get_engine_for(db_path)

        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "v2_5_0b"

        with (
            patch("nexusLIMS.builder.preflight.get_engine", return_value=engine),
            patch("nexusLIMS.builder.preflight.ScriptDirectory") as mock_sd_class,
        ):
            mock_sd_class.from_config.return_value = mock_script
            # Also patch Config so we don't need alembic.ini on disk
            with patch("nexusLIMS.builder.preflight.Config"):
                result = _check_alembic_migration()

        assert result.passed is True
        assert "up to date" in result.message

    def test_fail_hard_when_behind(self, tmp_path):
        db_path = tmp_path / "behind.db"
        _make_full_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO alembic_version VALUES ('v1_4_3')")
        conn.commit()
        conn.close()

        engine = _get_engine_for(db_path)

        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "v2_5_0b"

        with (
            patch("nexusLIMS.builder.preflight.get_engine", return_value=engine),
            patch("nexusLIMS.builder.preflight.ScriptDirectory") as mock_sd_class,
            patch("nexusLIMS.builder.preflight.Config"),
        ):
            mock_sd_class.from_config.return_value = mock_script
            result = _check_alembic_migration()

        assert result.passed is False
        assert result.severity == "error"
        assert "out of date" in result.message

    def test_pass_when_head_rev_is_none(self):
        """When no Alembic revisions exist, check passes (nothing to compare)."""
        mock_script = MagicMock()
        mock_script.get_current_head.return_value = None

        with (
            patch("nexusLIMS.builder.preflight.ScriptDirectory") as mock_sd_class,
            patch("nexusLIMS.builder.preflight.Config"),
        ):
            mock_sd_class.from_config.return_value = mock_script
            result = _check_alembic_migration()

        assert result.passed is True
        assert "no alembic revisions" in result.message.lower()

    def test_fail_when_config_raises(self):
        """Exception in Config/ScriptDirectory returns error result."""
        with patch(
            "nexusLIMS.builder.preflight.Config",
            side_effect=Exception("ini not found"),
        ):
            result = _check_alembic_migration()

        assert result.passed is False
        assert result.severity == "error"
        assert "could not determine" in result.message.lower()

    def test_fail_when_alembic_version_query_raises(self, tmp_path):
        """Exception querying alembic_version returns error result."""
        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "v2_5_0b"

        with (
            patch(
                "nexusLIMS.builder.preflight.get_engine",
                side_effect=Exception("db error"),
            ),
            patch("nexusLIMS.builder.preflight.ScriptDirectory") as mock_sd_class,
            patch("nexusLIMS.builder.preflight.Config"),
        ):
            mock_sd_class.from_config.return_value = mock_script
            result = _check_alembic_migration()

        assert result.passed is False
        assert result.severity == "error"
        assert "could not query alembic_version" in result.message.lower()

    def test_fail_hard_when_no_alembic_version_table(self, tmp_path):
        db_path = tmp_path / "no_alembic.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        mock_script = MagicMock()
        mock_script.get_current_head.return_value = "v2_5_0b"

        with (
            patch("nexusLIMS.builder.preflight.get_engine", return_value=engine),
            patch("nexusLIMS.builder.preflight.ScriptDirectory") as mock_sd_class,
            patch("nexusLIMS.builder.preflight.Config"),
        ):
            mock_sd_class.from_config.return_value = mock_script
            result = _check_alembic_migration()

        assert result.passed is False
        assert result.severity == "error"
        assert "alembic_version" in result.message.lower()


# ---------------------------------------------------------------------------
# _check_instruments_exist
# ---------------------------------------------------------------------------


class TestCheckInstrumentsExist:
    """Tests for _check_instruments_exist."""

    def test_pass_when_instruments_present(self, tmp_path):
        db_path = tmp_path / "with_instruments.db"
        _make_full_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO instruments "
            "(instrument_pid, api_url, calendar_url, location, display_name, "
            "property_tag, filestore_path, harvester, timezone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TEST-1",
                "http://example.com/api/tools/?id=1",
                "http://example.com/cal/",
                "Room 1",
                "Test Instrument",
                "TAG-001",
                "./data",
                "nemo",
                "America/New_York",
            ),
        )
        conn.commit()
        conn.close()

        engine = _get_engine_for(db_path)
        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            result = _check_instruments_exist()

        assert result.passed is True

    def test_warn_when_empty(self, tmp_path):
        db_path = tmp_path / "empty_instruments.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            result = _check_instruments_exist()

        assert result.passed is False
        assert result.severity == "warning"

    def test_warn_when_engine_raises(self):
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("engine error"),
        ):
            result = _check_instruments_exist()

        assert result.passed is False
        assert result.severity == "warning"
        assert "could not query" in result.message.lower()


# ---------------------------------------------------------------------------
# _check_instrument_filestore_paths
# ---------------------------------------------------------------------------


class TestCheckInstrumentFilestorePaths:
    """Tests for _check_instrument_filestore_paths."""

    def _make_db_with_instrument(self, path: Path, filestore: str) -> None:
        _make_full_db(path)
        conn = sqlite3.connect(str(path))
        conn.execute(
            "INSERT INTO instruments "
            "(instrument_pid, api_url, calendar_url, location, display_name, "
            "property_tag, filestore_path, harvester, timezone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TEST-1",
                "http://example.com/api/tools/?id=1",
                "http://example.com/cal/",
                "Room 1",
                "Test Instrument",
                "TAG-001",
                filestore,
                "nemo",
                "America/New_York",
            ),
        )
        conn.commit()
        conn.close()

    def test_pass_when_paths_exist(self, tmp_path, monkeypatch):
        instr_root = tmp_path / "instruments"
        filestore = instr_root / "MyScope"
        filestore.mkdir(parents=True)

        db_path = tmp_path / "paths.db"
        self._make_db_with_instrument(db_path, "MyScope")

        engine = _get_engine_for(db_path)
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_INSTRUMENT_DATA_PATH",
            instr_root,
        )
        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_filestore_paths()

        assert all(r.passed for r in results)

    def test_warn_when_path_missing(self, tmp_path, monkeypatch):
        instr_root = tmp_path / "instruments"
        instr_root.mkdir()  # root exists but no subdirectory

        db_path = tmp_path / "paths_missing.db"
        self._make_db_with_instrument(db_path, "NoSuchScope")

        engine = _get_engine_for(db_path)
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_INSTRUMENT_DATA_PATH",
            instr_root,
        )
        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_filestore_paths()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert all(r.severity == "warning" for r in failed)

    def test_warn_when_base_path_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_INSTRUMENT_DATA_PATH",
            tmp_path / "nonexistent_base",
        )
        results = _check_instrument_filestore_paths()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "warning"

    def test_warn_when_engine_raises(self, tmp_path, monkeypatch):
        """Base path exists but instruments query fails."""
        instr_root = tmp_path / "instruments"
        instr_root.mkdir()
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_INSTRUMENT_DATA_PATH",
            instr_root,
        )
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("db error"),
        ):
            results = _check_instrument_filestore_paths()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "warning"
        assert "could not query" in results[0].message.lower()

    def test_pass_when_no_instruments(self, tmp_path, monkeypatch):
        """Base path exists and DB has no instruments — skip with PASS."""
        instr_root = tmp_path / "instruments"
        instr_root.mkdir()
        db_path = tmp_path / "empty.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_INSTRUMENT_DATA_PATH",
            instr_root,
        )
        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_filestore_paths()

        assert len(results) == 1
        assert results[0].passed is True
        assert "skipping" in results[0].message.lower()


# ---------------------------------------------------------------------------
# _check_instrument_harvesters
# ---------------------------------------------------------------------------


class TestCheckInstrumentHarvesters:
    """Tests for _check_instrument_harvesters."""

    def _make_db_with_harvester(self, path: Path, harvester: str) -> None:
        _make_full_db(path)
        conn = sqlite3.connect(str(path))
        conn.execute(
            "INSERT INTO instruments "
            "(instrument_pid, api_url, calendar_url, location, display_name, "
            "property_tag, filestore_path, harvester, timezone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TEST-1",
                "http://example.com/api/tools/?id=1",
                "http://example.com/cal/",
                "Room 1",
                "Test Instrument",
                "TAG-001",
                "./data",
                harvester,
                "America/New_York",
            ),
        )
        conn.commit()
        conn.close()

    def test_pass_for_valid_nemo_harvester(self, tmp_path):
        db_path = tmp_path / "nemo.db"
        self._make_db_with_harvester(db_path, "nemo")
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_harvesters()

        assert all(r.passed for r in results)

    def test_fail_when_module_not_importable(self, tmp_path):
        db_path = tmp_path / "bad_harvester.db"
        self._make_db_with_harvester(db_path, "nonexistent_harvester")
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_harvesters()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert all(r.severity == "error" for r in failed)

    def test_fail_when_engine_raises(self):
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("db error"),
        ):
            results = _check_instrument_harvesters()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "error"
        assert "could not query" in results[0].message.lower()

    def test_pass_when_no_instruments(self, tmp_path):
        """DB has no instruments — skip with PASS."""
        db_path = tmp_path / "empty.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_harvesters()

        assert len(results) == 1
        assert results[0].passed is True
        assert "skipping" in results[0].message.lower()

    def test_fail_when_function_missing(self, tmp_path):
        db_path = tmp_path / "incomplete_harvester.db"
        self._make_db_with_harvester(db_path, "fake_harvester")
        engine = _get_engine_for(db_path)

        # Module exists but lacks res_event_from_session
        fake_module = MagicMock(spec=[])  # no attributes

        with (
            patch("nexusLIMS.builder.preflight.get_engine", return_value=engine),
            patch(
                "nexusLIMS.builder.preflight.import_module", return_value=fake_module
            ),
        ):
            results = _check_instrument_harvesters()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert any("res_event_from_session" in r.message for r in failed)


# ---------------------------------------------------------------------------
# _check_instrument_timezones
# ---------------------------------------------------------------------------


class TestCheckInstrumentTimezones:
    """Tests for _check_instrument_timezones."""

    def _make_db_with_tz(self, path: Path, tz: str) -> None:
        _make_full_db(path)
        conn = sqlite3.connect(str(path))
        conn.execute(
            "INSERT INTO instruments "
            "(instrument_pid, api_url, calendar_url, location, display_name, "
            "property_tag, filestore_path, harvester, timezone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TEST-1",
                "http://example.com/api/tools/?id=1",
                "http://example.com/cal/",
                "Room 1",
                "Test Instrument",
                "TAG-001",
                "./data",
                "nemo",
                tz,
            ),
        )
        conn.commit()
        conn.close()

    def test_pass_for_valid_timezone(self, tmp_path):
        db_path = tmp_path / "valid_tz.db"
        self._make_db_with_tz(db_path, "America/New_York")
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_timezones()

        assert all(r.passed for r in results)

    def test_warn_for_invalid_timezone(self, tmp_path):
        db_path = tmp_path / "invalid_tz.db"
        self._make_db_with_tz(db_path, "NotA/RealTimezone")
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_timezones()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert all(r.severity == "warning" for r in failed)

    def test_warn_when_engine_raises(self):
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("db error"),
        ):
            results = _check_instrument_timezones()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "warning"
        assert "could not query" in results[0].message.lower()

    def test_pass_when_no_instruments(self, tmp_path):
        """DB has no instruments — skip with PASS."""
        db_path = tmp_path / "empty.db"
        _make_full_db(db_path)
        engine = _get_engine_for(db_path)

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_instrument_timezones()

        assert len(results) == 1
        assert results[0].passed is True
        assert "skipping" in results[0].message.lower()


# ---------------------------------------------------------------------------
# _check_data_path_writable
# ---------------------------------------------------------------------------


class TestCheckDataPathWritable:
    """Tests for _check_data_path_writable."""

    def test_pass_when_writable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_DATA_PATH", tmp_path
        )
        with patch("nexusLIMS.builder.preflight.os.access", return_value=True):
            result = _check_data_path_writable()

        assert result.passed is True
        assert result.name == "data_path_writable"

    def test_fail_when_not_writable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.NX_DATA_PATH", tmp_path
        )
        with patch("nexusLIMS.builder.preflight.os.access", return_value=False):
            result = _check_data_path_writable()

        assert result.passed is False
        assert result.severity == "error"
        assert "not writable" in result.message.lower()


# ---------------------------------------------------------------------------
# _check_export_destinations
# ---------------------------------------------------------------------------


class TestCheckExportDestinations:
    """Tests for _check_export_destinations."""

    def test_pass_when_all_destinations_valid(self):
        dest = MagicMock()
        dest.name = "cdcs"
        dest.validate_config.return_value = (True, None)

        mock_registry = MagicMock()
        mock_registry.get_enabled_destinations.return_value = [dest]

        with patch(
            "nexusLIMS.builder.preflight.get_registry", return_value=mock_registry
        ):
            result = _check_export_destinations()

        assert result.passed is True
        assert "cdcs" in result.message

    def test_warn_when_destination_config_invalid(self):
        dest = MagicMock()
        dest.name = "cdcs"
        dest.validate_config.return_value = (False, "API key missing")

        mock_registry = MagicMock()
        mock_registry.get_enabled_destinations.return_value = [dest]

        with patch(
            "nexusLIMS.builder.preflight.get_registry", return_value=mock_registry
        ):
            result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"

    def test_warn_when_no_destinations_enabled(self):
        mock_registry = MagicMock()
        mock_registry.get_enabled_destinations.return_value = []

        with patch(
            "nexusLIMS.builder.preflight.get_registry", return_value=mock_registry
        ):
            result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"
        assert "no export destinations" in result.message.lower()

    def test_warn_when_get_registry_raises(self):
        with patch(
            "nexusLIMS.builder.preflight.get_registry",
            side_effect=Exception("registry error"),
        ):
            result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"
        assert "could not discover" in result.message.lower()

    def test_warn_when_validate_config_raises(self):
        dest = MagicMock()
        dest.name = "cdcs"
        dest.validate_config.side_effect = RuntimeError("unexpected crash")

        mock_registry = MagicMock()
        mock_registry.get_enabled_destinations.return_value = [dest]

        with patch(
            "nexusLIMS.builder.preflight.get_registry", return_value=mock_registry
        ):
            result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"
        assert "unexpected error" in result.message.lower()


# ---------------------------------------------------------------------------
# _check_nemo_harvester_config
# ---------------------------------------------------------------------------


class TestCheckNemoHarvesterConfig:
    """Tests for _check_nemo_harvester_config."""

    def _mock_connector(self, base_url="http://nemo.example.com/api/"):
        connector = MagicMock()
        connector.config = {"base_url": base_url, "token": "fake-token"}
        return connector

    def test_pass_when_harvesters_reachable(self, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters",
            lambda: {1: MagicMock()},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with (
            patch(
                "nexusLIMS.builder.preflight.get_harvesters_enabled",
                return_value=[self._mock_connector()],
            ),
            patch(
                "nexusLIMS.builder.preflight.nexus_req",
                return_value=mock_resp,
            ),
        ):
            results = _check_nemo_harvester_config()

        assert all(r.passed for r in results)
        assert any("reachable" in r.message for r in results)
        assert all(r.severity == "error" for r in results)

    def test_fail_hard_when_harvesters_unreachable_after_retries(self, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters",
            lambda: {1: MagicMock()},
        )

        with (
            patch(
                "nexusLIMS.builder.preflight.get_harvesters_enabled",
                return_value=[self._mock_connector()],
            ),
            patch(
                "nexusLIMS.builder.preflight.nexus_req",
                side_effect=Exception("Connection refused"),
            ),
            patch("nexusLIMS.builder.preflight.time.sleep"),
        ):
            results = _check_nemo_harvester_config()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert all(r.severity == "error" for r in failed)
        assert any("not reachable after 4 attempts" in r.message for r in failed)

    def test_retries_sleep_with_backoff(self, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters",
            lambda: {1: MagicMock()},
        )

        with (
            patch(
                "nexusLIMS.builder.preflight.get_harvesters_enabled",
                return_value=[self._mock_connector()],
            ),
            patch(
                "nexusLIMS.builder.preflight.nexus_req",
                side_effect=Exception("timeout"),
            ),
            patch("nexusLIMS.builder.preflight.time.sleep") as mock_sleep,
        ):
            _check_nemo_harvester_config()

        # Expect three sleep calls with delays 1, 2, 4
        assert mock_sleep.call_count == 3
        assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 2, 4]

    def test_warn_when_no_config_but_nemo_instruments(self, tmp_path, monkeypatch):
        db_path = tmp_path / "nemo_instruments.db"
        _make_full_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO instruments "
            "(instrument_pid, api_url, calendar_url, location, display_name, "
            "property_tag, filestore_path, harvester, timezone) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "TEST-NEMO",
                "http://example.com/api/tools/?id=1",
                "http://example.com/cal/",
                "Room 1",
                "Test Instrument",
                "TAG-001",
                "./data",
                "nemo",
                "America/New_York",
            ),
        )
        conn.commit()
        conn.close()

        engine = _get_engine_for(db_path)
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters", dict
        )

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_nemo_harvester_config()

        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        assert "TEST-NEMO" in failed[0].message

    def test_warn_when_nemo_harvesters_raises(self, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters",
            MagicMock(side_effect=Exception("config error")),
        )
        results = _check_nemo_harvester_config()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "warning"
        assert "could not read" in results[0].message.lower()

    def test_warn_when_no_harvesters_and_engine_raises(self, monkeypatch):
        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters", dict
        )
        with patch(
            "nexusLIMS.builder.preflight.get_engine",
            side_effect=Exception("db error"),
        ):
            results = _check_nemo_harvester_config()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].severity == "warning"
        assert "could not query" in results[0].message.lower()

    def test_pass_when_no_config_and_no_nemo_instruments(self, tmp_path, monkeypatch):
        db_path = tmp_path / "no_nemo.db"
        _make_full_db(db_path)  # No instruments inserted
        engine = _get_engine_for(db_path)

        monkeypatch.setattr(
            "nexusLIMS.builder.preflight.settings.nemo_harvesters", dict
        )

        with patch("nexusLIMS.builder.preflight.get_engine", return_value=engine):
            results = _check_nemo_harvester_config()

        assert all(r.passed for r in results)


# ---------------------------------------------------------------------------
# run_preflight_checks
# ---------------------------------------------------------------------------


class TestRunPreflightChecks:
    """Tests for the main run_preflight_checks() function."""

    def test_dry_run_skips_write_checks(self):
        """In dry-run mode, data_path_writable and export_destinations are absent."""
        with (
            patch(
                "nexusLIMS.builder.preflight._check_db_reachable",
                return_value=CheckResult("db_reachable", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_db_tables",
                return_value=CheckResult("db_tables", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_alembic_migration",
                return_value=CheckResult("alembic_migration", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instruments_exist",
                return_value=CheckResult("instruments_exist", True, "warning", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_filestore_paths",
                return_value=[
                    CheckResult("instrument_filestore_paths", True, "warning", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_harvesters",
                return_value=[
                    CheckResult("instrument_harvesters", True, "error", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_timezones",
                return_value=[
                    CheckResult("instrument_timezones", True, "warning", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_nemo_harvester_config",
                return_value=[
                    CheckResult("nemo_harvester_config", True, "warning", "ok")
                ],
            ),
        ):
            results = run_preflight_checks(dry_run=True)

        names = {r.name for r in results}
        assert "data_path_writable" not in names
        assert "export_destinations" not in names

    def test_non_dry_run_includes_write_checks(self):
        """In normal mode, data_path_writable and export_destinations are included."""
        with (
            patch(
                "nexusLIMS.builder.preflight._check_db_reachable",
                return_value=CheckResult("db_reachable", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_db_tables",
                return_value=CheckResult("db_tables", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_alembic_migration",
                return_value=CheckResult("alembic_migration", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instruments_exist",
                return_value=CheckResult("instruments_exist", True, "warning", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_filestore_paths",
                return_value=[
                    CheckResult("instrument_filestore_paths", True, "warning", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_harvesters",
                return_value=[
                    CheckResult("instrument_harvesters", True, "error", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_timezones",
                return_value=[
                    CheckResult("instrument_timezones", True, "warning", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_nemo_harvester_config",
                return_value=[
                    CheckResult("nemo_harvester_config", True, "warning", "ok")
                ],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_data_path_writable",
                return_value=CheckResult("data_path_writable", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_export_destinations",
                return_value=CheckResult("export_destinations", True, "warning", "ok"),
            ),
        ):
            results = run_preflight_checks(dry_run=False)

        names = {r.name for r in results}
        assert "data_path_writable" in names
        assert "export_destinations" in names

    def _all_checks_pass_patches(self):
        """Return a list of (target, return_value) for all checks that pass."""
        return [
            (
                "nexusLIMS.builder.preflight._check_db_reachable",
                CheckResult("db_reachable", True, "error", "ok"),
            ),
            (
                "nexusLIMS.builder.preflight._check_db_tables",
                CheckResult("db_tables", True, "error", "ok"),
            ),
            (
                "nexusLIMS.builder.preflight._check_alembic_migration",
                CheckResult("alembic_migration", True, "error", "ok"),
            ),
            (
                "nexusLIMS.builder.preflight._check_instruments_exist",
                CheckResult("instruments_exist", True, "warning", "ok"),
            ),
        ]

    def test_unexpected_exception_in_multi_check_returns_error_result(self):
        """Unexpected exception in a multi-result check is caught and returned."""
        with (
            patch(
                "nexusLIMS.builder.preflight._check_db_reachable",
                return_value=CheckResult("db_reachable", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_db_tables",
                return_value=CheckResult("db_tables", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_alembic_migration",
                return_value=CheckResult("alembic_migration", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instruments_exist",
                return_value=CheckResult("instruments_exist", True, "warning", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_filestore_paths",
                side_effect=RuntimeError("multi boom"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_harvesters",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_timezones",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_nemo_harvester_config",
                return_value=[],
            ),
        ):
            results = run_preflight_checks(dry_run=True)

        filestore_results = [
            r for r in results if r.name == "instrument_filestore_paths"
        ]
        assert len(filestore_results) == 1
        assert filestore_results[0].passed is False
        assert "multi boom" in filestore_results[0].message

    def test_unexpected_exception_in_write_check_returns_error_result(self):
        """Unexpected exception in a write-path check is caught and returned."""
        with (
            patch(
                "nexusLIMS.builder.preflight._check_db_reachable",
                return_value=CheckResult("db_reachable", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_db_tables",
                return_value=CheckResult("db_tables", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_alembic_migration",
                return_value=CheckResult("alembic_migration", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instruments_exist",
                return_value=CheckResult("instruments_exist", True, "warning", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_filestore_paths",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_harvesters",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_timezones",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_nemo_harvester_config",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_data_path_writable",
                side_effect=RuntimeError("write boom"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_export_destinations",
                return_value=CheckResult("export_destinations", True, "warning", "ok"),
            ),
        ):
            results = run_preflight_checks(dry_run=False)

        write_results = [r for r in results if r.name == "data_path_writable"]
        assert len(write_results) == 1
        assert write_results[0].passed is False
        assert "write boom" in write_results[0].message

    def test_unexpected_exception_in_single_check_returns_error_result(self):
        """Unexpected exception in a check is caught and returned as FAIL result."""
        with (
            patch(
                "nexusLIMS.builder.preflight._check_db_reachable",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_db_tables",
                return_value=CheckResult("db_tables", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_alembic_migration",
                return_value=CheckResult("alembic_migration", True, "error", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instruments_exist",
                return_value=CheckResult("instruments_exist", True, "warning", "ok"),
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_filestore_paths",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_harvesters",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_instrument_timezones",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.preflight._check_nemo_harvester_config",
                return_value=[],
            ),
        ):
            results = run_preflight_checks(dry_run=True)

        db_reachable_results = [r for r in results if r.name == "db_reachable"]
        assert len(db_reachable_results) == 1
        assert db_reachable_results[0].passed is False
        assert "boom" in db_reachable_results[0].message


# ---------------------------------------------------------------------------
# Integration: process_new_records raises PreflightError
# ---------------------------------------------------------------------------


class TestProcessNewRecordsAbortsOnPreflightError:
    """Verify that process_new_records() raises PreflightError on error checks."""

    def test_preflight_error_raised_on_error_check_failure(self):
        failed_check = CheckResult(
            name="db_reachable", passed=False, severity="error", message="DB missing"
        )

        with patch(
            "nexusLIMS.builder.record_builder.run_preflight_checks",
            return_value=[failed_check],
        ):
            from nexusLIMS.builder import record_builder

            with pytest.raises(PreflightError) as exc_info:
                record_builder.process_new_records(dry_run=True)

        assert "db_reachable" in str(exc_info.value)

    def test_no_preflight_error_when_all_pass(self):
        passing_check = CheckResult(
            name="db_reachable", passed=True, severity="error", message="ok"
        )

        with (
            patch(
                "nexusLIMS.builder.record_builder.run_preflight_checks",
                return_value=[passing_check],
            ),
            # Stop after preflight — don't actually run the record builder
            patch(
                "nexusLIMS.builder.record_builder.get_sessions_to_build",
                return_value=[],
            ),
            patch(
                "nexusLIMS.builder.record_builder.nemo_utils.get_usage_events_as_sessions",
                return_value=[],
            ),
        ):
            from nexusLIMS.builder import record_builder

            # Should not raise — empty sessions list causes early return
            record_builder.process_new_records(dry_run=True)
