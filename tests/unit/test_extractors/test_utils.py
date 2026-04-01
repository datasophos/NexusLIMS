"""Tests for nexusLIMS.extractors.utils utility functions."""

from nexusLIMS.extractors.utils import _set_eels_processing, add_to_extensions
from nexusLIMS.schemas.units import ureg


class TestSetEelsProcessing:
    """Tests for the _set_eels_processing utility function."""

    def test_taggroup_without_operation_key_is_skipped(self):
        """Test that TagGroups missing an Operation key are skipped gracefully.

        Some processing TagGroups (e.g. Summing) do not have an Operation key.
        The loop should continue past them without error.
        """
        pre_path = ["ImageList", "TagGroup0", "ImageTags", "EELS"]
        mdict = {
            "ImageList": {
                "TagGroup0": {
                    "ImageTags": {
                        "EELS": {
                            "Processing": {
                                "TagGroup0": {
                                    # No "Operation" key -- should be skipped
                                    "SomeOtherKey": "value",
                                },
                                "TagGroup1": {
                                    "Operation": "AlignSIByPeak",
                                    "Parameters": {},
                                },
                            }
                        }
                    }
                }
            },
            "nx_meta": {},
        }

        _set_eels_processing(mdict, pre_path)

        # Only the AlignSIByPeak step should appear; the keyless TagGroup is ignored
        assert (
            mdict["nx_meta"]["EELS"]["Processing Steps"] == "Aligned parent SI By Peak"
        )


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
