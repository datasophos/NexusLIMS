# pylint: disable=C0116

"""Tests for plugin extractor classes (not adapters).

This test suite tests the plugin-based extractors that wrap legacy extraction
functions. These plugins are the new architecture that will eventually replace
direct calls to legacy extractors.
"""

from pathlib import Path

import pytest

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.basic_metadata import BasicFileInfoExtractor
from nexusLIMS.extractors.plugins.digital_micrograph import DM3Extractor
from nexusLIMS.extractors.plugins.edax import MsaExtractor, SpcExtractor
from nexusLIMS.extractors.plugins.fei_emi import SerEmiExtractor
from nexusLIMS.extractors.plugins.quanta_tif import QuantaTiffExtractor


class TestDM3Extractor:
    """Test DM3Extractor plugin."""

    def test_supports_dm3(self):
        """DM3Extractor should support .dm3 files."""
        extractor = DM3Extractor()
        context = ExtractionContext(Path("test.dm3"), None)
        assert extractor.supports(context)

    def test_supports_dm4(self):
        """DM3Extractor should support .dm4 files."""
        extractor = DM3Extractor()
        context = ExtractionContext(Path("test.dm4"), None)
        assert extractor.supports(context)

    def test_supports_uppercase(self):
        """DM3Extractor should support uppercase extensions."""
        extractor = DM3Extractor()
        context = ExtractionContext(Path("test.DM3"), None)
        assert extractor.supports(context)

    def test_does_not_support_other_extensions(self):
        """DM3Extractor should not support other extensions."""
        extractor = DM3Extractor()
        context = ExtractionContext(Path("test.tif"), None)
        assert not extractor.supports(context)

    def test_extract_with_real_file(self, list_signal, mock_instrument_from_filepath):
        """Test extraction with a real DM3 file."""
        from tests.unit.test_instrument_factory import make_test_tool

        mock_instrument_from_filepath(make_test_tool())

        extractor = DM3Extractor()
        context = ExtractionContext(list_signal[0], None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"
        assert metadata["nx_meta"]["Microscope"] == "TEST Titan_______"

    def test_has_required_attributes(self):
        """DM3Extractor should have required plugin attributes."""
        extractor = DM3Extractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "dm3_extractor"
        assert extractor.priority == 100


class TestQuantaTiffExtractor:
    """Test QuantaTiffExtractor plugin."""

    def test_supports_tif(self):
        """QuantaTiffExtractor should support .tif files."""
        extractor = QuantaTiffExtractor()
        context = ExtractionContext(Path("test.tif"), None)
        assert extractor.supports(context)

    def test_supports_tiff(self):
        """QuantaTiffExtractor should support .tiff files."""
        extractor = QuantaTiffExtractor()
        context = ExtractionContext(Path("test.tiff"), None)
        assert extractor.supports(context)

    def test_supports_uppercase(self):
        """QuantaTiffExtractor should support uppercase extensions."""
        extractor = QuantaTiffExtractor()
        context = ExtractionContext(Path("test.TIF"), None)
        assert extractor.supports(context)

    def test_does_not_support_other_extensions(self):
        """QuantaTiffExtractor should not support other extensions."""
        extractor = QuantaTiffExtractor()
        context = ExtractionContext(Path("test.dm3"), None)
        assert not extractor.supports(context)

    def test_extract_with_real_file(self, quanta_test_file):
        """Test extraction with a real Quanta TIF file."""
        extractor = QuantaTiffExtractor()
        context = ExtractionContext(quanta_test_file[0], None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["Data Type"] == "SEM_Imaging"
        assert metadata["nx_meta"]["DatasetType"] == "Image"

    def test_has_required_attributes(self):
        """QuantaTiffExtractor should have required plugin attributes."""
        extractor = QuantaTiffExtractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "quanta_tif_extractor"
        assert extractor.priority == 100


class TestSerEmiExtractor:
    """Test SerEmiExtractor plugin."""

    def test_supports_ser(self):
        """SerEmiExtractor should support .ser files."""
        extractor = SerEmiExtractor()
        context = ExtractionContext(Path("test.ser"), None)
        assert extractor.supports(context)

    def test_supports_uppercase(self):
        """SerEmiExtractor should support uppercase extensions."""
        extractor = SerEmiExtractor()
        context = ExtractionContext(Path("test.SER"), None)
        assert extractor.supports(context)

    def test_does_not_support_other_extensions(self):
        """SerEmiExtractor should not support other extensions."""
        extractor = SerEmiExtractor()
        context = ExtractionContext(Path("test.dm3"), None)
        assert not extractor.supports(context)

    def test_extract_with_real_file(self, fei_ser_files):
        """Test extraction with a real SER file."""
        from tests.unit.utils import get_full_file_path

        test_file = get_full_file_path(
            "Titan_TEM_1_STEM_image_dataZeroed_1.ser",
            fei_ser_files,
        )

        extractor = SerEmiExtractor()
        context = ExtractionContext(test_file, None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["DatasetType"] == "Image"
        assert metadata["nx_meta"]["Data Type"] == "STEM_Imaging"

    def test_has_required_attributes(self):
        """SerEmiExtractor should have required plugin attributes."""
        extractor = SerEmiExtractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "ser_emi_extractor"
        assert extractor.priority == 100


class TestSpcExtractor:
    """Test SpcExtractor plugin."""

    def test_supports_spc(self):
        """SpcExtractor should support .spc files."""
        extractor = SpcExtractor()
        context = ExtractionContext(Path("test.spc"), None)
        assert extractor.supports(context)

    def test_supports_uppercase(self):
        """SpcExtractor should support uppercase extensions."""
        extractor = SpcExtractor()
        context = ExtractionContext(Path("test.SPC"), None)
        assert extractor.supports(context)

    def test_does_not_support_other_extensions(self):
        """SpcExtractor should not support other extensions."""
        extractor = SpcExtractor()
        context = ExtractionContext(Path("test.msa"), None)
        assert not extractor.supports(context)

    def test_extract_with_real_file(self):
        """Test extraction with a real SPC file."""
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.spc"

        extractor = SpcExtractor()
        context = ExtractionContext(test_file, None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["Azimuthal Angle (deg)"] == pytest.approx(0.0)
        assert metadata["nx_meta"]["Live Time (s)"] == pytest.approx(30.000002)

    def test_has_required_attributes(self):
        """SpcExtractor should have required plugin attributes."""
        extractor = SpcExtractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "spc_extractor"
        assert extractor.priority == 100


class TestMsaExtractor:
    """Test MsaExtractor plugin."""

    def test_supports_msa(self):
        """MsaExtractor should support .msa files."""
        extractor = MsaExtractor()
        context = ExtractionContext(Path("test.msa"), None)
        assert extractor.supports(context)

    def test_supports_uppercase(self):
        """MsaExtractor should support uppercase extensions."""
        extractor = MsaExtractor()
        context = ExtractionContext(Path("test.MSA"), None)
        assert extractor.supports(context)

    def test_does_not_support_other_extensions(self):
        """MsaExtractor should not support other extensions."""
        extractor = MsaExtractor()
        context = ExtractionContext(Path("test.spc"), None)
        assert not extractor.supports(context)

    def test_extract_with_real_file(self):
        """Test extraction with a real MSA file."""
        test_file = Path(__file__).parent.parent / "files" / "leo_edax_test.msa"

        extractor = MsaExtractor()
        context = ExtractionContext(test_file, None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["Azimuthal Angle (deg)"] == pytest.approx(0.0)
        assert metadata["nx_meta"]["Beam Energy (keV)"] == pytest.approx(10.0)

    def test_has_required_attributes(self):
        """MsaExtractor should have required plugin attributes."""
        extractor = MsaExtractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "msa_extractor"
        assert extractor.priority == 100


class TestBasicFileInfoExtractor:
    """Test BasicFileInfoExtractor plugin (fallback)."""

    def test_supports_any_file(self):
        """BasicFileInfoExtractor should support any file (fallback)."""
        extractor = BasicFileInfoExtractor()
        context = ExtractionContext(Path("test.xyz"), None)
        assert extractor.supports(context)

    def test_supports_dm3(self):
        """BasicFileInfoExtractor should support even known extensions (fallback)."""
        extractor = BasicFileInfoExtractor()
        context = ExtractionContext(Path("test.dm3"), None)
        assert extractor.supports(context)

    def test_extract_with_real_file(self, basic_txt_file):
        """Test extraction with a real file."""
        extractor = BasicFileInfoExtractor()
        context = ExtractionContext(basic_txt_file, None)

        metadata = extractor.extract(context)

        assert metadata is not None
        assert "nx_meta" in metadata
        assert metadata["nx_meta"]["Data Type"] == "Unknown"
        assert metadata["nx_meta"]["DatasetType"] == "Unknown"
        assert "Creation Time" in metadata["nx_meta"]

    def test_has_required_attributes(self):
        """BasicFileInfoExtractor should have required plugin attributes."""
        extractor = BasicFileInfoExtractor()
        assert hasattr(extractor, "name")
        assert hasattr(extractor, "priority")
        assert extractor.name == "basic_file_info_extractor"
        assert extractor.priority == 0  # Lowest priority

    def test_priority_is_zero(self):
        """BasicFileInfoExtractor should have priority 0 (fallback)."""
        extractor = BasicFileInfoExtractor()
        assert extractor.priority == 0


class TestPluginIntegration:
    """Test plugin extractors work with ExtractionContext."""

    def test_all_plugins_accept_extraction_context(self):
        """All plugins should accept ExtractionContext in extract()."""
        plugins = [
            DM3Extractor(),
            QuantaTiffExtractor(),
            SerEmiExtractor(),
            SpcExtractor(),
            MsaExtractor(),
            BasicFileInfoExtractor(),
        ]

        for plugin in plugins:
            # Should not raise - all plugins must accept ExtractionContext
            assert hasattr(plugin, "extract")
            assert callable(plugin.extract)

    def test_all_plugins_implement_supports(self):
        """All plugins should implement supports() method."""
        plugins = [
            DM3Extractor(),
            QuantaTiffExtractor(),
            SerEmiExtractor(),
            SpcExtractor(),
            MsaExtractor(),
            BasicFileInfoExtractor(),
        ]

        for plugin in plugins:
            assert hasattr(plugin, "supports")
            assert callable(plugin.supports)

    def test_all_plugins_have_name_and_priority(self):
        """All plugins should have name and priority attributes."""
        plugins = [
            DM3Extractor(),
            QuantaTiffExtractor(),
            SerEmiExtractor(),
            SpcExtractor(),
            MsaExtractor(),
            BasicFileInfoExtractor(),
        ]

        for plugin in plugins:
            assert hasattr(plugin, "name")
            assert hasattr(plugin, "priority")
            assert isinstance(plugin.name, str)
            assert isinstance(plugin.priority, int)
