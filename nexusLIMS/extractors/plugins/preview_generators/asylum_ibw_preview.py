"""Preview images and force curves from Asylum IBW waves."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, ClassVar

import matplotlib.pyplot as plt
import numpy as np

from nexusLIMS.extractors.plugins.asylum_ibw import IMAGE_DIMS, is_asylum, read_wave

if TYPE_CHECKING:
    from pathlib import Path

    from nexusLIMS.extractors.base import ExtractionContext

_logger = logging.getLogger(__name__)


class AsylumIbwPreviewGenerator:
    """Render image channels with line flattening and unmodified force curves."""

    name = "asylum_ibw_preview"
    priority = 150
    supported_extensions: ClassVar = {"ibw"}

    def supports(self, context: ExtractionContext) -> bool:
        """Return whether this file is a supported Asylum wave."""
        return is_asylum(context.file_path)

    def generate(self, context: ExtractionContext, output_path: Path) -> bool:
        """Save a preview of the channels to the requested path."""
        fig = None
        try:
            wave, _note, labels = read_wave(context.file_path)
            data = wave["wData"]
            if data.ndim == IMAGE_DIMS:
                fig, axes = plt.subplots(
                    math.ceil(len(labels) / 2),
                    2,
                    figsize=(6, 6),
                    layout="constrained",
                    squeeze=False,
                )
                for ax, label, channel in zip(
                    axes.flat, labels, np.moveaxis(data, -1, 0), strict=False
                ):
                    # Axis 0 becomes the horizontal scan direction after transpose.
                    x = np.arange(channel.shape[0], dtype=float)
                    x -= x.mean()
                    centered = channel - channel.mean(axis=0)
                    denominator = np.sum(x * x)
                    if denominator:
                        slope = np.sum(x[:, None] * centered, axis=0) / denominator
                        centered = centered - x[:, None] * slope
                    ax.imshow(centered.T, origin="lower", cmap="gray")
                    ax.set_title(label)
                    ax.set_axis_off()
                for ax in list(axes.flat)[len(labels) :]:
                    ax.set_axis_off()
            else:
                fig, axes = plt.subplots(
                    len(labels), 1, figsize=(6, 6), layout="constrained", sharex=True
                )
                header = wave["wave_header"]
                time = np.arange(data.shape[0]) * header["sfA"][0] + header["sfB"][0]
                unit = (
                    header["dimUnits"][0].tobytes().split(b"\0", 1)[0].decode("latin-1")
                )
                for ax, label, channel in zip(
                    np.atleast_1d(axes), labels, data.T, strict=True
                ):
                    ax.plot(time, channel, linewidth=0.7)
                    ax.set_ylabel(label)
                np.atleast_1d(axes)[-1].set_xlabel(
                    f"Time ({unit})" if unit == "s" else f"Axis ({unit or 'unitless'})"
                )
            fig.savefig(output_path, dpi=100)
        except Exception:
            _logger.exception(
                "Could not generate Asylum IBW preview for %s", context.file_path
            )
            return False
        else:
            return True
        finally:
            if fig is not None:
                plt.close(fig)
