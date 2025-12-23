"""
Pydantic schemas for validating metadata extracted from microscopy files.

This module defines the structure and validation rules for the ``nx_meta``
dictionary that all extractor plugins must return. Using Pydantic models
ensures consistent data structure across different plugins, provides early
error detection, and enables clear error messages when plugins return
malformed metadata.

The primary model is :class:`NexusMetadata`, which validates the complete
``nx_meta`` structure including required fields (creation time, data type,
dataset type) and common optional fields (dimensions, warnings, instrument ID).

Examples
--------
Validate metadata returned by an extractor plugin:

>>> from nexusLIMS.extractors.schemas import NexusMetadata
>>> # Metadata from plugin
>>> nx_meta = {
...     "Creation Time": "2024-01-15T10:30:00-05:00",
...     "Data Type": "STEM_Imaging",
...     "DatasetType": "Image",
...     "Data Dimensions": "(1024, 1024)",
...     "Instrument ID": "FEI-Titan-TEM-635816",
... }
>>> # Validate (raises ValidationError if invalid)
>>> validated = NexusMetadata.model_validate(nx_meta)
>>> # Access using Python-style attributes or original keys
>>> print(validated.creation_time)
2024-01-15T10:30:00-05:00
>>> print(validated.data_type)
STEM_Imaging
"""

import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class NexusMetadata(BaseModel):
    """
    Schema for the ``nx_meta`` data structure returned by extractor plugins.

    All extractor plugins must return a list of dictionaries, where each
    dictionary contains an ``nx_meta`` key with metadata conforming to this
    schema. This model validates:

    - **Required fields**: Creation time, data type, and dataset type must
      always be present
    - **ISO-8601 timestamps**: Creation time must be a valid ISO-8601 string
      with timezone information
    - **Controlled vocabularies**: DatasetType is restricted to schema-defined
      values
    - **Optional fields**: Allows data dimensions, instrument ID, warnings, and
      any instrument-specific metadata

    The schema uses Pydantic's ``populate_by_name=True`` configuration to accept
    both Python-style field names (``creation_time``) and the original dict keys
    (``Creation Time``), ensuring backward compatibility.

    Attributes
    ----------
    creation_time : str
        ISO-8601 formatted timestamp string with timezone information
        indicating when the data was acquired. Must include a timezone
        offset (e.g., ``+00:00``, ``-05:00``) or ``Z`` for UTC.

        Examples: ``"2024-01-15T10:30:00-05:00"`` (EST),
        ``"2024-01-15T15:30:00+00:00"`` (UTC),
        ``"2024-01-15T15:30:00Z"`` (UTC shorthand)

    data_type : str
        Human-readable description of the data type, typically using
        underscore-separated components. This field provides semantic
        information about what kind of microscopy data was acquired.

        Examples: ``"STEM_Imaging"`` (Scanning TEM imaging),
        ``"TEM_EDS"`` (TEM energy-dispersive X-ray spectroscopy),
        ``"SEM_Imaging"`` (SEM imaging),
        ``"EELS_Spectrum"`` (Electron energy loss spectroscopy),
        ``"HIM_Imaging"`` (Helium ion microscope imaging)

    dataset_type : Literal["Image", "Spectrum", "SpectrumImage",
                           "Diffraction", "Misc", "Unknown"]
        Schema-defined category for the dataset type. This value maps
        directly to the ``type`` attribute in the Nexus Experiment XML
        schema and must be one of the predefined literal values.

        - ``"Image"`` : 2D image data
        - ``"Spectrum"`` : 1D spectral data (e.g., EDS, EELS)
        - ``"SpectrumImage"`` : 3D hyperspectral data (spatial + spectral)
        - ``"Diffraction"`` : Diffraction pattern data
        - ``"Misc"`` : Other structured data types
        - ``"Unknown"`` : Fallback when type cannot be determined

    data_dimensions : str or None, optional
        String representation of the data's shape as a tuple. Used to
        describe the dimensionality of the dataset for display purposes.
        May be omitted if dimensions are not applicable or cannot be determined.

        Examples: ``"(1024, 1024)"`` (2D image),
        ``"(12, 1024, 1024)"`` (3D stack or spectrum image),
        ``"(2048,)"`` (1D spectrum)

    instrument_id : str or None, optional
        Persistent identifier (PID) for the instrument from the NexusLIMS
        instrument database. This links the acquired data to a specific
        instrument configuration. May be ``None`` if the instrument cannot
        be determined from the file path or metadata.

        Examples: ``"FEI-Titan-TEM-635816"``,
        ``"Quanta-FEG-650-SEM-555555"``

    warnings : list of (str or list of str), optional
        List of field names flagged as unreliable or missing during metadata
        extraction. During record building, these field names are used to mark
        corresponding metadata in the XML with a ``warning="true"`` attribute,
        alerting users that the values may not be trustworthy. Each warning can
        be either a plain string (field name) or a single-element list containing
        the field name.

        Examples: ``["Operator", "Specimen"]`` (field names as strings),
        ``[["Temperature"]]`` (field name in list format),
        ``[]`` (no warnings)

    Notes
    -----
    The schema allows arbitrary additional fields using Pydantic's
    ``extra="allow"`` configuration. This permits instrument-specific
    metadata fields without breaking validation. Common additional fields
    include:

    - ``Voltage`` : Accelerating voltage (e.g., ``"200 kV"``)
    - ``Magnification`` : Nominal magnification
    - ``Specimen`` : Sample name or description
    - ``Operator`` : User who acquired the data
    - ``Stage Position`` : Dict with X, Y, Z, alpha, beta coordinates
    - ``EELS``, ``EDS``, ``Spectrum Imaging`` : Technique-specific metadata

    The model performs strict validation on required fields:

    - ``creation_time`` must parse as valid ISO-8601 and include timezone
    - ``dataset_type`` must be one of the allowed literal values
    - All required fields must be present (no ``None`` values)

    Validation errors will include detailed information about which field
    failed and why, making it easy to debug extractor plugins.

    Examples
    --------
    Valid metadata that passes validation:

    >>> nx_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "STEM_Imaging",
    ...     "DatasetType": "Image",
    ...     "Data Dimensions": "(1024, 1024)",
    ...     "Instrument ID": "FEI-Titan-TEM-635816",
    ...     "warnings": [],
    ...     "Voltage": "200 kV",  # Extra field - allowed
    ...     "Magnification": "50000x",  # Extra field - allowed
    ... }
    >>> validated = NexusMetadata.model_validate(nx_meta)
    >>> validated.creation_time
    '2024-01-15T10:30:00-05:00'

    Invalid metadata that fails validation:

    >>> bad_meta = {
    ...     "Creation Time": "2024-01-15 10:30:00",  # Missing timezone!
    ...     "Data Type": "STEM_Imaging",
    ...     "DatasetType": "InvalidType",  # Not in allowed values!
    ... }
    >>> NexusMetadata.model_validate(bad_meta)  # doctest: +SKIP
    Traceback (most recent call last):
        ...
    pydantic.ValidationError: ...

    See Also
    --------
    nexusLIMS.extractors.base.ExtractorPlugin : Base class for all extractor plugins
    nexusLIMS.extractors.parse_metadata : Function that uses this schema for validation
    """

    # Required fields - these must always be present
    creation_time: str = Field(
        ...,
        alias="Creation Time",
        description=(
            "ISO-8601 timestamp string with timezone information indicating when "
            "the data was acquired. Must include timezone offset (+00:00, -05:00) "
            "or 'Z' for UTC. Example: '2024-01-15T10:30:00-05:00'"
        ),
    )

    data_type: str = Field(
        ...,
        alias="Data Type",
        description=(
            "Human-readable description of the data type using underscore-separated "
            "components. Examples: 'STEM_Imaging', 'TEM_EDS', 'SEM_Imaging', "
            "'EELS_Spectrum', 'HIM_Imaging'"
        ),
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
        description=(
            "Schema-defined category for the dataset type. Must be one of: 'Image', "
            "'Spectrum', 'SpectrumImage', 'Diffraction', 'Misc', or 'Unknown'. This "
            "value maps to the 'type' attribute in the Nexus Experiment XML schema."
        ),
    )

    # Common optional fields
    data_dimensions: str | None = Field(
        None,
        alias="Data Dimensions",
        description=(
            "String representation of the data shape as a tuple. Examples: "
            "'(1024, 1024)' for 2D image, '(12, 1024, 1024)' for 3D data, "
            "'(2048,)' for 1D spectrum. May be omitted if not applicable."
        ),
    )

    instrument_id: str | None = Field(
        None,
        alias="Instrument ID",
        description=(
            "Persistent identifier (PID) for the instrument from the NexusLIMS "
            "instrument database. Links data to specific instrument configuration. "
            "Example: 'FEI-Titan-TEM-635816'. May be None if instrument cannot be "
            "determined."
        ),
    )

    warnings: list[str | list[str]] = Field(
        default_factory=list,
        description=(
            "List of field names flagged as unreliable or missing. During record "
            "building, these field names are used to mark corresponding metadata "
            "in the XML with warning='true' attribute. Each entry can be a string "
            "(field name) or single-element list containing the field name. "
            "Examples: ['Operator', 'Specimen'], [['Temperature']]"
        ),
    )

    # Configuration
    model_config = {
        "extra": "allow",  # Permit instrument-specific fields
        "populate_by_name": True,  # Accept both Python names and aliases
    }

    @field_validator("creation_time")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        """
        Validate that creation_time is a valid ISO-8601 timestamp with timezone.

        This validator ensures that:

        1. The timestamp can be parsed as valid ISO-8601 format
        2. The timestamp includes timezone information (required for unambiguous
           time representation across different instruments and locations)

        Parameters
        ----------
        v : str
            The creation_time string to validate

        Returns
        -------
        str
            The validated timestamp string (unchanged if valid)

        Raises
        ------
        ValueError
            If the timestamp is invalid or missing timezone information

        Examples
        --------
        Valid timestamps:

        >>> NexusMetadata.validate_iso_timestamp("2024-01-15T10:30:00-05:00")
        '2024-01-15T10:30:00-05:00'
        >>> NexusMetadata.validate_iso_timestamp("2024-01-15T15:30:00Z")
        '2024-01-15T15:30:00Z'

        Invalid timestamps:

        >>> NexusMetadata.validate_iso_timestamp(
        ...     "2024-01-15 10:30:00"
        ... )  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        ValueError: Invalid ISO-8601 timestamp format: 2024-01-15 10:30:00
        """
        # Validate parseable as ISO-8601
        try:
            datetime.fromisoformat(v)
        except ValueError as e:
            msg = f"Invalid ISO-8601 timestamp format: {v}"
            raise ValueError(msg) from e

        # Require timezone information
        # Count "-" >= 3 handles negative timezone offsets like -05:00
        # (date has 2 dashes: 2024-01-15, timezone adds 1 more)
        min_dashes_for_tz = 3
        if not ("+" in v or v.endswith("Z") or v.count("-") >= min_dashes_for_tz):
            msg = (
                f"Timestamp must include timezone information: {v}. "
                f"Use format like '2024-01-15T10:30:00-05:00' or "
                f"'2024-01-15T10:30:00Z'"
            )
            raise ValueError(msg)

        return v

    @field_validator("data_type")
    @classmethod
    def validate_data_type_not_empty(cls, v: str) -> str:
        """
        Validate that data_type is not an empty string.

        The data_type field must contain meaningful information describing
        the type of data acquired. Empty strings are not allowed.

        Parameters
        ----------
        v : str
            The data_type string to validate

        Returns
        -------
        str
            The validated data_type string (unchanged if valid)

        Raises
        ------
        ValueError
            If the data_type is an empty string or contains only whitespace

        Examples
        --------
        Valid data types:

        >>> NexusMetadata.validate_data_type_not_empty("STEM_Imaging")
        'STEM_Imaging'
        >>> NexusMetadata.validate_data_type_not_empty("Unknown")
        'Unknown'

        Invalid data types:

        >>> NexusMetadata.validate_data_type_not_empty("")  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        ValueError: Data Type cannot be empty
        >>> NexusMetadata.validate_data_type_not_empty("   ")  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        ValueError: Data Type cannot be empty
        """
        if not v or not v.strip():
            msg = "Data Type cannot be empty"
            raise ValueError(msg)
        return v


class TEMImageMetadata(NexusMetadata):
    """
    Schema for TEM (Transmission Electron Microscopy) image metadata.

    Extends the base :class:`NexusMetadata` schema with TEM-specific fields.
    This schema validates metadata from TEM imaging modes including conventional
    TEM, STEM, diffraction patterns, and related techniques.

    Attributes
    ----------
    voltage : str or None, optional
        Accelerating voltage of the electron beam (e.g., ``"200 kV"``, ``"300 kV"``).
        This is a critical TEM parameter that affects resolution and sample interaction.

    magnification : str or float or None, optional
        Nominal magnification value. Can be string with units (e.g., ``"50000x"``)
        or numeric value. Note that this is the instrument's reported magnification,
        which may differ from calibrated values.

    illumination_mode : str or None, optional
        TEM illumination mode indicating the optical configuration.
        Common values: ``"TEM"`` (parallel beam), ``"STEM"`` (focused probe),
        ``"EFTEM"`` (energy-filtered TEM), ``"Diffraction"``.

    camera_length : str or float or None, optional
        Camera length for diffraction patterns (e.g., ``"200 mm"``, ``"1.5 m"``).
        Only applicable for diffraction mode acquisitions.

    acquisition_device : str or None, optional
        Name/model of the detector or camera used for acquisition.
        Examples: ``"BM-UltraScan"``, ``"OneView"``, ``"K2 Summit"``,
        ``"BF-Detector"`` (bright-field STEM), ``"HAADF"``
        (high-angle annular dark-field).

    Notes
    -----
    All base :class:`NexusMetadata` fields remain required (Creation Time,
    Data Type, DatasetType). TEM-specific fields are optional but recommended
    for complete metadata capture.

    The schema allows additional fields beyond those listed here (via
    ``extra="allow"``), enabling capture of instrument-specific parameters
    like lens settings, aperture sizes, or custom acquisition parameters.

    Examples
    --------
    Valid TEM image metadata:

    >>> tem_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "TEM_Imaging",
    ...     "DatasetType": "Image",
    ...     "voltage": "200 kV",
    ...     "magnification": "50000x",
    ...     "illumination_mode": "TEM",
    ...     "acquisition_device": "BM-UltraScan",
    ... }
    >>> validated = TEMImageMetadata.model_validate(tem_meta)

    STEM imaging metadata:

    >>> stem_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "STEM_Imaging",
    ...     "DatasetType": "Image",
    ...     "voltage": "200 kV",
    ...     "magnification": "225000",
    ...     "illumination_mode": "STEM",
    ...     "acquisition_device": "HAADF",
    ... }
    >>> validated = TEMImageMetadata.model_validate(stem_meta)

    Diffraction pattern metadata:

    >>> diff_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "TEM_Diffraction",
    ...     "DatasetType": "Diffraction",
    ...     "voltage": "200 kV",
    ...     "camera_length": "200 mm",
    ...     "illumination_mode": "Diffraction",
    ... }
    >>> validated = TEMImageMetadata.model_validate(diff_meta)

    See Also
    --------
    NexusMetadata : Base schema for all extractor metadata
    SEMImageMetadata : Schema for SEM-specific image metadata
    """

    voltage: str | float | None = Field(
        None,
        alias="Voltage",
        description=(
            "Accelerating voltage of the electron beam (e.g., '200 kV', '300 kV'). "
            "Can be string with units or numeric value."
        ),
    )

    magnification: str | float | None = Field(
        None,
        alias="Magnification",
        description=(
            "Nominal magnification value. Can be string with units (e.g., '50000x') "
            "or numeric value representing the magnification factor."
        ),
    )

    illumination_mode: str | None = Field(
        None,
        alias="Illumination Mode",
        description=(
            "TEM illumination mode: 'TEM' (parallel beam), 'STEM' (focused probe), "
            "'EFTEM' (energy-filtered), 'Diffraction', etc."
        ),
    )

    camera_length: str | float | None = Field(
        None,
        alias="Camera Length",
        description=(
            "Camera length for diffraction patterns (e.g., '200 mm', '1.5 m'). "
            "Applicable for diffraction mode acquisitions."
        ),
    )

    acquisition_device: str | None = Field(
        None,
        alias="Acquisition Device",
        description=(
            "Name/model of detector or camera. Examples: 'BM-UltraScan', 'OneView', "
            "'K2 Summit', 'BF-Detector', 'HAADF', 'ADF'."
        ),
    )


class SEMImageMetadata(NexusMetadata):
    """
    Schema for SEM (Scanning Electron Microscopy) image metadata.

    Extends the base :class:`NexusMetadata` schema with SEM-specific fields.
    This schema validates metadata from SEM and FIB (Focused Ion Beam) instruments,
    including various detector types and imaging modes.

    Attributes
    ----------
    voltage : str or float or None, optional
        Accelerating voltage or beam energy (e.g., ``"5 kV"``, ``"15.0 kV"``).
        For FIB, this is the ion beam energy. Critical parameter affecting
        resolution, penetration depth, and sample interaction.

    magnification : str or float or None, optional
        Nominal magnification value. Can be string with units (e.g., ``"10000x"``)
        or numeric value. Represents the instrument's reported magnification.

    working_distance : str or float or None, optional
        Working distance between the final lens and the sample surface
        (e.g., ``"10 mm"``, ``"5.2 mm"``). Affects depth of field and resolution.

    beam_current : str or float or None, optional
        Electron beam current (e.g., ``"100 pA"``, ``"1.2 nA"``).
        Higher currents increase signal but may cause sample damage.

    detector : str or None, optional
        Primary detector used for image acquisition.
        Common types: ``"ETD"`` (Everhart-Thornley), ``"TLD"`` (through-the-lens),
        ``"CBS"`` (circular backscatter), ``"InLens"``, ``"SE"`` (secondary electron),
        ``"BSE"`` (backscattered electron), ``"STEM"`` (in SEM-STEM mode).

    dwell_time : str or float or None, optional
        Pixel dwell time during scan (e.g., ``"1 µs"``, ``"10 us"``, ``"0.000001"``).
        Longer dwell times increase signal-to-noise ratio but slow acquisition.

    scan_rotation : str or float or None, optional
        Scan rotation angle in degrees (e.g., ``"0"``, ``"45.0"``, ``"-90"``).
        Used to align features with image axes.

    Notes
    -----
    All base :class:`NexusMetadata` fields remain required (Creation Time,
    Data Type, DatasetType). SEM-specific fields are optional but recommended
    for complete metadata capture.

    The schema allows additional fields beyond those listed (via ``extra="allow"``),
    enabling capture of instrument-specific parameters like spot size, aperture
    settings, gas injection, or environmental chamber conditions.

    Examples
    --------
    Valid SEM image metadata:

    >>> sem_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "SEM_Imaging",
    ...     "DatasetType": "Image",
    ...     "voltage": "10 kV",
    ...     "magnification": "5000x",
    ...     "working_distance": "10 mm",
    ...     "beam_current": "100 pA",
    ...     "detector": "ETD",
    ... }
    >>> validated = SEMImageMetadata.model_validate(sem_meta)

    FIB/SEM metadata (Helium Ion Microscope):

    >>> him_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "HIM_Imaging",
    ...     "DatasetType": "Image",
    ...     "voltage": "30 kV",
    ...     "magnification": "100000",
    ...     "working_distance": "8.5 mm",
    ...     "detector": "ETD",
    ...     "dwell_time": "1 us",
    ... }
    >>> validated = SEMImageMetadata.model_validate(him_meta)

    Low-vacuum SEM metadata:

    >>> lv_sem_meta = {
    ...     "Creation Time": "2024-01-15T10:30:00-05:00",
    ...     "Data Type": "SEM_Imaging",
    ...     "DatasetType": "Image",
    ...     "voltage": "15 kV",
    ...     "magnification": "2000x",
    ...     "working_distance": "15 mm",
    ...     "detector": "LFD",  # Large field detector
    ...     "Chamber Pressure": "0.5 Torr",  # Extra field
    ... }
    >>> validated = SEMImageMetadata.model_validate(lv_sem_meta)

    See Also
    --------
    NexusMetadata : Base schema for all extractor metadata
    TEMImageMetadata : Schema for TEM-specific image metadata
    """

    voltage: str | float | None = Field(
        None,
        alias="Voltage",
        description=(
            "Accelerating voltage or beam energy (e.g., '5 kV', '15.0 kV'). "
            "For FIB, this is the ion beam energy. Can be string with units or numeric."
        ),
    )

    magnification: str | float | None = Field(
        None,
        alias="Magnification",
        description=(
            "Nominal magnification value. Can be string with units (e.g., '10000x') "
            "or numeric value representing the magnification factor."
        ),
    )

    working_distance: str | float | None = Field(
        None,
        alias="Working Distance",
        description=(
            "Working distance between final lens and sample "
            "(e.g., '10 mm', '5.2'). Affects depth of field and resolution. "
            "Can include units or be numeric (mm)."
        ),
    )

    beam_current: str | float | None = Field(
        None,
        alias="Beam Current",
        description=(
            "Electron beam current (e.g., '100 pA', '1.2 nA'). "
            "Can be string with units or numeric value."
        ),
    )

    detector: str | None = Field(
        None,
        alias="Detector",
        description=(
            "Primary detector used for acquisition. Examples: 'ETD', 'TLD', 'CBS', "
            "'InLens', 'SE', 'BSE', 'STEM', 'LFD'."
        ),
    )

    dwell_time: str | float | None = Field(
        None,
        alias="Dwell Time",
        description=(
            "Pixel dwell time during scan (e.g., '1 µs', '10 us', '0.000001'). "
            "Can be string with units or numeric value in seconds."
        ),
    )

    scan_rotation: str | float | None = Field(
        None,
        alias="Scan Rotation",
        description=(
            "Scan rotation angle in degrees (e.g., '0', '45.0', '-90'). "
            "Can be string or numeric value."
        ),
    )
