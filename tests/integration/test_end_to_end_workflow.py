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

    def _load_and_validate_uploaded_record(self, settings):
        """Load uploaded XML record and validate against schema.

        Returns
        -------
        tuple
            (record_title, xml_doc, schema) - Record title, parsed XML, and schema
        """
        # Verify that XML records were written to disk and moved to uploaded/
        uploaded_dir = settings.records_dir_path / "uploaded"
        assert uploaded_dir.exists(), f"Uploaded directory not found: {uploaded_dir}"

        uploaded_records = list(uploaded_dir.glob("*.xml"))
        assert len(uploaded_records) == 1, (
            f"Expected 1 record uploaded; saw {len(uploaded_records)}"
        )

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

        return record_title, xml_doc, schema

    def _verify_session_logs(self):
        """Verify session log entries are correct."""
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

    def _verify_xml_structure(self, xml_doc, nx_ns):
        """Verify XML content structure is correct."""
        assert xml_doc.tag.endswith("Experiment"), "Root element is not Experiment"

        summary = xml_doc.find(f"{nx_ns}summary")
        assert summary is not None, "No Summary element found"

        activities = xml_doc.findall(f"{nx_ns}acquisitionActivity")
        assert len(activities) == 2, "Expected to find 2 acquisitionActivity elements"

        datasets = xml_doc.findall(f"{nx_ns}acquisitionActivity/{nx_ns}dataset")
        assert len(datasets) == 13, (
            "Expected to find 13 dataset elements (including Tescan image)"
        )

    def _verify_upload_logs(self):
        """Verify upload_log table entries and return record IDs/URLs."""
        from nexusLIMS.db.models import UploadLog

        with DBSession(get_engine()) as db_session:
            upload_logs = db_session.exec(
                select(UploadLog).order_by(UploadLog.destination_name)
            ).all()

        # Should have 2 upload log entries: one for CDCS, one for eLabFTW
        assert len(upload_logs) == 2, (
            f"Expected 2 upload log entries, got {len(upload_logs)}"
        )

        # Verify CDCS upload log
        cdcs_log = [log for log in upload_logs if log.destination_name == "cdcs"]
        assert len(cdcs_log) == 1, "Expected exactly one CDCS upload log entry"
        assert cdcs_log[0].success is True, "CDCS upload should be successful"
        assert cdcs_log[0].record_id is not None, "CDCS log should have record_id"
        assert cdcs_log[0].record_url is not None, "CDCS log should have record_url"
        assert cdcs_log[0].error_message is None, "CDCS log should have no error"

        cdcs_record_id = cdcs_log[0].record_id
        cdcs_record_url = cdcs_log[0].record_url
        print(f"[+] Verified CDCS upload log: record_id={cdcs_record_id}")

        # Verify eLabFTW upload log
        elabftw_log = [log for log in upload_logs if log.destination_name == "elabftw"]
        assert len(elabftw_log) == 1, "Expected exactly one eLabFTW upload log entry"
        assert elabftw_log[0].success is True, "eLabFTW upload should be successful"
        assert elabftw_log[0].record_id is not None, "eLabFTW log should have record_id"
        assert elabftw_log[0].record_url is not None, (
            "eLabFTW log should have record_url"
        )
        assert elabftw_log[0].error_message is None, "eLabFTW log should have no error"

        elabftw_record_id = elabftw_log[0].record_id
        elabftw_record_url = elabftw_log[0].record_url
        print(f"[+] Verified eLabFTW upload log: record_id={elabftw_record_id}")

        return {
            "cdcs_record_id": cdcs_record_id,
            "cdcs_record_url": cdcs_record_url,
            "elabftw_record_id": elabftw_record_id,
            "elabftw_record_url": elabftw_record_url,
        }

    def _verify_cdcs_export(self, cdcs_record_id, schema):
        """Verify CDCS export and return downloaded XML document."""
        from nexusLIMS.utils import cdcs

        print(f"[+] Downloading CDCS record using ID from upload_log: {cdcs_record_id}")

        # Download the record from CDCS and verify it exists
        downloaded_xml = cdcs.download_record(cdcs_record_id)
        assert len(downloaded_xml) > 0, "Downloaded XML is empty"

        # Verify downloaded XML is also valid
        downloaded_doc = etree.fromstring(downloaded_xml.encode())
        is_valid_download = schema.validate(downloaded_doc)
        assert is_valid_download, "Downloaded XML from CDCS is not valid against schema"

        return downloaded_doc

    def _verify_fileserver_access(self, downloaded_doc, nx_ns):
        """Verify fileserver URLs are accessible."""
        import requests

        # Find a dataset with a location
        dataset_locations = downloaded_doc.findall(f".//{nx_ns}dataset/{nx_ns}location")
        assert len(dataset_locations) > 0, "No dataset locations found in XML"

        # Test accessing a dataset file via fileserver
        dataset_location = dataset_locations[0].text
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

    def _verify_elabftw_export(
        self, elabftw_client, elabftw_record_id, cdcs_record_url, record_title
    ):
        """Verify eLabFTW export and cross-link."""
        print("\n[*] Verifying eLabFTW export...")

        # Fetch the experiment using the ID from upload_log
        elabftw_experiment_id = int(elabftw_record_id)
        elabftw_record = elabftw_client.get_experiment(elabftw_experiment_id)

        print(
            f"[+] Successfully fetched eLabFTW experiment: ID {elabftw_experiment_id}"
        )

        # Verify the title contains our record title
        assert record_title in elabftw_record.get("title", ""), (
            f"Expected record title '{record_title}' in eLabFTW experiment title, "
            f"got: {elabftw_record.get('title', '')}"
        )

        # Verify the CDCS URL is in the eLabFTW experiment body
        assert cdcs_record_url in elabftw_record.get("body", ""), (
            f"CDCS record URL not found in eLabFTW experiment body. "
            f"Expected to find: {cdcs_record_url}"
        )
        print("[+] Verified CDCS cross-link in eLabFTW experiment")

        return elabftw_experiment_id

    def _cleanup_exports(self, elabftw_client, elabftw_experiment_id, cdcs_record_id):
        """Clean up exported records from both destinations."""
        from nexusLIMS.utils import cdcs

        print("\n[*] Cleaning up test records...")

        # Delete from eLabFTW
        elabftw_client.delete_experiment(elabftw_experiment_id)
        print(f"[+] Deleted eLabFTW experiment {elabftw_experiment_id}")

        # Delete from CDCS
        cdcs.delete_record(cdcs_record_id)
        with pytest.raises(
            ValueError, match=f"Record with id {cdcs_record_id} not found"
        ):
            cdcs.download_record(cdcs_record_id)
        print(f"[+] Deleted CDCS record {cdcs_record_id}")

    def test_complete_record_building_workflow(
        self,
        test_environment_setup,
        elabftw_client,
    ):
        """
        Test complete workflow using process_new_records().

        NEMO Usage Event → NEMO Reservation → Session → Files → Record →
        CDCS upload → eLabFTW upload

        This is the most critical integration test. It verifies that:
        1. NEMO harvester detects usage events via add_all_usage_events_to_db()
        2. Sessions are created and stored in database with TO_BE_BUILT status
        3. Files are found based on session timespan
        4. Metadata is extracted from files
        5. XML record is generated and valid
        6. Record is uploaded to CDCS
        7. Record is uploaded to eLabFTW
        8. Session status transitions from TO_BE_BUILT to COMPLETED

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

        # Verify session log entries
        self._verify_session_logs()

        # Load and validate uploaded XML record
        record_title, xml_doc, schema = self._load_and_validate_uploaded_record(
            settings
        )

        # Verify XML content structure
        nx_ns = "{https://data.nist.gov/od/dm/nexus/experiment/v1.0}"
        self._verify_xml_structure(xml_doc, nx_ns)

        # Verify upload_log table
        upload_info = self._verify_upload_logs()

        # Verify CDCS export
        downloaded_doc = self._verify_cdcs_export(upload_info["cdcs_record_id"], schema)

        # Verify number of expected activities for default setting
        activities = downloaded_doc.findall(f".//{nx_ns}acquisitionActivity")
        assert len(activities) == 2, (
            "Did not find expected number of activities with default clustering"
        )

        # Verify fileserver URLs are accessible
        self._verify_fileserver_access(downloaded_doc, nx_ns)

        # Verify eLabFTW export and cross-link
        elabftw_experiment_id = self._verify_elabftw_export(
            elabftw_client,
            upload_info["elabftw_record_id"],
            upload_info["cdcs_record_url"],
            record_title,
        )

        # Clean up both destinations
        self._cleanup_exports(
            elabftw_client, elabftw_experiment_id, upload_info["cdcs_record_id"]
        )

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
        from nexusLIMS.config import refresh_settings, settings
        from nexusLIMS.utils import cdcs

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
        search_results = cdcs.search_records(title=record_title)

        cdcs_record = search_results[0]
        record_id = cdcs_record["id"]

        # Download the record from CDCS and verify it matches
        downloaded_xml = cdcs.download_record(record_id)
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
        from nexusLIMS.config import refresh_settings, settings
        from nexusLIMS.utils import cdcs

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
        search_results = cdcs.search_records(title=record_title)

        cdcs_record = search_results[0]
        record_id = cdcs_record["id"]

        # Download the record from CDCS and verify it matches
        downloaded_xml = cdcs.download_record(record_id)
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
        from nexusLIMS.builder import record_builder
        from nexusLIMS.utils import cdcs

        record_title = multi_signal_integration_record["record_title"]
        record_id = multi_signal_integration_record["record_id"]

        # Verify record is present in CDCS
        search_results = cdcs.search_records(title=record_title)
        assert len(search_results) > 0, f"Record '{record_title}' not found in CDCS"

        cdcs_record = search_results[0]
        assert cdcs_record["id"] == record_id, "Record ID mismatch"

        # Download the record from CDCS
        downloaded_xml = cdcs.download_record(record_id)
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

    def test_multi_destination_export(
        self,
        export_context_elabftw,
        elabftw_client,
        test_environment_setup,
        sample_microscopy_files,
    ):
        """
        Test exporting to both CDCS and eLabFTW destinations.

        This test verifies the multi-destination export workflow:
        1. Export a record to both CDCS and eLabFTW
        2. Verify both exports succeed
        3. Verify eLabFTW record includes cross-link to CDCS record

        Note: Both destinations are already configured by fixture dependencies:
        - CDCS: test_environment_setup → cdcs_client
        - eLabFTW: export_context_elabftw

        Parameters
        ----------
        export_context_elabftw : ExportContext
            Export context with pre-configured eLabFTW settings
        elabftw_client : ELabFTWClient
            eLabFTW API client
        test_environment_setup : dict
            Test environment configuration (instrument db, session data)
        sample_microscopy_files : list
            Sample microscopy files (ensures fileserver is populated)
        """
        from nexusLIMS.db.session_handler import Session
        from nexusLIMS.exporters import export_records

        # Export to all destinations
        xml_path = export_context_elabftw.xml_file_path
        instrument = test_environment_setup["instrument_db"][
            test_environment_setup["instrument_pid"]
        ]
        sessions = [
            Session(
                session_identifier=export_context_elabftw.session_identifier,
                instrument=instrument,
                dt_range=(export_context_elabftw.dt_from, export_context_elabftw.dt_to),
                user=export_context_elabftw.user,
            )
        ]

        results = export_records([xml_path], sessions)

        # Verify both destinations succeeded
        cdcs_results = [r for r in results[xml_path] if r.destination_name == "cdcs"]
        elabftw_results = [
            r for r in results[xml_path] if r.destination_name == "elabftw"
        ]

        assert len(cdcs_results) == 1, "Expected exactly one CDCS export result"
        assert len(elabftw_results) == 1, "Expected exactly one eLabFTW export result"

        cdcs_result = cdcs_results[0]
        elabftw_result = elabftw_results[0]

        assert cdcs_result.success, f"CDCS export failed: {cdcs_result.error_message}"
        assert elabftw_result.success, (
            f"eLabFTW export failed: {elabftw_result.error_message}"
        )

        assert isinstance(cdcs_result.record_url, str)
        assert isinstance(elabftw_result.record_url, str)

        # Fetch the eLabFTW experiment and verify CDCS URL is in the body
        experiment_id = int(elabftw_result.record_id)
        experiment = elabftw_client.get_experiment(experiment_id)

        # Verify the CDCS record URL appears in the eLabFTW experiment body
        assert cdcs_result.record_url in experiment["body"], (
            f"CDCS record URL not found in eLabFTW experiment body. "
            f"Expected to find: {cdcs_result.record_url}"
        )

        # Cleanup
        elabftw_client.delete_experiment(int(elabftw_result.record_id))

        from nexusLIMS.utils import cdcs

        cdcs.delete_record(cdcs_result.record_id)
