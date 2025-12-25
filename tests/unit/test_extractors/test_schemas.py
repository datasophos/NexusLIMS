# pylint: disable=C0116

"""Tests for nexusLIMS.schemas.metadata - Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from nexusLIMS.schemas.metadata import ImageMetadata, NexusMetadata


class TestNexusMetadataValidation:
    """Test the NexusMetadata Pydantic model validation."""

    def test_valid_minimal_metadata(self):
        """Test validation passes with minimal required fields."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"
        assert validated.data_type == "STEM_Imaging"
        assert validated.dataset_type == "Image"

    def test_valid_complete_metadata(self):
        """Test validation passes with all common fields."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Data Dimensions": "(1024, 1024)",
            "Instrument ID": "FEI-Titan-TEM-635816",
            "warnings": [],
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.data_dimensions == "(1024, 1024)"
        assert validated.instrument_id == "FEI-Titan-TEM-635816"
        assert validated.warnings == []

    def test_valid_with_extensions(self):
        """Test validation allows additional fields via extensions."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "extensions": {
                "voltage": "200 kV",
                "magnification": "50000x",
                "stage_position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            },
        }
        validated = NexusMetadata.model_validate(nx_meta)
        # Extensions should be preserved
        assert validated.extensions["voltage"] == "200 kV"
        assert validated.extensions["magnification"] == "50000x"
        assert validated.extensions["stage_position"]["X"] == 0.0

    def test_missing_creation_time(self):
        """Test validation fails when Creation Time is missing."""
        nx_meta = {
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "Creation Time" in str(exc_info.value)

    def test_missing_data_type(self):
        """Test validation fails when Data Type is missing."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "Data Type" in str(exc_info.value)

    def test_missing_dataset_type(self):
        """Test validation fails when DatasetType is missing."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "DatasetType" in str(exc_info.value)

    def test_invalid_timestamp_format(self):
        """Test validation fails with invalid ISO-8601 timestamp."""
        nx_meta = {
            "Creation Time": "2024-01-15 10:30:00",  # Missing timezone
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        # In Python 3.11+, this parses but fails timezone check
        assert "timezone" in str(exc_info.value)

    def test_invalid_timestamp_not_a_date(self):
        """Test validation fails when timestamp is not a valid date."""
        nx_meta = {
            "Creation Time": "not-a-timestamp",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "Invalid ISO-8601 timestamp" in str(exc_info.value)

    def test_missing_timezone(self):
        """Test validation fails when timestamp lacks timezone info."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00",  # No timezone
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "timezone" in str(exc_info.value)

    def test_valid_utc_z_notation(self):
        """Test validation accepts UTC 'Z' notation."""
        nx_meta = {
            "Creation Time": "2024-01-15T15:30:00Z",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.creation_time == "2024-01-15T15:30:00Z"

    def test_valid_positive_timezone_offset(self):
        """Test validation accepts positive timezone offset."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00+08:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.creation_time == "2024-01-15T10:30:00+08:00"

    def test_valid_negative_timezone_offset(self):
        """Test validation accepts negative timezone offset."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"

    def test_invalid_dataset_type(self):
        """Test validation fails with invalid DatasetType value."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "InvalidType",  # Not in allowed values
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "DatasetType" in str(exc_info.value)

    @pytest.mark.parametrize(
        "dataset_type",
        ["Image", "Spectrum", "SpectrumImage", "Diffraction", "Misc", "Unknown"],
    )
    def test_valid_dataset_types(self, dataset_type):
        """Test all allowed DatasetType values are accepted."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": dataset_type,
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.dataset_type == dataset_type

    def test_empty_data_type(self):
        """Test validation fails when Data Type is empty string."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "",  # Empty
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "Data Type cannot be empty" in str(exc_info.value)

    def test_whitespace_only_data_type(self):
        """Test validation fails when Data Type contains only whitespace."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "   ",  # Whitespace only
            "DatasetType": "Image",
        }
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata.model_validate(nx_meta)
        assert "Data Type cannot be empty" in str(exc_info.value)

    def test_warnings_as_list_of_strings(self):
        """Test warnings field accepts list of strings."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "warnings": ["Missing calibration", "Low contrast"],
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.warnings == ["Missing calibration", "Low contrast"]

    def test_warnings_as_list_of_lists(self):
        """Test warnings field accepts list of lists (message + context)."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "warnings": [
                ["Uncalibrated data", "No pixel size found"],
                ["Missing metadata", "Operator field empty"],
            ],
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert len(validated.warnings) == 2
        assert validated.warnings[0] == ["Uncalibrated data", "No pixel size found"]

    def test_warnings_mixed_format(self):
        """Test warnings field accepts mixed string/list format."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "warnings": [
                "Simple warning",
                ["Detailed warning", "Extra context"],
            ],
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert len(validated.warnings) == 2
        assert validated.warnings[0] == "Simple warning"
        assert validated.warnings[1] == ["Detailed warning", "Extra context"]

    def test_none_instrument_id(self):
        """Test Instrument ID can be None."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Instrument ID": None,
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.instrument_id is None

    def test_none_data_dimensions(self):
        """Test Data Dimensions can be None."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Data Dimensions": None,
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.data_dimensions is None

    def test_access_via_python_names(self):
        """Test fields can be accessed using Python-style attribute names."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        # Both styles should work
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"
        assert validated.data_type == "STEM_Imaging"
        assert validated.dataset_type == "Image"

    def test_populate_by_name_allows_both_styles(self):
        """Test schema accepts both 'Creation Time' and 'creation_time' keys."""
        # Using original keys
        nx_meta1 = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
        }
        validated1 = NexusMetadata.model_validate(nx_meta1)

        # Using Python-style keys
        nx_meta2 = {
            "creation_time": "2024-01-15T10:30:00-05:00",
            "data_type": "STEM_Imaging",
            "dataset_type": "Image",
        }
        validated2 = NexusMetadata.model_validate(nx_meta2)

        # Both should produce same result
        assert validated1.creation_time == validated2.creation_time
        assert validated1.data_type == validated2.data_type
        assert validated1.dataset_type == validated2.dataset_type

    def test_realistic_stem_metadata(self):
        """Test realistic STEM metadata example."""
        nx_meta = {
            "Creation Time": "2024-01-15T14:23:45-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Data Dimensions": "(2048, 2048)",
            "Instrument ID": "FEI-Titan-STEM-643481",
            "warnings": [],
            "extensions": {
                "voltage": "200 kV",
                "magnification": "50000x",
                "illumination_mode": "STEM",
                "acquisition_device": "BF-Detector",
            },
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.data_type == "STEM_Imaging"
        assert validated.dataset_type == "Image"
        assert validated.extensions["voltage"] == "200 kV"

    def test_realistic_eds_spectrum_metadata(self):
        """Test realistic EDS spectrum metadata example."""
        nx_meta = {
            "Creation Time": "2024-01-15T14:23:45Z",
            "Data Type": "TEM_EDS",
            "DatasetType": "Spectrum",
            "Data Dimensions": "(4096,)",
            "Instrument ID": "FEI-Titan-TEM-635816",
            "warnings": [["Low counts", "Acquisition time may be too short"]],
            "extensions": {
                "eds": {"live_time": 120.5, "dead_time": 12.3},
            },
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.dataset_type == "Spectrum"
        assert len(validated.warnings) == 1
        assert validated.extensions["eds"]["live_time"] == 120.5

    def test_realistic_unknown_dataset(self):
        """Test realistic Unknown dataset type (fallback for unsupported files)."""
        nx_meta = {
            "Creation Time": "2024-01-15T14:23:45-05:00",
            "Data Type": "Unknown",
            "DatasetType": "Unknown",
            "Instrument ID": None,
            "warnings": ["Extraction failed: Unsupported file format"],
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.dataset_type == "Unknown"
        assert validated.data_type == "Unknown"
        assert len(validated.warnings) == 1


class TestImageMetadata:
    """Test the ImageMetadata schema (unified for SEM/TEM/STEM imaging)."""

    def test_image_metadata_inherits_base_validation(self):
        """Test that Image schema inherits base NexusMetadata validation."""
        img_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "TEM_Imaging",
            "DatasetType": "Image",
        }
        validated = ImageMetadata.model_validate(img_meta)
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"
        assert validated.data_type == "TEM_Imaging"
        assert validated.dataset_type == "Image"

    def test_image_metadata_with_pint_quantities(self):
        """Test Image metadata with Pint Quantity fields."""
        from nexusLIMS.schemas.units import ureg

        img_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "acceleration_voltage": ureg.Quantity(10, "kilovolt"),
            "working_distance": ureg.Quantity(10, "millimeter"),
            "beam_current": ureg.Quantity(100, "picoampere"),
            "magnification": 5000.0,
        }
        validated = ImageMetadata.model_validate(img_meta)
        assert validated.acceleration_voltage.magnitude == 10
        assert str(validated.acceleration_voltage.units) == "kilovolt"
        assert validated.magnification == 5000.0

    def test_image_metadata_with_extensions(self):
        """Test Image metadata with extensions for instrument-specific fields."""
        img_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "extensions": {
                "chamber_pressure": "0.5 Torr",
                "gas": "Water vapor",
                "spot_size": 3.5,
            },
        }
        validated = ImageMetadata.model_validate(img_meta)
        assert validated.extensions["chamber_pressure"] == "0.5 Torr"
        assert validated.extensions["gas"] == "Water vapor"
        assert validated.extensions["spot_size"] == 3.5

    def test_image_metadata_forbids_unknown_top_level_fields(self):
        """Test Image schema forbids unknown top-level fields."""
        img_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "Unknown Field": "value",  # Should be rejected
        }
        with pytest.raises(ValidationError) as exc_info:
            ImageMetadata.model_validate(img_meta)
        assert "Extra inputs are not permitted" in str(exc_info.value)
