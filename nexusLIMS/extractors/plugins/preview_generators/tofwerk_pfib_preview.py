"""Tofwerk fibTOF pFIB-ToF-SIMS preview generator plugin."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

import h5py
import matplotlib as mpl
import numpy as np

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.patches import Patch
from mpl_toolkits.axes_grid1 import make_axes_locatable

from nexusLIMS.extractors.plugins.preview_generators.image_preview import _pad_to_square

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.extractors.base import ExtractionContext

_logger = logging.getLogger(__name__)

_RGB_COLORS = ["#e41a1c", "#4daf4a", "#377eb8"]

# ---------------------------------------------------------------------------
# Ion mass lookup tables (monoisotopic masses)
# ---------------------------------------------------------------------------

_IONS_POSITIVE = [
    (1.00782, "H\u207a"),
    (2.01565, "H\u2082\u207a"),
    (3.02347, "H\u2083\u207a"),
    (7.01600, "Li\u207a"),
    (9.01218, "Be\u207a"),
    (11.00931, "B\u207a"),
    (12.00000, "C\u207a"),
    (13.00782, "CH\u207a"),
    (14.00307, "N\u207a"),
    (14.01565, "CH\u2082\u207a"),
    (15.02348, "CH\u2083\u207a"),
    (15.99491, "O\u207a"),
    (17.00274, "OH\u207a"),
    (18.01057, "H\u2082O\u207a"),
    (18.99840, "F\u207a"),
    (22.98977, "Na\u207a"),
    (23.98504, "Mg\u207a"),
    (26.98154, "Al\u207a"),
    (27.97693, "Si\u207a"),
    (30.97376, "P\u207a"),
    (31.97207, "S\u207a"),
    (34.96885, "\u00b3\u2075Cl\u207a"),
    (36.96590, "\u00b3\u2077Cl\u207a"),
    (38.96371, "K\u207a"),
    (39.96259, "Ca\u207a"),
    (42.97645, "AlO\u207a"),
    (43.97184, "SiO\u207a"),
    (44.95592, "Sc\u207a"),
    (45.95263, "\u2074\u2076Ti\u207a"),
    (46.95176, "\u2074\u2077Ti\u207a"),
    (47.94795, "Ti\u207a"),
    (48.94787, "\u2074\u2079Ti\u207a"),
    (49.94479, "\u2075\u2070Ti\u207a"),
    (50.94396, "V\u207a"),
    (51.94051, "Cr\u207a"),
    (53.93882, "\u2075\u2074Cr\u207a"),
    (53.93961, "\u2075\u2074Fe\u207a"),
    (54.93805, "Mn\u207a"),
    (55.93494, "Fe\u207a"),
    (57.93535, "\u2075\u2078Ni\u207a"),
    (58.93320, "Co\u207a"),
    (59.93078, "\u2076\u2070Ni\u207a"),
    (62.92960, "Cu\u207a"),
    (63.92914, "Zn\u207a"),
    (64.92784, "\u2076\u2075Cu\u207a"),
    (65.92603, "\u2076\u2076Zn\u207a"),
    (68.92558, "\u2076\u2079Ga\u207a"),
    (70.92470, "\u2077\u00b9Ga\u207a"),
    (73.92118, "Ge\u207a"),
    (74.92160, "As\u207a"),
    (78.91834, "Br\u207a"),
    (79.91652, "Se\u207a"),
    (83.91151, "Kr\u207a"),
    (84.91179, "Rb\u207a"),
    (87.90561, "Sr\u207a"),
    (88.90585, "Y\u207a"),
    (89.90470, "Zr\u207a"),
    (92.90638, "Nb\u207a"),
    (97.90541, "Mo\u207a"),
    (102.90550, "Rh\u207a"),
    (106.90509, "Ag\u207a"),
    (113.90336, "Cd\u207a"),
    (114.90388, "In\u207a"),
    (119.90220, "Sn\u207a"),
    (120.90381, "Sb\u207a"),
    (126.90447, "I\u207a"),
    (132.90543, "Cs\u207a"),
    (137.90524, "Ba\u207a"),
    (138.90635, "La\u207a"),
    (139.90543, "Ce\u207a"),
    (157.92410, "Gd\u207a"),
    (179.94655, "Hf\u207a"),
    (183.95093, "W\u207a"),
    (194.96479, "Pt\u207a"),
    (196.96655, "Au\u207a"),
    (207.97665, "Pb\u207a"),
]

_IONS_NEGATIVE = [
    (1.00782, "H\u207b"),
    (11.00931, "B\u207b"),
    (12.00000, "C\u207b"),
    (13.00782, "CH\u207b"),
    (14.00307, "N\u207b"),
    (15.99491, "O\u207b"),
    (17.00274, "OH\u207b"),
    (18.99840, "F\u207b"),
    (25.97926, "CN\u207b"),
    (26.98154, "Al\u207b"),
    (27.97693, "Si\u207b"),
    (30.97376, "P\u207b"),
    (31.97207, "S\u207b"),
    (34.96885, "\u00b3\u2075Cl\u207b"),
    (36.96590, "\u00b3\u2077Cl\u207b"),
    (47.94795, "Ti\u207b"),
    (51.94051, "Cr\u207b"),
    (55.93494, "Fe\u207b"),
    (62.92960, "Cu\u207b"),
    (78.91834, "Br\u207b"),
    (106.90509, "Ag\u207b"),
    (126.90447, "I\u207b"),
    (194.96479, "Pt\u207b"),
    (196.96655, "Au\u207b"),
    (207.97665, "Pb\u207b"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_channel(arr: np.ndarray) -> np.ndarray:
    """Normalize 2-D array to [0,1] with 1st/99th-percentile clipping."""
    lo, hi = np.percentile(arr, 1), np.percentile(arr, 99)
    if hi == lo:
        return np.zeros_like(arr, dtype=float)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def _read_attr_scalar(obj, key: str, default=None):
    """Return a scalar attribute value, decoding bytes if needed."""
    if key not in obj.attrs:
        return default
    val = np.asarray(obj.attrs[key]).flat[0]
    if isinstance(val, (bytes, np.bytes_)):
        val = val.decode()
    return val


def _build_ion_lookup(ions: list) -> dict:
    """Build a dict round(mass) -> [(exact_mass, label)] for fast lookup."""
    lookup: dict = {}
    for mass, label in ions:
        lookup.setdefault(round(mass), []).append((mass, label))
    return lookup


def _ion_label(mz: float, lookup: dict, tol: float = 0.35) -> str | None:
    """Return the label of the nearest ion within tol Da, or None."""
    key = round(mz)
    candidates = []
    for k in (key - 1, key, key + 1):
        candidates.extend(lookup.get(k, []))
    if not candidates:
        return None
    best_mass, best_lbl = min(candidates, key=lambda x: abs(x[0] - mz))
    return best_lbl if abs(best_mass - mz) <= tol else None


_MARKER_THRESHOLD = 50
_MIN_INTERIOR_PIXELS = 100
_MIN_PEAK_SEPARATION_DA = 2.0
_N_RGB_CHANNELS = 3
_MAX_XTICK_WRITES = 30
_MILLION = 1e6
_THOUSAND = 1e3


def _depth_plot_style(nwrites: int):
    """Return (fmt, lw, ms, mew) suitable for the write count."""
    if nwrites <= _MARKER_THRESHOLD:
        return "o-", 1.8, 5, 1.5
    return "-", 1.4, 0, 0


def _tic_display_limits(
    tic_map: np.ndarray,
    border_frac: float = 0.06,
    lo_pct: float = 2,
    hi_pct: float = 98,
) -> tuple[float, float]:
    """
    Compute robust vmin/vmax for TIC map by sampling only interior pixels.

    Excludes a border fraction to avoid edge-enhancement artefacts inflating
    the percentile clipping.
    """
    h, w = tic_map.shape
    bord = max(1, int(min(h, w) * border_frac))
    interior = tic_map[bord:-bord, bord:-bord]
    if interior.size < _MIN_INTERIOR_PIXELS:
        interior = tic_map
    return float(np.percentile(interior, lo_pct)), float(
        np.percentile(interior, hi_pct)
    )


def _add_colorbar(fig, ax, im, label: str, extend: str = "neither"):
    div = make_axes_locatable(ax)
    cax = div.append_axes("right", size="5%", pad=0.05)
    cb = fig.colorbar(im, cax=cax, extend=extend)
    cb.set_label(label, fontsize=7)
    cb.ax.tick_params(labelsize=6)
    return cb


def _compute_tic_from_eventlist(el: h5py.Dataset) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute TIC map (nsegs x nx) and per-write depth counts from EventList.

    Reads one write at a time to avoid loading the full ragged array into memory.

    Parameters
    ----------
    el
        EventList HDF5 dataset of shape (nwrites, nsegs, nx), object dtype

    Returns
    -------
    tic_map
        2-D int64 array of shape (nsegs, nx)
    depth_counts
        1-D int64 array of shape (nwrites,)
    """
    nwrites, nsegs, nx = el.shape
    tic_map = np.zeros((nsegs, nx), dtype=np.int64)
    depth_counts = np.zeros(nwrites, dtype=np.int64)
    vec_len = np.frompyfunc(len, 1, 1)
    for w in range(nwrites):
        counts_2d = vec_len(el[w, :, :]).astype(np.int64)
        tic_map += counts_2d
        depth_counts[w] = counts_2d.sum()
    return tic_map, depth_counts


# ---------------------------------------------------------------------------
# Preview generator class
# ---------------------------------------------------------------------------


class TofwerkPfibPreviewGenerator:
    """
    Preview generator for Tofwerk fibTOF pFIB-ToF-SIMS HDF5 files.

    Generates a composite preview image showing:

    - **Raw files:** FIB SE image | TIC map | Depth profile (row 0);
      Sum mass spectrum (row 1, full width)
    - **Opened files:** FIB SE image | TIC map | RGB composite (row 0);
      Sum spectrum | Depth profiles (row 1)
    """

    name = "tofwerk_pfib_preview"
    priority = 150
    supported_extensions: ClassVar = {"h5"}

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this generator supports the given file.

        Performs content sniffing identical to the extractor to confirm this is a
        Tofwerk fibTOF FIB-SIMS HDF5 file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if this is a Tofwerk fibTOF FIB-SIMS HDF5 file
        """
        if context.file_path.suffix.lower() != ".h5":
            return False
        try:
            with h5py.File(context.file_path, "r") as f:
                return (
                    "FullSpectra/SumSpectrum" in f
                    and "FIBParams" in f
                    and "FIBImages" in f
                    and "TofDAQ Version" in f.attrs
                )
        except Exception:
            return False

    def generate(self, context: ExtractionContext, output_path: Path) -> bool:
        """
        Generate a composite preview image for a Tofwerk fibTOF HDF5 file.

        Parameters
        ----------
        context
            The extraction context containing file information
        output_path
            Path where the preview PNG should be saved

        Returns
        -------
        bool
            True if preview was successfully generated, False otherwise
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _generate_preview(str(context.file_path), output_path)
            _pad_to_square(output_path, new_width=500)
        except Exception:
            _logger.exception("Failed to generate preview for %s", context.file_path)
            return False
        else:
            return True


# ---------------------------------------------------------------------------
# Core preview generation (module-level for easier testing)
# ---------------------------------------------------------------------------


def _generate_preview(  # noqa: PLR0912, PLR0915
    h5_path: str, output_path: Path, min_mass: float = 5.0
) -> None:
    """
    Generate and save a composite preview image for a Tofwerk fibTOF HDF5 file.

    Parameters
    ----------
    h5_path
        Path to the input HDF5 file
    output_path
        Path where the output PNG will be saved
    min_mass
        Minimum m/z threshold; peaks/spectrum below this mass are ignored
    """
    with h5py.File(h5_path, "r") as f:
        has_peaks = "PeakData/PeakData" in f

        # FIB image (first/original surface image)
        fib_keys = sorted(f["FIBImages"].keys())
        if not fib_keys:
            msg = "No FIBImages found in file"
            raise ValueError(msg)
        fib_image = f[f"FIBImages/{fib_keys[0]}/Data"][:]
        fib_h, fib_w = fib_image.shape

        # Mass axis and sum spectrum
        mass_axis = f["FullSpectra/MassAxis"][:]
        sum_spec = f["FullSpectra/SumSpectrum"][:]

        # Root metadata for title
        voltage_kv = float(_read_attr_scalar(f["FIBParams"], "Voltage", 0)) / 1000.0
        ion_mode = _read_attr_scalar(f, "IonMode", "unknown")
        acq_time = _read_attr_scalar(f, "HDF5 File Creation Time", "")
        fib_hw = _read_attr_scalar(f["FIBParams"], "FibHardware", "unknown")
        nbr_writes = int(_read_attr_scalar(f, "NbrWrites", 0))

        if has_peaks:
            peak_data = f["PeakData/PeakData"][:]
            peak_table = f["PeakData/PeakTable"][:]
        else:
            el = f["FullSpectra/EventList"]
            tic_map, depth_counts = _compute_tic_from_eventlist(el)
            tic_h, tic_w = tic_map.shape

    ion_lookup = _build_ion_lookup(
        _IONS_POSITIVE if str(ion_mode).lower() == "positive" else _IONS_NEGATIVE
    )

    # Trim spectrum to min_mass
    valid = mass_axis >= min_mass
    mass_v = mass_axis[valid]
    spec_v = sum_spec[valid]

    # Derived arrays for opened files
    if has_peaks:
        nwrites_pk, ny, nx, npeaks = peak_data.shape
        per_mass = peak_data.sum(axis=(0, 1, 2))
        spatial = peak_data.sum(axis=0)
        tic_map = spatial.sum(axis=2)
        depth_prof = peak_data.sum(axis=(1, 2))

        peak_masses = np.array([float(peak_table[i]["mass"]) for i in range(npeaks)])
        above_min = np.where(peak_masses >= min_mass)[0]
        n_top = min(3, len(above_min))
        top_idx = above_min[np.argsort(per_mass[above_min])[::-1][:n_top]]
        top_masses = [float(peak_table[i]["mass"]) for i in top_idx]

        def _fmt_peak_label(i):
            raw_lbl = peak_table[i]["label"]
            if isinstance(raw_lbl, (bytes, np.bytes_)):
                raw_lbl = raw_lbl.decode().strip()
            if raw_lbl and raw_lbl.lower() not in ("", "nominal"):
                return raw_lbl
            matched = _ion_label(float(peak_table[i]["mass"]), ion_lookup)
            return matched if matched else f"{float(peak_table[i]['mass']):.0f} Da"

        top_labels = [_fmt_peak_label(i) for i in top_idx]
        rgb_channels = []
        for i in range(n_top):
            rgb_channels.append(_norm_channel(spatial[:, :, top_idx[i]]))
        # Pad to 3 channels if fewer than 3 peaks above min_mass
        _zero_channel = np.zeros((ny, nx), dtype=float)
        while len(rgb_channels) < _N_RGB_CHANNELS:
            rgb_channels.append(
                np.zeros_like(rgb_channels[0]) if rgb_channels else _zero_channel
            )
        rgb = np.stack(rgb_channels, axis=2)
        writes = np.arange(nwrites_pk) + 1
        mode_str = "Processed"
    else:
        writes = np.arange(nbr_writes) + 1
        mode_str = "Raw"

    # Annotate top peaks in sum spectrum (spaced >= 2 Da apart)
    annotated = []
    for idx in np.argsort(spec_v)[::-1]:
        mz = mass_v[idx]
        if all(abs(mz - m) > _MIN_PEAK_SEPARATION_DA for m in annotated):
            annotated.append(mz)
        if len(annotated) >= (5 if has_peaks else 6):
            break

    # Figure layout
    if has_peaks:
        fig = plt.figure(figsize=(13, 9))
        fig.patch.set_facecolor("white")
        gs = gridspec.GridSpec(
            2,
            3,
            figure=fig,
            left=0.06,
            right=0.97,
            top=0.88,
            bottom=0.08,
            hspace=0.44,
            wspace=0.40,
        )
        ax_fib = fig.add_subplot(gs[0, 0])
        ax_tic = fig.add_subplot(gs[0, 1])
        ax_rgb = fig.add_subplot(gs[0, 2])
        ax_spec = fig.add_subplot(gs[1, :2])
        ax_dep = fig.add_subplot(gs[1, 2])
    else:
        fig = plt.figure(figsize=(12, 9))
        fig.patch.set_facecolor("white")
        gs = gridspec.GridSpec(
            2,
            3,
            figure=fig,
            left=0.07,
            right=0.97,
            top=0.88,
            bottom=0.09,
            hspace=0.42,
            wspace=0.38,
        )
        ax_fib = fig.add_subplot(gs[0, 0])
        ax_tic = fig.add_subplot(gs[0, 1])
        ax_dep = fig.add_subplot(gs[0, 2])
        ax_spec = fig.add_subplot(gs[1, :])

    # Panel: FIB SE image
    im_fib = ax_fib.imshow(fib_image, cmap="gray", aspect="equal")
    ax_fib.set_title(
        f"FIB Secondary Electron Image\n({fib_w}\xd7{fib_h} px)", fontsize=9
    )
    ax_fib.set_xlabel("X pixel", fontsize=8)
    ax_fib.set_ylabel("Y pixel", fontsize=8)
    ax_fib.tick_params(labelsize=7)
    _add_colorbar(fig, ax_fib, im_fib, "SE Intensity")

    # Panel: TIC map
    vmin, vmax = _tic_display_limits(tic_map)
    tic_h2, tic_w2 = tic_map.shape
    im_tic = ax_tic.imshow(
        tic_map,
        cmap="inferno",
        aspect="equal",
        vmin=vmin,
        vmax=vmax,
        origin="upper",
    )
    if has_peaks:
        tic_title = f"Total Ion Count Map\n({npeaks} peaks, {tic_w2}\xd7{tic_h2} px)"
        tic_cb_label = "Integrated counts"
    else:
        tic_title = f"Total Ion Count Map\n({nbr_writes} slices, {tic_w}\xd7{tic_h} px)"
        tic_cb_label = "Ion events"
    ax_tic.set_title(tic_title, fontsize=9)
    ax_tic.set_xlabel("X pixel", fontsize=8)
    ax_tic.set_ylabel("Y pixel", fontsize=8)
    ax_tic.tick_params(labelsize=7)
    _add_colorbar(fig, ax_tic, im_tic, tic_cb_label, extend="max")

    # Panel: RGB composite (opened only)
    if has_peaks:
        ax_rgb.imshow(rgb, aspect="equal", origin="upper")
        ax_rgb.set_title(
            "False-Color RGB Composite\n(peak-integrated spatial maps)", fontsize=9
        )
        ax_rgb.set_xlabel("X pixel", fontsize=8)
        ax_rgb.set_ylabel("Y pixel", fontsize=8)
        ax_rgb.tick_params(labelsize=7)
        legend_elements = [
            Patch(
                facecolor=_RGB_COLORS[i],
                label=f"{'RGB'[i]}: {top_labels[i]} ({top_masses[i]:.0f} Da)",
            )
            for i in range(n_top)
        ]
        ax_rgb.legend(
            handles=legend_elements,
            loc="lower right",
            fontsize=6.5,
            framealpha=0.75,
            handlelength=1.0,
        )

    # Panel: Depth profile
    fmt, lw, ms, mew = _depth_plot_style(len(writes))
    if has_peaks:
        for color, pidx, mass_c, lbl in zip(
            _RGB_COLORS, top_idx, top_masses, top_labels
        ):
            kw: dict = {
                "color": color,
                "linewidth": lw,
                "label": f"{lbl} ({mass_c:.0f} Da)",
            }
            if ms:
                kw.update(markersize=ms, markerfacecolor="white", markeredgewidth=mew)
            ax_dep.plot(writes, depth_prof[:, pidx], fmt, **kw)
        ax_dep.set_title("Depth Profiles\n(top 3 mass channels)", fontsize=9)
        ax_dep.set_ylabel("Integrated counts", fontsize=8)
        ax_dep.legend(fontsize=7, framealpha=0.7)
    else:
        kw = {"color": "steelblue", "linewidth": lw}
        if ms:
            kw.update(markersize=ms, markerfacecolor="white", markeredgewidth=mew)
        ax_dep.plot(writes, depth_counts, fmt, **kw)
        ax_dep.set_title(
            "Depth Profile\n(total ion events per milling step)", fontsize=9
        )
        ax_dep.set_ylabel("Total ion events", fontsize=8)

    ax_dep.set_xlabel("Milling step (write)", fontsize=8)
    ax_dep.tick_params(labelsize=7)
    if len(writes) <= _MAX_XTICK_WRITES:
        ax_dep.set_xticks(writes)
    ax_dep.yaxis.set_major_formatter(
        plt.FuncFormatter(
            lambda x, _: (
                f"{x / _MILLION:.1f}M"
                if x >= _MILLION
                else (f"{x / _THOUSAND:.0f}k" if x >= _THOUSAND else f"{x:.0f}")
            )
        )
    )
    ax_dep.grid(visible=True, linestyle="--", alpha=0.4)
    if len(writes) > 0:
        ax_dep.set_xlim(writes[0] - 0.5, writes[-1] + 0.5)
    if has_peaks and len(top_idx) > 0:
        all_counts = np.concatenate([depth_prof[:, i] for i in top_idx])
    elif has_peaks:
        all_counts = depth_prof.sum(axis=1)
    else:
        all_counts = depth_counts
    if len(all_counts) > 0:
        ylo, yhi = np.percentile(all_counts, 2), np.percentile(all_counts, 98)
        pad = (yhi - ylo) * 0.1 or yhi * 0.05 or 1.0
        ax_dep.set_ylim(ylo - pad, yhi + pad)

    # Panel: Sum mass spectrum
    ax_spec.plot(mass_v, spec_v, color="#2c7bb6", linewidth=0.7, alpha=0.9)
    ax_spec.fill_between(mass_v, spec_v, alpha=0.15, color="#2c7bb6")
    if has_peaks:
        for color, pidx, lbl in zip(_RGB_COLORS, top_idx, top_labels):
            lo = float(peak_table[pidx]["lower integration limit"])
            hi = float(peak_table[pidx]["upper integration limit"])
            mc = float(peak_table[pidx]["mass"])
            ax_spec.axvspan(
                lo, hi, alpha=0.18, color=color, label=f"{lbl} ({mc:.0f} Da)"
            )
            ax_spec.axvline(mc, color=color, linewidth=0.8, linestyle="--", alpha=0.7)
        ax_spec.set_title(
            "Summed Mass Spectrum -- top 3 peak integration windows highlighted",
            fontsize=9,
        )
        ax_spec.legend(fontsize=7, framealpha=0.7)
    else:
        ax_spec.set_title(
            "Summed Mass Spectrum (all pixels, all depth slices)", fontsize=9
        )

    ax_spec.set_yscale("log")
    ax_spec.set_xlabel("m/z (Da)", fontsize=8)
    ax_spec.set_ylabel("Ion counts (log)", fontsize=8)
    ax_spec.tick_params(labelsize=7)
    if len(mass_v) > 0:
        ax_spec.set_xlim(mass_v.min(), mass_v.max())
    ax_spec.grid(visible=True, linestyle="--", alpha=0.3, which="both")

    for mz in annotated:
        idx = int(np.argmin(np.abs(mass_v - mz)))
        lbl = _ion_label(mz, ion_lookup)
        annot = f"{lbl}\n({mz:.1f})" if lbl else f"{mz:.1f} Da"
        ax_spec.annotate(
            annot,
            xy=(mz, spec_v[idx]),
            xytext=(0, 10),
            textcoords="offset points",
            fontsize=6.5,
            ha="center",
            color="#1a4d7a",
            arrowprops={"arrowstyle": "->", "color": "gray", "lw": 0.6},
        )

    # Title and disclaimer
    if has_peaks:
        dim_str = f"{nwrites_pk} depth slices, {nx}\xd7{ny} px, {npeaks} peaks"
    else:
        dim_str = f"{nbr_writes} depth slices, {tic_w}\xd7{tic_h} px"

    fig.suptitle(
        f"pFIB-ToF-SIMS Preview ({mode_str})  |  "
        f"{fib_hw} FIB, {voltage_kv:.0f} kV, {ion_mode} mode  |  "
        f"{dim_str}  |  {acq_time}",
        fontsize=10,
        fontweight="bold",
        y=0.97,
    )
    fig.text(
        0.5,
        0.01,
        "\u26a0 Peak identifications are preliminary best-guess assignments based on "
        "monoisotopic mass matching (\xb10.35 Da). Verify with high-resolution data.",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color="#666666",
        style="italic",
    )

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
