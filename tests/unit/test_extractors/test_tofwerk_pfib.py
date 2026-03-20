"""Tests for the Tofwerk fibTOF pFIB-ToF-SIMS HDF5 extractor and preview generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import h5py
import numpy as np

from nexusLIMS.extractors.base import ExtractionContext
from nexusLIMS.extractors.plugins.preview_generators.tofwerk_pfib_preview import (
    TofwerkPfibPreviewGenerator,
    _depth_plot_style,
    _norm_channel,
    _tic_display_limits,
)
from nexusLIMS.extractors.plugins.preview_generators.tofwerk_pfib_preview import (
    _read_attr_scalar as _preview_read_attr_scalar,
)
from nexusLIMS.extractors.plugins.tofwerk_pfib import (
    TofwerkPfibExtractor,
    _extract_fib_params,
    _parse_creation_time,
)

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
        for key in ("FIB Hardware", "accelerating_voltage", "Ion Mode", "File Variant"):
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
        pixel_size = _get_ext(result, "Pixel Size")
        # 0.01 mm * 1000 / 16 pixels = 0.625 um/pixel
        assert abs(float(pixel_size.magnitude) - 0.625) < 1e-6

    def test_mass_range_present(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert "Mass Range Minimum" in result[0]["nx_meta"]["extensions"]
        assert "Mass Range Maximum" in result[0]["nx_meta"]["extensions"]
        assert _get_ext(result, "Mass Range Maximum") > _get_ext(
            result, "Mass Range Minimum"
        )

    def test_file_variant_raw(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "File Variant") == "raw"

    def test_file_variant_opened(self, tofwerk_opened_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_opened_file))
        assert _get_ext(result, "File Variant") == "pre-processed"

    def test_chamber_pressure_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        pressure = _get_ext(result, "Chamber Pressure")
        # Fixture sets pressure to 1.7e-4 Pa
        assert abs(float(pressure.magnitude) - 1.7e-4) < 1e-9
        assert "pascal" in str(pressure.units)

    def test_ion_mode_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "Ion Mode") == "positive"

    def test_fib_hardware_extracted(self, tofwerk_raw_file):
        ext = TofwerkPfibExtractor()
        result = ext.extract(_make_context(tofwerk_raw_file))
        assert _get_ext(result, "FIB Hardware") == "Tescan"

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

    def test_output_is_1500x1500(self, tofwerk_raw_file, tmp_path):
        from PIL import Image

        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview.png"
        gen.generate(_make_context(tofwerk_raw_file), out)
        with Image.open(out) as img:
            assert img.size == (1500, 1500)

    def test_output_is_1500x1500_opened(self, tofwerk_opened_file, tmp_path):
        from PIL import Image

        gen = TofwerkPfibPreviewGenerator()
        out = tmp_path / "preview_opened.png"
        gen.generate(_make_context(tofwerk_opened_file), out)
        with Image.open(out) as img:
            assert img.size == (1500, 1500)

    def test_generate_returns_false_on_bad_file(self, tmp_path):
        p = tmp_path / "bad.h5"
        p.write_bytes(b"\x00" * 100)
        out = tmp_path / "preview.png"
        gen = TofwerkPfibPreviewGenerator()
        result = gen.generate(_make_context(p), out)
        assert result is False

    def test_supports_returns_false_on_unreadable_h5(self, tmp_path):
        """supports() returns False when the file cannot be opened by h5py."""
        p = tmp_path / "corrupt.h5"
        p.write_bytes(b"\x00" * 100)
        gen = TofwerkPfibPreviewGenerator()
        assert gen.supports(_make_context(p)) is False

    def test_generate_raises_on_empty_fib_images(self, tmp_path):
        """generate() returns False when FIBImages group has no sub-groups."""
        p = tmp_path / "no_images.h5"
        with h5py.File(p, "w") as f:
            f.attrs["TofDAQ Version"] = np.float32(1.99)
            f.attrs["IonMode"] = b"positive"
            f.attrs["NbrWrites"] = np.int32(2)
            f.attrs["HDF5 File Creation Time"] = b"01.01.2025 12:00:00"
            f.create_group("FIBParams").attrs["Voltage"] = np.float64(30000.0)
            f.create_group("FIBImages")  # empty -- no sub-groups
            fullspectra = f.create_group("FullSpectra")
            fullspectra.create_dataset(
                "SumSpectrum", data=np.zeros(512, dtype=np.float64)
            )
            fullspectra.create_dataset(
                "MassAxis", data=np.linspace(0, 200, 512, dtype=np.float32)
            )
        out = tmp_path / "preview.png"
        gen = TofwerkPfibPreviewGenerator()
        assert gen.generate(_make_context(p), out) is False

    def test_generate_opened_fewer_than_3_peaks_pads_rgb(self, tmp_path):
        """RGB channels are zero-padded when fewer than 3 peaks exceed min_mass."""
        p = tmp_path / "opened_2peaks.h5"
        nwrites, nsegs, nx, nsamples = 2, 4, 4, 128
        npeaks = 2
        peak_dtype = np.dtype(
            [
                ("label", "S64"),
                ("mass", np.float32),
                ("lower integration limit", np.float32),
                ("upper integration limit", np.float32),
            ]
        )
        # Both peaks above min_mass=5.0 so n_top=2 and one zero-pad channel is needed
        peaks = np.array(
            [
                (b"peak_A", np.float32(10.0), np.float32(9.5), np.float32(10.5)),
                (b"peak_B", np.float32(20.0), np.float32(19.5), np.float32(20.5)),
            ],
            dtype=peak_dtype,
        )
        from tests.unit.test_extractors.generate_tofwerk_test_files import _write_common

        with h5py.File(p, "w") as f:
            _write_common(f, nwrites, nsegs, nx, npeaks, nsamples)
            del f["PeakData/PeakTable"]
            f["PeakData"].create_dataset("PeakTable", data=peaks)
            rng = np.random.default_rng(99)
            peak_data = rng.exponential(50, (nwrites, nsegs, nx, npeaks)).astype(
                np.float32
            )
            f["PeakData"].create_dataset("PeakData", data=peak_data)
        out = tmp_path / "preview_2peaks.png"
        gen = TofwerkPfibPreviewGenerator()
        assert gen.generate(_make_context(p), out) is True
        assert out.exists()

    def test_generate_opened_zero_peaks_above_min_mass(self, tmp_path):
        """RGB composite uses zero channels when no peaks exceed min_mass."""
        p = tmp_path / "opened_0peaks.h5"
        nwrites, nsegs, nx, nsamples = 2, 4, 4, 128
        npeaks = 2
        peak_dtype = np.dtype(
            [
                ("label", "S64"),
                ("mass", np.float32),
                ("lower integration limit", np.float32),
                ("upper integration limit", np.float32),
            ]
        )
        # All peaks below min_mass=5.0 so n_top=0 and _zero_channel path is used
        peaks = np.array(
            [
                (b"peak_A", np.float32(1.0), np.float32(0.5), np.float32(1.5)),
                (b"peak_B", np.float32(2.0), np.float32(1.5), np.float32(2.5)),
            ],
            dtype=peak_dtype,
        )
        from tests.unit.test_extractors.generate_tofwerk_test_files import _write_common

        with h5py.File(p, "w") as f:
            _write_common(f, nwrites, nsegs, nx, npeaks, nsamples)
            del f["PeakData/PeakTable"]
            f["PeakData"].create_dataset("PeakTable", data=peaks)
            rng = np.random.default_rng(88)
            peak_data = rng.exponential(50, (nwrites, nsegs, nx, npeaks)).astype(
                np.float32
            )
            f["PeakData"].create_dataset("PeakData", data=peak_data)
        out = tmp_path / "preview_0peaks.png"
        gen = TofwerkPfibPreviewGenerator()
        assert gen.generate(_make_context(p), out) is True
        assert out.exists()

    def test_generate_opened_ion_label_lookup(self, tmp_path):
        """Peak label falls back to ion table lookup when label is 'nominal'."""
        p = tmp_path / "opened_ionalabel.h5"
        nwrites, nsegs, nx, nsamples = 2, 4, 4, 128
        peak_dtype = np.dtype(
            [
                ("label", "S64"),
                ("mass", np.float32),
                ("lower integration limit", np.float32),
                ("upper integration limit", np.float32),
            ]
        )
        # label="nominal" triggers ion table lookup; mass near Na+ (22.99 Da)
        peaks = np.array(
            [
                (b"nominal", np.float32(22.99), np.float32(22.5), np.float32(23.5)),
                (b"", np.float32(10.0), np.float32(9.5), np.float32(10.5)),
                (b"CO+", np.float32(27.99), np.float32(27.5), np.float32(28.5)),
            ],
            dtype=peak_dtype,
        )
        npeaks = len(peaks)
        from tests.unit.test_extractors.generate_tofwerk_test_files import _write_common

        with h5py.File(p, "w") as f:
            _write_common(f, nwrites, nsegs, nx, npeaks, nsamples)
            # Replace the PeakTable written by _write_common
            del f["PeakData/PeakTable"]
            f["PeakData"].create_dataset("PeakTable", data=peaks)
            rng = np.random.default_rng(77)
            peak_data = rng.exponential(50, (nwrites, nsegs, nx, npeaks)).astype(
                np.float32
            )
            f["PeakData"].create_dataset("PeakData", data=peak_data)
        out = tmp_path / "preview_ionlabel.png"
        gen = TofwerkPfibPreviewGenerator()
        assert gen.generate(_make_context(p), out) is True


# ---------------------------------------------------------------------------
# Private helper function coverage
# ---------------------------------------------------------------------------


class TestPrivateHelpers:
    """Tests for private helper functions to reach uncovered branches."""

    # -- tofwerk_pfib_preview.py helpers ------------------------------------

    def test_norm_channel_uniform_returns_zeros(self):
        """_norm_channel returns all zeros when the input array is uniform."""
        arr = np.full((4, 4), 5.0)
        result = _norm_channel(arr)
        assert np.all(result == 0.0)

    def test_preview_read_attr_scalar_missing_key(self, tmp_path):
        """_read_attr_scalar returns the default value when the key is absent."""
        p = tmp_path / "attrs.h5"
        with h5py.File(p, "w") as f:
            f.create_group("grp")
        with h5py.File(p, "r") as f:
            result = _preview_read_attr_scalar(
                f["grp"], "nonexistent", default="fallback"
            )
        assert result == "fallback"

    def test_preview_read_attr_scalar_bytes_value(self, tmp_path):
        """_read_attr_scalar decodes bytes attribute values to str."""
        p = tmp_path / "attrs.h5"
        with h5py.File(p, "w") as f:
            f.create_group("grp").attrs["key"] = b"hello"
        with h5py.File(p, "r") as f:
            result = _preview_read_attr_scalar(f["grp"], "key")
        assert result == "hello"

    def test_depth_plot_style_many_writes(self):
        """_depth_plot_style returns line-only style above the marker threshold."""
        fmt, _lw, ms, _mew = _depth_plot_style(51)
        assert fmt == "-"
        assert ms == 0

    def test_tic_display_limits_small_array(self):
        """_tic_display_limits uses the full array when it is too small for interior."""
        tiny = np.array([[1.0, 2.0], [3.0, 4.0]])
        lo, hi = _tic_display_limits(tiny)
        assert lo <= hi

    # -- tofwerk_pfib.py helpers --------------------------------------------

    def test_parse_creation_time_mtime_fallback(self, tmp_path):
        """_parse_creation_time falls back to file mtime when no timestamp attrs."""
        p = tmp_path / "no_time.h5"
        with h5py.File(p, "w") as f:
            f.attrs["TofDAQ Version"] = np.float32(1.99)
            # No AcquisitionLog, no HDF5 File Creation Time attr
        with h5py.File(p, "r") as f:
            result = _parse_creation_time(f, p)
        assert result  # non-empty ISO string from mtime

    def test_parse_creation_time_bytes_attr_decoded(self, tmp_path):
        """_parse_creation_time decodes np.bytes_ HDF5 File Creation Time attribute."""
        p = tmp_path / "bytes_time.h5"
        with h5py.File(p, "w") as f:
            f.attrs["HDF5 File Creation Time"] = np.bytes_(b"15.06.2024 10:30:00")
            # No AcquisitionLog so the fallback branch is used
        with h5py.File(p, "r") as f:
            result = _parse_creation_time(f, p)
        assert "2024-06-15" in result

    def test_extract_fib_params_missing_group(self, tmp_path):
        """_extract_fib_params does nothing when FIBParams group is absent."""
        p = tmp_path / "no_fibparams.h5"
        with h5py.File(p, "w") as f:
            f.create_group("other")
        nx_meta: dict = {}
        with h5py.File(p, "r") as f:
            _extract_fib_params(f, nx_meta)
        assert nx_meta == {}  # nothing was added
