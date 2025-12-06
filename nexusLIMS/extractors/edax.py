"""Parse metadata from EDAX EDS spectra saved as .spc and .msa files."""

import logging
from pathlib import Path
from typing import Dict

from hyperspy.io import load

from nexusLIMS.extractors.utils import _set_instr_name_and_time
from nexusLIMS.utils import try_getting_dict_value

logger = logging.getLogger(__name__)


def get_spc_metadata(filename: Path) -> Dict | None:
    """
    Return the metadata (as a dict) from a .spc file.

    This type of file is produced by EDAX EDS software. It is read by HyperSpy's
    file reader and relevant metadata extracted and returned

    Parameters
    ----------
    filename
        path to a .spc file saved by EDAX software (Genesis, TEAM, etc.)

    Returns
    -------
    metadata : Optional[Dict]
        The metadata of interest extracted from the file. If None, the file
        could not be opened
    """
    mdict = {"nx_meta": {}}

    # assume all .spc datasets are EDS single spectra
    mdict["nx_meta"]["DatasetType"] = "Spectrum"
    mdict["nx_meta"]["Data Type"] = "EDS_Spectrum"

    _set_instr_name_and_time(mdict, filename)

    s = load(filename, lazy=True)

    # original_metadata puts the entire xml under the root node "spc_header",
    # so this will just bump that all up to the root level for ease of use.
    mdict["original_metadata"] = s.original_metadata["spc_header"].as_dictionary()

    term_mapping = {
        "azimuth": "Azimuthal Angle (deg)",
        "liveTime": "Live Time (s)",
        "detReso": "Detector Energy Resolution (eV)",
        "elevation": "Elevation Angle (deg)",
        "evPerChan": "Channel Size (eV)",
        "kV": "Accelerating Voltage (kV)",
        "numPts": "Number of Spectrum Channels",
        "startEnergy": "Starting Energy (keV)",
        "endEnergy": "Ending Energy (keV)",
        "tilt": "Stage Tilt (deg)",
    }

    for in_term, out_term in term_mapping.items():
        if try_getting_dict_value(mdict["original_metadata"], in_term) != "not found":
            mdict["nx_meta"][out_term] = mdict["original_metadata"][in_term]

    # add any elements present:
    if "Sample" in s.metadata and "elements" in s.metadata.Sample:
        mdict["nx_meta"]["Elements"] = s.metadata.Sample.elements

    return mdict


def get_msa_metadata(filename: Path) -> Dict | None:
    """
    Return the metadata (as a dict) from an .msa spectrum file.

    This file may be saved by a number of different EDS acquisition software, but
    most often is produced as an export from EDAX or Oxford software. This format is
    a standard, but vendors (such as EDAX) often add other values into the metadata
    header. See https://www.microscopy.org/resources/scientific_data/ for the fomal
    specification.

    Parameters
    ----------
    filename
        path to a .msa file saved by various EDS software packages

    Returns
    -------
    metadata : Optional[Dict]
        The metadata of interest extracted from the file. If None, the file
        could not be opened
    """
    s = load(filename, lazy=False)
    mdict = {"nx_meta": {}}
    mdict["original_metadata"] = s.original_metadata.as_dictionary()

    # assume all .spc datasets are EDS single spectra
    mdict["nx_meta"]["DatasetType"] = "Spectrum"
    mdict["nx_meta"]["Data Type"] = "EDS_Spectrum"

    _set_instr_name_and_time(mdict, filename)

    term_mapping = {
        "AZIMANGLE-dg": "Azimuthal Angle (deg)",
        "AmpTime (usec)": "Amplifier Time (μs)",
        "Analyzer Type": "Analyzer Type",
        "BEAMKV   -kV": "Beam Energy (keV)",
        "CHOFFSET": "Channel Offset",
        "COMMENT": "EDAX Comment",
        "DATATYPE": "Data Format",
        "DATE": "EDAX Date",
        "ELEVANGLE-dg": "Elevation Angle (deg)",
        "Elements": "User-Selected Elements",
        "FILENAME": "Originating File of MSA Export",
        "FORMAT": "File Format",
        "FPGA Version": "FPGA Version",
        "LIVETIME  -s": "Live Time (s)",
        "NCOLUMNS": "Number of Data Columns",
        "NPOINTS": "Number of Data Points",
        "OFFSET": "Offset",
        "OWNER": "EDAX Owner",
        "REALTIME  -s": "Real Time (s)",
        "RESO (MnKa)": "Energy Resolution (eV)",
        "SIGNALTYPE": "Signal Type",
        "TACTYLR  -cm": "Active Layer Thickness (cm)",
        "TBEWIND  -cm": "Be Window Thickness (cm)",
        "TDEADLYR -cm": "Dead Layer Thickness (cm)",
        "TIME": "EDAX Time",
        "TITLE": "EDAX Title",
        "TakeOff Angle": "TakeOff Angle (deg)",
        "Tilt Angle": "Stage Tilt (deg)",
        "VERSION": "MSA Format Version",
        "XLABEL": "X Column Label",
        "XPERCHAN": "X Units Per Channel",
        "XUNITS": "X Column Units",
        "YLABEL": "Y Column Label",
        "YUNITS": "Y Column Units",
    }

    for in_term, out_term in term_mapping.items():
        if try_getting_dict_value(mdict["original_metadata"], in_term) != "not found":
            mdict["nx_meta"][out_term] = mdict["original_metadata"][in_term]

    return mdict
