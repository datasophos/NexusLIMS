"""
Type-specific metadata schemas for NexusLIMS extractor plugins.

This module defines Pydantic models for validating metadata extracted from different
types of microscopy data (Image, Spectrum, SpectrumImage, Diffraction). Each schema
uses Pint Quantity objects for physical measurements, EM Glossary field names, and
supports flexible extension fields.

The schemas follow a hierarchical structure:
- :class:`NexusMetadata` - Base schema with common fields
- :class:`ImageMetadata` - SEM/TEM/STEM image data
- :class:`SpectrumMetadata` - EDS/EELS spectral data
- :class:`SpectrumImageMetadata` - Hyperspectral data (inherits from both)
- :class:`DiffractionMetadata` - Diffraction pattern data

**Key Features:**
- Pint Quantity fields for machine-actionable units
- EM Glossary v2.0.0 terminology
- Automatic unit normalization to preferred units
- Flexible extensions section for instrument-specific metadata
- Strict validation of core fields

Examples
--------
Validate SEM image metadata:

>>> from nexusLIMS.schemas.metadata import ImageMetadata
>>> from nexusLIMS.schemas.units import ureg
>>>
>>> meta = ImageMetadata(
...     creation_time="2024-01-15T10:30:00-05:00",
...     data_type="SEM_Imaging",
...     dataset_type="Image",
...     acceleration_voltage=ureg.Quantity(10, "kilovolt"),
...     working_distance=ureg.Quantity(10, "millimeter"),
...     beam_current=ureg.Quantity(100, "picoampere"),
... )
>>> print(meta.acceleration_voltage)
10.0 kilovolt

Validate spectrum metadata:

>>> from nexusLIMS.schemas.metadata import SpectrumMetadata
>>>
>>> spec_meta = SpectrumMetadata(
...     creation_time="2024-01-15T10:30:00-05:00",
...     data_type="EDS_Spectrum",
...     dataset_type="Spectrum",
...     acquisition_time=ureg.Quantity(30, "second"),
...     live_time=ureg.Quantity(28.5, "second"),
... )

Use extensions for instrument-specific fields:

>>> meta_with_ext = ImageMetadata(
...     creation_time="2024-01-15T10:30:00-05:00",
...     data_type="SEM_Imaging",
...     dataset_type="Image",
...     extensions={
...         "facility": "Nexus Microscopy Center",
...         "detector_brightness": 50.0,
...         "scan_speed": 6,
...     }
... )
"""

import logging
from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from nexusLIMS.schemas.pint_types import PintQuantity

logger = logging.getLogger(__name__)


class StagePosition(BaseModel):
    """
    Stage position with coordinates and tilt angles.

    Represents the physical position and orientation of the microscope stage.
    All fields use Pint Quantity objects with appropriate units.

    Attributes
    ----------
    x : PintQuantity or None, optional
        Stage X coordinate. Preferred unit: micrometer (µm)

    y : PintQuantity or None, optional
        Stage Y coordinate. Preferred unit: micrometer (µm)

    z : PintQuantity or None, optional
        Stage Z coordinate (height). Preferred unit: millimeter (mm)

    rotation : PintQuantity or None, optional
        Stage rotation angle around Z axis. Preferred unit: degree (°)

    tilt_alpha : PintQuantity or None, optional
        Tilt angle along the stage's primary tilt axis (alpha).
        Preferred unit: degree (°)

    tilt_beta : PintQuantity or None, optional
        Tilt angle along the stage's secondary tilt axis (beta), if the stage
        is capable of dual-axis tilting. Preferred unit: degree (°)

    Examples
    --------
    >>> from nexusLIMS.schemas.metadata import StagePosition
    >>> from nexusLIMS.schemas.units import ureg
    >>>
    >>> pos = StagePosition(
    ...     x=ureg.Quantity(100, "um"),
    ...     y=ureg.Quantity(200, "um"),
    ...     z=ureg.Quantity(5, "mm"),
    ...     tilt_alpha=ureg.Quantity(10, "degree"),
    ... )
    >>> print(pos.x)
    100 micrometer

    Notes
    -----
    All fields are optional to accommodate different stage configurations.
    Some microscopes may not have all degrees of freedom. Single-tilt stages
    will only have tilt_alpha, while dual-tilt stages (e.g., tomography holders)
    will have both tilt_alpha and tilt_beta.
    """

    x: PintQuantity | None = Field(
        None,
        description="Stage X coordinate",
    )

    y: PintQuantity | None = Field(
        None,
        description="Stage Y coordinate",
    )

    z: PintQuantity | None = Field(
        None,
        description="Stage Z coordinate (height)",
    )

    rotation: PintQuantity | None = Field(
        None,
        description="Stage rotation angle around Z axis",
    )

    tilt_alpha: PintQuantity | None = Field(
        None,
        description="Tilt angle along primary tilt axis (alpha)",
    )

    tilt_beta: PintQuantity | None = Field(
        None,
        description="Tilt angle along secondary tilt axis (beta), if capable",
    )

    model_config = {
        "extra": "allow",  # Allow additional vendor-specific coordinates
    }


class NexusMetadata(BaseModel):
    """
    Base schema for all NexusLIMS metadata.

    This is the foundation schema that all type-specific schemas inherit from.
    It defines the required fields common to all dataset types and provides
    the extension mechanism for instrument-specific metadata.

    Attributes
    ----------
    creation_time : str
        ISO-8601 formatted timestamp with timezone indicating when the data
        was acquired. Must include timezone offset (+00:00, -05:00) or 'Z'.

        Examples: "2024-01-15T10:30:00-05:00", "2024-01-15T15:30:00Z"

    data_type : str
        Human-readable description of the data type using underscore-separated
        components. Examples: "STEM_Imaging", "TEM_EDS", "SEM_Imaging"

    dataset_type : Literal["Image", "Spectrum", "SpectrumImage", "Diffraction",
                           "Misc", "Unknown"]
        Schema-defined category matching the Nexus Experiment XML schema type
        attribute.

    data_dimensions : str or None, optional
        String representation of data shape as a tuple.
        Examples: "(1024, 1024)", "(2048,)", "(12, 1024, 1024)"

    instrument_id : str or None, optional
        NexusLIMS persistent identifier for the instrument.
        Examples: "FEI-Titan-TEM-635816", "Quanta-FEG-650-SEM-555555"

    warnings : list[str | list[str]], optional
        Field names flagged as unreliable. These are marked with warning="true"
        in the XML output.

    extensions : dict[str, Any], optional
        Flexible container for instrument-specific metadata that doesn't fit
        the core schema. Use this for vendor-specific fields, facility metadata,
        or experimental parameters not covered by EM Glossary.

    Notes
    -----
    The extensions section allows arbitrary metadata while maintaining strict
    validation on core fields. This hybrid approach ensures:
    - Core fields are consistent and validated
    - Instrument-specific metadata is preserved
    - No data loss during extraction

    Extensions should use descriptive key names and avoid conflicts with core
    field names.
    """

    # Required fields (common to all types)
    creation_time: str = Field(
        ...,
        alias="Creation Time",
        description="ISO-8601 timestamp with timezone",
    )

    data_type: str = Field(
        ...,
        alias="Data Type",
        description="Human-readable data type description",
    )

    dataset_type: Literal[
        "Image",
        "Spectrum",
        "SpectrumImage",
        "Diffraction",
        "Misc",
        "Unknown",
    ] = Field(
        ...,
        alias="DatasetType",
        description="Schema-defined dataset category",
    )

    # Common optional fields
    data_dimensions: str | None = Field(
        None,
        alias="Data Dimensions",
        description="String representation of data shape",
    )

    instrument_id: str | None = Field(
        None,
        alias="Instrument ID",
        description="NexusLIMS persistent instrument identifier",
    )

    warnings: list[str | list[str]] = Field(
        default_factory=list,
        description="Field names flagged as unreliable",
    )

    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Instrument-specific metadata extensions",
    )

    # Configuration
    model_config = {
        "populate_by_name": True,  # Accept both Python names and aliases
        "extra": "forbid",  # Force use of extensions for extra fields
    }

    @field_validator("creation_time")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        """Validate ISO-8601 timestamp with timezone."""
        try:
            datetime.fromisoformat(v)
        except ValueError as e:
            msg = f"Invalid ISO-8601 timestamp format: {v}"
            raise ValueError(msg) from e

        # Require timezone information
        min_dashes_for_tz = 3
        if not ("+" in v or v.endswith("Z") or v.count("-") >= min_dashes_for_tz):
            msg = (
                f"Timestamp must include timezone: {v}. "
                f"Use format like '2024-01-15T10:30:00-05:00' or '...Z'"
            )
            raise ValueError(msg)

        return v

    @field_validator("data_type")
    @classmethod
    def validate_data_type_not_empty(cls, v: str) -> str:
        """Validate data_type is not empty."""
        if not v or not v.strip():
            msg = "Data Type cannot be empty"
            raise ValueError(msg)
        return v


class ImageMetadata(NexusMetadata):
    """
    Schema for image dataset metadata (SEM, TEM, STEM, FIB, HIM).

    Extends :class:`NexusMetadata` with fields specific to 2D image acquisition.
    Uses Pint Quantity objects for all physical measurements.

    Attributes
    ----------
    acceleration_voltage : PintQuantity or None, optional
        Accelerating voltage of the electron/ion beam.
        Preferred unit: kilovolt (kV)
        EM Glossary: EMG_00000004

    working_distance : PintQuantity or None, optional
        Distance between final lens and sample surface.
        Preferred unit: millimeter (mm)
        EM Glossary: EMG_00000050

    beam_current : PintQuantity or None, optional
        Electron beam current.
        Preferred unit: picoampere (pA)
        EM Glossary: EMG_00000006

    emission_current : PintQuantity or None, optional
        Emission current from electron source.
        Preferred unit: microampere (µA)
        EM Glossary: EMG_00000025

    dwell_time : PintQuantity or None, optional
        Time the beam dwells on each pixel during scanning.
        Preferred unit: microsecond (µs)
        EM Glossary: EMG_00000015

    magnification : float or None, optional
        Nominal magnification (dimensionless).

    field_of_view : PintQuantity or None, optional
        Width of the scanned area.
        Preferred unit: micrometer (µm)

    pixel_width : PintQuantity or None, optional
        Physical width of a single pixel.
        Preferred unit: nanometer (nm)

    pixel_height : PintQuantity or None, optional
        Physical height of a single pixel.
        Preferred unit: nanometer (nm)

    scan_rotation : PintQuantity or None, optional
        Rotation angle of the scan frame.
        Preferred unit: degree (°)

    detector_type : str or None, optional
        Type or name of detector used.
        Examples: "ETD", "InLens", "HAADF", "BF"

    acquisition_device : str or None, optional
        Name of the acquisition device or camera.
        Examples: "BM-UltraScan", "K2 Summit"

    stage_position : StagePosition or None, optional
        Stage coordinates and tilt angles. See :class:`StagePosition` for details.
        Preferred units: x/y in µm, z in mm, angles in degrees

    Examples
    --------
    >>> from nexusLIMS.schemas.metadata import ImageMetadata
    >>> from nexusLIMS.schemas.units import ureg
    >>>
    >>> meta = ImageMetadata(
    ...     creation_time="2024-01-15T10:30:00-05:00",
    ...     data_type="SEM_Imaging",
    ...     dataset_type="Image",
    ...     acceleration_voltage=ureg.Quantity(15, "kV"),
    ...     working_distance=ureg.Quantity(10.5, "mm"),
    ...     beam_current=ureg.Quantity(50, "pA"),
    ...     magnification=5000.0,
    ... )
    """

    dataset_type: Literal["Image"] = Field(
        "Image",
        alias="DatasetType",
        description="Must be 'Image' for this schema",
    )

    # Image-specific fields (using EM Glossary names)
    acceleration_voltage: PintQuantity | None = Field(
        None,
        description="Accelerating voltage (EMG_00000004)",
    )

    working_distance: PintQuantity | None = Field(
        None,
        description="Working distance (EMG_00000050)",
    )

    beam_current: PintQuantity | None = Field(
        None,
        description="Beam current (EMG_00000006)",
    )

    emission_current: PintQuantity | None = Field(
        None,
        description="Emission current (EMG_00000025)",
    )

    dwell_time: PintQuantity | None = Field(
        None,
        description="Pixel dwell time (EMG_00000015)",
    )

    magnification: float | None = Field(
        None,
        description="Nominal magnification (dimensionless)",
    )

    field_of_view: PintQuantity | None = Field(
        None,
        description="Field of view width",
    )

    pixel_width: PintQuantity | None = Field(
        None,
        description="Physical pixel width",
    )

    pixel_height: PintQuantity | None = Field(
        None,
        description="Physical pixel height",
    )

    scan_rotation: PintQuantity | None = Field(
        None,
        description="Scan rotation angle",
    )

    detector_type: str | None = Field(
        None,
        description="Detector type or name",
    )

    acquisition_device: str | None = Field(
        None,
        description="Acquisition device or camera name",
    )

    stage_position: StagePosition | None = Field(
        None,
        description="Stage coordinates and tilt angles",
    )


class SpectrumMetadata(NexusMetadata):
    """
    Schema for spectrum dataset metadata (EDS, EELS, etc.).

    Extends :class:`NexusMetadata` with fields specific to spectral data acquisition.

    Attributes
    ----------
    acquisition_time : PintQuantity or None, optional
        Total time for spectrum acquisition.
        Preferred unit: second (s)
        EM Glossary: EMG_00000055

    live_time : PintQuantity or None, optional
        Live time excluding dead time.
        Preferred unit: second (s)

    detector_energy_resolution : PintQuantity or None, optional
        Energy resolution of the detector.
        Preferred unit: electronvolt (eV)

    channel_size : PintQuantity or None, optional
        Energy width of each channel.
        Preferred unit: electronvolt (eV)

    starting_energy : PintQuantity or None, optional
        Starting energy of the spectrum.
        Preferred unit: kiloelectronvolt (keV)

    azimuthal_angle : PintQuantity or None, optional
        Azimuthal angle of the detector.
        Preferred unit: degree (°)

    elevation_angle : PintQuantity or None, optional
        Elevation angle of the detector.
        Preferred unit: degree (°)

    takeoff_angle : PintQuantity or None, optional
        X-ray takeoff angle.
        Preferred unit: degree (°)

    elements : list[str] or None, optional
        Detected elements (e.g., ["Fe", "Cr", "Ni"])

    Examples
    --------
    >>> from nexusLIMS.schemas.metadata import SpectrumMetadata
    >>> from nexusLIMS.schemas.units import ureg
    >>>
    >>> meta = SpectrumMetadata(
    ...     creation_time="2024-01-15T10:30:00-05:00",
    ...     data_type="EDS_Spectrum",
    ...     dataset_type="Spectrum",
    ...     acquisition_time=ureg.Quantity(30, "s"),
    ...     live_time=ureg.Quantity(28.5, "s"),
    ...     channel_size=ureg.Quantity(10, "eV"),
    ... )
    """

    dataset_type: Literal["Spectrum"] = Field(
        "Spectrum",
        alias="DatasetType",
        description="Must be 'Spectrum' for this schema",
    )

    # Spectrum-specific fields
    acquisition_time: PintQuantity | None = Field(
        None,
        description="Total acquisition time (EMG_00000055)",
    )

    live_time: PintQuantity | None = Field(
        None,
        description="Live time (excludes dead time)",
    )

    detector_energy_resolution: PintQuantity | None = Field(
        None,
        description="Detector energy resolution",
    )

    channel_size: PintQuantity | None = Field(
        None,
        description="Energy width per channel",
    )

    starting_energy: PintQuantity | None = Field(
        None,
        description="Spectrum starting energy",
    )

    azimuthal_angle: PintQuantity | None = Field(
        None,
        description="Detector azimuthal angle",
    )

    elevation_angle: PintQuantity | None = Field(
        None,
        description="Detector elevation angle",
    )

    takeoff_angle: PintQuantity | None = Field(
        None,
        description="X-ray takeoff angle",
    )

    elements: list[str] | None = Field(
        None,
        description="Detected elements",
    )


class SpectrumImageMetadata(ImageMetadata, SpectrumMetadata):
    """
    Schema for spectrum image (hyperspectral) dataset metadata.

    Combines fields from both :class:`ImageMetadata` and :class:`SpectrumMetadata`
    since spectrum images have both spatial and spectral dimensions.

    Attributes
    ----------
    Inherits all fields from ImageMetadata and SpectrumMetadata, plus:

    pixel_time : PintQuantity or None, optional
        Time spent acquiring spectrum at each pixel.
        Preferred unit: second (s)

    scan_mode : str or None, optional
        Scanning mode used for acquisition.
        Examples: "raster", "serpentine", "fly-back"

    Examples
    --------
    >>> from nexusLIMS.schemas.metadata import SpectrumImageMetadata
    >>> from nexusLIMS.schemas.units import ureg
    >>>
    >>> meta = SpectrumImageMetadata(
    ...     creation_time="2024-01-15T10:30:00-05:00",
    ...     data_type="STEM_EDS_SpectrumImage",
    ...     dataset_type="SpectrumImage",
    ...     acceleration_voltage=ureg.Quantity(200, "kV"),  # Image field
    ...     acquisition_time=ureg.Quantity(1200, "s"),  # Spectrum field
    ...     pixel_time=ureg.Quantity(0.5, "s"),  # SpectrumImage specific
    ... )
    """

    dataset_type: Literal["SpectrumImage"] = Field(
        "SpectrumImage",
        alias="DatasetType",
        description="Must be 'SpectrumImage' for this schema",
    )

    # SpectrumImage-specific fields
    pixel_time: PintQuantity | None = Field(
        None,
        description="Time per pixel for spectrum acquisition",
    )

    scan_mode: str | None = Field(
        None,
        description="Scanning mode (raster, serpentine, etc.)",
    )

    @model_validator(mode="after")
    def validate_spectrum_image_fields(self) -> "SpectrumImageMetadata":
        """Ensure SpectrumImage has both image and spectrum metadata."""
        # Just a placeholder - could add validation logic here if needed
        return self


class DiffractionMetadata(NexusMetadata):
    """
    Schema for diffraction pattern dataset metadata (TEM, EBSD, etc.).

    Extends :class:`NexusMetadata` with fields specific to diffraction data.

    Attributes
    ----------
    camera_length : PintQuantity or None, optional
        Camera length for diffraction pattern.
        Preferred unit: millimeter (mm)
        EM Glossary: EMG_00000008

    convergence_angle : PintQuantity or None, optional
        Convergence angle of the electron beam.
        Preferred unit: milliradian (mrad)
        EM Glossary: EMG_00000010

    acceleration_voltage : PintQuantity or None, optional
        Accelerating voltage (also relevant for diffraction).
        Preferred unit: kilovolt (kV)
        EM Glossary: EMG_00000004

    acquisition_device : str or None, optional
        Name of the detector/camera used.

    Examples
    --------
    >>> from nexusLIMS.schemas.metadata import DiffractionMetadata
    >>> from nexusLIMS.schemas.units import ureg
    >>>
    >>> meta = DiffractionMetadata(
    ...     creation_time="2024-01-15T10:30:00-05:00",
    ...     data_type="TEM_Diffraction",
    ...     dataset_type="Diffraction",
    ...     camera_length=ureg.Quantity(200, "mm"),
    ...     convergence_angle=ureg.Quantity(0.5, "mrad"),
    ...     acceleration_voltage=ureg.Quantity(200, "kV"),
    ... )
    """

    dataset_type: Literal["Diffraction"] = Field(
        "Diffraction",
        alias="DatasetType",
        description="Must be 'Diffraction' for this schema",
    )

    # Diffraction-specific fields
    camera_length: PintQuantity | None = Field(
        None,
        description="Camera length (EMG_00000008)",
    )

    convergence_angle: PintQuantity | None = Field(
        None,
        description="Convergence angle (EMG_00000010)",
    )

    acceleration_voltage: PintQuantity | None = Field(
        None,
        description="Accelerating voltage (EMG_00000004)",
    )

    acquisition_device: str | None = Field(
        None,
        description="Detector or camera name",
    )
