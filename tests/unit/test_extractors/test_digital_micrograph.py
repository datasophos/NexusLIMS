# pylint: disable=C0116
# ruff: noqa: D102, SLF001

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
        # Vendor-specific fields now in extensions
        assert "extensions" in metadata["nx_meta"]
        assert metadata["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert metadata["nx_meta"]["extensions"]["Microscope"] == "TEST Titan_______"
        # acceleration_voltage should be a Quantity (EM Glossary name)
        voltage = metadata["nx_meta"]["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000.0
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
        # Vendor-specific fields in extensions
        assert "extensions" in meta["nx_meta"]
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan"
        # acceleration_voltage (EM Glossary name)
        voltage = meta["nx_meta"]["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000.0
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert

        meta_list = digital_micrograph.get_dm3_metadata(opmode_diff[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_Diffraction"
        # Vendor-specific fields in extensions
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan"
        # acceleration_voltage (EM Glossary name)
        voltage = meta["nx_meta"]["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000.0
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
        # Vendor-specific fields in extensions
        assert "extensions" in meta["nx_meta"]
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan"
        # acceleration_voltage (EM Glossary name)
        voltage = meta["nx_meta"]["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000.0
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert
        # EELS metadata in extensions
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Processing Steps"]
            == "Aligned parent SI By Peak, Extracted from SI"
        )
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Spectrometer Aperture label"]
            == "2mm"
        )

        meta_list = digital_micrograph.get_dm3_metadata(eels_si_drift[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        # Vendor-specific fields in extensions
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan"
        # acceleration_voltage (EM Glossary name)
        voltage = meta["nx_meta"]["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000.0
        assert str(voltage.units) in ["volt", "kilovolt"]  # Could auto-convert
        # Convergence semi-angle should be a Quantity in milliradians (in extensions)
        convergence_angle = meta["nx_meta"]["extensions"]["EELS"][
            "Convergence semi-angle"
        ]
        assert isinstance(convergence_angle, ureg.Quantity)
        assert float(convergence_angle.magnitude) == 10.0
        assert str(convergence_angle.units) == "milliradian"
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Spectrometer Aperture label"]
            == "2mm"
        )
        # Spectrum Imaging metadata in extensions
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 100 seconds"
        )
        # Pixel time should be a Quantity in seconds
        pixel_time = meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert float(pixel_time.magnitude) == 0.05
        assert str(pixel_time.units) == "second"

        meta_list = digital_micrograph.get_dm3_metadata(tecnai_mag[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "TEM_Imaging"
        # Vendor-specific fields in extensions
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "IMAGING"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan"
        # magnification (EM Glossary name)
        assert meta["nx_meta"]["magnification"] == pytest.approx(8100.0)
        # Tecnai-specific fields in extensions
        assert meta["nx_meta"]["extensions"]["Tecnai User"] == "USER"
        assert meta["nx_meta"]["extensions"]["Tecnai Mode"] == "TEM uP SA Zoom Image"

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
        # Vendor-specific fields in extensions
        assert "extensions" in meta["nx_meta"]
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "EFTEM DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Microscope"] == "TEST Titan_______"
        # camera_length is core field for Diffraction (EM Glossary name)
        camera_length = meta["nx_meta"]["camera_length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 5.0
        assert str(camera_length.units) == "millimeter"
        # EELS metadata in extensions
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Spectrometer Aperture label"]
            == "5 mm"
        )

        meta_list = digital_micrograph.get_dm3_metadata(eds_si_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EDS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        # Vendor-specific analytic metadata in extensions
        assert meta["nx_meta"]["extensions"]["Analytic Signal"] == "X-ray"
        assert meta["nx_meta"]["extensions"]["Analytic Format"] == "Spectrum image"
        # STEM Camera Length is in extensions for non-Diffraction types
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 77.0
        assert str(camera_length.units) == "millimeter"
        # EDS metadata in extensions
        assert meta["nx_meta"]["extensions"]["EDS"][
            "Real time (SI Average)"
        ] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        assert meta["nx_meta"]["extensions"]["EDS"][
            "Live time (SI Average)"
        ] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        # Spectrum Imaging metadata in extensions - Pixel time should be a Quantity
        pixel_time = meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert float(pixel_time.magnitude) == 1.0
        assert str(pixel_time.units) == "second"
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        )
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"][
                "Spatial Sampling (Horizontal)"
            ]
            == 100
        )

        meta_list = digital_micrograph.get_dm3_metadata(stem_stack_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        # acquisition_device is core field (EM Glossary name)
        assert meta["nx_meta"]["acquisition_device"] == "DigiScan"
        # Cs is vendor-specific, in extensions
        cs = meta["nx_meta"]["extensions"]["Cs"]
        assert isinstance(cs, ureg.Quantity)
        assert float(cs.magnitude) == 1.0
        assert str(cs.units) == "millimeter"
        assert meta["nx_meta"]["Data Dimensions"] == "(12, 1024, 1024)"
        # magnification is core field (EM Glossary name)
        assert meta["nx_meta"]["magnification"] == pytest.approx(7200000.0)
        # STEM Camera Length is in extensions for Image type
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 100.0
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
        # Vendor-specific fields in extensions
        assert "extensions" in meta["nx_meta"]
        assert meta["nx_meta"]["extensions"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["extensions"]["Operation Mode"] == "SCANNING"
        # STEM Camera Length in extensions for non-Diffraction
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 60.0
        assert str(camera_length.units) == "millimeter"
        # EELS metadata in extensions
        convergence_angle = meta["nx_meta"]["extensions"]["EELS"][
            "Convergence semi-angle"
        ]
        assert isinstance(convergence_angle, ureg.Quantity)
        assert float(convergence_angle.magnitude) == 13.0
        assert str(convergence_angle.units) == "milliradian"
        exposure = meta["nx_meta"]["extensions"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert float(exposure.magnitude) == 0.5
        assert str(exposure.units) == "second"
        # Spectrum Imaging metadata in extensions
        pixel_time = meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Pixel time"]
        assert isinstance(pixel_time, ureg.Quantity)
        assert float(pixel_time.magnitude) == 0.5
        assert str(pixel_time.units) == "second"
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        )
        acquisition_duration = meta["nx_meta"]["extensions"]["Spectrum Imaging"][
            "Acquisition Duration"
        ]
        assert isinstance(acquisition_duration, ureg.Quantity)
        assert float(acquisition_duration.magnitude) == 605
        assert str(acquisition_duration.units) == "second"

        meta_list = digital_micrograph.get_dm3_metadata(eels_proc_int_bg_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        # Analytic metadata in extensions
        assert meta["nx_meta"]["extensions"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["extensions"]["Analytic Format"] == "Image"
        # STEM Camera Length in extensions for Spectrum
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 48.0
        assert str(camera_length.units) == "millimeter"
        # EELS metadata in extensions
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Background Removal Model"]
            == "Power Law"
        )
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Processing Steps"]
            == "Background Removal, Signal Integration"
        )

        meta_list = digital_micrograph.get_dm3_metadata(eels_proc_thick_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        # Analytic metadata in extensions
        assert meta["nx_meta"]["extensions"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["extensions"]["Analytic Format"] == "Spectrum"
        # STEM Camera Length in extensions for Spectrum
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 60.0
        assert str(camera_length.units) == "millimeter"
        # EELS metadata in extensions
        exposure = meta["nx_meta"]["extensions"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert float(exposure.magnitude) == 0.05
        assert str(exposure.units) == "second"
        integration_time = meta["nx_meta"]["extensions"]["EELS"]["Integration time"]
        assert isinstance(integration_time, ureg.Quantity)
        assert float(integration_time.magnitude) == 0.25
        assert str(integration_time.units) == "second"
        assert (
            meta["nx_meta"]["extensions"]["EELS"]["Processing Steps"]
            == "Calibrated Post-acquisition, Compute Thickness"
        )
        assert meta["nx_meta"]["extensions"]["EELS"][
            "Thickness (absolute) [nm]"
        ] == pytest.approx(
            85.29884338378906,
            0.1,
        )

        meta_list = digital_micrograph.get_dm3_metadata(eels_si_drift_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        # Analytic metadata in extensions
        assert meta["nx_meta"]["extensions"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["extensions"]["Analytic Format"] == "Spectrum image"
        assert (
            meta["nx_meta"]["extensions"]["Analytic Acquisition Mode"]
            == "Parallel dispersive"
        )
        # STEM Camera Length in extensions for SpectrumImage
        camera_length = meta["nx_meta"]["extensions"]["STEM Camera Length"]
        assert isinstance(camera_length, ureg.Quantity)
        assert float(camera_length.magnitude) == 100.0
        assert str(camera_length.units) == "millimeter"
        # EELS metadata in extensions
        exposure = meta["nx_meta"]["extensions"]["EELS"]["Exposure"]
        assert isinstance(exposure, ureg.Quantity)
        assert float(exposure.magnitude) == 0.5
        assert str(exposure.units) == "second"
        assert meta["nx_meta"]["extensions"]["EELS"]["Number of frames"] == 1
        # Spectrum Imaging metadata in extensions
        acquisition_duration = meta["nx_meta"]["extensions"]["Spectrum Imaging"][
            "Acquisition Duration"
        ]
        assert isinstance(acquisition_duration, ureg.Quantity)
        assert float(acquisition_duration.magnitude) == 2173
        assert str(acquisition_duration.units) == "second"
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 1 row"
        )
        assert (
            meta["nx_meta"]["extensions"]["Spectrum Imaging"]["Scan Mode"] == "2D Array"
        )

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
        # acquisition_device is core field (EM Glossary name)
        assert meta["nx_meta"]["acquisition_device"] == "Orius "
        # Vendor-specific fields in extensions
        assert "extensions" in meta["nx_meta"]
        assert meta["nx_meta"]["extensions"]["Microscope"] == "JEM3010 UHR"
        assert meta["nx_meta"]["Data Dimensions"] == "(2672, 4008)"
        assert meta["nx_meta"]["extensions"]["Facility"] == "MicroLabFacility"
        assert (
            meta["nx_meta"]["extensions"]["Camera/Detector Processing"]
            == "Gain Normalized"
        )

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

        # Test Signal Name extraction (vendor-specific, in extensions)
        assert "extensions" in meta["nx_meta"]
        assert "Signal Name" in meta["nx_meta"]["extensions"]
        assert meta["nx_meta"]["extensions"]["Signal Name"] == "ADF"

        # Test aperture settings extraction (vendor-specific, in extensions)
        assert "Condenser Aperture" in meta["nx_meta"]["extensions"]
        assert meta["nx_meta"]["extensions"]["Condenser Aperture"] == 5
        assert "Objective Aperture" in meta["nx_meta"]["extensions"]
        assert meta["nx_meta"]["extensions"]["Objective Aperture"] == 4
        assert "Selected Area Aperture" in meta["nx_meta"]["extensions"]
        assert meta["nx_meta"]["extensions"]["Selected Area Aperture"] == 0

        # Test dwell_time extraction (core field with EM Glossary name)
        # This was "Sample Time" but is now "dwell_time" in schema
        dwell_time = meta["nx_meta"]["dwell_time"]
        assert isinstance(dwell_time, ureg.Quantity)
        assert float(dwell_time.magnitude) == 16.0
        assert str(dwell_time.units) == "microsecond"

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
        digital_micrograph._logger.setLevel(logging.WARNING)

        # Create a nested dict structure where the extensions dict raises on assignment
        class FailingExtensionsDict(dict):
            def __setitem__(self, key, value):
                # Raise on any key assignment to simulate field injection failure
                msg = "Simulated injection failure"
                raise RuntimeError(msg)

        # Create metadata with pre-existing extensions dict that will fail
        metadata = {"nx_meta": {"extensions": FailingExtensionsDict()}}

        # Call _apply_profile_to_metadata directly
        result = digital_micrograph._apply_profile_to_metadata(
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


class TestDigitalMicrographSchemaValidation:
    """Tests for schema validation and metadata migration in digital_micrograph."""

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

    def test_image_metadata_validates_against_schema(
        self,
        stem_image_dm3,
        mock_instrument_from_filepath,
    ):
        """Test that Image datasets validate against ImageMetadata schema."""
        from nexusLIMS.extractors import parse_metadata

        # Set up instrument
        mock_instrument_from_filepath(make_test_tool())

        # Extract metadata - should not raise validation error
        result, _ = parse_metadata(stem_image_dm3, generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result

        # Verify dataset type is Image
        assert metadata["nx_meta"]["DatasetType"] == "Image"

        # Verify metadata validates against ImageMetadata schema
        from nexusLIMS.schemas.metadata import ImageMetadata

        validated = ImageMetadata.model_validate(metadata["nx_meta"])
        assert validated is not None

    def test_diffraction_metadata_validates_against_schema(
        self,
        jeol3010_diff,
        mock_instrument_from_filepath,
    ):
        """Test that Diffraction datasets validate w/ DiffractionMetadata schema."""
        from nexusLIMS.extractors import parse_metadata

        # Set up JEOL instrument for diffraction file
        mock_instrument_from_filepath(make_jeol_tem())

        # Extract metadata - should not raise validation error
        # jeol3010_diff is a list of file paths
        result, _ = parse_metadata(jeol3010_diff[0], generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result

        # Verify dataset type is Diffraction
        assert metadata["nx_meta"]["DatasetType"] == "Diffraction"

        # Verify metadata validates against DiffractionMetadata schema
        from nexusLIMS.schemas.metadata import DiffractionMetadata

        validated = DiffractionMetadata.model_validate(metadata["nx_meta"])
        assert validated is not None

    def test_core_fields_use_em_glossary_names(
        self,
        stem_image_dm3,
        mock_instrument_from_filepath,
    ):
        """Test that core fields use EM Glossary snake_case names."""
        from nexusLIMS.extractors import parse_metadata

        mock_instrument_from_filepath(make_test_tool())
        result, _ = parse_metadata(stem_image_dm3, generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result
        nx_meta = metadata["nx_meta"]

        # Check for EM Glossary names (not display names)
        # These should be at the top level
        expected_core_fields = [
            "acceleration_voltage",  # Not "Voltage"
            "acquisition_device",  # Not "Acquisition Device"
            "horizontal_field_width",  # Not "Field of View"
            "vertical_field_width",
        ]

        for field in expected_core_fields:
            if field in nx_meta:
                # Field should be at top level
                assert field in nx_meta
                # And should NOT be in extensions
                if "extensions" in nx_meta:
                    assert field not in nx_meta["extensions"]

    def test_vendor_fields_in_extensions(
        self,
        stem_image_dm3,
        mock_instrument_from_filepath,
    ):
        """Test that vendor-specific fields are placed in extensions section."""
        from nexusLIMS.extractors import parse_metadata

        mock_instrument_from_filepath(make_test_tool())
        result, _ = parse_metadata(stem_image_dm3, generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result
        nx_meta = metadata["nx_meta"]

        # Vendor-specific fields should be in extensions
        assert "extensions" in nx_meta
        extensions = nx_meta["extensions"]

        # Check for expected vendor fields
        # These should NOT be at the top level
        vendor_fields = ["Microscope", "GMS Version", "Operator"]

        for field in vendor_fields:
            if field in extensions:
                # Field should be in extensions
                assert field in extensions
                # And should NOT be at top level
                assert field not in nx_meta or field == "extensions"

    def test_camera_length_core_for_diffraction(
        self,
        jeol3010_diff,
        mock_instrument_from_filepath,
    ):
        """Test that camera_length is core field for Diffraction datasets."""
        from nexusLIMS.extractors import parse_metadata

        # Set up JEOL instrument for diffraction file
        mock_instrument_from_filepath(make_jeol_tem())
        # jeol3010_diff is a list of file paths
        result, _ = parse_metadata(jeol3010_diff[0], generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result
        nx_meta = metadata["nx_meta"]

        # For Diffraction datasets, camera_length should be at top level
        assert nx_meta["DatasetType"] == "Diffraction"
        if "camera_length" in nx_meta or (
            "extensions" in nx_meta and "STEM Camera Length" in nx_meta["extensions"]
        ):
            # camera_length should be core field for Diffraction
            assert "camera_length" in nx_meta
            # Original field should not be at top level
            assert "STEM Camera Length" not in nx_meta

    def test_camera_length_extension_for_non_diffraction(
        self,
        stem_image_dm3,
        mock_instrument_from_filepath,
    ):
        """Test that STEM Camera Length goes to extensions for non-Diffraction."""
        from nexusLIMS.extractors import parse_metadata

        mock_instrument_from_filepath(make_test_tool())
        result, _ = parse_metadata(stem_image_dm3, generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result
        nx_meta = metadata["nx_meta"]

        # For non-Diffraction datasets, camera_length should NOT be at top level
        assert nx_meta["DatasetType"] != "Diffraction"
        assert "camera_length" not in nx_meta

        # If present, STEM Camera Length should be in extensions
        if "extensions" in nx_meta and "STEM Camera Length" in nx_meta["extensions"]:
            assert "STEM Camera Length" in nx_meta["extensions"]

    def test_extensions_preserved_from_profiles(
        self,
        stem_image_dm3,
        mock_instrument_from_filepath,
        profile_registry_manager,
    ):
        """Test extensions from instrument profiles are preserved during migration."""
        from nexusLIMS.extractors import parse_metadata
        from nexusLIMS.extractors.base import InstrumentProfile

        # Create instrument and profile with extension fields
        instrument = make_test_tool()
        mock_instrument_from_filepath(instrument)

        profile = InstrumentProfile(
            instrument_id=instrument.name,
            extension_fields={
                "facility": "NIST",
                "custom_field": "test_value",
            },
        )
        profile_registry_manager.register(profile)

        # Extract metadata
        result, _ = parse_metadata(stem_image_dm3, generate_preview=False)

        # DM3 files may return a list of metadata dicts for multi-signal files
        metadata = result[0] if isinstance(result, list) else result

        # Extensions from profile should be preserved
        assert "extensions" in metadata["nx_meta"]
        assert metadata["nx_meta"]["extensions"]["facility"] == "NIST"
        assert metadata["nx_meta"]["extensions"]["custom_field"] == "test_value"

    def test_migration_function_field_categorization(self):
        """Test _migrate_to_schema_compliant_metadata categorizes fields correctly."""
        # Test Image dataset
        test_meta = {
            "nx_meta": {
                "DatasetType": "Image",
                "Creation Time": "2025-12-25T10:00:00+00:00",
                "Data Type": "TEM_Imaging",
                # Display names that should be mapped to EM Glossary
                "Voltage": ureg.Quantity(200, "kilovolt"),
                "Horizontal Field Width": ureg.Quantity(10, "micrometer"),
                # Vendor field that should go to extensions
                "Microscope": "TEST Titan",
                "GMS Version": "3.60",
            }
        }

        migrated = digital_micrograph._migrate_to_schema_compliant_metadata(test_meta)

        nx_meta = migrated["nx_meta"]

        # Check EM Glossary names at top level
        assert "acceleration_voltage" in nx_meta
        assert nx_meta["acceleration_voltage"] == ureg.Quantity(200, "kilovolt")
        assert "horizontal_field_width" in nx_meta

        # Display names should not be at top level
        assert "Voltage" not in nx_meta
        assert "Horizonal Field Width" not in nx_meta
        assert "Vertical Field Width" not in nx_meta

        # Vendor fields should be in extensions
        assert "extensions" in nx_meta
        assert "Microscope" in nx_meta["extensions"]
        assert nx_meta["extensions"]["Microscope"] == "TEST Titan"
        assert nx_meta["extensions"]["GMS Version"] == "3.60"

    def test_migration_preserves_existing_extensions(self):
        """Test that migration preserves pre-existing extensions."""
        test_meta = {
            "nx_meta": {
                "DatasetType": "Image",
                "Creation Time": "2025-12-25T10:00:00+00:00",
                "Data Type": "TEM_Imaging",
                "extensions": {
                    "pre_existing_field": "preserved_value",
                },
                "Voltage": ureg.Quantity(200, "kilovolt"),
                "Microscope": "TEST Titan",
            }
        }

        migrated = digital_micrograph._migrate_to_schema_compliant_metadata(test_meta)

        # Pre-existing extension should be preserved
        assert "extensions" in migrated["nx_meta"]
        assert "pre_existing_field" in migrated["nx_meta"]["extensions"]
        assert (
            migrated["nx_meta"]["extensions"]["pre_existing_field"] == "preserved_value"
        )

        # New vendor field should be added
        assert "Microscope" in migrated["nx_meta"]["extensions"]

    def test_validation_enforces_type_specific_schema(
        self, mock_instrument_from_filepath
    ):
        """Test that validation uses type-specific schemas based on DatasetType."""
        from pydantic import ValidationError

        from nexusLIMS.extractors import validate_nx_meta

        mock_instrument_from_filepath(make_test_tool())

        # Valid Image metadata
        valid_image_meta = {
            "nx_meta": {
                "DatasetType": "Image",
                "Creation Time": "2025-12-25T10:00:00+00:00",
                "Data Type": "TEM_Imaging",
                "acceleration_voltage": ureg.Quantity(200, "kilovolt"),
            }
        }

        # Should not raise
        validate_nx_meta(valid_image_meta)

        # Invalid: Image-specific field with wrong type
        invalid_meta = {
            "nx_meta": {
                "DatasetType": "Image",
                "Creation Time": "2025-12-25T10:00:00+00:00",
                "Data Type": "TEM_Imaging",
                "acceleration_voltage": "not a quantity",  # Should be Pint Quantity
            }
        }

        # Should raise ValidationError
        with pytest.raises(ValidationError):
            validate_nx_meta(invalid_meta)

    def test_extensions_allowed_in_all_schemas(self, mock_instrument_from_filepath):
        """Test that extensions section is allowed in all schema types."""
        from nexusLIMS.extractors import validate_nx_meta

        mock_instrument_from_filepath(make_test_tool())

        # Test each dataset type with extensions
        dataset_types = ["Image", "Spectrum", "SpectrumImage", "Diffraction", "Misc"]

        for dataset_type in dataset_types:
            metadata = {
                "nx_meta": {
                    "DatasetType": dataset_type,
                    "Creation Time": "2025-12-25T10:00:00+00:00",
                    "Data Type": "Test_Type",
                    "extensions": {
                        "custom_field": "test_value",
                        "vendor_specific": 123,
                    },
                }
            }

            # Should not raise - extensions allowed in all schemas
            validate_nx_meta(metadata)
