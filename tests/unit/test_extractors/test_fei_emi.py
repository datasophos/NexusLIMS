# pylint: disable=C0116,too-many-public-methods
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors.fei_emi."""

from datetime import datetime as dt
from datetime import timedelta, timezone

import pytest

from nexusLIMS.extractors.plugins import fei_emi
from tests.unit.test_instrument_factory import make_titan_stem, make_titan_tem
from tests.unit.utils import get_full_file_path

# Helper to create timezone-aware datetime for tests
# FEI Titan instruments use UTC-6 (Central Time)
CST = timezone(timedelta(hours=-6))


class TestSerEmiExtractor:  # pylint: disable=too-many-public-methods
    """Tests nexusLIMS.extractors.fei_emi."""

    def test_titan_tem_stem_image_1(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_1_STEM_image_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2018, 11, 13, 15, 2, 43, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Magnification (x)"] == pytest.approx(225000)
        assert meta[0]["nx_meta"]["Mode"] == "STEM nP SA Zoom Diffraction"
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": -0.84,
            "B (°)": 0.0,
            "X (μm)": -194.379,
            "Y (μm)": -130.201,
            "Z (μm)": 128.364,
        }
        assert meta[0]["nx_meta"]["User"] == "USER"
        assert meta[0]["nx_meta"]["C2 Lens (%)"] == pytest.approx(22.133)

    def test_titan_tem_stem_image_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_1_STEM_image_dataZeroed_2.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["Defocus (μm)"] == 0
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert meta[0]["nx_meta"]["Gun Lens"] == 6
        assert meta[0]["nx_meta"]["Gun Type"] == "FEG"
        assert meta[0]["nx_meta"]["C2 Aperture (μm)"] == pytest.approx(50.0)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2018, 11, 13, 15, 2, 43, tzinfo=CST).isoformat()
        )

    def test_titan_tem_single_stem_image(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_2_HAADF_STEM_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 6, 28, 15, 53, 31, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["C1 Aperture (μm)"] == 2000
        assert meta[0]["nx_meta"]["Mode"] == "STEM nP SA Zoom Image"
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 0.0,
            "B (°)": 0.0,
            "X (μm)": -31.415,
            "Y (μm)": 42.773,
            "Z (μm)": -10.576,
        }
        assert meta[0]["nx_meta"]["SA Aperture"] == "retracted"
        assert meta[0]["ObjectInfo"]["Uuid"] == "cb7d82b8-5405-42fc-aa71-7680721a6e32"

    def test_titan_tem_eds_spectrum_image(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_3_eds_spectrum_image_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(9, 10, 3993)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 7, 17, 13, 50, 22, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Microscope Accelerating Voltage (V)"] == 300000
        assert meta[0]["nx_meta"]["Camera Length (m)"] == pytest.approx(0.195)
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 9.57,
            "B (°)": 0.0,
            "X (μm)": -505.273,
            "Y (μm)": -317.978,
            "Z (μm)": 15.525,
        }
        assert meta[0]["nx_meta"]["Spot Size"] == 6
        assert meta[0]["nx_meta"]["Magnification (x)"] == pytest.approx(14000.0)

    def test_titan_tem_eds_line_scan_1(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_4_eds_line_scan_1_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(100, 3993)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 11, 1, 15, 42, 16, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Dwell Time Path (s)"] == 6e-6
        assert meta[0]["nx_meta"]["Defocus (μm)"] == -1.12
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 7.32,
            "B (°)": -3.57,
            "X (μm)": 20.528,
            "Y (μm)": 243.295,
            "Z (μm)": 45.491,
        }
        assert meta[0]["nx_meta"]["STEM Rotation Correction (°)"] == -12.3
        assert meta[0]["nx_meta"]["Frame Time (s)"] == pytest.approx(1.88744)

    def test_titan_tem_eds_line_scan_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_4_eds_line_scan_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(6, 3993)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 7, 17, 15, 43, 21, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Diffraction Lens (%)"] == pytest.approx(34.922)
        assert meta[0]["nx_meta"]["Defocus (μm)"] == -0.145
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 9.57,
            "B (°)": 0,
            "X (μm)": -565.778,
            "Y (μm)": -321.364,
            "Z (μm)": 17.126,
        }
        assert meta[0]["nx_meta"]["Manufacturer"] == "FEI (ISAS)"
        assert (
            meta[0]["nx_meta"]["Microscope"]
            == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )

    def test_titan_tem_eds_spectrum(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_5_eds_spectrum_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_EDS_Spectrum"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(3993,)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 12, 11, 16, 2, 38, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Energy Resolution (eV)"] == 10
        assert meta[0]["nx_meta"]["Integration Time (s)"] == 25
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 0,
            "B (°)": 0.11,
            "X (μm)": -259.807,
            "Y (μm)": 18.101,
            "Z (μm)": 7.06,
        }
        assert meta[0]["nx_meta"]["Manufacturer"] == "EDAX"
        assert meta[0]["nx_meta"]["Emission (μA)"] == pytest.approx(145.0)

    def test_titan_tem_diffraction(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_6_diffraction_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(2048, 2048)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2018, 10, 30, 17, 1, 3, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Camera Name Path"] == "BM-UltraScan"
        assert meta[0]["nx_meta"]["Camera Length (m)"] == pytest.approx(0.3)
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": -28.59,
            "B (°)": 0.0,
            "X (μm)": -91.527,
            "Y (μm)": -100.11,
            "Z (μm)": 210.133,
        }
        assert meta[0]["nx_meta"]["Manufacturer"] == "FEI"
        assert meta[0]["nx_meta"]["Extraction Voltage (V)"] == 4400

    def test_titan_tem_image_stack_1(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_7_image_stack_1_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(20, 2048, 2048)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 3, 28, 21, 14, 16, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Dwell Time Path (s)"] == pytest.approx(0.000002)
        assert meta[0]["nx_meta"]["C2 Aperture (μm)"] == pytest.approx(50.0)
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 2.9,
            "B (°)": 0.0,
            "X (μm)": -207.808,
            "Y (μm)": 111.327,
            "Z (μm)": 74.297,
        }
        assert meta[0]["nx_meta"]["Gun Type"] == "FEG"
        assert meta[0]["nx_meta"]["Diffraction Lens (%)"] == pytest.approx(38.91)

    def test_titan_tem_image_stack_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_7_image_stack_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(20, 2048, 2048)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2019, 3, 28, 22, 41, 0, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Frame Time (s)"] == 10
        assert meta[0]["nx_meta"]["C1 Aperture (μm)"] == 2000
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 4.53,
            "B (°)": 0.0,
            "X (μm)": -207.438,
            "Y (μm)": 109.996,
            "Z (μm)": 76.932,
        }
        assert meta[0]["nx_meta"]["Gun Lens"] == 5
        assert "Tecnai Filter" not in meta[0]["nx_meta"]

    def test_titan_tem_diffraction_stack(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_7_diffraction_stack_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(33, 1024, 1024)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2018, 12, 13, 13, 33, 47, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["C2 Lens (%)"] == pytest.approx(43.465)
        assert meta[0]["nx_meta"]["C2 Aperture (μm)"] == 100
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 1.86,
            "B (°)": 0.0,
            "X (μm)": -179.33,
            "Y (μm)": -31.279,
            "Z (μm)": -158.512,
        }
        assert meta[0]["nx_meta"]["OBJ Aperture"] == "retracted"
        assert meta[0]["nx_meta"]["Mode"] == "TEM uP SA Zoom Diffraction"

    def test_titan_tem_emi_list_image_spectrum_1(self, fei_ser_files):
        test_file_1 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI1_dataZeroed_1.ser",
            fei_ser_files,
        )
        test_file_2 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI1_dataZeroed_2.ser",
            fei_ser_files,
        )
        meta_1 = fei_emi.get_ser_metadata(test_file_1)
        meta_2 = fei_emi.get_ser_metadata(test_file_2)

        assert meta_1[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta_1[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta_1[0]["nx_meta"]["Data Dimensions"] == "(2048, 2048)"
        assert meta_1[0]["nx_meta"]["High Tension (kV)"] == 300
        assert meta_1[0]["nx_meta"]["Gun Lens"] == 6
        assert meta_1[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 9.21,
            "B (°)": 0.0,
            "X (μm)": -202.298,
            "Y (μm)": -229.609,
            "Z (μm)": 92.45,
        }

        assert meta_2[0]["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta_2[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(3993,)"
        assert meta_2[0]["nx_meta"]["Beam Position (μm)"] == "(-0.99656, 0.74289)"
        assert meta_2[0]["nx_meta"]["Diffraction Lens (%)"] == pytest.approx(37.347)
        assert meta_2[0]["nx_meta"]["Objective Lens (%)"] == pytest.approx(87.987)
        assert meta_2[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 9.21,
            "B (°)": 0.0,
            "X (μm)": -202.296,
            "Y (μm)": -229.616,
            "Z (μm)": 92.45,
        }

    def test_titan_tem_emi_list_image_spectrum_2(self, fei_ser_files):
        test_file_1 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI2_dataZeroed_1.ser",
            fei_ser_files,
        )
        test_file_2 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI2_dataZeroed_2.ser",
            fei_ser_files,
        )
        test_file_3 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI2_dataZeroed_3.ser",
            fei_ser_files,
        )
        test_file_4 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI2_dataZeroed_4.ser",
            fei_ser_files,
        )
        test_file_5 = get_full_file_path(
            "Titan_TEM_8_emi_list_eds_SI2_dataZeroed_5.ser",
            fei_ser_files,
        )
        meta_1 = fei_emi.get_ser_metadata(test_file_1)
        meta_2 = fei_emi.get_ser_metadata(test_file_2)
        meta_3 = fei_emi.get_ser_metadata(test_file_3)
        meta_4 = fei_emi.get_ser_metadata(test_file_4)
        meta_5 = fei_emi.get_ser_metadata(test_file_5)

        assert meta_1[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta_1[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta_1[0]["nx_meta"]["Data Dimensions"] == "(512, 512)"
        assert (
            meta_1[0]["nx_meta"]["Creation Time"]
            == dt(2019, 6, 13, 19, 52, 6, tzinfo=CST).isoformat()
        )
        assert meta_1[0]["nx_meta"]["Diffraction Lens (%)"] == pytest.approx(37.347)
        assert meta_1[0]["nx_meta"]["Spot Size"] == 7
        assert meta_1[0]["nx_meta"]["Manufacturer"] == "FEI (ISAS)"
        assert meta_1[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 9.21,
            "B (°)": 0.0,
            "X (μm)": -202.296,
            "Y (μm)": -229.618,
            "Z (μm)": 92.45,
        }

        # the remaining spectra don't have metadata, only a UUID
        for meta, uuid in zip(
            [meta_2, meta_3, meta_4, meta_5],
            [
                "5bb5972e-276a-40c3-87c5-eb9ef3f4cb12",
                "36c60afe-f7e4-4356-b351-f329347fb464",
                "76e6b908-f988-48cb-adab-2c64fd6de24e",
                "9eabdd9d-6cb7-41c3-b234-bb44670a14f6",
            ],
        ):
            assert meta[0]["nx_meta"]["DatasetType"] == "Spectrum"
            # this might be incorrect, but we have no way of determining
            assert meta[0]["nx_meta"]["Data Type"] == "TEM_EDS_Spectrum"
            assert meta[0]["nx_meta"]["Data Dimensions"] == "(3993,)"
            assert meta[0]["ObjectInfo"]["Uuid"] == uuid
            assert "Manufacturer" not in meta[0]["nx_meta"]

    def test_titan_tem_emi_list_haadf_diff_stack(self, fei_ser_files):
        test_file_1 = get_full_file_path(
            "Titan_TEM_9_list_haadf_diff_stack_dataZeroed_1.ser",
            fei_ser_files,
        )
        test_file_2 = get_full_file_path(
            "Titan_TEM_9_list_haadf_diff_stack_dataZeroed_2.ser",
            fei_ser_files,
        )
        meta_1 = fei_emi.get_ser_metadata(test_file_1)
        meta_2 = fei_emi.get_ser_metadata(test_file_2)

        assert meta_1[0]["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta_1[0]["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta_1[0]["nx_meta"]["Data Dimensions"] == "(77, 1024, 1024)"
        assert (
            meta_1[0]["nx_meta"]["Creation Time"]
            == dt(2018, 9, 21, 14, 17, 25, tzinfo=CST).isoformat()
        )
        assert meta_1[0]["nx_meta"]["Binning"] == 2
        assert meta_1[0]["nx_meta"]["Tecnai Filter"]["Mode"] == "Spectroscopy"
        assert meta_1[0]["nx_meta"]["Tecnai Filter"]["Selected Aperture"] == "3mm"
        assert meta_1[0]["nx_meta"]["Image Shift X (μm)"] == pytest.approx(0.003)
        assert meta_1[0]["nx_meta"]["Mode"] == "TEM uP SA Zoom Diffraction"
        assert meta_1[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 0,
            "B (°)": 0,
            "X (μm)": -135.782,
            "Y (μm)": 637.285,
            "Z (μm)": 77.505,
        }

        assert meta_2[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta_2[0]["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(4, 1024, 1024)"
        assert (
            meta_2[0]["nx_meta"]["Creation Time"]
            == dt(2018, 9, 21, 14, 25, 11, tzinfo=CST).isoformat()
        )
        assert meta_2[0]["nx_meta"]["Dwell Time Path (s)"] == pytest.approx(0.8)
        assert meta_2[0]["nx_meta"]["Emission (μA)"] == pytest.approx(135.0)
        assert meta_2[0]["nx_meta"]["Magnification (x)"] == 10000
        assert meta_2[0]["nx_meta"]["Image Shift X (μm)"] == pytest.approx(0.003)
        assert meta_2[0]["nx_meta"]["Mode"] == "TEM uP SA Zoom Image"
        assert meta_2[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 0,
            "B (°)": 0,
            "X (μm)": -135.787,
            "Y (μm)": 637.281,
            "Z (μm)": 77.505,
        }

    def test_titan_tem_emi_list_four_images(self, fei_ser_files):
        test_file_1 = get_full_file_path(
            "Titan_TEM_10_emi_list_4_images_dataZeroed_1.ser",
            fei_ser_files,
        )
        test_file_2 = get_full_file_path(
            "Titan_TEM_10_emi_list_4_images_dataZeroed_2.ser",
            fei_ser_files,
        )
        test_file_3 = get_full_file_path(
            "Titan_TEM_10_emi_list_4_images_dataZeroed_3.ser",
            fei_ser_files,
        )
        test_file_4 = get_full_file_path(
            "Titan_TEM_10_emi_list_4_images_dataZeroed_4.ser",
            fei_ser_files,
        )

        for meta in [
            fei_emi.get_ser_metadata(f)
            for f in [test_file_1, test_file_2, test_file_3, test_file_4]
        ]:
            assert meta[0]["nx_meta"]["DatasetType"] == "Image"
            assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
            assert meta[0]["nx_meta"]["Data Dimensions"] == "(2048, 2048)"

            assert (
                meta[0]["nx_meta"]["Creation Time"]
                == dt(2018, 11, 14, 17, 9, 55, tzinfo=CST).isoformat()
            )
            assert meta[0]["nx_meta"]["Frame Time (s)"] == pytest.approx(30.199)
            assert (
                meta[0]["nx_meta"]["Tecnai Filter"]["Selected Dispersion (eV/Channel)"]
                == 0.1
            )
            assert (
                meta[0]["nx_meta"]["Microscope"] == "Microscope Titan 300 kV "
                "ABCD1 SuperTwin"
            )
            assert meta[0]["nx_meta"]["Mode"] == "STEM nP SA Zoom Diffraction"
            assert meta[0]["nx_meta"]["Spot Size"] == 8
            assert meta[0]["nx_meta"]["Gun Lens"] == 5
            assert meta[0]["nx_meta"]["Gun Type"] == "FEG"
            assert meta[0]["nx_meta"]["Stage Position"] == {
                "A (°)": 0,
                "B (°)": 0,
                "X (μm)": -116.939,
                "Y (μm)": -65.107,
                "Z (μm)": 79.938,
            }

    def test_643_stem_image(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_1_stem_image_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2011, 11, 16, 9, 46, 13, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["C2 Lens (%)"] == pytest.approx(8.967)
        assert meta[0]["nx_meta"]["C2 Aperture (μm)"] == 40
        assert meta[0]["nx_meta"]["Stage Position"] == {
            "A (°)": 0,
            "B (°)": 0,
            "X (μm)": 46.293,
            "Y (μm)": -14.017,
            "Z (μm)": -127.155,
        }
        assert meta[0]["nx_meta"]["STEM Rotation Correction (°)"] == pytest.approx(12.4)
        assert meta[0]["nx_meta"]["User"] == "OPERATOR__"
        assert (
            meta[0]["nx_meta"]["Microscope"]
            == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )

    def test_643_eds_and_eels_spectrum_image(self, fei_ser_files):
        test_file_eds = get_full_file_path(
            "Titan_STEM_2_spectrum_image_dataZeroed_1.ser",
            fei_ser_files,
        )
        test_file_eels = get_full_file_path(
            "Titan_STEM_2_spectrum_image_dataZeroed_2.ser",
            fei_ser_files,
        )
        meta_1 = fei_emi.get_ser_metadata(test_file_eds)
        meta_2 = fei_emi.get_ser_metadata(test_file_eels)

        assert meta_1[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta_1[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta_1[0]["nx_meta"]["Data Dimensions"] == "(40, 70, 4000)"
        assert (
            meta_1[0]["nx_meta"]["Creation Time"]
            == dt(2011, 11, 16, 16, 8, 54, tzinfo=CST).isoformat()
        )
        assert meta_1[0]["nx_meta"]["Frame Time (s)"] == 10
        assert meta_1[0]["nx_meta"]["Emission (μA)"] == pytest.approx(237.3)
        assert meta_1[0]["nx_meta"]["Tecnai Filter"]["Selected Aperture"] == "2.5 mm"
        assert meta_1[0]["nx_meta"]["Tecnai Filter"]["Slit State"] == "Retracted"

        assert meta_2[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta_2[0]["nx_meta"]["Data Type"] == "STEM_EELS_Spectrum_Imaging"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(40, 70, 2048)"
        assert (
            meta_2[0]["nx_meta"]["Creation Time"]
            == dt(2011, 11, 16, 16, 32, 27, tzinfo=CST).isoformat()
        )
        assert meta_2[0]["nx_meta"]["Energy Resolution (eV)"] == 10
        assert meta_2[0]["nx_meta"]["Integration Time (s)"] == pytest.approx(0.5)
        assert meta_2[0]["nx_meta"]["Extraction Voltage (V)"] == 4500
        assert meta_2[0]["nx_meta"]["Camera Length (m)"] == pytest.approx(0.06)
        assert meta_2[0]["nx_meta"]["C2 Lens (%)"] == pytest.approx(8.967)
        assert meta_2[0]["nx_meta"]["C3 Aperture (μm)"] == 1000

    def test_643_image_stack(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_3_image_stack_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(5, 1024, 1024)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2012, 1, 31, 13, 43, 40, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Frame Time (s)"] == pytest.approx(2.0)
        assert meta[0]["nx_meta"]["C1 Aperture (μm)"] == 2000
        assert meta[0]["nx_meta"]["C2 Lens (%)"] == pytest.approx(14.99)
        assert meta[0]["nx_meta"]["Defocus (μm)"] == -2.593
        assert (
            meta[0]["nx_meta"]["Microscope"]
            == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )
        assert meta[0]["nx_meta"]["Mode"] == "STEM nP SA Zoom Diffraction"
        assert meta[0]["nx_meta"]["Magnification (x)"] == 80000

    def test_643_image_stack_2_newer(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_4_image_stack_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(2, 512, 512)"
        assert (
            meta[0]["nx_meta"]["Creation Time"]
            == dt(2020, 3, 11, 16, 33, 38, tzinfo=CST).isoformat()
        )
        assert meta[0]["nx_meta"]["Frame Time (s)"] == pytest.approx(6.34179)
        assert meta[0]["nx_meta"]["Dwell Time Path (s)"] == pytest.approx(0.000001)
        assert meta[0]["nx_meta"]["C2 Aperture (μm)"] == 10
        assert meta[0]["nx_meta"]["C3 Lens (%)"] == -37.122
        assert meta[0]["nx_meta"]["Defocus (μm)"] == -0.889
        assert (
            meta[0]["nx_meta"]["Microscope"]
            == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )
        assert meta[0]["nx_meta"]["Mode"] == "STEM nP SA Zoom Diffraction"
        assert meta[0]["nx_meta"]["Magnification (x)"] == 80000
        assert meta[0]["nx_meta"]["STEM Rotation (°)"] == -90.0

    def test_no_emi_error(self, caplog, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_12_no_accompanying_emi_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)

        assert "Extractor Warning" in meta[0]["nx_meta"]
        assert (
            "NexusLIMS could not find a corresponding .emi metadata "
            "file for this .ser file" in meta[0]["nx_meta"]["Extractor Warning"]
        )
        assert (
            "NexusLIMS could not find a corresponding .emi metadata "
            "file for this .ser file" in caplog.text
        )
        assert meta[0]["nx_meta"]["emi Filename"] is None

    def test_unreadable_ser(self, caplog, fei_ser_files):
        # if the ser is unreadable, neither the emi or the ser can be read,
        # so we will get the bare minimum of metadata back from the parser
        test_file = get_full_file_path(
            "Titan_TEM_13_unreadable_ser_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert "nx_meta" in meta[0]
        assert meta[0]["nx_meta"]["Data Type"] == "Unknown"
        assert meta[0]["nx_meta"]["DatasetType"] == "Misc"
        assert "Creation Time" in meta[0]["nx_meta"]
        assert "13_unreadable_ser.emi" in meta[0]["nx_meta"]["emi Filename"]
        assert (
            "The .emi metadata file associated with this .ser file could "
            "not be opened by NexusLIMS." in caplog.text
        )
        assert (
            "The .ser file could not be opened (perhaps file is "
            "corrupted?)" in caplog.text
        )

    @staticmethod
    def _helper_test(caplog, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_14_unreadable_emi_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert "nx_meta" in meta[0]
        assert "ser_header_parameters" in meta[0]
        assert (
            "The .emi metadata file associated with this .ser file could "
            "not be opened by NexusLIMS" in caplog.text
        )
        assert (
            "The .emi metadata file associated with this .ser file could "
            "not be opened by NexusLIMS" in meta[0]["nx_meta"]["Extractor Warning"]
        )
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        return meta

    def test_unreadable_emi(self, caplog, fei_ser_files):
        # if emi is unreadable, we should still get basic metadata from the ser
        meta = TestSerEmiExtractor._helper_test(caplog, fei_ser_files)
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_Imaging"

    def test_instr_mode_parsing_with_unreadable_emi_tem(
        self,
        monkeypatch,
        caplog,
        fei_ser_files,
    ):
        """Test imaging mode parsing when EMI is unreadable (TEM instrument)."""
        # if emi is unreadable, we should get imaging mode based off
        # instrument, but testing directory doesn't allow proper handling of
        # this, so monkeypatch get_instr_from_filepath
        monkeypatch.setattr(
            fei_emi,
            "get_instr_from_filepath",
            lambda _: make_titan_tem(),
        )
        meta = TestSerEmiExtractor._helper_test(caplog, fei_ser_files)
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_Imaging"

    def test_instr_mode_parsing_with_unreadable_emi_stem(
        self,
        monkeypatch,
        caplog,
        fei_ser_files,
    ):
        """Test imaging mode parsing when EMI is unreadable (STEM instrument)."""
        # if emi is unreadable, we should get imaging mode based off
        # instrument, but testing directory doesn't allow proper handling of
        # this, so monkeypatch get_instr_from_filepath
        monkeypatch.setattr(
            fei_emi,
            "get_instr_from_filepath",
            lambda _: make_titan_stem(),
        )
        meta = TestSerEmiExtractor._helper_test(caplog, fei_ser_files)
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
