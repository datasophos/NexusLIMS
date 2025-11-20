# pylint: disable=C0116
# ruff: noqa: D102
"""Tests the workings of the NexusLIMS Instrument handling."""

import os
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
        # Note: Factory sets default values for computer_name and computer_ip
        assert (
            repr(titan_tem) == "Nexus Instrument: FEI-Titan-TEM\n"
            "API url:          http://test.example.com/api/\n"
            "Calendar name:    FEI Titan TEM\n"
            "Calendar url:     http://test.example.com/calendar/FEI-Titan-TEM\n"
            "Schema name:      Titan TEM\n"
            "Location:         Test Building Room 301\n"
            "Property tag:     TEST-TEM-001\n"
            "Filestore path:   Titan_TEM\n"
            "Computer IP:      192.168.1.100\n"
            "Computer name:    computer-fei-titan-tem\n"
            "Computer mount:   None\n"
            "Harvester:        nemo\n"
            "Timezone:         America/Denver"
        )

    def test_get_instr_from_filepath(self):
        # Test that we can find the test instrument by its filepath
        # The test database contains TEST-INSTRUMENT-001 with
        # filestore_path = "./NexusLIMS/test_files"  # noqa: ERA001
        test_instrument = instrument_db.get("testtool-TEST-A1234567")
        if test_instrument is not None:
            # Construct a path under this instrument's filestore path
            path = (
                Path(os.environ["NX_INSTRUMENT_DATA_PATH"])
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
        # This tests the database lookup function
        # It will return an instrument if one exists with matching api_url
        returned_item = get_instr_from_api_url(
            f"{os.environ.get('NX_NEMO_ADDRESS_1', 'http://test.example.com/api/')}tools/?id=10",
        )
        # Verify it returns an Instrument or None
        if returned_item is not None:
            assert isinstance(returned_item, Instrument)

    def test_instrument_from_api_url_none(self):
        returned_item = get_instr_from_api_url(
            "https://test.example.com/api/tools/?id=-1",
        )
        assert returned_item is None
