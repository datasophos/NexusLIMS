# ruff: noqa: S314
"""Zeiss Orion/Fibics TIFF extractor plugin."""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
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


class OrionFibicsTiffExtractor:
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

        # Define metadata fields: (xml_path, output_key, conversion_factor)
        fields = [
            # GFIS
            ("GFIS.AccelerationVoltage", ["GFIS", "Acceleration Voltage (kV)"], 1e-3),
            ("GFIS.ExtractionVoltage", ["GFIS", "Extraction Voltage (kV)"], 1e-3),
            ("GFIS.CondenserVoltage", ["GFIS", "Condenser Voltage (kV)"], 1e-3),
            ("GFIS.ObjectiveVoltage", ["GFIS", "Objective Voltage (kV)"], 1e-3),
            ("GFIS.BeamCurrent", ["GFIS", "Beam Current (pA)"], 1),
            ("GFIS.PanX", ["GFIS", "Pan X (μm)"], 1),
            ("GFIS.PanY", ["GFIS", "Pan Y (μm)"], 1),
            ("GFIS.FieldOfView", ["GFIS", "Field of View (μm)"], 1),
            ("GFIS.ScanRotation", ["GFIS", "Scan Rotation (degrees)"], 1),
            ("GFIS.StigmationX", ["GFIS", "Stigmation X"], 1),
            ("GFIS.StigmationY", ["GFIS", "Stigmation Y"], 1),
            ("GFIS.ApertureSize", ["GFIS", "Aperture Size (μm)"], 1),
            ("GFIS.ApertureIndex", ["GFIS", "Aperture Index"], 1),
            ("GFIS.IonGas", ["GFIS", "Ion Gas"], 1),
            ("GFIS.CrossoverPosition", ["GFIS", "Crossover Position (mm)"], 1),
            ("GFIS.WorkingDistance", ["GFIS", "Working Distance (mm)"], 1),
            # Beam
            ("AccelerationVoltage", ["Beam", "Voltage (kV)"], 1e-3),
            ("ExtractionVoltage", ["Beam", "Extraction Voltage (kV)"], 1e-3),
            ("BlankerCurrent", ["Beam", "Blanker Current (pA)"], 1),
            ("SampleCurrent", ["Beam", "Sample Current (pA)"], 1),
            ("SpotNumber", ["Beam", "Spot Number"], 1),
            ("WorkingDistance", ["Beam", "Working Distance (mm)"], 1),
            ("Fov", ["Beam", "Field of View (μm)"], 1),
            ("PanX", ["Beam", "Pan X (μm)"], 1),
            ("PanY", ["Beam", "Pan Y (μm)"], 1),
            ("StigmationX", ["Beam", "Stigmator X Value"], 1),
            ("StigmationY", ["Beam", "Stigmator Y Value"], 1),
            ("ApertureSize", ["Beam", "Aperture Size"], 1),
            ("CrossOverPosition", ["Beam", "Crossover Position (mm)"], 1),
            # Scan
            ("FrameRetrace", ["Scan", "Frame Retrace (μs)"], 1),
            ("LineRetrace", ["Scan", "Line Retrace (μs)"], 1),
            ("AveragingMode", ["Scan", "Averaging Mode"], 1),
            ("NumAverages", ["Scan", "Number of Averages"], 1),
            ("ScanRotate", ["Scan", "Rotation (degrees)"], 1),
            ("DwellTime", ["Scan", "Dwell Time (μs)"], 1),
            ("SAS.ScanSize", ["Scan", "Scan Size"], 1),
            # Stage
            ("StageX", ["Stage Position", "X (μm)"], 1),
            ("StageY", ["Stage Position", "Y (μm)"], 1),
            ("StageZ", ["Stage Position", "Z (mm)"], 1),
            ("StageTilt", ["Stage Position", "Tilt (degrees)"], 1),
            ("StageRotate", ["Stage Position", "Rotation (degrees)"], 1),
            ("Stage.XLocation", ["Stage Position", "X Location (μm)"], 1),
            ("Stage.YLocation", ["Stage Position", "Y Location (μm)"], 1),
            # Optics
            ("sFimFOV", ["Optics", "sFIM Field of View (μm)"], 1),
            ("McXShift", ["Optics", "MC X Shift (μrad)"], 1),
            ("McXTilt", ["Optics", "MC X Tilt (μrad)"], 1),
            ("McYShift", ["Optics", "MC Y Shift (μrad)"], 1),
            ("McYTilt", ["Optics", "MC Y Tilt (μrad)"], 1),
            ("ColumnMag", ["Optics", "Column Magnification"], 1),
            ("ColumnMode", ["Optics", "Column Mode"], 1),
            ("Lens1Voltage", ["Optics", "Lens 1 Voltage (kV)"], 1e-3),
            ("Lens2Voltage", ["Optics", "Lens 2 Voltage (kV)"], 1e-3),
            # Detector
            ("DetectorName", ["Detector", "Name"], 1),
            ("ETGridVoltage", ["Detector", "ET Grid Voltage (V)"], 1),
            ("ETContrast", ["Detector", "ET Contrast"], 1),
            ("ETBrightness", ["Detector", "ET Brightness"], 1),
            ("ETImageIntensity", ["Detector", "ET Image Intensity"], 1),
            ("MCPContrast", ["Detector", "MCP Contrast"], 1),
            ("MCPBrightness", ["Detector", "MCP Brightness"], 1),
            ("MCPBias", ["Detector", "MCP Bias (V)"], 1),
            ("MCPImageIntensity", ["Detector", "MCP Image Intensity"], 1),
            ("Detector.Scintillator", ["Detector", "Scintillator (kV)"], 1e-3),
            ("SampleBiasVoltage", ["Detector", "Sample Bias (V)"], 1),
            # System
            ("GunPressure", ["System", "Gun Pressure (Torr)"], 1),
            ("ColumnPressure", ["System", "Column Pressure (Torr)"], 1),
            ("ChamberPressure", ["System", "Chamber Pressure (Torr)"], 1),
            ("GunTemp", ["System", "Gun Temperature (K)"], 1),
            ("HeliumPressure", ["System", "Helium Pressure (Torr)"], 1),
            ("Magnification4x5", ["Optics", "Magnification 4x5"], 1),
            ("MagnificationDisplay", ["Optics", "Magnification Display (x)"], 1),
            ("System.Model", ["System", "Model"], 1),
            ("System.Name", ["System", "Name"], 1),
            ("TimeStamp", ["System", "Acquisition Date/Time"], 1),
            ("ColumnType", ["System", "Column Type"], 1),
            # Flood gun
            ("FloodGunMode", ["Flood Gun", "Mode"], 1),
            ("FloodGunEnergy", ["Flood Gun", "Energy (eV)"], 1),
            ("FloodGunTime", ["Flood Gun", "Time (μs)"], 1),
            ("FloodGun.DeflectionX", ["Flood Gun", "Deflection X"], 1),
            ("FloodGun.DeflectionY", ["Flood Gun", "Deflection Y"], 1),
            # Misc
            ("ScalingX", ["Calibration", "X Scale (m)"], 1),
            ("ScalingY", ["Calibration", "Y Scale (m)"], 1),
            ("ImageWidth", ["Image", "Width (pixels)"], 1),
            ("ImageHeight", ["Image", "Height (pixels)"], 1),
            # Display
            ("LutMode", ["Display", "LUT Mode"], 1),
            ("LowGray", ["Display", "Low Gray Value"], 1),
            ("HighGray", ["Display", "High Gray Value"], 1),
            ("LUT.LUTGamma", ["Display", "LUT Gamma"], 1),
        ]

        # Extract all fields
        for field_path, output_key, conversion_factor in fields:
            self._parse_zeiss_field(
                root, field_path, output_key, mdict, conversion_factor
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

        # Define sections and their fields:
        #   (section_name, [(field, output_key, conversion_factor)])  # noqa: ERA001
        sections = {
            "Application": [
                ("Version", ["Application", "Software Version"], 1),
                ("Date", ["Application", "Acquisition Date/Time"], 1),
                ("SupportsTransparency", ["Application", "Supports Transparency"], 1),
                (
                    "TransparentPixelValue",
                    ["Application", "Transparent Pixel Value"],
                    1,
                ),
            ],
            "Image": [
                ("Width", ["Image", "Width (pixels)"], 1),
                ("Height", ["Image", "Height (pixels)"], 1),
                ("BoundingBox.Left", ["Image", "Bounding Box Left"], 1),
                ("BoundingBox.Right", ["Image", "Bounding Box Right"], 1),
                ("BoundingBox.Top", ["Image", "Bounding Box Top"], 1),
                ("BoundingBox.Bottom", ["Image", "Bounding Box Bottom"], 1),
                ("Machine", ["Image", "Machine Name"], 1),
                ("Beam", ["Image", "Beam Type"], 1),
                ("Aperture", ["Image", "Aperture Description"], 1),
                ("Detector", ["Detector", "Name"], 1),
                ("Contrast", ["Detector", "Contrast"], 1),
                ("Brightness", ["Detector", "Brightness"], 1),
            ],
            "Scan": [
                ("Dwell", ["Scan", "Pixel Dwell Time (μs)"], 1e-3),  # Convert ns to μs
                ("LineAvg", ["Scan", "Line Averaging"], 1),
                ("FOV_X", ["Scan", "Field of View X (μm)"], 1),
                ("FOV_Y", ["Scan", "Field of View Y (μm)"], 1),
                ("ScanRot", ["Scan", "Scan Rotation (degrees)"], 1),
                ("Ux", ["Scan", "Affine Ux"], 1),
                ("Uy", ["Scan", "Affine Uy"], 1),
                ("Vx", ["Scan", "Affine Vx"], 1),
                ("Vy", ["Scan", "Affine Vy"], 1),
                ("Focus", ["Scan", "Focus Value"], 1),
                ("StigX", ["Scan", "Stigmator X Value"], 1),
                ("StigY", ["Scan", "Stigmator Y Value"], 1),
            ],
            "Stage": [
                ("X", ["Stage Position", "X (μm)"], 1),
                ("Y", ["Stage Position", "Y (μm)"], 1),
                ("Z", ["Stage Position", "Z (μm)"], 1),
                ("Tilt", ["Stage Position", "Tilt (degrees)"], 1),
                ("Rot", ["Stage Position", "Rotation (degrees)"], 1),
                ("M", ["Stage Position", "M (mm)"], 1),
            ],
            "BeamInfo": [
                ("BeamI", ["Beam", "Beam Current (pA)"], 1),
                ("AccV", ["Beam", "Acceleration Voltage (kV)"], 1e-3),
                ("Aperture", ["Beam", "Aperture"], 1),
                ("GFISGas", ["Beam", "GFIS Gas Type"], 1),
                ("GunGasPressure", ["Beam", "Gun Gas Pressure"], 1),
                ("SpotControl", ["Beam", "Spot Control"], 1),
            ],
            "DetectorInfo": [
                ("Collector", ["Detector", "Collector Voltage (V)"], "strip_units"),
                ("Stage Bias", ["Detector", "Stage Bias Voltage (V)"], "strip_units"),
            ],
        }

        # Extract fields from each section
        for section_name, fields in sections.items():
            section = self._find_fibics_section(root, section_name)
            if section is not None:
                for field_name, output_key, conversion_factor in fields:
                    value = self._parse_fibics_value(
                        section, field_name, conversion_factor
                    )
                    if value is not None:
                        set_nested_dict_value(
                            mdict,
                            ["nx_meta", output_key]
                            if isinstance(output_key, str)
                            else ["nx_meta", *output_key],
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
