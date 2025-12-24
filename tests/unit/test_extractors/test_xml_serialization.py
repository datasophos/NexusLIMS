"""
Tests for the XML serialization layer.

This module tests the conversion of new-style metadata (with Pint Quantities
and EM Glossary field names) to XML-compatible format.
"""

from nexusLIMS.extractors.xml_serialization import (
    EM_GLOSSARY_TO_XML_DISPLAY_NAMES,
    get_emg_id,
    get_qudt_uri,
    get_xml_field_name,
    prepare_metadata_for_xml,
    serialize_quantity_to_xml,
)
from nexusLIMS.schemas.units import ureg


class TestSerializeQuantityToXML:
    """Tests for serialize_quantity_to_xml function."""

    def test_serialize_basic_units(self):
        """Test serializing quantities with standard units."""
        # Test kilovolt
        qty_kv = ureg.Quantity(10, "kilovolt")
        value, unit = serialize_quantity_to_xml(qty_kv)
        assert value == 10.0
        assert unit == "kV"

        # Test millimeter
        qty_mm = ureg.Quantity(5.2, "millimeter")
        value, unit = serialize_quantity_to_xml(qty_mm)
        assert value == 5.2
        assert unit == "mm"

        # Test picoampere
        qty_pa = ureg.Quantity(100, "picoampere")
        value, unit = serialize_quantity_to_xml(qty_pa)
        assert value == 100.0
        assert unit == "pA"

    def test_serialize_units_with_symbol_variations(self):
        """Test units that may have different symbol representations."""
        # Microsecond can be µs or us depending on Pint version
        qty = ureg.Quantity(1.5, "microsecond")
        value, unit = serialize_quantity_to_xml(qty)
        assert value == 1.5
        assert unit in ["µs", "us", "μs"]

        # Degree symbol varies by platform
        qty = ureg.Quantity(45, "degree")
        value, unit = serialize_quantity_to_xml(qty)
        assert value == 45.0
        assert unit in ["°", "deg"]

        # Micrometer can vary
        qty = ureg.Quantity(100, "micrometer")
        value, unit = serialize_quantity_to_xml(qty)
        assert value == 100.0
        assert unit in ["µm", "um", "μm"]

    def test_magnitude_always_float(self):
        """Test that magnitude is always returned as float."""
        # Integer input
        qty_int = ureg.Quantity(15, "kilovolt")
        value, _ = serialize_quantity_to_xml(qty_int)
        assert isinstance(value, float)
        assert value == 15.0

        # Float input
        qty_float = ureg.Quantity(10.5, "kilovolt")
        value, _ = serialize_quantity_to_xml(qty_float)
        assert isinstance(value, float)
        assert value == 10.5


class TestGetXMLFieldName:
    """Tests for get_xml_field_name function."""

    def test_em_glossary_field_mappings(self):
        """Test EM Glossary field name to XML display name mappings."""
        # Sample of important mappings - verifies dict lookup works
        assert get_xml_field_name("acceleration_voltage") == "Voltage"
        assert get_xml_field_name("working_distance") == "Working Distance"
        assert get_xml_field_name("beam_current") == "Beam Current"
        assert get_xml_field_name("dwell_time") == "Pixel Dwell Time"

    def test_legacy_field_names_passthrough(self):
        """Test that legacy field names (with spaces) pass through unchanged."""
        assert get_xml_field_name("Voltage") == "Voltage"
        assert get_xml_field_name("Working Distance") == "Working Distance"
        assert get_xml_field_name("Data Type") == "Data Type"

    def test_unknown_field_conversion(self):
        """Test that unknown fields are converted to title case."""
        assert get_xml_field_name("some_custom_field") == "Some Custom Field"
        assert get_xml_field_name("facility_name") == "Facility Name"
        assert get_xml_field_name("scan_speed") == "Scan Speed"

    def test_mapping_dictionary_completeness(self):
        """Verify that the mapping dictionary contains expected field categories."""
        # Imaging fields
        assert "acceleration_voltage" in EM_GLOSSARY_TO_XML_DISPLAY_NAMES
        assert "magnification" in EM_GLOSSARY_TO_XML_DISPLAY_NAMES
        # Spectrum fields
        assert "acquisition_time" in EM_GLOSSARY_TO_XML_DISPLAY_NAMES
        # Diffraction fields
        assert "camera_length" in EM_GLOSSARY_TO_XML_DISPLAY_NAMES
        # Core fields
        assert "data_type" in EM_GLOSSARY_TO_XML_DISPLAY_NAMES


class TestPrepareMetadataForXML:
    """Tests for prepare_metadata_for_xml function."""

    def test_quantity_serialization_with_units(self):
        """Test Pint Quantities are split into value and unit."""
        metadata = {
            "acceleration_voltage": ureg.Quantity(10, "kilovolt"),
            "working_distance": ureg.Quantity(5.2, "millimeter"),
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        assert xml_dict["Voltage"] == 10.0
        assert xml_dict["Voltage_unit"] == "kV"
        assert xml_dict["Working Distance"] == 5.2
        assert xml_dict["Working Distance_unit"] == "mm"

    def test_mixed_types_preserved(self):
        """Test that non-Quantity values are preserved as-is."""
        metadata = {
            "acceleration_voltage": ureg.Quantity(10, "kilovolt"),
            "detector_type": "ETD",
            "magnification": 5000,
            "data_type": "SEM_Imaging",
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        assert xml_dict["Voltage"] == 10.0
        assert xml_dict["Detector"] == "ETD"
        assert xml_dict["Magnification"] == 5000
        assert xml_dict["Data Type"] == "SEM_Imaging"

    def test_filtering_internal_fields(self):
        """Test that internal fields are excluded from XML output."""
        metadata = {
            "acceleration_voltage": ureg.Quantity(10, "kilovolt"),
            "warnings": ["Operator", "Specimen"],
            "schema_version": "1.2.2",
            "extensions": {"facility": "Test Lab"},
            "beam_current": None,  # None values also filtered
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        # Should have voltage but not internal fields
        assert "Voltage" in xml_dict
        assert "warnings" not in xml_dict
        assert "schema_version" not in xml_dict
        assert "extensions" not in xml_dict
        assert "Beam Current" not in xml_dict  # None filtered

    def test_list_to_comma_separated_string(self):
        """Test that list values are converted to comma-separated strings."""
        metadata = {
            "elements": ["C", "O", "Si", "Au"],
            "tags": [],  # Empty list
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        assert xml_dict["Elements"] == "C, O, Si, Au"
        assert xml_dict["Tags"] == ""

    def test_stage_position_flattening(self):
        """Test that nested stage_position dict is flattened with proper units."""
        metadata = {
            "stage_position": {
                "x": ureg.Quantity(100, "micrometer"),
                "y": None,  # Test None handling
                "z": ureg.Quantity(5, "millimeter"),
                "tilt_alpha": ureg.Quantity(10, "degree"),
                "rotation": 45.0,  # Numeric without unit
            },
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        # Check flattened with units
        assert xml_dict["Stage X"] == 100.0
        assert xml_dict["Stage X_unit"] in ["µm", "um", "μm"]
        assert "Stage Y" not in xml_dict  # None excluded
        assert xml_dict["Stage Z"] == 5.0
        assert xml_dict["Stage Z_unit"] == "mm"
        assert xml_dict["Stage Tilt"] == 10.0
        assert xml_dict["Stage Tilt_unit"] in ["°", "deg"]
        assert xml_dict["Stage Rotation"] == 45.0
        assert "Stage Rotation_unit" not in xml_dict  # No unit for non-Quantity

    def test_spectrum_metadata_fields(self):
        """Test spectrum-specific field handling."""
        metadata = {
            "acquisition_time": ureg.Quantity(30, "second"),
            "detector_energy_resolution": ureg.Quantity(129, "electron_volt"),
            "elements": ["C", "O", "Au"],
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        assert xml_dict["Acquisition Time"] == 30.0
        assert xml_dict["Acquisition Time_unit"] == "s"
        assert xml_dict["Energy Resolution"] == 129.0
        assert xml_dict["Energy Resolution_unit"] == "eV"
        assert xml_dict["Elements"] == "C, O, Au"

    def test_custom_field_name_conversion(self):
        """Test that custom fields get title-cased names."""
        metadata = {
            "custom_field": "test value",
            "another_custom_field": 42,
        }
        xml_dict = prepare_metadata_for_xml(metadata)

        assert xml_dict["Custom Field"] == "test value"
        assert xml_dict["Another Custom Field"] == 42

    def test_empty_metadata_dict(self):
        """Test with empty metadata returns empty dict."""
        assert prepare_metadata_for_xml({}) == {}


class TestGetQUDTURI:
    """Tests for get_qudt_uri function."""

    def test_valid_unit_returns_qudt_uri(self):
        """Test that valid units return QUDT URIs."""
        # Test a few representative units
        uri_kv = get_qudt_uri("acceleration_voltage", "kV")
        assert uri_kv is not None
        assert "qudt.org" in uri_kv
        assert "KiloV" in uri_kv

        uri_mm = get_qudt_uri("working_distance", "mm")
        assert uri_mm is not None
        assert "MilliM" in uri_mm

    def test_invalid_unit_returns_none(self):
        """Test that invalid/unknown units return None."""
        assert get_qudt_uri("custom_field", "invalid_unit") is None
        assert get_qudt_uri("custom_field", "") is None


class TestGetEMGID:
    """Tests for get_emg_id function."""

    def test_known_fields_return_emg_ids(self):
        """Test that known EM Glossary fields return their IDs."""
        # Test a few key fields
        assert get_emg_id("acceleration_voltage") == "EMG_00000004"
        assert get_emg_id("working_distance") == "EMG_00000050"
        assert get_emg_id("beam_current") == "EMG_00000006"
        assert get_emg_id("camera_length") == "EMG_00000008"
        assert get_emg_id("dwell_time") == "EMG_00000015"

    def test_unknown_fields_return_none(self):
        """Test that unknown/custom fields return None."""
        assert get_emg_id("some_custom_field") is None
        assert get_emg_id("Voltage") is None  # Legacy name not in mapping
