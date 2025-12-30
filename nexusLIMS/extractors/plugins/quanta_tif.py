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
from nexusLIMS.extractors.utils import _set_instr_name_and_time, add_to_extensions
from nexusLIMS.instruments import get_instr_from_filepath
from nexusLIMS.schemas.units import ureg
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

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from a FEI/Thermo TIFF file.

        Returns the metadata (as a list of dictionaries) from a .tif file saved
        by the FEI Quanta SEM or related instruments. Specific tags of interest are
        extracted and placed under the root-level ``nx_meta`` node.

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
                return [mdict]

            # Handle XML metadata if present
            if xml_metadata:
                mdict["FEI_XML_Metadata"] = xml_metadata

            # Fix duplicate section headers (MultiGIS issue)
            metadata_str = self._fix_duplicate_multigis_metadata_tags(metadata_str)

            # Parse INI format metadata
            mdict.update(self._parse_metadata_string(metadata_str))

            # Extract important fields to nx_meta
            mdict = self._parse_nx_meta(mdict)

            # Migrate metadata to schema-compliant format
            mdict = self._migrate_to_schema_compliant_metadata(mdict)

        except Exception as e:
            _logger.exception("Error extracting metadata from %s", filename)
            mdict["nx_meta"]["Data Type"] = "Unknown"
            mdict["nx_meta"]["Extractor Warnings"] = f"Extraction failed: {e}"

        # sort the nx_meta dictionary (recursively) for nicer display
        mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

        return [mdict]

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
        if beam_name is not None:
            fields.extend(
                [
                    FD(
                        beam_name,
                        "EmissionCurrent",
                        "Emission Current",
                        1.0,
                        False,
                        target_unit="ampere",
                    ),
                    FD(
                        beam_name,
                        "HFW",
                        "Horizontal Field Width",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(beam_name, "HV", "Voltage", 1.0, False, target_unit="volt"),
                    FD(beam_name, "SourceTiltX", "Beam Tilt X", 1.0, False),
                    FD(beam_name, "SourceTiltY", "Beam Tilt Y", 1.0, False),
                    FD(beam_name, "StageR", ["Stage Position", "R"], 1.0, False),
                    FD(beam_name, "StageTa", ["Stage Position", "α"], 1.0, False),  # noqa: RUF001
                    FD(beam_name, "StageX", ["Stage Position", "X"], 1.0, False),
                    FD(beam_name, "StageY", ["Stage Position", "Y"], 1.0, False),
                    FD(beam_name, "StageZ", ["Stage Position", "Z"], 1.0, False),
                    FD(
                        beam_name,
                        "StageTb",
                        ["Stage Position", "β"],
                        1.0,
                        False,
                        suppress_zero=False,
                    ),
                    FD(beam_name, "StigmatorX", "Stigmator X Value", 1.0, False),
                    FD(beam_name, "StigmatorY", "Stigmator Y Value", 1.0, False),
                    FD(
                        beam_name,
                        "VFW",
                        "Vertical Field Width",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        beam_name,
                        "WD",
                        "Working Distance",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        beam_name,
                        "EucWD",
                        "Eucentric WD",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(beam_name, "ImageMode", "Image Mode", 1.0, True),
                    FD(
                        beam_name,
                        "BeamShiftX",
                        "Beam Shift X",
                        1.0,
                        False,
                    ),
                    FD(
                        beam_name,
                        "BeamShiftY",
                        "Beam Shift Y",
                        1.0,
                        False,
                    ),
                    FD(beam_name, "BeamMode", "Beam Mode", 1.0, True),
                    FD(beam_name, "PreTilt", "Pre-Tilt", 1.0, False),
                ]
            )

        # Scan section fields
        if scan_name is not None:
            fields.extend(
                [
                    FD(
                        scan_name,
                        "Dwell",
                        "Pixel Dwell Time",
                        1.0,
                        False,
                        target_unit="second",
                    ),
                    FD(
                        scan_name,
                        "FrameTime",
                        "Total Frame Time",
                        1.0,
                        False,
                        target_unit="second",
                    ),
                    FD(
                        scan_name,
                        "HorFieldsize",
                        "Horizontal Field Width",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        scan_name,
                        "VerFieldsize",
                        "Vertical Field Width",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        scan_name,
                        "PixelHeight",
                        "Pixel Width",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        scan_name,
                        "PixelWidth",
                        "Pixel Height",
                        1.0,
                        False,
                        target_unit="meter",
                    ),
                    FD(
                        scan_name,
                        "LineTime",
                        "Line Time",
                        1.0,
                        False,
                        target_unit="second",
                    ),
                    FD(
                        scan_name,
                        "LineIntegration",
                        "Line Integration",
                        1.0,
                        False,
                    ),
                    FD(
                        scan_name,
                        "ScanInterlacing",
                        "Scan Interlacing",
                        1.0,
                        False,
                    ),
                ]
            )

        # Detector section fields
        if det_name is not None:
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
                    FD(
                        det_name,
                        "Grid",
                        "Detector Grid Voltage",
                        1.0,
                        False,
                        target_unit="volt",
                    ),
                    FD(
                        det_name, "BrightnessDB", "Detector Brightness (DB)", 1.0, False
                    ),
                    FD(det_name, "ContrastDB", "Detector Contrast (DB)", 1.0, False),
                    FD(
                        det_name,
                        "Mix",
                        "Detector Mix (%)",
                        1.0,
                        False,
                    ),
                    FD(
                        det_name,
                        "MinimumDwellTime",
                        "Minimum Dwell Time",
                        1.0,
                        False,
                        target_unit="second",
                    ),
                ]
            )

        # System section fields
        fields.extend(
            [
                FD("System", "Chamber", "Chamber ID", 1.0, True),
                FD("System", "Pump", "Vacuum Pump", 1.0, True),
                FD("System", "SystemType", "System Type", 1.0, True),
                FD("System", "Stage", "Stage Description", 1.0, True),
                FD("System", "Dnumber", "Device Number", 1.0, True),
                FD("System", "Source", "Electron Source", 1.0, True),
                FD("System", "FinalLens", "Final Lens", 1.0, True),
                FD("System", "ESEM", "ESEM Setting", 1.0, True),
                FD("System", "Aperture", "Aperture Type", 1.0, True),
            ]
        )

        # Other fields
        fields.extend(
            [
                FD("Beam", "Spot", "Spot Size", 1.0, False),
                FD(
                    "Specimen",
                    "Temperature",
                    "Specimen Temperature",
                    1.0,
                    False,
                    target_unit="kelvin",
                ),
                FD(
                    "Specimen",
                    "Humidity",
                    "Specimen Humidity",
                    1.0,
                    False,
                    target_unit="percent",
                ),
                FD("User", "UserText", "User Text", 1.0, True),
                FD("User", "Date", "Acquisition Date", 1.0, True),
                FD("User", "Time", "Acquisition Time", 1.0, True),
                FD("Vacuum", "UserMode", "Vacuum Mode", 1.0, True),
                FD("Vacuum", "Gas", "Vacuum Gas", 1.0, False),
                FD("Image", "MagnificationMode", "Magnification Mode", 1.0, False),
                FD(
                    "Image",
                    "DigitalContrast",
                    "Digital Contrast",
                    1.0,
                    False,
                ),
                FD(
                    "Image",
                    "DigitalBrightness",
                    "Digital Brightness",
                    1.0,
                    False,
                ),
                FD(
                    "Image",
                    "DigitalGamma",
                    "Digital Gamma",
                    1.0,
                    False,
                ),
                FD(
                    "Image",
                    "ZoomFactor",
                    "Zoom Factor",
                    1.0,
                    False,
                ),
                FD("Image", "ZoomPanX", "Zoom Pan X", 1.0, False),
                FD("Image", "ZoomPanY", "Zoom Pan Y", 1.0, False),
                FD(
                    "Image",
                    "MagCanvasRealWidth",
                    "Magnification Canvas Real Width",
                    1.0,
                    False,
                ),
                FD(
                    "Image",
                    "ScreenMagCanvasRealWidth",
                    "Screen Magnification Canvas Real Width",
                    1.0,
                    False,
                ),
                FD(
                    "Image",
                    "ScreenMagnificationMode",
                    "Screen Magnification Mode",
                    1.0,
                    False,
                ),
                FD("Image", "Average", "Frame Average", 1.0, False),
                FD("Image", "PostProcessing", "Post Processing", 1.0, False),
            ]
        )

        # EScan Mainslock field
        if scan_name is not None:
            fields.append(FD(scan_name, "Mainslock", "Mainslock", 1.0, True))

        return fields

    def _process_standard_fields(
        self, mdict: dict, fields: list[FieldDefinition], det_name: str
    ) -> None:
        """Process standard field definitions."""
        for field in fields:
            value = try_getting_dict_value(mdict, [field.section, field.source_key])

            if value is not None and value != "":
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
                        field.target_unit,
                    )

    def _set_field_value(self, mdict: dict, output_key: str | list, value: str) -> None:
        """Set a string field value in metadata."""
        if isinstance(output_key, list):
            set_nested_dict_value(mdict, ["nx_meta", *output_key], value)
        else:
            set_nested_dict_value(mdict, ["nx_meta", output_key], value)

    def _set_numeric_field_value(  # noqa: PLR0913
        self,
        mdict: dict,
        output_key: str | list,
        value: str,
        factor: float,
        suppress_zero: bool,
        unit: str | None = None,
    ) -> None:
        """Set a numeric field value with unit conversion.

        Parameters
        ----------
        mdict
            Metadata dictionary
        output_key
            Output key or nested path
        value
            String value to convert
        factor
            Multiplicative conversion factor
        suppress_zero
            If True, skip if value equals zero
        unit
            Pint unit string (e.g., "kilovolt"). If provided, creates a Quantity.
        """
        try:
            decimal_val = Decimal(value) * Decimal(str(factor))
            if not suppress_zero or decimal_val != 0:
                # Create Pint Quantity if unit is specified
                if unit is not None:
                    quantity_val = ureg.Quantity(decimal_val, unit)
                    self._set_field_value(mdict, output_key, quantity_val)
                else:
                    # Convert to float for non-quantity values
                    self._set_field_value(mdict, output_key, float(decimal_val))
        except (ValueError, InvalidOperation, TypeError):
            # TypeError can occur if value is None
            if value is not None:
                self._set_field_value(mdict, output_key, value)

    def _parse_special_cases(self, mdict: dict, beam_name: str, det_name: str) -> None:
        """Parse special case metadata fields."""
        if beam_name is not None:
            set_nested_dict_value(mdict, ["nx_meta", "Beam Name"], beam_name)
        if det_name is not None:
            set_nested_dict_value(mdict, ["nx_meta", "Detector Name"], det_name)

        if beam_name is not None:
            self._parse_scan_rotation(mdict, beam_name)
            self._parse_tilt_correction(mdict, beam_name)
            self._parse_beam_control_flags(mdict, beam_name)
        self._parse_drift_correction(mdict)
        self._parse_frame_integration(mdict)
        self._parse_resolution(mdict)
        self._parse_operator(mdict)
        self._parse_chamber_pressure(mdict)
        self._parse_software_version(mdict)
        self._parse_column_type(mdict)
        self._parse_scan_settings(mdict)

    def _parse_scan_rotation(self, mdict: dict, beam_name: str) -> None:
        """Parse scan rotation (radians → degrees)."""
        scan_rot_val = try_getting_dict_value(mdict, [beam_name, "ScanRotation"])
        if scan_rot_val is not None:
            scan_rot_dec = Decimal(scan_rot_val)
            digits = abs(scan_rot_dec.as_tuple().exponent)
            scan_rot_degrees = round(degrees(scan_rot_dec), digits)
            scan_rot_quantity = ureg.Quantity(scan_rot_degrees, "degree")
            set_nested_dict_value(
                mdict, ["nx_meta", "Scan Rotation"], scan_rot_quantity
            )

    def _parse_tilt_correction(self, mdict: dict, beam_name: str) -> None:
        """Parse tilt correction (conditional on TiltCorrectionIsOn)."""
        tilt_corr_on = try_getting_dict_value(mdict, [beam_name, "TiltCorrectionIsOn"])
        if tilt_corr_on == "yes":
            tilt_corr_val = try_getting_dict_value(
                mdict, [beam_name, "TiltCorrectionAngle"]
            )
            if tilt_corr_val is not None:
                set_nested_dict_value(
                    mdict,
                    ["nx_meta", "Tilt Correction Angle"],
                    float(Decimal(tilt_corr_val)),
                )

    def _parse_beam_control_flags(self, mdict: dict, beam_name: str) -> None:
        """Parse beam control boolean flags."""
        # Tilt correction on/off
        tilt_corr_on = try_getting_dict_value(mdict, [beam_name, "TiltCorrectionIsOn"])
        if tilt_corr_on is not None:
            set_nested_dict_value(
                mdict, ["nx_meta", "Tilt Correction Enabled"], tilt_corr_on == "yes"
            )

        # Dynamic focus on/off
        dyn_focus = try_getting_dict_value(mdict, [beam_name, "DynamicFocusIsOn"])
        if dyn_focus is not None:
            set_nested_dict_value(
                mdict, ["nx_meta", "Dynamic Focus Enabled"], dyn_focus == "yes"
            )

        # Dynamic WD on/off
        dyn_wd = try_getting_dict_value(mdict, [beam_name, "DynamicWDIsOn"])
        if dyn_wd is not None:
            set_nested_dict_value(
                mdict, ["nx_meta", "Dynamic WD Enabled"], dyn_wd == "yes"
            )

    def _parse_drift_correction(self, mdict: dict) -> None:
        """Parse drift correction (boolean)."""
        drift_val = try_getting_dict_value(mdict, ["Image", "DriftCorrected"])
        if drift_val is not None:
            set_nested_dict_value(
                mdict, ["nx_meta", "Drift Correction Applied"], drift_val == "On"
            )

    def _parse_frame_integration(self, mdict: dict) -> None:
        """Parse frame integration (only if > 1)."""
        integrate_val = try_getting_dict_value(mdict, ["Image", "Integrate"])
        if integrate_val is not None:
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
        if x_val is not None and y_val is not None:
            with contextlib.suppress(ValueError):
                x_int = int(x_val)
                y_int = int(y_val)
                set_nested_dict_value(
                    mdict, ["nx_meta", "Data Dimensions"], str((x_int, y_int))
                )

    def _parse_operator(self, mdict: dict) -> None:
        """Parse operator (with warning)."""
        user_val = try_getting_dict_value(mdict, ["User", "User"])
        if user_val is not None:
            set_nested_dict_value(mdict, ["nx_meta", "Operator"], user_val)
            mdict["nx_meta"]["warnings"].append(["Operator"])

    def _parse_chamber_pressure(self, mdict: dict) -> None:
        """Parse chamber pressure (unit depends on vacuum mode)."""
        ch_pres_val = try_getting_dict_value(mdict, ["Vacuum", "ChPressure"])
        if ch_pres_val is not None and ch_pres_val != "":
            try:
                ch_pres_decimal = Decimal(ch_pres_val)
                is_high_vacuum = (
                    try_getting_dict_value(mdict, ["nx_meta", "Vacuum Mode"])
                    == "High vacuum"
                )

                if is_high_vacuum:
                    # Value is in Pa, multiply by 1000 to get mPa
                    ch_pres_decimal_mpa = ch_pres_decimal * 10**3
                    ch_pres_quantity = ureg.Quantity(ch_pres_decimal_mpa, "millipascal")
                else:
                    # Value is already in Pa
                    ch_pres_quantity = ureg.Quantity(ch_pres_decimal, "pascal")

                set_nested_dict_value(
                    mdict,
                    ["nx_meta", "Chamber Pressure"],
                    ch_pres_quantity,
                )
            except (ValueError, InvalidOperation):
                # If conversion fails, store as string without unit
                set_nested_dict_value(
                    mdict, ["nx_meta", "Chamber Pressure"], ch_pres_val
                )

    def _parse_software_version(self, mdict: dict) -> None:
        """Parse software version (aggregate Software + BuildNr)."""
        software_parts = []
        software_val = try_getting_dict_value(mdict, ["System", "Software"])
        if software_val is not None:
            software_parts.append(software_val)
        build_val = try_getting_dict_value(mdict, ["System", "BuildNr"])
        if build_val is not None:
            software_parts.append(f"(build {build_val})")
        if software_parts:
            set_nested_dict_value(
                mdict, ["nx_meta", "Software Version"], " ".join(software_parts)
            )

    def _parse_column_type(self, mdict: dict) -> None:
        """Parse column type (aggregate Column + Type)."""
        column_parts = []
        column_val = try_getting_dict_value(mdict, ["System", "Column"])
        if column_val is not None:
            column_parts.append(column_val)
        type_val = try_getting_dict_value(mdict, ["System", "Type"])
        if type_val is not None:
            column_parts.append(type_val)
        if column_parts:
            set_nested_dict_value(
                mdict, ["nx_meta", "Column Type"], " ".join(column_parts)
            )

    def _parse_scan_settings(self, mdict: dict) -> None:
        """Parse scan-related settings."""
        # Internal scan flag
        scan_name = try_getting_dict_value(mdict, ["Beam", "Scan"])
        if scan_name is not None:
            internal_scan = try_getting_dict_value(mdict, [scan_name, "InternalScan"])
            if internal_scan is not None:
                set_nested_dict_value(
                    mdict, ["nx_meta", "Internal Scan"], internal_scan == "true"
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

    def _migrate_to_schema_compliant_metadata(self, mdict: dict) -> dict:
        """
        Migrate metadata to schema-compliant format.

        Reorganizes metadata to conform to type-specific Pydantic schemas:
        - Extracts core EM Glossary fields to top level with standardized names
        - Moves vendor-specific nested dictionaries to extensions section
        - Preserves existing extensions from instrument profiles

        Parameters
        ----------
        mdict
            Metadata dictionary with nx_meta containing extracted fields

        Returns
        -------
        dict
            Metadata dictionary with schema-compliant nx_meta structure
        """
        nx_meta = mdict.get("nx_meta", {})

        # Preserve existing extensions from instrument profiles
        extensions = (
            nx_meta.get("extensions", {}).copy() if "extensions" in nx_meta else {}
        )

        # Field mappings from display names to EM Glossary names
        field_mappings = {
            "Voltage": "acceleration_voltage",
            "Working Distance": "working_distance",
            "Emission Current": "emission_current",
            "Pixel Dwell Time": "dwell_time",
            "Horizontal Field Width": "horizontal_field_width",
            "Vertical Field Width": "vertical_field_width",
            "Pixel Width": "pixel_width",
            "Pixel Height": "pixel_height",
        }

        # Fields that ALWAYS go to extensions (vendor-specific nested dicts)
        extension_top_level_keys = {
            "Beam",
            "Scan",
            "Detector",
            "Stage Position",
            "Image",
            "Application",
            "Vacuum",
            "System",
            "User",
            "Detectors",
            "GIS",
            "Specimen",
            "PrivateFei",
            "FEI_XML_Metadata",
            "Optics",
        }

        # Also move these individual vendor fields to extensions
        extension_field_names = {
            "Detector Brightness Setting",
            "Detector Contrast Setting",
            "Detector Enhanced Contrast Setting",
            "Detector Signal",
            "Detector Grid Voltage",
            "Beam Tilt X",
            "Beam Tilt Y",
            "Stigmator X Value",
            "Stigmator Y Value",
            "Beam Shift X",
            "Beam Shift Y",
            "Beam Mode",
            "Image Mode",
            "Pre-Tilt",
            "Eucentric WD",
            "Total Frame Time",
            "Line Time",
            "Line Integration",
            "Scan Interlacing",
        }

        # Build new nx_meta with proper field organization
        new_nx_meta = {}

        # Copy required fields
        for field in ["DatasetType", "Data Type", "Creation Time"]:
            if field in nx_meta:
                new_nx_meta[field] = nx_meta[field]

        # Copy instrument identification
        if "Instrument ID" in nx_meta:
            new_nx_meta["Instrument ID"] = nx_meta["Instrument ID"]

        # Process all fields and categorize
        for old_name, value in nx_meta.items():
            # Skip fields we've already handled
            if old_name in [
                "DatasetType",
                "Data Type",
                "Creation Time",
                "Instrument ID",
                "Extractor Warnings",
                "warnings",
                "extensions",
            ]:
                continue

            # Top-level vendor sections go to extensions
            if old_name in extension_top_level_keys:
                extensions[old_name] = value
                continue

            # Check if this is a core field that needs renaming
            if old_name in field_mappings:
                emg_name = field_mappings[old_name]
                new_nx_meta[emg_name] = value
                continue

            # Vendor-specific individual fields go to extensions
            if old_name in extension_field_names:
                extensions[old_name] = value
                continue

            # Everything else goes to extensions (vendor-specific by default)
            # This is safer than at top level where schema validation will reject
            extensions[old_name] = value

        # Copy warnings if present
        if "warnings" in nx_meta:
            new_nx_meta["warnings"] = nx_meta["warnings"]

        # Add extensions section if we have any
        for key, value in extensions.items():
            add_to_extensions(new_nx_meta, key, value)

        mdict["nx_meta"] = new_nx_meta
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
