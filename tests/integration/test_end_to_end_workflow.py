# ruff: noqa: T201
"""
End-to-end workflow integration tests for NexusLIMS.

This module tests the complete workflow from NEMO usage events through record
building to CDCS upload, verifying that all components work together correctly.
"""

from datetime import timedelta

import pytest
from lxml import etree
from sqlmodel import Session as DBSession
from sqlmodel import select

from nexusLIMS.builder import record_builder
from nexusLIMS.db.engine import get_engine
from nexusLIMS.db.enums import EventType, RecordStatus
from nexusLIMS.db.models import SessionLog
from tests.integration.conftest import (
    _get_metadata_urls_for_datasets,
    _verify_json_metadata_accessible,
    _verify_url_accessible,
)

# test_environment_setup fixture is now defined in conftest.py


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows from NEMO to CDCS."""

    def test_complete_record_building_workflow(  # noqa: PLR0915
        self,
        test_environment_setup,
    ):
        """
        Test complete workflow using process_new_records().

        NEMO Usage Event → NEMO Reservation → Session → Files → Record →
        CDCS upload

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

        **Test Record Composition:**
        The example record contains files from multiple instruments (currently
        Titan TEM and Orion HIM), which are clustered into separate
        acquisitionActivity elements based on temporal analysis. This test does
        NOT validate instrument-specific metadata parsing; it focuses on the
        end-to-end workflow and proper XML generation/upload. Instrument-specific
        parsing is tested in unit tests (see tests/unit/test_extractors/).

        Parameters
        ----------
        test_environment_setup : dict
            Test environment configuration (includes nemo_connector, cdcs_client,
            database, extracted_test_files, and session timespan via fixture
            dependencies)
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
        count = len(sessions_after)
        assert count == 0, (
            f"All sessions should be completed, but {count} remain TO_BE_BUILT"
        )

        # Verify database has correct session log entries
        # Should have 3 COMPLETED entries: START, END, and RECORD_GENERATION
        with DBSession(get_engine()) as db_session:
            all_sessions = db_session.exec(
                select(SessionLog.event_type, SessionLog.record_status).order_by(
                    SessionLog.session_identifier, SessionLog.event_type
                )
            ).all()

        completed_sessions = [s for s in all_sessions if s[1] == RecordStatus.COMPLETED]
        count = len(completed_sessions)
        assert count == 3, f"Expected 3 COMPLETED sessions, got {count}"

        events = {s[0] for s in completed_sessions}
        assert events == {
            EventType.START,
            EventType.END,
            EventType.RECORD_GENERATION,
        }, f"Expected START, END, and RECORD_GENERATION events, got {events}"

        # Verify that XML records were written to disk and moved to uploaded/
        uploaded_dir = settings.records_dir_path / "uploaded"
        assert uploaded_dir.exists(), f"Uploaded directory not found: {uploaded_dir}"

        uploaded_records = list(uploaded_dir.glob("*.xml"))
        assert len(uploaded_records) == 1, "No records were uploaded"

        # Read and validate one of the uploaded records
        test_record = uploaded_records[0]
        record_title = test_record.stem

        with test_record.open(encoding="utf-8") as f:
            xml_string = f.read()

        # Validate XML against schema
        schema_doc = etree.parse(str(record_builder.XSD_PATH))
        schema = etree.XMLSchema(schema_doc)
        xml_doc = etree.fromstring(xml_string.encode())

        is_valid = schema.validate(xml_doc)
        if not is_valid:
            errors = "\n".join(str(e) for e in schema.error_log)
            msg = f"XML validation failed:\n{errors}"
            raise AssertionError(msg)

        # Verify XML content structure
        assert xml_doc.tag.endswith("Experiment"), "Root element is not Experiment"
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"

        summary = xml_doc.find(f"{nx_ns}summary")
        assert summary is not None, "No Summary element found"

        activities = xml_doc.findall(f"{nx_ns}acquisitionActivity")
        assert len(activities) == 2, "Expected to find 2 acquisitionActivity elements"

        datasets = xml_doc.findall(f"{nx_ns}acquisitionActivity/{nx_ns}dataset")
        assert len(datasets) == 13, (
            "Expected to find 13 dataset elements (including Tescan image)"
        )

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

        # verify number of expected activities for default setting
        activities = downloaded_doc.findall(f".//{nx_ns}acquisitionActivity")
        assert len(activities) == 2, (
            "Did not find expected number of activities with default clustering"
        )

        # Verify fileserver URLs are accessible
        # Extract dataset location and preview URLs from the downloaded XML
        import requests

        # Find a dataset with a location
        dataset_locations = downloaded_doc.findall(f".//{nx_ns}dataset/{nx_ns}location")
        assert len(dataset_locations) > 0, "No dataset locations found in XML"

        # Test accessing a dataset file via fileserver
        dataset_location = dataset_locations[0].text
        # Location is relative path like "/path/to/data/file.dm3"
        # Convert to fileserver URL
        # The XML should contain the full path from NX_INSTRUMENT_DATA_PATH
        dataset_url = (
            f"http://fileserver.localhost:40080/instrument-data{dataset_location}"
        )

        print(f"\n[*] Testing fileserver access to dataset: {dataset_url}")
        dataset_response = requests.get(dataset_url, timeout=10)
        assert dataset_response.status_code == 200, (
            f"Failed to access dataset via fileserver: {dataset_response.status_code}"
        )
        assert len(dataset_response.content) > 0, "Dataset file is empty"
        size = len(dataset_response.content)
        print(f"[+] Successfully accessed dataset file ({size} bytes)")

        # Find a preview image URL (these are in <preview> elements)
        preview_elements = downloaded_doc.findall(f".//{nx_ns}dataset/{nx_ns}preview")
        if len(preview_elements) > 0:
            preview_path = preview_elements[0].text
            # Preview paths are relative to NX_DATA_PATH
            # Convert to fileserver URL using /data/ prefix
            preview_url = f"http://fileserver.localhost:40080/data{preview_path}"
            print(f"\n[*] Testing fileserver access to preview: {preview_url}")

            preview_response = requests.get(preview_url, timeout=10)
            assert preview_response.status_code == 200, (
                f"Failed to access preview via fileserver: "
                f"{preview_response.status_code}"
            )
            assert len(preview_response.content) > 0, "Preview file is empty"
            # Verify it's an image (PNG/JPG or image content type)
            content_type = preview_response.headers.get("Content-Type", "")
            is_image_type = "image" in content_type
            is_image_ext = preview_url.endswith((".png", ".jpg", ".jpeg"))
            assert is_image_type or is_image_ext, (
                f"Preview doesn't appear to be an image: {content_type}"
            )
            size = len(preview_response.content)
            print(f"[+] Successfully accessed preview image ({size} bytes)")
        else:
            print("[!] No preview elements found in XML (this may be expected)")

        # clean up uploaded record on success
        cdcs_module.delete_record(record_id)
        with pytest.raises(ValueError, match=f"Record with id {record_id} not found"):
            cdcs_module.download_record(record_id)

    # ========================================================================
    # Clustering sensitivity end to end tests
    # ========================================================================

    @pytest.mark.integration
    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_clustering_sensitivity_disabled(
        self,
        test_environment_setup,
        monkeypatch,
    ):
        """
        Test that NX_CLUSTERING_SENSITIVITY=0 disables file clustering.

        When clustering sensitivity is set to 0, all files should be grouped
        into a single acquisition activity regardless of their temporal
        distribution. This test verifies that the configuration is properly
        applied during record building.

        The default condition for this record produces 2 activities, and
        is tested in ``test_complete_record_building_workflow()``
        """
        import nexusLIMS.cdcs as cdcs_module
        from nexusLIMS.config import refresh_settings, settings

        # disable clustering to put all datasets in one activity
        monkeypatch.setenv("NX_CLUSTERING_SENSITIVITY", str(0))
        refresh_settings()

        # process record with default sensitivity
        record_builder.process_new_records(
            dt_from=test_environment_setup["dt_from"] - timedelta(hours=1),
            dt_to=test_environment_setup["dt_to"] + timedelta(hours=1),
        )

        uploaded_dir = settings.records_dir_path / "uploaded"
        uploaded_records = list(uploaded_dir.glob("*.xml"))
        test_record = uploaded_records[0]
        record_title = test_record.stem

        # this is not reliable if generating the same record twice
        search_results = cdcs_module.search_records(title=record_title)

        cdcs_record = search_results[0]
        record_id = cdcs_record["id"]

        # Download the record from CDCS and verify it matches
        downloaded_xml = cdcs_module.download_record(record_id)
        downloaded_doc = etree.fromstring(downloaded_xml.encode())
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"
        activities = downloaded_doc.findall(f".//{nx_ns}acquisitionActivity")
        assert len(activities) == 1, (
            "Did not find expected number of activities with default clustering"
        )

    @pytest.mark.integration
    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_clustering_high_sensitivity(
        self,
        test_environment_setup,
        monkeypatch,
    ):
        """
        Test that NX_CLUSTERING_SENSITIVITY=30 results in many activities.

        The default condition for this record produces 2 activities, and
        is tested in ``test_complete_record_building_workflow()``
        """
        import nexusLIMS.cdcs as cdcs_module
        from nexusLIMS.config import refresh_settings, settings

        # high sensitivity should result in more activities (6, tested empirically)
        monkeypatch.setenv("NX_CLUSTERING_SENSITIVITY", str(50))
        refresh_settings()

        # process record with default sensitivity
        record_builder.process_new_records(
            dt_from=test_environment_setup["dt_from"] - timedelta(hours=1),
            dt_to=test_environment_setup["dt_to"] + timedelta(hours=1),
        )

        uploaded_dir = settings.records_dir_path / "uploaded"
        uploaded_records = list(uploaded_dir.glob("*.xml"))
        test_record = uploaded_records[0]
        record_title = test_record.stem

        # this is not reliable if generating the same record twice
        search_results = cdcs_module.search_records(title=record_title)

        cdcs_record = search_results[0]
        record_id = cdcs_record["id"]

        # Download the record from CDCS and verify it matches
        downloaded_xml = cdcs_module.download_record(record_id)
        downloaded_doc = etree.fromstring(downloaded_xml.encode())
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"
        activities = downloaded_doc.findall(f".//{nx_ns}acquisitionActivity")
        assert len(activities) == 6, (
            "Did not find expected number of activities with default clustering"
        )

    # ========================================================================
    # Multi-signal workflow tests
    # ========================================================================

    @pytest.mark.integration
    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_multi_signal_record_generation_and_structure(
        self,
        multi_signal_integration_record,
    ):
        """
        Test multi-signal file handling in record generation and XML structure.

        This test verifies that multi-signal files (files containing multiple
        signals/datasets extracted from a single file) are properly handled:
        1. Each signal gets a unique dataset name with index: "filename.ext (X of Y)"
        2. Multi-signal files share one source file location
        3. Each signal gets its own preview image
        4. XML record is valid against schema

        Files tested:
        - neoarm-gatan_SI_dataZeroed.dm4: Spectrum image with 4 signals
        - TEM_list_signal_dataZeroed.dm3: File with list of 2 signals
        - test_STEM_image.dm3: Single STEM image (control)

        Parameters
        ----------
        multi_signal_integration_record : dict
            Fixture providing the generated XML and metadata
        """
        xml_doc = multi_signal_integration_record["xml_doc"]
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"

        # Verify XML structure
        assert xml_doc.tag.endswith("Experiment"), "Root element is not Experiment"

        summary = xml_doc.find(f"{nx_ns}summary")
        assert summary is not None, "No Summary element found"

        # Verify all datasets are present
        all_datasets = xml_doc.findall(f".//{nx_ns}dataset")
        dataset_names = [ds.find(f"{nx_ns}name").text for ds in all_datasets]

        # The neoarm DM4 should have 4 datasets with signal indices
        neoarm_names = [name for name in dataset_names if "neoarm" in name.lower()]
        assert len(neoarm_names) == 4, (
            f"Expected 4 neoarm dataset names, got {len(neoarm_names)}: {neoarm_names}"
        )

        # Verify signal indices are in order and properly formatted
        for i, name in enumerate(neoarm_names, start=1):
            assert name.endswith(f"({i} of 4)"), (
                f"Expected neoarm name {i} to end with '({i} of 4)', got: {name}"
            )

        # Verify multi-signal handling: 4 previews, 1 shared file location
        neoarm_datasets = [
            ds
            for ds in all_datasets
            if "neoarm" in ds.find(f"{nx_ns}name").text.lower()
        ]
        assert len(neoarm_datasets) == 4, (
            f"Expected 4 neoarm datasets, got {len(neoarm_datasets)}"
        )

        # Collect preview paths and file locations
        neoarm_preview_paths = set()
        neoarm_file_locations = set()

        for dataset in neoarm_datasets:
            location_el = dataset.find(f"{nx_ns}location")
            if location_el is not None:
                neoarm_file_locations.add(location_el.text)

            preview_el = dataset.find(f"{nx_ns}preview")
            if preview_el is not None:
                neoarm_preview_paths.add(preview_el.text)

        # Verify 4 different preview images
        assert len(neoarm_preview_paths) == 4, (
            f"Expected 4 different neoarm preview images, got "
            f"{len(neoarm_preview_paths)}: {neoarm_preview_paths}"
        )

        # Verify 1 shared file location
        assert len(neoarm_file_locations) == 1, (
            f"Expected 1 shared file location for all 4 neoarm signals, got "
            f"{len(neoarm_file_locations)}: {neoarm_file_locations}"
        )

        # Verify all datasets have required elements
        for dataset in all_datasets:
            name_el = dataset.find(f"{nx_ns}name")
            assert name_el is not None, "Dataset missing name element"
            assert name_el.text, "Dataset name is empty"

            location_el = dataset.find(f"{nx_ns}location")
            assert location_el is not None, "Dataset missing location element"

    @pytest.mark.integration
    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_multi_signal_cdcs_integration(
        self,
        multi_signal_integration_record,
    ):
        """
        Test multi-signal record upload to and retrieval from CDCS.

        This test verifies that:
        1. Multi-signal records upload successfully to CDCS
        2. Records can be searched and found by title
        3. Records can be downloaded from CDCS
        4. Downloaded XML is valid against schema

        Parameters
        ----------
        multi_signal_integration_record : dict
            Fixture providing the generated XML and metadata
        """
        import nexusLIMS.cdcs as cdcs_module
        from nexusLIMS.builder import record_builder

        record_title = multi_signal_integration_record["record_title"]
        record_id = multi_signal_integration_record["record_id"]

        # Verify record is present in CDCS
        search_results = cdcs_module.search_records(title=record_title)
        assert len(search_results) > 0, f"Record '{record_title}' not found in CDCS"

        cdcs_record = search_results[0]
        assert cdcs_record["id"] == record_id, "Record ID mismatch"

        # Download the record from CDCS
        downloaded_xml = cdcs_module.download_record(record_id)
        assert len(downloaded_xml) > 0, "Downloaded XML is empty"

        # Verify downloaded XML is valid against schema
        schema_doc = etree.parse(str(record_builder.XSD_PATH))
        schema = etree.XMLSchema(schema_doc)
        downloaded_doc = etree.fromstring(downloaded_xml.encode())

        is_valid = schema.validate(downloaded_doc)
        assert is_valid, (
            f"Downloaded XML from CDCS is not valid against schema: {schema.error_log}"
        )

    @pytest.mark.integration
    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_multi_signal_fileserver_accessibility(
        self,
        multi_signal_integration_record,
    ):
        """
        Test fileserver accessibility for multi-signal record artifacts.

        This test verifies that all files referenced in the multi-signal record
        are accessible via the fileserver:
        1. Original dataset files (instrument-data URLs)
        2. JSON metadata files (data URLs with .json extension)
        3. Preview images (data URLs)

        Parameters
        ----------
        multi_signal_integration_record : dict
            Fixture providing the generated XML and metadata
        """
        xml_doc = multi_signal_integration_record["xml_doc"]
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"

        print("\n[*] Verifying fileserver accessibility for multi-signal record...")

        # Test dataset file accessibility
        dataset_locations = xml_doc.findall(f".//{nx_ns}dataset/{nx_ns}location")
        assert len(dataset_locations) == 7, (
            "Unexpected number of dataset locations found in XML"
        )

        print(f"\n[*] Testing access to {len(dataset_locations)} dataset files...")
        for i, location_el in enumerate(dataset_locations, 1):
            dataset_location = location_el.text
            dataset_url = (
                f"http://fileserver.localhost:40080/instrument-data{dataset_location}"
            )
            _verify_url_accessible(dataset_url, i, len(dataset_locations))

        print(f"[+] Successfully accessed {len(dataset_locations)} dataset files")

        # Test JSON metadata file accessibility
        print("\n[*] Testing access to JSON metadata files...")
        metadata_urls = _get_metadata_urls_for_datasets(xml_doc, nx_ns)

        for i, metadata_url in enumerate(metadata_urls, 1):
            _verify_json_metadata_accessible(metadata_url, i, len(metadata_urls))

        print(f"[+] Successfully accessed {len(metadata_urls)} JSON metadata files")

        # Test preview image accessibility
        preview_elements = xml_doc.findall(f".//{nx_ns}dataset/{nx_ns}preview")
        if len(preview_elements) > 0:
            print(f"\n[*] Testing access to {len(preview_elements)} preview images...")
            for i, preview_el in enumerate(preview_elements, 1):
                preview_path = preview_el.text
                preview_url = f"http://fileserver.localhost:40080/data{preview_path}"
                _verify_url_accessible(
                    preview_url, i, len(preview_elements), expected_type="image"
                )

            print(f"[+] Successfully accessed {len(preview_elements)} preview images")

        print("\n[+] All fileserver accessibility checks passed")
