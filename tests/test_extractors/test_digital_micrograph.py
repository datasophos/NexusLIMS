# pylint: disable=C0116
# ruff: noqa: D102, PLR2004, DTZ001

"""Tests for nexusLIMS.extractors.digital_micrograph."""

from pathlib import Path

import pytest

from nexusLIMS.extractors import digital_micrograph
from nexusLIMS.extractors.utils import _try_decimal, _zero_data_in_dm3

from ..test_instrument_factory import (
    make_jeol_tem,
    make_test_tool,
    make_titan_stem,
    make_titan_tem,
)


class TestDigitalMicrographExtractor:
    """Tests nexusLIMS.extractors.digital_micrograph."""

    def test_corrupted_file(self, corrupted_file):
        assert digital_micrograph.get_dm3_metadata(corrupted_file) is None

    def test_dm3_list_file(self, list_signal, mock_instrument_from_filepath):
        """Test DM3 metadata extraction from list signal file.

        This test now uses the instrument factory instead of relying on
        specific database entries, making dependencies explicit.
        """
        # Set up instrument for this test
        mock_instrument_from_filepath(make_test_tool())

        metadata = digital_micrograph.get_dm3_metadata(list_signal[0])

        assert metadata is not None
        assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert metadata["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert metadata["nx_meta"]["Microscope"] == "TEST Titan_______"
        assert metadata["nx_meta"]["Voltage"] == pytest.approx(300000.0)

    def test_dm3_diffraction(
        self,
        stem_diff,
        opmode_diff,
        mock_instrument_from_filepath,
    ):
        """Test DM3 diffraction metadata extraction from Titan TEM."""
        mock_instrument_from_filepath(make_titan_tem())

        meta = digital_micrograph.get_dm3_metadata(stem_diff[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "STEM_Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Voltage"] == pytest.approx(300000.0)

        meta = digital_micrograph.get_dm3_metadata(opmode_diff[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Voltage"] == pytest.approx(300000.0)

    def test_titan_dm3_eels(
        self,
        eels_proc_1_titan,
        eels_si_drift,
        tecnai_mag,
        mock_instrument_from_filepath,
    ):
        """Test DM3 EELS metadata extraction from Titan TEM."""
        mock_instrument_from_filepath(make_titan_tem())

        meta = digital_micrograph.get_dm3_metadata(eels_proc_1_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Voltage"] == pytest.approx(300000.0)
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Aligned parent SI By Peak, Extracted from SI"
        )
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "2mm"

        meta = digital_micrograph.get_dm3_metadata(eels_si_drift[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Voltage"] == pytest.approx(300000.0)
        assert meta["nx_meta"]["EELS"][
            "Convergence semi-angle (mrad)"
        ] == pytest.approx(10.0)
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "2mm"
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 100 seconds"
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Pixel time (s)"] == pytest.approx(
            0.05,
        )

        meta = digital_micrograph.get_dm3_metadata(tecnai_mag[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta["nx_meta"]["Imaging Mode"] == "IMAGING"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert meta["nx_meta"]["Indicated Magnification"] == pytest.approx(8100.0)
        assert meta["nx_meta"]["Tecnai User"] == "USER"
        assert meta["nx_meta"]["Tecnai Mode"] == "TEM uP SA Zoom Image"

    def test_titan_stem_dm3(
        self,
        eftem_diff,
        eds_si_titan,
        stem_stack_titan,
        mock_instrument_from_filepath,
    ):
        """Test DM3 metadata extraction from a Titan STEM."""
        mock_instrument_from_filepath(make_titan_stem())

        meta = digital_micrograph.get_dm3_metadata(eftem_diff[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "TEM_EFTEM_Diffraction"
        assert meta["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta["nx_meta"]["Imaging Mode"] == "EFTEM DIFFRACTION"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan_______"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(5.0)
        assert meta["nx_meta"]["EELS"]["Spectrometer Aperture label"] == "5 mm"

        meta = digital_micrograph.get_dm3_metadata(eds_si_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "EDS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Analytic Signal"] == "X-ray"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum image"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(77.0)
        assert meta["nx_meta"]["EDS"]["Real time (SI Average)"] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        assert meta["nx_meta"]["EDS"]["Live time (SI Average)"] == pytest.approx(
            0.9696700292825698,
            0.1,
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Pixel time (s)"] == pytest.approx(
            1.0,
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Spatial Sampling (Horizontal)"] == 100
        )

        meta = digital_micrograph.get_dm3_metadata(stem_stack_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        assert meta["nx_meta"]["Acquisition Device"] == "DigiScan"
        assert meta["nx_meta"]["Cs(mm)"] == pytest.approx(1.0)
        assert meta["nx_meta"]["Data Dimensions"] == "(12, 1024, 1024)"
        assert meta["nx_meta"]["Indicated Magnification"] == pytest.approx(7200000.0)
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(100.0)

    def test_titan_stem_dm3_eels(
        self,
        eels_si_titan,
        eels_proc_int_bg_titan,
        eels_proc_thick_titan,
        eels_si_drift_titan,
        mock_instrument_from_filepath,
    ):
        """Test DM3 EELS metadata extraction from Titan STEM."""
        mock_instrument_from_filepath(make_titan_stem())

        meta = digital_micrograph.get_dm3_metadata(eels_si_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Imaging Mode"] == "DIFFRACTION"
        assert meta["nx_meta"]["Operation Mode"] == "SCANNING"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(60.0)
        assert meta["nx_meta"]["EELS"][
            "Convergence semi-angle (mrad)"
        ] == pytest.approx(13.0)
        assert meta["nx_meta"]["EELS"]["Exposure (s)"] == pytest.approx(0.5)
        assert meta["nx_meta"]["Spectrum Imaging"]["Pixel time (s)"] == pytest.approx(
            0.5,
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "LineScan"
        assert meta["nx_meta"]["Spectrum Imaging"]["Acquisition Duration (s)"] == 605

        meta = digital_micrograph.get_dm3_metadata(eels_proc_int_bg_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Image"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(48.0)
        assert meta["nx_meta"]["EELS"]["Background Removal Model"] == "Power Law"
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Background Removal, Signal Integration"
        )

        meta = digital_micrograph.get_dm3_metadata(eels_proc_thick_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "STEM_EELS"
        assert meta["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(60.0)
        assert meta["nx_meta"]["EELS"]["Exposure (s)"] == pytest.approx(0.05)
        assert meta["nx_meta"]["EELS"]["Integration time (s)"] == pytest.approx(0.25)
        assert (
            meta["nx_meta"]["EELS"]["Processing Steps"]
            == "Calibrated Post-acquisition, Compute Thickness"
        )
        assert meta["nx_meta"]["EELS"]["Thickness (absolute) [nm]"] == pytest.approx(
            85.29884338378906,
            0.1,
        )

        meta = digital_micrograph.get_dm3_metadata(eels_si_drift_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "EELS_Spectrum_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta["nx_meta"]["Analytic Signal"] == "EELS"
        assert meta["nx_meta"]["Analytic Format"] == "Spectrum image"
        assert meta["nx_meta"]["Analytic Acquisition Mode"] == "Parallel dispersive"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(100.0)
        assert meta["nx_meta"]["EELS"]["Exposure (s)"] == pytest.approx(0.5)
        assert meta["nx_meta"]["EELS"]["Number of frames"] == 1
        assert meta["nx_meta"]["Spectrum Imaging"]["Acquisition Duration (s)"] == 2173
        assert (
            meta["nx_meta"]["Spectrum Imaging"]["Artefact Correction"]
            == "Spatial drift correction every 1 row"
        )
        assert meta["nx_meta"]["Spectrum Imaging"]["Scan Mode"] == "2D Array"

    def test_jeol3010_dm3(self, jeol3010_diff, mock_instrument_from_filepath):
        """Test DM3 metadata extraction from JEOL 3010 TEM file."""
        # Set up JEOL 3010 instrument for this test
        mock_instrument_from_filepath(make_jeol_tem())

        meta = digital_micrograph.get_dm3_metadata(jeol3010_diff[0])
        assert meta is not None
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

        meta_in = digital_micrograph.get_dm3_metadata(input_path)
        meta_3 = digital_micrograph.get_dm3_metadata(fname_3)

        # Creation times will be different, so remove that metadata
        assert meta_in is not None
        assert meta_3 is not None
        del meta_in["nx_meta"]["Creation Time"]
        del meta_3["nx_meta"]["Creation Time"]

        # All other metadata should be equal
        assert meta_in == meta_3

        for filename in [fname_1, fname_2, fname_3]:
            filename.unlink(missing_ok=True)
