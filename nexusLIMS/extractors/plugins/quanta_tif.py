# ruff: noqa: N817, FBT001, FBT003
"""FEI/Thermo Fisher TIFF extractor plugin."""

import configparser
import contextlib
import io
import logging
import re
from decimal import Decimal, InvalidOperation
from math import degrees
from pathlib import Path
from typing import Any, ClassVar, Tuple

from lxml import etree
from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext, FieldDefinition
from nexusLIMS.extractors.base import FieldDefinition as FD
from nexusLIMS.extractors.utils import _set_instr_name_and_time
from nexusLIMS.instruments import get_instr_from_filepath
from nexusLIMS.utils import set_nested_dict_value, sort_dict, try_getting_dict_value

FEI_TIFF_TAG = 34682
"""
TIFF tag ID where FEI/Thermo stores metadata in TIFF files.
The tag contains INI-style metadata with sections like [User], [Beam], [Image], etc.
"""

FEI_XML_TIFF_TAG = 34683
"""
TIFF tag ID where FEI/Thermo stores XML metadata in TIFF files (if present).
This tag contains supplementary XML metadata that may be embedded after
the standard INI metadata.
"""

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


class QuantaTiffExtractor:
    """
    Extractor for FEI/Thermo Fisher TIFF files.

    This extractor handles metadata extraction from .tif files saved by
    FEI/Thermo Fisher FIBs and SEMs (e.g., Quanta, Helios, etc.). The extractor
    performs content sniffing to verify the file contains FEI metadata before
    attempting extraction.
    """

    name = "quanta_tif_extractor"
    priority = 100
    supported_extensions: ClassVar = {"tif", "tiff"}

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Performs content sniffing to verify this is a FEI/Thermo TIFF file by:
        1. Checking for the FEI-specific TIFF tag (34682) containing [User] or [Beam]
        2. Falling back to binary content sniffing for files with FEI metadata markers

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if this appears to be a FEI/Thermo TIFF file with metadata
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        if extension not in {"tif", "tiff"}:
            return False

        # Strategy 1: Check for FEI metadata signature using TIFF tag 34682
        try:
            with Image.open(context.file_path) as img:
                # Check for FEI custom tag
                fei_metadata = img.tag_v2.get(FEI_TIFF_TAG)
                if fei_metadata is not None:
                    # Verify the metadata starts with FEI-style markers
                    metadata_str = str(fei_metadata)
                    if "[User]" in metadata_str or "[Beam]" in metadata_str:
                        return True
        except Exception as e:
            _logger.debug(
                "Could not read TIFF tags from %s: %s",
                context.file_path,
                e,
            )

        # Strategy 2: Fallback to binary content sniffing for files that may not be
        # proper TIFF files or use different metadata storage
        try:
            with context.file_path.open(mode="rb") as f:
                content = f.read(5000)  # Read first 5KB to check for metadata markers
        except Exception as e:
            _logger.debug(
                "Could not read binary content from %s: %s",
                context.file_path,
                e,
            )
            return False
        else:
            # Check for FEI metadata markers in file
            return b"[User]" in content or b"[Beam]" in content

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a FEI/Thermo TIFF file.

        Returns the metadata (as a dictionary) from a .tif file saved by the FEI
        Quanta SEM or related instruments. Specific tags of interest are
        extracted and placed under the root-level ``nx_meta`` node.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        dict
            Metadata dictionary with 'nx_meta' key containing NexusLIMS metadata
        """
        filename = context.file_path
        _logger.debug("Extracting metadata from FEI TIFF file: %s", filename)

        mdict = {"nx_meta": {}}
        # assume all datasets coming from Quanta are Images, currently
        mdict["nx_meta"]["DatasetType"] = "Image"
        mdict["nx_meta"]["Data Type"] = "SEM_Imaging"

        _set_instr_name_and_time(mdict, filename)

        try:
            # Extract metadata from TIFF tags/binary
            metadata_str, xml_metadata = self._extract_metadata_from_tiff_tag(filename)

            if not metadata_str:
                _logger.warning(
                    "Did not find expected FEI tags in .tif file: %s", filename
                )
                mdict["nx_meta"]["Data Type"] = "Unknown"
                mdict["nx_meta"]["Extractor Warnings"] = (
                    "Did not find expected FEI tags. Could not read metadata"
                )
                mdict["nx_meta"] = sort_dict(mdict["nx_meta"])
                return mdict

            # Handle XML metadata if present
            if xml_metadata:
                mdict["FEI_XML_Metadata"] = xml_metadata

            # Fix duplicate section headers (MultiGIS issue)
            metadata_str = self._fix_duplicate_multigis_metadata_tags(metadata_str)

            # Parse INI format metadata
            mdict.update(self._parse_metadata_string(metadata_str))

            # Extract important fields to nx_meta
            mdict = self._parse_nx_meta(mdict)

        except Exception as e:
            _logger.exception("Error extracting metadata from %s", filename)
            mdict["nx_meta"]["Data Type"] = "Unknown"
            mdict["nx_meta"]["Extractor Warnings"] = f"Extraction failed: {e}"

        # sort the nx_meta dictionary (recursively) for nicer display
        mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

        return mdict

    def _extract_metadata_from_tiff_tag(self, tiff_path: Path) -> Tuple[str, dict]:
        """
        Extract metadata string from FEI TIFF tags 34682 and 34683.

        Extracts standard INI metadata from tag 34682 and XML metadata from tag 34683
        if present. Falls back to binary content sniffing if TIFF tags are not present.

        Parameters
        ----------
        tiff_path
            Path to the TIFF file

        Returns
        -------
        metadata_str
            Metadata string (INI format), or empty string if not found
        xml_metadata
            Dictionary of XML metadata if tag 34683 is present, else empty dict
        """
        metadata_str = ""
        xml_metadata = {}

        # Strategy 1: Try to extract from TIFF tags 34682 and 34683
        try:
            with Image.open(tiff_path) as img:
                # Extract standard metadata from tag 34682
                fei_metadata = img.tag_v2.get(FEI_TIFF_TAG)
                if fei_metadata is not None:
                    # Convert tag to string
                    metadata_str_val = (
                        fei_metadata
                        if isinstance(fei_metadata, str)
                        else str(fei_metadata)
                    )
                    metadata_str = self._extract_metadata_string(
                        metadata_str_val.encode()
                    )

                # Extract XML metadata from tag 34683 if present
                xml_metadata_tag = img.tag_v2.get(FEI_XML_TIFF_TAG)
                if xml_metadata_tag is not None:
                    xml_metadata_str = (
                        xml_metadata_tag
                        if isinstance(xml_metadata_tag, str)
                        else str(xml_metadata_tag)
                    )
                    # Check if this is XML
                    if "<?xml" in xml_metadata_str:
                        try:
                            root = etree.fromstring(xml_metadata_str)
                            xml_metadata = self._xml_el_to_dict(root)
                        except Exception as e:
                            _logger.debug(
                                "Failed to parse XML from TIFF tag 34683: %s", e
                            )
        except Exception as e:
            _logger.debug("Failed to extract FEI metadata from TIFF tags: %s", e)

        # If we got metadata from TIFF tags, return it
        if metadata_str:
            return metadata_str, xml_metadata

        # Strategy 2: Fallback to binary content extraction for files where
        # metadata might not be in a standard TIFF tag
        try:
            with tiff_path.open(mode="rb") as f:
                content = f.read()
            user_idx = content.find(b"[User]")
            if user_idx != -1:
                # Extract metadata string from binary
                metadata_str_raw = self._extract_metadata_string(content[user_idx:])
                # Check for XML in the binary content
                metadata_str_clean, xml_meta = self._detect_and_process_xml_metadata(
                    metadata_str_raw
                )
                return metadata_str_clean, xml_meta
        except Exception as e:
            _logger.debug("Failed to extract FEI metadata from binary content: %s", e)

        return "", {}

    def _extract_metadata_string(self, metadata_bytes: bytes) -> str:
        """
        Extract metadata string from binary data.

        Removes null bytes and normalizes line endings from the binary
        metadata extracted from the TIFF file.

        Parameters
        ----------
        metadata_bytes
            Raw binary metadata from the TIFF file

        Returns
        -------
        str
            Cleaned metadata string
        """
        # remove any null bytes since they break the extractor
        metadata_bytes = metadata_bytes.replace(b"\x00", b"")
        metadata_str = metadata_bytes.decode(errors="ignore")
        # normalize line endings
        return metadata_str.replace("\r\n", "\n").replace("\r", "\n")

    def _detect_and_process_xml_metadata(
        self,
        metadata_str: str,
    ) -> Tuple[str, dict]:
        """
        Find and (if necessary) parse XML metadata in a Thermo Fisher FIB/SEM TIF file.

        Some Thermo Fisher FIB/SEM files have additional metadata embedded as XML
        at the end of the TIF file, which cannot be handled by the ConfigParser.
        This method will detect, parse, and remove the XML from the metadata if present.

        Parameters
        ----------
        metadata_str
            The metadata at the end of the TIF file as a string. May or may not include
            an XML section (this depends on the version of the Thermo software that
            saved the image).

        Returns
        -------
        metadata_str
            The originally provided metadata as a string, but with the XML portion
            removed if it was present

        xml_metadata
            A dictionary containing the metadata that was present in the XML portion.
            Will be an empty dictionary if there was no XML.
        """
        xml_regex = re.compile(r'<\?xml version=".+"\?>')
        regex_match = xml_regex.search(metadata_str)
        if regex_match:
            # there is an xml declaration in the metadata of this file, so parse it:
            xml_str = metadata_str[regex_match.span()[0] :]
            metadata_str = metadata_str[: regex_match.span()[0]]
            root = etree.fromstring(xml_str)
            return metadata_str, self._xml_el_to_dict(root)

        return metadata_str, {}

    @staticmethod
    def _xml_el_to_dict(node: etree.ElementBase) -> dict:
        """
        Convert an lxml.etree node tree into a dict.

        This is used to transform the XML metadata section into a dictionary
        representation so it can be stored alongside the other metadata.

        Taken from https://stackoverflow.com/a/66103841/1435788

        Parameters
        ----------
        node
            XML element to convert

        Returns
        -------
        dict
            Dictionary representation of the XML element
        """
        result = {}

        for element in node.iterchildren():
            # Remove namespace prefix
            key = element.tag.split("}")[1] if "}" in element.tag else element.tag

            # Process element as tree element if the inner XML contains
            # non-whitespace content
            if element.text and element.text.strip():
                value = element.text
            else:
                value = QuantaTiffExtractor._xml_el_to_dict(element)
            if key in result:
                if isinstance(result[key], list):
                    result[key].append(value)  # pragma: no cover
                else:
                    tempvalue = result[key].copy()
                    result[key] = [tempvalue, value]
            else:
                result[key] = value
        return result

    @staticmethod
    def _fix_duplicate_multigis_metadata_tags(metadata_str: str) -> str:
        """
        Rename the metadata section headers to allow parsing by ConfigParser.

        Some instruments have metadata section titles like so:

            [MultiGIS]
            [MultiGISUnit1]
            [MultiGISGas1]
            [MultiGISGas2]
            [MultiGISGas3]
            [MultiGISUnit2]
            [MultiGISGas1]
            ...

        Which causes errors because ConfigParser raises a DuplicateSectionError.
        This method renames them to:

            [MultiGIS]
            [MultiGISUnit1]
            [MultiGISUnit1.MultiGISGas1]
            [MultiGISUnit1.MultiGISGas2]
            [MultiGISUnit1.MultiGISGas3]
            [MultiGISUnit2]
            [MultiGISUnit2.MultiGISGas1]
            ...

        Parameters
        ----------
        metadata_str
            Metadata string potentially with duplicate section headers

        Returns
        -------
        str
            Metadata string with unique section headers
        """
        metadata_to_return = ""
        multi_gis_section_numbers = re.findall(r"\[MultiGISUnit(\d+)\]", metadata_str)
        if multi_gis_section_numbers:
            multi_gis_unit_indices = [
                metadata_str.index(f"[MultiGISUnit{num}]")
                for num in multi_gis_section_numbers
            ]
            metadata_to_return += metadata_str[: multi_gis_unit_indices[0]]
            for i, num in enumerate(multi_gis_section_numbers):
                if i < len(multi_gis_unit_indices) - 1:
                    to_process = metadata_str[
                        multi_gis_unit_indices[i] : multi_gis_unit_indices[i + 1]
                    ]
                else:
                    to_process = metadata_str[multi_gis_unit_indices[i] :]
                multi_gis_gas_tags = re.findall(r"\[(MultiGISGas\d+)\]", to_process)
                for tag in multi_gis_gas_tags:
                    to_process = to_process.replace(tag, f"MultiGISUnit{num}.{tag}")
                metadata_to_return += to_process
        else:
            metadata_to_return = metadata_str

        return metadata_to_return

    @staticmethod
    def _parse_metadata_string(hdr_string: str) -> dict[str, dict[str, str]]:
        """
        Parse metadata from a string in INI format.

        Parameters
        ----------
        hdr_string
            Metadata as a string in INI format

        Returns
        -------
        dict
            Dictionary with section names as keys and key-value dicts as values
        """
        config = configparser.RawConfigParser()
        # Make ConfigParser respect upper/lowercase values
        config.optionxform = lambda option: option

        buf = io.StringIO(hdr_string)
        config.read_file(buf)

        metadata = {}
        for section in config.sections():
            metadata[section] = dict(config.items(section))

        return metadata

    def _build_field_definitions(self, mdict: dict) -> list[FieldDefinition]:
        """Build field definitions for metadata extraction.

        Parameters
        ----------
        mdict
            Metadata dictionary with raw extracted metadata

        Returns
        -------
        list[FieldDefinition]
            List of field definitions for extraction
        """
        beam_name = try_getting_dict_value(mdict, ["Beam", "Beam"])
        det_name = try_getting_dict_value(mdict, ["Detectors", "Name"])
        scan_name = try_getting_dict_value(mdict, ["Beam", "Scan"])

        fields = []

        # Beam section fields
        if beam_name != "not found":
            fields.extend(
                [
                    FD(
                        beam_name,
                        "EmissionCurrent",
                        "Emission Current (μA)",
                        1e6,
                        False,
                    ),
                    FD(beam_name, "HFW", "Horizontal Field Width (μm)", 1e6, False),
                    FD(beam_name, "HV", "Voltage (kV)", 1e-3, False),
                    FD(beam_name, "SourceTiltX", "Beam Tilt X", 1.0, False),
                    FD(beam_name, "SourceTiltY", "Beam Tilt Y", 1.0, False),
                    FD(beam_name, "StageR", ["Stage Position", "R"], 1.0, False),
                    FD(beam_name, "StageTa", ["Stage Position", "α"], 1.0, False),  # noqa: RUF001
                    FD(beam_name, "StageX", ["Stage Position", "X"], 1.0, False),
                    FD(beam_name, "StageY", ["Stage Position", "Y"], 1.0, False),
                    FD(beam_name, "StageZ", ["Stage Position", "Z"], 1.0, False),
                    FD(beam_name, "StigmatorX", "Stigmator X Value", 1.0, False),
                    FD(beam_name, "StigmatorY", "Stigmator Y Value", 1.0, False),
                    FD(beam_name, "VFW", "Vertical Field Width (μm)", 1e6, False),
                    FD(beam_name, "WD", "Working Distance (mm)", 1e3, False),
                    FD(
                        beam_name,
                        "BeamShiftX",
                        "Beam Shift X",
                        1.0,
                        False,
                        suppress_zero=True,
                    ),
                    FD(
                        beam_name,
                        "BeamShiftY",
                        "Beam Shift Y",
                        1.0,
                        False,
                        suppress_zero=True,
                    ),
                ]
            )

        # Scan section fields
        if scan_name != "not found":
            fields.extend(
                [
                    FD(scan_name, "Dwell", "Pixel Dwell Time (μs)", 1e6, False),
                    FD(scan_name, "FrameTime", "Total Frame Time (s)", 1.0, False),
                    FD(
                        scan_name,
                        "HorFieldsize",
                        "Horizontal Field Width (μm)",
                        1e6,
                        False,
                    ),
                    FD(
                        scan_name,
                        "VerFieldsize",
                        "Vertical Field Width (μm)",
                        1e6,
                        False,
                    ),
                    FD(scan_name, "PixelHeight", "Pixel Width (nm)", 1e9, False),
                    FD(scan_name, "PixelWidth", "Pixel Height (nm)", 1e9, False),
                ]
            )

        # Detector section fields
        if det_name != "not found":
            fields.extend(
                [
                    FD(
                        det_name,
                        "Brightness",
                        "Detector Brightness Setting",
                        1.0,
                        False,
                    ),
                    FD(det_name, "Contrast", "Detector Contrast Setting", 1.0, False),
                    FD(
                        det_name,
                        "EnhancedContrast",
                        "Detector Enhanced Contrast Setting",
                        1.0,
                        False,
                    ),
                    FD(det_name, "Signal", "Detector Signal", 1.0, False),
                    FD(det_name, "Grid", "Detector Grid Voltage (V)", 1.0, False),
                ]
            )

        # System section fields
        fields.extend(
            [
                FD("System", "Chamber", "Chamber ID", 1.0, True),
                FD("System", "Pump", "Vacuum Pump", 1.0, True),
                FD("System", "SystemType", "System Type", 1.0, True),
                FD("System", "Stage", "Stage Description", 1.0, True),
            ]
        )

        # Other fields
        fields.extend(
            [
                FD("Beam", "Spot", "Spot Size", 1.0, False),
                FD("Specimen", "Temperature", "Specimen Temperature (K)", 1.0, False),
                FD("User", "UserText", "User Text", 1.0, True),
                FD("User", "Date", "Acquisition Date", 1.0, True),
                FD("User", "Time", "Acquisition Time", 1.0, True),
                FD("Vacuum", "UserMode", "Vacuum Mode", 1.0, True),
                FD("Image", "MagnificationMode", "Magnification Mode", 1.0, False),
            ]
        )

        return fields

    def _process_standard_fields(
        self, mdict: dict, fields: list[FieldDefinition], det_name: str
    ) -> None:
        """Process standard field definitions."""
        for field in fields:
            value = try_getting_dict_value(mdict, [field.section, field.source_key])

            if value not in ("not found", ""):
                # Skip detector "Setting" if numeric (duplicate of Grid voltage)
                if field.section == det_name and field.source_key == "Setting":
                    try:
                        Decimal(value)
                        continue
                    except (ValueError, InvalidOperation):
                        pass

                if field.is_string:
                    self._set_field_value(mdict, field.output_key, value)
                else:
                    self._set_numeric_field_value(
                        mdict,
                        field.output_key,
                        value,
                        field.factor,
                        field.suppress_zero,
                    )

    def _set_field_value(self, mdict: dict, output_key: str | list, value: str) -> None:
        """Set a string field value in metadata."""
        if isinstance(output_key, list):
            set_nested_dict_value(mdict, ["nx_meta", *output_key], value)
        else:
            set_nested_dict_value(mdict, ["nx_meta", output_key], value)

    def _set_numeric_field_value(
        self,
        mdict: dict,
        output_key: str | list,
        value: str,
        factor: float,
        suppress_zero: bool,
    ) -> None:
        """Set a numeric field value with unit conversion."""
        try:
            decimal_val = Decimal(value) * Decimal(str(factor))
            float_val = float(decimal_val)
            if not suppress_zero or float_val != 0.0:
                self._set_field_value(mdict, output_key, float_val)
        except (ValueError, InvalidOperation):
            self._set_field_value(mdict, output_key, value)

    def _parse_special_cases(self, mdict: dict, beam_name: str, det_name: str) -> None:
        """Parse special case metadata fields."""
        if beam_name != "not found":
            set_nested_dict_value(mdict, ["nx_meta", "Beam Name"], beam_name)
        if det_name != "not found":
            set_nested_dict_value(mdict, ["nx_meta", "Detector Name"], det_name)

        if beam_name != "not found":
            self._parse_scan_rotation(mdict, beam_name)
            self._parse_tilt_correction(mdict, beam_name)
        self._parse_drift_correction(mdict)
        self._parse_frame_integration(mdict)
        self._parse_resolution(mdict)
        self._parse_operator(mdict)
        self._parse_chamber_pressure(mdict)
        self._parse_software_version(mdict)
        self._parse_column_type(mdict)

    def _parse_scan_rotation(self, mdict: dict, beam_name: str) -> None:
        """Parse scan rotation (radians → degrees)."""
        scan_rot_val = try_getting_dict_value(mdict, [beam_name, "ScanRotation"])
        if scan_rot_val != "not found" and Decimal(scan_rot_val) != 0:
            scan_rot_dec = Decimal(scan_rot_val)
            digits = abs(scan_rot_dec.as_tuple().exponent)
            scan_rot_val = round(degrees(scan_rot_dec), digits)
            set_nested_dict_value(mdict, ["nx_meta", "Scan Rotation (°)"], scan_rot_val)

    def _parse_tilt_correction(self, mdict: dict, beam_name: str) -> None:
        """Parse tilt correction (conditional on TiltCorrectionIsOn)."""
        tilt_corr_on = try_getting_dict_value(mdict, [beam_name, "TiltCorrectionIsOn"])
        if tilt_corr_on == "yes":
            tilt_corr_val = try_getting_dict_value(
                mdict, [beam_name, "TiltCorrectionAngle"]
            )
            if tilt_corr_val != "not found":
                set_nested_dict_value(
                    mdict,
                    ["nx_meta", "Tilt Correction Angle"],
                    float(Decimal(tilt_corr_val)),
                )

    def _parse_drift_correction(self, mdict: dict) -> None:
        """Parse drift correction (boolean)."""
        drift_val = try_getting_dict_value(mdict, ["Image", "DriftCorrected"])
        if drift_val != "not found":
            set_nested_dict_value(
                mdict, ["nx_meta", "Drift Correction Applied"], drift_val == "On"
            )

    def _parse_frame_integration(self, mdict: dict) -> None:
        """Parse frame integration (only if > 1)."""
        integrate_val = try_getting_dict_value(mdict, ["Image", "Integrate"])
        if integrate_val != "not found":
            with contextlib.suppress(ValueError):
                integrate_int = int(integrate_val)
                if integrate_int > 1:
                    set_nested_dict_value(
                        mdict, ["nx_meta", "Frames Integrated"], integrate_int
                    )

    def _parse_resolution(self, mdict: dict) -> None:
        """Parse resolution (paired X/Y as tuple string)."""
        x_val = try_getting_dict_value(mdict, ["Image", "ResolutionX"])
        y_val = try_getting_dict_value(mdict, ["Image", "ResolutionY"])
        if x_val != "not found" and y_val != "not found":
            with contextlib.suppress(ValueError):
                x_int = int(x_val)
                y_int = int(y_val)
                set_nested_dict_value(
                    mdict, ["nx_meta", "Data Dimensions"], str((x_int, y_int))
                )

    def _parse_operator(self, mdict: dict) -> None:
        """Parse operator (with warning)."""
        user_val = try_getting_dict_value(mdict, ["User", "User"])
        if user_val != "not found":
            set_nested_dict_value(mdict, ["nx_meta", "Operator"], user_val)
            mdict["nx_meta"]["warnings"].append(["Operator"])

    def _parse_chamber_pressure(self, mdict: dict) -> None:
        """Parse chamber pressure (unit depends on vacuum mode)."""
        ch_pres_val = try_getting_dict_value(mdict, ["Vacuum", "ChPressure"])
        if ch_pres_val not in ("not found", ""):
            try:
                ch_pres_decimal = Decimal(ch_pres_val)
                if (
                    try_getting_dict_value(mdict, ["nx_meta", "Vacuum Mode"])
                    == "High vacuum"
                ):
                    ch_pres_str = "Chamber Pressure (mPa)"
                    ch_pres_decimal = ch_pres_decimal * 10**3
                else:
                    ch_pres_str = "Chamber Pressure (Pa)"
                set_nested_dict_value(
                    mdict,
                    ["nx_meta", ch_pres_str],
                    float(ch_pres_decimal),
                )
            except (ValueError, InvalidOperation):
                if (
                    try_getting_dict_value(mdict, ["nx_meta", "Vacuum Mode"])
                    == "High vacuum"
                ):
                    ch_pres_str = "Chamber Pressure (mPa)"
                else:
                    ch_pres_str = "Chamber Pressure (Pa)"
                set_nested_dict_value(mdict, ["nx_meta", ch_pres_str], ch_pres_val)

    def _parse_software_version(self, mdict: dict) -> None:
        """Parse software version (aggregate Software + BuildNr)."""
        software_parts = []
        software_val = try_getting_dict_value(mdict, ["System", "Software"])
        if software_val != "not found":
            software_parts.append(software_val)
        build_val = try_getting_dict_value(mdict, ["System", "BuildNr"])
        if build_val != "not found":
            software_parts.append(f"(build {build_val})")
        if software_parts:
            set_nested_dict_value(
                mdict, ["nx_meta", "Software Version"], " ".join(software_parts)
            )

    def _parse_column_type(self, mdict: dict) -> None:
        """Parse column type (aggregate Column + Type)."""
        column_parts = []
        column_val = try_getting_dict_value(mdict, ["System", "Column"])
        if column_val != "not found":
            column_parts.append(column_val)
        type_val = try_getting_dict_value(mdict, ["System", "Type"])
        if type_val != "not found":
            column_parts.append(type_val)
        if column_parts:
            set_nested_dict_value(
                mdict, ["nx_meta", "Column Type"], " ".join(column_parts)
            )

    def _parse_nx_meta(self, mdict: dict) -> dict:
        """
        Parse metadata into NexusLIMS format.

        Parse the "important" metadata that is saved at specific places within
        the Quanta tag structure into a consistent place in the metadata dictionary.

        The metadata contained in the XML section (if present) is not parsed, since it
        appears to only contain duplicates or slightly renamed metadata values compared
        to the typical config-style section.

        Parameters
        ----------
        mdict
            A metadata dictionary with raw extracted metadata

        Returns
        -------
        dict
            The same metadata dictionary with parsed values added under the
            root-level ``nx_meta`` key
        """
        if "warnings" not in mdict["nx_meta"]:
            mdict["nx_meta"]["warnings"] = []

        beam_name = try_getting_dict_value(mdict, ["Beam", "Beam"])
        det_name = try_getting_dict_value(mdict, ["Detectors", "Name"])

        fields = self._build_field_definitions(mdict)
        self._process_standard_fields(mdict, fields, det_name)
        self._parse_special_cases(mdict, beam_name, det_name)

        return mdict


# Backward compatibility function for tests
def get_quanta_metadata(filename):
    """
    Get metadata from a Quanta TIF file.

    .. deprecated::
        This function is deprecated. Use QuantaTiffExtractor class instead.

    Parameters
    ----------
    filename : pathlib.Path
        path to a file saved in the harvested directory of the instrument

    Returns
    -------
    mdict : dict
        A description of the file's metadata.
    """
    context = ExtractionContext(
        file_path=filename, instrument=get_instr_from_filepath(filename)
    )
    return QuantaTiffExtractor().extract(context)
