# ruff: noqa: S314, N817, FBT003
"""Zeiss Orion/Fibics TIFF extractor plugin."""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.base import FieldDefinition as FD
from nexusLIMS.extractors.utils import _set_instr_name_and_time
from nexusLIMS.utils import set_nested_dict_value, sort_dict

ZEISS_TIFF_TAG = 65000
"""
TIFF tag ID where Zeiss Orion stores XML metadata in TIFF files.
The tag contains serialized XML with an <ImageTags> root element
that holds instrument configuration, beam parameters, stage position,
detector settings, and other acquisition metadata.
"""

FIBICS_TIFF_TAG = 51023
"""
TIFF tag ID where Fibics helium ion microscope stores XML metadata in TIFF files.
The tag contains serialized XML with a <Fibics> root element that holds
application info, image data, scan parameters, stage position, beam info,
and detector settings.
"""

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


class OrionTiffExtractor:
    """
    Extractor for Zeiss Orion and Fibics helium ion microscope TIFF files.

    This extractor handles metadata extraction from .tif files saved by
    Zeiss Orion and Fibics helium ion microscopes (HIM). These files contain
    embedded XML metadata in custom TIFF tags:
    - Zeiss: TIFF tag 65000 with <ImageTags> XML
    - Fibics: TIFF tag 51023 with <Fibics> XML
    """

    name = "orion_HIM_tif_extractor"
    priority = 150  # Higher than QuantaTiffExtractor (100) to handle Orion TIFFs first
    supported_extensions: ClassVar = {
        "tif",
        "tiff",
    }  # Uses content sniffing in supports() to detect variant

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Uses content sniffing to detect Zeiss/Fibics TIFF files by checking
        for the presence of custom TIFF tags containing XML metadata.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if file is a Zeiss Orion or Fibics TIFF file
        """
        # File must exist to check TIFF tags
        if not context.file_path.exists():
            _logger.warning("File does not exist: %s", context.file_path)
            return False

        try:
            with Image.open(context.file_path) as img:
                variant = self._detect_variant(img)
                return variant is not None
        except Exception as e:
            _logger.warning("Error checking TIFF tags for %s: %s", context.file_path, e)
            return False

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a Zeiss Orion or Fibics TIFF file.

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
        _logger.debug("Extracting metadata from Zeiss/Fibics TIFF file: %s", filename)

        mdict = {"nx_meta": {}}
        mdict["nx_meta"]["DatasetType"] = "Image"
        mdict["nx_meta"]["Data Type"] = "HIM_Imaging"
        try:
            _set_instr_name_and_time(mdict, filename)
            with Image.open(filename) as img:
                # Detect which variant we have
                variant = self._detect_variant(img)

                if variant == "zeiss":
                    xml_data = img.tag_v2[ZEISS_TIFF_TAG]
                    root = ET.fromstring(xml_data)
                    mdict = self._extract_zeiss_metadata(root, img, filename, mdict)
                elif variant == "fibics":
                    xml_data = img.tag_v2[FIBICS_TIFF_TAG]
                    root = ET.fromstring(xml_data)
                    mdict = self._extract_fibics_metadata(root, img, filename, mdict)
                else:
                    _logger.warning(
                        "Could not detect Zeiss/Fibics variant for %s", filename
                    )
                    mdict["nx_meta"]["Data Type"] = "Unknown"
                    mdict["nx_meta"]["Extractor Warnings"] = (
                        "Could not detect Zeiss/Fibics variant"
                    )

        except Exception as e:
            _logger.exception("Error extracting metadata from %s", filename)
            mdict["nx_meta"]["Data Type"] = "Unknown"
            mdict["nx_meta"]["Extractor Warnings"] = f"Extraction failed: {e}"

        # Sort the nx_meta dictionary for nicer display
        mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

        return mdict

    def _detect_variant(self, img: Image.Image) -> str | None:
        """
        Detect whether this is a Zeiss or Fibics TIFF file.

        Parameters
        ----------
        img
            PIL Image object

        Returns
        -------
        str | None
            "zeiss", "fibics", or None if neither detected
        """
        if ZEISS_TIFF_TAG in img.tag_v2:
            xml_data = img.tag_v2[ZEISS_TIFF_TAG]
            try:
                root = ET.fromstring(xml_data)
                if root.tag == "ImageTags" or "ImageTags" in root.tag:
                    return "zeiss"
            except ET.ParseError as e:
                _logger.warning("Failed to parse Zeiss XML from TIFF tag: %s", e)

        if FIBICS_TIFF_TAG in img.tag_v2:
            xml_data = img.tag_v2[FIBICS_TIFF_TAG]
            try:
                root = ET.fromstring(xml_data)
                if root.tag == "Fibics" or "Fibics" in root.tag:
                    return "fibics"
            except ET.ParseError as e:
                _logger.warning("Failed to parse Fibics XML from TIFF tag: %s", e)

        return None

    def _extract_zeiss_metadata(
        self,
        root: ET.Element,
        img: Image.Image,
        filename: Path,  # noqa: ARG002
        mdict: dict,
    ) -> dict:
        """
        Extract metadata from Zeiss Orion XML format.

        Parameters
        ----------
        root
            XML root element
        img
            PIL Image object
        filename
            Path to the file
        mdict
            Metadata dictionary to update

        Returns
        -------
        dict
            Updated metadata dictionary
        """
        # Parse Zeiss XML structure
        # <ImageTags> contains nested sections with Value/Units pairs

        # Set image dimensions
        width, height = img.size
        set_nested_dict_value(
            mdict, ["nx_meta", "Data Dimensions"], str((width, height))
        )

        # Define metadata fields using FieldDefinition
        fields = [
            # GFIS
            FD(
                "",
                "GFIS.AccelerationVoltage",
                ["GFIS", "Acceleration Voltage (kV)"],
                1e-3,
                False,
            ),
            FD(
                "",
                "GFIS.ExtractionVoltage",
                ["GFIS", "Extraction Voltage (kV)"],
                1e-3,
                False,
            ),
            FD(
                "",
                "GFIS.CondenserVoltage",
                ["GFIS", "Condenser Voltage (kV)"],
                1e-3,
                False,
            ),
            FD(
                "",
                "GFIS.ObjectiveVoltage",
                ["GFIS", "Objective Voltage (kV)"],
                1e-3,
                False,
            ),
            FD("", "GFIS.BeamCurrent", ["GFIS", "Beam Current (pA)"], 1, False),
            FD("", "GFIS.PanX", ["GFIS", "Pan X (μm)"], 1, False),
            FD("", "GFIS.PanY", ["GFIS", "Pan Y (μm)"], 1, False),
            FD("", "GFIS.FieldOfView", ["GFIS", "Field of View (μm)"], 1, False),
            FD("", "GFIS.ScanRotation", ["GFIS", "Scan Rotation (degrees)"], 1, False),
            FD("", "GFIS.StigmationX", ["GFIS", "Stigmation X"], 1, False),
            FD("", "GFIS.StigmationY", ["GFIS", "Stigmation Y"], 1, False),
            FD("", "GFIS.ApertureSize", ["GFIS", "Aperture Size (μm)"], 1, False),
            FD("", "GFIS.ApertureIndex", ["GFIS", "Aperture Index"], 1, False),
            FD("", "GFIS.IonGas", ["GFIS", "Ion Gas"], 1, False),
            FD(
                "",
                "GFIS.CrossoverPosition",
                ["GFIS", "Crossover Position (mm)"],
                1,
                False,
            ),
            FD("", "GFIS.WorkingDistance", ["GFIS", "Working Distance (mm)"], 1, False),
            # Beam
            FD("", "AccelerationVoltage", ["Beam", "Voltage (kV)"], 1e-3, False),
            FD(
                "",
                "ExtractionVoltage",
                ["Beam", "Extraction Voltage (kV)"],
                1e-3,
                False,
            ),
            FD("", "BlankerCurrent", ["Beam", "Blanker Current (pA)"], 1, False),
            FD("", "SampleCurrent", ["Beam", "Sample Current (pA)"], 1, False),
            FD("", "SpotNumber", ["Beam", "Spot Number"], 1, False),
            FD("", "WorkingDistance", ["Beam", "Working Distance (mm)"], 1, False),
            FD("", "Fov", ["Beam", "Field of View (μm)"], 1, False),
            FD("", "PanX", ["Beam", "Pan X (μm)"], 1, False),
            FD("", "PanY", ["Beam", "Pan Y (μm)"], 1, False),
            FD("", "StigmationX", ["Beam", "Stigmator X Value"], 1, False),
            FD("", "StigmationY", ["Beam", "Stigmator Y Value"], 1, False),
            FD("", "ApertureSize", ["Beam", "Aperture Size"], 1, False),
            FD("", "CrossOverPosition", ["Beam", "Crossover Position (mm)"], 1, False),
            # Scan
            FD("", "FrameRetrace", ["Scan", "Frame Retrace (μs)"], 1, False),
            FD("", "LineRetrace", ["Scan", "Line Retrace (μs)"], 1, False),
            FD("", "AveragingMode", ["Scan", "Averaging Mode"], 1, False),
            FD("", "NumAverages", ["Scan", "Number of Averages"], 1, False),
            FD("", "ScanRotate", ["Scan", "Rotation (degrees)"], 1, False),
            FD("", "DwellTime", ["Scan", "Dwell Time (μs)"], 1, False),
            FD("", "SAS.ScanSize", ["Scan", "Scan Size"], 1, False),
            # Stage
            FD("", "StageX", ["Stage Position", "X (μm)"], 1, False),
            FD("", "StageY", ["Stage Position", "Y (μm)"], 1, False),
            FD("", "StageZ", ["Stage Position", "Z (mm)"], 1, False),
            FD("", "StageTilt", ["Stage Position", "Tilt (degrees)"], 1, False),
            FD("", "StageRotate", ["Stage Position", "Rotation (degrees)"], 1, False),
            FD("", "Stage.XLocation", ["Stage Position", "X Location (μm)"], 1, False),
            FD("", "Stage.YLocation", ["Stage Position", "Y Location (μm)"], 1, False),
            # Optics
            FD("", "sFimFOV", ["Optics", "sFIM Field of View (μm)"], 1, False),
            FD("", "McXShift", ["Optics", "MC X Shift (μrad)"], 1, False),
            FD("", "McXTilt", ["Optics", "MC X Tilt (μrad)"], 1, False),
            FD("", "McYShift", ["Optics", "MC Y Shift (μrad)"], 1, False),
            FD("", "McYTilt", ["Optics", "MC Y Tilt (μrad)"], 1, False),
            FD("", "ColumnMag", ["Optics", "Column Magnification"], 1, False),
            FD("", "ColumnMode", ["Optics", "Column Mode"], 1, False),
            FD("", "Lens1Voltage", ["Optics", "Lens 1 Voltage (kV)"], 1e-3, False),
            FD("", "Lens2Voltage", ["Optics", "Lens 2 Voltage (kV)"], 1e-3, False),
            # Detector
            FD("", "DetectorName", ["Detector", "Name"], 1, False),
            FD("", "ETGridVoltage", ["Detector", "ET Grid Voltage (V)"], 1, False),
            FD("", "ETContrast", ["Detector", "ET Contrast"], 1, False),
            FD("", "ETBrightness", ["Detector", "ET Brightness"], 1, False),
            FD("", "ETImageIntensity", ["Detector", "ET Image Intensity"], 1, False),
            FD("", "MCPContrast", ["Detector", "MCP Contrast"], 1, False),
            FD("", "MCPBrightness", ["Detector", "MCP Brightness"], 1, False),
            FD("", "MCPBias", ["Detector", "MCP Bias (V)"], 1, False),
            FD("", "MCPImageIntensity", ["Detector", "MCP Image Intensity"], 1, False),
            FD(
                "",
                "Detector.Scintillator",
                ["Detector", "Scintillator (kV)"],
                1e-3,
                False,
            ),
            FD("", "SampleBiasVoltage", ["Detector", "Sample Bias (V)"], 1, False),
            # System
            FD("", "GunPressure", ["System", "Gun Pressure (Torr)"], 1, False),
            FD("", "ColumnPressure", ["System", "Column Pressure (Torr)"], 1, False),
            FD("", "ChamberPressure", ["System", "Chamber Pressure (Torr)"], 1, False),
            FD("", "GunTemp", ["System", "Gun Temperature (K)"], 1, False),
            FD("", "HeliumPressure", ["System", "Helium Pressure (Torr)"], 1, False),
            FD("", "Magnification4x5", ["Optics", "Magnification 4x5"], 1, False),
            FD(
                "",
                "MagnificationDisplay",
                ["Optics", "Magnification Display (x)"],
                1,
                False,
            ),
            FD("", "System.Model", ["System", "Model"], 1, False),
            FD("", "System.Name", ["System", "Name"], 1, False),
            FD("", "TimeStamp", ["System", "Acquisition Date/Time"], 1, False),
            FD("", "ColumnType", ["System", "Column Type"], 1, False),
            # Flood gun
            FD("", "FloodGunMode", ["Flood Gun", "Mode"], 1, False),
            FD("", "FloodGunEnergy", ["Flood Gun", "Energy (eV)"], 1, False),
            FD("", "FloodGunTime", ["Flood Gun", "Time (μs)"], 1, False),
            FD("", "FloodGun.DeflectionX", ["Flood Gun", "Deflection X"], 1, False),
            FD("", "FloodGun.DeflectionY", ["Flood Gun", "Deflection Y"], 1, False),
            # Misc
            FD("", "ScalingX", ["Calibration", "X Scale (m)"], 1, False),
            FD("", "ScalingY", ["Calibration", "Y Scale (m)"], 1, False),
            FD("", "ImageWidth", ["Image", "Width (pixels)"], 1, False),
            FD("", "ImageHeight", ["Image", "Height (pixels)"], 1, False),
            # Display
            FD("", "LutMode", ["Display", "LUT Mode"], 1, False),
            FD("", "LowGray", ["Display", "Low Gray Value"], 1, False),
            FD("", "HighGray", ["Display", "High Gray Value"], 1, False),
            FD("", "LUT.LUTGamma", ["Display", "LUT Gamma"], 1, False),
        ]

        # Extract all fields
        for field in fields:
            self._parse_zeiss_field(
                root, field.source_key, field.output_key, mdict, field.factor
            )

        return mdict

    def _extract_fibics_metadata(
        self,
        root: ET.Element,
        img: Image.Image,
        filename: Path,  # noqa: ARG002
        mdict: dict,
    ) -> dict:
        """
        Extract metadata from Fibics XML format.

        Parameters
        ----------
        root
            XML root element
        img
            PIL Image object
        filename
            Path to the file
        mdict
            Metadata dictionary to update

        Returns
        -------
        dict
            Updated metadata dictionary
        """
        # Set image dimensions
        width, height = img.size
        set_nested_dict_value(
            mdict, ["nx_meta", "Data Dimensions"], str((width, height))
        )

        # Define Fibics metadata fields using FD
        # Note: factor=-1 is a sentinel value for "strip_units" conversion
        fibics_fields = [
            # Application section
            FD("Application", "Version", ["Application", "Software Version"], 1, False),
            FD(
                "Application",
                "Date",
                ["Application", "Acquisition Date/Time"],
                1,
                False,
            ),
            FD(
                "Application",
                "SupportsTransparency",
                ["Application", "Supports Transparency"],
                1,
                False,
            ),
            FD(
                "Application",
                "TransparentPixelValue",
                ["Application", "Transparent Pixel Value"],
                1,
                False,
            ),
            # Image section
            FD("Image", "Width", ["Image", "Width (pixels)"], 1, False),
            FD("Image", "Height", ["Image", "Height (pixels)"], 1, False),
            FD("Image", "BoundingBox.Left", ["Image", "Bounding Box Left"], 1, False),
            FD("Image", "BoundingBox.Right", ["Image", "Bounding Box Right"], 1, False),
            FD("Image", "BoundingBox.Top", ["Image", "Bounding Box Top"], 1, False),
            FD(
                "Image",
                "BoundingBox.Bottom",
                ["Image", "Bounding Box Bottom"],
                1,
                False,
            ),
            FD("Image", "Machine", ["Image", "Machine Name"], 1, False),
            FD("Image", "Beam", ["Image", "Beam Type"], 1, False),
            FD("Image", "Aperture", ["Image", "Aperture Description"], 1, False),
            FD("Image", "Detector", ["Detector", "Name"], 1, False),
            FD("Image", "Contrast", ["Detector", "Contrast"], 1, False),
            FD("Image", "Brightness", ["Detector", "Brightness"], 1, False),
            # Scan section
            FD(
                "Scan", "Dwell", ["Scan", "Pixel Dwell Time (μs)"], 1e-3, False
            ),  # Convert ns to μs
            FD("Scan", "LineAvg", ["Scan", "Line Averaging"], 1, False),
            FD("Scan", "FOV_X", ["Scan", "Field of View X (μm)"], 1, False),
            FD("Scan", "FOV_Y", ["Scan", "Field of View Y (μm)"], 1, False),
            FD("Scan", "ScanRot", ["Scan", "Scan Rotation (degrees)"], 1, False),
            FD("Scan", "Ux", ["Scan", "Affine Ux"], 1, False),
            FD("Scan", "Uy", ["Scan", "Affine Uy"], 1, False),
            FD("Scan", "Vx", ["Scan", "Affine Vx"], 1, False),
            FD("Scan", "Vy", ["Scan", "Affine Vy"], 1, False),
            FD("Scan", "Focus", ["Scan", "Focus Value"], 1, False),
            FD("Scan", "StigX", ["Scan", "Stigmator X Value"], 1, False),
            FD("Scan", "StigY", ["Scan", "Stigmator Y Value"], 1, False),
            # Stage section
            FD("Stage", "X", ["Stage Position", "X (μm)"], 1, False),
            FD("Stage", "Y", ["Stage Position", "Y (μm)"], 1, False),
            FD("Stage", "Z", ["Stage Position", "Z (μm)"], 1, False),
            FD("Stage", "Tilt", ["Stage Position", "Tilt (degrees)"], 1, False),
            FD("Stage", "Rot", ["Stage Position", "Rotation (degrees)"], 1, False),
            FD("Stage", "M", ["Stage Position", "M (mm)"], 1, False),
            # BeamInfo section
            FD("BeamInfo", "BeamI", ["Beam", "Beam Current (pA)"], 1, False),
            FD("BeamInfo", "AccV", ["Beam", "Acceleration Voltage (kV)"], 1e-3, False),
            FD("BeamInfo", "Aperture", ["Beam", "Aperture"], 1, False),
            FD("BeamInfo", "GFISGas", ["Beam", "GFIS Gas Type"], 1, False),
            FD("BeamInfo", "GunGasPressure", ["Beam", "Gun Gas Pressure"], 1, False),
            FD("BeamInfo", "SpotControl", ["Beam", "Spot Control"], 1, False),
            # DetectorInfo section - using -1 as sentinel for "strip_units"
            FD(
                "DetectorInfo",
                "Collector",
                ["Detector", "Collector Voltage (V)"],
                -1,
                False,
            ),
            FD(
                "DetectorInfo",
                "Stage Bias",
                ["Detector", "Stage Bias Voltage (V)"],
                -1,
                False,
            ),
        ]

        # Extract fields from each section
        for field in fibics_fields:
            section = self._find_fibics_section(root, field.section)
            if section is not None:
                # Use -1 as sentinel for "strip_units" conversion
                conversion_factor = (
                    "strip_units" if field.factor == -1 else field.factor
                )
                value = self._parse_fibics_value(
                    section, field.source_key, conversion_factor
                )
                if value is not None:
                    set_nested_dict_value(
                        mdict,
                        ["nx_meta", field.output_key]
                        if isinstance(field.output_key, str)
                        else ["nx_meta", *field.output_key],
                        value,
                    )

        return mdict

    def _parse_zeiss_field(
        self,
        root: ET.Element,
        field_path: str,
        output_key: str | list,
        mdict: dict,
        conversion_factor: float = 1.0,
    ) -> None:
        """
        Parse a field from Zeiss XML and set it in the metadata dictionary.

        Parameters
        ----------
        root
            XML root element
        field_path
            Path to the field. Can be a simple tag name (e.g., "AccelerationVoltage"),
            a tag name with dots (e.g., "GFIS.AccelerationVoltage"), or a nested path
            (e.g., "System.Name"). First tries to find as a direct tag name, then falls
            back to nested navigation.
        output_key
            Key path in nx_meta (e.g., "Voltage (kV)" or ["Stage Position", "X"])
        mdict
            Metadata dictionary to update
        conversion_factor
            Factor to multiply the value by for unit conversion
        """
        try:
            # First try to find as a direct tag
            # (handles dotted names like "GFIS.AccelerationVoltage")
            current = root.find(field_path)

            # If not found as direct tag, try nested path navigation
            if current is None:
                parts = field_path.split(".")
                current = root
                for part in parts:
                    found = False
                    for child in current:
                        if child.tag == part:
                            current = child
                            found = True
                            break
                    if not found:
                        return

            # Get value and units
            value = current.find("Value")
            # if we want to eventually handle units, this is how we extract them
            # units = current.find("Units")  # noqa: ERA001

            if value is not None and value.text:
                try:
                    numeric_value = float(value.text) * conversion_factor
                    set_nested_dict_value(
                        mdict,
                        ["nx_meta", output_key]
                        if isinstance(output_key, str)
                        else ["nx_meta", *output_key],
                        numeric_value,
                    )
                except (ValueError, TypeError):
                    # If conversion fails, store as string
                    set_nested_dict_value(
                        mdict,
                        ["nx_meta", output_key]
                        if isinstance(output_key, str)
                        else ["nx_meta", *output_key],
                        value.text,
                    )
        except Exception as e:
            # Log parsing errors for individual fields
            _logger.debug(
                "Error parsing Zeiss field %s: %s", field_path, e, exc_info=True
            )

    def _find_fibics_section(
        self, root: ET.Element, section_name: str
    ) -> ET.Element | None:
        """
        Find a section in Fibics XML.

        Parameters
        ----------
        root
            XML root element
        section_name
            Name of section to find (e.g., "BeamInfo", "Scan")

        Returns
        -------
        ET.Element | None
            Section element if found, None otherwise
        """
        try:
            for child in root:
                if child.tag == section_name:
                    return child
        except Exception:
            return None
        return None

    def _parse_fibics_value(
        self, section: ET.Element, field_name: str, conversion_factor: float | str = 1.0
    ) -> float | str | None:
        """
        Parse a value from a Fibics XML section.

        Parameters
        ----------
        section
            XML section element
        field_name
            Name of field to parse. First tries to find an element with this tag name.
            If not found, searches for an "item" element with a "name" attribute
            matching field_name.
        conversion_factor
            Factor to multiply the value by for unit conversion, or "strip_units" to
            remove unit suffixes (e.g., "=500.0 V" becomes 500.0)

        Returns
        -------
        float | str | None
            Parsed value, or None if not found or parsing failed
        """
        try:
            # First try to find field as direct element
            field = section.find(field_name)

            # If not found, try to find an "item" element with matching "name" attribute
            if field is None:
                for item in section.findall("item"):
                    if item.get("name") == field_name:
                        field = item
                        break

            if field is not None and field.text:
                text = field.text.strip()

                # Special handling for stripping unit suffixes
                # (e.g., "=500.0 V" -> "500.0")
                if conversion_factor == "strip_units":
                    # Remove leading symbols like "=" and trailing units like " V"
                    text = text.lstrip("=").strip()
                    # Try to extract numeric value before unit suffix
                    parts = text.split()
                    if parts:
                        text = parts[0]
                    try:
                        return float(text)
                    except ValueError:
                        return text

                try:
                    return float(text) * conversion_factor  # type: ignore[operator]
                except ValueError:
                    return text
        except Exception:
            return None
        return None
