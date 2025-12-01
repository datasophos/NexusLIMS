"""Tests for the record builder module."""

# pylint: disable=missing-function-docstring,too-many-locals
# ruff: noqa: D102, ARG001, ARG002, ARG005, PLR2004

import re
import shutil
from datetime import datetime as dt
from datetime import timedelta as td
from functools import partial
from pathlib import Path

import pytest
from lxml import etree

from nexusLIMS.builder import record_builder
from nexusLIMS.builder.record_builder import build_record
from nexusLIMS.db import make_db_query, session_handler
from nexusLIMS.db.session_handler import Session, SessionLog, db_query
from nexusLIMS.harvesters.nemo.exceptions import NoMatchingReservationError
from nexusLIMS.harvesters.reservation_event import ReservationEvent
from nexusLIMS.instruments import Instrument
from nexusLIMS.utils import current_system_tz
from tests.test_instrument_factory import (
    make_test_tool,
    make_titan_tem,
)


class TestRecordBuilder:
    """Tests the record building module."""

    @property
    def instr_data_path(self):
        """Get the NX_INSTRUMENT_DATA_PATH as a Path object."""
        from nexusLIMS.config import settings

        return Path(settings.NX_INSTRUMENT_DATA_PATH)

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_dry_run_file_find(
        self,
        test_record_files,
    ):
        """Test file finding for multiple sessions with different instruments."""
        # Get all sessions from test database
        # fresh_test_db fixture provides 3 sessions:
        #   FEI-Titan-TEM, JEOL-JEM-TEM, testtool
        sessions = session_handler.get_sessions_to_build()
        assert len(sessions) == 3

        # Expected file counts for each session:
        # - FEI-Titan-TEM (2018-11-13): 10 files (8 .dm3 + 2 .ser, .emi excluded)
        # - JEOL-JEM-TEM (2019-07-24): 8 files (.dm3 in subdirs)
        # - testtool-TEST-A1234567 (2021-08-02): 4 files (.dm3)
        correct_files_per_session = [10, 8, 4]

        file_list_list = []
        for session, expected_count in zip(sessions, correct_files_per_session):
            found_files = record_builder.dry_run_file_find(session)
            file_list_list.append(found_files)
            assert len(found_files) == expected_count

        # Verify specific files are found in each session
        assert (
            self.instr_data_path
            / "Titan_TEM/researcher_a/project_alpha/20181113/image_001.dm3"
        ) in file_list_list[0]

        assert (
            self.instr_data_path
            / "JEOL_TEM/researcher_b/project_beta/20190724/beam_study_1/image_1.dm3"
        ) in file_list_list[1]

        assert (
            self.instr_data_path / "Nexus_Test_Instrument/test_files/sample_001.dm3"
        ) in file_list_list[2]

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_dry_run_file_find_no_files(
        self,
        test_record_files,
        caplog,
    ):
        """Test file finding for multiple sessions with different instruments."""
        # Get all sessions from test database
        # fresh_test_db fixture provides 3 sessions:
        #   FEI-Titan-TEM, JEOL-JEM-TEM, testtool
        dt_from = dt.fromisoformat("2019-09-06T17:00:00.000-06:00")
        dt_to = dt.fromisoformat("2019-09-06T18:00:00.000-06:00")
        s = Session(
            session_identifier="test_session",
            instrument=make_test_tool(),
            dt_range=(dt_from, dt_to),
            user="test",
        )

        # this should find no files for the given time range and test tool,
        # and a warning should be logged
        found_files = record_builder.dry_run_file_find(s)
        assert found_files == []
        assert re.search(r"\nWARNING.*No files found for this session", caplog.text)

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_process_new_records_dry_run(self, test_record_files):
        # just running to ensure coverage, tests are included above
        record_builder.process_new_records(
            dry_run=True,
            dt_to=dt.fromisoformat("2021-08-03T00:00:00-04:00"),
        )

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_process_new_records_dry_run_no_sessions(
        self,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(record_builder, "get_sessions_to_build", list)
        # there shouldn't be any MARLIN sessions before July 1, 2017
        record_builder.process_new_records(
            dry_run=True,
            dt_to=dt.fromisoformat("2017-07-01T00:00:00-04:00"),
        )
        assert "No 'TO_BE_BUILT' sessions were found. Exiting." in caplog.text

    @pytest.mark.usefixtures(
        "_cleanup_session_log",
        "mock_nemo_reservation",
    )
    def test_process_new_records_no_files_warning(
        self,
        monkeypatch,
        caplog,
    ):
        # overload "get_sessions_to_build" to return just one session
        dt_str_from = "2019-09-06T17:00:00.000-06:00"
        dt_str_to = "2019-09-06T18:00:00.000-06:00"
        monkeypatch.setattr(
            record_builder,
            "get_sessions_to_build",
            lambda: [
                Session(
                    session_identifier="test_session",
                    instrument=make_test_tool(),
                    dt_range=(
                        dt.fromisoformat(dt_str_from),
                        dt.fromisoformat(dt_str_to),
                    ),
                    user="test",
                ),
            ],
        )
        record_builder.process_new_records(
            dry_run=False,
            dt_to=dt.fromisoformat("2021-07-01T00:00:00-04:00"),
        )
        assert "No files found in " in caplog.text

    @pytest.fixture(name="_add_recent_test_session")
    def _add_recent_test_session(self, request, monkeypatch):
        # insert a dummy session to DB that was within past day so it gets
        # skipped (we assume no files are being regularly added into the test
        # instrument folder)

        # the ``request.param`` parameter controls whether the timestamps have
        # timezones attached
        if request.param:
            start_ts = dt.now(tz=current_system_tz()).replace(tzinfo=None) - td(days=1)
            end_ts = dt.now(tz=current_system_tz()).replace(tzinfo=None) - td(days=0.5)
        else:
            start_ts = dt.now(tz=current_system_tz()) - td(days=1)
            end_ts = dt.now(tz=current_system_tz()) - td(days=0.5)
        start = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=start_ts.isoformat(),
            event_type="START",
            user="test",
            record_status="TO_BE_BUILT",
        )
        start.insert_log()
        end = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=end_ts.isoformat(),
            event_type="END",
            user="test",
            record_status="TO_BE_BUILT",
        )
        end.insert_log()

        s = Session(
            session_identifier="test_session",
            instrument=make_titan_tem(),
            dt_range=(start_ts, end_ts),
            user="test",
        )
        # return just our session of interest to build and disable nemo
        # harvester's add_all_usage_events_to_db method
        monkeypatch.setattr(record_builder, "get_sessions_to_build", lambda: [s])
        monkeypatch.setattr(
            record_builder.nemo_utils,
            "add_all_usage_events_to_db",
            lambda dt_from, dt_to: None,
        )
        monkeypatch.setattr(
            record_builder.nemo,
            "res_event_from_session",
            lambda session: ReservationEvent(
                experiment_title="test",
                instrument=session.instrument,
                username="test",
                start_time=session.dt_from,
                end_time=session.dt_to,
            ),
        )

    # this parametrize call provides "request.param" with values of True and
    # then False to the add_recent_test_session fixture, which is used to
    # test both timezone-aware and timezone-naive delay implementations
    # (see https://stackoverflow.com/a/36087408)
    @pytest.mark.parametrize("_add_recent_test_session", [True, False], indirect=True)
    @pytest.mark.usefixtures(
        "_add_recent_test_session",
        "_cleanup_session_log",
    )
    def test_process_new_records_within_delay(
        self,
        caplog,
    ):
        record_builder.process_new_records(dry_run=False)
        assert (
            "Configured record building delay has not passed; "
            "Removing previously inserted RECORD_GENERATION " in caplog.text
        )

        _, res = db_query(
            "SELECT * FROM session_log WHERE session_identifier = ?",
            ("test_session",),
        )
        inserted_row_count = 2
        assert res[0][5] == "TO_BE_BUILT"
        assert res[1][5] == "TO_BE_BUILT"
        assert len(res) == inserted_row_count

    @pytest.mark.usefixtures("_cleanup_session_log")
    def test_process_new_nemo_record_with_no_reservation(
        self,
        monkeypatch,
        caplog,
    ):
        """
        Test building record with no reservation.

        This test method tests building a record from a NEMO instrument with
        no matching reservation; should result in "COMPLETED" status
        """
        start_ts = "2020-01-01T12:00:00.000-05:00"
        end_ts = "2020-01-01T20:00:00.000-05:00"
        start = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=start_ts,
            event_type="START",
            user="test",
            record_status="TO_BE_BUILT",
        )
        start.insert_log()
        end = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=end_ts,
            event_type="END",
            user="test",
            record_status="TO_BE_BUILT",
        )
        end.insert_log()

        s = Session(
            session_identifier="test_session",
            instrument=make_test_tool(),
            dt_range=(dt.fromisoformat(start_ts), dt.fromisoformat(end_ts)),
            user="test",
        )
        # return just our session of interest to build and disable nemo
        # harvester's add_all_usage_events_to_db method
        monkeypatch.setattr(record_builder, "get_sessions_to_build", lambda: [s])
        monkeypatch.setattr(
            record_builder.nemo_utils,
            "add_all_usage_events_to_db",
            lambda dt_from, dt_to: None,
        )

        # Mock res_event_from_session to raise NoMatchingReservationError
        # This simulates the scenario where no reservation is found
        def mock_res_event_no_reservation(session):
            msg = (
                "No reservation found matching this session, so assuming NexusLIMS "
                "does not have user consent for data harvesting."
            )
            raise NoMatchingReservationError(msg)

        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.res_event_from_session",
            mock_res_event_no_reservation,
        )

        record_builder.process_new_records(dry_run=False)

        assert (
            "No reservation found matching this session, so assuming "
            "NexusLIMS does not have user consent for data harvesting." in caplog.text
        )

        _, res = db_query(
            "SELECT * FROM session_log WHERE session_identifier = ?",
            ("test_session",),
        )
        assert res[0][5] == "NO_RESERVATION"
        assert res[1][5] == "NO_RESERVATION"
        assert res[2][5] == "NO_RESERVATION"

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_new_session_processor(
        self,
        test_record_files,
        monkeypatch,
    ):
        # make record uploader just pretend by returning all files provided
        # (as if they were actually uploaded)
        monkeypatch.setattr(record_builder, "upload_record_files", lambda x: (x, x))

        # Override the build_records function to not generate previews (since
        # this is tested elsewhere) to speed things up
        monkeypatch.setattr(
            record_builder,
            "build_record",
            partial(build_record, generate_previews=False),
        )

        # Process all sessions in the database (all 3 test sessions)
        # The fresh_test_db fixture already has FEI-Titan-TEM, JEOL-JEM-TEM,
        # and testtool sessions
        record_builder.process_new_records(
            dt_from=dt.fromisoformat("2018-01-01T00:00:00-04:00"),
            dt_to=dt.fromisoformat("2022-01-01T00:00:00-04:00"),
        )

        # tests on the database entries
        # after processing the records, there should be added
        # "RECORD_GENERATION" logs
        # Updated counts to match 3 test sessions:
        # - FEI-Titan-TEM (2 logs: START + END)
        # - JEOL-JEM-TEM (2 logs: START + END)
        # - testtool-TEST-A1234567 (2 logs: START + END)
        # - 3 RECORD_GENERATION logs added during processing
        total_session_log_count = 9  # 6 original + 3 RECORD_GENERATION
        record_generation_count = 3  # One for each session
        to_be_built_count = 0
        no_files_found_count = 0
        completed_count = 9  # All 9 logs marked as COMPLETED
        assert (
            len(
                make_db_query("SELECT * FROM session_log"),
            )
            == total_session_log_count
        )
        assert (
            len(
                make_db_query(
                    "SELECT * FROM session_log WHERE "
                    '"event_type" = "RECORD_GENERATION"',
                ),
            )
            == record_generation_count
        )
        assert (
            len(
                make_db_query(
                    'SELECT * FROM session_log WHERE "record_status" = "TO_BE_BUILT"',
                ),
            )
            == to_be_built_count
        )
        assert (
            len(
                make_db_query(
                    'SELECT * FROM session_log WHERE"record_status" = "NO_FILES_FOUND"',
                ),
            )
            == no_files_found_count
        )
        assert (
            len(
                make_db_query(
                    'SELECT * FROM session_log WHERE "record_status" = "COMPLETED"',
                ),
            )
            == completed_count
        )

        # tests on the XML records
        # Updated for 3 test sessions (Titan TEM, JEOL TEM, Nexus Test Instrument)
        from nexusLIMS.config import settings

        upload_path = settings.records_dir_path / "uploaded"
        xmls = list(upload_path.glob("*.xml"))
        xml_count = 3  # One for each test session
        assert len(xmls) == xml_count

        # test some various values from the records saved to disk:
        nexus_ns = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"
        expected = {
            # Updated for simplified test sessions with URL-based session identifiers
            # Titan TEM session (id=101)
            "2018-11-13_FEI-Titan-TEM_101.xml": {
                f"/{{{nexus_ns}}}title": "Microstructure analysis of steel alloys",
                f"//{{{nexus_ns}}}acquisitionActivity": 2,
                f"//{{{nexus_ns}}}dataset": 10,
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation": (
                    "Characterize phase transformations in heat-treated steel"
                ),
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument": "FEI-Titan-TEM",
                f"//{{{nexus_ns}}}sample": 1,
            },
            # JEOL TEM session (id=202)
            "2019-07-24_JEOL-JEM-TEM_202.xml": {
                f"/{{{nexus_ns}}}title": "EELS mapping of multilayer thin films",
                f"//{{{nexus_ns}}}acquisitionActivity": 1,
                f"//{{{nexus_ns}}}dataset": 8,
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation": (
                    "Study layer intermixing in deposited thin films"
                ),
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument": "JEOL-JEM-TEM",
                f"//{{{nexus_ns}}}sample": 1,
            },
            # Nexus Test Instrument session (id=303)
            "2021-08-02_testtool-TEST-A1234567_303.xml": {
                f"/{{{nexus_ns}}}title": "EDX spectroscopy of platinum-nickel alloys",
                f"//{{{nexus_ns}}}acquisitionActivity": 1,
                f"//{{{nexus_ns}}}dataset": 4,
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation": (
                    "Determine composition of Pt-Ni alloy samples"
                ),
                f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument": (
                    "testtool-TEST-A1234567"
                ),
                f"//{{{nexus_ns}}}sample": 1,
            },
        }
        for f in sorted(xmls):
            base_f = f.name
            root = etree.parse(f)

            xpath = f"/{{{nexus_ns}}}title"
            if root.find(xpath) is not None:
                assert root.find(xpath).text == expected[base_f][xpath]

            xpath = f"//{{{nexus_ns}}}acquisitionActivity"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            xpath = f"//{{{nexus_ns}}}dataset"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            xpath = f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation"
            if root.find(xpath) is not None:
                assert root.find(xpath).text == expected[base_f][xpath]
            else:
                assert root.find(xpath) == expected[base_f][xpath]

            xpath = f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument"
            assert root.find(xpath).get("pid") == expected[base_f][xpath]

            xpath = f"//{{{nexus_ns}}}sample"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            # remove record
            f.unlink()

        # clean up directory
        shutil.rmtree(upload_path.parent)

    @pytest.mark.usefixtures("mock_nemo_reservation")
    @pytest.mark.parametrize(
        ("strategy_name", "env_value", "expected_datasets"),
        [
            ("inclusive", "inclusive", 14),
            ("default", None, 10),
            ("unsupported", "bob", 10),
        ],
        ids=["inclusive_strategy", "default_strategy", "unsupported_strategy"],
    )
    def test_record_builder_file_strategies(
        self,
        test_record_files,
        monkeypatch,
        strategy_name,
        env_value,
        expected_datasets,
    ):
        """Test record builder with different file-finding strategies.

        Args:
            strategy_name: Name of the strategy being tested (for clarity)
            env_value: Value to set for NX_FILE_STRATEGY (None = unset)
            expected_datasets: Expected number of dataset elements in XML
        """

        # Use the Titan TEM session from fresh_test_db
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            return [s for s in all_sessions if s.instrument.name == "FEI-Titan-TEM"]

        nexus_ns = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "upload_record_files", lambda x: (x, x))
        monkeypatch.setattr(
            record_builder,
            "build_record",
            partial(build_record, generate_previews=False),
        )

        # Set or unset the file strategy in settings
        # (monkeypatching environment variables doesn't work because settings
        # is already instantiated)
        from nexusLIMS.config import settings

        if env_value is None:
            # Use default "exclusive" strategy
            monkeypatch.setattr(settings, "NX_FILE_STRATEGY", "exclusive")
        else:
            monkeypatch.setattr(settings, "NX_FILE_STRATEGY", env_value)

        # Build the record
        xml_files = record_builder.build_new_session_records()
        assert len(xml_files) == 1
        f = xml_files[0]

        # Parse and validate the XML
        root = etree.parse(f)
        aa_count = 2  # Two temporal clusters based on file timestamps

        assert (
            root.find(f"/{{{nexus_ns}}}title").text
            == "Microstructure analysis of steel alloys"
        )
        assert len(root.findall(f"//{{{nexus_ns}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{nexus_ns}}}dataset")) == expected_datasets
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation").text
            == "Characterize phase transformations in heat-treated steel"
        )
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument").get("pid")
            == "FEI-Titan-TEM"
        )
        assert len(root.findall(f"//{{{nexus_ns}}}sample")) == 1

        # remove record
        f.unlink()

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_new_session_bad_upload(
        self,
        monkeypatch,
        caplog,
    ):
        # set the methods used to determine if all records were uploaded to
        # just return known lists
        monkeypatch.setattr(
            record_builder,
            "build_new_session_records",
            lambda: ["dummy_file1", "dummy_file2", "dummy_file3"],
        )
        monkeypatch.setattr(record_builder, "upload_record_files", lambda _x: ([], []))

        record_builder.process_new_records(
            dt_from=dt.fromisoformat("2021-08-01T13:00:00-06:00"),
            dt_to=dt.fromisoformat("2021-09-05T20:00:00-06:00"),
        )
        assert (
            "Some record files were not uploaded: "
            "['dummy_file1', 'dummy_file2', 'dummy_file3']" in caplog.text
        )

    def test_build_record_error(self, monkeypatch, caplog):
        def mock_get_sessions():
            return [
                session_handler.Session(
                    "dummy_id",
                    "no_instrument",
                    (dt.now(tz=current_system_tz()), dt.now(tz=current_system_tz())),
                    "None",
                ),
            ]

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        record_builder.build_new_session_records()
        assert 'Marking dummy_id as "ERROR"' in caplog.text

    def test_non_validating_record(
        self,
        monkeypatch,
        caplog,
    ):
        # pylint: disable=unused-argument
        def mock_get_sessions():
            return [
                session_handler.Session(
                    session_identifier="1c3a6a8d-9038-41f5-b969-55fd02e12345",
                    instrument=make_titan_tem(),
                    dt_range=(
                        dt.fromisoformat("2020-02-04T09:00:00.000"),
                        dt.fromisoformat("2020-02-04T12:00:00.001"),
                    ),
                    user="None",
                ),
            ]

        def mock_build_record(
            session,
            sample_id=None,
            *,
            generate_previews=True,
        ):
            return "<xml>Record that will not validate against NexusLIMS Schema</xml>"

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "build_record", mock_build_record)
        record_builder.build_new_session_records()
        assert "ERROR" in caplog.text
        assert "Could not validate record, did not write to disk" in caplog.text

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_dump_record(self, test_record_files):
        dt_str_from = "2021-08-02T09:00:00-07:00"
        dt_str_to = "2021-08-02T11:00:00-07:00"
        session = Session(
            session_identifier="an-identifier-string",
            instrument=make_test_tool(),
            dt_range=(dt.fromisoformat(dt_str_from), dt.fromisoformat(dt_str_to)),
            user="unused",
        )
        out_fname = record_builder.dump_record(session=session, generate_previews=False)
        out_fname.unlink()

    def test_no_sessions(self, monkeypatch):
        # monkeypatch to return empty list (as if there are no sessions)
        monkeypatch.setattr(record_builder, "get_sessions_to_build", list)
        with pytest.raises(SystemExit) as exception:
            record_builder.build_new_session_records()
        assert exception.type is SystemExit

    def test_build_record_no_consent(
        self,
        monkeypatch,
        caplog,
    ):
        # Mock res_event_from_session to raise NoDataConsentError
        from nexusLIMS.harvesters.nemo.exceptions import NoDataConsentError

        def mock_res_event_no_consent(session):
            msg = "Reservation requested not to have their data harvested"
            raise NoDataConsentError(msg)

        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.res_event_from_session",
            mock_res_event_no_consent,
        )

        def mock_get_sessions():
            return [
                session_handler.Session(
                    session_identifier="test_session",
                    instrument=make_test_tool(),
                    dt_range=(
                        dt.fromisoformat("2021-12-08T09:00:00.000-07:00"),
                        dt.fromisoformat("2021-12-08T12:00:00.000-07:00"),
                    ),
                    user="None",
                ),
            ]

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        xmls_files = record_builder.build_new_session_records()

        _, res = db_query(
            "SELECT * FROM session_log WHERE session_identifier = ?",
            ("test_session",),
        )
        assert res[0][5] == "NO_CONSENT"
        assert "Reservation requested not to have their data harvested" in caplog.text
        assert len(xmls_files) == 0  # no record should be returned

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_build_record_single_file(self, test_record_files, monkeypatch):
        """Test record builder with a narrow time window that captures only 1 file."""

        # Use testtool-TEST-A1234567 from database with narrow time window
        # Files are at: 17:00, 17:15, 17:30, 17:45 UTC (10:00, 10:15, 10:30, 10:45 PDT)
        # This window captures only sample_002.dm3 at 17:15 UTC
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            test_instr = next(
                s for s in all_sessions if s.instrument.name == "testtool-TEST-A1234567"
            )
            # Create custom session with narrow window
            return [
                session_handler.Session(
                    session_identifier=test_instr.session_identifier,
                    instrument=test_instr.instrument,
                    dt_range=(
                        dt.fromisoformat("2021-08-02T17:10:00.000+00:00"),
                        dt.fromisoformat("2021-08-02T17:20:00.000+00:00"),
                    ),
                    user="test_user",
                ),
            ]

        nexus_ns = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "upload_record_files", lambda x: (x, x))

        xml_files = record_builder.build_new_session_records()
        assert len(xml_files) == 1

        aa_count = 1
        dataset_count = 1

        f = xml_files[0]
        root = etree.parse(f)

        # Verify it used the mock_nemo_reservation data for testtool-TEST-A1234567
        assert (
            root.find(f"/{{{nexus_ns}}}title").text
            == "EDX spectroscopy of platinum-nickel alloys"
        )
        assert len(root.findall(f"//{{{nexus_ns}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{nexus_ns}}}dataset")) == dataset_count
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation").text
            == "Determine composition of Pt-Ni alloy samples"
        )
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument").get("pid")
            == "testtool-TEST-A1234567"
        )

        # remove record
        f.unlink()

    def test_build_record_with_sample_elements(
        self,
        test_record_files,
        monkeypatch,
    ):
        # Mock res_event_from_session to return reservation with multiple samples
        def mock_res_event_with_samples(session):
            return ReservationEvent(
                experiment_title=(
                    "Test reservation for multiple samples, "
                    "some with elements, some not"
                ),
                instrument=session.instrument,
                username=session.user,
                user_full_name="Test User",
                start_time=session.dt_from,
                end_time=session.dt_to,
                experiment_purpose="testing",
                reservation_type="User session",
                sample_details=[
                    "Sample without elements",
                    "Sample with S, Rb, Sb, Re, Cm elements",
                    "Sample with Ir element",
                ],
                sample_pid=["sample-001", "sample-002", "sample-003"],
                sample_name=["Sample 1", "Sample 2", "Sample 3"],
                project_name=["Test Project"],
                project_id=["test-project-001"],
                sample_elements=[None, ["S", "Rb", "Sb", "Re", "Cm"], ["Ir"]],
            )

        monkeypatch.setattr(
            "nexusLIMS.harvesters.nemo.res_event_from_session",
            mock_res_event_with_samples,
        )

        # Use the Nexus Test Instrument session from fresh_test_db
        # Filter to get just the testtool-TEST-A1234567 session
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            return [
                s for s in all_sessions if s.instrument.name == "testtool-TEST-A1234567"
            ]

        nexus_ns = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)

        # make record uploader just pretend by returning all files provided (
        # as if they were actually uploaded)
        monkeypatch.setattr(record_builder, "upload_record_files", lambda x: (x, x))

        # override preview generation to save time
        monkeypatch.setattr(
            record_builder,
            "build_record",
            partial(build_record, generate_previews=False),
        )

        xml_files = record_builder.build_new_session_records()

        aa_count = 1
        dataset_count = 4
        sample_count = 3

        assert len(xml_files) == 1
        f = xml_files[0]
        root = etree.parse(f)

        assert (
            root.find(f"/{{{nexus_ns}}}title").text
            == "Test reservation for multiple samples, some with elements, some not"
        )
        assert len(root.findall(f"//{{{nexus_ns}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{nexus_ns}}}dataset")) == dataset_count
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}motivation").text
            == "testing"
        )
        assert (
            root.find(f"/{{{nexus_ns}}}summary/{{{nexus_ns}}}instrument").get("pid")
            == "testtool-TEST-A1234567"
        )
        assert len(root.findall(f"//{{{nexus_ns}}}sample")) == sample_count

        # test sample element tags
        expected = [
            None,
            [
                f"{{{nexus_ns}}}S",
                f"{{{nexus_ns}}}Rb",
                f"{{{nexus_ns}}}Sb",
                f"{{{nexus_ns}}}Re",
                f"{{{nexus_ns}}}Cm",
            ],
            [f"{{{nexus_ns}}}Ir"],
        ]
        sample_elements = root.findall(f"//{{{nexus_ns}}}sample")
        for exp, element in zip(expected, sample_elements):
            this_element = element.find(f"{{{nexus_ns}}}elements")
            if exp is None:
                assert exp == this_element
            else:
                assert [i.tag for i in this_element] == exp

        # remove record
        f.unlink()

    def test_not_implemented_harvester(self):
        # need to create a session with an instrument with a bogus harvester
        i = Instrument(harvester="bogus")
        s = session_handler.Session(
            session_identifier="identifier",
            instrument=i,
            dt_range=(
                dt.fromisoformat("2021-12-09T11:40:00-07:00"),
                dt.fromisoformat("2021-12-09T11:41:00-07:00"),
            ),
            user="miclims",
        )
        with pytest.raises(NotImplementedError) as exception:
            record_builder.get_reservation_event(s)
        assert "Harvester bogus not found in nexusLIMS.harvesters" in str(
            exception.value,
        )

    def test_not_implemented_res_event_from_session(self, monkeypatch):
        # create a session, but mock remove the res_event_from_session
        # attribute from the nemo harvester to simulate a module that doesn't
        # have that method defined
        with monkeypatch.context() as m_patch:
            m_patch.delattr("nexusLIMS.harvesters.nemo.res_event_from_session")
            with pytest.raises(NotImplementedError) as exception:
                record_builder.get_reservation_event(
                    session_handler.Session(
                        session_identifier="identifier",
                        instrument=make_test_tool(),
                        dt_range=(
                            dt.fromisoformat("2021-12-09T11:40:00-07:00"),
                            dt.fromisoformat("2021-12-09T11:41:00-07:00"),
                        ),
                        user="miclims",
                    ),
                )
            assert "res_event_from_session has not been implemented for" in str(
                exception.value,
            )
