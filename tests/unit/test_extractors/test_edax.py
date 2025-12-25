# pylint: disable=C0116
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors.edax."""

from pathlib import Path

import pytest

from nexusLIMS.extractors.plugins.edax import get_msa_metadata, get_spc_metadata
from nexusLIMS.schemas.units import ureg


class TestEDAXSPCExtractor:
    """Tests nexusLIMS.extractors.edax."""

    def test_leo_edax_spc(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"
        meta = get_spc_metadata(test_file)
        assert meta is not None

        # Azimuthal Angle
        field = meta[0]["nx_meta"]["Azimuthal Angle"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.0)
        assert str(field.units) == "degree"

        # Live Time
        field = meta[0]["nx_meta"]["Live Time"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(30.000002)
        assert str(field.units) == "second"

        # Detector Energy Resolution
        field = meta[0]["nx_meta"]["Detector Energy Resolution"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(125.16211)
        assert str(field.units) == "electron_volt"

        # Elevation Angle
        field = meta[0]["nx_meta"]["Elevation Angle"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(35.0)
        assert str(field.units) == "degree"

        # Channel Size
        field = meta[0]["nx_meta"]["Channel Size"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == 5
        assert str(field.units) == "electron_volt"

        # Number of Spectrum Channels (no units)
        assert meta[0]["nx_meta"]["Number of Spectrum Channels"] == 4096

        # Stage Tilt
        field = meta[0]["nx_meta"]["Stage Tilt"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == -1.0
        assert str(field.units) == "degree"

        # Starting Energy
        field = meta[0]["nx_meta"]["Starting Energy"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.0)
        assert str(field.units) == "kiloelectron_volt"

        # Ending Energy
        field = meta[0]["nx_meta"]["Ending Energy"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(20.475)
        assert str(field.units) == "kiloelectron_volt"

    def test_leo_edax_msa(self):  # noqa: PLR0915
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"
        meta = get_msa_metadata(test_file)
        assert meta is not None

        # Azimuthal Angle
        field = meta[0]["nx_meta"]["Azimuthal Angle"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.0)
        assert str(field.units) == "degree"

        # Amplifier Time
        field = meta[0]["nx_meta"]["Amplifier Time"]
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == pytest.approx(7.68)
        assert str(field.units) == "microsecond"

        # Analyzer Type (no units)
        assert meta[0]["nx_meta"]["Analyzer Type"] == "DPP4"

        # Beam Energy
        field = meta[0]["nx_meta"]["Beam Energy"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(10.0)
        assert str(field.units) == "kiloelectron_volt"

        # Channel Offset (no units)
        assert meta[0]["nx_meta"]["Channel Offset"] == pytest.approx(0.0)

        # EDAX Comment (no units)
        assert (
            meta[0]["nx_meta"]["EDAX Comment"]
            == "Converted by EDAX.TeamEDS V4.5.1-RC2.20170623.3 Friday, June 23, 2017"
        )

        # Data Format (no units)
        assert meta[0]["nx_meta"]["Data Format"] == "XY"

        # EDAX Date (no units)
        assert meta[0]["nx_meta"]["EDAX Date"] == "29-Aug-2022"

        # Elevation Angle
        field = meta[0]["nx_meta"]["Elevation Angle"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(35.0)
        assert str(field.units) == "degree"

        # User-Selected Elements (no units)
        assert meta[0]["nx_meta"]["User-Selected Elements"] == "8,27,16"

        # Originating File of MSA Export (no units)
        assert (
            meta[0]["nx_meta"]["Originating File of MSA Export"]
            == "20220829_XXXXXXXXXXXX_XXXXXX.spc"
        )

        # File Format (no units)
        assert meta[0]["nx_meta"]["File Format"] == "EMSA/MAS Spectral Data File"

        # FPGA Version (no units)
        assert meta[0]["nx_meta"]["FPGA Version"] == "0"

        # Live Time
        field = meta[0]["nx_meta"]["Live Time"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(30.0)
        assert str(field.units) == "second"

        # Number of Data Columns (no units)
        assert meta[0]["nx_meta"]["Number of Data Columns"] == pytest.approx(1.0)

        # Number of Data Points (no units)
        assert meta[0]["nx_meta"]["Number of Data Points"] == pytest.approx(4096.0)

        # Offset (no units)
        assert meta[0]["nx_meta"]["Offset"] == pytest.approx(0.0)

        # EDAX Owner (no units)
        assert meta[0]["nx_meta"]["EDAX Owner"] == "EDAX TEAM EDS/block"

        # Real Time
        field = meta[0]["nx_meta"]["Real Time"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.0)
        assert str(field.units) == "second"

        # Energy Resolution
        field = meta[0]["nx_meta"]["Energy Resolution"]
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == pytest.approx(125.2)
        assert str(field.units) == "electron_volt"

        # Signal Type (no units)
        assert meta[0]["nx_meta"]["Signal Type"] == "EDS"

        # Active Layer Thickness
        field = meta[0]["nx_meta"]["Active Layer Thickness"]
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == pytest.approx(0.1)
        assert str(field.units) == "centimeter"

        # Be Window Thickness
        field = meta[0]["nx_meta"]["Be Window Thickness"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.0)
        assert str(field.units) == "centimeter"

        # Dead Layer Thickness
        field = meta[0]["nx_meta"]["Dead Layer Thickness"]
        assert isinstance(field, ureg.Quantity)
        assert field.magnitude == pytest.approx(0.03)
        assert str(field.units) == "centimeter"

        # EDAX Time (no units)
        assert meta[0]["nx_meta"]["EDAX Time"] == "10:14"

        # EDAX Title (no units)
        assert meta[0]["nx_meta"]["EDAX Title"] == ""

        # TakeOff Angle
        field = meta[0]["nx_meta"]["TakeOff Angle"]
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == pytest.approx(35.5)
        assert str(field.units) == "degree"

        # Stage Tilt
        field = meta[0]["nx_meta"]["Stage Tilt"]
        assert isinstance(field, ureg.Quantity)
        assert float(field.magnitude) == pytest.approx(-1.0)
        assert str(field.units) == "degree"

        # MSA Format Version (no units)
        assert meta[0]["nx_meta"]["MSA Format Version"] == "1.0"

        # X Column Label (no units)
        assert meta[0]["nx_meta"]["X Column Label"] == "X-RAY Energy"

        # X Units Per Channel (no units)
        assert meta[0]["nx_meta"]["X Units Per Channel"] == pytest.approx(5.0)

        # X Column Units (no units)
        assert meta[0]["nx_meta"]["X Column Units"] == "Energy (EV)"

        # Y Column Label (no units)
        assert meta[0]["nx_meta"]["Y Column Label"] == "X-RAY Intensity"

        # Y Column Units (no units)
        assert meta[0]["nx_meta"]["Y Column Units"] == "Intensity"
