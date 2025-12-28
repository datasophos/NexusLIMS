"""EDAX EDS spectrum (.spc/.msa) extractor plugin."""

import contextlib
import logging
from typing import Any, ClassVar

from hyperspy.io import load

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.utils import _set_instr_name_and_time, add_to_extensions
from nexusLIMS.instruments import get_instr_from_filepath
from nexusLIMS.schemas.units import ureg
from nexusLIMS.utils import try_getting_dict_value

logger = logging.getLogger(__name__)


class SpcExtractor:
    """
    Extractor for EDAX .spc files.

    This extractor handles metadata extraction from .spc files saved by
    EDAX EDS software (Genesis, TEAM, etc.).
    """

    name = "spc_extractor"
    priority = 100
    supported_extensions: ClassVar = {"spc"}

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
            True if file extension is .spc
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "spc"

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from a .spc file.

        Returns the metadata (as a list of dicts) from a .spc file.
        This type of file is produced by EDAX EDS software. It is read by HyperSpy's
        file reader and relevant metadata extracted and returned

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        list[dict]
            List containing a single metadata dict with 'nx_meta' key.
            If None, the file could not be opened
        """
        filename = context.file_path
        logger.debug("Extracting metadata from SPC file: %s", filename)

        mdict = {"nx_meta": {}}

        # assume all .spc datasets are EDS single spectra
        mdict["nx_meta"]["DatasetType"] = "Spectrum"
        mdict["nx_meta"]["Data Type"] = "EDS_Spectrum"

        _set_instr_name_and_time(mdict, filename)

        s = load(filename, lazy=True)

        # original_metadata puts the entire xml under the root node "spc_header",
        # so this will just bump that all up to the root level for ease of use.
        mdict["original_metadata"] = s.original_metadata["spc_header"].as_dictionary()

        # Map input field names to (output_name, unit) tuples
        # If unit is None, value is stored as-is; otherwise, create Pint Quantity
        term_mapping = {
            "azimuth": ("Azimuthal Angle", "degree"),
            "liveTime": ("Live Time", "second"),
            "detReso": ("Detector Energy Resolution", "electron_volt"),
            "elevation": ("Elevation Angle", "degree"),
            "evPerChan": ("Channel Size", "electron_volt"),
            "kV": ("Accelerating Voltage", "kilovolt"),
            "numPts": ("Number of Spectrum Channels", None),
            "startEnergy": ("Starting Energy", "kiloelectron_volt"),
            "endEnergy": ("Ending Energy", "kiloelectron_volt"),
            "tilt": ("Stage Tilt", "degree"),
        }

        for in_term, (out_name, unit) in term_mapping.items():
            val = try_getting_dict_value(mdict["original_metadata"], in_term)
            if val is not None:
                if unit is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        val = ureg.Quantity(val, unit)
                mdict["nx_meta"][out_name] = val

        # add any elements present:
        if "Sample" in s.metadata and "elements" in s.metadata.Sample:
            mdict["nx_meta"]["Elements"] = s.metadata.Sample.elements

        # Move vendor-specific fields to extensions
        mdict = self._migrate_to_schema_compliant_metadata(mdict)

        return [mdict]

    def _migrate_to_schema_compliant_metadata(self, mdict: dict) -> dict:
        """
        Migrate metadata to schema-compliant format.

        Moves EDAX-specific fields to extensions section.

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
        extensions = {}

        # These EDAX-specific fields go to extensions
        vendor_fields = {
            "Azimuthal Angle",
            "Live Time",
            "Detector Energy Resolution",
            "Elevation Angle",
            "Channel Size",
            "Accelerating Voltage",
            "Number of Spectrum Channels",
            "Starting Energy",
            "Ending Energy",
            "Stage Tilt",
            "Elements",
        }

        # Build new nx_meta with core fields only
        new_nx_meta = {}
        for field in [
            "DatasetType",
            "Data Type",
            "Creation Time",
            "Instrument ID",
            "warnings",
        ]:
            if field in nx_meta:
                new_nx_meta[field] = nx_meta[field]

        # Move vendor fields to extensions
        for field_name, value in nx_meta.items():
            if field_name in vendor_fields:
                extensions[field_name] = value
            elif field_name not in new_nx_meta:
                # Any other unknown fields also go to extensions
                extensions[field_name] = value

        # Add extensions if we have any
        for key, value in extensions.items():
            add_to_extensions(new_nx_meta, key, value)

        mdict["nx_meta"] = new_nx_meta
        return mdict


class MsaExtractor:
    """
    Extractor for EMSA/MAS .msa spectrum files.

    This extractor handles metadata extraction from .msa files, which may be
    saved by various EDS acquisition software packages, most commonly as exports
    from EDAX or Oxford software.
    """

    name = "msa_extractor"
    priority = 100
    supported_extensions: ClassVar = {"msa"}

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
            True if file extension is .msa
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "msa"

    def extract(self, context: ExtractionContext) -> list[dict[str, Any]]:
        """
        Extract metadata from an .msa file.

        Returns the metadata (as a list of dicts) from an .msa spectrum file.
        This file may be saved by a number of different EDS acquisition software, but
        most often is produced as an export from EDAX or Oxford software. This format is
        a standard, but vendors (such as EDAX) often add other values into the metadata
        header. See https://www.microscopy.org/resources/scientific_data/ for the fomal
        specification.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        list[dict]
            List containing a single metadata dict with 'nx_meta' key.
            If None, the file could not be opened
        """
        filename = context.file_path
        logger.debug("Extracting metadata from MSA file: %s", filename)

        s = load(filename, lazy=False)
        mdict = {"nx_meta": {}}
        mdict["original_metadata"] = s.original_metadata.as_dictionary()

        # assume all .spc datasets are EDS single spectra
        mdict["nx_meta"]["DatasetType"] = "Spectrum"
        mdict["nx_meta"]["Data Type"] = "EDS_Spectrum"

        _set_instr_name_and_time(mdict, filename)

        # Map input field names to (output_name, unit) tuples
        # If unit is None, value is stored as-is; otherwise, create Pint Quantity
        term_mapping = {
            "AZIMANGLE-dg": ("Azimuthal Angle", "degree"),
            "AmpTime (usec)": ("Amplifier Time", "microsecond"),
            "Analyzer Type": ("Analyzer Type", None),
            "BEAMKV   -kV": ("Beam Energy", "kiloelectron_volt"),
            "CHOFFSET": ("Channel Offset", None),
            "COMMENT": ("EDAX Comment", None),
            "DATATYPE": ("Data Format", None),
            "DATE": ("EDAX Date", None),
            "ELEVANGLE-dg": ("Elevation Angle", "degree"),
            "Elements": ("User-Selected Elements", None),
            "FILENAME": ("Originating File of MSA Export", None),
            "FORMAT": ("File Format", None),
            "FPGA Version": ("FPGA Version", None),
            "LIVETIME  -s": ("Live Time", "second"),
            "NCOLUMNS": ("Number of Data Columns", None),
            "NPOINTS": ("Number of Data Points", None),
            "OFFSET": ("Offset", None),
            "OWNER": ("EDAX Owner", None),
            "REALTIME  -s": ("Real Time", "second"),
            "RESO (MnKa)": ("Energy Resolution", "electron_volt"),
            "SIGNALTYPE": ("Signal Type", None),
            "TACTYLR  -cm": ("Active Layer Thickness", "centimeter"),
            "TBEWIND  -cm": ("Be Window Thickness", "centimeter"),
            "TDEADLYR -cm": ("Dead Layer Thickness", "centimeter"),
            "TIME": ("EDAX Time", None),
            "TITLE": ("EDAX Title", None),
            "TakeOff Angle": ("TakeOff Angle", "degree"),
            "Tilt Angle": ("Stage Tilt", "degree"),
            "VERSION": ("MSA Format Version", None),
            "XLABEL": ("X Column Label", None),
            "XPERCHAN": ("X Units Per Channel", None),
            "XUNITS": ("X Column Units", None),
            "YLABEL": ("Y Column Label", None),
            "YUNITS": ("Y Column Units", None),
        }

        for in_term, (out_name, unit) in term_mapping.items():
            val = try_getting_dict_value(mdict["original_metadata"], in_term)
            if val is not None:
                if unit is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        val = ureg.Quantity(val, unit)
                mdict["nx_meta"][out_name] = val

        # Move vendor-specific fields to extensions
        mdict = self._migrate_to_schema_compliant_metadata(mdict)

        return [mdict]

    def _migrate_to_schema_compliant_metadata(self, mdict: dict) -> dict:
        """
        Migrate metadata to schema-compliant format.

        Moves EDAX/EMSA-specific fields to extensions section.

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
        extensions = {}

        # These EDAX/EMSA-specific fields go to extensions
        vendor_fields = {
            "Azimuthal Angle",
            "Live Time",
            "Detector Energy Resolution",
            "Elevation Angle",
            "Channel Size",
            "Accelerating Voltage",
            "Number of Spectrum Channels",
            "Starting Energy",
            "Ending Energy",
            "Stage Tilt",
            "Elements",
        }

        # Build new nx_meta with core fields only
        new_nx_meta = {}
        for field in [
            "DatasetType",
            "Data Type",
            "Creation Time",
            "Instrument ID",
            "warnings",
        ]:
            if field in nx_meta:
                new_nx_meta[field] = nx_meta[field]

        # Move vendor fields to extensions
        for field_name, value in nx_meta.items():
            if field_name in vendor_fields:
                extensions[field_name] = value
            elif field_name not in new_nx_meta:
                # Any other unknown fields also go to extensions
                extensions[field_name] = value

        # Add extensions if we have any
        for key, value in extensions.items():
            add_to_extensions(new_nx_meta, key, value)

        mdict["nx_meta"] = new_nx_meta
        return mdict


# Backward compatibility functions for tests
def get_spc_metadata(filename):
    """
    Get metadata from a .spc file.

    .. deprecated::
        This function is deprecated. Use SpcExtractor class instead.

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
    extractor = SpcExtractor()
    return extractor.extract(context)


def get_msa_metadata(filename):
    """
    Get metadata from an .msa file.

    .. deprecated::
        This function is deprecated. Use MsaExtractor class instead.

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
    extractor = MsaExtractor()
    return extractor.extract(context)
