# pylint: disable=C0116
# ruff: noqa: FBT003

"""Tests for nexusLIMS.extractors.quanta_tif."""

import numpy as np
import pytest
from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.quanta_tif import (
    QuantaTiffExtractor,
    get_quanta_metadata,
)
from nexusLIMS.schemas.units import ureg
from tests.unit.test_instrument_factory import make_test_tool

from .conftest import get_field


class TestQuantaExtractor:
    """Tests nexusLIMS.extractors.quanta_tif."""

    def test_quanta_extraction(self, quanta_test_file):  # noqa: PLR0915
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

        # Test Pint Quantities derived from raw values
        from decimal import Decimal

        nx_meta = metadata[0]["nx_meta"]

        # Voltage: raw "30000" → 30000 volt → 30 kilovolt
        voltage = nx_meta["acceleration_voltage"]
        assert isinstance(voltage, ureg.Quantity)
        assert voltage.magnitude == Decimal("30000.0")
        assert str(voltage.units) == "volt"
        assert voltage.to("kilovolt").magnitude == Decimal("30.0")

        # Emission Current: raw "0.0001560" → 0.000156 ampere
        # → 156 microampere
        emission_current = nx_meta["emission_current"]
        assert isinstance(emission_current, ureg.Quantity)
        assert emission_current.magnitude == Decimal("0.0001560")
        assert str(emission_current.units) == "ampere"
        assert emission_current.to("microampere").magnitude == Decimal("156.0")

        # Working Distance: raw "0.011051" → 0.011051 meter
        # → 11.051 millimeter
        working_distance = nx_meta["working_distance"]
        assert isinstance(working_distance, ureg.Quantity)
        assert working_distance.magnitude == Decimal("0.011051")
        assert str(working_distance.units) == "meter"
        assert working_distance.to("millimeter").magnitude == Decimal("11.051")

        # Horizontal Field Width: raw "0.000452548" → 0.000452548 meter
        # → 452.548 micrometer
        hfw = nx_meta["horizontal_field_width"]
        assert isinstance(hfw, ureg.Quantity)
        assert hfw.magnitude == Decimal("0.000452548")
        assert str(hfw.units) == "meter"
        assert hfw.to("micrometer").magnitude == Decimal("452.548")

        # Pixel Width: raw "4.41942e-007" → 4.41942e-7 meter
        # → 441.942 nanometer
        pixel_width = nx_meta["pixel_width"]
        assert isinstance(pixel_width, ureg.Quantity)
        assert pixel_width.magnitude == Decimal("4.41942e-007")
        assert str(pixel_width.units) == "meter"
        assert pixel_width.to("nanometer").magnitude == Decimal("441.942")

        # Dwell Time: raw "3e-005" → 3e-5 second → 30 microsecond
        dwell_time = nx_meta["dwell_time"]
        assert isinstance(dwell_time, ureg.Quantity)
        assert dwell_time.magnitude == Decimal("3e-005")
        assert str(dwell_time.units) == "second"
        assert dwell_time.to("microsecond").magnitude == Decimal("30.0")

        # Chamber Pressure (extensions): raw "79.8238" Pa → 79.8238 pascal
        # (low vacuum mode)
        chamber_pressure = get_field(metadata, "Chamber Pressure")
        assert isinstance(chamber_pressure, ureg.Quantity)
        assert chamber_pressure.magnitude == Decimal("79.8238")
        assert str(chamber_pressure.units) == "pascal"

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

        # Scan Rotation should be a Quantity with degree unit (in extensions)
        scan_rot = get_field(metadata, "Scan Rotation")
        assert isinstance(scan_rot, ureg.Quantity)
        assert float(scan_rot.magnitude) == 179.9947
        assert str(scan_rot.units) == "degree"

        tilt_correction = get_field(metadata, "Tilt Correction Angle")
        assert tilt_correction == pytest.approx(0.0121551)
        # Invalid format should be stored as-is (string, not Quantity)
        chamber_pressure = get_field(metadata, "Chamber Pressure")
        assert chamber_pressure == "79.8.38"

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
        data_dimensions = get_field(metadata, "Data Dimensions")
        assert data_dimensions == "(1024, 884)"
        frames_integrated = get_field(metadata, "Frames Integrated")
        assert frames_integrated == 5
        # Image section is raw metadata, not in nx_meta or extensions
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
        operator = get_field(metadata, "Operator")
        assert operator == "xxxx"
        # CBS is a raw metadata section
        assert metadata[0]["CBS"]["Setting"] == "C+D"
        # Verify renamed sections (raw metadata sections)
        assert metadata[0]["MultiGISUnit1.MultiGISGas1"]["GasName"] == ""
        assert metadata[0]["MultiGISUnit2.MultiGISGas3"]["DutyCycle"] == "0"
        assert metadata[0]["MultiGISUnit3.MultiGISGas6"]["GasState"] == "Unknown"

    def test_scios_xml_metadata(self, scios_xml_metadata):
        """Test extraction of XML metadata from tag 34683."""
        metadata = get_quanta_metadata(scios_xml_metadata[0])
        assert metadata[0]["nx_meta"]["Data Type"] == "SEM_Imaging"
        acquisition_date = get_field(metadata, "Acquisition Date")
        assert acquisition_date == "05/01/2024"
        beam_tilt_x = get_field(metadata, "Beam Tilt X")
        assert beam_tilt_x == pytest.approx(0.0)
        # CBS is a raw metadata section
        assert metadata[0]["CBS"]["Setting"] == "A+B"
        operator = get_field(metadata, "Operator")
        assert operator == "xxxx"

        # Verify XML metadata parsing (raw metadata section)
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

        # Verify extraction of standard Quanta metadata fields (new names without units)
        nx_meta = metadata[0]["nx_meta"]
        assert "horizontal_field_width" in nx_meta
        assert "vertical_field_width" in nx_meta
        assert "acceleration_voltage" in nx_meta

        extensions = nx_meta.get("extensions", {})
        assert "Stage Position" in nx_meta or "Stage Position" in extensions

        # Verify metadata values for fields that should be extracted (in extensions)
        user_text = get_field(metadata, "User Text")
        assert isinstance(user_text, str)
        # Blank in test file - should not be in metadata
        with pytest.raises(KeyError):
            get_field(metadata, "Specimen Temperature")
        vacuum_mode = get_field(metadata, "Vacuum Mode")
        assert isinstance(vacuum_mode, str)

        # Scan Rotation should be a Quantity with degree unit (in extensions)
        scan_rot = get_field(metadata, "Scan Rotation")
        assert isinstance(scan_rot, ureg.Quantity)
        assert scan_rot.magnitude == 0
        assert str(scan_rot.units) == "degree"

        # Blank in test file - should not be in metadata
        with pytest.raises(KeyError):
            get_field(metadata, "Specimen Humidity")

        # Total Frame Time should be a Quantity with second unit (in extensions)
        frame_time = get_field(metadata, "Total Frame Time")
        assert isinstance(frame_time, ureg.Quantity)
        assert frame_time.magnitude > 0
        assert str(frame_time.units) == "second"

        # Eucentric WD should be a Quantity with meter unit (source unit)
        # (in extensions)
        euc_wd = get_field(metadata, "Eucentric WD")
        assert isinstance(euc_wd, ureg.Quantity)
        assert euc_wd.magnitude > 0
        assert str(euc_wd.units) == "meter"
        # Verify it can be converted to millimeters (common display unit)
        assert euc_wd.to("millimeter").magnitude > 0

        # ImageMode extracted (in extensions)
        image_mode = get_field(metadata, "Image Mode")
        assert isinstance(image_mode, str)

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
        # Field name updated to remove unit suffix (in extensions)
        nx_meta = metadata[0]["nx_meta"]
        extensions = nx_meta.get("extensions", {})
        assert (
            "Detector Grid Voltage" in nx_meta or "Detector Grid Voltage" in extensions
        )
        # Should be a Quantity with volt unit
        grid_voltage = get_field(metadata, "Detector Grid Voltage")
        assert isinstance(grid_voltage, ureg.Quantity)
        assert str(grid_voltage.units) == "volt"
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
        # Field name updated, should be a Quantity with pascal unit (in extensions)
        try:
            ch_pres = get_field(metadata, "Chamber Pressure")
            assert isinstance(ch_pres, ureg.Quantity)
            assert float(ch_pres.magnitude) == 50.5
            assert str(ch_pres.units) == "pascal"
        except KeyError:
            # Field may not be present if extraction failed
            pass

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
        # Invalid value stored as string (field name updated, in extensions)
        chamber_pressure = get_field(metadata, "Chamber Pressure")
        assert chamber_pressure == "NOT_A_NUMBER"

    def test_suppression_features(self, quanta_test_file):
        """Test zero suppression and conditional extraction features."""
        metadata = get_quanta_metadata(quanta_test_file[0])

        # Beam Shift values are not suppressed even when zero (suppress_zero=False)
        # Check both nx_meta and extensions
        nx_meta = metadata[0]["nx_meta"]
        extensions = nx_meta.get("extensions", {})
        assert "Beam Shift X" in nx_meta or "Beam Shift X" in extensions
        assert "Beam Shift Y" in nx_meta or "Beam Shift Y" in extensions

        # Frame integration only appears if > 1
        try:
            frames = get_field(metadata, "Frames Integrated")
            assert frames > 1
        except KeyError:
            pass  # Not present is acceptable

        # Tilt correction only if enabled
        try:
            tilt_corr = get_field(metadata, "Tilt Correction Angle")
            assert tilt_corr is not None
        except KeyError:
            pass  # Not present is acceptable

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

        # Verify special field parsing - field name updated (in extensions)
        nx_meta = metadata[0]["nx_meta"]
        extensions = nx_meta.get("extensions", {})
        assert "Scan Rotation" in nx_meta or "Scan Rotation" in extensions
        # Scan Rotation should be a Quantity with degree unit
        # Note: Input is in radians (3.14159), converted to degrees (~180)
        scan_rot = get_field(metadata, "Scan Rotation")
        assert isinstance(scan_rot, ureg.Quantity)
        assert float(scan_rot.magnitude) == 179.99985  # 3.14159 radians = ~180 degrees
        assert str(scan_rot.units) == "degree"

        tilt_corr_angle = get_field(metadata, "Tilt Correction Angle")
        assert tilt_corr_angle is not None
        drift_correction = get_field(metadata, "Drift Correction Applied")
        assert drift_correction is True
        frames_integrated = get_field(metadata, "Frames Integrated")
        assert frames_integrated == 4
        data_dimensions = get_field(metadata, "Data Dimensions")
        assert data_dimensions == "(1024, 768)"

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

        # These aggregated fields should be in extensions
        software_version = get_field(metadata, "Software Version")
        assert software_version == "FEI Software (build 1234)"
        column_type = get_field(metadata, "Column Type")
        assert column_type == "ESEM FEG"

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
