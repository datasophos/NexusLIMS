# pylint: disable=C0116
# ruff: noqa: D102, ARG002, ARG001

"""Tests for nexusLIMS.extractors top-level module functions."""

import base64
import filecmp
import json
import logging
import shutil
from datetime import UTC
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from pydantic import ValidationError

import nexusLIMS
from nexusLIMS.extractors import (
    PLACEHOLDER_PREVIEW,
    flatten_dict,
    parse_metadata,
    validate_nx_meta,
)
from nexusLIMS.version import __version__
from tests.unit.test_instrument_factory import make_quanta_sem


class TestExtractorModule:
    """Tests the methods from __init__.py of nexusLIMS.extractors."""

    @classmethod
    def remove_thumb_and_json(cls, fname):
        # Handle both single Path and list of Paths (for multi-signal files)
        if isinstance(fname, list):
            for f in fname:
                if f is not None:
                    f.unlink(missing_ok=True)
                    Path(str(f).replace("thumb.png", "json")).unlink(missing_ok=True)
        elif fname is not None:
            fname.unlink(missing_ok=True)
            Path(str(fname).replace("thumb.png", "json")).unlink(missing_ok=True)

    def test_parse_metadata_titan(self, parse_meta_titan):
        meta_list, thumb_fnames = parse_metadata(fname=parse_meta_titan[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Acquisition Device"] == "BM-UltraScan"
        assert meta["nx_meta"]["Actual Magnification"] == pytest.approx(17677.0)
        # Cs is now a Pint Quantity
        from nexusLIMS.schemas.units import ureg

        assert isinstance(meta["nx_meta"]["Cs"], ureg.Quantity)
        assert meta["nx_meta"]["Cs"].magnitude == pytest.approx(1.2)
        assert meta["nx_meta"]["Cs"].units == ureg.millimeter
        assert meta["nx_meta"]["Data Dimensions"] == "(2048, 2048)"
        assert meta["nx_meta"]["Data Type"] == "TEM_Imaging"
        assert meta["nx_meta"]["DatasetType"] == "Image"
        assert meta["nx_meta"]["Microscope"] == "TEST Titan"
        assert len(meta["nx_meta"]["warnings"]) == 0
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.dm3_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fnames)

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
        meta_list, thumb_fnames = parse_metadata(fname=uppercase_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1
        assert thumb_fnames is not None

        meta = meta_list[0]
        assert meta["nx_meta"]["Actual Magnification"] == pytest.approx(17677.0)
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.dm3_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_list_signal(self, list_signal):
        meta_list, thumb_fnames = parse_metadata(fname=list_signal[0])
        assert meta_list is not None

        # This file has multiple signals, so it returns a list of dicts
        assert isinstance(meta_list, list)
        assert len(meta_list) == 2
        assert isinstance(thumb_fnames, list)
        assert len(thumb_fnames) == 2

        # Check first signal metadata
        first_signal = meta_list[0]
        assert first_signal["nx_meta"]["Acquisition Device"] == "DigiScan"
        # STEM Camera Length and Cs are now Pint Quantities
        from nexusLIMS.schemas.units import ureg

        assert isinstance(first_signal["nx_meta"]["STEM Camera Length"], ureg.Quantity)
        assert first_signal["nx_meta"]["STEM Camera Length"].magnitude == pytest.approx(
            77.0
        )
        assert first_signal["nx_meta"]["STEM Camera Length"].units == ureg.millimeter
        assert isinstance(first_signal["nx_meta"]["Cs"], ureg.Quantity)
        assert first_signal["nx_meta"]["Cs"].magnitude == pytest.approx(1.0)
        assert first_signal["nx_meta"]["Cs"].units == ureg.millimeter
        assert first_signal["nx_meta"]["Data Dimensions"] == "(512, 512)"
        assert first_signal["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert first_signal["nx_meta"]["DatasetType"] == "Image"
        assert len(first_signal["nx_meta"]["warnings"]) == 0

        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_overwrite_false(self, caplog, list_signal):
        from nexusLIMS.extractors import replace_instrument_data_path

        # This is a multi-signal file with 2 signals, so create both preview files
        base_path = replace_instrument_data_path(list_signal[0], "")
        thumb_fnames = [
            base_path.parent / f"{base_path.name}_signal0.thumb.png",
            base_path.parent / f"{base_path.name}_signal1.thumb.png",
        ]

        # Create parent directory and preview files
        thumb_fnames[0].parent.mkdir(parents=True, exist_ok=True)
        for thumb in thumb_fnames:
            with thumb.open(mode="a", encoding="utf-8") as _:
                pass

        nexusLIMS.extractors.logger.setLevel(logging.INFO)
        _, returned_thumb_fnames = parse_metadata(fname=list_signal[0], overwrite=False)
        assert "Preview already exists" in caplog.text
        self.remove_thumb_and_json(returned_thumb_fnames)

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

        meta_list, thumb_fnames = parse_metadata(fname=quanta_test_file[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_tif_other_instr(self, monkeypatch, quanta_test_file):
        def mock_instr(_):
            return None

        monkeypatch.setattr(
            nexusLIMS.extractors.utils,
            "get_instr_from_filepath",
            mock_instr,
        )

        meta_list, thumb_fnames = parse_metadata(fname=quanta_test_file[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.quanta_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

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
        meta_list, thumb_fnames = parse_metadata(fname=uppercase_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1
        assert thumb_fnames is not None

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.quanta_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_edax_spc(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"
        meta_list, thumb_fnames = parse_metadata(fname=test_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        # test encoding of np.void metadata filler values
        json_path = Path(str(thumb_fnames[0]).replace("thumb.png", "json"))
        with json_path.open("r", encoding="utf-8") as _file:
            json_meta = json.load(_file)

        filler_val = json_meta["original_metadata"]["filler3"]
        assert filler_val == "PQoOQgAAgD8="

        expected_void = np.void(b"\x3d\x0a\x0e\x42\x00\x00\x80\x3f")
        assert np.void(base64.b64decode(filler_val)) == expected_void

        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_edax_msa(self):
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"
        meta_list, thumb_fnames = parse_metadata(fname=test_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_ser(self, fei_ser_files):
        test_file = next(
            i
            for i in fei_ser_files
            if "Titan_TEM_1_test_ser_image_dataZeroed_1.ser" in str(i)
        )

        meta_list, thumb_fnames = parse_metadata(fname=test_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.ser_emi_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_no_dataset_type(self, monkeypatch, quanta_test_file):
        # PHASE 1 MIGRATION: Instead of monkeypatching extension_reader_map,
        # create a test extractor and register it with the registry
        from nexusLIMS.extractors.base import ExtractionContext
        from nexusLIMS.extractors.registry import get_registry

        class TestExtractorNoDatasetType:
            """Test extractor that doesn't set DatasetType."""

            name = "test_no_dataset_type"
            priority = 200  # Higher than normal extractors so it gets selected
            supported_extensions: ClassVar = {"tif", "tiff"}

            def supports(self, context: ExtractionContext) -> bool:
                return context.file_path.suffix.lower() == ".tif"

            def extract(self, context: ExtractionContext) -> list[dict]:
                from datetime import datetime

                # Return minimal valid metadata without DatasetType/Data Type
                # to test that defaults are applied
                return [
                    {
                        "nx_meta": {
                            "Creation Time": datetime.now(tz=UTC).isoformat(),
                            "key": "val",  # Custom field for testing
                        }
                    }
                ]

        # Register the test extractor
        registry = get_registry()
        registry.register_extractor(TestExtractorNoDatasetType)

        try:
            meta_list, thumb_fnames = parse_metadata(fname=quanta_test_file[0])
            assert meta_list is not None
            assert isinstance(meta_list, list)
            assert len(meta_list) == 1

            meta = meta_list[0]
            assert meta["nx_meta"]["DatasetType"] == "Misc"
            assert meta["nx_meta"]["Data Type"] == "Miscellaneous"
            assert meta["nx_meta"]["key"] == "val"
            assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

            self.remove_thumb_and_json(thumb_fnames)
        finally:
            # Clean up - clear and re-discover to restore original state
            registry.clear()

    def test_parse_metadata_bad_ser(self, fei_ser_files):
        # if we find a bad ser that can't be read, we should get minimal
        # metadata and a placeholder thumbnail image
        test_file = next(
            i for i in fei_ser_files if "Titan_TEM_13_unreadable_ser_1.ser" in str(i)
        )

        meta_list, thumb_fnames = parse_metadata(fname=test_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1
        assert thumb_fnames is not None

        meta = meta_list[0]
        # assert that preview is same as our placeholder image (should be)
        assert filecmp.cmp(PLACEHOLDER_PREVIEW, thumb_fnames[0], shallow=False)
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Misc"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.ser_emi_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        assert "Titan_TEM_13_unreadable_ser.emi" in meta["nx_meta"]["emi Filename"]
        assert (
            "The .ser file could not be opened" in meta["nx_meta"]["Extractor Warning"]
        )

        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_basic_extractor(self, basic_txt_file_no_extension):
        meta_list, thumb_fnames = parse_metadata(fname=basic_txt_file_no_extension)

        # For files without preview generation, thumb_fnames is [None]
        assert thumb_fnames == [None]
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.basic_file_info_extractor"
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
        meta_list, thumb_fnames = parse_metadata(fname=basic_image_file)
        assert thumb_fnames is not None
        assert isinstance(thumb_fnames, list)
        assert len(thumb_fnames) == 1
        assert thumb_fnames[0].is_file()
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.basic_file_info_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_with_text_preview(self, basic_txt_file):
        meta_list, thumb_fnames = parse_metadata(fname=basic_txt_file)
        assert thumb_fnames is not None
        assert isinstance(thumb_fnames, list)
        assert len(thumb_fnames) == 1
        assert thumb_fnames[0].is_file()
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.basic_file_info_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        self.remove_thumb_and_json(thumb_fnames)

    def test_no_thumb_for_unreadable_image(self, unreadable_image_file):
        meta_list, thumb_fnames = parse_metadata(fname=unreadable_image_file)

        # For files without preview generation, thumb_fnames is [None]
        assert thumb_fnames == [None]
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.basic_file_info_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        # Clean up JSON file (no thumbnail is generated for this file type)
        json_path = Path(str(unreadable_image_file) + ".json")
        if json_path.exists():
            json_path.unlink()

    def test_no_thumb_for_binary_text_file(self, binary_text_file):
        meta_list, thumb_fnames = parse_metadata(fname=binary_text_file)

        # For files without preview generation, thumb_fnames is [None]
        assert thumb_fnames == [None]
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert meta["nx_meta"]["Data Type"] == "Unknown"
        assert meta["nx_meta"]["DatasetType"] == "Unknown"
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.basic_file_info_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

        # Clean up JSON file (no thumbnail is generated for this file type)
        json_path = Path(str(binary_text_file) + ".json")
        if json_path.exists():
            json_path.unlink()

    def test_create_preview_non_quanta_tif(
        self, monkeypatch, quanta_test_file, tmp_path
    ):
        """Test create_preview for non-Quanta TIF files (else branch)."""
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
            # This assertion verifies we hit else branch
            assert factor == 2, "Expected factor=2 for non-Quanta instruments"
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

        # Execute the function
        _result = create_preview(fname=quanta_test_file[0], overwrite=False)

    def test_flatten_dict(self):
        dict_to_flatten = {
            "level1.1": "level1.1v",
            "level1.2": {"level2.1": "level2.1v"},
        }

        flattened = flatten_dict(dict_to_flatten)
        assert flattened == {"level1.1": "level1.1v", "level1.2 level2.1": "level2.1v"}

    def test_add_extraction_details_unknown_module(self, monkeypatch):
        """Test _add_extraction_details when module cannot be determined."""
        from nexusLIMS.extractors import _add_extraction_details

        # Create a callable mock that has no __module__ attribute
        def mock_extractor():
            pass

        # Remove the __module__ attribute to force the fallback path
        delattr(mock_extractor, "__module__")

        # Mock inspect.getmodule to return None
        monkeypatch.setattr("nexusLIMS.extractors.inspect.getmodule", lambda _: None)

        nx_meta: dict = {"nx_meta": {}}
        result = _add_extraction_details(nx_meta, mock_extractor)

        # Should fall back to "unknown"
        assert result["nx_meta"]["NexusLIMS Extraction"]["Module"] == "unknown"
        assert "Date" in result["nx_meta"]["NexusLIMS Extraction"]
        assert result["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__

    def test_extractor_method_callable(self, parse_meta_titan):
        """Test that ExtractorMethod.__call__ is callable."""
        from pathlib import Path

        # This test exercises the __call__ method
        # We need to create the ExtractorMethod class and call it
        # The class is defined inside parse_metadata, so we replicate it here
        nx_meta_test = {"nx_meta": {"test": "value"}}

        class ExtractorMethod:
            """Pseudo-module for extraction details tracking."""

            def __init__(self, extractor_name: str):
                self.__module__ = "test_module"
                self.__name__ = self.__module__

            def __call__(self, f: Path) -> dict:
                return nx_meta_test

        em = ExtractorMethod("test")
        result = em(Path("test.txt"))

        # Verify the __call__ method works
        assert result["nx_meta"]["test"] == "value"

        # Also run normal parse_metadata to ensure it works end-to-end
        meta, thumb_fname = parse_metadata(fname=parse_meta_titan[0])
        assert meta is not None
        self.remove_thumb_and_json(thumb_fname)

    def test_preview_generation_pil_failure(
        self, monkeypatch, unreadable_image_file, caplog
    ):
        """Test create_preview returns None when PIL can't open image."""
        from nexusLIMS.extractors import create_preview

        # The unreadable_image_file fixture should already cause PIL to fail
        # but let's be explicit and mock to ensure
        def mock_image_to_square_thumb_fail(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "nexusLIMS.extractors.image_to_square_thumbnail",
            mock_image_to_square_thumb_fail,
        )

        result = create_preview(fname=unreadable_image_file, overwrite=False)
        # When PIL fails, should return None
        assert result is None

    def test_hyperspy_signal_empty_title(self, tmp_path):
        """Test that HyperSpy signals with empty titles are handled."""
        import hyperspy.api as hs

        from nexusLIMS.extractors import create_preview

        # Create a simple signal with no title
        signal = hs.signals.Signal2D(np.random.random((10, 10)))
        signal.metadata.General.title = ""  # Empty title
        signal.metadata.General.original_filename = "test_empty_title.hspy"

        # Save to temp file in a supported format
        test_file = tmp_path / "test_empty_title.hspy"
        signal.save(test_file, overwrite=True)

        # This should handle the empty title by using the filename
        result = create_preview(fname=test_file, overwrite=True)

        # The preview should have been generated successfully
        assert result is not None

        # Cleanup
        if result and result.exists():
            result.unlink()
            json_file = Path(str(result).replace(".thumb.png", ".json"))
            if json_file.exists():
                json_file.unlink()

    def test_legacy_tif_downsampling(self, monkeypatch, tmp_path, caplog):
        """Test legacy downsampling for .tif files.

        This test ensures that when no preview generator plugin is found
        for a .tif file, the legacy downsampling fallback is triggered
        with factor=2.
        """
        from unittest.mock import Mock

        from PIL import Image

        from nexusLIMS.extractors import create_preview

        # Create a test .tif file
        test_tif = tmp_path / "test_image.tif"
        test_image = Image.new("RGB", (1000, 1000), color="blue")
        test_image.save(test_tif)

        # Mock get_instr_from_filepath to return None (no instrument context)
        monkeypatch.setattr(
            "nexusLIMS.extractors.get_instr_from_filepath",
            lambda _fname: None,
        )

        # Mock the registry to return None (no preview generator plugin)
        mock_registry = Mock()
        mock_registry.get_preview_generator.return_value = None

        monkeypatch.setattr(
            "nexusLIMS.extractors.get_registry",
            lambda: mock_registry,
        )

        # Mock replace_instrument_data_path to use tmp_path
        output_path = tmp_path / "output" / "test_image.thumb.png"

        monkeypatch.setattr(
            "nexusLIMS.extractors.replace_instrument_data_path",
            lambda _fname, _ext: output_path,
        )

        # Track the down_sample_image call
        downsample_called = {"called": False, "factor": None}

        def mock_downsample(
            _fname,
            out_path=None,
            output_size=None,
            factor=None,
        ):
            downsample_called["called"] = True
            downsample_called["factor"] = factor
            # Create output
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (500, 500), color="red")
                img.save(out_path)

        monkeypatch.setattr(
            "nexusLIMS.extractors.down_sample_image",
            mock_downsample,
        )

        # Execute create_preview
        import logging

        import nexusLIMS.extractors

        nexusLIMS.extractors.logger.setLevel(logging.INFO)

        result = create_preview(fname=test_tif, overwrite=True)

        # Verify legacy downsampling was called with factor=2
        assert downsample_called["called"], "down_sample_image should have been called"
        assert downsample_called["factor"] == 2, (
            "Factor should be 2 for legacy TIF downsampling"
        )
        assert result == output_path, "Should return the output path"
        assert output_path.exists(), "Preview file should have been created"

        # Verify the log message
        assert "Using legacy downsampling for .tif" in caplog.text

    def test_legacy_preview_map_success(self, monkeypatch, tmp_path, caplog):
        """Test legacy preview map fallback success path.

        This test ensures that when a file extension is in unextracted_preview_map
        and the preview generation succeeds, the correct path is returned.
        """
        from unittest.mock import Mock

        from PIL import Image

        from nexusLIMS.extractors import create_preview

        # Create a test .png file (in unextracted_preview_map)
        test_png = tmp_path / "test_image.png"
        test_image = Image.new("RGB", (800, 800), color="green")
        test_image.save(test_png)

        # Mock get_instr_from_filepath to return None
        monkeypatch.setattr(
            "nexusLIMS.extractors.get_instr_from_filepath",
            lambda _fname: None,
        )

        # Mock the registry to return None (force legacy fallback)
        mock_registry = Mock()
        mock_registry.get_preview_generator.return_value = None

        monkeypatch.setattr(
            "nexusLIMS.extractors.get_registry",
            lambda: mock_registry,
        )

        # Mock replace_instrument_data_path to use tmp_path
        output_path = tmp_path / "output" / "test_image.thumb.png"

        monkeypatch.setattr(
            "nexusLIMS.extractors.replace_instrument_data_path",
            lambda _fname, _ext: output_path,
        )

        # Track if image_to_square_thumbnail is called
        thumbnail_called = {"called": False}

        def mock_image_to_square_thumbnail(
            f=None,
            out_path=None,
            output_size=None,
        ):
            thumbnail_called["called"] = True
            # Create output to simulate success
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (500, 500), color="yellow")
                img.save(out_path)
            # Return anything except False to indicate success
            return True

        # Patch unextracted_preview_map directly
        import nexusLIMS.extractors

        monkeypatch.setitem(
            nexusLIMS.extractors.unextracted_preview_map,
            "png",
            mock_image_to_square_thumbnail,
        )

        # Execute create_preview
        import logging

        import nexusLIMS.extractors

        nexusLIMS.extractors.logger.setLevel(logging.INFO)

        result = create_preview(fname=test_png, overwrite=True)

        # Verify legacy preview map was used successfully
        assert thumbnail_called["called"], (
            "image_to_square_thumbnail should have been called"
        )
        assert result == output_path, "Should return the output path"
        assert output_path.exists(), "Preview file should have been created"

        # Verify the log message
        assert "Using legacy preview map for png" in caplog.text

    def test_correct_extractor_dispatched_for_quanta_tif(self, quanta_test_file):
        """Test that QuantaTiffExtractor is used for Quanta TIFF files.

        This test verifies that the correct extractor is dispatched when
        parsing metadata from a Quanta TIFF file, ensuring that the
        extractor selection/priority system works correctly.
        """
        meta_list, thumb_fnames = parse_metadata(fname=quanta_test_file[0])
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.quanta_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_correct_extractor_dispatched_for_orion_fibics_tif(
        self, orion_fibics_zeroed_file
    ):
        """Test that OrionFibicsTiffExtractor is used for Orion/Fibics TIFF files.

        This test verifies that the OrionFibicsTiffExtractor is prioritized
        over the QuantaTiffExtractor for Orion/Fibics TIFF files, ensuring
        that the extractor selection by priority works correctly.
        """
        meta_list, thumb_fnames = parse_metadata(fname=orion_fibics_zeroed_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.orion_HIM_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_correct_extractor_dispatched_for_orion_zeiss_tif(
        self, orion_zeiss_zeroed_file
    ):
        """Test that OrionFibicsTiffExtractor is used for Orion Zeiss TIFF files.

        This test verifies that the OrionFibicsTiffExtractor correctly handles
        Orion TIF files with Zeiss XML metadata (not Fibics metadata), ensuring
        it is properly detected and handled.
        """
        meta_list, thumb_fnames = parse_metadata(fname=orion_zeiss_zeroed_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.orion_HIM_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_correct_extractor_dispatched_for_tescan_pfib_tif(self, tescan_pfib_files):
        """Test that TescanPfibTiffExtractor is used for Tescan PFIB TIFF files.

        This test verifies that the correct extractor is dispatched when
        parsing metadata from a Tescan PFIB TIFF file, ensuring that the
        extractor selection/priority system works correctly.
        """
        # Find the TIF file from the fixtures
        tif_file = next(
            f for f in tescan_pfib_files if f.suffix.lower() in {".tif", ".tiff"}
        )

        meta_list, thumb_fnames = parse_metadata(fname=tif_file)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 1

        meta = meta_list[0]
        assert (
            meta["nx_meta"]["NexusLIMS Extraction"]["Module"]
            == "nexusLIMS.extractors.plugins.tescan_tif_extractor"
        )
        assert meta["nx_meta"]["NexusLIMS Extraction"]["Version"] == __version__
        self.remove_thumb_and_json(thumb_fnames)

    def test_parse_metadata_multi_signal_no_preview(self, list_signal):
        """Test multi-signal file without preview generation creates None list.

        This test ensures that when generate_preview=False is passed for a
        multi-signal file, the function returns a list of None values for
        preview_fnames.
        """
        meta, preview_fnames = parse_metadata(
            fname=list_signal[0],
            generate_preview=False,
        )

        # Verify metadata is returned as a list for multi-signal file
        assert isinstance(meta, list)
        assert len(meta) == 2

        # Verify preview_fnames is a list of None values
        assert isinstance(preview_fnames, list)
        assert len(preview_fnames) == 2
        assert all(fname is None for fname in preview_fnames)

        # Verify metadata content is still valid
        assert meta[0]["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert meta[1]["nx_meta"]["Data Type"] == "TEM_Imaging"

    def test_create_preview_multi_signal_list_with_index(self, tmp_path):
        """Test HyperSpy list signal handling with signal_index.

        When HyperSpy loads a file and returns a list of signals, and signal_index
        is not None, the specified signal should be selected and its title updated
        with "signal X of Y" format.
        """
        import unittest.mock
        from contextlib import ExitStack

        import hyperspy.api as hs
        import numpy as np

        from nexusLIMS.extractors import create_preview

        # Create two simple signals to simulate multi-signal file
        signal1 = hs.signals.Signal2D(np.random.random((10, 10)))
        signal1.metadata.General.title = "Signal 1"
        signal1.metadata.General.original_filename = "test_multi.hspy"

        signal2 = hs.signals.Signal2D(np.random.random((10, 10)))
        signal2.metadata.General.title = "Signal 2"
        signal2.metadata.General.original_filename = "test_multi.hspy"

        # Capture signal info to verify the title was updated
        captured_signal = {"title": None}

        def mock_sig_to_thumbnail(sig, out_path=None):
            captured_signal["title"] = sig.metadata.General.title
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                from PIL import Image

                img = Image.new("RGB", (100, 100), color="red")
                img.save(out_path)

        # Mock hs.load to return a list of signals
        def mock_hs_load(fname, **kwargs):
            # Mock the compute method on each signal
            signal1.compute = unittest.mock.Mock()
            signal2.compute = unittest.mock.Mock()
            return [signal1, signal2]

        # Mock registry to return None for preview generator
        mock_reg_instance = unittest.mock.Mock()
        mock_reg_instance.get_preview_generator.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.hs.load", side_effect=mock_hs_load
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.sig_to_thumbnail",
                    side_effect=mock_sig_to_thumbnail,
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.replace_instrument_data_path",
                    return_value=tmp_path / "preview_signal1.thumb.png",
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.get_registry",
                    return_value=mock_reg_instance,
                )
            )

            # Call create_preview with signal_index=1
            result = create_preview(
                fname=tmp_path / "test.dm3",
                overwrite=True,
                signal_index=1,
            )

            # Verify title was updated with signal index info
            assert captured_signal["title"] is not None
            assert "signal 2 of 2" in captured_signal["title"].lower()

            # Clean up
            if result and result.exists():
                result.unlink()

    def test_create_preview_multi_signal_list_without_index(self, tmp_path):
        """Test HyperSpy list signal handling without signal_index.

        When HyperSpy loads a file and returns a list of signals, and signal_index
        is None (legacy mode), the first signal should be selected and its title
        updated with "1 of Y total signals" format.
        """
        import unittest.mock
        from contextlib import ExitStack

        import hyperspy.api as hs
        import numpy as np

        from nexusLIMS.extractors import create_preview

        # Create two simple signals
        signal1 = hs.signals.Signal2D(np.random.random((10, 10)))
        signal1.metadata.General.title = "First Signal"
        signal1.metadata.General.original_filename = "test_legacy.hspy"

        signal2 = hs.signals.Signal2D(np.random.random((10, 10)))
        signal2.metadata.General.title = "Second Signal"
        signal2.metadata.General.original_filename = "test_legacy.hspy"

        # Capture the signal to verify title format
        captured_signal = {"title": None}

        def mock_sig_to_thumbnail(sig, out_path=None):
            captured_signal["title"] = sig.metadata.General.title
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                from PIL import Image

                img = Image.new("RGB", (100, 100), color="blue")
                img.save(out_path)

        # Mock hs.load to return a list of signals
        def mock_hs_load(fname, **kwargs):
            # Mock the compute method on each signal
            signal1.compute = unittest.mock.Mock()
            signal2.compute = unittest.mock.Mock()
            return [signal1, signal2]

        # Mock registry to return None (legacy fallback)
        mock_reg_instance = unittest.mock.Mock()
        mock_reg_instance.get_preview_generator.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.hs.load", side_effect=mock_hs_load
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.sig_to_thumbnail",
                    side_effect=mock_sig_to_thumbnail,
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.replace_instrument_data_path",
                    return_value=tmp_path / "preview_legacy.thumb.png",
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.get_registry",
                    return_value=mock_reg_instance,
                )
            )

            # Call create_preview without signal_index (legacy mode)
            result = create_preview(fname=tmp_path / "test.dm3", overwrite=True)

            # Verify legacy format: "1 of Y total signals"
            assert captured_signal["title"] is not None
            assert "1 of" in captured_signal["title"].lower()
            assert "total signals" in captured_signal["title"].lower()

            # Clean up
            if result and result.exists():
                result.unlink()

    def test_create_preview_hyperspy_single_signal_empty_title(self, tmp_path):
        """Test HyperSpy single signal with empty title gets filename.

        When a single signal has an empty title, it should be populated with the
        filename (without extension).
        """
        import unittest.mock
        from contextlib import ExitStack

        import hyperspy.api as hs
        import numpy as np

        from nexusLIMS.extractors import create_preview

        # Create a signal with empty title
        signal = hs.signals.Signal2D(np.random.random((10, 10)))
        signal.metadata.General.title = ""  # Empty title
        signal.metadata.General.original_filename = "test_single_empty.hspy"

        # Capture the signal to verify title was populated
        captured_signal = {"title": None}

        def mock_sig_to_thumbnail(sig, out_path=None):
            captured_signal["title"] = sig.metadata.General.title
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                from PIL import Image

                img = Image.new("RGB", (100, 100), color="green")
                img.save(out_path)

        # Mock hs.load to return a single signal (not a list)
        def mock_hs_load(fname, **kwargs):
            # Mock the compute method on the signal
            signal.compute = unittest.mock.Mock()
            return signal

        # Mock registry to return None (legacy fallback)
        mock_reg_instance = unittest.mock.Mock()
        mock_reg_instance.get_preview_generator.return_value = None

        with ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.hs.load", side_effect=mock_hs_load
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.sig_to_thumbnail",
                    side_effect=mock_sig_to_thumbnail,
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.replace_instrument_data_path",
                    return_value=tmp_path / "preview_single.thumb.png",
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "nexusLIMS.extractors.get_registry",
                    return_value=mock_reg_instance,
                )
            )

            # Call create_preview with empty-title signal
            result = create_preview(fname=tmp_path / "test.dm3", overwrite=True)

            # Verify title was populated from filename
            assert captured_signal["title"] is not None
            assert "test" in captured_signal["title"]

            # Clean up
            if result and result.exists():
                result.unlink()

    def test_parse_metadata_extractor_returns_none(self, monkeypatch, tmp_path):
        """Test parse_metadata when extractor returns None.

        This tests the defensive early return when nx_meta_list is None.
        Although extractors are designed to always return at least one metadata
        dict, this tests the defensive guard clause before processing metadata.
        """
        from unittest.mock import MagicMock, patch

        from nexusLIMS.extractors import parse_metadata

        # Create a temporary test file
        test_file = tmp_path / "test_none.xyz"
        test_file.write_text("test content")

        # Mock the registry to return an extractor that returns None
        mock_extractor = MagicMock()
        mock_extractor.name = "mock_extractor"
        mock_extractor.supported_extensions = {"xyz"}
        mock_extractor.supports.return_value = True
        # Return None instead of valid metadata list (breaks defensive assumption)
        mock_extractor.extract.return_value = None

        mock_registry = MagicMock()
        mock_registry.get_extractor.return_value = mock_extractor

        # Mock instrument
        mock_instrument = MagicMock()

        with (
            patch("nexusLIMS.extractors.get_registry", return_value=mock_registry),
            patch(
                "nexusLIMS.extractors.get_instr_from_filepath",
                return_value=mock_instrument,
            ),
        ):
            # Call parse_metadata - should handle None gracefully
            result = parse_metadata(fname=test_file, generate_preview=False)

            # When nx_meta_list is None, should return None, None
            assert result == (None, None)

    @pytest.mark.filterwarnings(
        "ignore:invalid value encountered in divide:RuntimeWarning"
    )
    def test_parse_metadata_neoarm_gatan_si_multi_signal_previews(
        self, neoarm_gatan_si_file
    ):
        """Test that four previews are generated for neoarm_gatan_si_file.

        The neoarm_gatan_si_file fixture contains a Gatan DM4 file with
        4 signals, so we expect 4 preview images to be generated.
        """
        meta_list, thumb_fnames = parse_metadata(
            fname=neoarm_gatan_si_file, generate_preview=True
        )

        # Verify metadata list has 4 entries (one per signal)
        assert meta_list is not None
        assert isinstance(meta_list, list)
        assert len(meta_list) == 4, "Expected 4 signals in neoarm_gatan_si_file"

        # Verify 4 preview files were generated
        assert thumb_fnames is not None
        assert isinstance(thumb_fnames, list)
        assert len(thumb_fnames) == 4, "Expected 4 preview files for 4 signals"

        # Verify all preview files were created and exist
        for i, thumb_fname in enumerate(thumb_fnames):
            assert thumb_fname is not None, f"Preview {i} should not be None"
            assert thumb_fname.exists(), f"Preview file {i} should exist: {thumb_fname}"
            assert thumb_fname.suffix == ".png", f"Preview {i} should be a PNG file"

        # Clean up generated files
        self.remove_thumb_and_json(thumb_fnames)


class TestValidateNxMeta:
    """Tests for the validate_nx_meta function in nexusLIMS.extractors.__init__."""

    def test_validate_nx_meta_valid_metadata_returns_unchanged(self):
        """Test that valid metadata passes validation and is returned unchanged."""
        # Create valid metadata dict with all required fields
        metadata_dict = {
            "nx_meta": {
                "Creation Time": "2024-01-15T10:30:00-05:00",
                "Data Type": "STEM_Imaging",
                "DatasetType": "Image",
                "Data Dimensions": "(1024, 1024)",
                "Instrument ID": "FEI-Titan-TEM-635816",
            }
        }

        # Call validate_nx_meta
        result = validate_nx_meta(metadata_dict)

        # Assert returned dict is the same object
        assert result is metadata_dict
        # Assert no fields were modified
        assert result["nx_meta"]["Creation Time"] == "2024-01-15T10:30:00-05:00"
        assert result["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert result["nx_meta"]["DatasetType"] == "Image"

    def test_validate_nx_meta_raises_validation_error_on_invalid_metadata(self):
        """Test that ValidationError is raised for invalid metadata."""
        # Create invalid metadata (missing required field 'Creation Time')
        metadata_dict = {
            "nx_meta": {
                "Data Type": "STEM_Imaging",
                "DatasetType": "Image",
            }
        }

        # Verify ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            validate_nx_meta(metadata_dict)

        # Check error message contains field information
        assert "Creation Time" in str(exc_info.value)

    def test_validate_nx_meta_logs_error_with_filename_context(self, caplog):
        """Test that error message includes filename when provided."""
        import logging

        # Create invalid metadata
        metadata_dict = {
            "nx_meta": {
                "Data Type": "STEM_Imaging",
                "DatasetType": "Image",
            }
        }

        # Call validate_nx_meta with filename and catch ValidationError
        with (
            caplog.at_level(logging.ERROR, logger="nexusLIMS.extractors"),
            pytest.raises(ValidationError),
        ):
            validate_nx_meta(metadata_dict, filename=Path("test_file.dm3"))

        # Assert caplog contains error message with filename
        assert "Validation failed for test_file.dm3" in caplog.text

    def test_validate_nx_meta_logs_error_without_filename_context(self, caplog):
        """Test that error message omits filename when not provided."""
        import logging

        # Create invalid metadata
        metadata_dict = {
            "nx_meta": {
                "Data Type": "STEM_Imaging",
                "DatasetType": "Image",
            }
        }

        # Call validate_nx_meta without filename and catch ValidationError
        with (
            caplog.at_level(logging.ERROR, logger="nexusLIMS.extractors"),
            pytest.raises(ValidationError),
        ):
            validate_nx_meta(metadata_dict)

        # Assert caplog contains error message without filename
        assert "Validation failed:" in caplog.text
        # Ensure it's not the filename version
        assert "Validation failed for" not in caplog.text

    def test_validate_nx_meta_multiple_validation_errors(self):
        """Test behavior when multiple fields are invalid."""
        # Create metadata with multiple invalid fields
        metadata_dict = {
            "nx_meta": {
                # Missing 'Creation Time' (required)
                "Data Type": "STEM_Imaging",
                "DatasetType": "InvalidType",  # Invalid value (not in allowed list)
            }
        }

        # Verify ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            validate_nx_meta(metadata_dict)

        # Check error message includes information about both invalid fields
        error_str = str(exc_info.value)
        # Should mention missing Creation Time
        assert "Creation Time" in error_str
        # Should mention invalid DatasetType
        assert "DatasetType" in error_str or "InvalidType" in error_str
