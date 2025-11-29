# pylint: disable=C0116
# ruff: noqa: D102, PLR2004

"""Tests for nexusLIMS.extractors.edax."""

from pathlib import Path

import pytest

from nexusLIMS.extractors.edax import get_msa_metadata, get_spc_metadata


class TestEDAXSPCExtractor:
    """Tests nexusLIMS.extractors.edax."""

    def test_leo_edax_spc(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"
        meta = get_spc_metadata(test_file)
        assert meta is not None
        assert meta["nx_meta"]["Azimuthal Angle (deg)"] == pytest.approx(0.0)
        assert meta["nx_meta"]["Live Time (s)"] == pytest.approx(30.000002)
        assert meta["nx_meta"]["Detector Energy Resolution (eV)"] == pytest.approx(
            125.16211,
        )
        assert meta["nx_meta"]["Elevation Angle (deg)"] == pytest.approx(35.0)
        assert meta["nx_meta"]["Channel Size (eV)"] == 5
        assert meta["nx_meta"]["Number of Spectrum Channels"] == 4096
        assert meta["nx_meta"]["Stage Tilt (deg)"] == -1.0
        assert meta["nx_meta"]["Starting Energy (keV)"] == pytest.approx(0.0)
        assert meta["nx_meta"]["Ending Energy (keV)"] == pytest.approx(20.475)

    def test_leo_edax_msa(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"
        meta = get_msa_metadata(test_file)
        assert meta is not None
        assert meta["nx_meta"]["Azimuthal Angle (deg)"] == pytest.approx(0.0)
        assert meta["nx_meta"]["Amplifier Time (μs)"] == "7.68"
        assert meta["nx_meta"]["Analyzer Type"] == "DPP4"
        assert meta["nx_meta"]["Beam Energy (keV)"] == pytest.approx(10.0)
        assert meta["nx_meta"]["Channel Offset"] == pytest.approx(0.0)
        assert (
            meta["nx_meta"]["EDAX Comment"]
            == "Converted by EDAX.TeamEDS V4.5.1-RC2.20170623.3 Friday, June 23, 2017"
        )
        assert meta["nx_meta"]["Data Format"] == "XY"
        assert meta["nx_meta"]["EDAX Date"] == "29-Aug-2022"
        assert meta["nx_meta"]["Elevation Angle (deg)"] == pytest.approx(35.0)
        assert meta["nx_meta"]["User-Selected Elements"] == "8,27,16"
        assert (
            meta["nx_meta"]["Originating File of MSA Export"]
            == "20220829_XXXXXXXXXXXX_XXXXXX.spc"
        )
        assert meta["nx_meta"]["File Format"] == "EMSA/MAS Spectral Data File"
        assert meta["nx_meta"]["FPGA Version"] == "0"
        assert meta["nx_meta"]["Live Time (s)"] == pytest.approx(30.0)
        assert meta["nx_meta"]["Number of Data Columns"] == pytest.approx(1.0)
        assert meta["nx_meta"]["Number of Data Points"] == pytest.approx(4096.0)
        assert meta["nx_meta"]["Offset"] == pytest.approx(0.0)
        assert meta["nx_meta"]["EDAX Owner"] == "EDAX TEAM EDS/block"
        assert meta["nx_meta"]["Real Time (s)"] == pytest.approx(0.0)
        assert meta["nx_meta"]["Energy Resolution (eV)"] == "125.2"
        assert meta["nx_meta"]["Signal Type"] == "EDS"
        assert meta["nx_meta"]["Active Layer Thickness (cm)"] == "0.1"
        assert meta["nx_meta"]["Be Window Thickness (cm)"] == pytest.approx(0.0)
        assert meta["nx_meta"]["Dead Layer Thickness (cm)"] == pytest.approx(0.03)
        assert meta["nx_meta"]["EDAX Time"] == "10:14"
        assert meta["nx_meta"]["EDAX Title"] == ""
        assert meta["nx_meta"]["TakeOff Angle (deg)"] == "35.5"
        assert meta["nx_meta"]["Stage Tilt (deg)"] == "-1.0"
        assert meta["nx_meta"]["MSA Format Version"] == "1.0"
        assert meta["nx_meta"]["X Column Label"] == "X-RAY Energy"
        assert meta["nx_meta"]["X Units Per Channel"] == pytest.approx(5.0)
        assert meta["nx_meta"]["X Column Units"] == "Energy (EV)"
        assert meta["nx_meta"]["Y Column Label"] == "X-RAY Intensity"
        assert meta["nx_meta"]["Y Column Units"] == "Intensity"
