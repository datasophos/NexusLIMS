"""Tests for the handle_config_error context manager and its CLI integration."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Helper to create a realistic ValidationError
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = [
    "NX_INSTRUMENT_DATA_PATH",
    "NX_DATA_PATH",
    "NX_DB_PATH",
    "NX_CDCS_TOKEN",
    "NX_CDCS_URL",
]


def _make_validation_error(fields: list[str] | None = None) -> ValidationError:
    """Create a Pydantic ValidationError with the given field names missing."""
    if fields is None:
        fields = _REQUIRED_FIELDS
    model_cls = type(
        "Model",
        (BaseModel,),
        {"__annotations__": dict.fromkeys(fields, str)},
    )
    try:
        model_cls.model_validate({})
    except ValidationError as exc:
        return exc
    msg = "Expected ValidationError"  # pragma: no cover
    raise AssertionError(msg)  # pragma: no cover


class TestHandleConfigError:
    """Tests for the handle_config_error context manager."""

    def test_no_error_passes_through(self):
        """Normal code runs unmodified when no ValidationError is raised."""
        from nexusLIMS.cli import handle_config_error

        with handle_config_error():
            result = 1 + 1

        assert result == 2

    def test_non_validation_errors_propagate(self):
        """Exceptions other than ValidationError are not caught."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(RuntimeError, match="unrelated"), handle_config_error():  # noqa: PT012
            msg = "unrelated"
            raise RuntimeError(msg)

    def test_validation_error_causes_sys_exit(self):
        """A ValidationError triggers sys.exit(1)."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(SystemExit) as exc_info, handle_config_error():
            raise _make_validation_error(["NX_DATA_PATH"])

        assert exc_info.value.code == 1

    def test_output_contains_missing_fields(self, capsys):
        """The error message lists the missing/invalid field names."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(SystemExit), handle_config_error():
            raise _make_validation_error(["NX_DATA_PATH", "NX_CDCS_TOKEN"])

        stderr = capsys.readouterr().err
        assert "NX_DATA_PATH" in stderr
        assert "NX_CDCS_TOKEN" in stderr

    def test_output_mentions_config_edit(self, capsys):
        """The error message promotes 'nexuslims config edit'."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(SystemExit), handle_config_error():
            raise _make_validation_error(["NX_DB_PATH"])

        stderr = capsys.readouterr().err
        assert "nexuslims config edit" in stderr

    def test_output_contains_docs_url(self, capsys):
        """The error message includes the documentation URL."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(SystemExit), handle_config_error():
            raise _make_validation_error(["NX_DB_PATH"])

        stderr = capsys.readouterr().err
        assert "datasophos.github.io/NexusLIMS" in stderr
        assert "/user_guide/configuration.html" in stderr

    def test_dev_version_suffix_stripped_from_url(self, capsys):
        """A '.dev123' suffix on the version is stripped from the docs URL."""
        from nexusLIMS.cli import handle_config_error

        with (
            patch("nexusLIMS.version.__version__", "2.5.0.dev42"),
            pytest.raises(SystemExit),
            handle_config_error(),
        ):
            raise _make_validation_error(["NX_DB_PATH"])

        stderr = capsys.readouterr().err
        assert "2.5.0/user_guide" in stderr
        assert "dev" not in stderr

    def test_output_says_incomplete_or_invalid(self, capsys):
        """The first line communicates the problem clearly."""
        from nexusLIMS.cli import handle_config_error

        with pytest.raises(SystemExit), handle_config_error():
            raise _make_validation_error(["NX_DB_PATH"])

        stderr = capsys.readouterr().err
        assert "configuration is incomplete or invalid" in stderr


class TestProcessRecordsConfigError:
    """Test that nexuslims build-records shows a friendly config error."""

    def test_missing_config_shows_friendly_error(self):
        """Running without config shows the friendly message, not a traceback."""
        from nexusLIMS.cli.process_records import main

        runner = CliRunner(mix_stderr=False)

        # Mock the settings proxy so that any attribute access raises
        # ValidationError, simulating a completely unconfigured environment.
        error = _make_validation_error()
        with patch(
            "nexusLIMS.config._manager.get",
            side_effect=error,
        ):
            result = runner.invoke(main, catch_exceptions=False)

        assert result.exit_code == 1
        assert "nexuslims config edit" in result.stderr
        assert "Traceback" not in result.stderr
        assert "NX_DATA_PATH" in result.stderr


class TestConfigDumpConfigError:
    """Test that 'nexuslims config dump' shows a friendly config error."""

    def test_missing_config_shows_friendly_error(self):
        """Running dump without config shows the friendly message."""
        from nexusLIMS.cli.config import main

        runner = CliRunner(mix_stderr=False)

        error = _make_validation_error()
        with patch(
            "nexusLIMS.config._manager.get",
            side_effect=error,
        ):
            result = runner.invoke(main, ["dump"], catch_exceptions=False)

        assert result.exit_code == 1
        assert "nexuslims config edit" in result.stderr
        assert "Traceback" not in result.stderr
        assert "NX_CDCS_TOKEN" in result.stderr
