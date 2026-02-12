"""Tests for the record builder module."""

# pylint: disable=missing-function-docstring,too-many-locals
# ruff: noqa: ARG005

import re
import shutil
from datetime import datetime as dt
from datetime import timedelta as td
from functools import partial
from pathlib import Path

import pytest
from lxml import etree
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.builder import record_builder
from nexusLIMS.builder.record_builder import build_record
from nexusLIMS.db import session_handler
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog
from nexusLIMS.db.session_handler import Session
from nexusLIMS.exporters.base import ExportResult
from nexusLIMS.harvesters.nemo.exceptions import NoMatchingReservationError
from nexusLIMS.harvesters.reservation_event import ReservationEvent
from nexusLIMS.instruments import Instrument
from nexusLIMS.utils.time import current_system_tz
from tests.unit.test_instrument_factory import (
    make_test_tool,
    make_titan_tem,
)

NX_NS = "https://data.nist.gov/od/dm/nexus/experiment/v1.0"
"""Nexus Schema XML namespace for use throughout the tests"""


def _mock_successful_export(xml_files, sessions):
    """Create mock successful export results for testing.

    Returns a dict mapping each XML file to a list with one successful ExportResult.
    """
    from datetime import datetime as dt

    results = {}
    for xml_file in xml_files:
        results[xml_file] = [
            ExportResult(
                success=True,
                destination_name="cdcs",
                record_id="test_record_id",
                record_url="https://test.cdcs.url/record/123",
                timestamp=dt.now(),
            )
        ]
    return results


def _mock_failed_export(xml_files, sessions):
    """Create mock failed export results for testing.

    Returns a dict mapping each XML file to a list with one failed ExportResult.
    """
    from datetime import datetime as dt

    results = {}
    for xml_file in xml_files:
        results[xml_file] = [
            ExportResult(
                success=False,
                destination_name="cdcs",
                error_message="Test export failure",
                timestamp=dt.now(),
            )
        ]
    return results


@pytest.fixture
def skip_preview_generation(monkeypatch):
    """Skip preview generation in tests to improve performance.

    This fixture monkeypatches build_new_session_records to skip preview
    generation, which is time-consuming and tested separately. This speeds
    up tests that don't specifically need to test preview generation.
    """
    original_build_new_session_records = record_builder.build_new_session_records
    monkeypatch.setattr(
        record_builder,
        "build_new_session_records",
        lambda: original_build_new_session_records(generate_previews=False),
    )


@pytest.mark.needs_db(
    instruments=["FEI-Titan-TEM", "JEOL-JEM-TEM", "TEST-TOOL"],
    sessions=True,
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
        # - FEI-Titan-TEM (2018-11-13): 11 files
        #       (8 .dm3 + 2 .ser, .emi excluded, 1 .tif from Tescan)
        # - JEOL-JEM-TEM (2019-07-24): 8 files (.dm3 in subdirs)
        # - TEST-TOOL (2021-08-02): 4 files (.dm3)
        correct_files_per_session = [11, 8, 4]

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
    def test_dry_run_file_find_mixed_case_extensions(
        self,
        test_record_files,
    ):
        """Test file finding with mixed-case extensions (e.g., .dm3 and .DM3)."""
        # Get the Titan TEM session
        sessions = session_handler.get_sessions_to_build()
        titan_session = sessions[0]  # FEI-Titan-TEM session

        # Create copies of existing files with uppercase extensions
        test_dir = (
            self.instr_data_path / "Titan_TEM/researcher_a/project_alpha/20181113"
        )

        # Copy image_001.dm3 to image_001_copy.DM3 (uppercase)
        src_file = test_dir / "image_001.dm3"
        uppercase_copy = test_dir / "image_001_copy.DM3"
        shutil.copy2(src_file, uppercase_copy)

        # Copy image_002.dm3 to image_002_copy.Dm3 (mixed case)
        src_file2 = test_dir / "image_002.dm3"
        mixedcase_copy = test_dir / "image_002_copy.Dm3"
        shutil.copy2(src_file2, mixedcase_copy)

        try:
            # Find files - should now include the uppercase/mixed-case copies
            found_files = record_builder.dry_run_file_find(titan_session)

            # Original count: 11 files
            #   (8 .dm3 + 2 .ser, .emi excluded, 1 .tif from Tescan)
            # New count: 13 files (11 original + 2 uppercase copies)
            assert len(found_files) == 13

            # Verify both lowercase and uppercase versions are found
            assert (test_dir / "image_001.dm3") in found_files
            assert (test_dir / "image_001_copy.DM3") in found_files
            assert (test_dir / "image_002.dm3") in found_files
            assert (test_dir / "image_002_copy.Dm3") in found_files

        finally:
            # Clean up the test copies
            uppercase_copy.unlink(missing_ok=True)
            mixedcase_copy.unlink(missing_ok=True)

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_dry_run_file_find_mixed_case_tif_extensions(
        self,
        test_record_files,
    ):
        """Test file finding with mixed-case .tif extensions (.tif/.TIF/.Tif)."""
        # Get the Titan TEM session
        sessions = session_handler.get_sessions_to_build()
        titan_session = sessions[0]  # FEI-Titan-TEM session

        # Create test TIFF files with various case combinations
        test_dir = (
            self.instr_data_path / "Titan_TEM/researcher_a/project_alpha/20181113"
        )

        # Use image_001.dm3 as source, copy to various .tif extensions
        src_file = test_dir / "image_001.dm3"

        # Create .tif files with different case combinations
        # Note: The system uses -iname *.tif/*.tiff pattern, which matches
        # case-insensitively
        tif_lowercase = test_dir / "scan_lowercase.tif"
        tif_uppercase = test_dir / "scan_uppercase.TIF"
        tif_mixed1 = test_dir / "scan_mixed1.Tif"
        tif_mixed2 = test_dir / "scan_mixed2.TiF"
        tiff_lowercase = test_dir / "scan_lowercase.tiff"
        tiff_uppercase = test_dir / "scan_uppercase.TIFF"
        tiff_mixed1 = test_dir / "scan_mixed1.TifF"
        tiff_mixed2 = test_dir / "scan_mixed2.TiFf"

        test_files = [
            tif_lowercase,
            tif_uppercase,
            tif_mixed1,
            tif_mixed2,
            tiff_lowercase,
            tiff_uppercase,
            tiff_mixed1,
            tiff_mixed2,
        ]

        try:
            # Create all test TIFF files
            for test_file in test_files:
                shutil.copy2(src_file, test_file)

            # Find files - should now include all .tif variations
            found_files = record_builder.dry_run_file_find(titan_session)

            # Original count: 11 files
            #   (8 .dm3 + 2 .ser, .emi excluded, 1 .tif from Tescan)
            # New count: 19 files (11 original + 4 .tif + 4 .tiff files)
            assert len(found_files) == 19

            # Verify all .tif variations are found
            for test_file in test_files:
                assert test_file in found_files, f"{test_file} not found in results"

        finally:
            # Clean up all test copies
            for test_file in test_files:
                test_file.unlink(missing_ok=True)

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
    def _add_recent_test_session(self, request, monkeypatch, db_context):
        # insert a dummy session to DB that was within past day so it gets
        # skipped (we assume no files are being regularly added into the test
        # instrument folder)
        # NOTE: Depends on db_context to ensure test database is set up first

        # Create the instrument directory structure for file finding
        # This prevents gfind errors when trying to search for files
        instrument_dir = self.instr_data_path / "Titan_TEM"
        instrument_dir.mkdir(parents=True, exist_ok=True)

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
            timestamp=start_ts,
            event_type=EventType.START,
            user="test",
            record_status=RecordStatus.TO_BE_BUILT,
        )
        start.insert_log()
        end = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=end_ts,
            event_type=EventType.END,
            user="test",
            record_status=RecordStatus.TO_BE_BUILT,
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

        with DBSession(get_engine()) as db_session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == "test_session"
            )
            res = db_session.exec(statement).all()

        # Filter to START and END events (record_builder adds RECORD_GENERATION)
        start_end_logs = [
            r for r in res if r.event_type in (EventType.START, EventType.END)
        ]
        inserted_row_count = 2
        assert start_end_logs[0].record_status == RecordStatus.TO_BE_BUILT
        assert start_end_logs[1].record_status == RecordStatus.TO_BE_BUILT
        assert len(start_end_logs) == inserted_row_count

        # Verify that RECORD_GENERATION log was actually deleted
        record_gen_logs = [
            r for r in res if r.event_type == EventType.RECORD_GENERATION
        ]
        assert len(record_gen_logs) == 0, (
            "RECORD_GENERATION log should have been deleted when delay hasn't passed"
        )

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
        start_ts = dt.fromisoformat("2020-01-01T12:00:00.000-05:00")
        end_ts = dt.fromisoformat("2020-01-01T20:00:00.000-05:00")
        start = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=start_ts,
            event_type=EventType.START,
            user="test",
            record_status=RecordStatus.TO_BE_BUILT,
        )
        start.insert_log()
        end = SessionLog(
            session_identifier="test_session",
            instrument="FEI-Titan-TEM",
            timestamp=end_ts,
            event_type=EventType.END,
            user="test",
            record_status=RecordStatus.TO_BE_BUILT,
        )
        end.insert_log()

        s = Session(
            session_identifier="test_session",
            instrument=make_test_tool(),
            dt_range=(start_ts, end_ts),  # Already datetime objects
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

        # Query session logs using SQLModel
        with DBSession(get_engine()) as db_session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == "test_session"
            )
            logs = db_session.exec(statement).all()

        assert len(logs) == 3
        for log in logs:
            assert log.record_status == RecordStatus.NO_RESERVATION

    @pytest.mark.usefixtures("mock_nemo_reservation", "skip_preview_generation")
    def test_new_session_processor(
        self,
        test_record_files,
        monkeypatch,
    ):
        # Mock export_records to return successful results
        monkeypatch.setattr(record_builder, "export_records", _mock_successful_export)

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
        # - TEST-TOOL (2 logs: START + END)
        # - 3 RECORD_GENERATION logs added during processing
        total_session_log_count = 9  # 6 original + 3 RECORD_GENERATION
        record_generation_count = 3  # One for each session
        to_be_built_count = 0
        no_files_found_count = 0
        completed_count = 9  # All 9 logs marked as COMPLETED

        with DBSession(get_engine()) as db_session:
            # Count all session logs
            all_logs = db_session.exec(select(SessionLog)).all()
            assert len(all_logs) == total_session_log_count

            # Count RECORD_GENERATION logs
            record_gen_logs = db_session.exec(
                select(SessionLog).where(
                    SessionLog.event_type == EventType.RECORD_GENERATION
                )
            ).all()
            assert len(record_gen_logs) == record_generation_count

            # Count TO_BE_BUILT logs
            to_be_built_logs = db_session.exec(
                select(SessionLog).where(
                    SessionLog.record_status == RecordStatus.TO_BE_BUILT
                )
            ).all()
            assert len(to_be_built_logs) == to_be_built_count

            # Count NO_FILES_FOUND logs
            no_files_logs = db_session.exec(
                select(SessionLog).where(
                    SessionLog.record_status == RecordStatus.NO_FILES_FOUND
                )
            ).all()
            assert len(no_files_logs) == no_files_found_count

            # Count COMPLETED logs
            completed_logs = db_session.exec(
                select(SessionLog).where(
                    SessionLog.record_status == RecordStatus.COMPLETED
                )
            ).all()
            assert len(completed_logs) == completed_count

        # tests on the XML records
        # Updated for 3 test sessions (Titan TEM, JEOL TEM, Nexus Test Instrument)
        from nexusLIMS.config import settings

        upload_path = settings.records_dir_path / "uploaded"
        xmls = list(upload_path.glob("*.xml"))
        xml_count = 3  # One for each test session
        assert len(xmls) == xml_count

        # test some various values from the records saved to disk:
        expected = {
            # Updated for simplified test sessions with URL-based session identifiers
            # Titan TEM session (id=101)
            "2018-11-13_FEI-Titan-TEM_101.xml": {
                f"/{{{NX_NS}}}title": "Microstructure analysis of steel alloys",
                f"//{{{NX_NS}}}acquisitionActivity": 3,
                f"//{{{NX_NS}}}dataset": 11,
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation": (
                    "Characterize phase transformations in heat-treated steel"
                ),
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument": "FEI-Titan-TEM",
                f"//{{{NX_NS}}}sample": 1,
            },
            # JEOL TEM session (id=202)
            "2019-07-24_JEOL-JEM-TEM_202.xml": {
                f"/{{{NX_NS}}}title": "EELS mapping of multilayer thin films",
                f"//{{{NX_NS}}}acquisitionActivity": 1,
                f"//{{{NX_NS}}}dataset": 8,
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation": (
                    "Study layer intermixing in deposited thin films"
                ),
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument": "JEOL-JEM-TEM",
                f"//{{{NX_NS}}}sample": 1,
            },
            # Nexus Test Instrument session (id=303)
            "2021-08-02_TEST-TOOL_303.xml": {
                f"/{{{NX_NS}}}title": "EDX spectroscopy of platinum-nickel alloys",
                f"//{{{NX_NS}}}acquisitionActivity": 1,
                f"//{{{NX_NS}}}dataset": 4,
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation": (
                    "Determine composition of Pt-Ni alloy samples"
                ),
                f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument": ("TEST-TOOL"),
                f"//{{{NX_NS}}}sample": 1,
            },
        }
        for f in sorted(xmls):
            base_f = f.name
            root = etree.parse(f)

            xpath = f"/{{{NX_NS}}}title"
            if root.find(xpath) is not None:
                assert root.find(xpath).text == expected[base_f][xpath]

            xpath = f"//{{{NX_NS}}}acquisitionActivity"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            xpath = f"//{{{NX_NS}}}dataset"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            xpath = f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation"
            if root.find(xpath) is not None:
                assert root.find(xpath).text == expected[base_f][xpath]
            else:
                assert root.find(xpath) == expected[base_f][xpath]

            xpath = f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument"
            assert root.find(xpath).get("pid") == expected[base_f][xpath]

            xpath = f"//{{{NX_NS}}}sample"
            assert len(root.findall(xpath)) == expected[base_f][xpath]

            # remove record
            f.unlink()

        # clean up directory
        shutil.rmtree(upload_path.parent)

    @pytest.mark.usefixtures("mock_nemo_reservation")
    @pytest.mark.parametrize(
        ("strategy_name", "env_value", "expected_datasets"),
        [
            ("inclusive", "inclusive", 16),
            ("default", None, 11),
            ("unsupported", "bob", 11),
        ],
        ids=["inclusive_strategy", "default_strategy", "unsupported_strategy"],
    )
    def test_record_builder_file_strategies(  # noqa: PLR0913
        self,
        test_record_files,
        monkeypatch,
        strategy_name,
        env_value,
        expected_datasets,
        skip_preview_generation,
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

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "export_records", _mock_successful_export)
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
        xml_files, _ = record_builder.build_new_session_records()
        assert len(xml_files) == 1
        f = xml_files[0]

        # Parse and validate the XML
        root = etree.parse(f)
        aa_count = 3  # Three temporal clusters based on file timestamps

        assert (
            root.find(f"/{{{NX_NS}}}title").text
            == "Microstructure analysis of steel alloys"
        )
        assert len(root.findall(f"//{{{NX_NS}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{NX_NS}}}dataset")) == expected_datasets
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation").text
            == "Characterize phase transformations in heat-treated steel"
        )
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument").get("pid")
            == "FEI-Titan-TEM"
        )
        assert len(root.findall(f"//{{{NX_NS}}}sample")) == 1

        # remove record
        f.unlink()

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_new_session_bad_upload(
        self,
        monkeypatch,
        caplog,
    ):
        # Mock build_new_session_records to return dummy files and mock sessions
        # Mock export_records to return failed results
        dummy_files = [Path("dummy_file1"), Path("dummy_file2"), Path("dummy_file3")]

        # Create mock Session objects with required attributes
        from unittest.mock import Mock

        dummy_sessions = []
        for i in range(3):
            mock_session = Mock(spec=Session)
            mock_session.session_identifier = f"dummy_session_{i}"
            dummy_sessions.append(mock_session)

        monkeypatch.setattr(
            record_builder,
            "build_new_session_records",
            lambda: (dummy_files, dummy_sessions),
        )
        monkeypatch.setattr(record_builder, "export_records", _mock_failed_export)

        record_builder.process_new_records(
            dt_from=dt.fromisoformat("2021-08-01T13:00:00-06:00"),
            dt_to=dt.fromisoformat("2021-09-05T20:00:00-06:00"),
        )
        assert "Some record files were not exported:" in caplog.text

    def test_build_record_error(self, monkeypatch, caplog, skip_preview_generation):
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
        skip_preview_generation,
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
    def test_dump_record(self, test_record_files, monkeypatch):
        dt_str_from = "2021-08-02T09:00:00-07:00"
        dt_str_to = "2021-08-02T11:00:00-07:00"
        session = Session(
            session_identifier="an-identifier-string",
            instrument=make_test_tool(),
            dt_range=(dt.fromisoformat(dt_str_from), dt.fromisoformat(dt_str_to)),
            user="unused",
        )
        # Skip preview generation to speed up test
        monkeypatch.setattr(
            record_builder,
            "build_record",
            partial(build_record, generate_previews=False),
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
        skip_preview_generation,
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
        xml_files, _ = record_builder.build_new_session_records()

        # Query session logs using SQLModel
        with DBSession(get_engine()) as db_session:
            statement = select(SessionLog).where(
                SessionLog.session_identifier == "test_session"
            )
            logs = db_session.exec(statement).all()

        assert len(logs) >= 1
        # All logs should have NO_CONSENT status
        for log in logs:
            assert log.record_status == RecordStatus.NO_CONSENT
        assert "Reservation requested not to have their data harvested" in caplog.text
        assert len(xml_files) == 0  # no record should be returned

    @pytest.mark.usefixtures("mock_nemo_reservation", "skip_preview_generation")
    def test_build_record_single_file(self, test_record_files, monkeypatch):
        """Test record builder with a narrow time window that captures only 1 file."""

        # Use TEST-TOOL from database with narrow time window
        # Files are at: 17:00, 17:15, 17:30, 17:45 UTC (10:00, 10:15, 10:30, 10:45 PDT)
        # This window captures only sample_002.dm3 at 17:15 UTC
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            test_instr = next(
                s for s in all_sessions if s.instrument.name == "TEST-TOOL"
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

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "export_records", _mock_successful_export)

        xml_files, _ = record_builder.build_new_session_records()
        assert len(xml_files) == 1

        aa_count = 1
        dataset_count = 1

        f = xml_files[0]
        root = etree.parse(f)

        # Verify it used the mock_nemo_reservation data for TEST-TOOL
        assert (
            root.find(f"/{{{NX_NS}}}title").text
            == "EDX spectroscopy of platinum-nickel alloys"
        )
        assert len(root.findall(f"//{{{NX_NS}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{NX_NS}}}dataset")) == dataset_count
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation").text
            == "Determine composition of Pt-Ni alloy samples"
        )
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument").get("pid")
            == "TEST-TOOL"
        )

        # remove record
        f.unlink()

    def test_build_record_with_sample_elements(
        self,
        test_record_files,
        monkeypatch,
        skip_preview_generation,
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
        # Filter to get just the TEST-TOOL session
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            return [s for s in all_sessions if s.instrument.name == "TEST-TOOL"]

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)

        # Mock export_records to return successful results
        monkeypatch.setattr(record_builder, "export_records", _mock_successful_export)

        # override preview generation to save time
        monkeypatch.setattr(
            record_builder,
            "build_record",
            partial(build_record, generate_previews=False),
        )

        xml_files, _ = record_builder.build_new_session_records()

        aa_count = 1
        dataset_count = 4
        sample_count = 3

        assert len(xml_files) == 1
        f = xml_files[0]
        root = etree.parse(f)

        assert (
            root.find(f"/{{{NX_NS}}}title").text
            == "Test reservation for multiple samples, some with elements, some not"
        )
        assert len(root.findall(f"//{{{NX_NS}}}acquisitionActivity")) == aa_count
        assert len(root.findall(f"//{{{NX_NS}}}dataset")) == dataset_count
        assert root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}motivation").text == "testing"
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument").get("pid")
            == "TEST-TOOL"
        )
        assert len(root.findall(f"//{{{NX_NS}}}sample")) == sample_count

        # test sample element tags
        expected = [
            None,
            [
                f"{{{NX_NS}}}S",
                f"{{{NX_NS}}}Rb",
                f"{{{NX_NS}}}Sb",
                f"{{{NX_NS}}}Re",
                f"{{{NX_NS}}}Cm",
            ],
            [f"{{{NX_NS}}}Ir"],
        ]
        sample_elements = root.findall(f"//{{{NX_NS}}}sample")
        for exp, element in zip(expected, sample_elements):
            this_element = element.find(f"{{{NX_NS}}}elements")
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

    @pytest.mark.usefixtures("mock_nemo_reservation")
    def test_process_new_records_multi_signal(
        self,
        multi_signal_test_files,
        skip_preview_generation,
        monkeypatch,
    ):
        """Test record builder with multi-signal microscopy files.

        Tests processing of multi-signal data including:
        - Gatan DM4 spectrum image with multiple signals (NEOARM_GATAN_SI) -- 4 signals
        - DM3 file with list of signals (LIST_SIGNAL) -- 2 signals
        - Single STEM image file (test_STEM_image.dm3) -- 1 signal

        Files are in the TEST-TOOL instrument directory with
        mtimes set to 2025-06-15 03:00-03:30 UTC (21:00-21:30 MDT on 2025-06-14).
        """

        # Create a custom session that captures all three multi-signal files
        # Session window: 2025-06-14 20:00 MDT - 2025-06-15 22:00 MDT
        # (2025-06-15 02:00 UTC - 2025-06-16 04:00 UTC)
        def mock_get_sessions():
            all_sessions = session_handler.get_sessions_to_build()
            test_instr = next(
                s for s in all_sessions if s.instrument.name == "TEST-TOOL"
            )
            # Return a session with a custom time window for multi-signal files
            return [
                session_handler.Session(
                    session_identifier=test_instr.session_identifier,
                    instrument=test_instr.instrument,
                    dt_range=(
                        dt.fromisoformat("2025-06-15T02:00:00+00:00"),
                        dt.fromisoformat("2025-06-16T04:00:00+00:00"),
                    ),
                    user="test_user",
                ),
            ]

        monkeypatch.setattr(record_builder, "get_sessions_to_build", mock_get_sessions)
        monkeypatch.setattr(record_builder, "export_records", _mock_successful_export)

        xml_files, _ = record_builder.build_new_session_records()
        assert len(xml_files) == 1

        f = xml_files[0]
        root = etree.parse(f)

        # Verify the XML record was generated with title from mock reservation
        assert (
            root.find(f"/{{{NX_NS}}}title").text
            == "EDX spectroscopy of platinum-nickel alloys"
        )

        # Check that we have acquisition activities and datasets
        acquisition_activities = root.findall(f"//{{{NX_NS}}}acquisitionActivity")
        datasets = root.findall(f"//{{{NX_NS}}}dataset")

        assert len(acquisition_activities) == 1

        # should be 4 from neoarm gatan, 2 from TEM_list signal,
        # and one from test_STEM_image.dm3
        assert len(datasets) == 7, f"Expected at 7 datasets, got {len(datasets)}"

        # Verify the datasets correspond to our multi-signal files
        dataset_names = [ds.find(f"{{{NX_NS}}}name").text for ds in datasets]
        assert any("neoarm" in name.lower() for name in dataset_names), (
            f"Expected neoarm file in datasets: {dataset_names}"
        )
        assert any(
            "list_signal" in name.lower() or "tem" in name.lower()
            for name in dataset_names
        ), f"Expected TEM signal file in datasets: {dataset_names}"

        # Verify that multi-signal files have unique dataset names with signal indices
        # NEOARM DM4 should have 4 datasets with names like "(1 of 4)", "(2 of 4)"...
        neoarm_names = [name for name in dataset_names if "neoarm" in name.lower()]
        assert len(neoarm_names) == 4, (
            f"Expected 4 neoarm dataset names, got {len(neoarm_names)}: {neoarm_names}"
        )
        # Verify signal indices are in order
        for i, name in enumerate(neoarm_names, start=1):
            assert name.endswith(f"({i} of 4)"), (
                f"Expected neoarm name {i} to end with '({i} of 4)', got: {name}"
            )

        # Verify that 4 different JSON metadata files were created for neoarm signals
        import json

        from nexusLIMS.config import settings

        neoarm_json_files = []
        data_path = Path(settings.NX_DATA_PATH)
        multi_signal_dir = data_path / "Nexus_Test_Instrument" / "multi_signal_data"

        for i in range(4):
            json_file = (
                multi_signal_dir / f"neoarm-gatan_SI_dataZeroed.dm4_signal{i}.json"
            )
            assert json_file.exists(), (
                f"Expected JSON metadata for neoarm signal {i} not found: {json_file}"
            )
            # Verify it's valid JSON
            with json_file.open() as json_fh:
                metadata = json.load(json_fh)
            assert "nx_meta" in metadata, f"Invalid JSON structure in {json_file}"
            neoarm_json_files.append(json_file)

        assert len(neoarm_json_files) == 4, (
            f"Expected 4 JSON metadata files for neoarm, got {len(neoarm_json_files)}"
        )

        # Verify instrument information
        assert (
            root.find(f"/{{{NX_NS}}}summary/{{{NX_NS}}}instrument").get("pid")
            == "TEST-TOOL"
        )

        # Remove record
        f.unlink()
