"""
End-to-end workflow integration tests for NexusLIMS.

This module tests the complete workflow from NEMO usage events through record
building to CDCS upload, verifying that all components work together correctly.
"""

from datetime import timedelta

import pytest
from lxml import etree

from nexusLIMS.builder import record_builder
from nexusLIMS.db.session_handler import db_query

# test_environment_setup fixture is now defined in conftest.py


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows from NEMO to CDCS."""

    def test_complete_record_building_workflow(
        self,
        test_environment_setup,
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
        dataset_url = f"http://fileserver.localhost/instrument-data{dataset_location}"

        print(f"\n[*] Testing fileserver access to dataset: {dataset_url}")
        dataset_response = requests.get(dataset_url, timeout=10)
        assert dataset_response.status_code == 200, (
            f"Failed to access dataset via fileserver: {dataset_response.status_code}"
        )
        assert len(dataset_response.content) > 0, "Dataset file is empty"
        print(
            f"[+] Successfully accessed dataset file ({len(dataset_response.content)} bytes)"
        )

        # Find a preview image URL (these are in <preview> elements)
        preview_elements = downloaded_doc.findall(f".//{nx_ns}dataset/{nx_ns}preview")
        if len(preview_elements) > 0:
            preview_path = preview_elements[0].text
            # Preview paths are relative to NX_DATA_PATH
            # Convert to fileserver URL using /data/ prefix
            preview_url = f"http://fileserver.localhost/data{preview_path}"
            print(f"\n[*] Testing fileserver access to preview: {preview_url}")

            preview_response = requests.get(preview_url, timeout=10)
            assert preview_response.status_code == 200, (
                f"Failed to access preview via fileserver: {preview_response.status_code}"
            )
            assert len(preview_response.content) > 0, "Preview file is empty"
            # Verify it's an image (should have image content type or be PNG/JPG)
            content_type = preview_response.headers.get("Content-Type", "")
            assert "image" in content_type or preview_url.endswith(
                (".png", ".jpg", ".jpeg")
            ), f"Preview doesn't appear to be an image: {content_type}"
            print(
                f"[+] Successfully accessed preview image ({len(preview_response.content)} bytes)"
            )
        else:
            print("[!] No preview elements found in XML (this may be expected)")

        # clean up uploaded record on success
        cdcs_module.delete_record(record_id)
        with pytest.raises(ValueError, match=f"Record with id {record_id} not found"):
            cdcs_module.download_record(record_id)
