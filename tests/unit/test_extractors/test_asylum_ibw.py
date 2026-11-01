"""Integration coverage for Asylum IBW image and force-curve files."""

import gzip
from pathlib import Path

import pytest
from PIL import Image

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.registry import ExtractorRegistry


@pytest.mark.parametrize(
    ("filename", "dataset_type"),
    [("NS10013.ibw", "Image"), ("Image0037.ibw", "Spectrum")],
)
def test_asylum_ibw_extract_and_preview(filename, dataset_type, tmp_path):
    """Discover both plugins and render a preview for each example."""
    fixture_path = Path(__file__).parents[1] / "files" / f"{filename}.gz"
    path = tmp_path / filename
    path.write_bytes(gzip.decompress(fixture_path.read_bytes()))
    context = ExtractionContext(path)
    registry = ExtractorRegistry()
    extractor = registry.get_extractor(context)
    assert extractor.name == "asylum_ibw_extractor"
    metadata = extractor.extract(context)[0]
    assert metadata["nx_meta"]["DatasetType"] == dataset_type
    assert metadata["original_metadata"]["Raw Wave Note"].count("SaveImage:") >= 2
    if filename == "NS10013.ibw":
        assert metadata["original_metadata"]["ScanSize"] == "4e-06"
        assert metadata["original_metadata"]["ImagingMode"] == "Contact"
    else:
        assert metadata["original_metadata"]["TriggerChannel"] == "AmpVolts"
        assert metadata["original_metadata"]["Indexes"] == "0,951,1958"
    generator = registry.get_preview_generator(context)
    assert generator.name == "asylum_ibw_preview"
    output = tmp_path / "preview.png"
    assert generator.generate(context, output)
    assert output.stat().st_size > 1000
    with Image.open(output) as preview:
        assert preview.size == (600, 600)
        assert preview.convert("RGB").getextrema()[0][0] < 100


def test_corrupt_ibw_falls_back(tmp_path):
    """Invalid IBW files must not select the AFM plugin."""
    path = tmp_path / "invalid.ibw"
    path.write_bytes(b"not an igor wave")
    registry = ExtractorRegistry()
    assert (
        registry.get_extractor(ExtractionContext(path)).name
        == "basic_file_info_extractor"
    )


def test_image_metadata_uses_physical_units(tmp_path):
    """Scan and probe values should retain their physical units."""
    from nexusLIMS.extractors.plugins.asylum_ibw import AsylumIbwExtractor
    from nexusLIMS.extractors.xml_serialization import serialize_quantity_to_xml

    fixture = Path(__file__).parents[1] / "files" / "NS10013.ibw.gz"
    path = tmp_path / "image.ibw"
    path.write_bytes(gzip.decompress(fixture.read_bytes()))
    metadata = AsylumIbwExtractor().extract(ExtractionContext(path))[0]["nx_meta"]
    magnitude, unit = serialize_quantity_to_xml(metadata["extensions"]["Scan Size"])
    assert magnitude == pytest.approx(4)
    assert unit == "µm"
    assert metadata["extensions"]["Scan Size"].to(
        "micrometer"
    ).magnitude == pytest.approx(4)
    assert float(
        metadata["extensions"]["Spring Constant"].to("newton/meter").magnitude
    ) == pytest.approx(0.15258)


def test_missing_file_extract_does_not_raise(tmp_path):
    """A missing input must return minimal metadata rather than raising."""
    from nexusLIMS.extractors.plugins.asylum_ibw import AsylumIbwExtractor

    result = AsylumIbwExtractor().extract(ExtractionContext(tmp_path / "missing.ibw"))
    assert result[0]["nx_meta"]["DatasetType"] == "Misc"
    assert result[0]["nx_meta"]["warnings"]


@pytest.mark.parametrize(
    ("filename", "data_type"),
    [("NS10013.ibw", "AFM Image"), ("Image0037.ibw", "AFM Force Curve")],
)
def test_parse_metadata_validates_and_serializes(tmp_path, filename, data_type):
    """Both file types must pass validation and JSON serialization."""
    import json

    from nexusLIMS.extractors import _CustomEncoder, parse_metadata

    fixture = Path(__file__).parents[1] / "files" / f"{filename}.gz"
    path = tmp_path / filename
    path.write_bytes(gzip.decompress(fixture.read_bytes()))
    metadata, _ = parse_metadata(path, write_output=False, generate_preview=False)
    assert metadata[0]["nx_meta"]["Data Type"] == data_type
    assert str(metadata[0]["nx_meta"]["extensions"]["Scan Size"].units) == "micrometer"
    assert metadata[0]["nx_meta"]["extensions"]["Scan Size"].to(
        "micrometer"
    ).magnitude == pytest.approx(4 if filename == "NS10013.ibw" else 6)
    serialized = json.loads(json.dumps(metadata[0], cls=_CustomEncoder))
    assert "Scan Size" in serialized["nx_meta"]["extensions"]


def test_corrupt_file_preview_fails_cleanly(tmp_path):
    """A bad wave should not produce a successful preview."""
    from nexusLIMS.extractors.plugins.preview_generators.asylum_ibw_preview import (
        AsylumIbwPreviewGenerator,
    )

    path = tmp_path / "corrupt.ibw"
    path.write_bytes(b"not an igor wave")
    output = tmp_path / "preview.png"
    generator = AsylumIbwPreviewGenerator()
    assert not generator.supports(ExtractionContext(path))
    assert not generator.generate(ExtractionContext(path), output)
    assert not output.exists()


def test_reader_does_not_log_raw_file_bytes(tmp_path, caplog):
    """Debug logging must not dump private wave bytes into application logs."""
    import logging

    from nexusLIMS.extractors.plugins.asylum_ibw import read_wave

    fixture = Path(__file__).parents[1] / "files" / "Image0037.ibw.gz"
    path = tmp_path / "curve.ibw"
    path.write_bytes(gzip.decompress(fixture.read_bytes()))
    with caplog.at_level(logging.DEBUG):
        read_wave(path)
    assert not any(record.name == "igor2.struct" for record in caplog.records)


def test_image_preview_plots_each_measured_channel(tmp_path, monkeypatch):
    """The preview must draw actual data for each image channel."""
    import numpy as np
    from matplotlib.axes import Axes

    from nexusLIMS.extractors.plugins.preview_generators.asylum_ibw_preview import (
        AsylumIbwPreviewGenerator,
    )

    fixture = Path(__file__).parents[1] / "files" / "NS10013.ibw.gz"
    path = tmp_path / "image.ibw"
    path.write_bytes(gzip.decompress(fixture.read_bytes()))
    original = Axes.imshow
    plotted = []

    def capture(ax, data, *args, **kwargs):
        plotted.append(np.asarray(data))
        return original(ax, data, *args, **kwargs)

    monkeypatch.setattr(Axes, "imshow", capture)
    assert AsylumIbwPreviewGenerator().generate(
        ExtractionContext(path), tmp_path / "preview.png"
    )
    assert len(plotted) == 4
    assert all(
        channel.shape == (256, 256) and np.ptp(channel) > 0 for channel in plotted
    )
