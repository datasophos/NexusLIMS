"""Base protocols and data structures for the extractor plugin system.

This module defines the core interfaces that all extractors must implement,
along with supporting data structures for passing context to extractors.

The plugin system uses Protocol-based structural typing (PEP 544) rather than
inheritance, allowing flexibility in implementation while maintaining type safety.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, NamedTuple, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.instruments import Instrument

logger = logging.getLogger(__name__)

__all__ = [
    "BaseExtractor",
    "ExtractionContext",
    "FieldDefinition",
    "PreviewGenerator",
]


class FieldDefinition(NamedTuple):
    """
    Configuration for extracting a single metadata field.

    This NamedTuple provides a declarative way to define how metadata fields
    should be extracted from instrument data files. It's used by TIFF-based
    extractors (Quanta, Tescan, Orion HIM) to reduce code duplication.

    Attributes
    ----------
    section : str
        Section name in metadata dict (e.g., "Beam", "User", "System").
        For nested dicts, this is the top-level key.
    source_key : str
        Key within the section to extract the value from.
    output_key : str | list[str]
        Output key in nx_meta. Can be a string for flat keys or a list
        for nested paths (e.g., ["Stage Position", "X"]).
    factor : float
        Unit conversion factor. The extracted value is multiplied by this.
        Use 1.0 for no conversion. For SI unit conversions, use powers of 10
        (e.g., 1e6 to convert meters to micrometers).
    is_string : bool
        If True, keep value as string. If False, attempt numeric conversion
        with Decimal for precision.
    suppress_zero : bool, default=False
        If True, skip field if the numeric value equals zero.
        Only applies when is_string=False.

    Examples
    --------
    >>> # Simple numeric field with unit conversion (m → μm)
    >>> FieldDefinition("Beam", "HFW", "Horizontal Field Width (μm)", 1e6, False)

    >>> # String field (no conversion)
    >>> FieldDefinition("System", "Chamber", "Chamber ID", 1.0, True)

    >>> # Nested output path
    >>> FieldDefinition("Beam", "StageX", ["Stage Position", "X"], 1.0, False)

    >>> # Suppress zero values
    >>> FieldDefinition("Beam", "BeamShiftX", "Beam Shift X",
    >>>                 1.0, False, suppress_zero=True)
    """

    section: str
    source_key: str
    output_key: str | list[str]
    factor: float
    is_string: bool
    suppress_zero: bool = False


@dataclass
class ExtractionContext:
    """
    Context information passed to extractors and preview generators.

    This dataclass encapsulates all the information an extractor needs to
    process a file. Using a context object allows us to add new parameters
    in the future without breaking existing extractors.

    Attributes
    ----------
    file_path
        Path to the file to be processed
    instrument
        The instrument that created this file, if known. Can be None for
        files that cannot be associated with a specific instrument.
    signal_index
        For files with multiple signals, the index of the signal to process.
        If None, processes all signals or defaults to the first signal.

    Examples
    --------
    >>> from pathlib import Path
    >>> from nexusLIMS.instruments import get_instr_from_filepath
    >>> file_path = Path("/path/to/data.dm3")
    >>> instrument = get_instr_from_filepath(file_path)
    >>> context = ExtractionContext(file_path, instrument)
    """

    file_path: Path
    instrument: Instrument | None = None
    signal_index: int | None = None


class BaseExtractor(Protocol):
    """
    Protocol defining the interface for metadata extractors.

    This is a Protocol (structural subtype) rather than an ABC, meaning any class
    that implements these attributes and methods is automatically considered a
    valid extractor - no inheritance required.

    All extractors MUST implement defensive error handling:
    - Never raise exceptions from extract() - catch all and return minimal metadata
    - Always return a list of metadata dicts (one per signal)
    - Log errors for debugging but don't propagate them

    Attributes
    ----------
    name : str
        Unique identifier for this extractor (e.g., "dm3_extractor").
        Should be a valid Python identifier.
    priority : int
        Priority for this extractor (0-1000, higher = preferred).
        See notes below for conventions.
    supported_extensions : set[str] | None
        File extensions this extractor supports (without dots).
        Set to None for wildcard extractors that support all files.
        Empty set means no extensions are directly supported (content sniffing only).

    Notes
    -----
    **Priority Conventions:**

    - 0-49: Low priority (generic/fallback extractors)
    - 50-149: Normal priority (standard extractors)
    - 150-249: High priority (specialized/optimized extractors)
    - 250+: Override priority (force specific behavior)

    When multiple extractors support the same file, the registry will
    try them in descending priority order until one's supports() method
    returns True.

    Examples
    --------
    >>> class DM3Extractor:
    ...     \"\"\"Extract metadata from DigitalMicrograph .dm3/.dm4 files.\"\"\"
    ...
    ...     name = "dm3_extractor"
    ...     priority = 100
    ...
    ...     def supports(self, context: ExtractionContext) -> bool:
    ...         ext = context.file_path.suffix.lower().lstrip('.')
    ...         return ext in ('dm3', 'dm4')
    ...
    ...     def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
    ...         # Extraction logic here
    ...         return [{"nx_meta": {...}}]
    """

    name: str
    priority: int
    supported_extensions: set[str] | None

    def supports(self, context: ExtractionContext) -> bool:
        """
        Determine if this extractor can handle the given file.

        This method allows complex logic beyond simple extension matching:
        - Content sniffing (read file headers)
        - File size checks
        - Instrument-specific handling
        - Metadata validation

        The registry will call supports() on extractors in priority order
        until one returns True.

        Parameters
        ----------
        context
            Context containing file path, instrument info, etc.

        Returns
        -------
        bool
            True if this extractor can handle this file, False otherwise

        Examples
        --------
        Extension-based matching:

        >>> def supports(self, context: ExtractionContext) -> bool:
        ...     ext = context.file_path.suffix.lower().lstrip('.')
        ...     return ext in ('dm3', 'dm4')

        Content sniffing:

        >>> def supports(self, context: ExtractionContext) -> bool:
        ...     if context.file_path.suffix.lower() != '.tif':
        ...         return False
        ...     with open(context.file_path, 'rb') as f:
        ...         header = f.read(1024)
        ...         return b'[User]' in header  # FEI signature

        Instrument-specific:

        >>> def supports(self, context: ExtractionContext) -> bool:
        ...     return (context.instrument is not None and
        ...             context.instrument.name.startswith("FEI-Quanta"))
        """
        ...  # pragma: no cover

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from the file.

        CRITICAL: This method MUST follow defensive design principles:
        - Never raise exceptions - catch all errors and return minimal metadata
        - Always return a list of metadata dicts where each contains an 'nx_meta' key
        - Log errors for debugging but continue gracefully

        Return Format:
        All extractors return a list of metadata dicts. Each dict contains:
        - 'nx_meta': Required - NexusLIMS-specific metadata (dict)
        - Other keys: Optional - Raw metadata extracted from the file

        Single-signal files return a list with one element. Multi-signal files return
        a list with one element per signal. This consistent list-based approach allows
        the Activity layer to expand multi-signal files into multiple datasets.

        Each 'nx_meta' dict should contain:
        - 'Creation Time': ISO format datetime string
        - 'Data Type': Human-readable data type (e.g., "STEM_Imaging")
        - 'DatasetType': Dataset type per schema (e.g., "Image", "Spectrum")
        - 'Data Dimensions': String like "(1024, 1024)" or "(12, 1024, 1024)"
        - 'Instrument ID': Instrument PID from database
        - 'warnings': List of warning messages (optional)

        Parameters
        ----------
        context
            Context containing file path, instrument info, etc.
            For multi-signal files, signal_index indicates which signal to process.
            If None, extractors may return all signals or the first signal.

        Returns
        -------
        list[dict]
            List of metadata dicts (one per signal). Each dict contains 'nx_meta'
            key with NexusLIMS-specific metadata, plus optional raw metadata keys.

        Examples
        --------
        Single-signal extraction:

        >>> def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        ...     try:
        ...         metadata = [{"nx_meta": {
        ...             "Creation Time": "2024-01-15T10:30:00-05:00",
        ...             "Data Type": "STEM_Imaging",
        ...             "DatasetType": "Image",
        ...             "Data Dimensions": "(1024, 1024)",
        ...             "Instrument ID": "643-Titan"
        ...         }}]
        ...         return metadata
        ...     except Exception as e:
        ...         logger.error(f"Extraction failed: {e}")
        ...         return self._minimal_metadata(context)

        Multi-signal extraction:

        >>> def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        ...     try:
        ...         # For a file with 2 signals
        ...         return [
        ...             {"nx_meta": {
        ...                 "Creation Time": "2024-01-15T10:30:00-05:00",
        ...                 "Data Type": "STEM_Imaging", ...}},
        ...             {"nx_meta": {
        ...                 "Creation Time": "2024-01-15T10:30:00-05:00",
        ...                 "Data Type": "EDS_Spectrum", ...}}
        ...         ]
        ...     except Exception as e:
        ...         logger.error(f"Extraction failed: {e}")
        ...         return self._minimal_metadata(context)

        Minimal metadata on error:

        >>> def _minimal_metadata(self, context: ExtractionContext) -> list[dict]:
        ...     return [{
        ...         "nx_meta": {
        ...             "DatasetType": "Unknown",
        ...             "Data Type": "Unknown",
        ...             "Creation Time": context.file_path.stat().st_mtime,
        ...             "Instrument ID": None,
        ...             "warnings": ["Extraction failed"]
        ...         }
        ...     }]
        """
        ...  # pragma: no cover


class PreviewGenerator(Protocol):
    """
    Protocol for thumbnail/preview image generation.

    Preview generators are separate from extractors to allow:
    - Different preview strategies for the same file type
    - Reusable preview logic across extractors
    - Batch preview generation independent of extraction

    Like BaseExtractor, this is a Protocol (structural subtype).

    Attributes
    ----------
    name : str
        Unique identifier for this generator
    priority : int
        Priority (same conventions as BaseExtractor)
    supported_extensions : set[str] | None
        File extensions this generator supports (without dots).
        Set to None for wildcard generators that support all files.
        Empty set means no extensions are directly supported (content sniffing only).

    Examples
    --------
    >>> class HyperSpyPreview:
    ...     \"\"\"Generate previews using HyperSpy.\"\"\"
    ...
    ...     name = "hyperspy_preview"
    ...     priority = 100
    ...
    ...     def supports(self, context: ExtractionContext) -> bool:
    ...         ext = context.file_path.suffix.lower().lstrip('.')
    ...         return ext in ('dm3', 'dm4', 'ser')
    ...
    ...     def generate(self, context: ExtractionContext,
    ...                  output_path: Path) -> bool:
    ...         # Preview generation logic
    ...         return True
    """

    name: str
    priority: int
    supported_extensions: set[str] | None

    def supports(self, context: ExtractionContext) -> bool:
        """
        Determine if this generator can create a preview for the given file.

        Parameters
        ----------
        context
            Context containing file path, instrument info, etc.

        Returns
        -------
        bool
            True if this generator can handle this file
        """
        ...  # pragma: no cover

    def generate(self, context: ExtractionContext, output_path: Path) -> bool:
        """
        Generate a thumbnail preview and save to output_path.

        This method should:
        - Create a square thumbnail (typically 500x500 pixels)
        - Save to output_path as PNG
        - Return True on success, False on failure
        - Never raise exceptions (catch all and return False)

        Parameters
        ----------
        context
            Context containing file path, instrument info, etc.
        output_path
            Where to save the generated preview PNG

        Returns
        -------
        bool
            True if preview was successfully generated, False otherwise

        Examples
        --------
        >>> def generate(self, context: ExtractionContext,
        ...              output_path: Path) -> bool:
        ...     try:
        ...         # Create thumbnail
        ...         output_path.parent.mkdir(parents=True, exist_ok=True)
        ...         # ... generation logic ...
        ...         return True
        ...     except Exception as e:
        ...         logger.error(f"Preview generation failed: {e}")
        ...         return False
        """
        ...  # pragma: no cover


@dataclass
class InstrumentProfile:
    """
    Instrument-specific customization profile.

    Decouples instrument-specific logic from extractors, making it easy to add
    custom behavior for specific microscopes without modifying extractor code.

    This is the CRITICAL component for extensibility - each NexusLIMS installation
    has unique instruments, and this system makes it trivial to add customizations.

    Attributes
    ----------
    instrument_id
        Instrument identifier (e.g., "FEI-Titan-STEM-630901")
    parsers
        Custom metadata parsing functions for this instrument.
        Keys are parser names, values are callables.
    transformations
        Metadata transformation functions applied after extraction.
        Keys are transform names, values are callables.
    extractor_overrides
        Force specific extractors for certain extensions.
        Keys are file extensions, values are extractor names.
    static_metadata
        Metadata to inject for all files from this instrument.
        Keys are metadata paths, values are static values.

    Examples
    --------
    Creating a custom profile for FEI Titan STEM:

    >>> def parse_643_titan_microscope(metadata: dict) -> dict:
    ...     # Custom parsing logic
    ...     return metadata
    >>>
    >>> titan_stem_profile = InstrumentProfile(
    ...     instrument_id="FEI-Titan-STEM-630901",
    ...     parsers={
    ...         "microscope_info": parse_643_titan_microscope,
    ...     },
    ...     static_metadata={
    ...         "nx_meta.Facility": "Nexus Facility",
    ...         "nx_meta.Building": "Bldg. 1",
    ...     }
    ... )

    Using extractor overrides:

    >>> zeiss_profile = InstrumentProfile(
    ...     instrument_id="Zeiss-Merlin-12345",
    ...     extractor_overrides={
    ...         "tif": "zeiss_tif_extractor",  # Use Zeiss-specific TIF extractor
    ...     }
    ... )
    """

    instrument_id: str
    parsers: dict[str, Callable] = field(default_factory=dict)
    transformations: dict[str, Callable] = field(default_factory=dict)
    extractor_overrides: dict[str, str] = field(default_factory=dict)
    static_metadata: dict[str, Any] = field(default_factory=dict)
