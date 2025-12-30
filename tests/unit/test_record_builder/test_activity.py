"""Tests for AcquisitionActivity functionality."""

# pylint: disable=missing-function-docstring
# ruff: noqa: D102

from pathlib import Path

import pytest

from nexusLIMS.schemas import activity


class TestActivity:
    """Test the representation and functionality of acquisition activities."""

    def test_activity_repr(self, gnu_find_activities):
        expected = "             AcquisitionActivity; "
        expected += "start: 2018-11-13T11:01:00-07:00; "
        expected += "end: 2018-11-13T11:04:00-07:00"
        assert repr(gnu_find_activities["activities_list"][0]) == expected

    def test_activity_str(self, gnu_find_activities):
        expected = "2018-11-13T11:01:00-07:00 AcquisitionActivity "
        assert str(gnu_find_activities["activities_list"][0]) == expected

    def test_activity_default_start_end(self):
        """Test that AcquisitionActivity sets start/end to current time by default."""
        import datetime

        from freezegun import freeze_time

        from nexusLIMS.schemas.activity import AcquisitionActivity
        from nexusLIMS.utils import current_system_tz

        # Freeze time at a specific moment
        frozen_time = "2024-01-15 10:30:00"
        with freeze_time(frozen_time):
            expected_time = datetime.datetime.now(tz=current_system_tz())

            # Create activity without providing start or end times
            test_activity = AcquisitionActivity()

            # Verify start and end are set to the frozen time
            assert test_activity.start == expected_time
            assert test_activity.end == expected_time

        # Verify that unique_params is also set to empty set
        assert test_activity.unique_params == set()

    def test_add_file_bad_meta(
        self,
        monkeypatch,
        caplog,
        gnu_find_activities,
        eels_si_titan,
    ):
        # make parse_metadata return None to force into error situation
        monkeypatch.setattr(
            activity,
            "parse_metadata",
            lambda fname, generate_preview: (None, ""),  # noqa: ARG005
        )
        orig_activity_file_length = len(
            gnu_find_activities["activities_list"][0].files,
        )
        gnu_find_activities["activities_list"][0].add_file(eels_si_titan[0])
        assert (
            len(gnu_find_activities["activities_list"][0].files)
            == orig_activity_file_length + 1
        )
        assert f"Could not parse metadata of {eels_si_titan[0]}" in caplog.text

    def test_add_file_bad_file(self, gnu_find_activities):
        with pytest.raises(FileNotFoundError):
            gnu_find_activities["activities_list"][0].add_file(
                Path("dummy_file_does_not_exist"),
            )

    def test_store_unique_before_setup(
        self,
        monkeypatch,
        caplog,
        gnu_find_activities,
    ):
        activity_1 = gnu_find_activities["activities_list"][0]
        monkeypatch.setattr(activity_1, "setup_params", None)
        activity_1.store_unique_metadata()
        assert (
            "setup_params has not been defined; call store_setup_params() "
            "prior to using this method. Nothing was done." in caplog.text
        )

    def test_as_xml(self, gnu_find_activities):
        activity_1 = gnu_find_activities["activities_list"][0]
        # setup a few values in the activity to trigger XML escaping:
        activity_1.setup_params["Acquisition Device"] = "<TEST>"
        activity_1.files[0] += "<&"
        activity_1.unique_meta[0]["Imaging Mode"] = "<IMAGING>"

        _ = activity_1.as_xml(seqno=0, sample_id="sample_id")

    def test_as_xml_with_warnings(self, gnu_find_activities):
        """Test that warning attributes are correctly added to XML elements."""
        activity_1 = gnu_find_activities["activities_list"][0]

        # Add some metadata with warnings
        # Setup a warning in the setup_params (affects all files)
        activity_1.setup_params["Beam Energy"] = "200.0 kV"
        activity_1.warnings[0].append("Beam Energy")

        # Add a warning to unique metadata for the first file
        activity_1.unique_meta[0]["Magnification"] = "50000x"
        activity_1.warnings[0].append("Magnification")

        # Generate XML (returns an lxml Element)
        root = activity_1.as_xml(seqno=0, sample_id="sample_id")

        # Check that setup param with warning has warning="true" attribute
        setup_params = root.xpath(".//setup/param[@name='Beam Energy']")
        assert len(setup_params) == 1
        assert setup_params[0].get("warning") == "true"

        # Check that unique metadata with warning has warning="true" attribute
        meta_elements = root.xpath(".//dataset/meta[@name='Magnification']")
        assert len(meta_elements) >= 1
        assert meta_elements[0].get("warning") == "true"

        # Check that elements without warnings don't have the warning attribute
        # (or it's not set to "true")
        non_warning_params = root.xpath(".//setup/param[@name='Acquisition Device']")
        if len(non_warning_params) > 0:
            assert non_warning_params[0].get("warning") != "true"

    def test_add_file_multi_signal_no_preview(self, list_signal):
        """Test add_file with multi-signal file without preview generation.

        This tests the code path where preview_fnames is None or empty
        for a multi-signal file when generate_preview=False.
        """
        from nexusLIMS.schemas.activity import AcquisitionActivity

        # Create activity and add multi-signal file without preview generation
        test_activity = AcquisitionActivity()
        test_activity.add_file(list_signal[0], generate_preview=False)

        # Verify file was added with multiple signals
        assert len(test_activity.files) == 2  # Multi-signal file
        assert all(f == str(list_signal[0]) for f in test_activity.files)

        # Verify previews are all None (because generate_preview=False)
        assert len(test_activity.previews) == 2
        assert all(p is None for p in test_activity.previews)

        # Verify metadata was added
        assert len(test_activity.meta) == 2
        assert "Data Type" in test_activity.meta[0]
        assert "Data Type" in test_activity.meta[1]

    def test_as_xml_with_quantity_metadata(self, gnu_find_activities):
        """Test Pint Quantity objects serialize to XML with unit attributes."""
        from nexusLIMS.schemas.units import ureg

        activity_1 = gnu_find_activities["activities_list"][0]

        # Add Pint Quantity objects to unique_meta for the first file
        activity_1.unique_meta[0]["Beam Energy"] = ureg.Quantity(200.0, "kilovolt")
        activity_1.unique_meta[0]["Working Distance"] = ureg.Quantity(
            10.5, "millimeter"
        )
        activity_1.unique_meta[0]["Beam Current"] = ureg.Quantity(100, "picoampere")

        # Generate XML
        root = activity_1.as_xml(seqno=0, sample_id="sample_id")

        # Check that Quantity objects are serialized with magnitude and unit attribute
        beam_energy_elements = root.xpath(".//dataset/meta[@name='Beam Energy']")
        assert len(beam_energy_elements) >= 1
        beam_energy_el = beam_energy_elements[0]
        assert beam_energy_el.text == "200.0"
        assert beam_energy_el.get("unit") == "kV"

        working_distance_elements = root.xpath(
            ".//dataset/meta[@name='Working Distance']",
        )
        assert len(working_distance_elements) >= 1
        wd_el = working_distance_elements[0]
        assert wd_el.text == "10.5"
        assert wd_el.get("unit") == "mm"

        beam_current_elements = root.xpath(".//dataset/meta[@name='Beam Current']")
        assert len(beam_current_elements) >= 1
        bc_el = beam_current_elements[0]
        assert bc_el.text == "100.0"
        assert bc_el.get("unit") == "pA"

    def test_as_xml_with_quantity_and_warning(self, gnu_find_activities):
        """Test Quantity objects with warnings get unit and warning attributes."""
        from nexusLIMS.schemas.units import ureg

        activity_1 = gnu_find_activities["activities_list"][0]

        # Add a Quantity object with a warning
        activity_1.unique_meta[0]["Magnification"] = ureg.Quantity(
            50000, "dimensionless"
        )
        activity_1.warnings[0].append("Magnification")

        # Generate XML
        root = activity_1.as_xml(seqno=0, sample_id="sample_id")

        # Check that the element has both warning and unit attributes
        mag_elements = root.xpath(".//dataset/meta[@name='Magnification']")
        assert len(mag_elements) >= 1
        mag_el = mag_elements[0]
        assert mag_el.text == "50000.0"
        assert mag_el.get("warning") == "true"
        assert mag_el.get("unit") == ""  # dimensionless has empty unit string

    def test_end_to_end_with_profile_and_quantities(self):  # noqa: PLR0915
        """End-to-end test: extractor → profile extension_fields → XML with Quantities.

        This test verifies the complete integration flow:
        1. Extractor produces metadata with Pint Quantities
        2. Instrument profile adds extension_fields (including Quantities)
        3. Activity collects metadata from multiple files
        4. XML generation properly serializes all Quantities with unit attributes
        5. Extension fields appear in the correct XML structure
        """
        from unittest.mock import MagicMock

        from nexusLIMS.db.session_handler import Session
        from nexusLIMS.extractors.base import InstrumentProfile
        from nexusLIMS.extractors.profiles import get_profile_registry
        from nexusLIMS.schemas.activity import AcquisitionActivity
        from nexusLIMS.schemas.units import ureg

        # Setup: Create a mock instrument with a profile that adds extension_fields
        registry = get_profile_registry()
        # Save original state
        original_profiles = registry._profiles.copy()  # noqa: SLF001

        try:
            # Create an instrument profile with extension fields (including Quantities)
            profile = InstrumentProfile(
                instrument_id="test-instrument-integration",
                extension_fields={
                    "facility": "Test Electron Microscopy Facility",
                    "building": ureg.Quantity(220, "dimensionless"),  # Building number
                    "elevation": ureg.Quantity(100.5, "meter"),  # Building elevation
                    "calibration_date": "2025-12-01",
                },
            )
            registry.register(profile)

            # Create a mock instrument
            mock_instrument = MagicMock(spec=Session)
            mock_instrument.instrument_id = "test-instrument-integration"

            # Create an activity and add mock metadata simulating extractor output
            activity = AcquisitionActivity()

            # Simulate first file with Quantities from extractor
            # Note: metadata is stored flattened (not wrapped in nx_meta)
            meta1 = {
                "DatasetType": "Image",
                "Data Type": "SEM_Imaging",
                "Creation Time": "2025-12-16T10:00:00+00:00",
                "Beam Energy": ureg.Quantity(5.0, "kilovolt"),
                "Working Distance": ureg.Quantity(8.5, "millimeter"),
                "Pixel Size": ureg.Quantity(2.5, "nanometer"),
            }
            # Inject extension fields (simulating what happens in parse_metadata)
            meta1.update(profile.extension_fields)

            activity.files.append("file1.tif")
            activity.previews.append(None)
            activity.meta.append(meta1)
            activity.warnings.append([])

            # Simulate second file with different parameters
            meta2 = {
                "DatasetType": "Image",
                "Data Type": "SEM_Imaging",
                "Creation Time": "2025-12-16T10:05:00+00:00",
                "Beam Energy": ureg.Quantity(10.0, "kilovolt"),
                "Working Distance": ureg.Quantity(10.0, "millimeter"),
                "Magnification": ureg.Quantity(25000, "dimensionless"),
            }
            # Inject extension fields (simulating what happens in parse_metadata)
            meta2.update(profile.extension_fields)

            activity.files.append("file2.tif")
            activity.previews.append(None)
            activity.meta.append(meta2)
            activity.warnings.append([])

            # Set instrument for activity
            activity.instrument = mock_instrument

            # Store setup and unique params
            activity.store_setup_params()
            activity.store_unique_metadata()

            # Generate XML
            root = activity.as_xml(seqno=0, sample_id="test_sample")

            # Verify extension fields are present in XML
            facility_elements = root.xpath(".//setup/param[@name='facility']")
            assert len(facility_elements) == 1
            assert facility_elements[0].text == "Test Electron Microscopy Facility"

            building_elements = root.xpath(".//setup/param[@name='building']")
            assert len(building_elements) == 1
            assert building_elements[0].text == "220.0"
            assert building_elements[0].get("unit") == ""  # dimensionless

            elevation_elements = root.xpath(".//setup/param[@name='elevation']")
            assert len(elevation_elements) == 1
            assert elevation_elements[0].text == "100.5"
            assert elevation_elements[0].get("unit") == "m"

            calibration_elements = root.xpath(
                ".//setup/param[@name='calibration_date']"
            )
            assert len(calibration_elements) == 1
            assert calibration_elements[0].text == "2025-12-01"
            assert calibration_elements[0].get("unit") is None  # No unit for strings

            # Verify extractor-provided Quantities in unique metadata
            # Beam Energy and Working Distance vary, so should be in unique metadata
            beam_energy_elements = root.xpath(".//dataset/meta[@name='Beam Energy']")
            assert len(beam_energy_elements) == 2  # Two different files
            assert beam_energy_elements[0].text == "5.0"
            assert beam_energy_elements[0].get("unit") == "kV"
            assert beam_energy_elements[1].text == "10.0"
            assert beam_energy_elements[1].get("unit") == "kV"

            wd_elements = root.xpath(".//dataset/meta[@name='Working Distance']")
            assert len(wd_elements) == 2  # Two different files
            assert wd_elements[0].text == "8.5"
            assert wd_elements[0].get("unit") == "mm"
            assert wd_elements[1].text == "10.0"
            assert wd_elements[1].get("unit") == "mm"

            # Pixel Size only appears in first file, so should be in unique metadata
            pixel_size_elements = root.xpath(".//dataset/meta[@name='Pixel Size']")
            assert len(pixel_size_elements) == 1  # Only in first file
            assert pixel_size_elements[0].text == "2.5"
            assert pixel_size_elements[0].get("unit") == "nm"

            # Magnification only appears in second file, so should be in unique metadata
            mag_elements = root.xpath(".//dataset/meta[@name='Magnification']")
            assert len(mag_elements) == 1  # Only in second file
            assert mag_elements[0].text == "25000.0"
            assert mag_elements[0].get("unit") == ""  # dimensionless

        finally:
            # Restore original registry state
            registry._profiles = original_profiles  # noqa: SLF001

    def test_setup_params_missing_key_in_second_file(self):
        """Test that missing keys in subsequent files are not kept in setup_params.

        This is a regression test for a bug where if a parameter appeared in file1
        but was missing from file2, it would incorrectly remain in setup_params
        instead of being moved to unique_meta for file1.
        """
        from nexusLIMS.schemas.activity import AcquisitionActivity
        from nexusLIMS.schemas.units import ureg

        activity = AcquisitionActivity()

        # File 1 has "Pixel Size"
        meta1 = {
            "DatasetType": "Image",
            "Beam Energy": ureg.Quantity(5.0, "kilovolt"),
            "Pixel Size": ureg.Quantity(2.5, "nanometer"),
        }
        activity.files.append("file1.tif")
        activity.previews.append(None)
        activity.meta.append(meta1)
        activity.warnings.append([])

        # File 2 does NOT have "Pixel Size" - it's missing
        meta2 = {
            "DatasetType": "Image",
            "Beam Energy": ureg.Quantity(10.0, "kilovolt"),
            # Note: No "Pixel Size" key here
        }
        activity.files.append("file2.tif")
        activity.previews.append(None)
        activity.meta.append(meta2)
        activity.warnings.append([])

        # Store setup and unique params
        activity.store_setup_params()
        activity.store_unique_metadata()

        # Verify:
        # - "DatasetType" should be in setup_params (present and same in both files)
        assert "DatasetType" in activity.setup_params
        assert activity.setup_params["DatasetType"] == "Image"

        # - "Beam Energy" should NOT be in setup_params (different values)
        assert "Beam Energy" not in activity.setup_params

        # - "Pixel Size" should NOT be in setup_params (missing in file2)
        assert "Pixel Size" not in activity.setup_params

        # - "Pixel Size" should be in unique_meta for file1 only
        assert "Pixel Size" in activity.unique_meta[0]
        assert activity.unique_meta[0]["Pixel Size"] == ureg.Quantity(2.5, "nanometer")
        assert "Pixel Size" not in activity.unique_meta[1]

        # - "Beam Energy" should be in unique_meta for both files (different values)
        assert "Beam Energy" in activity.unique_meta[0]
        assert "Beam Energy" in activity.unique_meta[1]
