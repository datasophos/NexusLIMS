"""Tests for the Zeiss Orion/Fibics TIFF extractor plugin."""

import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.orion_HIM_tif import (
    FIBICS_TIFF_TAG,
    ZEISS_TIFF_TAG,
    OrionTiffExtractor,
)
from nexusLIMS.extractors.registry import get_registry
from nexusLIMS.schemas.units import ureg

from .conftest import get_field


@pytest.fixture
def minimal_tiff_file(tmp_path):
    """Fixture that creates a minimal valid TIFF file and cleans it up."""
    file_path = tmp_path / "test.tif"
    img = Image.new("RGB", (100, 100), color="black")
    img.save(file_path, "TIFF")
    return file_path
    # Cleanup is handled automatically by tmp_path fixture


def _create_tiff_with_custom_tags(file_path, zeiss_xml=None, fibics_xml=None):
    """Create a TIFF file with custom Zeiss/Fibics tags using PIL."""
    # Create a simple image
    image_data = np.zeros((100, 100, 3), dtype=np.uint8)  # 100x100 RGB image
    img = Image.fromarray(image_data, mode="RGB")

    # Create TiffInfo object for custom tags
    tiffinfo = {}

    # Add Zeiss tag if provided
    if zeiss_xml:
        # TIFF tags expect bytes
        xml_bytes = (
            zeiss_xml.encode("utf-8") if isinstance(zeiss_xml, str) else zeiss_xml
        )
        tiffinfo[ZEISS_TIFF_TAG] = xml_bytes

    # Add Fibics tag if provided
    if fibics_xml:
        # TIFF tags expect bytes
        xml_bytes = (
            fibics_xml.encode("utf-8") if isinstance(fibics_xml, str) else fibics_xml
        )
        tiffinfo[FIBICS_TIFF_TAG] = xml_bytes

    # Save the TIFF with custom tags
    img.save(file_path, "TIFF", tiffinfo=tiffinfo)


@pytest.fixture
def zeiss_tiff_file(tmp_path):
    """Fixture that creates a TIFF file with Zeiss Orion metadata tags."""
    file_path = tmp_path / "zeiss_test.tif"

    _create_tiff_with_custom_tags(
        file_path,
        zeiss_xml="<ImageTags><StageRotate><Value>1.2</Value><Units>Degrees</Units></StageRotate></ImageTags>",
    )
    return file_path


@pytest.fixture
def fibics_tiff_file(tmp_path):
    """Fixture that creates a TIFF file with Fibics metadata tags."""
    file_path = tmp_path / "fibics_test.tif"

    _create_tiff_with_custom_tags(
        file_path,
        # this is a minimal set of fibics XML metadata
        fibics_xml='<?xml version="1.0" encoding="iso-8859-1"?><Fibics version="1.0"><Application><Version>NPVE v4.5</Version></Application><Image><Width>2048</Width><Height>2048</Height></Image><Scan><Dwell units="ns">10000</Dwell></Scan><Stage><X units="um">-21319.2368624182</X></Stage><BeamInfo><item name="BeamI">1.3275146484375</item></BeamInfo><DetectorInfo><item name="Collector">=500.0 V</item></DetectorInfo></Fibics>',  # noqa: E501
    )
    return file_path


@pytest.fixture
def unknown_xml_tiff_file(tmp_path):
    """Fixture that creates a TIFF file with neither Fibics or Zeiss metadata tags."""
    file_path = tmp_path / "unknown_xml_test.tif"

    _create_tiff_with_custom_tags(
        file_path,
        # this is a minimal set of metadata that should trigger "unknown" XML variant
        fibics_xml="<Version>NPVE v4.5</Version >",
    )
    return file_path


class TestOrionFibicsTiffExtractor:
    """Test the OrionFibicsTiffExtractor plugin."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = OrionTiffExtractor()
        self.registry = get_registry()
        self.registry.clear()  # Clear registry for isolated testing
        self.registry.register_extractor(OrionTiffExtractor)

    def test_has_required_attributes(self):
        """Test that the extractor has required attributes."""
        assert hasattr(self.extractor, "name")
        assert hasattr(self.extractor, "priority")
        assert self.extractor.name == "orion_HIM_tif_extractor"
        assert self.extractor.priority == 150

    def test_supports_tif_extension(self):
        """Test that the extractor does not support tif files without Orion tags."""
        context = ExtractionContext(Path("test.tif"), instrument=None)
        # This should return False because we don't have actual TIFF tags
        supported = self.extractor.supports(context)
        assert supported is False

    def test_supports_tiff_extension(self):
        """Test that the extractor does not support tiff files without Orion tags."""
        context = ExtractionContext(Path("test.tiff"), instrument=None)
        supported = self.extractor.supports(context)
        assert supported is False

    def test_supports_zeiss_tiff(self, zeiss_tiff_file):
        """Test that the extractor supports tif files with Zeiss tags."""
        context = ExtractionContext(zeiss_tiff_file, instrument=None)
        supported = self.extractor.supports(context)
        assert supported is True

    def test_supports_fibics_tiff(self, fibics_tiff_file):
        """Test that the extractor supports tif files with Zeiss tags."""
        context = ExtractionContext(fibics_tiff_file, instrument=None)
        supported = self.extractor.supports(context)
        assert supported is True

    def test_does_not_support_non_tif_files(self):
        """Test that the extractor does not support non-TIFF files."""
        context = ExtractionContext(Path("test.dm3"), instrument=None)
        result = self.extractor.supports(context)
        assert result is False

    def test_extract_returns_dict_with_nx_meta(self, minimal_tiff_file):
        """
        Test that extract() returns a list with a dictionary containing 'nx_meta' key.

        The extraction will fail because the TIFF doesn't have the required
        Zeiss/Fibics metadata tags, but should still return basic metadata.
        """
        context = ExtractionContext(minimal_tiff_file, instrument=None)
        result = self.extractor.extract(context)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "nx_meta" in result[0]
        assert isinstance(result[0]["nx_meta"], dict)
        assert result[0]["nx_meta"].get("Data Type") == "Unknown"
        assert result[0]["nx_meta"].get("DatasetType") == "Image"
        assert "Could not detect Zeiss/Fibics variant" in result[0]["nx_meta"].get(
            "Extractor Warnings", ""
        )
        assert "Creation Time" in result[0]["nx_meta"]

    def test_extract_handles_corrupted_xml(self, zeiss_tiff_file):
        """Test that extract() handles corrupted XML gracefully."""
        context = ExtractionContext(zeiss_tiff_file, instrument=None)

        # Mock a TIFF with corrupted XML in the Zeiss tag
        with patch.object(self.extractor, "_detect_variant") as mock_detect:
            mock_detect.return_value = "zeiss"
            with patch("xml.etree.ElementTree.fromstring") as mock_fromstring:
                mock_fromstring.side_effect = ET.ParseError("Corrupted XML")
                result = self.extractor.extract(context)
                nx_meta = result[0]["nx_meta"]
                # Should handle the error gracefully
                assert "Extractor Warnings" in nx_meta
                assert (
                    nx_meta["Extractor Warnings"] == "Extraction failed: Corrupted XML"
                )

    def test_extract_handles_unknown_variant(self, unknown_xml_tiff_file):
        """Test that extract() handles unknown variants gracefully."""
        context = ExtractionContext(unknown_xml_tiff_file, instrument=None)
        result = self.extractor.extract(context)
        nx_meta = result[0]["nx_meta"]
        # Should handle unknown variant gracefully
        assert nx_meta["Data Type"] == "Unknown"
        assert "Extractor Warnings" in nx_meta
        assert nx_meta["Extractor Warnings"] == "Could not detect Zeiss/Fibics variant"

    def test_detect_variant_zeiss(self, zeiss_tiff_file):
        """Test variant detection for Zeiss files."""
        img = Image.open(zeiss_tiff_file)
        result = self.extractor._detect_variant(img)
        assert result == "zeiss"

    def test_detect_variant_fibics(self, fibics_tiff_file):
        """Test variant detection for Fibics files."""
        img = Image.open(fibics_tiff_file)
        result = self.extractor._detect_variant(img)
        assert result == "fibics"

    def test_detect_variant_neither(self, unknown_xml_tiff_file):
        """Test variant detection when neither format is found."""
        img = Image.open(unknown_xml_tiff_file)
        result = self.extractor._detect_variant(img)
        assert result is None

    def test_extract_from_real_orion_zeiss_file(self, orion_zeiss_zeroed_file):  # noqa: PLR0915
        """Test extraction from real Zeiss Orion TIFF file."""
        if orion_zeiss_zeroed_file is None:
            pytest.skip("Real test file not available")

        context = ExtractionContext(orion_zeiss_zeroed_file, instrument=None)
        result = self.extractor.extract(context)

        # Should extract successfully
        assert isinstance(result, list)
        assert "nx_meta" in result[0]
        assert result[0]["nx_meta"]["Data Type"] == "HIM_Imaging"
        assert result[0]["nx_meta"]["DatasetType"] == "Image"

        assert isinstance(result[0]["nx_meta"]["acceleration_voltage"], ureg.Quantity)
        assert float(result[0]["nx_meta"]["acceleration_voltage"].magnitude) == 29.997
        assert result[0]["nx_meta"]["acceleration_voltage"].units == ureg.kilovolt

        # Random sampling of extracted values from real file
        # Beam section - now Pint Quantities (in extensions)
        beam = get_field(result, "Beam")
        assert beam["Spot Number"] == 6.0  # Dimensionless
        assert isinstance(beam["Pan X"], ureg.Quantity)
        assert float(beam["Pan X"].magnitude) == 3.0
        assert beam["Pan X"].units == ureg.micrometer
        assert isinstance(beam["Extraction Voltage"], ureg.Quantity)
        assert float(beam["Extraction Voltage"].magnitude) == -36.769
        assert beam["Extraction Voltage"].units == ureg.kilovolt
        # GFIS section
        gfis = get_field(result, "GFIS")
        assert gfis["Ion Gas"] == "Helium"  # String
        assert isinstance(gfis["Beam Current"], ureg.Quantity)
        assert float(gfis["Beam Current"].magnitude) == 0.938
        assert gfis["Beam Current"].units == ureg.picoampere
        assert isinstance(gfis["Crossover Position"], ureg.Quantity)
        assert float(gfis["Crossover Position"].magnitude) == -246.999
        assert gfis["Crossover Position"].units == ureg.millimeter
        # Calibration
        calibration = get_field(result, "Calibration")
        assert isinstance(calibration["X Scale"], ureg.Quantity)
        assert float(calibration["X Scale"].magnitude) == 9.765625e-10
        assert calibration["X Scale"].units == ureg.meter
        # Detector
        detector = get_field(result, "Detector")
        assert detector["ET Image Intensity"] == 23.3  # Dimensionless
        assert detector["Name"] == "ETDetector"  # String
        # Scan
        scan = get_field(result, "Scan")
        assert scan["Averaging Mode"] == "Line"  # String
        assert scan["Number of Averages"] == 64.0  # Dimensionless
        # Stage Position
        stage = get_field(result, "Stage Position")
        assert isinstance(stage["X"], ureg.Quantity)
        assert float(stage["X"].magnitude) == 25157.23
        assert stage["X"].units == ureg.micrometer
        assert isinstance(stage["Tilt"], ureg.Quantity)
        assert float(stage["Tilt"].magnitude) == 0.16
        assert stage["Tilt"].units == ureg.degree
        # System
        system = get_field(result, "System")
        assert system["Column Type"] == "GFIS"  # String
        assert isinstance(system["Gun Temperature"], ureg.Quantity)
        assert float(system["Gun Temperature"].magnitude) == 75.5
        assert system["Gun Temperature"].units == ureg.kelvin
        # Optics
        optics = get_field(result, "Optics")
        assert isinstance(optics["sFIM Field of View"], ureg.Quantity)
        assert float(optics["sFIM Field of View"].magnitude) == 0.04
        assert optics["sFIM Field of View"].units == ureg.micrometer
        assert isinstance(optics["MC X Shift"], ureg.Quantity)
        assert float(optics["MC X Shift"].magnitude) == -0.0007959
        assert optics["MC X Shift"].units == ureg.microradian
        # Image dimensions
        image = get_field(result, "Image")
        assert image["Height"] == 1024.0  # Dimensionless
        assert image["Width"] == 1024.0  # Dimensionless

    def test_voltage_unit_conversions(self, orion_zeiss_zeroed_file):
        """Test that voltages are correctly converted from V to kV Pint Quantities."""
        if orion_zeiss_zeroed_file is None:
            pytest.skip("Real test file not available")

        context = ExtractionContext(orion_zeiss_zeroed_file, instrument=None)
        result = self.extractor.extract(context)

        # Test various voltage conversions (V to kV, multiply by 1000)
        # acceleration voltage should be at top level
        acc_voltage = get_field(result, "acceleration_voltage")
        assert isinstance(acc_voltage, ureg.Quantity)
        assert float(acc_voltage.magnitude) == 29.997  # AccelerationVoltage: 29997 V
        assert acc_voltage.units == ureg.kilovolt

        # Beam section voltages (in extensions)
        beam = get_field(result, "Beam")
        assert isinstance(beam["Extraction Voltage"], ureg.Quantity)
        assert (
            float(beam["Extraction Voltage"].magnitude) == -36.769
        )  # ExtractionVoltage: -36769 V
        assert beam["Extraction Voltage"].units == ureg.kilovolt

        # GFIS section voltages (same values as non-GFIS versions)
        gfis = get_field(result, "GFIS")
        assert isinstance(gfis["Acceleration Voltage"], ureg.Quantity)
        assert float(gfis["Acceleration Voltage"].magnitude) == 29.997
        assert gfis["Acceleration Voltage"].units == ureg.kilovolt
        assert isinstance(gfis["Extraction Voltage"], ureg.Quantity)
        assert float(gfis["Extraction Voltage"].magnitude) == -36.769
        assert gfis["Extraction Voltage"].units == ureg.kilovolt
        assert isinstance(gfis["Condenser Voltage"], ureg.Quantity)
        assert (
            float(gfis["Condenser Voltage"].magnitude) == 23.995
        )  # Lens1Voltage: 23995 V
        assert gfis["Condenser Voltage"].units == ureg.kilovolt
        assert isinstance(gfis["Objective Voltage"], ureg.Quantity)
        assert (
            float(gfis["Objective Voltage"].magnitude) == 18.535
        )  # Lens2Voltage: 18535 V
        assert gfis["Objective Voltage"].units == ureg.kilovolt

        # Optics section voltages (Lens voltages)
        optics = get_field(result, "Optics")
        assert isinstance(optics["Lens 1 Voltage"], ureg.Quantity)
        assert float(optics["Lens 1 Voltage"].magnitude) == 23.995
        assert optics["Lens 1 Voltage"].units == ureg.kilovolt
        assert isinstance(optics["Lens 2 Voltage"], ureg.Quantity)
        assert float(optics["Lens 2 Voltage"].magnitude) == 18.535
        assert optics["Lens 2 Voltage"].units == ureg.kilovolt

        # Detector scintillator voltage
        detector = get_field(result, "Detector")
        assert isinstance(detector["Scintillator"], ureg.Quantity)
        assert (
            float(detector["Scintillator"].magnitude) == 10.000
        )  # Detector.Scintillator: 10000 V
        assert detector["Scintillator"].units == ureg.kilovolt

    def test_extract_from_real_orion_fibics_file(self, orion_fibics_zeroed_file):  # noqa: PLR0915
        """Test extraction from real Fibics Orion TIFF file."""
        if orion_fibics_zeroed_file is None:
            pytest.skip("Real test file not available")

        context = ExtractionContext(orion_fibics_zeroed_file, instrument=None)
        result = self.extractor.extract(context)

        # Should extract successfully
        assert isinstance(result, list)
        assert "nx_meta" in result[0]
        assert result[0]["nx_meta"]["Data Type"] == "HIM_Imaging"
        assert result[0]["nx_meta"]["DatasetType"] == "Image"

        # Comprehensive value checks from orion_fibics_tif_metadata.xml
        # top-level core values
        dwell_time = get_field(result, "dwell_time")
        assert isinstance(dwell_time, ureg.Quantity)
        # 10000 ns converted to μs
        assert dwell_time.magnitude == 10.0
        assert dwell_time.units == ureg.microsecond
        hfw = get_field(result, "horizontal_field_width")
        assert isinstance(hfw, ureg.Quantity)
        assert hfw.magnitude == 2.5
        assert hfw.units == ureg.micrometer
        vfw = get_field(result, "vertical_field_width")
        assert isinstance(vfw, ureg.Quantity)
        assert vfw.magnitude == 2.5
        assert vfw.units == ureg.micrometer
        scan_rot = get_field(result, "scan_rotation")
        assert isinstance(scan_rot, ureg.Quantity)
        assert scan_rot.magnitude == Decimal("1.23797181004193e-05")
        assert scan_rot.units == ureg.degree
        beam_current = get_field(result, "beam_current")
        assert isinstance(beam_current, ureg.Quantity)
        assert beam_current.magnitude == 1.3275146484375
        assert beam_current.units == ureg.picoampere
        acc_volt = get_field(result, "acceleration_voltage")
        assert isinstance(acc_volt, ureg.Quantity)
        assert acc_volt.magnitude == 30.0
        assert acc_volt.units == ureg.kilovolt

        # Application section (strings, in extensions)
        application = get_field(result, "Application")
        assert application["Software Version"] == "NPVE v4.5"
        assert application["Acquisition Date/Time"] == "2025-05-27T10:32:12.498-04:00"
        assert application["Supports Transparency"] == "true"
        assert application["Transparent Pixel Value"] == 0.0  # Dimensionless

        # Image section (dimensionless and strings)
        image = get_field(result, "Image")
        assert image["Width"] == 2048.0
        assert image["Height"] == 2048.0
        assert image["Bounding Box Left"] == 0.0
        assert image["Bounding Box Right"] == 2048.0
        assert image["Bounding Box Top"] == 0.0
        assert image["Bounding Box Bottom"] == 2048.0
        assert image["Machine Name"] == "CONSOLE18"
        assert image["Beam Type"] == "Orion"
        assert image["Aperture Description"] == "[1] Ne 10 µm (30.0kV|s=5.0)"
        detector = get_field(result, "Detector")
        assert detector["Name"] == "ET"
        assert detector["Contrast"] == 32.466667175293  # Dimensionless
        assert detector["Brightness"] == 55.0  # Dimensionless

        # Scan section - now with Pint Quantities where applicable
        scan = get_field(result, "Scan")
        assert scan["Line Averaging"] == 1.0  # Dimensionless
        assert scan["Affine Ux"] == 0.001220703125  # Dimensionless
        assert scan["Affine Uy"] == 0.0  # Dimensionless
        assert scan["Affine Vx"] == 0.0  # Dimensionless
        assert scan["Affine Vy"] == -0.001220703125  # Dimensionless
        assert scan["Focus Value"] == 0.0118617592379451  # Dimensionless
        assert scan["Stigmator X Value"] == -16.4666652679443  # Dimensionless
        assert scan["Stigmator Y Value"] == 9.63332939147949  # Dimensionless

        # Stage section - now with Pint Quantities
        stage = get_field(result, "Stage Position")
        assert isinstance(stage["X"], ureg.Quantity)
        assert float(stage["X"].magnitude) == -21319.2368624182
        assert stage["X"].units == ureg.micrometer
        assert isinstance(stage["Y"], ureg.Quantity)
        assert float(stage["Y"].magnitude) == -27311.808629448
        assert stage["Y"].units == ureg.micrometer
        assert isinstance(stage["Z"], ureg.Quantity)
        assert float(stage["Z"].magnitude) == 10.80012316379
        assert stage["Z"].units == ureg.micrometer
        assert isinstance(stage["Tilt"], ureg.Quantity)
        assert float(stage["Tilt"].magnitude) == 0.191424190998077
        assert stage["Tilt"].units == ureg.degree
        assert isinstance(stage["Rotation"], ureg.Quantity)
        assert float(stage["Rotation"].magnitude) == 46.2030220031738
        assert stage["Rotation"].units == ureg.degree
        assert isinstance(stage["M"], ureg.Quantity)
        assert float(stage["M"].magnitude) == 0.0
        assert stage["M"].units == ureg.millimeter

        # BeamInfo section (item-based) - now with Pint Quantities
        beam = get_field(result, "Beam")
        assert beam["Aperture"] == 0.0  # Dimensionless
        assert beam["GFIS Gas Type"] == "He"  # String
        assert beam["Gun Gas Pressure"] == 0.0  # Dimensionless (or unknown unit)
        assert beam["Spot Control"] == 5.0  # Dimensionless

        # DetectorInfo section (item-based with unit stripping) - with Pint Quantities
        assert isinstance(detector["Collector Voltage"], ureg.Quantity)
        # "=500.0 V" stripped
        assert float(detector["Collector Voltage"].magnitude) == 500.0
        assert detector["Collector Voltage"].units == ureg.volt
        assert isinstance(detector["Stage Bias Voltage"], ureg.Quantity)
        # "=0.0 V" stripped
        assert float(detector["Stage Bias Voltage"].magnitude) == 0.0
        assert detector["Stage Bias Voltage"].units == ureg.volt

    def test_extractor_priority_higher_than_quanta(self):
        """Test OrionFibicsTiffExtractor is higher priority than QuantaTiffExtractor."""
        from nexusLIMS.extractors.plugins.quanta_tif import QuantaTiffExtractor

        quanta_extractor = QuantaTiffExtractor()
        assert self.extractor.priority > quanta_extractor.priority

    def test_extractor_registered_in_registry(self):
        """Test that the extractor is properly registered in the registry."""
        # Re-register to ensure it's in the registry
        self.registry.register_extractor(OrionTiffExtractor)

        # Get extractors for .tif extension
        tif_extractors = self.registry.get_extractors_for_extension("tif")

        assert len(tif_extractors) == 3  # Should have three tif extractors
        assert any(
            isinstance(i, OrionTiffExtractor) for i in tif_extractors
        )  # at least one should be the Orion extractor

    def test_error_handling_in_supports(self):
        """Test that supports() handles errors gracefully."""
        context = ExtractionContext(Path("nonexistent.tif"), instrument=None)

        # Should not crash even with nonexistent file
        result = self.extractor.supports(context)
        assert isinstance(result, bool)

    def test_error_handling_in_extract(self):
        """Test that extract() handles errors gracefully."""
        # Mock Image.open to raise an exception (simulating invalid TIFF)
        with patch("PIL.Image.open") as mock_open:
            mock_open.side_effect = Exception("Invalid TIFF file")

            # Should not crash even with invalid file
            result = self.extractor.extract(
                ExtractionContext(Path("nonexistent.tif"), instrument=None)
            )
            assert isinstance(result, list)
            assert "nx_meta" in result[0]
            assert "Extractor Warnings" in result[0]["nx_meta"]
            assert (
                result[0]["nx_meta"]["Extractor Warnings"]
                == "Extraction failed: [Errno 2] No such file or directory: "
                "'nonexistent.tif'"
            )

    def test_supports_handles_tiff_open_error(self, tmp_path):
        """Test that supports() handles exceptions when opening TIF files gracefully."""
        # Create a file that looks like a TIFF but will fail to open
        bad_file = tmp_path / "bad.tif"
        bad_file.write_bytes(b"not a valid tiff")

        context = ExtractionContext(bad_file, instrument=None)
        # Should return False instead of raising an exception
        result = self.extractor.supports(context)
        assert result is False

    def test_zeiss_xml_parse_error_handling(self, tmp_path):
        """Test that malformed Zeiss XML is handled gracefully in variant detection."""
        file_path = tmp_path / "bad_zeiss.tif"

        # Create TIFF with malformed Zeiss XML
        _create_tiff_with_custom_tags(
            file_path,
            zeiss_xml="<ImageTags><InvalidXML>unclosed tag</ImageTags>",
        )

        with Image.open(file_path) as img:
            result = self.extractor._detect_variant(img)
            # Should return None instead of raising exception
            assert result is None

    def test_fibics_xml_parse_error_handling(self, tmp_path):
        """Test that malformed Fibics XML is handled gracefully in variant detection."""
        file_path = tmp_path / "bad_fibics.tif"

        # Create TIFF with malformed Fibics XML
        _create_tiff_with_custom_tags(
            file_path,
            fibics_xml="<Fibics><InvalidXML>unclosed tag</Fibics>",
        )

        with Image.open(file_path) as img:
            result = self.extractor._detect_variant(img)
            # Should return None instead of raising exception
            assert result is None

    def test_parse_zeiss_field_with_nested_path_navigation(self, tmp_path):
        """Test that Zeiss nested XML paths trigger fallback navigation."""
        file_path = tmp_path / "nested_zeiss.tif"

        # Create TIFF with nested Zeiss XML structure
        # Using nested elements to force fallback navigation code path
        nested_zeiss_xml = """<ImageTags>
            <System><Name><Value>TestSystem</Value></Name></System>
        </ImageTags>"""

        _create_tiff_with_custom_tags(file_path, zeiss_xml=nested_zeiss_xml)

        context = ExtractionContext(file_path, instrument=None)
        result = self.extractor.extract(context)
        # Should handle nested path without crashing
        assert isinstance(result, list)
        assert "nx_meta" in result[0]

    def test_fibics_extraction_full_path(self, fibics_tiff_file):
        """
        Test complete Fibics extraction.

        Includes dwell conversion, item fields, and unit stripping.
        """
        context = ExtractionContext(fibics_tiff_file, instrument=None)
        result = self.extractor.extract(context)

        # Verify dwell time conversion (ns to μs) as Pint Quantity
        dwell_time = get_field(result, "dwell_time")
        assert isinstance(dwell_time, ureg.Quantity)
        assert dwell_time.magnitude == 10.0
        assert dwell_time.units == ureg.microsecond

        # Verify beam current converted to pA
        beam_current = get_field(result, "beam_current")
        assert isinstance(beam_current, ureg.Quantity)
        assert beam_current.magnitude == 1.3275146484375
        assert beam_current.units == ureg.picoampere

        # Verify unit stripping works (should be
        # "Collector Voltage" rather than "Collector")
        detector = get_field(result, "Detector")
        assert "Collector Voltage" in detector

    def test_parse_zeiss_field_exception_handling(self):
        """Test that _parse_zeiss_field handles exceptions during parsing gracefully."""
        from unittest.mock import MagicMock

        root = MagicMock()
        root.find.side_effect = Exception("Mock error")
        mdict = {"nx_meta": {}}

        # Should not crash, just log and return
        self.extractor._parse_zeiss_field(root, "TestField", "test_key", mdict, 1.0)

        # mdict should not be modified
        assert "test_key" not in mdict["nx_meta"]

    def test_parse_fibics_value_exception_in_field_parsing(self):
        """Test that _parse_fibics_value handles exceptions when parsing fields."""
        from unittest.mock import MagicMock

        section = MagicMock()
        section.find.side_effect = Exception("Mock error")
        section.findall.side_effect = Exception("Mock error")

        result = self.extractor._parse_fibics_value(section, "TestField", 1.0)
        # Should return None on exception
        assert result is None

    def test_parse_fibics_value_numeric_conversion_with_non_numeric_input(self):
        """Test that _parse_fibics_value falls back to string when conversion fails."""
        import xml.etree.ElementTree as ET

        section = ET.Element("TestSection")
        field = ET.Element("NumField")
        field.text = "abc123xyz"  # Mixed alphanumeric
        section.append(field)

        result = self.extractor._parse_fibics_value(section, "NumField", 1.0)
        # Should return the string value, not crash
        assert result == "abc123xyz"
        assert isinstance(result, str)

    def test_parse_fibics_value_strip_units_with_non_numeric_value(self):
        """Test _parse_fibics_value with strip_units and non-numeric value."""
        import xml.etree.ElementTree as ET

        section = ET.Element("TestSection")
        field = ET.Element("UnitField")
        field.text = "=invalid V"  # Has unit format but non-numeric value
        section.append(field)

        result = self.extractor._parse_fibics_value(section, "UnitField", "strip_units")
        # Should return the text portion after stripping
        assert result == "invalid"

    def test_parse_fibics_value_strip_units_numeric_without_unit(self):
        """Test _parse_fibics_value with strip_units, numeric value, but no unit arg.

        This tests line 968 in orion_HIM_tif.py where conversion_factor is
        "strip_units", the value converts to float successfully, but unit=None
        so it returns the raw numeric value instead of a Quantity.
        """
        import xml.etree.ElementTree as ET

        section = ET.Element("TestSection")
        field = ET.Element("NumericField")
        field.text = "=42.5 V"  # Numeric value with unit suffix
        section.append(field)

        # Call with strip_units but no unit parameter (defaults to None)
        result = self.extractor._parse_fibics_value(
            section, "NumericField", "strip_units", unit=None
        )
        # Should return numeric value without creating a Quantity
        assert result == 42.5
        assert not isinstance(result, ureg.Quantity)

    def test_find_fibics_section_exception_handling(self):
        """Test that _find_fibics_section handles exceptions during iteration."""
        from unittest.mock import MagicMock

        root = MagicMock()
        # Make iteration raise an exception
        root.__iter__.side_effect = Exception("Mock iteration error")

        result = self.extractor._find_fibics_section(root, "TestSection")
        # Should return None on exception instead of crashing
        assert result is None

    def test_find_fibics_section_not_found(self):
        """Test that _find_fibics_section returns None when section not found."""
        import xml.etree.ElementTree as ET

        root = ET.Element("Root")
        # Add some children that don't match
        child1 = ET.Element("Section1")
        child2 = ET.Element("Section2")
        root.append(child1)
        root.append(child2)

        result = self.extractor._find_fibics_section(root, "NonExistent")
        # Should return None when section not found
        assert result is None

    def test_migrate_to_schema_compliant_metadata_with_field_renaming(self):
        """Test that display names are renamed to EM Glossary names.

        This test covers orion_HIM_tif.py where fields with
        display names (like "Acceleration Voltage") are renamed to EM Glossary
        names (like "acceleration_voltage") and kept at the top level.
        """
        # Create metadata dict with fields using display names
        mdict = {
            "nx_meta": {
                "DatasetType": "Image",
                "Data Type": "HIM_Imaging",
                "Creation Time": "2024-01-15T10:30:00-05:00",
                # Add fields with display names that need renaming
                "Acceleration Voltage": ureg.Quantity(30.0, "kilovolt"),
                "Working Distance": ureg.Quantity(5.0, "millimeter"),
                "Beam Current": ureg.Quantity(1.5, "picoampere"),
                "Emission Current": ureg.Quantity(100.0, "microampere"),
                "Dwell Time": ureg.Quantity(10.0, "microsecond"),
                "Field of View": ureg.Quantity(50.0, "micrometer"),
                "Pixel Width": ureg.Quantity(0.1, "micrometer"),
                "Pixel Height": ureg.Quantity(0.1, "micrometer"),
                # Add a vendor-specific section that should go to extensions
                "Beam": {"some_field": "value"},
            }
        }

        # Call the migration method
        result = self.extractor._migrate_to_schema_compliant_metadata(mdict)

        # Verify display names were renamed to EM Glossary names and stayed at top level
        assert "acceleration_voltage" in result["nx_meta"]
        assert result["nx_meta"]["acceleration_voltage"] == ureg.Quantity(
            30.0, "kilovolt"
        )

        assert "working_distance" in result["nx_meta"]
        assert result["nx_meta"]["working_distance"] == ureg.Quantity(5.0, "millimeter")

        assert "beam_current" in result["nx_meta"]
        assert result["nx_meta"]["beam_current"] == ureg.Quantity(1.5, "picoampere")

        assert "emission_current" in result["nx_meta"]
        assert result["nx_meta"]["emission_current"] == ureg.Quantity(
            100.0, "microampere"
        )

        assert "dwell_time" in result["nx_meta"]
        assert result["nx_meta"]["dwell_time"] == ureg.Quantity(10.0, "microsecond")

        assert "horizontal_field_width" in result["nx_meta"]
        assert result["nx_meta"]["horizontal_field_width"] == ureg.Quantity(
            50.0, "micrometer"
        )

        assert "pixel_width" in result["nx_meta"]
        assert result["nx_meta"]["pixel_width"] == ureg.Quantity(0.1, "micrometer")

        assert "pixel_height" in result["nx_meta"]
        assert result["nx_meta"]["pixel_height"] == ureg.Quantity(0.1, "micrometer")

        # Verify original display names are NOT at top level
        assert "Acceleration Voltage" not in result["nx_meta"]
        assert "Working Distance" not in result["nx_meta"]
        assert "Beam Current" not in result["nx_meta"]
        assert "Emission Current" not in result["nx_meta"]
        assert "Dwell Time" not in result["nx_meta"]
        assert "Field of View" not in result["nx_meta"]
        assert "Pixel Width" not in result["nx_meta"]
        assert "Pixel Height" not in result["nx_meta"]

        # Verify vendor sections went to extensions
        assert "extensions" in result["nx_meta"]
        assert "Beam" in result["nx_meta"]["extensions"]
        assert result["nx_meta"]["extensions"]["Beam"]["some_field"] == "value"

        # Verify core fields stayed at top level
        assert result["nx_meta"]["DatasetType"] == "Image"
        assert result["nx_meta"]["Data Type"] == "HIM_Imaging"
        assert result["nx_meta"]["Creation Time"] == "2024-01-15T10:30:00-05:00"
