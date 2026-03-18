"""Tests for the Tofwerk fibTOF pFIB-ToF-SIMS HDF5 extractor and preview generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import h5py
import numpy as np

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.preview_generators.tofwerk_pfib_preview import (
    TofwerkPfibPreviewGenerator,
)
from nexusLIMS.extractors.plugins.tofwerk_pfib import TofwerkPfibExtractor

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(path: Path) -> ExtractionContext:
    return ExtractionContext(file_path=path)


def _get_ext(result: list[dict], field: str):
    """Return a field from nx_meta['extensions'] in the first result element."""
    return result[0]["nx_meta"]["extensions"][field]


# ---------------------------------------------------------------------------
# Extractor — supports()
# ---------------------------------------------------------------------------


class TestTofwerkPfibExtractorSupports:
    """Tests for TofwerkPfibExtractor.supports()."""

    def test_supports_raw_file(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        ctx = _make_context(tofwerk_raw_file)
        assert ext.supports(ctx) is True

    def test_supports_opened_file(self, tofwerk_opened_file):
        ext = TofwerkPfibExtractor()
        ctx = _make_context(tofwerk_opened_file)
        assert ext.supports(ctx) is True

    def test_rejects_non_h5_extension(self, tmp_path):
        p = tmp_path / "data.tif"
        p.write_bytes(b"\x00" * 16)
        ext = TofwerkPfibExtractor()
        assert ext.supports(_make_context(p)) is False

    def test_rejects_non_tofwerk_h5(self, tmp_path):
        """A generic HDF5 file (no TofDAQ markers) should not be supported."""
        p = tmp_path / "other.h5"
        with h5py.File(p, "w") as f:
            f.create_dataset("data", data=np.zeros((10, 10)))
        ext = TofwerkPfibExtractor()
        assert ext.supports(_make_context(p)) is False

    def test_rejects_missing_file(self, tmp_path):
        p = tmp_path / "nonexistent.h5"
        ext = TofwerkPfibExtractor()
        assert ext.supports(_make_context(p)) is False


# ---------------------------------------------------------------------------
# Extractor — extract()
# ---------------------------------------------------------------------------


class TestTofwerkPfibExtractorExtract:
    """Tests for TofwerkPfibExtractor.extract()."""

    def test_returns_list_with_one_element(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert isinstance(result, list)
        assert len(result) == 1

    def test_required_fields_present_raw(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        nx_meta = result[0]["nx_meta"]
        assert nx_meta["DatasetType"] == "SpectrumImage"
        assert nx_meta["Data Type"] == "PFIB_TOFSIMS"
        assert "Creation Time" in nx_meta

    def test_required_fields_present_opened(self, tofwerk_opened_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_opened_file))
        nx_meta = result[0]["nx_meta"]
        assert nx_meta["DatasetType"] == "SpectrumImage"
        assert nx_meta["Data Type"] == "PFIB_TOFSIMS"
        assert "Creation Time" in nx_meta

    def test_creation_time_from_acquisition_log(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        creation_time = result[0]["nx_meta"]["Creation Time"]
        # Fixture sets AcquisitionLog timestring to 2025-01-01T12:00:00-05:00
        assert creation_time == "2025-01-01T12:00:00-05:00"

    def test_creation_time_fallback_to_hdf5_creation_time(self, tmp_path):
        """When AcquisitionLog is absent, fall back to HDF5 File Creation Time."""
        p = tmp_path / "no_log.h5"
        with h5py.File(p, "w") as f:
            f.attrs["TofDAQ Version"] = np.float32(1.99)
            f.attrs["HDF5 File Creation Time"] = b"15.06.2024 10:30:00"
            f.create_group("FIBParams").attrs["FibHardware"] = b"Tescan"
            f.create_group("FIBImages").create_group("Image0000").create_dataset(
                "Data", data=np.zeros((10, 10))
            )
            fullspectra = f.create_group("FullSpectra")
            fullspectra.create_dataset(
                "SumSpectrum", data=np.zeros(512, dtype=np.float64)
            )
            fullspectra.create_dataset(
                "MassAxis", data=np.linspace(0, 200, 512, dtype=np.float32)
            )
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(p))
        creation_time = result[0]["nx_meta"]["Creation Time"]
        assert "2024-06-15" in creation_time

    def test_vendor_fields_in_extensions_not_top_level(self, tofwerk_raw_file):
        """Vendor-specific fields must live in nx_meta['extensions']."""
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        nx_meta = result[0]["nx_meta"]
        assert "extensions" in nx_meta
        ext_keys = set(nx_meta["extensions"].keys())
        # These must be in extensions, not top-level
        for key in ("fib_hardware", "accelerating_voltage", "ion_mode", "file_variant"):
            assert key in ext_keys, f"Expected '{key}' in extensions"
            assert key not in nx_meta, f"'{key}' should not be at top level of nx_meta"

    def test_voltage_is_pint_quantity_in_kv(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        voltage = _get_ext(result, "accelerating_voltage")
        # Fixture has 30000 V → 30 kV
        assert abs(float(voltage.magnitude) - 30.0) < 0.1
        assert "kilovolt" in str(voltage.units)

    def test_field_of_view_is_pint_quantity(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        fov = _get_ext(result, "field_of_view")
        # Fixture ViewField = 0.01 mm
        assert abs(float(fov.magnitude) - 0.01) < 1e-6

    def test_pixel_size_derived_correctly(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        pixel_size = _get_ext(result, "pixel_size")
        # 0.01 mm * 1000 / 16 pixels = 0.625 um/pixel
        assert abs(float(pixel_size.magnitude) - 0.625) < 1e-6

    def test_mass_range_present(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert "mass_range_min_Da" in result[0]["nx_meta"]["extensions"]
        assert "mass_range_max_Da" in result[0]["nx_meta"]["extensions"]
        assert _get_ext(result, "mass_range_max_Da") > _get_ext(
            result, "mass_range_min_Da"
        )

    def test_file_variant_raw(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "file_variant") == "raw"

    def test_file_variant_opened(self, tofwerk_opened_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_opened_file))
        assert _get_ext(result, "file_variant") == "opened"

    def test_chamber_pressure_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        pressure = _get_ext(result, "chamber_pressure")
        # Fixture sets pressure to 1.7e-4 Pa
        assert abs(float(pressure.magnitude) - 1.7e-4) < 1e-9
        assert "pascal" in str(pressure.units)

    def test_ion_mode_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "ion_mode") == "positive"

    def test_fib_hardware_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "fib_hardware") == "Tescan"

    def test_no_exception_on_corrupted_file(self, tmp_path):
        """extract() must not raise even for malformed/empty HDF5-like files."""
        p = tmp_path / "corrupt.h5"
        p.write_bytes(b"\x00" * 100)
        ext = TofwerkPfibExtractor()
        # supports() would return False, but test extract() is robust anyway
        result = ext.extract(_make_context(p))
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Creation Time" in result[0]["nx_meta"]


# ---------------------------------------------------------------------------
# Preview Generator — supports()
# ---------------------------------------------------------------------------


class TestTofwerkPfibPreviewGeneratorSupports:
    """Tests for TofwerkPfibPreviewGenerator.supports()."""

    def test_supports_raw_file(self, tofwerk_raw_file):
        gen = TofwerkPfibPreviewGenerator()
        assert gen.supports(_make_context(tofwerk_raw_file)) is True

    def test_supports_opened_file(self, tofwerk_opened_file):
        gen = TofwerkPfibPreviewGenerator()
        assert gen.supports(_make_context(tofwerk_opened_file)) is True

    def test_rejects_non_h5(self, tmp_path):
        p = tmp_path / "image.png"
        p.write_bytes(b"\x89PNG\r\n")
        gen = TofwerkPfibPreviewGenerator()
        assert gen.supports(_make_context(p)) is False

    def test_rejects_non_tofwerk_h5(self, tmp_path):
        p = tmp_path / "other.h5"
        with h5py.File(p, "w") as f:
            f.create_dataset("data", data=np.zeros(10))
        gen = TofwerkPfibPreviewGenerator()
        assert gen.supports(_make_context(p)) is False


# ---------------------------------------------------------------------------
# Preview Generator — generate()
# ---------------------------------------------------------------------------


class TestTofwerkPfibPreviewGeneratorGenerate:
    """Tests for TofwerkPfibPreviewGenerator.generate()."""

    def test_generate_raw_creates_png(self, tofwerk_raw_file, tmp_path):
        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview.png"
        result = gen.generate(_make_context(tofwerk_raw_file), out)
        assert result is True
        assert out.exists()

    def test_generate_opened_creates_png(self, tofwerk_opened_file, tmp_path):
        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview_opened.png"
        result = gen.generate(_make_context(tofwerk_opened_file), out)
        assert result is True
        assert out.exists()

    def test_output_is_500x500(self, tofwerk_raw_file, tmp_path):
        from PIL import Image

        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview.png"
        gen.generate(_make_context(tofwerk_raw_file), out)
        with Image.open(out) as img:
            assert img.size == (500, 500)

    def test_output_is_500x500_opened(self, tofwerk_opened_file, tmp_path):
        from PIL import Image

        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview_opened.png"
        gen.generate(_make_context(tofwerk_opened_file), out)
        with Image.open(out) as img:
            assert img.size == (500, 500)

    def test_generate_returns_false_on_bad_file(self, tmp_path):
        p = tmp_path / "bad.h5"
        p.write_bytes(b"\x00" * 100)
        out = tmp_path / "preview.png"
        gen = TofwerkPfibPreviewGenerator()
        result = gen.generate(_make_context(p), out)
        assert result is False
