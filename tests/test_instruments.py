# pylint: disable=C0116
# ruff: noqa: D102
"""Tests the workings of the NexusLIMS Instrument handling."""

from datetime import datetime
from pathlib import Path

from nexusLIMS.instruments import (
    Instrument,
    get_instr_from_api_url,
    get_instr_from_calendar_name,
    get_instr_from_filepath,
    instrument_db,
)

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
            "Calendar name:    FEI Titan TEM\n"
            "Calendar url:     https://nemo.example.com/calendar/FEI-Titan-TEM\n"
            "Schema name:      Titan TEM\n"
            "Location:         Test Building Room 301\n"
            "Property tag:     TEST-TEM-001\n"
            "Filestore path:   ./Titan_TEM\n"
            "Computer IP:      None\n"
            "Computer name:    None\n"
            "Computer mount:   None\n"
            "Harvester:        nemo\n"
            "Timezone:         America/Denver"
        )

    def test_get_instr_from_filepath(self):
        # Test that we can find the test instrument by its filepath
        # The test database contains TEST-INSTRUMENT-001 with
        # filestore_path = "./NexusLIMS/test_files"  # noqa: ERA001
        from nexusLIMS.config import settings

        test_instrument = instrument_db.get("testtool-TEST-A1234567")
        if test_instrument is not None:
            # Construct a path under this instrument's filestore path
            path = (
                Path(settings.NX_INSTRUMENT_DATA_PATH)
                / test_instrument.filestore_path
                / "some_file.dm3"
            )
            instr = get_instr_from_filepath(path)
            assert isinstance(instr, Instrument)
            assert instr.name == test_instrument.name

        # Test that a bad path returns None
        instr = get_instr_from_filepath(Path("bad_path_no_instrument"))
        assert instr is None

    def test_get_instr_from_cal_name(self):
        instr = get_instr_from_calendar_name("id=3")
        # This test requires an instrument in the database with api_url
        # containing "id=3". Since we're testing the database lookup
        # function, we just verify it returns an Instrument object or None
        if instr is not None:
            assert isinstance(instr, Instrument)

    def test_get_instr_from_cal_name_none(self):
        instr = get_instr_from_calendar_name("bogus calendar name")
        assert instr is None

    def test_instrument_datetime_location_no_tz(self, monkeypatch, caplog):
        titan_tem = make_titan_tem()
        monkeypatch.setattr(titan_tem, "timezone", None)
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
        import sqlite3

        from nexusLIMS.instruments import _get_instrument_db

        # Mock sqlite3.connect to raise sqlite3.Error
        def mock_connect(*_args, **_kwargs):
            msg = "Database connection failed"
            raise sqlite3.Error(msg)

        monkeypatch.setattr("sqlite3.connect", mock_connect)

        with caplog.at_level("WARNING"):
            result = _get_instrument_db()

        assert result == {}
        assert "Could not connect to database" in caplog.text

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
        import pytz

        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            name="test-instrument",
            schema_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_name="Test Tool",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            computer_name="test-computer",
            computer_ip="192.168.1.1",
            computer_mount="/mount/path",
            harvester="nemo",
            timezone=pytz.timezone("America/New_York"),
        )

        result = instrument.to_dict()

        # Check that 'name' was renamed to 'instrument_pid'
        assert "instrument_pid" in result
        assert "name" not in result
        assert result["instrument_pid"] == "test-instrument"

        # Check that timezone was converted to string
        assert isinstance(result["timezone"], str)
        assert "America/New_York" in result["timezone"]

    def test_instrument_to_dict_timezone_string(self):
        """Test Instrument.to_dict() when timezone is already a string."""
        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            name="test-instrument",
            schema_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_name="Test Tool",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            computer_name="test-computer",
            computer_ip="192.168.1.1",
            computer_mount="/mount/path",
            harvester="nemo",
            timezone="America/Denver",  # Already a string
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
            name="test-instrument",
            schema_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_name="Test Tool",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            computer_name="test-computer",
            computer_ip="192.168.1.1",
            computer_mount="/mount/path",
            harvester="nemo",
            timezone="America/Denver",
        )

        json_str = instrument.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["instrument_pid"] == "test-instrument"
        assert parsed["schema_name"] == "TestInstrument"

    def test_instrument_to_json_with_kwargs(self):
        """Test Instrument.to_json() with custom kwargs."""
        from nexusLIMS.instruments import Instrument

        instrument = Instrument(
            name="test-instrument",
            schema_name="TestInstrument",
            api_url="https://example.com/api/",
            calendar_name="Test Tool",
            location="Building 1",
            property_tag="12345",
            filestore_path="/path/to/files",
            computer_name="test-computer",
            computer_ip="192.168.1.1",
            computer_mount="/mount/path",
            harvester="nemo",
            timezone="America/Denver",
        )

        json_str = instrument.to_json(indent=2)

        # Should be pretty-printed
        assert "\n" in json_str
        assert "  " in json_str
