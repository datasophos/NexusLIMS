# pylint: disable=C0116

"""Tests for nexusLIMS.extractors.schemas - Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from nexusLIMS.extractors.schemas import (
    NexusMetadata,
    SEMImageMetadata,
    TEMImageMetadata,
)


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

    def test_valid_with_extra_fields(self):
        """Test validation allows additional instrument-specific fields."""
        nx_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Voltage": "200 kV",  # Extra field
            "Magnification": "50000x",  # Extra field
            "Stage Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},  # Extra nested
        }
        validated = NexusMetadata.model_validate(nx_meta)
        # Extra fields should be preserved
        assert validated.model_extra["Voltage"] == "200 kV"
        assert validated.model_extra["Magnification"] == "50000x"
        assert validated.model_extra["Stage Position"]["X"] == 0.0

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
        assert "timezone information" in str(exc_info.value)

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
        assert "timezone information" in str(exc_info.value)

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
            "Voltage": "200 kV",
            "Magnification": "50000x",
            "Illumination Mode": "STEM",
            "Acquisition Device": "BF-Detector",
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.data_type == "STEM_Imaging"
        assert validated.dataset_type == "Image"
        assert validated.model_extra["Voltage"] == "200 kV"

    def test_realistic_eds_spectrum_metadata(self):
        """Test realistic EDS spectrum metadata example."""
        nx_meta = {
            "Creation Time": "2024-01-15T14:23:45Z",
            "Data Type": "TEM_EDS",
            "DatasetType": "Spectrum",
            "Data Dimensions": "(4096,)",
            "Instrument ID": "FEI-Titan-TEM-635816",
            "warnings": [["Low counts", "Acquisition time may be too short"]],
            "EDS": {"Live Time": 120.5, "Dead Time": 12.3},
        }
        validated = NexusMetadata.model_validate(nx_meta)
        assert validated.dataset_type == "Spectrum"
        assert len(validated.warnings) == 1
        assert validated.model_extra["EDS"]["Live Time"] == 120.5

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


class TestTEMImageMetadata:
    """Test the TEMImageMetadata schema."""

    def test_tem_metadata_inherits_base_validation(self):
        """Test that TEM schema inherits base NexusMetadata validation."""
        tem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "TEM_Imaging",
            "DatasetType": "Image",
        }
        validated = TEMImageMetadata.model_validate(tem_meta)
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"
        assert validated.data_type == "TEM_Imaging"
        assert validated.dataset_type == "Image"

    def test_tem_metadata_with_optional_fields(self):
        """Test TEM metadata with TEM-specific fields."""
        tem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "TEM_Imaging",
            "DatasetType": "Image",
            "Voltage": "200 kV",
            "Magnification": "50000x",
            "Illumination Mode": "TEM",
            "Acquisition Device": "BM-UltraScan",
        }
        validated = TEMImageMetadata.model_validate(tem_meta)
        # TEM-specific fields are stored as actual model fields
        assert validated.voltage == "200 kV"
        assert validated.magnification == "50000x"
        assert validated.illumination_mode == "TEM"
        assert validated.acquisition_device == "BM-UltraScan"

    def test_stem_metadata(self):
        """Test STEM imaging metadata."""
        stem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "STEM_Imaging",
            "DatasetType": "Image",
            "Voltage": "200 kV",
            "Magnification": 225000,  # Numeric magnification
            "Illumination Mode": "STEM",
            "Acquisition Device": "HAADF",
        }
        validated = TEMImageMetadata.model_validate(stem_meta)
        assert validated.magnification == 225000

    def test_diffraction_metadata(self):
        """Test diffraction pattern metadata."""
        diff_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "TEM_Diffraction",
            "DatasetType": "Diffraction",
            "Voltage": "200 kV",
            "Camera Length": "200 mm",
            "Illumination Mode": "Diffraction",
        }
        validated = TEMImageMetadata.model_validate(diff_meta)
        assert validated.camera_length == "200 mm"

    def test_tem_metadata_allows_extra_fields(self):
        """Test that TEM schema allows additional instrument-specific fields."""
        tem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "TEM_Imaging",
            "DatasetType": "Image",
            "C2 Lens (%)": 22.133,  # Extra field
            "Spot Size": 5,  # Extra field
            "Objective Aperture": "70 µm",  # Extra field
        }
        validated = TEMImageMetadata.model_validate(tem_meta)
        assert validated.model_extra["C2 Lens (%)"] == 22.133
        assert validated.model_extra["Spot Size"] == 5


class TestSEMImageMetadata:
    """Test the SEMImageMetadata schema."""

    def test_sem_metadata_inherits_base_validation(self):
        """Test that SEM schema inherits base NexusMetadata validation."""
        sem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
        }
        validated = SEMImageMetadata.model_validate(sem_meta)
        assert validated.creation_time == "2024-01-15T10:30:00-05:00"
        assert validated.data_type == "SEM_Imaging"
        assert validated.dataset_type == "Image"

    def test_sem_metadata_with_optional_fields(self):
        """Test SEM metadata with SEM-specific fields."""
        sem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "Voltage": "10 kV",
            "Magnification": "5000x",
            "Working Distance": "10 mm",
            "Beam Current": "100 pA",
            "Detector": "ETD",
        }
        validated = SEMImageMetadata.model_validate(sem_meta)
        # SEM-specific fields are stored as actual model fields
        assert validated.voltage == "10 kV"
        assert validated.magnification == "5000x"
        assert validated.working_distance == "10 mm"
        assert validated.beam_current == "100 pA"
        assert validated.detector == "ETD"

    def test_him_metadata(self):
        """Test Helium Ion Microscope metadata."""
        him_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "HIM_Imaging",
            "DatasetType": "Image",
            "Voltage": "30 kV",
            "Magnification": 100000,  # Numeric
            "Working Distance": 8.5,  # Numeric (mm)
            "Detector": "ETD",
            "Dwell Time": "1 us",
        }
        validated = SEMImageMetadata.model_validate(him_meta)
        assert validated.magnification == 100000
        assert validated.working_distance == 8.5

    def test_sem_metadata_with_scan_params(self):
        """Test SEM metadata with scan parameters."""
        sem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "Voltage": "5 kV",
            "Dwell Time": 1e-6,  # Numeric in seconds
            "Scan Rotation": "45.0",
        }
        validated = SEMImageMetadata.model_validate(sem_meta)
        assert validated.dwell_time == 1e-6
        assert validated.scan_rotation == "45.0"

    def test_sem_metadata_allows_extra_fields(self):
        """Test that SEM schema allows additional instrument-specific fields."""
        sem_meta = {
            "Creation Time": "2024-01-15T10:30:00-05:00",
            "Data Type": "SEM_Imaging",
            "DatasetType": "Image",
            "Chamber Pressure": "0.5 Torr",  # Extra field
            "Gas": "Water vapor",  # Extra field
            "Spot Size": "3.5",  # Extra field
        }
        validated = SEMImageMetadata.model_validate(sem_meta)
        assert validated.model_extra["Chamber Pressure"] == "0.5 Torr"
        assert validated.model_extra["Gas"] == "Water vapor"
