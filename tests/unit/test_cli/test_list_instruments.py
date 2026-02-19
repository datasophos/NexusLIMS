"""Tests for the ``nexuslims instruments list`` CLI command."""

import datetime
import json
from unittest.mock import MagicMock, patch

import pytz
from click.testing import CliRunner

from nexusLIMS.cli.main import main
from nexusLIMS.cli.manage_instruments import _truncate_url_middle


class TestTruncateUrlMiddle:
    """Tests for _truncate_url_middle helper."""

    def test_short_url_unchanged(self):
        url = "https://nemo.example.com/"
        assert _truncate_url_middle(url, max_width=40) == url

    def test_exact_width_unchanged(self):
        url = "https://nemo.example.com/?id=1"
        assert _truncate_url_middle(url, max_width=len(url)) == url

    def test_long_url_truncated(self):
        url = "https://nemo.example.com/api/tools/?id=12345"
        result = _truncate_url_middle(url, max_width=22)
        assert len(result) == 22
        assert "…" in result

    def test_truncated_preserves_start_and_end(self):
        url = "https://nemo.example.com/api/tools/?id=123"
        result = _truncate_url_middle(url, max_width=20)
        assert result.startswith("https://")
        assert result.endswith(url[-9:])


class TestListInstrumentsCommand:
    """Tests for ``nexuslims instruments list`` via CliRunner."""

    def _make_instrument(self, pid, display_name, location, api_url):
        inst = MagicMock()
        inst.instrument_pid = pid
        inst.display_name = display_name
        inst.location = location
        inst.api_url = api_url
        inst.harvester = "nemo"
        inst.timezone_str = "America/New_York"
        tz = pytz.timezone("America/New_York")
        inst.localize_datetime = lambda dt: dt.astimezone(tz)
        return inst

    def test_help_shows_expected_text(self):
        runner = CliRunner()
        result = runner.invoke(main, ["instruments", "list", "--help"])
        assert result.exit_code == 0
        assert "List all instruments in the database" in result.output
        assert "--format" in result.output

    def test_table_output_with_instruments(self, monkeypatch):
        """Table output lists instrument IDs and display names."""
        inst1 = self._make_instrument(
            "FEI-Titan-TEM-01",
            "FEI Titan TEM",
            "Room 123",
            "https://nemo.example.com/api/tools/?id=1",
        )
        inst2 = self._make_instrument(
            "JEOL-ARM-200F-67",
            "JEOL ARM 200F",
            "Room 456",
            "https://nemo.example.com/api/tools/?id=42",
        )

        last_ts = datetime.datetime(2025, 11, 3, 19, 22, 0, tzinfo=pytz.UTC)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.exec.side_effect = [
            MagicMock(all=MagicMock(return_value=[inst1, inst2])),
            MagicMock(one=MagicMock(return_value=(15, last_ts))),
            MagicMock(one=MagicMock(return_value=(8, last_ts))),
        ]

        with (
            patch("dotenv.load_dotenv"),
            patch("os.getenv", return_value="/fake/path/db.db"),
            patch("pathlib.Path.exists", return_value=True),
            patch("nexusLIMS.db.engine.get_engine"),
            patch("sqlmodel.Session", return_value=mock_session),
        ):
            runner = CliRunner()
            # Use wide terminal so Rich doesn't compress table columns
            result = runner.invoke(
                main,
                ["instruments", "list"],
                catch_exceptions=False,
                env={"COLUMNS": "200"},
            )

        assert result.exit_code == 0
        assert "FEI-Titan-TEM-01" in result.output
        assert "FEI Titan TEM" in result.output
        assert "JEOL-ARM-200F-67" in result.output
        assert "JEOL ARM 200F" in result.output

    def test_json_output_format(self, monkeypatch):
        """JSON output is valid JSON with expected keys."""
        inst = self._make_instrument(
            "FEI-Titan-TEM-01",
            "FEI Titan TEM",
            "Room 123",
            "https://nemo.example.com/api/tools/?id=1",
        )
        last_ts = datetime.datetime(2025, 11, 3, 19, 22, 0, tzinfo=pytz.UTC)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.exec.side_effect = [
            MagicMock(all=MagicMock(return_value=[inst])),
            MagicMock(one=MagicMock(return_value=(15, last_ts))),
        ]

        with (
            patch("dotenv.load_dotenv"),
            patch("os.getenv", return_value="/fake/path/db.db"),
            patch("pathlib.Path.exists", return_value=True),
            patch("nexusLIMS.db.engine.get_engine"),
            patch("sqlmodel.Session", return_value=mock_session),
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["instruments", "list", "--format", "json"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        record = data[0]
        assert record["instrument_pid"] == "FEI-Titan-TEM-01"
        assert record["display_name"] == "FEI Titan TEM"
        assert record["sessions_total"] == 15
        assert record["last_session"] is not None
        assert record["harvester"] == "nemo"

    def test_json_output_null_last_session(self):
        """JSON output has null last_session when no sessions exist."""
        inst = self._make_instrument(
            "FEI-Titan-TEM-01",
            "FEI Titan TEM",
            "Room 123",
            "https://nemo.example.com/api/tools/?id=1",
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.exec.side_effect = [
            MagicMock(all=MagicMock(return_value=[inst])),
            MagicMock(one=MagicMock(return_value=(0, None))),
        ]

        with (
            patch("dotenv.load_dotenv"),
            patch("os.getenv", return_value="/fake/path/db.db"),
            patch("pathlib.Path.exists", return_value=True),
            patch("nexusLIMS.db.engine.get_engine"),
            patch("sqlmodel.Session", return_value=mock_session),
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["instruments", "list", "--format", "json"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["sessions_total"] == 0
        assert data[0]["last_session"] is None

    def test_table_output_null_last_session(self):
        """Table output shows em dash when no sessions exist for an instrument."""
        inst = self._make_instrument(
            "FEI-Titan-TEM-01",
            "FEI Titan TEM",
            "Room 123",
            "https://nemo.example.com/api/tools/?id=1",
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.exec.side_effect = [
            MagicMock(all=MagicMock(return_value=[inst])),
            MagicMock(one=MagicMock(return_value=(0, None))),
        ]

        with (
            patch("dotenv.load_dotenv"),
            patch("os.getenv", return_value="/fake/path/db.db"),
            patch("pathlib.Path.exists", return_value=True),
            patch("nexusLIMS.db.engine.get_engine"),
            patch("sqlmodel.Session", return_value=mock_session),
        ):
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["instruments", "list"],
                catch_exceptions=False,
                env={"COLUMNS": "200"},
            )

        assert result.exit_code == 0
        assert "—" in result.output

    def test_empty_database_message(self):
        """Empty database prints a helpful message instead of a table."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.exec.return_value = MagicMock(all=MagicMock(return_value=[]))

        with (
            patch("dotenv.load_dotenv"),
            patch("os.getenv", return_value="/fake/path/db.db"),
            patch("pathlib.Path.exists", return_value=True),
            patch("nexusLIMS.db.engine.get_engine"),
            patch("sqlmodel.Session", return_value=mock_session),
        ):
            runner = CliRunner()
            result = runner.invoke(
                main, ["instruments", "list"], catch_exceptions=False
            )

        assert result.exit_code == 0
        assert "No instruments found" in result.output
        assert "nexuslims instruments manage" in result.output
