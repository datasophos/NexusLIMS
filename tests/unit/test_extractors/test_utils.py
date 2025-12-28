"""Tests for nexusLIMS.extractors.utils utility functions."""

from nexusLIMS.extractors.utils import add_to_extensions
from nexusLIMS.schemas.units import ureg


class TestAddToExtensions:
    """Tests for the add_to_extensions utility function."""

    def test_creates_extensions_dict_and_adds_field(self):
        """Test adding fields creates extensions dict if needed."""
        nx_meta = {"DatasetType": "Image"}
        add_to_extensions(nx_meta, "spot_size", 3.5)
        add_to_extensions(nx_meta, "contrast", 50.0)

        assert nx_meta["extensions"] == {"spot_size": 3.5, "contrast": 50.0}

    def test_preserves_existing_extensions(self):
        """Test adding to existing extensions preserves other fields."""
        nx_meta = {"extensions": {"existing": "value"}}
        add_to_extensions(nx_meta, "new_field", 123)

        assert nx_meta["extensions"]["existing"] == "value"
        assert nx_meta["extensions"]["new_field"] == 123

    def test_handles_various_types(self):
        """Test handles scalars, dicts, and Pint Quantities."""
        nx_meta = {}
        add_to_extensions(nx_meta, "scalar", 3.5)
        add_to_extensions(nx_meta, "quantity", ureg.Quantity(79.8, "pascal"))
        add_to_extensions(nx_meta, "dict", {"key": "value"})

        assert nx_meta["extensions"]["scalar"] == 3.5
        assert nx_meta["extensions"]["quantity"] == ureg.Quantity(79.8, "pascal")
        assert nx_meta["extensions"]["dict"] == {"key": "value"}
