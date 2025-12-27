"""Tests for the Zeiss Orion/Fibics TIFF extractor plugin."""

import xml.etree.ElementTree as ET
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
        result = self.extractor._detect_variant(img)  # noqa: SLF001
        assert result == "zeiss"

    def test_detect_variant_fibics(self, fibics_tiff_file):
        """Test variant detection for Fibics files."""
        img = Image.open(fibics_tiff_file)
        result = self.extractor._detect_variant(img)  # noqa: SLF001
        assert result == "fibics"

    def test_detect_variant_neither(self, unknown_xml_tiff_file):
        """Test variant detection when neither format is found."""
        img = Image.open(unknown_xml_tiff_file)
        result = self.extractor._detect_variant(img)  # noqa: SLF001
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

        # Random sampling of extracted values from real file
        meta = result[0]["nx_meta"]
        # Beam section - now Pint Quantities
        assert isinstance(meta["Beam"]["Voltage"], ureg.Quantity)
        assert meta["Beam"]["Voltage"].magnitude == pytest.approx(29.997)
        assert meta["Beam"]["Voltage"].units == ureg.kilovolt
        assert meta["Beam"]["Spot Number"] == 6.0  # Dimensionless
        assert isinstance(meta["Beam"]["Pan X"], ureg.Quantity)
        assert meta["Beam"]["Pan X"].magnitude == pytest.approx(3.0)
        assert meta["Beam"]["Pan X"].units == ureg.micrometer
        assert isinstance(meta["Beam"]["Extraction Voltage"], ureg.Quantity)
        assert meta["Beam"]["Extraction Voltage"].magnitude == pytest.approx(-36.769)
        assert meta["Beam"]["Extraction Voltage"].units == ureg.kilovolt
        # GFIS section
        assert meta["GFIS"]["Ion Gas"] == "Helium"  # String
        assert isinstance(meta["GFIS"]["Beam Current"], ureg.Quantity)
        assert meta["GFIS"]["Beam Current"].magnitude == pytest.approx(0.938)
        assert meta["GFIS"]["Beam Current"].units == ureg.picoampere
        assert isinstance(meta["GFIS"]["Crossover Position"], ureg.Quantity)
        assert meta["GFIS"]["Crossover Position"].magnitude == pytest.approx(-246.999)
        assert meta["GFIS"]["Crossover Position"].units == ureg.millimeter
        # Calibration
        assert isinstance(meta["Calibration"]["X Scale"], ureg.Quantity)
        assert meta["Calibration"]["X Scale"].magnitude == pytest.approx(9.765625e-10)
        assert meta["Calibration"]["X Scale"].units == ureg.meter
        # Detector
        assert meta["Detector"]["ET Image Intensity"] == 23.3  # Dimensionless
        assert meta["Detector"]["Name"] == "ETDetector"  # String
        # Scan
        assert meta["Scan"]["Averaging Mode"] == "Line"  # String
        assert meta["Scan"]["Number of Averages"] == 64.0  # Dimensionless
        # Stage Position
        assert isinstance(meta["Stage Position"]["X"], ureg.Quantity)
        assert meta["Stage Position"]["X"].magnitude == pytest.approx(25157.23)
        assert meta["Stage Position"]["X"].units == ureg.micrometer
        assert isinstance(meta["Stage Position"]["Tilt"], ureg.Quantity)
        assert meta["Stage Position"]["Tilt"].magnitude == pytest.approx(0.16)
        assert meta["Stage Position"]["Tilt"].units == ureg.degree
        # System
        assert meta["System"]["Column Type"] == "GFIS"  # String
        assert isinstance(meta["System"]["Gun Temperature"], ureg.Quantity)
        assert meta["System"]["Gun Temperature"].magnitude == pytest.approx(75.5)
        assert meta["System"]["Gun Temperature"].units == ureg.kelvin
        # Optics
        assert isinstance(meta["Optics"]["sFIM Field of View"], ureg.Quantity)
        assert meta["Optics"]["sFIM Field of View"].magnitude == pytest.approx(0.04)
        assert meta["Optics"]["sFIM Field of View"].units == ureg.micrometer
        assert isinstance(meta["Optics"]["MC X Shift"], ureg.Quantity)
        assert meta["Optics"]["MC X Shift"].magnitude == pytest.approx(-0.0007959)
        assert meta["Optics"]["MC X Shift"].units == ureg.microradian
        # Image dimensions
        assert meta["Image"]["Height"] == 1024.0  # Dimensionless
        assert meta["Image"]["Width"] == 1024.0  # Dimensionless

    def test_voltage_unit_conversions(self, orion_zeiss_zeroed_file):
        """Test that voltages are correctly converted from V to kV Pint Quantities."""
        if orion_zeiss_zeroed_file is None:
            pytest.skip("Real test file not available")

        context = ExtractionContext(orion_zeiss_zeroed_file, instrument=None)
        result = self.extractor.extract(context)
        meta = result[0]["nx_meta"]

        # Test various voltage conversions (V to kV, multiply by 1000)
        # Beam section voltages
        assert isinstance(meta["Beam"]["Voltage"], ureg.Quantity)
        assert meta["Beam"]["Voltage"].magnitude == pytest.approx(
            29.997
        )  # AccelerationVoltage: 29997 V
        assert meta["Beam"]["Voltage"].units == ureg.kilovolt
        assert isinstance(meta["Beam"]["Extraction Voltage"], ureg.Quantity)
        assert meta["Beam"]["Extraction Voltage"].magnitude == pytest.approx(
            -36.769
        )  # ExtractionVoltage: -36769 V
        assert meta["Beam"]["Extraction Voltage"].units == ureg.kilovolt

        # GFIS section voltages (same values as non-GFIS versions)
        assert isinstance(meta["GFIS"]["Acceleration Voltage"], ureg.Quantity)
        assert meta["GFIS"]["Acceleration Voltage"].magnitude == pytest.approx(29.997)
        assert meta["GFIS"]["Acceleration Voltage"].units == ureg.kilovolt
        assert isinstance(meta["GFIS"]["Extraction Voltage"], ureg.Quantity)
        assert meta["GFIS"]["Extraction Voltage"].magnitude == pytest.approx(-36.769)
        assert meta["GFIS"]["Extraction Voltage"].units == ureg.kilovolt
        assert isinstance(meta["GFIS"]["Condenser Voltage"], ureg.Quantity)
        assert meta["GFIS"]["Condenser Voltage"].magnitude == pytest.approx(
            23.995
        )  # Lens1Voltage: 23995 V
        assert meta["GFIS"]["Condenser Voltage"].units == ureg.kilovolt
        assert isinstance(meta["GFIS"]["Objective Voltage"], ureg.Quantity)
        assert meta["GFIS"]["Objective Voltage"].magnitude == pytest.approx(
            18.535
        )  # Lens2Voltage: 18535 V
        assert meta["GFIS"]["Objective Voltage"].units == ureg.kilovolt

        # Optics section voltages (Lens voltages)
        assert isinstance(meta["Optics"]["Lens 1 Voltage"], ureg.Quantity)
        assert meta["Optics"]["Lens 1 Voltage"].magnitude == pytest.approx(23.995)
        assert meta["Optics"]["Lens 1 Voltage"].units == ureg.kilovolt
        assert isinstance(meta["Optics"]["Lens 2 Voltage"], ureg.Quantity)
        assert meta["Optics"]["Lens 2 Voltage"].magnitude == pytest.approx(18.535)
        assert meta["Optics"]["Lens 2 Voltage"].units == ureg.kilovolt

        # Detector scintillator voltage
        assert isinstance(meta["Detector"]["Scintillator"], ureg.Quantity)
        assert meta["Detector"]["Scintillator"].magnitude == pytest.approx(
            10.000
        )  # Detector.Scintillator: 10000 V
        assert meta["Detector"]["Scintillator"].units == ureg.kilovolt

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
        meta = result[0]["nx_meta"]

        # Application section (strings)
        assert meta["Application"]["Software Version"] == "NPVE v4.5"
        assert (
            meta["Application"]["Acquisition Date/Time"]
            == "2025-05-27T10:32:12.498-04:00"
        )
        assert meta["Application"]["Supports Transparency"] == "true"
        assert meta["Application"]["Transparent Pixel Value"] == 0.0  # Dimensionless

        # Image section (dimensionless and strings)
        assert meta["Image"]["Width"] == 2048.0
        assert meta["Image"]["Height"] == 2048.0
        assert meta["Image"]["Bounding Box Left"] == 0.0
        assert meta["Image"]["Bounding Box Right"] == 2048.0
        assert meta["Image"]["Bounding Box Top"] == 0.0
        assert meta["Image"]["Bounding Box Bottom"] == 2048.0
        assert meta["Image"]["Machine Name"] == "CONSOLE18"
        assert meta["Image"]["Beam Type"] == "Orion"
        assert meta["Image"]["Aperture Description"] == "[1] Ne 10 µm (30.0kV|s=5.0)"
        assert meta["Detector"]["Name"] == "ET"
        assert meta["Detector"]["Contrast"] == 32.466667175293  # Dimensionless
        assert meta["Detector"]["Brightness"] == 55.0  # Dimensionless

        # Scan section - now with Pint Quantities where applicable
        assert isinstance(meta["Scan"]["Pixel Dwell Time"], ureg.Quantity)
        assert meta["Scan"]["Pixel Dwell Time"].magnitude == pytest.approx(
            10.0
        )  # 10000 ns converted to μs
        assert meta["Scan"]["Pixel Dwell Time"].units == ureg.microsecond
        assert meta["Scan"]["Line Averaging"] == 1.0  # Dimensionless
        assert isinstance(meta["Scan"]["Field of View X"], ureg.Quantity)
        assert meta["Scan"]["Field of View X"].magnitude == pytest.approx(2.5)
        assert meta["Scan"]["Field of View X"].units == ureg.micrometer
        assert isinstance(meta["Scan"]["Field of View Y"], ureg.Quantity)
        assert meta["Scan"]["Field of View Y"].magnitude == pytest.approx(2.5)
        assert meta["Scan"]["Field of View Y"].units == ureg.micrometer
        assert isinstance(meta["Scan"]["Scan Rotation"], ureg.Quantity)
        assert meta["Scan"]["Scan Rotation"].magnitude == pytest.approx(
            1.23797181004193e-05
        )
        assert meta["Scan"]["Scan Rotation"].units == ureg.degree
        assert meta["Scan"]["Affine Ux"] == 0.001220703125  # Dimensionless
        assert meta["Scan"]["Affine Uy"] == 0.0  # Dimensionless
        assert meta["Scan"]["Affine Vx"] == 0.0  # Dimensionless
        assert meta["Scan"]["Affine Vy"] == -0.001220703125  # Dimensionless
        assert meta["Scan"]["Focus Value"] == 0.0118617592379451  # Dimensionless
        assert meta["Scan"]["Stigmator X Value"] == -16.4666652679443  # Dimensionless
        assert meta["Scan"]["Stigmator Y Value"] == 9.63332939147949  # Dimensionless

        # Stage section - now with Pint Quantities
        assert isinstance(meta["Stage Position"]["X"], ureg.Quantity)
        assert meta["Stage Position"]["X"].magnitude == pytest.approx(-21319.2368624182)
        assert meta["Stage Position"]["X"].units == ureg.micrometer
        assert isinstance(meta["Stage Position"]["Y"], ureg.Quantity)
        assert meta["Stage Position"]["Y"].magnitude == pytest.approx(-27311.808629448)
        assert meta["Stage Position"]["Y"].units == ureg.micrometer
        assert isinstance(meta["Stage Position"]["Z"], ureg.Quantity)
        assert meta["Stage Position"]["Z"].magnitude == pytest.approx(10.80012316379)
        assert meta["Stage Position"]["Z"].units == ureg.micrometer
        assert isinstance(meta["Stage Position"]["Tilt"], ureg.Quantity)
        assert meta["Stage Position"]["Tilt"].magnitude == pytest.approx(
            0.191424190998077
        )
        assert meta["Stage Position"]["Tilt"].units == ureg.degree
        assert isinstance(meta["Stage Position"]["Rotation"], ureg.Quantity)
        assert meta["Stage Position"]["Rotation"].magnitude == pytest.approx(
            46.2030220031738
        )
        assert meta["Stage Position"]["Rotation"].units == ureg.degree
        assert isinstance(meta["Stage Position"]["M"], ureg.Quantity)
        assert meta["Stage Position"]["M"].magnitude == pytest.approx(0.0)
        assert meta["Stage Position"]["M"].units == ureg.millimeter

        # BeamInfo section (item-based) - now with Pint Quantities
        assert isinstance(meta["Beam"]["Beam Current"], ureg.Quantity)
        assert meta["Beam"]["Beam Current"].magnitude == pytest.approx(1.3275146484375)
        assert meta["Beam"]["Beam Current"].units == ureg.picoampere
        assert isinstance(meta["Beam"]["Acceleration Voltage"], ureg.Quantity)
        assert meta["Beam"]["Acceleration Voltage"].magnitude == pytest.approx(
            30.0
        )  # 30000 V converted to kV
        assert meta["Beam"]["Acceleration Voltage"].units == ureg.kilovolt
        assert meta["Beam"]["Aperture"] == 0.0  # Dimensionless
        assert meta["Beam"]["GFIS Gas Type"] == "He"  # String
        assert (
            meta["Beam"]["Gun Gas Pressure"] == 0.0
        )  # Dimensionless (or unknown unit)
        assert meta["Beam"]["Spot Control"] == 5.0  # Dimensionless

        # DetectorInfo section (item-based with unit stripping) - with Pint Quantities
        assert isinstance(meta["Detector"]["Collector Voltage"], ureg.Quantity)
        assert meta["Detector"]["Collector Voltage"].magnitude == pytest.approx(
            500.0
        )  # "=500.0 V" stripped
        assert meta["Detector"]["Collector Voltage"].units == ureg.volt
        assert isinstance(meta["Detector"]["Stage Bias Voltage"], ureg.Quantity)
        assert meta["Detector"]["Stage Bias Voltage"].magnitude == pytest.approx(
            0.0
        )  # "=0.0 V" stripped
        assert meta["Detector"]["Stage Bias Voltage"].units == ureg.volt

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
            result = self.extractor._detect_variant(img)  # noqa: SLF001
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
            result = self.extractor._detect_variant(img)  # noqa: SLF001
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
        meta = result[0]["nx_meta"]

        # Verify dwell time conversion (ns to μs) as Pint Quantity
        assert isinstance(meta["Scan"]["Pixel Dwell Time"], ureg.Quantity)
        assert meta["Scan"]["Pixel Dwell Time"].magnitude == pytest.approx(10.0)
        assert meta["Scan"]["Pixel Dwell Time"].units == ureg.microsecond
        # Verify item-based field extraction
        assert "Beam Current" in meta.get("Beam", {})
        # Verify unit stripping works
        assert "Collector Voltage" in meta.get("Detector", {})

    def test_parse_zeiss_field_exception_handling(self):
        """Test that _parse_zeiss_field handles exceptions during parsing gracefully."""
        from unittest.mock import MagicMock

        root = MagicMock()
        root.find.side_effect = Exception("Mock error")
        mdict = {"nx_meta": {}}

        # Should not crash, just log and return
        self.extractor._parse_zeiss_field(  # noqa: SLF001
            root, "TestField", "test_key", mdict, 1.0
        )

        # mdict should not be modified
        assert "test_key" not in mdict["nx_meta"]

    def test_parse_fibics_value_exception_in_field_parsing(self):
        """Test that _parse_fibics_value handles exceptions when parsing fields."""
        from unittest.mock import MagicMock

        section = MagicMock()
        section.find.side_effect = Exception("Mock error")
        section.findall.side_effect = Exception("Mock error")

        result = self.extractor._parse_fibics_value(  # noqa: SLF001
            section, "TestField", 1.0
        )
        # Should return None on exception
        assert result is None

    def test_parse_fibics_value_numeric_conversion_with_non_numeric_input(self):
        """Test that _parse_fibics_value falls back to string when conversion fails."""
        import xml.etree.ElementTree as ET

        section = ET.Element("TestSection")
        field = ET.Element("NumField")
        field.text = "abc123xyz"  # Mixed alphanumeric
        section.append(field)

        result = self.extractor._parse_fibics_value(section, "NumField", 1.0)  # noqa: SLF001
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

        result = self.extractor._parse_fibics_value(  # noqa: SLF001
            section, "UnitField", "strip_units"
        )
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
        result = self.extractor._parse_fibics_value(  # noqa: SLF001
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

        result = self.extractor._find_fibics_section(root, "TestSection")  # noqa: SLF001
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

        result = self.extractor._find_fibics_section(root, "NonExistent")  # noqa: SLF001
        # Should return None when section not found
        assert result is None
