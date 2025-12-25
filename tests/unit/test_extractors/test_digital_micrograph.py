# pylint: disable=C0116
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors.digital_micrograph."""

from pathlib import Path

import pytest

from nexusLIMS.extractors.plugins import digital_micrograph
from nexusLIMS.extractors.utils import _try_decimal, _zero_data_in_dm3
from nexusLIMS.schemas.units import ureg
from tests.unit.test_instrument_factory import (
    make_jeol_tem,
    make_test_tool,
    make_titan_stem,
    make_titan_tem,
)


class TestDigitalMicrographExtractor:
    """Tests nexusLIMS.extractors.digital_micrograph."""

    @pytest.fixture
    def profile_registry_manager(self):
        """Fixture that saves and restores profile registry state.

        This ensures that test profiles don't pollute the registry for
        subsequent tests. Use this when registering temporary test profiles.

        Yields
        ------
        InstrumentProfileRegistry
            The profile registry instance
        """
        from nexusLIMS.extractors.profiles import get_profile_registry

        registry = get_profile_registry()
        # Save existing profiles before test
        existing_profiles = registry.get_all_profiles()

        yield registry

        # Restore original state after test
        registry.clear()
        for profile in existing_profiles.values():
            registry.register(profile)

    def test_corrupted_file(self, corrupted_file):
        assert digital_micrograph.get_dm3_metadata(corrupted_file) is None

    def test_corrupted_file_via_extractor(self, corrupted_file):
        """Test that the extractor class handles corrupted files gracefully."""
        from nexusLIMS.extractors.base import ExtractionContext
        from nexusLIMS.extractors.plugins.digital_micrograph import DM3Extractor

        # Create extractor and context
        extractor = DM3Extractor()
        context = ExtractionContext(file_path=corrupted_file[0], instrument=None)

        # Extract should return basic metadata with a warning, not raise
        metadata = extractor.extract(context)

        # Should have basic metadata structure (now as a list)
        assert metadata is not None
        assert isinstance(metadata, list)
        assert len(metadata) == 1

        meta = metadata[0]
        assert "nx_meta" in meta

        # Should have a warning about the failure
        assert "warnings" in meta["nx_meta"]
        warnings = meta["nx_meta"]["warnings"]
        assert any(
            "DM3/DM4 file could not be read by HyperSpy" in str(w) for w in warnings
        )

    def test_dm3_list_file(self, list_signal, mock_instrument_from_filepath):
        """Test DM3 metadata extraction from list signal file.

        This test now uses the instrument factory instead of relying on
        specific database entries, making dependencies explicit.
        """
        # Set up instrument for this test
        mock_instrument_from_filepath(make_test_tool())

        metadata_list = digital_micrograph.get_dm3_metadata(list_signal[0])

        assert metadata_list is not None
        assert isinstance(metadata_list, list)
        assert len(metadata_list) > 0

        # Check first signal
        metadata = metadata_list[0]
        assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert metadata["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert metadata["nx_meta"]["Microscope"] == "TEST Titan_______"
        # Voltage should be a Quantity in volts
        voltage = metadata["nx_meta"]["Voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == pytest.approx(300000.0)
        assert str(voltage.units) in [
            "volt",
            "kilovolt",
        ]  # Could be either depending on auto-conversion

    def test_dm3_diffraction(
        self,
        stem_diff,
        opmode_diff,
        mock_instrument_from_filepath,
    ):
        """Test DM3 diffraction metadata extraction from Titan TEM."""
        mock_instrument_from_filepath(make_titan_tem())

        meta_list = digital_micrograph.get_dm3_metadata(stem_diff[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        # Voltage should be a Quantity in volts
        voltage = meta["nx_meta"]["Voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == pytest.approx(300000.0)
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert

        meta_list = digital_micrograph.get_dm3_metadata(opmode_diff[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        # Voltage should be a Quantity in volts
        voltage = meta["nx_meta"]["Voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == pytest.approx(300000.0)
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert

    def test_titan_dm3_eels(
        self,
        eels_proc_1_titan,
        eels_si_drift,
        tecnai_mag,
        mock_instrument_from_filepath,
    ):
        """Test DM3 EELS metadata extraction from Titan TEM."""
        mock_instrument_from_filepath(make_titan_tem())

        meta_list = digital_micrograph.get_dm3_metadata(eels_proc_1_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        # Voltage should be a Quantity in volts
        voltage = meta["nx_meta"]["Voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == pytest.approx(300000.0)
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Aligned parent SI By Peak, Extracted from SI"
        )
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "2mm"

        meta_list = digital_micrograph.get_dm3_metadata(eels_si_drift[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        # Voltage should be a Quantity in volts
        voltage = meta["nx_meta"]["Voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == pytest.approx(300000.0)
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert
        # Convergence semi-angle should be a Quantity in milliradians
        convergence_angle = meta["nx_meta"]["EELS"]["Convergence semi-angle"]
        assert isinstance(convergence_angle, ureg.Quantity)
        assert convergence_angle.magnitude == pytest.approx(10.0)
        assert str(convergence_angle.units) == "milliradian"
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "2mm"
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 100 seconds"
        )
        # Pixel time should be a Quantity in seconds
        pixel_time = meta["nx_meta"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert pixel_time.magnitude == pytest.approx(0.05)
        assert str(pixel_time.units) == "second"

        meta_list = digital_micrograph.get_dm3_metadata(tecnai_mag[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta["nx_meta"]["Imaging Mode"] == "IMAGING"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Indicated Magnification"] == pytest.approx(8100.0)
        assert meta["nx_meta"]["Tecnai User"] == "USER"
        assert meta["nx_meta"]["Tecnai Mode"] == "TEM uP SA Zoom Image"

    def test_titan_stem_dm3(  # noqa: PLR0915
        self,
        eftem_diff,
        eds_si_titan,
        stem_stack_titan,
        mock_instrument_from_filepath,
    ):
        """Test DM3 metadata extraction from a Titan STEM."""
        mock_instrument_from_filepath(make_titan_stem())

        meta_list = digital_micrograph.get_dm3_metadata(eftem_diff[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_EFTEM_Diffraction"
        assert meta["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "EFTEM DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan_______"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(5.0)
        assert str(camera_length.units) == "millimeter"
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "5 mm"

        meta_list = digital_micrograph.get_dm3_metadata(eds_si_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EDS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Analytic Signal"] == "X-ray"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum image"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(77.0)
        assert str(camera_length.units) == "millimeter"
        assert meta["nx_meta"]["EDS"]["Real time (SI Average)"] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        assert meta["nx_meta"]["EDS"]["Live time (SI Average)"] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        # Pixel time should be a Quantity in seconds
        pixel_time = meta["nx_meta"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert pixel_time.magnitude == pytest.approx(1.0)
        assert str(pixel_time.units) == "second"
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Spatial Sampling (Horizontal)"] == 100
        )

        meta_list = digital_micrograph.get_dm3_metadata(stem_stack_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        assert meta["nx_meta"]["Acquisition Device"] == "DigiScan"
        # Cs should be a Quantity in millimeters
        cs = meta["nx_meta"]["Cs"]
        assert isinstance(cs, ureg.Quantity)
        assert cs.magnitude == pytest.approx(1.0)
        assert str(cs.units) == "millimeter"
        assert meta["nx_meta"]["Data Dimensions"] == "(12, 1024, 1024)"
        assert meta["nx_meta"]["Indicated Magnification"] == pytest.approx(7200000.0)
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(100.0)
        assert str(camera_length.units) == "millimeter"

    def test_titan_stem_dm3_eels(  # noqa: PLR0915
        self,
        eels_si_titan,
        eels_proc_int_bg_titan,
        eels_proc_thick_titan,
        eels_si_drift_titan,
        mock_instrument_from_filepath,
    ):
        """Test DM3 EELS metadata extraction from Titan STEM."""
        mock_instrument_from_filepath(make_titan_stem())

        meta_list = digital_micrograph.get_dm3_metadata(eels_si_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Operation Mode"] == "SCANNING"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(60.0)
        assert str(camera_length.units) == "millimeter"
        # Convergence semi-angle should be a Quantity in milliradians
        convergence_angle = meta["nx_meta"]["EELS"]["Convergence semi-angle"]
        assert isinstance(convergence_angle, ureg.Quantity)
        assert convergence_angle.magnitude == pytest.approx(13.0)
        assert str(convergence_angle.units) == "milliradian"
        # Exposure should be a Quantity in seconds
        exposure = meta["nx_meta"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert exposure.magnitude == pytest.approx(0.5)
        assert str(exposure.units) == "second"
        # Pixel time should be a Quantity in seconds
        pixel_time = meta["nx_meta"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert pixel_time.magnitude == pytest.approx(0.5)
        assert str(pixel_time.units) == "second"
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        # Acquisition Duration should be a Quantity in seconds
        acquisition_duration = meta["nx_meta"]["Spectrum Imaging"][
            "Acquisition Duration"
        ]
        assert isinstance(acquisition_duration, ureg.Quantity)
        assert acquisition_duration.magnitude == pytest.approx(605)
        assert str(acquisition_duration.units) == "second"

        meta_list = digital_micrograph.get_dm3_metadata(eels_proc_int_bg_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Image"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(48.0)
        assert str(camera_length.units) == "millimeter"
        assert meta["nx_meta"]["EELS"]["Background Removal Model"] == "Power Law"
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Background Removal, Signal Integration"
        )

        meta_list = digital_micrograph.get_dm3_metadata(eels_proc_thick_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(60.0)
        assert str(camera_length.units) == "millimeter"
        # Exposure should be a Quantity in seconds
        exposure = meta["nx_meta"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert exposure.magnitude == pytest.approx(0.05)
        assert str(exposure.units) == "second"
        # Integration time should be a Quantity in seconds
        integration_time = meta["nx_meta"]["EELS"]["Integration time"]
        assert isinstance(integration_time, ureg.Quantity)
        assert integration_time.magnitude == pytest.approx(0.25)
        assert str(integration_time.units) == "second"
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Calibrated Post-acquisition, Compute Thickness"
        )
        assert meta["nx_meta"]["EELS"]["Thickness (absolute) [nm]"] == pytest.approx(
            85.29884338378906,
            0.1,
        )

        meta_list = digital_micrograph.get_dm3_metadata(eels_si_drift_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum image"
        assert meta["nx_meta"]["Analytic Acquisition Mode"] == "Parallel dispersive"
        # STEM Camera Length should be a Quantity in millimeters
        camera_length = meta["nx_meta"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert camera_length.magnitude == pytest.approx(100.0)
        assert str(camera_length.units) == "millimeter"
        # Exposure should be a Quantity in seconds
        exposure = meta["nx_meta"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert exposure.magnitude == pytest.approx(0.5)
        assert str(exposure.units) == "second"
        assert meta["nx_meta"]["EELS"]["Number of frames"] == 1
        # Acquisition Duration should be a Quantity in seconds
        acquisition_duration = meta["nx_meta"]["Spectrum Imaging"][
            "Acquisition Duration"
        ]
        assert isinstance(acquisition_duration, ureg.Quantity)
        assert acquisition_duration.magnitude == pytest.approx(2173)
        assert str(acquisition_duration.units) == "second"
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 1 row"
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "2D Array"

    def test_jeol3010_dm3(self, jeol3010_diff, mock_instrument_from_filepath):
        """Test DM3 metadata extraction from JEOL 3010 TEM file."""
        # Set up JEOL 3010 instrument for this test
        mock_instrument_from_filepath(make_jeol_tem())

        meta_list = digital_micrograph.get_dm3_metadata(jeol3010_diff[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta["nx_meta"]["Acquisition Device"] == "Orius "
        assert meta["nx_meta"]["Microscope"] == "JEM3010 UHR"
        assert meta["nx_meta"]["Data Dimensions"] == "(2672, 4008)"
        assert meta["nx_meta"]["Facility"] == "MicroLabFacility"
        assert meta["nx_meta"]["Camera/Detector Processing"] == "Gain Normalized"

    def test_try_decimal(self):
        # this function should just return the input if it cannot be
        # converted to a decimal
        assert _try_decimal("bogus") == "bogus"

    def test_zero_data(self, stem_image_dm3: Path):
        input_path = stem_image_dm3
        output_path = input_path.parent / (input_path.stem + "_test.dm3")
        fname_1 = _zero_data_in_dm3(input_path, out_filename=None)
        fname_2 = _zero_data_in_dm3(input_path, out_filename=output_path)
        fname_3 = _zero_data_in_dm3(input_path, compress=False)

        # All three files should have been created
        for filename in [fname_1, fname_2, fname_3]:
            assert filename.is_file()

        # The first two files should be compressed so data is smaller
        assert input_path.stat().st_size > fname_1.stat().st_size
        assert input_path.stat().st_size > fname_2.stat().st_size
        # The last should be the same size
        assert input_path.stat().st_size == fname_3.stat().st_size

        meta_in_list = digital_micrograph.get_dm3_metadata(input_path)
        meta_3_list = digital_micrograph.get_dm3_metadata(fname_3)

        # Creation times will be different, so remove that metadata
        assert meta_in_list is not None
        assert meta_3_list is not None
        assert isinstance(meta_in_list, list)
        assert isinstance(meta_3_list, list)

        meta_in = meta_in_list[0]
        meta_3 = meta_3_list[0]
        del meta_in["nx_meta"]["Creation Time"]
        del meta_3["nx_meta"]["Creation Time"]

        # All other metadata should be equal
        assert meta_in == meta_3

        for filename in [fname_1, fname_2, fname_3]:
            filename.unlink(missing_ok=True)

    def test_apply_profile_with_parsers(
        self,
        list_signal,
        mock_instrument_from_filepath,
        caplog,
        profile_registry_manager,
    ):
        """Test _apply_profile with custom parsers."""
        import logging

        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with a custom parser
        def custom_parser(metadata, ctx):  # noqa: ARG001
            metadata["nx_meta"]["CustomField"] = "CustomValue"
            return metadata

        profile = InstrumentProfile(
            instrument_id=instrument.name,
            parsers={"custom": custom_parser},
        )

        # Register the profile using the manager fixture
        profile_registry_manager.register(profile)

        # Extract metadata - should apply profile
        digital_micrograph.logger.setLevel(logging.DEBUG)
        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Verify parser was applied
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert result["nx_meta"]["CustomField"] == "CustomValue"

        # Verify log message
        assert f"Applying profile for instrument: {instrument.name}" in caplog.text

    def test_apply_profile_parser_failure(
        self,
        list_signal,
        mock_instrument_from_filepath,
        caplog,
        profile_registry_manager,
    ):
        """Test _apply_profile when parser raises exception."""
        import logging

        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with a failing parser
        def failing_parser(metadata, ctx):  # noqa: ARG001
            msg = "Parser intentionally failed"
            raise ValueError(msg)

        profile = InstrumentProfile(
            instrument_id=instrument.name,
            parsers={"failing": failing_parser},
        )

        # Register the profile using the manager fixture
        profile_registry_manager.register(profile)

        # Extract metadata - should handle parser failure gracefully
        digital_micrograph.logger.setLevel(logging.WARNING)

        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Metadata should still be extracted despite parser failure
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert "nx_meta" in result

        # Verify warning was logged
        assert "Profile parser 'failing' failed" in caplog.text
        assert "Parser intentionally failed" in caplog.text

    def test_apply_profile_with_transformations(
        self,
        list_signal,
        mock_instrument_from_filepath,
        profile_registry_manager,
    ):
        """Test _apply_profile with transformations."""
        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with a transformation on the nx_meta dict
        # Transformations work on top-level keys in the metadata dict
        def add_custom_field(nx_meta_dict):
            """Transform nx_meta by adding a custom field."""
            nx_meta_dict["TransformedField"] = "TRANSFORMATION_APPLIED"
            return nx_meta_dict

        profile = InstrumentProfile(
            instrument_id=instrument.name,
            # Transform the "nx_meta" top-level key
            transformations={"nx_meta": add_custom_field},
        )

        # Register the profile using the manager fixture
        profile_registry_manager.register(profile)

        # Extract metadata - should apply transformation
        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Verify transformation was applied
        # The nx_meta dict should have the transformed field
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert result["nx_meta"]["TransformedField"] == "TRANSFORMATION_APPLIED"

    def test_apply_profile_transformation_failure(
        self,
        list_signal,
        mock_instrument_from_filepath,
        caplog,
        profile_registry_manager,
    ):
        """Test _apply_profile when transformation raises exception."""
        import logging

        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with a failing transformation
        def failing_transform(value):  # noqa: ARG001
            msg = "Transform intentionally failed"
            raise RuntimeError(msg)

        profile = InstrumentProfile(
            instrument_id=instrument.name,
            transformations={"nx_meta": failing_transform},
        )

        # Register the profile using the manager fixture
        profile_registry_manager.register(profile)

        # Extract metadata - should handle transformation failure gracefully
        digital_micrograph.logger.setLevel(logging.WARNING)

        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Metadata should still be extracted despite transformation failure
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert "nx_meta" in result

        # Verify warning was logged
        assert "Profile transformation 'nx_meta' failed" in caplog.text
        assert "Transform intentionally failed" in caplog.text

    def test_apply_profile_with_extension_fields(
        self,
        list_signal,
        mock_instrument_from_filepath,
        profile_registry_manager,
    ):
        """Test _apply_profile with extension fields injection."""
        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with extension fields
        profile = InstrumentProfile(
            instrument_id=instrument.name,
            extension_fields={
                "facility": "Test Facility",
                "building": "Building 123",
                "custom_info": "Custom Value",
            },
        )

        # Register the profile using the manager fixture
        profile_registry_manager.register(profile)

        # Extract metadata - should inject extension fields
        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Verify extension fields were injected
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert "extensions" in result["nx_meta"]
        assert result["nx_meta"]["extensions"]["facility"] == "Test Facility"
        assert result["nx_meta"]["extensions"]["building"] == "Building 123"
        assert result["nx_meta"]["extensions"]["custom_info"] == "Custom Value"

    def test_apply_profile_empty_extension_fields(
        self,
        list_signal,
        mock_instrument_from_filepath,
        profile_registry_manager,
    ):
        """Test _apply_profile with empty extension fields dict."""
        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with empty extension fields
        profile = InstrumentProfile(
            instrument_id=instrument.name,
            extension_fields={},
        )

        # Register the profile
        profile_registry_manager.register(profile)

        result_list = digital_micrograph.get_dm3_metadata(
            list_signal[0], instrument=instrument
        )

        # Metadata should still be extracted
        assert result_list is not None
        assert isinstance(result_list, list)
        result = result_list[0]
        assert "nx_meta" in result
        # Extensions section should not be created if there are no extension fields
        assert "extensions" not in result["nx_meta"]

    def test_neoarm_gatan_image_metadata(
        self,
        neoarm_gatan_image_file,
        mock_instrument_from_filepath,
    ):
        """Test Signal Name, Apertures, and Sample Time from NeoArm file."""
        # Set up instrument for this test
        mock_instrument_from_filepath(make_test_tool())

        meta_list = digital_micrograph.get_dm3_metadata(neoarm_gatan_image_file)

        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) > 0

        meta = meta_list[0]
        assert "nx_meta" in meta

        # Test Signal Name extraction
        assert "Signal Name" in meta["nx_meta"]
        assert meta["nx_meta"]["Signal Name"] == "ADF"

        # Test aperture settings extraction
        assert "Condenser Aperture" in meta["nx_meta"]
        assert meta["nx_meta"]["Condenser Aperture"] == 5
        assert "Objective Aperture" in meta["nx_meta"]
        assert meta["nx_meta"]["Objective Aperture"] == 4
        assert "Selected Area Aperture" in meta["nx_meta"]
        assert meta["nx_meta"]["Selected Area Aperture"] == 0

        # Test Sample Time (dwell time) extraction - should be Quantity in microseconds
        sample_time = meta["nx_meta"]["Sample Time"]
        assert isinstance(sample_time, ureg.Quantity)
        assert sample_time.magnitude == pytest.approx(16.0)
        assert str(sample_time.units) == "microsecond"

    def test_dm4_multi_signal_extraction(
        self,
        neoarm_gatan_si_file,
        mock_instrument_from_filepath,
    ):
        """Test that all signals are extracted from multi-signal DM4 file."""
        from nexusLIMS.extractors.base import ExtractionContext
        from nexusLIMS.extractors.plugins.digital_micrograph import DM3Extractor

        # Set up instrument for this test
        mock_instrument_from_filepath(make_test_tool())

        extractor = DM3Extractor()
        context = ExtractionContext(file_path=neoarm_gatan_si_file, instrument=None)

        result = extractor.extract(context)

        # Should return a list of metadata dicts (multi-signal)
        assert isinstance(result, list)
        assert len(result) > 1  # Multiple signals

        # Check that each signal has required metadata
        for signal_meta in result:
            assert "nx_meta" in signal_meta
            assert "Creation Time" in signal_meta["nx_meta"]
            assert "DatasetType" in signal_meta["nx_meta"]
            assert "Data Type" in signal_meta["nx_meta"]

    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_dm4_multi_signal_previews(
        self,
        neoarm_gatan_si_file,
        tmp_path,
        monkeypatch,
    ):
        """Test that multiple preview images are generated with correct naming."""
        from nexusLIMS.extractors import parse_metadata

        # Mock the NX_DATA_PATH to use tmp_path
        monkeypatch.setenv("NX_DATA_PATH", str(tmp_path))

        _, previews = parse_metadata(
            neoarm_gatan_si_file, generate_preview=True, write_output=False
        )

        # Should return list of preview paths for multi-signal file
        assert isinstance(previews, list)
        assert len(previews) > 1

        # Check naming convention (should have _signalN suffix for multi-signal)
        for i, preview in enumerate(previews):
            if preview is not None:
                assert f"_signal{i}.thumb.png" in str(preview)

    def test_apply_profile_extension_field_injection_failure(
        self,
        list_signal,
        mock_instrument_from_filepath,
        caplog,
        profile_registry_manager,
    ):
        """Test _apply_profile when extension field injection raises exception."""
        import logging

        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and setup context
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        # Create a profile with extension fields
        profile = InstrumentProfile(
            instrument_id=instrument.name,
            extension_fields={
                "test_field": "test_value",
            },
        )

        # Register the profile
        profile_registry_manager.register(profile)

        # Set up logging to capture warnings
        digital_micrograph.logger.setLevel(logging.WARNING)

        # Create a nested dict structure where the extensions dict raises on assignment
        class FailingExtensionsDict(dict):
            def __setitem__(self, key, value):
                # Raise on any key assignment to simulate field injection failure
                msg = "Simulated injection failure"
                raise RuntimeError(msg)

        # Create metadata with pre-existing extensions dict that will fail
        metadata = {"nx_meta": {"extensions": FailingExtensionsDict()}}

        # Call _apply_profile_to_metadata directly
        result = digital_micrograph._apply_profile_to_metadata(  # noqa: SLF001
            metadata, instrument, list_signal[0]
        )

        # Should still return metadata despite the error
        assert result is not None

        # Verify warning was logged
        assert "Profile extension field injection" in caplog.text
        assert "failed" in caplog.text

    def test_quantity_conversion_failure_keeps_original_value(self):
        """Test that failed unit conversions keep original value w/ original field name.

        This tests lines 474-476 in parse_dm3_microscope_info where conversion to
        Pint Quantity fails due to ValueError or TypeError, and the original value
        is preserved with the original field name.
        """
        # Test dict value that will trigger TypeError when passed to ureg.Quantity
        invalid_value = {"metadata": "dict"}
        mdict = {
            "ImageList": {
                "TagGroup0": {
                    "ImageTags": {
                        "Microscope Info": {
                            "Cs(mm)": invalid_value,  # Should fail ureg.Quantity() call
                        }
                    }
                }
            },
            "nx_meta": {},
        }

        result = digital_micrograph.parse_dm3_microscope_info(mdict)

        # When conversion fails, the original value should be kept
        # with the original field name (not the converted name "Cs")
        assert "Cs(mm)" in result["nx_meta"]
        assert result["nx_meta"]["Cs(mm)"] == invalid_value
