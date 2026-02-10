# pylint: disable=C0116

"""Tests for nexusLIMS.extractors.edax."""

from pathlib import Path

import pytest

from nexusLIMS.extractors.plugins.edax import get_msa_metadata, get_spc_metadata
from nexusLIMS.schemas.units import ureg

from .conftest import get_field


class TestEDAXSPCExtractor:
    """Tests nexusLIMS.extractors.edax."""

    def test_leo_edax_spc(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"
        meta = get_spc_metadata(test_file)
        assert meta is not None

        # Azimuthal Angle
        field = get_field(meta, "Azimuthal Angle")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.0
        assert str(field.units) == "degree"

        # Live Time
        field = get_field(meta, "Live Time")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 30.000002
        assert str(field.units) == "second"

        # Detector Energy Resolution
        field = get_field(meta, "Detector Energy Resolution")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 125.16211
        assert str(field.units) == "electron_volt"

        # Elevation Angle
        field = get_field(meta, "Elevation Angle")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 35.0
        assert str(field.units) == "degree"

        # Channel Size
        field = get_field(meta, "Channel Size")
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == 5
        assert str(field.units) == "electron_volt"

        # Number of Spectrum Channels (no units)
        assert get_field(meta, "Number of Spectrum Channels") == 4096

        # Stage Tilt
        field = get_field(meta, "Stage Tilt")
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == -1.0
        assert str(field.units) == "degree"

        # Starting Energy
        field = get_field(meta, "Starting Energy")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.0
        assert str(field.units) == "kiloelectron_volt"

        # Ending Energy
        field = get_field(meta, "Ending Energy")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 20.475
        assert str(field.units) == "kiloelectron_volt"

    def test_leo_edax_msa(self):  # noqa: PLR0915
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"
        meta = get_msa_metadata(test_file)
        assert meta is not None

        # Azimuthal Angle
        field = get_field(meta, "Azimuthal Angle")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.0
        assert str(field.units) == "degree"

        # Amplifier Time
        field = get_field(meta, "Amplifier Time")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 7.68
        assert str(field.units) == "microsecond"

        # Analyzer Type (no units)
        assert get_field(meta, "Analyzer Type") == "DPP4"

        # Beam Energy
        field = get_field(meta, "Beam Energy")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 10.0
        assert str(field.units) == "kiloelectron_volt"

        # Channel Offset (no units)
        assert get_field(meta, "Channel Offset") == pytest.approx(0.0)

        # EDAX Comment (no units)
        assert (
            get_field(meta, "EDAX Comment")
            == "Converted by EDAX.TeamEDS V4.5.1-RC2.20170623.3 Friday, June 23, 2017"
        )

        # Data Format (no units)
        assert get_field(meta, "Data Format") == "XY"

        # EDAX Date (no units)
        assert get_field(meta, "EDAX Date") == "29-Aug-2022"

        # Elevation Angle
        field = get_field(meta, "Elevation Angle")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 35.0
        assert str(field.units) == "degree"

        # User-Selected Elements (no units)
        assert get_field(meta, "User-Selected Elements") == "8,27,16"

        # Originating File of MSA Export (no units)
        assert (
            get_field(meta, "Originating File of MSA Export")
            == "20220829_XXXXXXXXXXXX_XXXXXX.spc"
        )

        # File Format (no units)
        assert get_field(meta, "File Format") == "EMSA/MAS Spectral Data File"

        # FPGA Version (no units)
        assert get_field(meta, "FPGA Version") == "0"

        # Live Time
        field = get_field(meta, "Live Time")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 30.0
        assert str(field.units) == "second"

        # Number of Data Columns (no units)
        assert get_field(meta, "Number of Data Columns") == pytest.approx(1.0)

        # Number of Data Points (no units)
        assert get_field(meta, "Number of Data Points") == pytest.approx(4096.0)

        # Offset (no units)
        assert get_field(meta, "Offset") == pytest.approx(0.0)

        # EDAX Owner (no units)
        assert get_field(meta, "EDAX Owner") == "EDAX TEAM EDS/block"

        # Real Time
        field = get_field(meta, "Real Time")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.0
        assert str(field.units) == "second"

        # Energy Resolution
        field = get_field(meta, "Energy Resolution")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 125.2
        assert str(field.units) == "electron_volt"

        # Signal Type (no units)
        assert get_field(meta, "Signal Type") == "EDS"

        # Active Layer Thickness
        field = get_field(meta, "Active Layer Thickness")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.1
        assert str(field.units) == "centimeter"

        # Be Window Thickness
        field = get_field(meta, "Be Window Thickness")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.0
        assert str(field.units) == "centimeter"

        # Dead Layer Thickness
        field = get_field(meta, "Dead Layer Thickness")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 0.03
        assert str(field.units) == "centimeter"

        # EDAX Time (no units)
        assert get_field(meta, "EDAX Time") == "10:14"

        # EDAX Title (no units)
        assert get_field(meta, "EDAX Title") == ""

        # TakeOff Angle
        field = get_field(meta, "TakeOff Angle")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == 35.5
        assert str(field.units) == "degree"

        # Stage Tilt
        field = get_field(meta, "Stage Tilt")
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == -1.0
        assert str(field.units) == "degree"

        # MSA Format Version (no units)
        assert get_field(meta, "MSA Format Version") == "1.0"

        # X Column Label (no units)
        assert get_field(meta, "X Column Label") == "X-RAY Energy"

        # X Units Per Channel (no units)
        assert get_field(meta, "X Units Per Channel") == pytest.approx(5.0)

        # X Column Units (no units)
        assert get_field(meta, "X Column Units") == "Energy (EV)"

        # Y Column Label (no units)
        assert get_field(meta, "Y Column Label") == "X-RAY Intensity"

        # Y Column Units (no units)
        assert get_field(meta, "Y Column Units") == "Intensity"

    def test_migrate_to_schema_compliant_metadata_with_unknown_field(self):
        """Test unknown fields go to extensions.

        This covers line 167 in edax.py where unknown fields move to extensions.
        """
        from nexusLIMS.extractors.plugins.edax import SpcExtractor

        extractor = SpcExtractor()

        # Create metadata dict with a custom unknown field
        mdict = {
            "nx_meta": {
                "DatasetType": "Spectrum",
                "Data Type": "EDS_Spectrum",
                "Creation Time": "2024-01-15T10:30:00-05:00",
                # Add a field that's not in vendor_fields and not in core fields
                "Custom Unknown Field": "test_value",
                # Also add a vendor field for comparison
                "Azimuthal Angle": "0.0",
            }
        }

        # Call the migration method
        result = extractor._migrate_to_schema_compliant_metadata(mdict)

        # Verify the unknown field went to extensions
        assert "extensions" in result["nx_meta"]
        assert "Custom Unknown Field" in result["nx_meta"]["extensions"]
        assert result["nx_meta"]["extensions"]["Custom Unknown Field"] == "test_value"

        # Verify vendor field also went to extensions
        assert "Azimuthal Angle" in result["nx_meta"]["extensions"]
        assert result["nx_meta"]["extensions"]["Azimuthal Angle"] == "0.0"

        # Verify core fields stayed at top level
        assert result["nx_meta"]["DatasetType"] == "Spectrum"
        assert result["nx_meta"]["Data Type"] == "EDS_Spectrum"
        assert result["nx_meta"]["Creation Time"] == "2024-01-15T10:30:00-05:00"
