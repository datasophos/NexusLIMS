# pylint: disable=C0116
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors top-level module functions."""

import base64
import filecmp
import json
import logging
import shutil
from pathlib import Path

import numpy as np
import pytest

import nexusLIMS
from nexusLIMS.extractors import PLACEHOLDER_PREVIEW, flatten_dict, parse_metadata
from nexusLIMS.version import __version__
from tests.test_instrument_factory import make_quanta_sem


class TestExtractorModule:
    """Tests the methods from __init__.py of nexusLIMS.extractors."""

    @classmethod
    def remove_thumb_and_json(cls, fname):
        fname.unlink()
        Path(str(fname).replace("thumb.png", "json")).unlink()

    def test_parse_metadata_titan(self, parse_meta_titan):
        meta, thumb_fname = parse_metadata(fname=parse_meta_titan[0])
        assert meta is not None
        assert meta["nx_meta"]["Acquisition Device"] == "BM-UltraScan"
        assert meta["nx_meta"]["Actual Magnification"] == pytest.approx(17677.0)
        assert meta["nx_meta"]["Cs(mm)"] == pytest.approx(1.2)
        assert meta["nx_meta"]["Data Dimensions"] == "(2048, 2048)"
        assert meta["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert len(meta["nx_meta"]["warnings"]) == 0
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.digital_micrograph"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_titan_mixed_case_extension(
        self, parse_meta_titan, tmp_path
    ):
        """Test metadata extraction with non-lowercase .dm4 extension.

        This test ensures that file extension matching is case-insensitive
        and that metadata extraction works properly for files with uppercase
        or mixed-case extensions like .TIF, .Tif, etc.
        """
        # Create a copy of the test file with mixed case extension
        original_file = parse_meta_titan[0]
        uppercase_file = tmp_path / (original_file.stem + ".Dm4")
        shutil.copy2(original_file, uppercase_file)

        # Test that metadata extraction works with mixed case extension
        meta, thumb_fname = parse_metadata(fname=uppercase_file)
        assert meta is not None
        assert thumb_fname is not None
        assert meta["nx_meta"]["Actual Magnification"] == pytest.approx(17677.0)
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.digital_micrograph"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_list_signal(self, list_signal):
        meta, thumb_fname = parse_metadata(fname=list_signal[0])
        assert meta is not None
        assert meta["nx_meta"]["Acquisition Device"] == "DigiScan"
        assert meta["nx_meta"]["STEM Camera Length"] == pytest.approx(77.0)
        assert meta["nx_meta"]["Cs(mm)"] == pytest.approx(1.0)
        assert meta["nx_meta"]["Data Dimensions"] == "(512, 512)"
        assert meta["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        assert len(meta["nx_meta"]["warnings"]) == 0
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.digital_micrograph"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_overwrite_false(self, caplog, list_signal):
        from nexusLIMS.extractors import replace_instrument_data_path

        thumb_fname = replace_instrument_data_path(list_signal[0], ".thumb.png")
        thumb_fname.parent.mkdir(parents=True, exist_ok=True)
        # create the thumbnail file so we can't overwrite
        with thumb_fname.open(mode="a", encoding="utf-8") as _:
            pass
        nexusLIMS.extractors.logger.setLevel(logging.INFO)
        _, thumb_fname = parse_metadata(fname=list_signal[0], overwrite=False)
        assert "Preview already exists" in caplog.text
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_quanta(
        self,
        quanta_test_file,
        mock_instrument_from_filepath,
    ):
        """Test metadata parsing for Quanta SEM files.

        This test now uses the instrument factory instead of relying on
        specific database entries, making dependencies explicit.
        """
        # Set up Quanta SEM instrument for this test
        mock_instrument_from_filepath(make_quanta_sem())

        _, thumb_fname = parse_metadata(fname=quanta_test_file[0])
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_tif_other_instr(self, monkeypatch, quanta_test_file):
        def mock_instr(_):
            return None

        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            mock_instr,
        )

        meta, thumb_fname = parse_metadata(fname=quanta_test_file[0])
        assert meta is not None
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.quanta_tif"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_tif_uppercase_extension(
        self, monkeypatch, quanta_test_file, tmp_path
    ):
        """Test metadata extraction with non-lowercase .TIF extension.

        This test ensures that file extension matching is case-insensitive
        and that metadata extraction works properly for files with uppercase
        or mixed-case extensions like .TIF, .Tif, etc.
        """
        import shutil

        def mock_instr(_):
            return None

        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            mock_instr,
        )

        # Create a copy of the test file with uppercase .TIF extension
        original_file = quanta_test_file[0]
        uppercase_file = tmp_path / (original_file.stem + ".TIF")
        shutil.copy2(original_file, uppercase_file)

        # Test that metadata extraction works with uppercase extension
        meta, thumb_fname = parse_metadata(fname=uppercase_file)
        assert meta is not None
        assert thumb_fname is not None
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.quanta_tif"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_edax_spc(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"
        _, thumb_fname = parse_metadata(fname=test_file)

        # test encoding of np.void metadata filler values
        json_path = Path(str(thumb_fname).replace("thumb.png", "json"))
        with json_path.open("r", encoding="utf-8") as _file:
            json_meta = json.load(_file)

        filler_val = json_meta["original_metadata"]["filler3"]
        assert filler_val == "PQoOQgAAgD8="

        expected_void = np.void(b"\x3d\x0a\x0e\x42\x00\x00\x80\x3f")
        assert np.void(base64.b64decode(filler_val)) == expected_void

        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_edax_msa(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"
        _, thumb_fname = parse_metadata(fname=test_file)
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_ser(self, fei_ser_files):
        test_file = next(
            i
            for i in fei_ser_files
            if "Titan_TEM_1_test_ser_image_dataZeroed_1.ser" in str(i)
        )

        meta, thumb_fname = parse_metadata(fname=test_file)
        assert meta is not None
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.fei_emi"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_no_dataset_type(self, monkeypatch, quanta_test_file):
        # PHASE 1 MIGRATION: Instead of monkeypatching extension_reader_map,
        # create a test extractor and register it with the registry
        from nexusLIMS.extractors.base import ExtractionContext
        from nexusLIMS.extractors.registry import get_registry

        class TestExtractorNoDatasetType:
            """Test extractor that doesn't set DatasetType."""

            name = "test_no_dataset_type"
            priority = 200  # Higher than normal extractors so it gets selected

            def supports(self, context: ExtractionContext) -> bool:
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context: ExtractionContext) -> dict:
                return {"nx_meta": {"key": "val"}}

        # Register the test extractor
        registry = get_registry()
        registry.register_extractor(TestExtractorNoDatasetType)

        try:
            meta, thumb_fname = parse_metadata(fname=quanta_test_file[0])
            assert meta is not None
            assert meta["nx_meta"]["DatasetType"] == "Misc"
            assert meta["nx_meta"]["Data Type"] == "Miscellaneous"
            assert meta["nx_meta"]["key"] == "val"
            assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

            self.remove_thumb_and_json(thumb_fname)
        finally:
            # Clean up - clear and re-discover to restore original state
            registry.clear()

    def test_parse_metadata_bad_ser(self, fei_ser_files):
        # if we find a bad ser that can't be read, we should get minimal
        # metadata and a placeholder thumbnail image
        test_file = next(
            i for i in fei_ser_files if "Titan_TEM_13_unreadable_ser_1.ser" in str(i)
        )

        meta, thumb_fname = parse_metadata(fname=test_file)
        assert thumb_fname is not None
        assert meta is not None
        # assert that preview is same as our placeholder image (should be)
        assert filecmp.cmp(PLACEHOLDER_PREVIEW, thumb_fname, shallow=False)
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Misc"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.fei_emi"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        assert "Titan_TEM_13_unreadable_ser.emi" in meta["nx_meta"]["emi Filename"]
        assert (
            "The .ser file could not be opened" in meta["nx_meta"]["Extractor Warning"]
        )

        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_basic_extractor(self, basic_txt_file_no_extension):
        meta, thumb_fname = parse_metadata(fname=basic_txt_file_no_extension)

        assert thumb_fname is None
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.basic_metadata"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        # remove json file
        from nexusLIMS.config import settings

        Path(
            str(basic_txt_file_no_extension).replace(
                str(settings.NX_INSTRUMENT_DATA_PATH),
                str(settings.NX_DATA_PATH),
            )
            + ".json",
        ).unlink()

    def test_parse_metadata_with_image_preview(self, basic_image_file):
        meta, thumb_fname = parse_metadata(fname=basic_image_file)
        assert thumb_fname is not None
        assert thumb_fname.is_file()
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.basic_metadata"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fname)

    def test_parse_metadata_with_text_preview(self, basic_txt_file):
        meta, thumb_fname = parse_metadata(fname=basic_txt_file)
        assert thumb_fname is not None
        assert thumb_fname.is_file()
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.basic_metadata"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fname)

    def test_no_thumb_for_unreadable_image(self, unreadable_image_file):
        meta, thumb_fname = parse_metadata(fname=unreadable_image_file)

        assert thumb_fname is None
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.basic_metadata"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

    def test_no_thumb_for_binary_text_file(self, binary_text_file):
        meta, thumb_fname = parse_metadata(fname=binary_text_file)

        assert thumb_fname is None
        assert meta is not None
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.basic_metadata"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

    def test_create_preview_non_quanta_tif(
        self, monkeypatch, quanta_test_file, tmp_path
    ):
        """Test create_preview for non-Quanta TIF files (else branch, lines 275-276)."""
        from unittest.mock import Mock

        from PIL import Image

        from nexusLIMS.extractors import create_preview

        # Create a mock instrument that is NOT Quanta (to hit the else branch)
        mock_instr = Mock()
        mock_instr.name = "Some-Other-Instrument"

        monkeypatch.setattr(
            "nexusLIMS.extractors.get_instr_from_filepath",
            lambda _fname: mock_instr,
        )

        # Create output path
        output_path = tmp_path / "preview.png"

        monkeypatch.setattr(
            "nexusLIMS.extractors.replace_instrument_data_path",
            lambda _fname, _ext: output_path,
        )

        # Mock down_sample_image to verify factor=2 is used and create output
        def mock_downsample(_fname, out_path=None, factor=None, output_size=None):
            # This assertion verifies we hit lines 275-276 (else branch)
            assert factor == 2, "Expected factor=2 for non-Quanta instruments"  # noqa: PLR2004
            assert output_size is None, "Expected output_size=None for non-Quanta"
            # Create output
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (100, 100), color="red")
                img.save(out_path)

        monkeypatch.setattr(
            "nexusLIMS.extractors.down_sample_image",
            mock_downsample,
        )

        # Execute the function - this should hit lines 275-276
        _result = create_preview(fname=quanta_test_file[0], overwrite=False)

    def test_flatten_dict(self):
        dict_to_flatten = {
            "level1.1": "level1.1v",
            "level1.2": {"level2.1": "level2.1v"},
        }

        flattened = flatten_dict(dict_to_flatten)
        assert flattened == {"level1.1": "level1.1v", "level1.2 level2.1": "level2.1v"}
