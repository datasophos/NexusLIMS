"""Tests for nexusLIMS.schemas.pint_types module."""

import pytest
from pydantic import BaseModel, ValidationError

from nexusLIMS.schemas.pint_types import PintQuantity
from nexusLIMS.schemas.units import ureg


class SampleModel(BaseModel):
    """Sample model for PintQuantity validation."""

    voltage: PintQuantity
    current: PintQuantity | None = None


class TestPintQuantityValidation:
    """Test PintQuantity field validation."""

    def test_validate_quantity_object(self):
        """Test validating a Pint Quantity object."""
        qty = ureg.Quantity(10, "kilovolt")
        model = SampleModel(voltage=qty)

        assert model.voltage == qty
        assert model.voltage.magnitude == 10
        assert model.voltage.units == ureg.kilovolt

    def test_validate_string_quantity(self):
        """Test validating a string like '10 kV'."""
        model = SampleModel(voltage="10 kV")

        assert isinstance(model.voltage, ureg.Quantity)
        assert model.voltage.magnitude == 10
        assert model.voltage.units == ureg.kilovolt

    def test_validate_numeric_dimensionless(self):
        """Test validating a numeric value (dimensionless)."""
        model = SampleModel(voltage=15.0)

        assert isinstance(model.voltage, ureg.Quantity)
        assert model.voltage.magnitude == 15.0

    def test_validate_dict_with_units(self):
        """Test validating a dict with 'value' and 'units' keys."""
        model = SampleModel(voltage={"value": 20.0, "units": "kilovolt"})

        assert isinstance(model.voltage, ureg.Quantity)
        assert model.voltage.magnitude == 20.0
        assert model.voltage.units == ureg.kilovolt

    def test_validate_none_optional_field(self):
        """Test that None is accepted for optional fields."""
        model = SampleModel(voltage="10 kV", current=None)

        assert model.voltage.magnitude == 10
        assert model.current is None

    def test_invalid_string_raises_error(self):
        """Test that unparseable string raises ValidationError."""
        with pytest.raises(ValidationError, match="Could not parse"):
            SampleModel(voltage="invalid quantity")

    def test_invalid_type_raises_error(self):
        """Test that invalid types raise ValidationError."""
        with pytest.raises(ValidationError, match="Cannot convert"):
            SampleModel(voltage=["not", "a", "quantity"])


class TestPintQuantitySerialization:
    """Test PintQuantity JSON serialization."""

    def test_serialize_to_json(self):
        """Test serializing Quantity to JSON."""
        model = SampleModel(voltage=ureg.Quantity(10, "kilovolt"))
        json_data = model.model_dump(mode="json")

        assert json_data["voltage"] == {"value": 10.0, "units": "kilovolt"}
        assert json_data["current"] is None

    def test_serialize_with_optional_field(self):
        """Test serializing with optional field populated."""
        model = SampleModel(
            voltage=ureg.Quantity(10, "kV"), current=ureg.Quantity(100, "pA")
        )
        json_data = model.model_dump(mode="json")

        assert json_data["voltage"] == {"value": 10.0, "units": "kilovolt"}
        assert json_data["current"] == {"value": 100.0, "units": "picoampere"}

    def test_deserialize_from_json(self):
        """Test deserializing from JSON dict."""
        json_data = {
            "voltage": {"value": 15.0, "units": "kilovolt"},
            "current": {"value": 50.0, "units": "picoampere"},
        }
        model = SampleModel.model_validate(json_data)

        assert model.voltage.magnitude == 15.0
        assert model.voltage.units == ureg.kilovolt
        assert model.current.magnitude == 50.0
        assert model.current.units == ureg.picoampere

    def test_round_trip_serialization(self):
        """Test that serialize/deserialize round-trips correctly."""
        original = SampleModel(
            voltage=ureg.Quantity(10, "kV"), current=ureg.Quantity(100, "pA")
        )

        # Serialize
        json_data = original.model_dump(mode="json")

        # Deserialize
        restored = SampleModel.model_validate(json_data)

        assert restored.voltage.magnitude == original.voltage.magnitude
        assert restored.voltage.units == original.voltage.units
        assert restored.current.magnitude == original.current.magnitude
        assert restored.current.units == original.current.units


class TestPintQuantityJSONSchema:
    """Test JSON schema generation."""

    def test_json_schema_generation(self):
        """Test that JSON schema is generated correctly."""
        schema = SampleModel.model_json_schema()

        # Check that voltage field has oneOf schema
        assert "voltage" in schema["properties"]
        voltage_schema = schema["properties"]["voltage"]

        # Should have oneOf with multiple options
        assert "oneOf" in voltage_schema
        one_of_options = voltage_schema["oneOf"]

        # Should include object, string, number, null options
        types = [opt.get("type") for opt in one_of_options]
        assert "object" in types
        assert "string" in types
        assert "number" in types
        assert "null" in types

        # Object option should have value and units properties
        object_option = next(
            opt for opt in one_of_options if opt.get("type") == "object"
        )
        assert "properties" in object_option
        assert "value" in object_option["properties"]
        assert "units" in object_option["properties"]


class TestPintQuantityValidationExceptions:
    """Test exception handling in validate_quantity function."""

    def test_validate_none_passes_through(self):
        """Test that None is passed through without modification."""
        model = SampleModel(voltage="10 kV", current=None)
        assert model.current is None

    def test_dict_deserialization_valid(self):
        """Test that dict deserialization works with valid data."""
        model = SampleModel(voltage={"value": 10.0, "units": "kilovolt"})
        assert isinstance(model.voltage, ureg.Quantity)
        assert model.voltage.magnitude == 10.0
        assert model.voltage.units == ureg.kilovolt

    def test_dict_deserialization_invalid_units(self):
        """Test dict deserialization with invalid unit string."""
        with pytest.raises(ValidationError, match="Could not deserialize quantity"):
            SampleModel(voltage={"value": 10.0, "units": "not_a_real_unit_xyz"})


class TestPintQuantitySerializationExceptions:
    """Test exception handling in serialize_quantity_json function."""

    def test_serialize_none_returns_none(self):
        """Test that None is returned when serializing None."""
        model = SampleModel(voltage="10 kV", current=None)
        json_data = model.model_dump(mode="json")
        assert json_data["current"] is None


class TestPintQuantityEdgeCases:
    """Test edge cases and special scenarios."""

    def test_different_unit_systems(self):
        """Test quantities with different unit systems."""
        model = SampleModel(voltage="10000 V")
        assert model.voltage.magnitude == 10000
        assert model.voltage.units == ureg.volt
