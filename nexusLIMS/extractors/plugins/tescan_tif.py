# ruff: noqa: N817, FBT003
"""Tescan (P)FIB/SEM TIFF extractor plugin."""

import configparser
import contextlib
import io
import logging
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.base import FieldDefinition as FD
from nexusLIMS.extractors.utils import _set_instr_name_and_time
from nexusLIMS.schemas.units import ureg
from nexusLIMS.utils import set_nested_dict_value, sort_dict

TESCAN_TIFF_TAG = 50431
"""
TIFF tag ID where Tescan stores INI-style metadata in TIFF files.
The tag contains holds instrument configuration, beam parameters, stage position,
detector settings, and other acquisition metadata.
"""

_MAX_ASCII_VALUE = 128
"""Maximum value for ASCII characters. Used to filter non-ASCII binary data."""

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


def _get_source_unit(target_unit: str) -> str:  # noqa: PLR0911
    """
    Determine the source unit (in SI base units) for a given target unit.

    Tescan stores metadata in SI base units (meters, volts, amperes, seconds, etc.).
    This function maps the target unit to the appropriate source unit.

    Parameters
    ----------
    target_unit
        The target Pint unit name (e.g., 'kilovolt', 'nanometer', 'microsecond')

    Returns
    -------
    str
        The source unit in SI base units
    """
    # Map unit dimensions to SI base units
    # Voltage units
    if target_unit in ("volt", "kilovolt", "millivolt"):
        return "volt"
    # Length units
    if target_unit in ("meter", "millimeter", "micrometer", "nanometer"):
        return "meter"
    # Current units
    if target_unit in ("ampere", "microampere", "milliampere", "picoampere"):
        return "ampere"
    # Time units
    if target_unit in ("second", "millisecond", "microsecond", "nanosecond"):
        return "second"
    # Pressure units
    if target_unit in ("pascal", "millipascal", "kilopascal", "megapascal"):
        return "pascal"
    # Angle units
    if target_unit in ("degree", "radian"):
        return "degree"  # Tescan uses degrees
    # Magnification units
    if target_unit == "kiloX":
        return (
            "dimensionless"  # Tescan stores magnification as raw count (e.g., 160000x)
        )

    # Default: return the target unit itself
    return target_unit


class TescanTiffExtractor:
    """
    Extractor for Tescan FIB/SEM TIFF files.

    This extractor handles metadata extraction from .tif files saved by
    Tescan FIB and SEM instruments (e.g., AMBER X). The extractor uses
    a two-tier strategy:

    1. Primary: Look for sidecar .hdr file with full metadata in INI format
    2. Fallback: Extract basic metadata from TIFF tags if no .hdr file exists

    The .hdr file contains comprehensive acquisition parameters in two sections:
    [MAIN] and [SEM], which are parsed using Python's configparser.
    """

    name = "tescan_tif_extractor"
    priority = 150
    supported_extensions: ClassVar = {"tif", "tiff"}

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Performs content sniffing to verify this is a Tescan TIFF file by:
        1. Checking file extension (.tif or .tiff)
        2. Looking for either a sidecar .hdr file or Tescan-specific TIFF tags

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if this appears to be a Tescan TIFF file
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        if extension not in {"tif", "tiff"}:
            return False

        # Check for sidecar HDR file
        hdr_file = self._find_hdr_file(context.file_path)
        if hdr_file is not None and self._is_tescan_hdr(hdr_file):
            return True

        # Fallback: check TIFF tags for Tescan signature
        try:
            with Image.open(context.file_path) as img:
                # Check for TESCAN in Make tag (271) or Software tag (305)
                make = img.tag_v2.get(271, "")
                software = img.tag_v2.get(305, "")
                if "TESCAN" in str(make).upper() or "TESCAN" in str(software).upper():
                    return True
                # check for custom Tescan metadata tag
                tescan_metadata = img.tag_v2.get(TESCAN_TIFF_TAG, "")
                if tescan_metadata != "":
                    return True
        except Exception as e:
            _logger.debug(
                "Could not read TIFF tags from %s: %s",
                context.file_path,
                e,
            )
            return False

        return False

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from a Tescan FIB/SEM TIFF file.

        Returns the metadata (as a list of dictionaries) from a .tif file saved by
        Tescan instruments. Uses a three-tier extraction strategy:
        1. Try to parse embedded HDR metadata from TIFF Tag 50431
        2. If that fails, look for a sidecar .hdr file
        3. Always extract basic TIFF tags as well

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        list[dict]
            List containing a single metadata dict with 'nx_meta' key
        """
        filename = context.file_path
        _logger.debug("Extracting metadata from Tescan TIFF file: %s", filename)

        mdict = {"nx_meta": {}}
        # Assume all datasets coming from Tescan are SEM Images, originally
        mdict["nx_meta"]["DatasetType"] = "Image"
        mdict["nx_meta"]["Data Type"] = "SEM_Imaging"

        _set_instr_name_and_time(mdict, filename)

        hdr_parsed = False

        # Strategy 1: Try to parse embedded HDR metadata from TIFF tag 50431
        try:
            embedded_metadata = self._extract_embedded_hdr(filename)
            if embedded_metadata:
                mdict.update(embedded_metadata)
                mdict = self._parse_nx_meta(mdict)
                hdr_parsed = True
                _logger.debug("Successfully parsed embedded HDR from TIFF tag")
        except Exception as e:
            _logger.debug("Could not parse embedded HDR metadata: %s", e)

        # Strategy 2: If embedded parsing failed, try sidecar HDR file
        if not hdr_parsed:
            hdr_file = self._find_hdr_file(filename)
            if hdr_file is not None and self._is_tescan_hdr(hdr_file):
                try:
                    hdr_metadata = self._read_hdr_metadata(hdr_file)
                    mdict.update(hdr_metadata)
                    mdict = self._parse_nx_meta(mdict)
                    hdr_parsed = True
                    _logger.debug("Successfully parsed sidecar HDR file")
                except Exception as e:
                    _logger.warning(
                        "Failed to parse HDR file %s: %s",
                        hdr_file,
                        e,
                    )

        # Strategy 3: Always extract basic TIFF tags (may supplement or override)
        self._extract_from_tiff_tags(filename, mdict)

        # Sort the nx_meta dictionary (recursively) for nicer display
        mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

        return [mdict]

    def _find_hdr_file(self, tiff_path: Path) -> Path | None:
        """
        Find the sidecar .hdr file for a given TIFF file.

        Parameters
        ----------
        tiff_path
            Path to the TIFF file

        Returns
        -------
        Path or None
            Path to the .hdr file if it exists, None otherwise
        """
        hdr_path = tiff_path.with_suffix(".hdr")
        if hdr_path.exists():
            return hdr_path
        return None

    def _is_tescan_hdr(self, hdr_path: Path) -> bool:
        """
        Verify that an HDR file is a Tescan format file.

        Checks for the presence of [MAIN] and [SEM] sections which are
        characteristic of Tescan HDR files.

        Parameters
        ----------
        hdr_path
            Path to the .hdr file

        Returns
        -------
        bool
            True if this appears to be a Tescan HDR file
        """
        try:
            with hdr_path.open("r", encoding="utf-8", errors="ignore") as f:
                content = f.read(500)  # Read first 500 chars
                # Look for characteristic Tescan sections
                return "[MAIN]" in content or "Device=TESCAN" in content
        except Exception as e:
            _logger.debug("Could not verify HDR file %s: %s", hdr_path, e)
            return False

    def _extract_embedded_hdr(
        self, tiff_path: Path
    ) -> dict[str, dict[str, str]] | None:
        """
        Extract embedded HDR metadata from TIFF Tag TESCAN_TIFF_TAG.

        Tescan embeds the complete HDR metadata in TIFF tag TESCAN_TIFF_TAG as a
        binary blob containing the INI-formatted text. The tag may contain binary
        garbage at the beginning before the actual metadata starts.

        Parameters
        ----------
        tiff_path
            Path to the TIFF file

        Returns
        -------
        dict or None
            Dictionary with section names as keys and key-value dicts as values,
            or None if tag is not present or cannot be parsed
        """
        try:
            with Image.open(tiff_path) as img:
                metadata_tag = img.tag_v2.get(TESCAN_TIFF_TAG)
                if metadata_tag is None:
                    return None

                # Convert tag to bytes
                metadata_bytes = self._tag_to_bytes(metadata_tag)

                # Extract metadata string from binary data
                metadata_str = self._extract_metadata_string(metadata_bytes)

                # Clean up non-printable characters
                metadata_str = self._clean_metadata_string(metadata_str)

                # Add section headers if missing
                metadata_str = self._add_section_headers_if_needed(metadata_str)

                # Parse as INI format
                return self._parse_hdr_string(metadata_str)

        except Exception as e:
            _logger.debug("Failed to extract embedded HDR from tag 50431: %s", e)
            return None

    def _tag_to_bytes(self, metadata_tag: Any) -> bytes:
        """Convert TIFF tag data to bytes.

        Parameters
        ----------
        metadata_tag
            Tag data in various formats (bytes, str, etc.)

        Returns
        -------
        bytes
            Converted bytes

        Raises
        ------
        TypeError
            If tag data is not bytes or str
        """
        if isinstance(metadata_tag, bytes):
            return metadata_tag
        if isinstance(metadata_tag, str):
            return metadata_tag.encode("utf-8")
        msg = f"Unsupported metadata tag type: {type(metadata_tag)}"
        raise TypeError(msg)

    def _extract_metadata_string(self, metadata_bytes: bytes) -> str:
        """Extract metadata string from binary data by removing garbage.

        The tag may contain binary garbage at the beginning. This method looks
        for known keys to find the start of actual metadata.

        Parameters
        ----------
        metadata_bytes
            Raw binary metadata from TIFF tag

        Returns
        -------
        str
            Cleaned metadata string
        """
        # Look for the start of metadata by searching for known keys
        search_keys = [b"[MAIN]", b"AccFrames=", b"AccType=", b"Company=", b"Date="]
        for search_key in search_keys:
            pos = metadata_bytes.find(search_key)
            if pos >= 0:
                metadata_bytes = metadata_bytes[pos:]
                return metadata_bytes.replace(b"\x00", b"").decode(
                    "utf-8", errors="ignore"
                )

        # Fallback: decode whole thing
        return metadata_bytes.replace(b"\x00", b"").decode("utf-8", errors="ignore")

    def _clean_metadata_string(self, metadata_str: str) -> str:
        """Remove non-printable binary characters from metadata string.

        Parameters
        ----------
        metadata_str
            Metadata string that may contain non-printable characters

        Returns
        -------
        str
            Cleaned metadata string
        """
        return "".join(
            c
            for c in metadata_str
            if ord(c) < _MAX_ASCII_VALUE and (c.isprintable() or c in "\n\r\t")
        )

    def _add_section_headers_if_needed(self, metadata_str: str) -> str:
        """Add [MAIN] and [SEM] section headers if missing.

        Tescan's embedded metadata doesn't include section headers, so this
        method detects where the SEM section starts and inserts headers.

        Parameters
        ----------
        metadata_str
            Metadata string potentially without section headers

        Returns
        -------
        str
            Metadata string with section headers
        """
        if "[MAIN]" in metadata_str or "[SEM]" in metadata_str:
            return metadata_str

        # Find where SEM section starts by looking for known SEM keys
        sem_keys = [
            "AcceleratorVoltage=",
            "ApertureDiameter=",
            "ApertureOptimization=",
            "ChamberPressure=",
            "CrossFree=",
            "HV=",
        ]
        sem_start_pos = self._find_sem_section_start(metadata_str, sem_keys)

        # Insert section headers at line boundaries
        if sem_start_pos < len(metadata_str):
            line_start = metadata_str.rfind("\n", 0, sem_start_pos)
            if line_start < 0:
                line_start = 0
            else:
                line_start += 1  # Move past the \n
            return (
                "[MAIN]\n"
                + metadata_str[:line_start]
                + "[SEM]\n"
                + metadata_str[line_start:]
            )

        # No SEM section found
        return "[MAIN]\n" + metadata_str

    def _find_sem_section_start(self, metadata_str: str, sem_keys: list[str]) -> int:
        """Find the position where SEM section starts.

        Parameters
        ----------
        metadata_str
            Metadata string to search
        sem_keys
            List of keys that typically appear in SEM section

        Returns
        -------
        int
            Position of first SEM key, or length of string if not found
        """
        sem_start_pos = len(metadata_str)
        for sem_key in sem_keys:
            pos = metadata_str.find(sem_key)
            if pos >= 0 and pos < sem_start_pos:
                sem_start_pos = pos
        return sem_start_pos

    def _parse_hdr_string(self, hdr_string: str) -> dict[str, dict[str, str]]:
        """
        Parse HDR metadata from a string in INI format.

        Parameters
        ----------
        hdr_string
            HDR metadata as a string in INI format

        Returns
        -------
        dict
            Dictionary with section names as keys and key-value dicts as values
        """
        # Normalize line endings
        hdr_string = hdr_string.replace("\r\n", "\n").replace("\r", "\n")

        # Parse with ConfigParser
        config = configparser.ConfigParser()
        # Make ConfigParser respect upper/lowercase values
        config.optionxform = lambda option: option

        # Use StringIO to read from string
        buf = io.StringIO(hdr_string)
        config.read_file(buf)

        metadata = {}
        for section in config.sections():
            metadata[section] = dict(config.items(section))

        return metadata

    def _read_hdr_metadata(self, hdr_path: Path) -> dict[str, dict[str, str]]:
        """
        Read and parse a Tescan .hdr file.

        The .hdr file is in INI format with sections like [MAIN] and [SEM].

        Parameters
        ----------
        hdr_path
            Path to the .hdr file

        Returns
        -------
        dict
            Dictionary with section names as keys and key-value dicts as values
        """
        with hdr_path.open("r", encoding="utf-8", errors="ignore") as f:
            hdr_string = f.read()

        return self._parse_hdr_string(hdr_string)

    def _extract_from_tiff_tags(self, filename: Path, mdict: dict) -> None:
        """
        Extract basic metadata from TIFF tags.

        This supplements metadata from HDR files with standard TIFF tags.
        Only adds fields that haven't already been set by HDR parsing.
        Updates mdict in place.

        Parameters
        ----------
        filename
            Path to the TIFF file
        mdict
            Metadata dictionary to update
        """
        try:
            with Image.open(filename) as img:
                # Extract standard TIFF tags
                # 271 = Make
                # 272 = Model
                # 305 = Software
                # 306 = DateTime
                # 315 = Artist (username)

                # Only add Make if not already present
                if "Make" not in mdict["nx_meta"]:
                    make = img.tag_v2.get(271)
                    if make:
                        mdict["nx_meta"]["Make"] = make

                # Only add Model if not already present
                if "Model" not in mdict["nx_meta"]:
                    model = img.tag_v2.get(272)
                    if model:
                        mdict["nx_meta"]["Model"] = model

                # Only add Software Version if not already present
                if "Software Version" not in mdict["nx_meta"]:
                    software = img.tag_v2.get(305)
                    if software:
                        mdict["nx_meta"]["Software Version"] = software

                # Always add TIFF DateTime as supplemental info
                datetime_str = img.tag_v2.get(306)
                if datetime_str:
                    mdict["nx_meta"]["TIFF DateTime"] = datetime_str

                # Only add Operator from Artist tag if not already present
                if "Operator" not in mdict["nx_meta"]:
                    artist = img.tag_v2.get(315)
                    if artist:
                        mdict["nx_meta"]["Operator"] = artist

                # Only add dimensions if not already present
                if "Data Dimensions" not in mdict["nx_meta"]:
                    width = img.tag_v2.get(256)  # ImageWidth
                    height = img.tag_v2.get(257)  # ImageLength
                    if width and height:
                        mdict["nx_meta"]["Data Dimensions"] = str((width, height))

        except Exception as e:
            _logger.warning("Failed to extract TIFF tags from %s: %s", filename, e)
            mdict["nx_meta"]["Extractor Warnings"] = f"Failed to extract TIFF tags: {e}"

    def _parse_nx_meta(self, mdict: dict) -> dict:  # noqa: PLR0912
        """
        Parse metadata into NexusLIMS format.

        Extracts important metadata from the [MAIN] and [SEM] sections
        of the HDR file and places them in standardized locations under
        the nx_meta key.

        Parameters
        ----------
        mdict
            Metadata dictionary with [MAIN] and [SEM] sections

        Returns
        -------
        dict
            Updated metadata dictionary with parsed nx_meta fields
        """
        # Initialize warnings list
        if "warnings" not in mdict["nx_meta"]:
            mdict["nx_meta"]["warnings"] = []

        main_section = mdict.get("MAIN", {})
        sem_section = mdict.get("SEM", {})

        # Field definitions using FD NamedTuple
        # Format:
        #   FD(section, source_key, output_key, factor, is_string, unit)  # noqa: ERA001
        # Note: factor is for legacy compatibility; unit should be the target unit name
        fields = [
            # [MAIN] section - in order as they appear in HDR file
            FD("MAIN", "AccFrames", "Accumulated Frames", 1, False),
            FD("MAIN", "AccType", "Accumulation Type", 1, True),
            FD("MAIN", "Company", "Company", 1, True),
            FD("MAIN", "Date", "Acquisition Date", 1, True),
            FD("MAIN", "Description", "Description", 1, True),
            FD("MAIN", "Device", "Device", 1, True),
            FD("MAIN", "DeviceModel", "Device Model", 1, True),
            FD("MAIN", "FullUserName", "Full User Name", 1, True),
            FD("MAIN", "ImageStripSize", "Image Strip Size", 1, False),
            FD("MAIN", "Magnification", "Magnification", 1, False, unit="kiloX"),
            FD("MAIN", "MagnificationReference", "Magnification Reference", 1, False),
            FD("MAIN", "OrigFileName", "Original Filename", 1, True),
            FD("MAIN", "PixelSizeX", "Pixel Width", 1, False, unit="nanometer"),
            FD("MAIN", "PixelSizeY", "Pixel Height", 1, False, unit="nanometer"),
            FD("MAIN", "SerialNumber", "Serial Number", 1, True),
            FD("MAIN", "Sign", "Sign", 1, True),
            FD("MAIN", "SoftwareVersion", "Software Version", 1, True),
            FD("MAIN", "Time", "Acquisition Time", 1, True),
            FD("MAIN", "UserName", "User Name", 1, True),
            FD("MAIN", "ViewFieldsCountX", "View Fields Count X", 1, False),
            FD("MAIN", "ViewFieldsCountY", "View Fields Count Y", 1, False),
            # [SEM] section - in order as they appear in HDR file
            FD(
                "SEM",
                "AcceleratorVoltage",
                "Accelerator Voltage",
                1,
                False,
                unit="kilovolt",
            ),
            FD(
                "SEM",
                "ApertureDiameter",
                "Aperture Diameter",
                1,
                False,
                unit="micrometer",
            ),
            FD("SEM", "ApertureOptimization", "Aperture Optimization", 1, False),
            FD(
                "SEM",
                "ChamberPressure",
                "Chamber Pressure",
                1,
                False,
                unit="millipascal",
            ),
            FD("SEM", "CrossFree", "Cross Free", 1, False),
            FD(
                "SEM",
                "CrossSectionShiftX",
                "Cross Section Shift X",
                1,
                False,
                unit="micrometer",
            ),
            FD(
                "SEM",
                "CrossSectionShiftY",
                "Cross Section Shift Y",
                1,
                False,
                unit="micrometer",
            ),
            FD("SEM", "DepthOfFocus", "Depth of Focus", 1, False, unit="micrometer"),
            FD("SEM", "Detector", "Detector Name", 1, True),
            FD("SEM", "Detector0", "Detector 0", 1, True),
            FD("SEM", "Detector0FlatField", "Detector 0 Flat Field", 1, False),
            FD("SEM", "Detector0Gain", "Detector 0 Gain", 1, False),
            FD("SEM", "Detector0Offset", "Detector 0 Offset", 1, False),
            FD("SEM", "DwellTime", "Pixel Dwell Time", 1, False, unit="microsecond"),
            FD(
                "SEM",
                "EmissionCurrent",
                "Emission Current",
                1,
                False,
                unit="microampere",
            ),
            FD("SEM", "Gun", "Gun Type", 1, True),
            FD("SEM", "GunShiftX", "Gun Shift X", 1, False),
            FD("SEM", "GunShiftY", "Gun Shift Y", 1, False),
            FD("SEM", "GunTiltX", "Gun Tilt X", 1, False),
            FD("SEM", "GunTiltY", "Gun Tilt Y", 1, False),
            FD("SEM", "HV", "HV Voltage", 1, False, unit="kilovolt"),
            FD("SEM", "IMLCenteringX", "IML Centering X", 1, False),
            FD("SEM", "IMLCenteringY", "IML Centering Y", 1, False),
            FD("SEM", "ImageShiftX", "Image Shift X", 1, False, unit="meter"),
            FD("SEM", "ImageShiftY", "Image Shift Y", 1, False, unit="meter"),
            FD("SEM", "InjectedGas", "Injected Gas", 1, True),
            FD("SEM", "LUTGamma", "LUT Gamma", 1, False),
            FD("SEM", "LUTMaximum", "LUT Maximum", 1, False),
            FD("SEM", "LUTMinimum", "LUT Minimum", 1, False),
            FD("SEM", "MTDGrid", "MTD Grid", 1, False, unit="kilovolt"),
            FD("SEM", "MTDScintillator", "MTD Scintillator", 1, False, unit="kilovolt"),
            FD("SEM", "OBJCenteringX", "OBJ Centering X", 1, False),
            FD("SEM", "OBJCenteringY", "OBJ Centering Y", 1, False),
            FD("SEM", "OBJPreCenteringX", "OBJ Pre-Centering X", 1, False),
            FD("SEM", "OBJPreCenteringY", "OBJ Pre-Centering Y", 1, False),
            FD("SEM", "PotentialMode", "Potential Mode", 1, True),
            FD(
                "SEM",
                "PredictedBeamCurrent",
                "Predicted Beam Current",
                1,
                False,
                "picoampere",
            ),
            FD("SEM", "PrimaryDetectorGain", "Primary Detector Gain", 1, False),
            FD("SEM", "PrimaryDetectorOffset", "Primary Detector Offset", 1, False),
            FD("SEM", "SampleVoltage", "Sample Voltage", 1, False, unit="volt"),
            FD("SEM", "ScanID", "Scan ID", 1, False),
            FD("SEM", "ScanMode", "Scan Mode", 1, True),
            FD("SEM", "ScanRotation", "Scan Rotation", 1, False, unit="degree"),
            FD("SEM", "ScanSpeed", "Scan Speed", 1, False),
            FD("SEM", "SessionID", "Session ID", 1, True),
            FD(
                "SEM",
                "SpecimenCurrent",
                "Specimen Current",
                1,
                False,
                unit="picoampere",
            ),
            FD("SEM", "SpotSize", "Spot Size", 1, False, unit="nanometer"),
            FD(
                "SEM",
                "StageRotation",
                ["Stage Position", "Rotation"],
                1,
                False,
                "degree",
            ),
            FD("SEM", "StageTilt", ["Stage Position", "Tilt"], 1, False, unit="degree"),
            FD("SEM", "StageX", ["Stage Position", "X"], 1, False, unit="meter"),
            FD("SEM", "StageY", ["Stage Position", "Y"], 1, False, unit="meter"),
            FD("SEM", "StageZ", ["Stage Position", "Z"], 1, False, unit="meter"),
            FD("SEM", "StigmatorX", "Stigmator X Value", 1, False),
            FD("SEM", "StigmatorY", "Stigmator Y Value", 1, False),
            FD(
                "SEM",
                "SymmetrizationVoltage",
                "Symmetrization Voltage",
                1,
                False,
                "kilovolt",
            ),
            FD("SEM", "SyncMains", "Sync to Mains", 1, True),
            FD("SEM", "TiltCorrection", "Tilt Correction", 1, False),
            FD("SEM", "TubeVoltage", "Tube Voltage", 1, False, unit="kilovolt"),
            FD(
                "SEM",
                "VirtualObserverDistance",
                "Virtual Observer Distance",
                1,
                False,
                "millimeter",
            ),
            FD("SEM", "WD", "Working Distance", 1, False, unit="millimeter"),
        ]

        # Extract standard fields
        for field in fields:
            section = main_section if field.section == "MAIN" else sem_section
            value = section.get(field.source_key)

            # Try fallback keys for some fields
            if value is None and field.source_key == "HV":
                value = sem_section.get("AcceleratorVoltage")
            elif value is None and field.source_key == "Detector0Gain":
                value = sem_section.get("PrimaryDetectorGain")
            elif value is None and field.source_key == "Detector0Offset":
                value = sem_section.get("PrimaryDetectorOffset")

            if value:
                if field.is_string:
                    # Handle nested dict paths vs flat keys
                    # (impossible to test with existing metadata structure,
                    # so exclude from coverage)
                    if isinstance(field.output_key, list):  # pragma: no cover
                        set_nested_dict_value(
                            mdict, ["nx_meta", *field.output_key], value
                        )
                    else:
                        mdict["nx_meta"][field.output_key] = value
                else:
                    with contextlib.suppress(ValueError):
                        # Convert to float first
                        float_val = float(value)

                        # Skip if suppress_zero is True and value is zero
                        if field.suppress_zero and float_val == 0.0:
                            continue

                        # Create Pint Quantity if unit is specified
                        if field.unit:
                            # Source data is in base SI units (meters, volts, amperes,
                            # seconds). Create Quantity from source value, then convert
                            # to target unit. Determine source unit based on target unit
                            # type
                            source_unit = _get_source_unit(field.unit)
                            quantity = ureg.Quantity(float_val, source_unit).to(
                                field.unit
                            )

                            if isinstance(field.output_key, list):
                                set_nested_dict_value(
                                    mdict, ["nx_meta", *field.output_key], quantity
                                )
                            else:
                                mdict["nx_meta"][field.output_key] = quantity
                        # No unit specified, just store as float
                        elif isinstance(field.output_key, list):
                            set_nested_dict_value(
                                mdict, ["nx_meta", *field.output_key], float_val
                            )
                        else:
                            mdict["nx_meta"][field.output_key] = float_val

        # Handle user information (prefer FullUserName over UserName)
        full_username = main_section.get("FullUserName")
        username = main_section.get("UserName")
        if full_username or username:
            mdict["nx_meta"]["Operator"] = full_username or username
            mdict["nx_meta"]["warnings"].append(["Operator"])

        return mdict
