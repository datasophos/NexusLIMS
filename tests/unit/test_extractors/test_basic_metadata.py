# pylint: disable=C0116
# ruff: noqa: D102

"""Tests for nexusLIMS.extractors.basic_metadata."""

from datetime import datetime as dt

from nexusLIMS.extractors.plugins.basic_metadata import get_basic_metadata


class TestBasicExtractor:
    """Tests nexusLIMS.extractors.basic_metadata."""

    def test_basic_extraction(self, basic_txt_file):
        metadata = get_basic_metadata(basic_txt_file)

        # test 'nx_meta' values of interest
        assert metadata["nx_meta"]["Data Type"] == "Unknown"
        assert metadata["nx_meta"]["DatasetType"] == "Unknown"
        assert "Creation Time" in metadata["nx_meta"]
        assert dt.fromisoformat(metadata["nx_meta"]["Creation Time"])

    def test_basic_extraction_no_extension(self, basic_txt_file_no_extension):
        metadata = get_basic_metadata(basic_txt_file_no_extension)

        # test 'nx_meta' values of interest
        assert metadata["nx_meta"]["Data Type"] == "Unknown"
        assert metadata["nx_meta"]["DatasetType"] == "Unknown"
        assert "Creation Time" in metadata["nx_meta"]
        assert dt.fromisoformat(metadata["nx_meta"]["Creation Time"])
