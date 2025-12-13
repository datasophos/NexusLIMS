"""
End-to-end workflow integration tests for NexusLIMS.

This module tests the complete workflow from NEMO usage events through record
building to CDCS upload, verifying that all components work together correctly.
"""

import shutil
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from lxml import etree

from nexusLIMS.builder import record_builder
from nexusLIMS.db.session_handler import Session, db_query
from nexusLIMS.harvesters.nemo import utils as nemo_utils

# Test data archive location
TEST_RECORD_FILES_ARCHIVE = (
    Path(__file__).parents[1] / "unit/files/test_record_files.tar.gz"
)


@pytest.fixture
def extracted_test_files(tmp_path, test_data_dirs):
    """
    Extract test_record_files.tar.gz to test instrument data directory.

    This fixture extracts the test record files archive to the temporary
    test instrument data directory, making them available for end-to-end
    record building tests.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory fixture

    Yields
    ------
    dict
        Dictionary with paths and metadata:
        - 'base_dir': Base directory where files were extracted
        - 'titan_dir': Path to Titan_TEM instrument directory
        - 'jeol_dir': Path to JEOL_TEM instrument directory
        - 'titan_date': Expected date for Titan files (2018-11-13)
        - 'jeol_date': Expected date for JEOL files (2019-07-24)
    """
    from nexusLIMS.config import settings

    # Get the test instrument data directory from settings
    instrument_data_dir = Path(settings.NX_INSTRUMENT_DATA_PATH)
    nx_data_dir = Path(settings.NX_DATA_PATH)

    # Extract archive to instrument data directory and track what was extracted
    print(f"\n[*] Extracting test files to {instrument_data_dir}")
    extracted_top_level_dirs = []

    with tarfile.open(TEST_RECORD_FILES_ARCHIVE, "r:gz") as tar:
        # Get list of top-level directories that will be extracted
        for member in tar.getmembers():
            if member.isdir():
                top_level = member.name.split("/")[0]
                if top_level not in extracted_top_level_dirs:
                    extracted_top_level_dirs.append(top_level)

        tar.extractall(instrument_data_dir)

    print(f"[+] Top-level directories extracted: {extracted_top_level_dirs}")

    # Dates from the archive structure (Titan: 20181113, JEOL: 20190724)
    titan_date = datetime(2018, 11, 13)
    jeol_date = datetime(2019, 7, 24)

    yield {
        "base_dir": instrument_data_dir,
        "titan_date": titan_date,
        "jeol_date": jeol_date,
    }

    # # Cleanup: Remove extracted directories from both instrument data and NX_DATA_PATH
    # print("\n[*] Cleaning up extracted test files and generated metadata")
    # for dir_name in extracted_top_level_dirs:
    #     # Clean up source files in instrument data directory
    #     source_dir = instrument_data_dir / dir_name
    #     if source_dir.exists():
    #         print(f"[*] Removing {source_dir}")
    #         shutil.rmtree(source_dir)

    #     # Clean up generated metadata in NX_DATA_PATH
    #     metadata_dir = nx_data_dir / dir_name
    #     if metadata_dir.exists():
    #         print(f"[*] Removing generated metadata {metadata_dir}")
    #         shutil.rmtree(metadata_dir)


@pytest.fixture
def test_environment_setup(
    nemo_connector, populated_test_database, extracted_test_files, monkeypatch
):
    """
    Set up the test environment for end-to-end workflow testing.

    This fixture configures the environment so that process_new_records()
    can run naturally, including NEMO harvesting. It does NOT create sessions
    directly - that's left to the NEMO harvester to do.

    Parameters
    ----------
    nemo_connector : NemoConnector
        Configured NEMO connector from fixture (already mocked to return test usage events)
    populated_test_database : Path
        Test database with instruments
    extracted_test_files : dict
        Extracted test files information
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    dict
        Test environment information:
        - 'instrument_pid': Instrument PID to use for testing
        - 'dt_from': Expected session start datetime
        - 'dt_to': Expected session end datetime
        - 'user': Expected username
        - 'instrument_db': Test instrument database
    """
    from nexusLIMS import instruments
    from nexusLIMS.config import refresh_settings

    # Patch settings to use test database
    monkeypatch.setenv("NX_DB_PATH", str(populated_test_database))
    refresh_settings()

    # Patch the instrument_db to use test database
    test_instrument_db = instruments._get_instrument_db(db_path=populated_test_database)
    monkeypatch.setattr(instruments, "instrument_db", test_instrument_db)

    # Get Titan instrument from test database (should be FEI-Titan-TEM)
    instrument = test_instrument_db["FEI-Titan-TEM"]

    # Reload instrument database to pick up the change
    test_instrument_db = instruments._get_instrument_db(db_path=populated_test_database)
    instrument = test_instrument_db["FEI-Titan-TEM"]

    # Create expected session timespan that covers the test files
    # Files are dated 2018-11-13, so expect a session around that time
    # (the nemo_connector fixture should already be configured to return this)
    session_start = extracted_test_files["titan_date"].replace(
        hour=4, minute=0, second=0
    )
    session_end = session_start + timedelta(hours=12)

    print(f"\n[+] Test environment configured")
    print(f"    Instrument: {instrument.name}")
    print(f"    Expected session time: {session_start} to {session_end}")
    print(f"    Expected user: captain")

    return {
        "instrument_pid": instrument.name,  # instrument.name is the PID
        "dt_from": session_start,
        "dt_to": session_end,
        "user": "captain",
        "instrument_db": test_instrument_db,
    }


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows from NEMO to CDCS."""

    def test_complete_record_building_workflow(
        self,
        docker_services_running,
        nemo_connector,
        cdcs_client,
        populated_test_database,
        extracted_test_files,
        test_environment_setup,
        monkeypatch,
    ):
        """
        Test complete workflow using process_new_records().

        NEMO Usage Event → NEMO Reservation → Session → Files → Record → CDCS upload

        This is the most critical integration test. It verifies that:
        1. NEMO harvester detects usage events via add_all_usage_events_to_db()
        2. Sessions are created and stored in database with TO_BE_BUILT status
        3. Files are found based on session timespan
        4. Metadata is extracted from files
        5. XML record is generated and valid
        6. Record is uploaded to CDCS
        7. Session status transitions from TO_BE_BUILT to COMPLETED

        This test calls process_new_records() directly, which exercises the
        complete production code path.

        Parameters
        ----------
        docker_services_running : dict
            Docker services status
        nemo_connector : NemoConnector
            NEMO connector fixture (mocked to return test usage events)
        cdcs_client : dict
            CDCS client configuration
        populated_test_database : Path
            Test database with instruments
        extracted_test_files : dict
            Extracted test files
        test_environment_setup : dict
            Test environment configuration
        monkeypatch : pytest.MonkeyPatch
            Pytest monkeypatch fixture
        """
        from nexusLIMS.config import settings
        from nexusLIMS.db.session_handler import get_sessions_to_build

        # Verify no sessions exist before harvesting
        sessions_before = get_sessions_to_build()
        assert len(sessions_before) == 0, "Database should be empty before harvesting"

        # Run process_new_records() - This does the entire workflow:
        # 1. Harvest NEMO usage events via add_all_usage_events_to_db()
        # 2. Find files for each session
        # 3. Extract metadata from files
        # 4. Build XML records
        # 5. Validate XML against schema
        # 6. Upload records to CDCS
        # 7. Update session status to COMPLETED
        record_builder.process_new_records(
            dt_from=test_environment_setup["dt_from"] - timedelta(hours=1),
            dt_to=test_environment_setup["dt_to"] + timedelta(hours=1),
        )

        # Verify that sessions were created and then completed
        sessions_after = get_sessions_to_build()
        assert len(sessions_after) == 0, (
            f"All sessions should be completed, but {len(sessions_after)} remain TO_BE_BUILT"
        )

        # Verify database has correct session log entries
        # Should have 3 COMPLETED entries: START, END, and RECORD_GENERATION
        success, all_sessions = db_query(
            "SELECT event_type, record_status FROM session_log ORDER BY session_identifier, event_type"
        )

        completed_sessions = [s for s in all_sessions if s[1] == "COMPLETED"]
        assert len(completed_sessions) == 3, (
            f"Expected 3 COMPLETED sessions (START, END, RECORD_GENERATION), got {len(completed_sessions)}"
        )

        events = {s[0] for s in completed_sessions}
        assert events == {
            "START",
            "END",
            "RECORD_GENERATION",
        }, f"Expected START, END, and RECORD_GENERATION events, got {events}"

        # Verify that XML records were written to disk and moved to uploaded/
        uploaded_dir = settings.records_dir_path / "uploaded"
        assert uploaded_dir.exists(), f"Uploaded directory not found: {uploaded_dir}"

        uploaded_records = list(uploaded_dir.glob("*.xml"))
        assert len(uploaded_records) == 1, "No records were uploaded"

        # Read and validate one of the uploaded records
        test_record = uploaded_records[0]
        record_title = test_record.stem

        with open(test_record, "r", encoding="utf-8") as f:
            xml_string = f.read()

        # Validate XML against schema
        schema_doc = etree.parse(str(record_builder.XSD_PATH))
        schema = etree.XMLSchema(schema_doc)
        xml_doc = etree.fromstring(xml_string.encode())

        is_valid = schema.validate(xml_doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in schema.error_log)
            raise AssertionError(f"XML validation failed:\n{errors}")

        # Verify XML content structure
        assert xml_doc.tag.endswith("Experiment"), "Root element is not Experiment"
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"

        summary = xml_doc.find(f"{nx_ns}summary")
        assert summary is not None, "No Summary element found"

        activities = xml_doc.findall(f"{nx_ns}acquisitionActivity")
        assert len(activities) == 2, "Expected to find 2 acquisitionActivity elements"

        datasets = xml_doc.findall(f"{nx_ns}acquisitionActivity/{nx_ns}dataset")
        assert len(datasets) == 10, "Expected to find 10 dataset elements"

        # Verify record is present in CDCS via API
        import nexusLIMS.cdcs as cdcs_module

        search_results = cdcs_module.search_records(title=record_title)
        assert len(search_results) > 0, f"Record '{record_title}' not found in CDCS"

        cdcs_record = search_results[0]
        record_id = cdcs_record["id"]

        # Download the record from CDCS and verify it matches
        downloaded_xml = cdcs_module.download_record(record_id)
        assert len(downloaded_xml) > 0, "Downloaded XML is empty"

        # Verify downloaded XML is also valid
        downloaded_doc = etree.fromstring(downloaded_xml.encode())
        is_valid_download = schema.validate(downloaded_doc)
        assert is_valid_download, "Downloaded XML from CDCS is not valid against schema"

        # clean up uploaded record on success
        cdcs_module.delete_record(record_id)
        with pytest.raises(ValueError, match=f"Record with id {record_id} not found"):
            cdcs_module.download_record(record_id)
