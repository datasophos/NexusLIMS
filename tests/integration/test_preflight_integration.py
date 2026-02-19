"""Integration tests for preflight checks.

These tests verify that the preflight checks interact correctly with live
external services (NEMO, CDCS). They require Docker services to be running.

Unlike the unit tests (which mock every external call), these tests:
- Let the NEMO connectivity probe hit the real NEMO API.
- Let the CDCS export destination check authenticate against real CDCS.
- Run ``run_preflight_checks()`` end-to-end with the full service stack.

Run with Docker services up:
    pytest tests/integration/test_preflight_integration.py -v
"""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from nexusLIMS.builder.preflight import (
    _ALEMBIC_INI_PATH,
    PreflightError,
    _check_export_destinations,
    _check_nemo_harvester_config,
    run_preflight_checks,
)

# ---------------------------------------------------------------------------
# Session-scoped helper: seed alembic_version into the shared integration DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def integration_db_with_alembic(docker_services):
    """Add an alembic_version row at the current head to the session DB.

    The shared integration DB is created via SQLModel (no alembic migrations
    are run), so it has all ORM tables but no alembic_version table.  This
    fixture seeds that row so ``_check_alembic_migration`` reports PASS rather
    than a hard error during full-run tests.
    """
    from nexusLIMS.db.engine import get_engine

    cfg = Config(str(_ALEMBIC_INI_PATH))
    cfg.set_main_option(
        "script_location",
        str(_ALEMBIC_INI_PATH.parent / "nexusLIMS" / "db" / "migrations"),
    )
    head = ScriptDirectory.from_config(cfg).get_current_head()

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text(f"INSERT INTO alembic_version VALUES ('{head}')"))
        conn.commit()

    yield head

    # Cleanup: drop so other tests that expect the table to be absent aren't affected
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()


# ---------------------------------------------------------------------------
# NEMO connectivity
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPreflightNemoConnectivity:
    """nemo_harvester_config check against a live NEMO service."""

    def test_nemo_reachable_when_service_running(self, nemo_client):
        """Connectivity probe passes when NEMO Docker service is up.

        ``nemo_client`` sets NX_NEMO_ADDRESS_1 / NX_NEMO_TOKEN_1 and calls
        refresh_settings(), so ``nemo_harvesters()`` returns one harvester.
        The probe should receive any HTTP response and report PASS.
        """
        results = _check_nemo_harvester_config()

        assert len(results) == 1
        result = results[0]
        assert result.passed is True
        assert result.severity == "error"
        assert "reachable" in result.message.lower()
        assert "HTTP" in result.message

    def test_nemo_unreachable_fails_hard(self, monkeypatch):
        """Connectivity probe exhausts retries and returns severity=error.

        The NEMO address is unreachable (nothing listening on the port).
        A connection-refused error on localhost is immediate so the test
        completes in roughly 7 s (3 sleeps: 1 + 2 + 4 s).
        """
        from nexusLIMS.config import refresh_settings

        monkeypatch.setenv("NX_NEMO_ADDRESS_1", "http://localhost:19999/api/")
        monkeypatch.setenv("NX_NEMO_TOKEN_1", "irrelevant")
        refresh_settings()

        results = _check_nemo_harvester_config()

        assert len(results) == 1
        result = results[0]
        assert result.passed is False
        assert result.severity == "error"
        assert "not reachable after 4 attempts" in result.message

    def test_nemo_http_error_still_counts_as_reachable(self, nemo_url, monkeypatch):
        """An HTTP 4xx/5xx from NEMO counts as reachable (server is up).

        Using the correct NEMO base URL but a deliberately wrong token should
        still return an HTTP response (likely 401/403), which the check treats
        as "server is reachable".
        """
        from nexusLIMS.config import refresh_settings

        monkeypatch.setenv("NX_NEMO_ADDRESS_1", f"{nemo_url}/api/")
        monkeypatch.setenv("NX_NEMO_TOKEN_1", "bad-token-that-does-not-exist")
        refresh_settings()

        results = _check_nemo_harvester_config()

        assert len(results) == 1
        result = results[0]
        assert result.passed is True, (
            f"Expected PASS (HTTP error = server up), got: {result.message}"
        )
        assert "HTTP" in result.message


# ---------------------------------------------------------------------------
# CDCS export destinations
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPreflightExportDestinations:
    """export_destinations check against a live CDCS service."""

    def test_cdcs_passes_with_valid_credentials(self, cdcs_client, monkeypatch):
        """CDCS destination passes when credentials are valid.

        ``cdcs_client`` sets NX_CDCS_URL and NX_CDCS_TOKEN to the test
        instance values and calls refresh_settings().

        In NX_TEST_MODE the eLabFTW settings have non-None defaults, so
        eLabFTW is always enabled alongside CDCS.  We disable it here so the
        check is purely about CDCS.
        """
        from nexusLIMS.exporters.destinations.elabftw import ELabFTWDestination

        monkeypatch.setattr(ELabFTWDestination, "enabled", property(lambda _: False))

        result = _check_export_destinations()

        assert result.passed is True, f"Expected CDCS to pass; got: {result.message}"
        assert result.severity == "warning"

    def test_cdcs_warns_with_invalid_token(self, cdcs_url, monkeypatch):
        """CDCS destination warns (not errors) when the token is invalid.

        The check uses severity="warning" for destination config issues because
        a transient network error should not abort a run.
        """
        from nexusLIMS.config import refresh_settings

        monkeypatch.setenv("NX_CDCS_URL", cdcs_url)
        monkeypatch.setenv("NX_CDCS_TOKEN", "this-token-is-definitely-invalid-xyz")
        refresh_settings()

        result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"
        msg = result.message.lower()
        assert "cdcs" in msg or "authentication" in msg

    def test_cdcs_warns_when_no_destinations_configured(self, monkeypatch):
        """export_destinations warns when all destination ``enabled`` props are False.

        NX_TEST_MODE provides default values for NX_CDCS_URL and NX_CDCS_TOKEN,
        so env-var deletion alone can't produce "no destinations".  We monkeypatch
        the ``enabled`` property on both destination classes to force the
        no-destinations code path.
        """
        from nexusLIMS.exporters.destinations.cdcs import CDCSDestination
        from nexusLIMS.exporters.destinations.elabftw import ELabFTWDestination

        monkeypatch.setattr(CDCSDestination, "enabled", property(lambda _: False))
        monkeypatch.setattr(ELabFTWDestination, "enabled", property(lambda _: False))

        result = _check_export_destinations()

        assert result.passed is False
        assert result.severity == "warning"
        assert "no export destinations" in result.message.lower()


# ---------------------------------------------------------------------------
# Full run_preflight_checks() with all services live
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPreflightFullRun:
    """End-to-end tests that call run_preflight_checks() with real services."""

    def test_no_error_checks_fail_with_full_stack(
        self,
        nemo_client,
        cdcs_client,
        integration_db_with_alembic,
    ):
        """With NEMO, CDCS, and a properly migrated DB, no error-severity check fails.

        Expected result: all checks pass or produce warnings only.  Warnings
        (instruments_exist, nemo_harvester_config, etc.) are fine because the
        test DB is empty.  There should be zero error-severity failures.
        """
        results = run_preflight_checks(dry_run=True)

        failed_errors = [r for r in results if not r.passed and r.severity == "error"]
        assert failed_errors == [], "Unexpected error-severity failures: " + str(
            [(r.name, r.message) for r in failed_errors]
        )

    def test_process_new_records_does_not_abort_on_valid_config(
        self,
        nemo_client,
        cdcs_client,
        integration_db_with_alembic,
    ):
        """process_new_records(dry_run=True) must not raise PreflightError.

        With all services configured correctly, the preflight gate should pass
        and execution should continue (finding no sessions to build in the
        empty test DB is fine).
        """
        from nexusLIMS.builder import record_builder

        try:
            record_builder.process_new_records(dry_run=True)
        except PreflightError as e:
            pytest.fail(
                "process_new_records raised PreflightError unexpectedly. "
                f"Failed checks: {[(c.name, c.message) for c in e.failed_checks]}"
            )
        except Exception:
            # Post-preflight failures (no sessions, gfind errors, missing files,
            # etc.) are acceptable — the preflight gate passed, which is what
            # this test verifies.
            pass
