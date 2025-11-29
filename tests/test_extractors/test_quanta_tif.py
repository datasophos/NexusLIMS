# pylint: disable=C0116
# ruff: noqa: D102, PLR2004, DTZ001

"""Tests for nexusLIMS.extractors.quanta_tif."""

import pytest

from nexusLIMS.extractors.quanta_tif import get_quanta_metadata

from ..test_instrument_factory import make_test_tool


class TestQuantaExtractor:
    """Tests nexusLIMS.extractors.quanta_tif."""

    def test_quanta_extraction(self, quanta_test_file):
        metadata = get_quanta_metadata(quanta_test_file[0])

        # test 'nx_meta' values of interest
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        assert metadata["nx_meta"]["warnings"] == [["Operator"]]

        # test two values from each of the native sections
        assert metadata["User"]["User"] == "user_"
        assert metadata["User"]["Date"] == "12/18/2017"
        assert metadata["User"]["Time"] == "01:04:14 PM"
        assert metadata["System"]["Type"] == "SEM"
        assert metadata["System"]["Dnumber"] == "ABCD1"
        assert metadata["Beam"]["HV"] == "30000"
        assert metadata["Beam"]["Spot"] == "3"
        assert metadata["EBeam"]["Source"] == "FEG"
        assert metadata["EBeam"]["FinalLens"] == "S45"
        assert metadata["GIS"]["Number"] == "0"
        assert metadata["EScan"]["InternalScan"]
        assert metadata["EScan"]["Scan"] == "PIA 2.0"
        assert metadata["Stage"]["StageX"] == "0.009654"
        assert metadata["Stage"]["StageY"] == "0.0146008"
        assert metadata["Image"]["ResolutionX"] == "1024"
        assert metadata["Image"]["DigitalContrast"] == "1"
        assert metadata["Vacuum"]["ChPressure"] == "79.8238"
        assert metadata["Vacuum"]["Gas"] == "Wet"
        assert metadata["Specimen"]["Temperature"] == ""
        assert metadata["Detectors"]["Number"] == "1"
        assert metadata["Detectors"]["Name"] == "LFD"
        assert metadata["LFD"]["Contrast"] == "62.4088"
        assert metadata["LFD"]["Brightness"] == "45.7511"
        assert metadata["Accessories"]["Number"] == "0"
        assert metadata["PrivateFei"]["BitShift"] == "0"
        assert (
            metadata["PrivateFei"]["DataBarSelected"]
            == "DateTime dwell HV HFW pressure Label MicronBar"
        )
        assert metadata["HiResIllumination"]["BrightFieldIsOn"] == ""
        assert metadata["HiResIllumination"]["BrightFieldValue"] == ""

    def test_bad_metadata(self, quanta_bad_metadata):
        metadata = get_quanta_metadata(quanta_bad_metadata)
        assert (
            metadata["nx_meta"]["Extractor Warnings"]
            == "Did not find expected FEI tags. Could not read metadata"
        )
        assert metadata["nx_meta"]["Data Type"] == "Unknown"
        assert metadata["nx_meta"]["Data Type"] == "Unknown"

    def test_modded_metadata(self, quanta_just_modded_mdata):
        metadata = get_quanta_metadata(quanta_just_modded_mdata)

        # test 'nx_meta' values of interest
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        assert metadata["nx_meta"]["warnings"] == [["Operator"]]

        assert metadata["nx_meta"]["Scan Rotation (°)"] == pytest.approx(179.9947)
        assert metadata["nx_meta"]["Tilt Correction Angle"] == pytest.approx(0.0121551)
        assert metadata["nx_meta"]["Specimen Temperature (K)"] == "j"
        assert len(metadata["nx_meta"]["Chamber Pressure (mPa)"]) == 7000

    def test_no_beam_scan_or_system_metadata(
        self,
        mock_instrument_from_filepath,
        quanta_no_beam_meta,
    ):
        """Test Quanta extraction with missing beam/scan/system metadata."""
        mock_instrument_from_filepath(make_test_tool())

        metadata = get_quanta_metadata(quanta_no_beam_meta[0])
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        assert (
            metadata["nx_meta"]["Creation Time"] == "2025-11-17T17:52:13.811711-07:00"
        )
        assert metadata["nx_meta"]["Instrument ID"] == "testtool-TEST-A1234567"
        assert metadata["nx_meta"]["Data Dimensions"] == "(1024, 884)"
        assert metadata["nx_meta"]["Frames Integrated"] == 5
        assert metadata["Image"]["ResolutionX"] == "1024"
        assert metadata["Image"]["DigitalContrast"] == "1"

    def test_scios_duplicate_metadata_sections(self, scios_multiple_gis_meta):
        metadata = get_quanta_metadata(scios_multiple_gis_meta[0])
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        # this test file doesn't have an instrument associated with it,
        # so timestamp for creation time should be in UTC
        assert (
            metadata["nx_meta"]["Creation Time"] == "2025-11-18T00:53:37.585629+00:00"
        )
        assert metadata["nx_meta"]["Operator"] == "xxxx"
        assert metadata["CBS"]["Setting"] == "C+D"
        assert metadata["MultiGISUnit1.MultiGISGas1"]["GasName"] == ""
        assert metadata["MultiGISUnit2.MultiGISGas3"]["DutyCycle"] == "0"
        assert metadata["MultiGISUnit3.MultiGISGas6"]["GasState"] == "Unknown"
        assert metadata["MultiGISUnit4.MultiGISGas4"]["GasState"] == "Unknown"

    def test_scios_xml_metadata(self, scios_xml_metadata):
        metadata = get_quanta_metadata(scios_xml_metadata[0])
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["Acquisition Date"] == "05/01/2024"
        assert metadata["nx_meta"]["Beam Name"] == "EBeam"
        assert metadata["nx_meta"]["Beam Tilt X"] == pytest.approx(0.0)
        assert metadata["CBS"]["Setting"] == "A+B"
        assert metadata["nx_meta"]["Operator"] == "xxxx"

        assert metadata["FEI_XML_Metadata"]["Core"]["ApplicationSoftware"] == "xT"
        assert metadata["FEI_XML_Metadata"]["Core"]["UserID"] == "xxxx"
        assert (
            metadata["FEI_XML_Metadata"]["Instrument"]["Manufacturer"] == "FEI Company"
        )
        assert (
            metadata["FEI_XML_Metadata"]["GasInjectionSystems"]["Gis"][1]["PortName"]
            == "Port2"
        )
        assert (
            metadata["FEI_XML_Metadata"]["StageSettings"]["StagePosition"]["Tilt"][
                "Alpha"
            ]
            == "-1.4439342452859871E-05"
        )
