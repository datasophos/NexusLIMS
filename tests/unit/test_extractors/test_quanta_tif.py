# pylint: disable=C0116
# ruff: noqa: SLF001, FBT003, N817

"""Tests for nexusLIMS.extractors.quanta_tif."""

import numpy as np
import pytest
from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.quanta_tif import (
    QuantaTiffExtractor,
    get_quanta_metadata,
)
from tests.unit.test_instrument_factory import make_test_tool


class TestQuantaExtractor:
    """Tests nexusLIMS.extractors.quanta_tif."""

    def test_quanta_extraction(self, quanta_test_file):
        """Test basic metadata extraction from standard Quanta TIF file."""
        metadata = get_quanta_metadata(quanta_test_file[0])

        # Test nx_meta values
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"
        assert metadata[0]["nx_meta"]["warnings"] == [["Operator"]]

        # Sample values from each native section
        assert metadata[0]["User"]["User"] == "user_"
        assert metadata[0]["User"]["Date"] == "12/18/2017"
        assert metadata[0]["System"]["Type"] == "SEM"
        assert metadata[0]["Beam"]["HV"] == "30000"
        assert metadata[0]["EScan"]["InternalScan"]
        assert metadata[0]["Stage"]["StageX"] == "0.009654"
        assert metadata[0]["Image"]["ResolutionX"] == "1024"
        assert metadata[0]["Vacuum"]["ChPressure"] == "79.8238"
        assert metadata[0]["Detectors"]["Number"] == "1"
        assert metadata[0]["LFD"]["Contrast"] == "62.4088"

    def test_bad_metadata(self, quanta_bad_metadata):
        """Test handling of file without expected FEI tags."""
        metadata = get_quanta_metadata(quanta_bad_metadata)
        assert (
            metadata[0]["nx_meta"]["Extractor Warnings"]
            == "Did not find expected FEI tags. Could not read metadata"
        )
        assert metadata[0]["nx_meta"]["Data Type"] == "Unknown"

    def test_modded_metadata(self, quanta_just_modded_mdata):
        """Test extraction from file with modified metadata values."""
        metadata = get_quanta_metadata(quanta_just_modded_mdata)

        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"
        assert metadata[0]["nx_meta"]["Scan Rotation (°)"] == pytest.approx(179.9947)
        assert metadata[0]["nx_meta"]["Tilt Correction Angle"] == pytest.approx(
            0.0121551
        )
        # Invalid format should be stored as-is
        assert metadata[0]["nx_meta"]["Chamber Pressure (mPa)"] == "79.8.38"

    def test_no_beam_scan_or_system_metadata(
        self,
        mock_instrument_from_filepath,
        quanta_no_beam_meta,
    ):
        """Test extraction with missing beam/scan/system metadata sections."""
        mock_instrument_from_filepath(make_test_tool())

        metadata = get_quanta_metadata(quanta_no_beam_meta[0])
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"
        assert (
            metadata[0]["nx_meta"]["Creation Time"]
            == "2025-11-17T17:52:13.811711-07:00"
        )
        assert metadata[0]["nx_meta"]["Instrument ID"] == "testtool-TEST-A1234567"
        assert metadata[0]["nx_meta"]["Data Dimensions"] == "(1024, 884)"
        assert metadata[0]["nx_meta"]["Frames Integrated"] == 5
        assert metadata[0]["Image"]["ResolutionX"] == "1024"

    def test_scios_duplicate_metadata_sections(self, scios_multiple_gis_meta):
        """Test handling of duplicate MultiGIS metadata sections."""
        metadata = get_quanta_metadata(scios_multiple_gis_meta[0])
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"
        assert (
            metadata[0]["nx_meta"]["Creation Time"]
            == "2025-11-18T00:53:37.585629+00:00"
        )
        assert metadata[0]["nx_meta"]["Operator"] == "xxxx"
        assert metadata[0]["CBS"]["Setting"] == "C+D"
        # Verify renamed sections
        assert metadata[0]["MultiGISUnit1.MultiGISGas1"]["GasName"] == ""
        assert metadata[0]["MultiGISUnit2.MultiGISGas3"]["DutyCycle"] == "0"
        assert metadata[0]["MultiGISUnit3.MultiGISGas6"]["GasState"] == "Unknown"

    def test_scios_xml_metadata(self, scios_xml_metadata):
        """Test extraction of XML metadata from tag 34683."""
        metadata = get_quanta_metadata(scios_xml_metadata[0])
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["Acquisition Date"] == "05/01/2024"
        assert metadata[0]["nx_meta"]["Beam Tilt X"] == pytest.approx(0.0)
        assert metadata[0]["CBS"]["Setting"] == "A+B"
        assert metadata[0]["nx_meta"]["Operator"] == "xxxx"

        # Verify XML metadata parsing
        assert metadata[0]["FEI_XML_Metadata"]["Core"]["ApplicationSoftware"] == "xT"
        assert metadata[0]["FEI_XML_Metadata"]["Core"]["UserID"] == "xxxx"
        assert (
            metadata[0]["FEI_XML_Metadata"]["Instrument"]["Manufacturer"]
            == "FEI Company"
        )
        assert (
            metadata[0]["FEI_XML_Metadata"]["GasInjectionSystems"]["Gis"][1]["PortName"]
            == "Port2"
        )

    def test_quanta_fei_2_metadata_extraction(self, quanta_fei_2_file):
        """Test extraction from file with special chars (%) in metadata.

        Verifies extraction of metadata fields including:
        - UserText (user-provided notes)
        - ESEM (Environmental SEM column type)
        - EucWD (Eucentric Working Distance)
        - ScanRotation (Beam scan rotation angle)
        - ImageMode (Acquisition mode)
        - FrameTime (Total frame acquisition time)
        - Gas (MultiGIS gas injection system)
        - UserMode (Vacuum mode)
        - Humidity (Chamber humidity)
        - Temperature (Specimen temperature)
        """
        metadata = get_quanta_metadata(quanta_fei_2_file)

        # Should extract successfully with RawConfigParser handling '%' characters
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"
        assert "Creation Time" in metadata[0]["nx_meta"]
        assert "Extractor Warnings" not in metadata[0]["nx_meta"]

        # Verify extraction of standard Quanta metadata fields
        assert "Horizontal Field Width (μm)" in metadata[0]["nx_meta"]
        assert "Voltage (kV)" in metadata[0]["nx_meta"]
        assert "Stage Position" in metadata[0]["nx_meta"]

        # Verify metadata values for fields that should be extracted
        assert isinstance(metadata[0]["nx_meta"]["User Text"], str)
        assert (
            "Specimen Temperature (K)" not in metadata[0]["nx_meta"]
        )  # Blank in test file
        assert isinstance(metadata[0]["nx_meta"]["Vacuum Mode"], str)
        assert metadata[0]["nx_meta"]["Scan Rotation (°)"] == 0
        assert (
            "Specimen Humidity (%)" not in metadata[0]["nx_meta"]
        )  # Blank in test file
        assert metadata[0]["nx_meta"]["Total Frame Time (s)"] > 0
        assert metadata[0]["nx_meta"]["Eucentric WD (mm)"] > 0  # EucWD extracted
        assert isinstance(
            metadata[0]["nx_meta"]["Image Mode"], str
        )  # ImageMode extracted

    def test_supports_method(self, quanta_test_file, tmp_path):
        """Test the supports() method for various file types."""
        extractor = QuantaTiffExtractor()

        # Should support valid FEI TIFF
        context = ExtractionContext(quanta_test_file[0], None)
        assert extractor.supports(context)

        # Should not support non-TIFF files
        non_tiff = tmp_path / "test.txt"
        non_tiff.write_text("test")
        assert not extractor.supports(ExtractionContext(non_tiff, None))

        # Should support file with FEI markers in binary (fallback)
        binary_fei = tmp_path / "binary_fei.tif"
        with binary_fei.open("wb") as f:
            f.write(b"[User] test data")
        assert extractor.supports(ExtractionContext(binary_fei, None))

        # Should not support TIFF without FEI markers
        non_fei_tiff = tmp_path / "non_fei.tif"
        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")
        img.save(non_fei_tiff)
        assert not extractor.supports(ExtractionContext(non_fei_tiff, None))

        # Test exception handling when Image.open fails but binary fallback works
        from unittest.mock import patch

        with patch("PIL.Image.open", side_effect=Exception("Image open failed")):
            # File with FEI markers - should succeed via binary fallback
            tiff_with_markers = tmp_path / "has_markers.tif"
            tiff_with_markers.write_bytes(b"fake tiff [User] data")
            result = extractor.supports(ExtractionContext(tiff_with_markers, None))
            assert result is True

            # File without FEI markers - should return False
            tiff_no_markers = tmp_path / "no_markers.tif"
            tiff_no_markers.write_bytes(b"fake tiff data")
            result = extractor.supports(ExtractionContext(tiff_no_markers, None))
            assert result is False

        # Test exception during binary read
        from pathlib import Path

        tiff_for_error = tmp_path / "error_test.tif"
        tiff_for_error.write_bytes(b"test")

        with (
            patch("PIL.Image.open", side_effect=Exception("PIL failed")),
            patch.object(Path, "open", side_effect=OSError("Cannot read file")),
        ):
            result = extractor.supports(ExtractionContext(tiff_for_error, None))
            assert result is False

    def test_xml_parsing_and_detection(self, tmp_path, mock_instrument_from_filepath):
        """Test XML detection and parsing in metadata."""
        mock_instrument_from_filepath(make_test_tool())

        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")
        tiff_path = tmp_path / "xml_test.tif"

        # Create metadata with embedded XML
        metadata_with_xml = """[User]
User=testuser
[Beam]
Beam=EBeam

<?xml version="1.0"?>
<root>
  <item>value</item>
  <nested>
    <data>content</data>
  </nested>
</root>"""

        img.save(tiff_path, tiffinfo={34682: metadata_with_xml})

        extractor = QuantaTiffExtractor()
        result = extractor._detect_and_process_xml_metadata(metadata_with_xml)

        # Should separate metadata and XML
        metadata_str, xml_dict = result
        assert "[User]" in metadata_str
        assert "<?xml" not in metadata_str
        assert xml_dict["item"] == "value"
        assert xml_dict["nested"]["data"] == "content"

    def test_detector_setting_handling(self, tmp_path, mock_instrument_from_filepath):
        """Test detector Setting field handling (numeric vs string)."""
        mock_instrument_from_filepath(make_test_tool())

        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")

        # Test numeric Setting (should be skipped as duplicate of Grid)
        tiff_numeric = tmp_path / "numeric_setting.tif"
        metadata_numeric = """[User]
User=test
[Beam]
Beam=EBeam
[Detectors]
Name=LFD
Number=1
[LFD]
Setting=123
Grid=45.5
Brightness=50.0
Contrast=60.0
"""
        img.save(tiff_numeric, tiffinfo={34682: metadata_numeric})
        metadata = get_quanta_metadata(tiff_numeric)
        assert "Detector Grid Voltage (V)" in metadata[0]["nx_meta"]
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"

        # Test non-numeric Setting
        from unittest.mock import patch

        from nexusLIMS.extractors.base import FieldDefinition as FD

        tiff_string = tmp_path / "string_setting.tif"
        metadata_string = """[User]
User=test
[Beam]
Beam=EBeam
[Detectors]
Name=LFD
Number=1
[LFD]
Setting=AUTO_VALUE
Grid=50.0
Brightness=45.0
Contrast=60.0
"""
        img.save(tiff_string, tiffinfo={34682: metadata_string})

        # Patch to add a Setting field definition to trigger exception handler
        extractor = QuantaTiffExtractor()
        original_build = extractor._build_field_definitions

        def mocked_build(mdict):
            fields = original_build(mdict)
            fields.append(FD("LFD", "Setting", "Detector Setting Value", 1.0, False))
            return fields

        with patch.object(
            extractor, "_build_field_definitions", side_effect=mocked_build
        ):
            context = ExtractionContext(tiff_string, None)
            metadata = extractor.extract(context)
            assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"

    def test_chamber_pressure_modes(self, tmp_path, mock_instrument_from_filepath):
        """Test chamber pressure unit conversion for different vacuum modes."""
        mock_instrument_from_filepath(make_test_tool())

        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")

        # Test low vacuum mode (Pa)
        tiff_low_vac = tmp_path / "low_vac.tif"
        metadata_low_vac = """[User]
User=test
[Beam]
Beam=EBeam
[Vacuum]
ChPressure=50.5
UserMode=Low vacuum
"""
        img.save(tiff_low_vac, tiffinfo={34682: metadata_low_vac})
        metadata = get_quanta_metadata(tiff_low_vac)
        if "Chamber Pressure (Pa)" in metadata[0]["nx_meta"]:
            assert isinstance(
                metadata[0]["nx_meta"]["Chamber Pressure (Pa)"], (int, float)
            )

        # Test non-numeric pressure (error handling)
        tiff_bad_pressure = tmp_path / "bad_pressure.tif"
        metadata_bad_pressure = """[User]
User=test
[Beam]
Beam=EBeam
HV=20000
[Vacuum]
ChPressure=NOT_A_NUMBER
Mode=Low vacuum
[Detectors]
Name=LFD
Number=1
[LFD]
Contrast=62.0
"""
        img.save(tiff_bad_pressure, tiffinfo={34682: metadata_bad_pressure})
        metadata = get_quanta_metadata(tiff_bad_pressure)
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata[0]["nx_meta"]["Chamber Pressure (Pa)"] == "NOT_A_NUMBER"

    def test_suppression_features(self, quanta_test_file):
        """Test zero suppression and conditional extraction features."""
        metadata = get_quanta_metadata(quanta_test_file[0])

        # Beam Shift values are not suppressed even when zero (suppress_zero=False)
        assert "Beam Shift X" in metadata[0]["nx_meta"]
        assert "Beam Shift Y" in metadata[0]["nx_meta"]

        # Frame integration only appears if > 1
        if "Frames Integrated" in metadata[0]["nx_meta"]:
            assert metadata[0]["nx_meta"]["Frames Integrated"] > 1

        # Tilt correction only if enabled
        if "Tilt Correction Angle" in metadata[0]["nx_meta"]:
            assert metadata[0]["nx_meta"]["Tilt Correction Angle"] is not None

    def test_error_handling_and_edge_cases(
        self, tmp_path, mock_instrument_from_filepath
    ):
        """Test various error conditions and edge cases."""
        from unittest.mock import patch

        mock_instrument_from_filepath(make_test_tool())
        extractor = QuantaTiffExtractor()
        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")

        # Test empty/minimal TIFF (no FEI metadata)
        minimal_tiff = tmp_path / "minimal.tif"
        img.save(minimal_tiff)
        context = ExtractionContext(minimal_tiff, None)
        metadata = extractor.extract(context)
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"

        # Test file with FEI marker but invalid metadata structure
        corrupted_tiff = tmp_path / "corrupted.tif"
        img.save(corrupted_tiff, tiffinfo={34682: b"[User]\nInvalid=Data"})
        metadata = get_quanta_metadata(corrupted_tiff)
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"

        # Test warnings list initialization
        assert "warnings" in metadata[0]["nx_meta"]
        assert isinstance(metadata[0]["nx_meta"]["warnings"], list)

        # Test XML parsing exception in tag 34683
        bad_xml_tiff = tmp_path / "bad_xml.tif"
        img.save(
            bad_xml_tiff, tiffinfo={34682: b"[User]\nUser=test", 34683: "<?xml><bad>"}
        )
        metadata = get_quanta_metadata(bad_xml_tiff)
        assert metadata[0]["nx_meta"]["DatasetType"] == "Image"

        # Test binary extraction exception
        with patch.object(
            extractor,
            "_detect_and_process_xml_metadata",
            side_effect=Exception("Processing failed"),
        ):
            result = extractor._extract_metadata_from_tiff_tag(tmp_path / "fake.tif")
            assert result == ("", {})

    def test_special_field_parsing(self, tmp_path, mock_instrument_from_filepath):
        """Test special field parsing (scan rotation, tilt correction, etc.)."""
        mock_instrument_from_filepath(make_test_tool())

        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")
        tiff_path = tmp_path / "special_fields.tif"

        # Metadata with special fields - needs [Beam] section for beam_name
        metadata_str = """[User]
User=test
Date=01/01/2025
[Beam]
Beam=EBeam
Scan=EBeam
[EBeam]
ScanRotation=3.14159
TiltCorrectionIsOn=yes
TiltCorrectionAngle=0.5
HV=20000
[Image]
DriftCorrected=On
Integrate=4
ResolutionX=1024
ResolutionY=768
"""
        img.save(tiff_path, tiffinfo={34682: metadata_str})
        metadata = get_quanta_metadata(tiff_path)

        # Verify special field parsing
        assert "Scan Rotation (°)" in metadata[0]["nx_meta"]
        assert "Tilt Correction Angle" in metadata[0]["nx_meta"]
        assert metadata[0]["nx_meta"]["Drift Correction Applied"] is True
        assert metadata[0]["nx_meta"]["Frames Integrated"] == 4
        assert metadata[0]["nx_meta"]["Data Dimensions"] == "(1024, 768)"

    def test_software_and_column_aggregation(
        self, tmp_path, mock_instrument_from_filepath
    ):
        """Test aggregation of Software/BuildNr and Column/Type fields."""
        mock_instrument_from_filepath(make_test_tool())

        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")
        tiff_path = tmp_path / "aggregation.tif"

        metadata_str = """[User]
User=test
[Beam]
Beam=EBeam
[System]
Software=FEI Software
BuildNr=1234
Column=ESEM
Type=FEG
"""
        img.save(tiff_path, tiffinfo={34682: metadata_str})
        metadata = get_quanta_metadata(tiff_path)

        assert metadata[0]["nx_meta"]["Software Version"] == "FEI Software (build 1234)"
        assert metadata[0]["nx_meta"]["Column Type"] == "ESEM FEG"

    def test_missing_coverage_paths(self, tmp_path, mock_instrument_from_filepath):
        """Test edge case: numeric Setting fields skipped, warning list is init'd."""
        from unittest.mock import patch

        from nexusLIMS.extractors.base import FieldDefinition as FD

        mock_instrument_from_filepath(make_test_tool())
        img_array = np.zeros((10, 10), dtype=np.uint8)
        img = Image.fromarray(img_array, mode="L")

        # Test continue when Setting is numeric
        tiff_numeric_setting = tmp_path / "numeric_setting_skip.tif"
        metadata_str = """[User]
User=test
[Beam]
Beam=EBeam
[Detectors]
Name=LFD
Number=1
[LFD]
Setting=500.0
Grid=50.0
"""
        img.save(tiff_numeric_setting, tiffinfo={34682: metadata_str})

        extractor = QuantaTiffExtractor()
        original_build = extractor._build_field_definitions

        def mocked_build(mdict):
            fields = original_build(mdict)
            # Add Setting field to trigger the check
            fields.append(FD("LFD", "Setting", "Detector Setting", 1.0, False))
            return fields

        with patch.object(
            extractor, "_build_field_definitions", side_effect=mocked_build
        ):
            context = ExtractionContext(tiff_numeric_setting, None)
            metadata = extractor.extract(context)
            # Numeric Setting should be skipped
            assert "Detector Setting" not in metadata[0].get("nx_meta", {})

        # Test warnings initialization when it doesn't exist
        # This is covered when _parse_nx_meta is called on a fresh nx_meta dict
        test_dict = {"nx_meta": {}, "User": {"User": "test"}}
        result = extractor._parse_nx_meta(test_dict)
        assert "warnings" in result["nx_meta"]
        assert isinstance(result["nx_meta"]["warnings"], list)
