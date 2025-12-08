"""FEI/Thermo Fisher TIFF extractor plugin."""

import configparser
import contextlib
import io
import logging
import re
from decimal import Decimal, InvalidOperation
from math import degrees
from pathlib import Path
from typing import Any, Tuple

from lxml import etree

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.utils import _set_instr_name_and_time
from nexusLIMS.utils import set_nested_dict_value, sort_dict, try_getting_dict_value

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class QuantaTiffExtractor:
    """
    Extractor for FEI/Thermo Fisher TIFF files.

    This extractor handles metadata extraction from .tif files saved by
    FEI/Thermo Fisher FIBs and SEMs (e.g., Quanta, Helios, etc.).
    """

    name = "quanta_tif_extractor"
    priority = 100

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this extractor supports the given file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if file extension is .tif or .tiff
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension in {"tif", "tiff"}

    def extract(self, context: ExtractionContext) -> dict[str, Any]:
        """
        Extract metadata from a FEI/Thermo TIFF file.

        Returns the metadata (as a dictionary) from a .tif file saved by the FEI
        Quanta SEM in the Nexus Microscopy Facility. Specific tags of interest are
        duplicated under the root-level ``nx_meta`` node in the dictionary.

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
        logger.debug("Extracting metadata from FEI TIFF file: %s", filename)

        with filename.open(mode="rb") as f:
            content = f.read()
        user_idx = content.find(b"[User]")

        mdict = {"nx_meta": {}}
        # assume all datasets coming from Quanta are Images, currently
        mdict["nx_meta"]["DatasetType"] = "Image"
        mdict["nx_meta"]["Data Type"] = "SEM_Imaging"

        _set_instr_name_and_time(mdict, filename)

        # if the user_idx is -1, it means the [User] tag was not found in the
        # file, and so the metadata is missing (so we should just return 0)
        if user_idx == -1:
            logger.warning("Did not find expected FEI tags in .tif file: %s", filename)
            mdict["nx_meta"]["Data Type"] = "Unknown"
            mdict["nx_meta"]["Extractor Warnings"] = (
                "Did not find expected FEI tags. Could not read metadata"
            )
            mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

            return mdict

        metadata_bytes = content[user_idx:]
        # remove any null bytes since they break the extractor
        metadata_bytes = metadata_bytes.replace(b"\x00", b"")
        metadata_str = metadata_bytes.decode().replace("\r\n", "\n")
        metadata_str = metadata_str.replace("\r", "\n")
        metadata_str = _fix_duplicate_multigis_metadata_tags(metadata_str)

        # test if file has XML metadata and if so, extract it separately
        metadata_str, mdict["FEI_XML_Metadata"] = _detect_and_process_xml_metadata(
            metadata_str,
        )

        buf = io.StringIO(metadata_str)
        config = configparser.ConfigParser()
        # make ConfigParser respect upper/lowercase values
        config.optionxform = lambda option: option
        config.read_file(buf)

        for itm in config.items():
            if itm[0] == "DEFAULT":
                pass
            else:
                mdict[itm[0]] = {}
                for k, v in itm[1].items():
                    mdict[itm[0]][k] = v

        mdict = parse_nx_meta(mdict)

        # sort the nx_meta dictionary (recursively) for nicer display
        mdict["nx_meta"] = sort_dict(mdict["nx_meta"])

        return mdict


def _detect_and_process_xml_metadata(
    metadata_str: str,
) -> Tuple[str, dict]:
    """
    Find and (if necessary) parse XML metadata in a Thermo Fisher FIB/SEM TIF file.

    Some Thermo Fisher FIB/SEM files have additional metadata embedded as XML at the end
    of the TIF file, which cannot be handled by the ``ConfigParser`` implementation of
    :py:meth:`get_quanta_metadata`. This method will detect, parse, and remove the XML
    from the metadata if present.

    Parameters
    ----------
    metadata_str
        The metadata at the end of the TIF file as a string. May or may not include
        an XML section (this depends on the version of the Thermo software that saved
        the image).

    Returns
    -------
    metadata_str
        The originally provided metadata as a string, but with the XML portion removed
        if it was present

    xml_metadata
        A dictionary containing the metadata that was present in the XML portion. Will
        be an empty dictionary if there was no XML.
    """
    xml_regex = re.compile(r'<\?xml version=".+"\?>')
    regex_match = xml_regex.search(metadata_str)
    if regex_match:
        # there is an xml declaration in the metadata of this file, so parse it:
        xml_str = metadata_str[regex_match.span()[0] :]
        metadata_str = metadata_str[: regex_match.span()[0]]
        root = etree.fromstring(xml_str)
        return metadata_str, _xml_el_to_dict(root)

    return metadata_str, {}


def _xml_el_to_dict(node: etree.ElementBase):
    """
    Convert an lxml.etree node tree into a dict.

    This is used to transform the XML metadata section into a dictionary representation
    so it can be stored alongside the other metadata.

    Taken from https://stackoverflow.com/a/66103841/1435788
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
            value = _xml_el_to_dict(element)
        if key in result:
            if isinstance(result[key], list):
                result[key].append(value)  # pragma: no cover
            else:
                tempvalue = result[key].copy()
                result[key] = [tempvalue, value]
        else:
            result[key] = value
    return result


def _fix_duplicate_multigis_metadata_tags(metadata_str: str) -> str:
    """
    Rename the metadata section headers to allow parsing by ``ConfigParser``.

    Some instruments have metadata section titles like so:

        [MultiGIS]
        [MultiGISUnit1]
        [MultiGISGas1]
        [MultiGISGas2]
        [MultiGISGas3]
        [MultiGISUnit2]
        [MultiGISGas1]
        [MultiGISGas2]
        [MultiGISGas3]
        [MultiGISUnit3]
        [MultiGISGas1]
        [MultiGISGas2]
        [MultiGISGas3]

    Which causes errors because ``ConfigParser`` raises a ``DuplicateSectionError`` on
    the first time it sees a duplicate of ``MultiGISGas1``. As a workaround, this method
    will modify an entire string of "Quanta" metadata so that it instead reads like so:

        [MultiGIS]
        [MultiGISUnit1]
        [MultiGISUnit1.MultiGISGas1]
        [MultiGISUnit1.MultiGISGas2]
        [MultiGISUnit1.MultiGISGas3]
        [MultiGISUnit2]
        [MultiGISUnit2.MultiGISGas1]
        [MultiGISUnit2.MultiGISGas2]
        [MultiGISUnit2.MultiGISGas3]
        [MultiGISUnit3]
        [MultiGISUnit3.MultiGISGas1]
        [MultiGISUnit3.MultiGISGas2]
        [MultiGISUnit3.MultiGISGas3]

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


def parse_nx_meta(mdict):
    """
    Parse metadata into NexusLIMS format.

    Parse the "important" metadata that is saved at specific places within
    the Quanta tag structure into a consistent place in the metadata dictionary
    returned by :py:meth:`get_quanta_metadata`.

    The metadata contained in the XML section (if present) is not parsed, since it
    appears to only contain duplicates or slightly renamed metadata values compared
    to the typical config-style section that is always present.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    # The name of the beam, scan, and detector will determine which sections are
    # present (have not seen more than one beam/detector -- although likely
    # will be the case for dual beam FIB/SEM)
    beam_name = try_getting_dict_value(mdict, ["Beam", "Beam"])
    det_name = try_getting_dict_value(mdict, ["Detectors", "Name"])
    scan_name = try_getting_dict_value(mdict, ["Beam", "Scan"])

    # some parsers are broken off into helper methods:
    mdict = parse_beam_info(mdict, beam_name)
    mdict = parse_scan_info(mdict, scan_name)
    mdict = parse_det_info(mdict, det_name)
    mdict = parse_system_info(mdict)

    # process the rest of the metadata tags:

    # process beam spot size
    val = try_getting_dict_value(mdict, ["Beam", "Spot"])
    if val != "not found":
        with contextlib.suppress(ValueError, InvalidOperation):
            val = Decimal(val)
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Spot Size"],
            float(val) if isinstance(val, Decimal) else val,
        )

    mdict = parse_image_info(mdict)

    # test for specimen temperature value if present and non-empty
    temp_val = try_getting_dict_value(mdict, ["Specimen", "Temperature"])
    if temp_val not in ("not found", ""):
        with contextlib.suppress(ValueError, InvalidOperation):
            temp_val = Decimal(temp_val)
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Specimen Temperature (K)"],
            float(temp_val) if isinstance(temp_val, Decimal) else temp_val,
        )

    # parse SpecTilt (think this is specimen pre-tilt, but not definite)
    # # tests showed that this is always the same value as StageT, so we do not
    # # need to parse this one

    # if val != 'not found' and val != '0':
    #     set_nested_dict_value(mdict, ['nx_meta', 'Stage Position',
    #                                'Specimen Tilt'], val)

    # Get user ID (sometimes it's not correct because the person left the
    # instrument logged in as the previous user, so make sure to add it to
    # the warnings list
    user_val = try_getting_dict_value(mdict, ["User", "User"])
    if user_val != "not found":
        set_nested_dict_value(mdict, ["nx_meta", "Operator"], user_val)
        mdict["nx_meta"]["warnings"].append(["Operator"])

    # parse acquisition date and time
    acq_date_val = try_getting_dict_value(mdict, ["User", "Date"])
    acq_time_val = try_getting_dict_value(mdict, ["User", "Time"])
    if acq_date_val != "not found":
        set_nested_dict_value(mdict, ["nx_meta", "Acquisition Date"], acq_date_val)
    if acq_time_val != "not found":
        set_nested_dict_value(mdict, ["nx_meta", "Acquisition Time"], acq_time_val)

    # parse vacuum mode
    vac_val = try_getting_dict_value(mdict, ["Vacuum", "UserMode"])
    if user_val != "not found":
        set_nested_dict_value(mdict, ["nx_meta", "Vacuum Mode"], vac_val)

    # parse chamber pressure
    ch_pres_val = try_getting_dict_value(mdict, ["Vacuum", "ChPressure"])
    if ch_pres_val not in ("not found", ""):
        # keep track of original digits so we don't propagate float errors
        with contextlib.suppress(InvalidOperation):
            ch_pres_val = Decimal(ch_pres_val)
        if try_getting_dict_value(mdict, ["nx_meta", "Vacuum Mode"]) == "High vacuum":
            ch_pres_str = "Chamber Pressure (mPa)"
            ch_pres_val = ch_pres_val * 10**3
        else:
            ch_pres_str = "Chamber Pressure (Pa)"
        set_nested_dict_value(
            mdict,
            ["nx_meta", ch_pres_str],
            float(ch_pres_val) if isinstance(ch_pres_val, Decimal) else ch_pres_val,
        )

    return mdict


def parse_beam_info(mdict, beam_name):
    """
    Parse the "Beam info" section of the metadata.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`
    beam_name : str
        The "beam name" read from the root-level ``Beam`` node of the
        metadata dictionary

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    if beam_name == "not found":
        return mdict

    # Values are in SI units, but we want easy to display, so include the
    # exponential factor that will get us from input unit (such as seconds)
    # to output unit (such as μs -- meaning factor = 6)
    to_parse = [
        ([beam_name, "EmissionCurrent"], ["Emission Current (μA)"], 6),
        ([beam_name, "HFW"], ["Horizontal Field Width (μm)"], 6),
        ([beam_name, "HV"], ["Voltage (kV)"], -3),
        ([beam_name, "SourceTiltX"], ["Beam Tilt X"], 0),
        ([beam_name, "SourceTiltY"], ["Beam Tilt Y"], 0),
        ([beam_name, "StageR"], ["Stage Position", "R"], 0),
        ([beam_name, "StageTa"], ["Stage Position", "α"], 0),  # noqa: RUF001
        # all existing quanta images have a value of zero for beta
        # ([beam_name, 'StageTb'], ['Stage Position', 'β'], 0),  # noqa: ERA001
        ([beam_name, "StageX"], ["Stage Position", "X"], 0),
        ([beam_name, "StageY"], ["Stage Position", "Y"], 0),
        ([beam_name, "StageZ"], ["Stage Position", "Z"], 0),
        ([beam_name, "StigmatorX"], ["Stigmator X Value"], 0),
        ([beam_name, "StigmatorY"], ["Stigmator Y Value"], 0),
        ([beam_name, "VFW"], ["Vertical Field Width (μm)"], 6),
        ([beam_name, "WD"], ["Working Distance (mm)"], 3),
    ]
    for m_in, m_out, factor in to_parse:
        val = try_getting_dict_value(mdict, m_in)
        if val not in ("not found", ""):
            val = Decimal(val) * Decimal(str(10**factor))
            set_nested_dict_value(
                mdict,
                ["nx_meta", *m_out],
                float(val) if isinstance(val, Decimal) else val,
            )

    # Add beam name to metadata:
    set_nested_dict_value(mdict, ["nx_meta", "Beam Name"], beam_name)

    # BeamShiftX and BeamShiftY require an additional test:
    bs_x_val = try_getting_dict_value(mdict, [beam_name, "BeamShiftX"])
    bs_y_val = try_getting_dict_value(mdict, [beam_name, "BeamShiftY"])
    if bs_x_val != "not found" and Decimal(bs_x_val) != 0:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Beam Shift X"],
            float(Decimal(bs_x_val)),
        )
    if bs_y_val != "not found" and Decimal(bs_y_val) != 0:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Beam Shift Y"],
            float(Decimal(bs_y_val)),
        )

    # only parse scan rotation if value is not zero:
    # Not sure what the units of this value are... looks like radians because
    # unique values range from 0 to 6.24811 - convert to degrees for display
    scan_rot_val = try_getting_dict_value(mdict, [beam_name, "ScanRotation"])
    if scan_rot_val != "not found" and Decimal(scan_rot_val) != 0:
        scan_rot_dec = Decimal(scan_rot_val)  # make scan_rot a Decimal
        # get number of digits in Decimal value (so we don't artificially
        # introduce extra precision)
        digits = abs(scan_rot_dec.as_tuple().exponent)
        # round the final float value to that number of digits
        scan_rot_val = round(degrees(scan_rot_dec), digits)
        set_nested_dict_value(mdict, ["nx_meta", "Scan Rotation (°)"], scan_rot_val)

    # TiltCorrectionAngle only if TiltCorrectionIsOn == 'yes'
    tilt_corr_on = try_getting_dict_value(mdict, [beam_name, "TiltCorrectionIsOn"])
    if tilt_corr_on == "yes":
        tilt_corr_val = try_getting_dict_value(
            mdict,
            [beam_name, "TiltCorrectionAngle"],
        )
        if tilt_corr_val != "not found":
            tilt_corr_val = float(Decimal(tilt_corr_val))
            set_nested_dict_value(
                mdict,
                ["nx_meta", "Tilt Correction Angle"],
                tilt_corr_val,
            )

    return mdict


def parse_scan_info(mdict, scan_name):
    """
    Parse the "Scan info" section of the metadata.

    Parses the `Scan` portion of the metadata dictionary (on a Quanta this is
    always `"EScan"`) to get values such as dwell time, field width, and pixel
    size.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`
    scan_name : str
        The "scan name" read from the root-level ``Beam`` node of the
        metadata dictionary

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    if scan_name == "not found":
        return mdict

    # Values are in SI units, but we want easy to display, so include the
    # exponential factor that will get us from input unit (such as seconds)
    # to output unit (such as μs -- meaning factor = 6)
    to_parse = [
        ([scan_name, "Dwell"], ["Pixel Dwell Time (μs)"], 6),
        ([scan_name, "FrameTime"], ["Total Frame Time (s)"], 0),
        ([scan_name, "HorFieldsize"], ["Horizontal Field Width (μm)"], 6),
        ([scan_name, "VerFieldsize"], ["Vertical Field Width (μm)"], 6),
        ([scan_name, "PixelHeight"], ["Pixel Width (nm)"], 9),
        ([scan_name, "PixelWidth"], ["Pixel Height (nm)"], 9),
    ]

    for m_in, m_out, factor in to_parse:
        val = try_getting_dict_value(mdict, m_in)
        if val not in ("not found", ""):
            val = Decimal(val) * Decimal(str(10**factor))
            set_nested_dict_value(
                mdict,
                ["nx_meta", *m_out],
                float(val) if isinstance(val, Decimal) else val,
            )

    return mdict


def parse_det_info(mdict, det_name):
    """
    Parse the "Detector info" section of the metadata.

    Parses the `Detector` portion of the metadata dictionary from the Quanta to
    get values such as brightness, contrast, signal, etc.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`
    det_name : str
        The "detector name" read from the root-level ``Beam`` node of the
        metadata dictionary

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    if det_name == "not found":
        return mdict

    to_parse = [
        ([det_name, "Brightness"], ["Detector Brightness Setting"]),
        ([det_name, "Contrast"], ["Detector Contrast Setting"]),
        ([det_name, "EnhancedContrast"], ["Detector Enhanced Contrast Setting"]),
        ([det_name, "Signal"], ["Detector Signal"]),
        ([det_name, "Grid"], ["Detector Grid Voltage (V)"]),
        ([det_name, "Setting"], ["Detector Setting"]),
    ]

    for m_in, m_out in to_parse:
        val = try_getting_dict_value(mdict, m_in)
        if val != "not found":
            try:
                val = Decimal(val)
                if m_in == [det_name, "Setting"]:
                    # if "Setting" value is numeric, it's just the Grid
                    # voltage so skip it
                    continue
            except (ValueError, InvalidOperation):
                pass
            set_nested_dict_value(
                mdict,
                ["nx_meta", *m_out],
                float(val) if isinstance(val, Decimal) else val,
            )

    set_nested_dict_value(mdict, ["nx_meta", "Detector Name"], det_name)

    return mdict


def parse_system_info(mdict):
    """
    Parse the "System info" section of the metadata.

    Parses the `System` portion of the metadata dictionary from the Quanta to
    get values such as software version, chamber config, etc.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    if try_getting_dict_value(mdict, ["System"]) == "not found":
        return mdict

    to_parse = [
        (["System", "Chamber"], ["Chamber ID"]),
        (["System", "Pump"], ["Vacuum Pump"]),
        (["System", "SystemType"], ["System Type"]),
        (["System", "Stage"], ["Stage Description"]),
    ]

    for m_in, m_out in to_parse:
        val = try_getting_dict_value(mdict, m_in)
        if val != "not found":
            set_nested_dict_value(mdict, ["nx_meta", *m_out], val)

    # Parse software info into one output tag:
    output_vals = []
    val = try_getting_dict_value(mdict, ["System", "Software"])
    if val != "not found":
        output_vals.append(val)
    val = try_getting_dict_value(mdict, ["System", "BuildNr"])
    if val != "not found":
        output_vals.append(f"(build {val})")
    if len(output_vals) > 0:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Software Version"],
            " ".join(output_vals),
        )

    # parse column and type into one output tag:
    output_vals = []
    val = try_getting_dict_value(mdict, ["System", "Column"])
    if val != "not found":
        output_vals.append(val)
    val = try_getting_dict_value(mdict, ["System", "Type"])
    if val != "not found":
        output_vals.append(val)
    if len(output_vals) > 0:
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Column Type"],
            " ".join(output_vals),
        )

    return mdict


def parse_image_info(mdict):
    """
    Parse the "Image info" section of the metadata.

    Parses the `Image` portion of the metadata dictionary from the Quanta to
    get values such as drift correction, image integration settings, etc.

    Parameters
    ----------
    mdict : dict
        A metadata dictionary as returned by :py:meth:`get_quanta_metadata`

    Returns
    -------
    mdict : dict
        The same metadata dictionary with some values added under the
        root-level ``nx_meta`` key
    """
    # process drift correction
    val = try_getting_dict_value(mdict, ["Image", "DriftCorrected"])
    if val != "not found":
        # set to true if the value is 'On'
        val = val == "On"
        set_nested_dict_value(mdict, ["nx_meta", "Drift Correction Applied"], val)

    # process frame integration
    val = try_getting_dict_value(mdict, ["Image", "Integrate"])
    if val != "not found":
        try:
            val = int(val)
            if val > 1:
                set_nested_dict_value(mdict, ["nx_meta", "Frames Integrated"], val)
        except ValueError:
            pass

    # process mag mode
    val = try_getting_dict_value(mdict, ["Image", "MagnificationMode"])
    if val != "not found":
        with contextlib.suppress(ValueError):
            val = int(val)
        set_nested_dict_value(mdict, ["nx_meta", "Magnification Mode"], val)

    # Process "ResolutionX/Y" (data size)
    x_val = try_getting_dict_value(mdict, ["Image", "ResolutionX"])
    y_val = try_getting_dict_value(mdict, ["Image", "ResolutionY"])
    try:
        x_val = int(x_val)
        y_val = int(y_val)
    except ValueError:
        pass
    if x_val != "not found" and y_val != "not found":
        set_nested_dict_value(
            mdict,
            ["nx_meta", "Data Dimensions"],
            str((x_val, y_val)),
        )

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
    from nexusLIMS.instruments import get_instr_from_filepath

    context = ExtractionContext(file_path=filename, instrument=get_instr_from_filepath(filename))
    extractor = QuantaTiffExtractor()
    return extractor.extract(context)
