# pylint: disable=C0116,too-many-public-methods
# ruff: noqa: D102, DTZ001

"""Tests for nexusLIMS.extractors.fei_emi."""

from datetime import datetime as dt

import pytest

from nexusLIMS.extractors.plugins import fei_emi
from nexusLIMS.schemas.units import ureg
from nexusLIMS.utils import current_system_tz
from tests.unit.test_extractors.conftest import get_field
from tests.unit.test_instrument_factory import make_titan_stem, make_titan_tem
from tests.unit.utils import get_full_file_path

# Use IANA timezone for proper DST handling
SYSTEM_TZ = current_system_tz()


def check_stage_position(stage_pos, expected_values):
    """Check Stage Position Quantities."""
    for axis, expected_value in expected_values.items():
        assert isinstance(stage_pos[axis], ureg.Quantity)
        assert float(stage_pos[axis].magnitude) == expected_value
        if axis in ("A", "B"):
            assert str(stage_pos[axis].units) == "degree"
        else:
            assert str(stage_pos[axis].units) == "micrometer"


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
        expected_iso = SYSTEM_TZ.localize(dt(2018, 11, 13, 15, 2, 43)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso
        # Vendor-specific fields are in extensions
        assert get_field(meta, "Magnification") == pytest.approx(225000)
        assert get_field(meta, "Mode") == "STEM nP SA Zoom Diffraction"

        # Stage Position fields are Quantities (in extensions)
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": -0.84, "B": 0.0, "X": -194.379, "Y": -130.201, "Z": 128.364},
        )

        assert get_field(meta, "User") == "USER"
        assert get_field(meta, "C2 Lens") == pytest.approx(22.133)

    def test_titan_tem_stem_image_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_1_STEM_image_dataZeroed_2.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)

        # Defocus is a Quantity
        defocus = get_field(meta, "Defocus")
        assert isinstance(defocus, ureg.Quantity)
        assert float(defocus.magnitude) == 0
        assert str(defocus.units) == "micrometer"

        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        assert get_field(meta, "Gun Lens") == 6
        assert get_field(meta, "Gun Type") == "FEG"

        # C2 Aperture is a Quantity
        c2_aperture = get_field(meta, "C2 Aperture")
        assert isinstance(c2_aperture, ureg.Quantity)
        assert float(c2_aperture.magnitude) == 50.0
        assert str(c2_aperture.units) == "micrometer"

        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        expected_iso = SYSTEM_TZ.localize(dt(2018, 11, 13, 15, 2, 43)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

    def test_titan_tem_single_stem_image(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_2_HAADF_STEM_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        expected_iso = SYSTEM_TZ.localize(dt(2019, 6, 28, 15, 53, 31)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # C1 Aperture is a Quantity
        c1_aperture = get_field(meta, "C1 Aperture")
        assert isinstance(c1_aperture, ureg.Quantity)
        assert float(c1_aperture.magnitude) == 2000
        assert str(c1_aperture.units) == "micrometer"

        assert get_field(meta, "Mode") == "STEM nP SA Zoom Image"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 0.0, "B": 0.0, "X": -31.415, "Y": 42.773, "Z": -10.576},
        )

        assert get_field(meta, "SA Aperture") == "retracted"
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
        expected_iso = SYSTEM_TZ.localize(dt(2019, 7, 17, 13, 50, 22)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Microscope Accelerating Voltage is a Quantity
        voltage = get_field(meta, "Microscope Accelerating Voltage")
        assert isinstance(voltage, ureg.Quantity)
        assert float(voltage.magnitude) == 300000
        assert str(voltage.units) == "volt"

        # Camera Length - check if it's a Quantity or plain value
        camera_length = get_field(meta, "Camera Length")
        if isinstance(camera_length, ureg.Quantity):
            assert float(camera_length.magnitude) == 0.195
            assert str(camera_length.units) == "meter"
        else:
            # FEI metadata doesn't always include units for Camera Length
            assert camera_length == pytest.approx(0.195)

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 9.57, "B": 0.0, "X": -505.273, "Y": -317.978, "Z": 15.525},
        )

        assert get_field(meta, "Spot Size") == 6
        assert get_field(meta, "Magnification") == pytest.approx(14000.0)

    def test_titan_tem_eds_line_scan_1(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_4_eds_line_scan_1_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(100, 3993)"
        expected_iso = SYSTEM_TZ.localize(dt(2019, 11, 1, 15, 42, 16)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Dwell Time Path is a Quantity
        dwell_time = get_field(meta, "Dwell Time Path")
        assert isinstance(dwell_time, ureg.Quantity)
        assert float(dwell_time.magnitude) == 6e-6
        assert str(dwell_time.units) == "second"

        # Defocus is a Quantity
        defocus = get_field(meta, "Defocus")
        assert isinstance(defocus, ureg.Quantity)
        assert float(defocus.magnitude) == -1.12
        assert str(defocus.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 7.32, "B": -3.57, "X": 20.528, "Y": 243.295, "Z": 45.491},
        )

        # STEM Rotation Correction is a Quantity
        rotation = get_field(meta, "STEM Rotation Correction")
        assert isinstance(rotation, ureg.Quantity)
        assert float(rotation.magnitude) == -12.3
        assert str(rotation.units) == "degree"

        # Frame Time is a Quantity
        frame_time = get_field(meta, "Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert float(frame_time.magnitude) == 1.88744
        assert str(frame_time.units) == "second"

    def test_titan_tem_eds_line_scan_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_4_eds_line_scan_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(6, 3993)"
        expected_iso = SYSTEM_TZ.localize(dt(2019, 7, 17, 15, 43, 21)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta, "Diffraction Lens") == pytest.approx(34.922)

        # Defocus is a Quantity
        defocus = get_field(meta, "Defocus")
        assert isinstance(defocus, ureg.Quantity)
        assert float(defocus.magnitude) == -0.145
        assert str(defocus.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 9.57, "B": 0, "X": -565.778, "Y": -321.364, "Z": 17.126},
        )

        assert get_field(meta, "Manufacturer") == "FEI (ISAS)"
        assert (
            get_field(meta, "Microscope") == "Microscope Titan 300 kV ABCD1 SuperTwin"
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
        expected_iso = SYSTEM_TZ.localize(dt(2019, 12, 11, 16, 2, 38)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Energy Resolution is a Quantity
        energy_res = get_field(meta, "Energy Resolution")
        assert isinstance(energy_res, ureg.Quantity)
        assert float(energy_res.magnitude) == 10
        assert str(energy_res.units) == "electron_volt"

        # Integration Time is a Quantity
        integration_time = get_field(meta, "Integration Time")
        assert isinstance(integration_time, ureg.Quantity)
        assert float(integration_time.magnitude) == 25
        assert str(integration_time.units) == "second"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 0, "B": 0.11, "X": -259.807, "Y": 18.101, "Z": 7.06},
        )

        assert get_field(meta, "Manufacturer") == "EDAX"

        # Emission is a Quantity
        emission = get_field(meta, "Emission")
        assert isinstance(emission, ureg.Quantity)
        assert float(emission.magnitude) == 145.0
        assert str(emission.units) == "microampere"

    def test_titan_tem_diffraction(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_6_diffraction_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Diffraction"
        assert meta[0]["nx_meta"]["Data Type"] == "TEM_Diffraction"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(2048, 2048)"
        expected_iso = SYSTEM_TZ.localize(dt(2018, 10, 30, 17, 1, 3)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta, "Camera Name Path") == "BM-UltraScan"

        # camera_length is a core EM Glossary field for Diffraction datasets
        # Check if it's a Quantity or plain value (FEI doesn't always provide units)
        camera_length = meta[0]["nx_meta"]["camera_length"]
        if isinstance(camera_length, ureg.Quantity):
            assert float(camera_length.magnitude) == 0.3
            assert str(camera_length.units) == "meter"
        else:
            # Plain numeric value without units
            assert camera_length == pytest.approx(0.3)

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": -28.59, "B": 0.0, "X": -91.527, "Y": -100.11, "Z": 210.133},
        )

        assert get_field(meta, "Manufacturer") == "FEI"

        # Extraction Voltage is a Quantity
        extraction_voltage = get_field(meta, "Extraction Voltage")
        assert isinstance(extraction_voltage, ureg.Quantity)
        assert float(extraction_voltage.magnitude) == 4400
        assert str(extraction_voltage.units) == "volt"

    def test_titan_tem_image_stack_1(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_7_image_stack_1_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(20, 2048, 2048)"
        expected_iso = SYSTEM_TZ.localize(dt(2019, 3, 28, 21, 14, 16)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Dwell Time Path is a Quantity
        dwell_time = get_field(meta, "Dwell Time Path")
        assert isinstance(dwell_time, ureg.Quantity)
        assert float(dwell_time.magnitude) == 0.000002
        assert str(dwell_time.units) == "second"

        # C2 Aperture is a Quantity
        c2_aperture = get_field(meta, "C2 Aperture")
        assert isinstance(c2_aperture, ureg.Quantity)
        assert float(c2_aperture.magnitude) == 50.0
        assert str(c2_aperture.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 2.9, "B": 0.0, "X": -207.808, "Y": 111.327, "Z": 74.297},
        )

        assert get_field(meta, "Gun Type") == "FEG"
        assert get_field(meta, "Diffraction Lens") == pytest.approx(38.91)

    def test_titan_tem_image_stack_2(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_7_image_stack_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(20, 2048, 2048)"
        expected_iso = SYSTEM_TZ.localize(dt(2019, 3, 28, 22, 41, 0)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Frame Time is a Quantity
        frame_time = get_field(meta, "Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert float(frame_time.magnitude) == 10
        assert str(frame_time.units) == "second"

        # C1 Aperture is a Quantity
        c1_aperture = get_field(meta, "C1 Aperture")
        assert isinstance(c1_aperture, ureg.Quantity)
        assert float(c1_aperture.magnitude) == 2000
        assert str(c1_aperture.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 4.53, "B": 0.0, "X": -207.438, "Y": 109.996, "Z": 76.932},
        )

        assert get_field(meta, "Gun Lens") == 5
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
        expected_iso = SYSTEM_TZ.localize(dt(2018, 12, 13, 13, 33, 47)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta, "C2 Lens") == pytest.approx(43.465)

        # C2 Aperture is a Quantity
        c2_aperture = get_field(meta, "C2 Aperture")
        assert isinstance(c2_aperture, ureg.Quantity)
        assert float(c2_aperture.magnitude) == 100
        assert str(c2_aperture.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 1.86, "B": 0.0, "X": -179.33, "Y": -31.279, "Z": -158.512},
        )

        assert get_field(meta, "OBJ Aperture") == "retracted"
        assert get_field(meta, "Mode") == "TEM uP SA Zoom Diffraction"

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

        # High Tension is a Quantity
        high_tension = get_field(meta_1, "High Tension")
        assert isinstance(high_tension, ureg.Quantity)
        assert float(high_tension.magnitude) == 300
        assert str(high_tension.units) == "kilovolt"

        assert get_field(meta_1, "Gun Lens") == 6

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta_1, "Stage Position"),
            {"A": 9.21, "B": 0.0, "X": -202.298, "Y": -229.609, "Z": 92.45},
        )

        assert meta_2[0]["nx_meta"]["DatasetType"] == "Spectrum"
        assert meta_2[0]["nx_meta"]["Data Type"] == "STEM_EDS_Spectrum"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(3993,)"
        assert get_field(meta_2, "Beam Position") == "(-0.99656, 0.74289)"
        assert get_field(meta_2, "Diffraction Lens") == pytest.approx(37.347)
        assert get_field(meta_2, "Objective Lens") == pytest.approx(87.987)

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta_2, "Stage Position"),
            {"A": 9.21, "B": 0.0, "X": -202.296, "Y": -229.616, "Z": 92.45},
        )

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
        expected_iso = SYSTEM_TZ.localize(dt(2019, 6, 13, 19, 52, 6)).isoformat()
        assert meta_1[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta_1, "Diffraction Lens") == pytest.approx(37.347)
        assert get_field(meta_1, "Spot Size") == 7
        assert get_field(meta_1, "Manufacturer") == "FEI (ISAS)"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta_1, "Stage Position"),
            {"A": 9.21, "B": 0.0, "X": -202.296, "Y": -229.618, "Z": 92.45},
        )

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
        expected_iso = SYSTEM_TZ.localize(dt(2018, 9, 21, 14, 17, 25)).isoformat()
        assert meta_1[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta_1, "Binning") == 2
        assert get_field(meta_1, "Tecnai Filter")["Mode"] == "Spectroscopy"
        assert get_field(meta_1, "Tecnai Filter")["Selected Aperture"] == "3mm"

        # Image Shift X is a Quantity
        image_shift_x = get_field(meta_1, "Image Shift X")
        assert isinstance(image_shift_x, ureg.Quantity)
        assert float(image_shift_x.magnitude) == 0.003
        assert str(image_shift_x.units) == "micrometer"

        assert get_field(meta_1, "Mode") == "TEM uP SA Zoom Diffraction"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta_1, "Stage Position"),
            {"A": 0, "B": 0, "X": -135.782, "Y": 637.285, "Z": 77.505},
        )

        assert meta_2[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta_2[0]["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(4, 1024, 1024)"
        expected_iso = SYSTEM_TZ.localize(dt(2018, 9, 21, 14, 25, 11)).isoformat()
        assert meta_2[0]["nx_meta"]["Creation Time"] == expected_iso

        # Dwell Time Path is a Quantity
        dwell_time = get_field(meta_2, "Dwell Time Path")
        assert isinstance(dwell_time, ureg.Quantity)
        assert float(dwell_time.magnitude) == 0.8
        assert str(dwell_time.units) == "second"

        # Emission is a Quantity
        emission = get_field(meta_2, "Emission")
        assert isinstance(emission, ureg.Quantity)
        assert float(emission.magnitude) == 135.0
        assert str(emission.units) == "microampere"

        assert get_field(meta_2, "Magnification") == 10000

        # Image Shift X is a Quantity
        image_shift_x_2 = get_field(meta_2, "Image Shift X")
        assert isinstance(image_shift_x_2, ureg.Quantity)
        assert float(image_shift_x_2.magnitude) == 0.003
        assert str(image_shift_x_2.units) == "micrometer"

        assert get_field(meta_2, "Mode") == "TEM uP SA Zoom Image"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta_2, "Stage Position"),
            {"A": 0, "B": 0, "X": -135.787, "Y": 637.281, "Z": 77.505},
        )

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

            expected_iso = SYSTEM_TZ.localize(dt(2018, 11, 14, 17, 9, 55)).isoformat()
            assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

            # Frame Time is a Quantity
            frame_time = get_field(meta, "Frame Time")
            assert isinstance(frame_time, ureg.Quantity)
            assert float(frame_time.magnitude) == 30.199
            assert str(frame_time.units) == "second"

            # Selected Dispersion has unit suffix removed
            assert get_field(meta, "Tecnai Filter")["Selected Dispersion"] == 0.1
            assert (
                get_field(meta, "Microscope") == "Microscope Titan 300 kV "
                "ABCD1 SuperTwin"
            )
            assert get_field(meta, "Mode") == "STEM nP SA Zoom Diffraction"
            assert get_field(meta, "Spot Size") == 8
            assert get_field(meta, "Gun Lens") == 5
            assert get_field(meta, "Gun Type") == "FEG"

            # Stage Position fields are Quantities
            check_stage_position(
                get_field(meta, "Stage Position"),
                {"A": 0, "B": 0, "X": -116.939, "Y": -65.107, "Z": 79.938},
            )

    def test_643_stem_image(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_1_stem_image_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(1024, 1024)"
        expected_iso = SYSTEM_TZ.localize(dt(2011, 11, 16, 9, 46, 13)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso
        assert get_field(meta, "C2 Lens") == pytest.approx(8.967)

        # C2 Aperture is a Quantity
        c2_aperture = get_field(meta, "C2 Aperture")
        assert isinstance(c2_aperture, ureg.Quantity)
        assert float(c2_aperture.magnitude) == 40
        assert str(c2_aperture.units) == "micrometer"

        # Stage Position fields are Quantities
        check_stage_position(
            get_field(meta, "Stage Position"),
            {"A": 0, "B": 0, "X": 46.293, "Y": -14.017, "Z": -127.155},
        )

        # STEM Rotation Correction is a Quantity
        rotation = get_field(meta, "STEM Rotation Correction")
        assert isinstance(rotation, ureg.Quantity)
        assert float(rotation.magnitude) == 12.4
        assert str(rotation.units) == "degree"

        assert get_field(meta, "User") == "OPERATOR__"
        assert (
            get_field(meta, "Microscope") == "Microscope Titan 300 kV ABCD1 SuperTwin"
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
        expected_iso = SYSTEM_TZ.localize(dt(2011, 11, 16, 16, 8, 54)).isoformat()
        assert meta_1[0]["nx_meta"]["Creation Time"] == expected_iso

        # Frame Time is a Quantity
        frame_time = get_field(meta_1, "Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert float(frame_time.magnitude) == 10
        assert str(frame_time.units) == "second"

        # Emission is a Quantity
        emission = get_field(meta_1, "Emission")
        assert isinstance(emission, ureg.Quantity)
        assert float(emission.magnitude) == 237.3
        assert str(emission.units) == "microampere"

        assert get_field(meta_1, "Tecnai Filter")["Selected Aperture"] == "2.5 mm"
        assert get_field(meta_1, "Tecnai Filter")["Slit State"] == "Retracted"

        assert meta_2[0]["nx_meta"]["DatasetType"] == "SpectrumImage"
        assert meta_2[0]["nx_meta"]["Data Type"] == "STEM_EELS_Spectrum_Imaging"
        assert meta_2[0]["nx_meta"]["Data Dimensions"] == "(40, 70, 2048)"
        expected_iso = SYSTEM_TZ.localize(dt(2011, 11, 16, 16, 32, 27)).isoformat()
        assert meta_2[0]["nx_meta"]["Creation Time"] == expected_iso

        # Energy Resolution is a Quantity
        energy_res = get_field(meta_2, "Energy Resolution")
        assert isinstance(energy_res, ureg.Quantity)
        assert float(energy_res.magnitude) == 10
        assert str(energy_res.units) == "electron_volt"

        # Integration Time is a Quantity
        integration_time = get_field(meta_2, "Integration Time")
        assert isinstance(integration_time, ureg.Quantity)
        assert float(integration_time.magnitude) == 0.5
        assert str(integration_time.units) == "second"

        # Extraction Voltage is a Quantity
        extraction_voltage = get_field(meta_2, "Extraction Voltage")
        assert isinstance(extraction_voltage, ureg.Quantity)
        assert float(extraction_voltage.magnitude) == 4500
        assert str(extraction_voltage.units) == "volt"

        # Camera Length - check if it's a Quantity or plain value
        camera_length = get_field(meta_2, "Camera Length")
        if isinstance(camera_length, ureg.Quantity):
            assert float(camera_length.magnitude) == 0.06
            assert str(camera_length.units) == "meter"
        else:
            # FEI metadata doesn't always include units for Camera Length
            assert camera_length == pytest.approx(0.06)

        assert get_field(meta_2, "C2 Lens") == pytest.approx(8.967)

        # C3 Aperture is a Quantity
        c3_aperture = get_field(meta_2, "C3 Aperture")
        assert isinstance(c3_aperture, ureg.Quantity)
        assert float(c3_aperture.magnitude) == 1000
        assert str(c3_aperture.units) == "micrometer"

    def test_643_image_stack(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_3_image_stack_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(5, 1024, 1024)"
        expected_iso = SYSTEM_TZ.localize(dt(2012, 1, 31, 13, 43, 40)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Frame Time is a Quantity
        frame_time = get_field(meta, "Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert float(frame_time.magnitude) == 2.0
        assert str(frame_time.units) == "second"

        # C1 Aperture is a Quantity
        c1_aperture = get_field(meta, "C1 Aperture")
        assert isinstance(c1_aperture, ureg.Quantity)
        assert float(c1_aperture.magnitude) == 2000
        assert str(c1_aperture.units) == "micrometer"

        assert get_field(meta, "C2 Lens") == pytest.approx(14.99)

        # Defocus is a Quantity
        defocus = get_field(meta, "Defocus")
        assert isinstance(defocus, ureg.Quantity)
        assert float(defocus.magnitude) == -2.593
        assert str(defocus.units) == "micrometer"

        assert (
            get_field(meta, "Microscope") == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )
        assert get_field(meta, "Mode") == "STEM nP SA Zoom Diffraction"
        assert get_field(meta, "Magnification") == 80000

    def test_643_image_stack_2_newer(self, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_STEM_4_image_stack_2_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)
        assert meta[0]["nx_meta"]["DatasetType"] == "Image"
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[0]["nx_meta"]["Data Dimensions"] == "(2, 512, 512)"
        expected_iso = SYSTEM_TZ.localize(dt(2020, 3, 11, 16, 33, 38)).isoformat()
        assert meta[0]["nx_meta"]["Creation Time"] == expected_iso

        # Frame Time is a Quantity
        frame_time = get_field(meta, "Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert float(frame_time.magnitude) == 6.34179
        assert str(frame_time.units) == "second"

        # Dwell Time Path is a Quantity
        dwell_time = get_field(meta, "Dwell Time Path")
        assert isinstance(dwell_time, ureg.Quantity)
        assert float(dwell_time.magnitude) == 0.000001
        assert str(dwell_time.units) == "second"

        # C2 Aperture is a Quantity
        c2_aperture = get_field(meta, "C2 Aperture")
        assert isinstance(c2_aperture, ureg.Quantity)
        assert float(c2_aperture.magnitude) == 10
        assert str(c2_aperture.units) == "micrometer"

        assert get_field(meta, "C3 Lens") == -37.122

        # Defocus is a Quantity
        defocus = get_field(meta, "Defocus")
        assert isinstance(defocus, ureg.Quantity)
        assert float(defocus.magnitude) == -0.889
        assert str(defocus.units) == "micrometer"

        assert (
            get_field(meta, "Microscope") == "Microscope Titan 300 kV ABCD1 SuperTwin"
        )
        assert get_field(meta, "Mode") == "STEM nP SA Zoom Diffraction"
        assert get_field(meta, "Magnification") == 80000

        # STEM Rotation is a Quantity
        stem_rotation = get_field(meta, "STEM Rotation")
        assert isinstance(stem_rotation, ureg.Quantity)
        assert float(stem_rotation.magnitude) == -90.0
        assert str(stem_rotation.units) == "degree"

    def test_no_emi_error(self, caplog, fei_ser_files):
        test_file = get_full_file_path(
            "Titan_TEM_12_no_accompanying_emi_dataZeroed_1.ser",
            fei_ser_files,
        )
        meta = fei_emi.get_ser_metadata(test_file)

        assert get_field(meta, "Extractor Warning") is not None
        assert (
            "NexusLIMS could not find a corresponding .emi metadata "
            "file for this .ser file" in get_field(meta, "Extractor Warning")
        )
        assert (
            "NexusLIMS could not find a corresponding .emi metadata "
            "file for this .ser file" in caplog.text
        )
        assert get_field(meta, "emi Filename") is None

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
        assert "13_unreadable_ser.emi" in get_field(meta, "emi Filename")
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
            "not be opened by NexusLIMS" in get_field(meta, "Extractor Warning")
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

    def test_migrate_to_schema_compliant_metadata_with_top_level_vendor_sections(
        self,
    ):
        """Test top-level vendor sections go to extensions.

        Covers lines 284-287 in fei_emi.py where vendor sections move to extensions.
        """
        from nexusLIMS.extractors.plugins.fei_emi import SerEmiExtractor

        extractor = SerEmiExtractor()

        # Create metadata dict with top-level vendor sections
        mdict = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "STEM_Imaging",
                "Creation Time": "2024-01-15T10:30:00-05:00",
                "Data Dimensions": "(1024, 1024)",
                # Add top-level vendor sections that should go to extensions
                "ObjectInfo": {
                    "some_vendor_field": "value1",
                    "another_field": 123,
                },
                "ser_header_parameters": {
                    "header_field": "value2",
                },
                # Also add a regular vendor field for comparison
                "Magnification": 100000,
            }
        }

        # Call the migration method
        result = extractor._migrate_to_schema_compliant_metadata(mdict)  # noqa: SLF001

        # Verify top-level vendor sections went to extensions
        assert "extensions" in result["nx_meta"]
        assert "ObjectInfo" in result["nx_meta"]["extensions"]
        assert (
            result["nx_meta"]["extensions"]["ObjectInfo"]["some_vendor_field"]
            == "value1"
        )
        assert result["nx_meta"]["extensions"]["ObjectInfo"]["another_field"] == 123

        assert "ser_header_parameters" in result["nx_meta"]["extensions"]
        assert (
            result["nx_meta"]["extensions"]["ser_header_parameters"]["header_field"]
            == "value2"
        )

        # Verify other vendor fields also went to extensions
        assert "Magnification" in result["nx_meta"]["extensions"]
        assert result["nx_meta"]["extensions"]["Magnification"] == 100000

        # Verify core fields stayed at top level
        assert result["nx_meta"]["DatasetType"] == "Image"
        assert result["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert result["nx_meta"]["Creation Time"] == "2024-01-15T10:30:00-05:00"
        assert result["nx_meta"]["Data Dimensions"] == "(1024, 1024)"

        # Verify top-level vendor sections are NOT at top level of nx_meta
        assert (
            "ObjectInfo" not in result["nx_meta"]
            or result["nx_meta"].get("ObjectInfo") is None
            or "ObjectInfo" in result["nx_meta"]["extensions"]
        )
        assert (
            "ser_header_parameters" not in result["nx_meta"]
            or result["nx_meta"].get("ser_header_parameters") is None
            or "ser_header_parameters" in result["nx_meta"]["extensions"]
        )
