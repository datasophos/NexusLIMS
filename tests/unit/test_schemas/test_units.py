"""Tests for nexusLIMS.schemas.units module."""

import logging
from unittest.mock import patch

import pytest

from nexusLIMS.schemas.units import (
    PREFERRED_UNITS,
    _load_qudt_units,
    deserialize_quantity,
    get_qudt_uri,
    normalize_quantity,
    parse_quantity,
    quantity_to_xml_parts,
    serialize_quantity,
    ureg,
)


class TestUnitRegistry:
    """Test the Pint unit registry setup."""

    def test_ureg_exists(self):
        """Test that unit registry is created."""
        assert ureg is not None

    def test_common_units_defined(self):
        """Test that common units are accessible."""
        # Voltage/Energy
        assert ureg.kilovolt
        assert ureg.volt
        assert ureg.eV
        assert ureg.keV

        # Length
        assert ureg.millimeter
        assert ureg.micrometer
        assert ureg.nanometer

        # Current
        assert ureg.picoampere
        assert ureg.nanoampere
        assert ureg.microampere

        # Time
        assert ureg.microsecond
        assert ureg.second

        # Angle
        assert ureg.degree
        assert ureg.radian
        assert ureg.milliradian

    def test_preferred_units_mapping(self):
        """Test that PREFERRED_UNITS dict is populated."""
        assert len(PREFERRED_UNITS) > 0
        assert "acceleration_voltage" in PREFERRED_UNITS
        assert "working_distance" in PREFERRED_UNITS
        assert "beam_current" in PREFERRED_UNITS

    def test_qudt_unit_loading(self):
        """Test that QUDT units are loaded from TTL file."""
        qudt_map = _load_qudt_units()
        assert len(qudt_map) > 1000  # Should have thousands of units
        assert "kilovolt" in qudt_map
        assert qudt_map["kilovolt"] == "http://qudt.org/vocab/unit/KiloV"


class TestNormalizeQuantity:
    """Test the normalize_quantity function."""

    def test_normalize_to_preferred_unit(self):
        """Test normalizing a quantity to its preferred unit."""
        voltage = ureg.Quantity(10000, "volt")
        normalized = normalize_quantity("acceleration_voltage", voltage)
        assert normalized.magnitude == 10.0
        assert normalized.units == ureg.kilovolt

    def test_normalize_unknown_field_returns_unchanged(self):
        """Test that unknown fields pass through unchanged."""
        qty = ureg.Quantity(5.0, "furlong")
        result = normalize_quantity("unknown_field", qty)
        assert result == qty

    def test_normalize_non_quantity_returns_unchanged(self):
        """Test that non-Quantity values pass through."""
        assert normalize_quantity("field", "string") == "string"
        assert normalize_quantity("field", 42) == 42
        assert normalize_quantity("field", None) is None


class TestParseQuantity:
    """Test the parse_quantity function."""

    def test_parse_string_quantity(self):
        """Test parsing a string like '10 kV'."""
        qty = parse_quantity("acceleration_voltage", "10 kV")

        assert isinstance(qty, ureg.Quantity)
        assert qty.magnitude == 10.0
        assert qty.units == ureg.kilovolt

    def test_parse_string_with_normalization(self):
        """Test parsing string and normalizing to preferred unit."""
        qty = parse_quantity("beam_current", "0.1 nA")

        assert qty.magnitude == pytest.approx(100.0)
        assert qty.units == ureg.picoampere

    def test_parse_existing_quantity(self):
        """Test parsing an existing Quantity normalizes it."""
        original = ureg.Quantity(10000, "volt")
        qty = parse_quantity("acceleration_voltage", original)

        assert qty.magnitude == 10.0
        assert qty.units == ureg.kilovolt

    def test_parse_numeric_assumes_preferred_unit(self):
        """Test that numeric values are assumed to be in preferred units."""
        qty = parse_quantity("acceleration_voltage", 15.0)

        assert isinstance(qty, ureg.Quantity)
        assert qty.magnitude == 15.0
        assert qty.units == ureg.kilovolt

    def test_parse_numeric_without_preferred_unit(self):
        """Test numeric value for field without preferred unit."""
        result = parse_quantity("unknown_field", 42.0)

        # Should return as-is since no preferred unit defined
        assert result == 42.0

    def test_parse_none_returns_none(self):
        """Test that None passes through."""
        assert parse_quantity("field", None) is None

    def test_parse_unparseable_string_returns_original(self):
        """Test that unparseable strings return as-is."""
        result = parse_quantity("field", "not a quantity")

        assert result == "not a quantity"


class TestQuantityToXmlParts:
    """Test the quantity_to_xml_parts function."""

    def test_quantity_to_xml_parts(self):
        """Test converting a Quantity to XML parts."""
        qty = ureg.Quantity(10.0, "kilovolt")
        name, value, unit = quantity_to_xml_parts("acceleration_voltage", qty)

        assert name == "Voltage"  # Display name from EM Glossary
        assert float(value) == pytest.approx(10.0)
        assert unit == "kV"

    def test_xml_parts_working_distance(self):
        """Test XML parts for working distance."""
        qty = ureg.Quantity(5.2, "millimeter")
        name, value, unit = quantity_to_xml_parts("working_distance", qty)

        assert name == "Working Distance"
        assert value == "5.2"
        assert unit == "mm"

    def test_xml_parts_dimensionless(self):
        """Test XML parts for dimensionless quantity."""
        qty = ureg.Quantity(5000, "dimensionless")
        name, value, unit = quantity_to_xml_parts("magnification", qty)

        assert name == "Magnification"
        assert value == "5000"
        assert unit is None  # No unit for dimensionless

    def test_xml_parts_scientific_notation_small(self):
        """Test that very small numbers use scientific notation."""
        qty = ureg.Quantity(1e-6, "ampere")
        _, value, unit = quantity_to_xml_parts("beam_current", qty)

        assert "e" in value  # Scientific notation
        assert unit == "A"

    def test_xml_parts_scientific_notation_large(self):
        """Test that very large numbers use scientific notation."""
        qty = ureg.Quantity(1e7, "volt")
        _, value, _ = quantity_to_xml_parts("acceleration_voltage", qty)

        assert "e" in value  # Scientific notation

    def test_xml_parts_non_quantity(self):
        """Test XML parts for non-Quantity value."""
        name, value, unit = quantity_to_xml_parts("operator", "John Doe")

        assert name == "Operator"
        assert value == "John Doe"
        assert unit is None


class TestGetQudtUri:
    """Test the get_qudt_uri function."""

    def test_get_qudt_uri_success(self):
        """Test getting QUDT URI for a valid unit."""
        qty = ureg.Quantity(10, "kilovolt")
        uri = get_qudt_uri(qty)
        assert uri == "http://qudt.org/vocab/unit/KiloV"

    def test_get_qudt_uri_non_quantity(self):
        """Test that non-Quantity returns None."""
        assert get_qudt_uri("not a quantity") is None

    def test_get_qudt_uri_unknown_unit(self):
        """Test getting URI for unit not in QUDT."""
        ureg.define("florp = 42 * meter")
        qty = ureg.Quantity(5, "florp")
        assert get_qudt_uri(qty) is None


class TestSerializeDeserialize:
    """Test serialization and deserialization functions."""

    def test_serialize_quantity(self):
        """Test serializing a Quantity to dict."""
        qty = ureg.Quantity(10.0, "kilovolt")
        serialized = serialize_quantity(qty)

        assert serialized == {"value": 10.0, "units": "kilovolt"}

    def test_serialize_non_quantity(self):
        """Test serializing a non-Quantity value."""
        serialized = serialize_quantity("some string")

        assert serialized == {"value": "some string"}

    def test_deserialize_quantity(self):
        """Test deserializing a dict to Quantity."""
        data = {"value": 10.0, "units": "kilovolt"}
        qty = deserialize_quantity(data)

        assert isinstance(qty, ureg.Quantity)
        assert qty.magnitude == 10.0
        assert qty.units == ureg.kilovolt

    def test_deserialize_non_quantity(self):
        """Test deserializing a non-Quantity dict."""
        data = {"value": "some string"}
        result = deserialize_quantity(data)

        assert result == "some string"

    def test_round_trip_serialization(self):
        """Test that serialize/deserialize round-trips correctly."""
        original = ureg.Quantity(5.2, "millimeter")
        serialized = serialize_quantity(original)
        deserialized = deserialize_quantity(serialized)

        assert deserialized.magnitude == original.magnitude
        assert deserialized.units == original.units


class TestLoadQudtUnitsErrorHandling:
    """Test error handling in _load_qudt_units function."""

    def test_qudt_file_not_found_returns_empty_dict(self, caplog):
        """Test that missing QUDT file returns empty dict and logs warning."""
        # Clear the cache to force re-loading
        _load_qudt_units.cache_clear()

        with patch("nexusLIMS.schemas.units.QUDT_UNIT_TTL_PATH") as mock_path:
            # Mock the path to not exist
            mock_path.exists.return_value = False

            with caplog.at_level(logging.WARNING):
                result = _load_qudt_units()

            # Should return empty dict
            assert result == {}
            # Should log warning about missing file
            assert any(
                "not found" in record.message.lower() for record in caplog.records
            )

    def test_qudt_parse_exception_returns_empty_dict(self, caplog, tmp_path):
        """Test that parsing exception returns empty dict and logs error."""
        # Clear the cache to force re-loading
        _load_qudt_units.cache_clear()

        # Create a temporary invalid TTL file
        invalid_ttl_file = tmp_path / "invalid.ttl"
        invalid_ttl_file.write_text("not valid ttl syntax }{]")

        with patch("nexusLIMS.schemas.units.QUDT_UNIT_TTL_PATH", invalid_ttl_file):
            with caplog.at_level(logging.ERROR):
                result = _load_qudt_units()

            # Should return empty dict
            assert result == {}
            # Should log error about parsing failure
            assert any(
                "failed to parse" in record.message.lower() for record in caplog.records
            )


class TestNormalizeQuantityErrorHandling:
    """Test error handling in normalize_quantity function."""

    def test_unit_conversion_exception_returns_original(self, caplog):
        """Test unit conversion exception logs warning and returns original quantity."""
        # Create a quantity with an incompatible unit for conversion
        # We'll mock the to() method to raise an exception
        qty = ureg.Quantity(10, "volt")

        with patch.object(qty, "to", side_effect=Exception("Incompatible units")):
            with caplog.at_level(logging.WARNING):
                result = normalize_quantity("acceleration_voltage", qty)

            # Should return the original quantity
            assert result == qty
            # Should log warning about conversion error
            assert any(
                "could not convert" in record.message.lower()
                for record in caplog.records
            )


class TestParseQuantityEdgeCases:
    """Test edge cases and unknown types in parse_quantity function."""

    def test_parse_unknown_type_returns_as_is(self):
        """Test that unknown types are returned as-is."""
        # Test with various non-standard types
        test_obj = object()
        result = parse_quantity("field", test_obj)
        assert result is test_obj

        # Test with list
        test_list = [1, 2, 3]
        result = parse_quantity("field", test_list)
        assert result is test_list

        # Test with dict
        test_dict = {"key": "value"}
        result = parse_quantity("field", test_dict)
        assert result is test_dict

    def test_parse_bool_returns_as_is(self):
        """Test that boolean values are returned as-is."""
        assert parse_quantity("field", value=True) is True
        assert parse_quantity("field", value=False) is False

    def test_parse_complex_number_returns_as_is(self):
        """Test that complex numbers are returned as-is."""
        test_complex = 1 + 2j
        result = parse_quantity("field", test_complex)
        assert result == test_complex
