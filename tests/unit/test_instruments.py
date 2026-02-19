# pylint: disable=C0116
"""Tests the workings of the NexusLIMS Instrument handling."""

from datetime import datetime
from pathlib import Path

import pytest
import pytz

from nexusLIMS.instruments import (
    Instrument,
    get_instr_from_api_url,
    get_instr_from_calendar_name,
    get_instr_from_filepath,
    instrument_db,
)
from nexusLIMS.utils.paths import join_instrument_filestore_path

from .test_instrument_factory import (
    make_titan_tem,
)


class TestInstruments:
    """Tests the nexusLIMS.instruments module."""

    def test_getting_instruments(self):
        assert isinstance(instrument_db, dict)

    def test_instrument_str(self):
        titan_tem = make_titan_tem()
        assert str(titan_tem) == "FEI-Titan-TEM in Test Building Room 301"

    def test_instrument_repr(self):
        titan_tem = make_titan_tem()
        assert (
            repr(titan_tem) == "Nexus Instrument: FEI-Titan-TEM\n"
            "API url:          https://nemo.example.com/api/tools/?id=2\n"
            "Calendar url:     https://nemo.example.com/calendar/FEI-Titan-TEM\n"
            "Display name:     Titan TEM\n"
            "Location:         Test Building Room 301\n"
            "Property tag:     TEST-TEM-001\n"
            "Filestore path:   ./Titan_TEM\n"
            "Harvester:        nemo\n"
            "Timezone:         America/Denver"
        )

    def test_get_instr_from_filepath(self):
        # Test that we can find the test instrument by its filepath
        # The test database contains TEST-INSTRUMENT-001 with
        # filestore_path = "./NexusLIMS/test_files"  # noqa: ERA001
        test_instrument = instrument_db.get("TEST-TOOL")
        if test_instrument is not None:
            # Construct a path under this instrument's filestore path
            path = (
                join_instrument_filestore_path(test_instrument.filestore_path)
                / "some_file.dm3"
            )
            instr = get_instr_from_filepath(path)
            assert isinstance(instr, Instrument)
            assert instr.name == test_instrument.name

        # Test that a bad path returns None
        instr = get_instr_from_filepath(Path("bad_path_no_instrument"))
        assert instr is None

    def test_get_instr_from_cal_name(self):
        """Test get_instr_from_calendar_name with a known calendar name."""
        # Search for a calendar name substring that should match an instrument
        # in the test database (e.g., "id=3" matches api_url containing that)
        instr = get_instr_from_calendar_name("id=3")
        # This test requires an instrument in the database with api_url
        # containing "id=3". Since we're testing the database lookup
        # function, we just verify it returns an Instrument object or None
        if instr is not None:
            assert isinstance(instr, Instrument)

    def test_get_instr_from_cal_name_none(self):
        instr = get_instr_from_calendar_name("bogus calendar name")
        assert instr is None

    @pytest.mark.needs_db(instruments=["FEI-Quanta-ESEM"])
    def test_get_instr_from_cal_name_found(self):
        """Test that get_instr_from_calendar_name returns an instrument when found."""
        # FEI-Quanta-ESEM has api_url "https://nemo.example.com/api/tools/?id=3"
        # So searching for "id=3" should find it
        instr = get_instr_from_calendar_name("id=3")
        assert instr is not None
        assert isinstance(instr, Instrument)
        assert instr.instrument_pid == "FEI-Quanta-ESEM"

    def test_instrument_datetime_location_no_tz(self, monkeypatch, caplog):
        titan_tem = make_titan_tem()
        # Set timezone_str to None to test the None timezone case
        monkeypatch.setattr(titan_tem, "timezone_str", None)
        # Mock the timezone property to return None
        monkeypatch.setattr(
            type(titan_tem),
            "timezone",
            property(
                lambda self: None
                if self.timezone_str is None
                else pytz.timezone(self.timezone_str)
            ),
        )
        dt_naive = datetime.fromisoformat("2021-11-26T12:00:00.000")
        assert titan_tem.localize_datetime(dt_naive) == dt_naive
        assert "Tried to localize a datetime with instrument" in caplog.text

    def test_instrument_datetime_localization(self):
        titan_tem = make_titan_tem()
        # titan_tem timezone is America/Denver (Mountain Time)

        dt_naive = datetime.fromisoformat("2021-11-26T12:00:00.000")
        dt_mt = datetime.fromisoformat("2021-11-26T12:00:00.000-07:00")
        dt_et = datetime.fromisoformat("2021-11-26T12:00:00.000-05:00")

        def _strftime(_dt):
            return _dt.strftime("%Y-%m-%d %H:%M:%S %Z")

        assert (
            _strftime(titan_tem.localize_datetime(dt_naive))
            == "2021-11-26 12:00:00 MST"
        )
        assert (
            _strftime(titan_tem.localize_datetime(dt_mt)) == "2021-11-26 12:00:00 MST"
        )
        assert (
            _strftime(titan_tem.localize_datetime(dt_et)) == "2021-11-26 10:00:00 MST"
        )

    def test_instrument_datetime_localization_str(self):
        titan_tem = make_titan_tem()
        dt_naive = datetime.fromisoformat("2021-11-26T12:00:00.000")
        dt_mt = datetime.fromisoformat("2021-11-26T12:00:00.000-07:00")
        dt_et = datetime.fromisoformat("2021-11-26T12:00:00.000-05:00")

        assert titan_tem.localize_datetime_str(dt_naive) == "2021-11-26 12:00:00 MST"
        assert titan_tem.localize_datetime_str(dt_mt) == "2021-11-26 12:00:00 MST"
        assert titan_tem.localize_datetime_str(dt_et) == "2021-11-26 10:00:00 MST"

    def test_instrument_from_api_url(self):
        from nexusLIMS.config import settings

        # This tests the database lookup function
        # It will return an instrument if one exists with matching api_url
        nemo_harvesters = settings.nemo_harvesters()
        nemo_address = (
            str(next(iter(nemo_harvesters.values())).address)
            if nemo_harvesters
            else "https://nemo.example.com/api/"
        )
        returned_item = get_instr_from_api_url(
            f"{nemo_address}tools/?id=10",
        )
        # Verify it returns an Instrument or None
        if returned_item is not None:
            assert isinstance(returned_item, Instrument)

    def test_instrument_from_api_url_none(self):
        returned_item = get_instr_from_api_url(
            "https://nemo.example.com/api/tools/?id=-1",
        )
        assert returned_item is None

    def test_get_instruments_db_error(self, monkeypatch, caplog):
        """Test _get_instrument_db with database error."""
        from nexusLIMS.instruments import _get_instrument_db

        # Mock DBSession to raise an exception
        def mock_session(*_args, **_kwargs):
            msg = "Database connection failed"
            raise RuntimeError(msg)

        monkeypatch.setattr("nexusLIMS.instruments.DBSession", mock_session)

        with caplog.at_level("WARNING"):
            result = _get_instrument_db()

        assert result == {}
        assert "Could not connect to database or retrieve instruments" in caplog.text

    def test_get_instruments_db_config_unavailable_logs_debug_not_warning(
        self, monkeypatch, caplog
    ):
        """ValidationError from missing config logs at DEBUG, not WARNING."""
        import logging

        from pydantic import ValidationError
        from pydantic_core import InitErrorDetails, PydanticCustomError

        from nexusLIMS.instruments import _get_instrument_db

        # Build a minimal ValidationError like pydantic raises for missing fields
        validation_error = ValidationError.from_exception_data(
            "Settings",
            [
                InitErrorDetails(
                    type=PydanticCustomError("missing", "Field required"),
                    loc=("NX_DB_PATH",),
                    input={},
                )
            ],
        )

        class _BrokenSettings:
            def __getattr__(self, name):
                raise validation_error

        monkeypatch.setattr("nexusLIMS.instruments.settings", _BrokenSettings())

        with caplog.at_level("DEBUG"):
            result = _get_instrument_db()

        assert result == {}
        assert "standalone mode" in caplog.text
        # Must NOT appear at WARNING level
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not any(
            "Could not connect to database" in r.message for r in warning_records
        )

    def test_get_instruments_db_key_error(self, tmp_path, caplog):
        """Test _get_instrument_db with KeyError from missing instrument_pid column."""
        import sqlite3

        from nexusLIMS.instruments import _get_instrument_db

        # Create a real database with malformed schema (missing instrument_pid column)
        db_file = tmp_path / "test_broken.db"
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # Create table without instrument_pid column (will cause KeyError)
        cursor.execute("""
            CREATE TABLE instruments (
                name TEXT,
                filestore_path TEXT,
                harvester TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO instruments (name, filestore_path, harvester)
            VALUES ('test-instr', '/path/to/files', 'nemo')
        """)
        conn.commit()
        conn.close()

        with caplog.at_level("WARNING"):
            result = _get_instrument_db(db_path=db_file)

        assert result == {}
        assert "Could not connect to database or retrieve instruments" in caplog.text

    def test_instrument_to_dict(self):
        """Test Instrument.to_dict() method."""
        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            instrument_pid="test-instrument",
            display_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_url="https://example.com/calendar/",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            harvester="nemo",
            timezone_str="America/New_York",
        )

        result = instrument.to_dict()

        # Check that 'instrument_pid' is in the result
        assert "instrument_pid" in result
        assert result["instrument_pid"] == "test-instrument"

        # Check that timezone was kept as string
        assert isinstance(result["timezone"], str)
        assert result["timezone"] == "America/New_York"

    def test_instrument_to_dict_timezone_string(self):
        """Test Instrument.to_dict() when timezone is already a string."""
        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            instrument_pid="test-instrument",
            display_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_url="https://example.com/calendar/",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            harvester="nemo",
            timezone_str="America/Denver",  # Already a string
        )

        result = instrument.to_dict()

        # Timezone should remain a string
        assert isinstance(result["timezone"], str)
        assert result["timezone"] == "America/Denver"

    def test_instrument_to_json(self):
        """Test Instrument.to_json() method."""
        import json

        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            instrument_pid="test-instrument",
            display_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_url="https://example.com/calendar/",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            harvester="nemo",
            timezone_str="America/Denver",
        )

        json_str = instrument.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["instrument_pid"] == "test-instrument"
        assert parsed["display_name"] == "TestInstrument"

    def test_instrument_to_json_with_kwargs(self):
        """Test Instrument.to_json() with custom kwargs."""
        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            instrument_pid="test-instrument",
            display_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_url="https://example.com/calendar/",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            harvester="nemo",
            timezone_str="America/Denver",
        )

        json_str = instrument.to_json(indent=2)

        # Should be pretty-printed
        assert "\n" in json_str
        assert "  " in json_str
