"""
Comprehensive unit tests for nexusLIMS schema metadata models.

Tests cover:
- Required field validation
- Optional field handling
- Pint Quantity integration
- StagePosition model
- Extensions section
- Type-specific schemas (Image, Spectrum, SpectrumImage, Diffraction)
- Error handling and edge cases
"""

import pytest
from pydantic import ValidationError

from nexusLIMS.schemas.metadata import (
    DiffractionMetadata,
    ImageMetadata,
    NexusMetadata,
    SpectrumImageMetadata,
    SpectrumMetadata,
    StagePosition,
)
from nexusLIMS.schemas.units import ureg


class TestStagePosition:
    """Tests for StagePosition model."""

    def test_stage_position_all_fields(self):
        """Test StagePosition with all fields populated."""
        pos = StagePosition(
            x=ureg.Quantity(100, "um"),
            y=ureg.Quantity(200, "um"),
            z=ureg.Quantity(5, "mm"),
            rotation=ureg.Quantity(45, "degree"),
            tilt_alpha=ureg.Quantity(15, "degree"),
            tilt_beta=ureg.Quantity(20, "degree"),
        )
        assert pos.x.magnitude == 100
        assert pos.y.magnitude == 200
        assert pos.z.magnitude == 5
        assert pos.rotation.magnitude == 45
        assert pos.tilt_alpha.magnitude == 15
        assert pos.tilt_beta.magnitude == 20

    def test_stage_position_minimal(self):
        """Test StagePosition with only required fields (none)."""
        pos = StagePosition()
        assert pos.x is None
        assert pos.y is None
        assert pos.z is None

    def test_stage_position_with_string_quantities(self):
        """Test StagePosition accepts string quantity input."""
        pos = StagePosition(x="100 um", z="5 mm")
        assert pos.x.magnitude == 100
        assert pos.z.magnitude == 5

    def test_stage_position_allows_extra_fields(self):
        """Test StagePosition allows extra vendor-specific coordinates."""
        pos = StagePosition(
            x=ureg.Quantity(100, "um"),
            custom_coord=ureg.Quantity(42, "mm"),  # type: ignore
        )
        assert pos.x.magnitude == 100
        assert hasattr(pos, "custom_coord")


class TestNexusMetadataBase:
    """Tests for NexusMetadata base schema."""

    def test_required_fields(self):
        """Test that all required fields are necessary."""
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata()

        errors = exc_info.value.errors()
        required_fields = {e["loc"][0] for e in errors}
        # Schema uses aliases (Creation Time, Data Type, DatasetType)
        assert "Creation Time" in required_fields or "creation_time" in required_fields
        assert "Data Type" in required_fields or "data_type" in required_fields
        assert "DatasetType" in required_fields or "dataset_type" in required_fields

    def test_valid_metadata_minimal(self):
        """Test valid metadata with only required fields."""
        meta = NexusMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TestData",
            dataset_type="Misc",
        )
        assert meta.creation_time == "2024-01-15T10:30:00Z"
        assert meta.data_type == "TestData"
        assert meta.dataset_type == "Misc"
        assert meta.extensions == {}
        assert meta.warnings == []

    def test_invalid_creation_time_no_timezone(self):
        """Test that creation_time without timezone is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata(
                creation_time="2024-01-15T10:30:00",  # No timezone
                data_type="TestData",
                dataset_type="Misc",
            )

        errors = exc_info.value.errors()
        assert any("Timestamp must include timezone" in str(e) for e in errors)

    def test_invalid_creation_time_format(self):
        """Test that invalid ISO format is rejected."""
        with pytest.raises(ValidationError):
            NexusMetadata(
                creation_time="15-01-2024 10:30:00",  # Wrong format
                data_type="TestData",
                dataset_type="Misc",
            )

    def test_empty_data_type_rejected(self):
        """Test that empty data_type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata(
                creation_time="2024-01-15T10:30:00Z",
                data_type="",  # Empty
                dataset_type="Misc",
            )

        errors = exc_info.value.errors()
        assert any("cannot be empty" in str(e).lower() for e in errors)

    def test_whitespace_only_data_type_rejected(self):
        """Test that whitespace-only data_type is rejected."""
        with pytest.raises(ValidationError):
            NexusMetadata(
                creation_time="2024-01-15T10:30:00Z",
                data_type="   ",  # Whitespace only
                dataset_type="Misc",
            )

    def test_valid_dataset_types(self):
        """Test all valid dataset_type values."""
        valid_types = [
            "Image",
            "Spectrum",
            "SpectrumImage",
            "Diffraction",
            "Misc",
            "Unknown",
        ]

        for dtype in valid_types:
            meta = NexusMetadata(
                creation_time="2024-01-15T10:30:00Z",
                data_type="Test",
                dataset_type=dtype,  # type: ignore
            )
            assert meta.dataset_type == dtype

    def test_invalid_dataset_type(self):
        """Test that invalid dataset_type is rejected."""
        with pytest.raises(ValidationError):
            NexusMetadata(
                creation_time="2024-01-15T10:30:00Z",
                data_type="Test",
                dataset_type="InvalidType",  # type: ignore
            )

    def test_optional_fields(self):
        """Test optional fields with various values."""
        meta = NexusMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TestData",
            dataset_type="Misc",
            data_dimensions="(1024, 1024)",
            instrument_id="TEST-INSTR-001",
            warnings=["field1", ["field2", "field3"]],
        )

        assert meta.data_dimensions == "(1024, 1024)"
        assert meta.instrument_id == "TEST-INSTR-001"
        assert len(meta.warnings) == 2

    def test_extensions_section(self):
        """Test extensions section for flexible metadata."""
        meta = NexusMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TestData",
            dataset_type="Misc",
            extensions={
                "facility": "Nexus Center",
                "operator": "John Doe",
                "custom_param": 42,
                "nested": {"key": "value"},
            },
        )

        assert meta.extensions["facility"] == "Nexus Center"
        assert meta.extensions["operator"] == "John Doe"
        assert meta.extensions["custom_param"] == 42
        assert meta.extensions["nested"]["key"] == "value"

    def test_forbid_extra_fields(self):
        """Test that extra fields not in schema or extensions are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NexusMetadata(
                creation_time="2024-01-15T10:30:00Z",
                data_type="TestData",
                dataset_type="Misc",
                unknown_field="value",  # type: ignore
            )

        errors = exc_info.value.errors()
        assert any("Extra inputs are not permitted" in str(e) for e in errors)

    def test_populate_by_name_aliases(self):
        """Test that field aliases work (populate_by_name=True)."""
        meta = NexusMetadata(
            **{
                "Creation Time": "2024-01-15T10:30:00Z",
                "Data Type": "TestData",
                "DatasetType": "Misc",
            }
        )

        assert meta.creation_time == "2024-01-15T10:30:00Z"
        assert meta.data_type == "TestData"
        assert meta.dataset_type == "Misc"

    def test_warnings_list_of_strings(self):
        """Test warnings as list of strings."""
        meta = NexusMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TestData",
            dataset_type="Misc",
            warnings=["field1", "field2"],
        )

        assert meta.warnings == ["field1", "field2"]

    def test_warnings_list_of_lists(self):
        """Test warnings as nested lists."""
        meta = NexusMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TestData",
            dataset_type="Misc",
            warnings=[["group1_field1", "group1_field2"], ["group2_field1"]],
        )

        assert len(meta.warnings) == 2


class TestImageMetadata:
    """Tests for ImageMetadata schema."""

    def test_image_metadata_valid_minimal(self):
        """Test ImageMetadata with required fields only."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
        )
        assert meta.dataset_type == "Image"
        assert meta.data_type == "SEM_Imaging"

    def test_image_metadata_with_quantities(self):
        """Test ImageMetadata with Pint Quantity fields."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            acceleration_voltage=ureg.Quantity(15, "kilovolt"),
            working_distance=ureg.Quantity(10.5, "millimeter"),
            beam_current=ureg.Quantity(100, "picoampere"),
        )
        assert meta.acceleration_voltage.magnitude == 15
        assert meta.working_distance.magnitude == 10.5
        assert meta.beam_current.magnitude == 100

    def test_image_metadata_with_string_quantities(self):
        """Test ImageMetadata accepts string quantities."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            acceleration_voltage="15 kV",
            working_distance="10.5 mm",
        )
        assert meta.acceleration_voltage.magnitude == 15
        assert meta.working_distance.magnitude == 10.5

    def test_image_metadata_with_stage_position(self):
        """Test ImageMetadata with StagePosition."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            stage_position=StagePosition(
                x=ureg.Quantity(100, "um"),
                tilt_alpha=ureg.Quantity(15, "degree"),
            ),
        )
        assert meta.stage_position.x.magnitude == 100
        assert meta.stage_position.tilt_alpha.magnitude == 15

    def test_image_metadata_type_enforcement(self):
        """Test that dataset_type is locked to 'Image'."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
        )
        assert meta.dataset_type == "Image"

    def test_image_metadata_allows_extensions(self):
        """Test ImageMetadata extensions for instrument-specific data."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            extensions={"detector_brightness": 50, "scan_speed": 6},
        )
        assert meta.extensions["detector_brightness"] == 50
        assert meta.extensions["scan_speed"] == 6


class TestSpectrumMetadata:
    """Tests for SpectrumMetadata schema."""

    def test_spectrum_metadata_valid_minimal(self):
        """Test SpectrumMetadata with required fields only."""
        meta = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS_Spectrum",
            dataset_type="Spectrum",
        )

        assert meta.dataset_type == "Spectrum"
        assert meta.data_type == "EDS_Spectrum"

    def test_spectrum_metadata_with_quantities(self):
        """Test SpectrumMetadata with Pint Quantity fields."""
        meta = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS_Spectrum",
            dataset_type="Spectrum",
            acquisition_time=ureg.Quantity(30, "second"),
            live_time=ureg.Quantity(28.5, "second"),
            detector_energy_resolution=ureg.Quantity(150, "eV"),
            channel_size=ureg.Quantity(10, "eV"),
            starting_energy=ureg.Quantity(0, "keV"),
        )

        assert meta.acquisition_time.magnitude == 30
        assert meta.live_time.magnitude == 28.5
        assert meta.detector_energy_resolution.magnitude == 150

    def test_spectrum_metadata_with_angles(self):
        """Test SpectrumMetadata with angle fields."""
        meta = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS_Spectrum",
            dataset_type="Spectrum",
            azimuthal_angle=ureg.Quantity(45, "degree"),
            elevation_angle=ureg.Quantity(30, "degree"),
            takeoff_angle=ureg.Quantity(35, "degree"),
        )

        assert meta.azimuthal_angle.magnitude == 45
        assert meta.elevation_angle.magnitude == 30

    def test_spectrum_metadata_with_elements(self):
        """Test SpectrumMetadata with elements list."""
        meta = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS_Spectrum",
            dataset_type="Spectrum",
            elements=["Fe", "Cr", "Ni"],
        )

        assert meta.elements == ["Fe", "Cr", "Ni"]

    def test_spectrum_metadata_type_enforcement(self):
        """Test that dataset_type is locked to 'Spectrum'."""
        meta = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS_Spectrum",
        )
        assert meta.dataset_type == "Spectrum"


class TestSpectrumImageMetadata:
    """Tests for SpectrumImageMetadata schema."""

    def test_spectrum_image_metadata_minimal(self):
        """Test SpectrumImageMetadata with required fields only."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
            dataset_type="SpectrumImage",
        )

        assert meta.dataset_type == "SpectrumImage"

    def test_spectrum_image_metadata_with_image_fields(self):
        """Test SpectrumImageMetadata includes ImageMetadata fields."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
            dataset_type="SpectrumImage",
            acceleration_voltage=ureg.Quantity(200, "kV"),
            magnification=50000.0,
        )

        assert meta.acceleration_voltage.magnitude == 200
        assert meta.magnification == 50000.0

    def test_spectrum_image_metadata_with_spectrum_fields(self):
        """Test SpectrumImageMetadata includes SpectrumMetadata fields."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
            dataset_type="SpectrumImage",
            acquisition_time=ureg.Quantity(300, "second"),
            live_time=ureg.Quantity(280, "second"),
        )

        assert meta.acquisition_time.magnitude == 300
        assert meta.live_time.magnitude == 280

    def test_spectrum_image_metadata_with_spectrum_image_fields(self):
        """Test SpectrumImageMetadata-specific fields."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
            dataset_type="SpectrumImage",
            pixel_time=ureg.Quantity(0.5, "second"),
            scan_mode="raster",
        )

        assert meta.pixel_time.magnitude == 0.5
        assert meta.scan_mode == "raster"

    def test_spectrum_image_metadata_combined(self):
        """Test SpectrumImageMetadata with fields from all parent schemas."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
            dataset_type="SpectrumImage",
            # From ImageMetadata
            acceleration_voltage=ureg.Quantity(200, "kV"),
            working_distance=ureg.Quantity(15, "mm"),
            magnification=50000.0,
            # From SpectrumMetadata
            acquisition_time=ureg.Quantity(300, "s"),
            live_time=ureg.Quantity(280, "s"),
            elements=["Cu", "Sn"],
            # SpectrumImageMetadata specific
            pixel_time=ureg.Quantity(0.5, "s"),
            scan_mode="serpentine",
        )

        assert meta.acceleration_voltage.magnitude == 200
        assert meta.acquisition_time.magnitude == 300
        assert meta.pixel_time.magnitude == 0.5
        assert meta.elements == ["Cu", "Sn"]

    def test_spectrum_image_type_enforcement(self):
        """Test that dataset_type is locked to 'SpectrumImage'."""
        meta = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS_SpectrumImage",
        )
        assert meta.dataset_type == "SpectrumImage"


class TestDiffractionMetadata:
    """Tests for DiffractionMetadata schema."""

    def test_diffraction_metadata_minimal(self):
        """Test DiffractionMetadata with required fields only."""
        meta = DiffractionMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TEM_Diffraction",
            dataset_type="Diffraction",
        )

        assert meta.dataset_type == "Diffraction"

    def test_diffraction_metadata_with_quantities(self):
        """Test DiffractionMetadata with Pint Quantity fields."""
        meta = DiffractionMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TEM_Diffraction",
            dataset_type="Diffraction",
            camera_length=ureg.Quantity(200, "millimeter"),
            convergence_angle=ureg.Quantity(0.5, "milliradian"),
            acceleration_voltage=ureg.Quantity(200, "kilovolt"),
        )

        assert meta.camera_length.magnitude == 200
        assert meta.convergence_angle.magnitude == 0.5
        assert meta.acceleration_voltage.magnitude == 200

    def test_diffraction_metadata_with_device(self):
        """Test DiffractionMetadata with acquisition device."""
        meta = DiffractionMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TEM_Diffraction",
            dataset_type="Diffraction",
            acquisition_device="K2 Summit Camera",
        )

        assert meta.acquisition_device == "K2 Summit Camera"

    def test_diffraction_type_enforcement(self):
        """Test that dataset_type is locked to 'Diffraction'."""
        meta = DiffractionMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="TEM_Diffraction",
        )
        assert meta.dataset_type == "Diffraction"


class TestMetadataRobustness:
    """Tests for edge cases and robustness."""

    def test_unicode_in_strings(self):
        """Test handling of unicode characters in strings."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging_μm_Å_©",
            dataset_type="Image",
            extensions={"operator": "José García"},
        )
        assert "μm" in meta.data_type
        assert meta.extensions["operator"] == "José García"

    def test_complex_extensions(self):
        """Test extensions with complex nested structures."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            extensions={
                "nested": {"level1": {"level2": {"level3": ["a", "b", "c"]}}},
                "list_of_dicts": [{"key1": "value1"}, {"key2": "value2"}],
            },
        )
        assert meta.extensions["nested"]["level1"]["level2"]["level3"] == [
            "a",
            "b",
            "c",
        ]
        assert meta.extensions["list_of_dicts"][0]["key1"] == "value1"

    def test_various_iso_timestamp_formats(self):
        """Test various valid ISO-8601 formats with timezone."""
        valid_timestamps = [
            "2024-01-15T10:30:00-05:00",
            "2024-01-15T10:30:00+00:00",
            "2024-01-15T10:30:00Z",
            "2024-12-31T23:59:59.999999-08:00",
        ]
        for ts in valid_timestamps:
            meta = ImageMetadata(
                creation_time=ts, data_type="SEM_Imaging", dataset_type="Image"
            )
            assert meta.creation_time == ts


class TestMetadataValidationIntegration:
    """Tests for validation integration across schemas."""

    def test_dataset_type_mismatch_detection(self):
        """Verify each schema enforces its own dataset_type."""
        # ImageMetadata should have dataset_type="Image"
        img = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM",
        )
        assert img.dataset_type == "Image"

        # SpectrumMetadata should have dataset_type="Spectrum"
        spec = SpectrumMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="EDS",
        )
        assert spec.dataset_type == "Spectrum"

    def test_inheritance_field_availability(self):
        """Test that all fields are available after inheritance."""
        spec_img = SpectrumImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="STEM_EDS",
            # Can use fields from ImageMetadata
            beam_current=ureg.Quantity(10, "pA"),
            # Can use fields from SpectrumMetadata
            elements=["Cu"],
            # Can use SpectrumImageMetadata-specific fields
            pixel_time=ureg.Quantity(0.1, "s"),
        )

        assert spec_img.beam_current is not None
        assert spec_img.elements is not None
        assert spec_img.pixel_time is not None

    def test_schema_json_schema_generation(self):
        """Test that Pydantic JSON schemas are properly generated."""
        schema = ImageMetadata.model_json_schema()

        assert "properties" in schema
        props = schema["properties"]
        # Schema uses aliases in JSON schema
        assert "Creation Time" in props or "creation_time" in props
        assert "DatasetType" in props or "dataset_type" in props
        assert "acceleration_voltage" in props

    def test_model_serialization(self):
        """Test that models can be serialized to JSON."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            acceleration_voltage=ureg.Quantity(15, "kV"),
        )

        # Should be able to serialize without error
        json_data = meta.model_dump()
        assert json_data["creation_time"] == "2024-01-15T10:30:00Z"
        assert json_data["data_type"] == "SEM_Imaging"

    def test_model_dump_with_mode(self):
        """Test model dumping with JSON mode."""
        meta = ImageMetadata(
            creation_time="2024-01-15T10:30:00Z",
            data_type="SEM_Imaging",
            dataset_type="Image",
            beam_current=ureg.Quantity(50, "pA"),
        )

        # JSON mode should serialize Pint quantities
        json_data = meta.model_dump(mode="json")
        assert json_data["creation_time"] == "2024-01-15T10:30:00Z"
