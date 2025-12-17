"""Image file preview generator."""

import logging
import shutil
from pathlib import Path
from typing import ClassVar, Tuple

import matplotlib.pyplot as plt
from PIL import Image, UnidentifiedImageError

from nexusLIMS.extractors.base import ExtractionContext

logger = logging.getLogger(__name__)

_LANCZOS = Image.Resampling.LANCZOS


def _pad_to_square(im_path: Path, new_width: int = 500):
    """
    Pad an image to square.

    Helper method to pad an image saved on disk to a square with size
    ``width x width``. This ensures consistent display on the front-end web
    page. Increasing the size of a dimension is done by padding with empty
    space. The original image is overwritten.

    Method adapted from:
    https://jdhao.github.io/2017/11/06/resize-image-to-square-with-padding/

    Parameters
    ----------
    im_path
        The path to the image that should be resized/padded
    new_width
        Desired output width/height of the image (in pixels)
    """
    image = Image.open(im_path)
    old_size = image.size  # old_size[0] is in (width, height) format
    ratio = float(new_width) / max(old_size)
    new_size = tuple(int(x * ratio) for x in old_size)
    image = image.resize(new_size, _LANCZOS)

    new_im = Image.new("RGBA", (new_width, new_width))
    new_im.paste(
        image,
        ((new_width - new_size[0]) // 2, (new_width - new_size[1]) // 2),
    )
    new_im.save(im_path)


def image_to_square_thumbnail(f: Path, out_path: Path, output_size: int) -> bool:
    """
    Generate a preview thumbnail from a non-data image file.

    Images of common filetypes will be transformed into 500 x 500 pixel images
    by first scaling the largest dimension to 500 pixels and then padding the
    resulting image to square.

    Parameters
    ----------
    f
        The string of the path of an image file for which a thumbnail should be
        generated.
    out_path
        A path to the desired thumbnail filename. All formats supported by
        :py:meth:`~PIL.Image.Image.save` can be used.
    output_size
        The desired resulting size of the thumbnail image.

    Returns
    -------
    bool
        Whether a preview was generated
    """
    shutil.copy(f, out_path)
    try:
        _pad_to_square(out_path, output_size)
    except UnidentifiedImageError as exc:
        logger.warning("no preview generated; PIL error text: %s", str(exc))
        out_path.unlink()
        return False

    return True


def down_sample_image(
    fname: Path,
    out_path: Path,
    output_size: Tuple[int, int] | None = None,
    factor: int | None = None,
):
    """
    Load an image file from disk, down-sample it to the requested dpi, and save.

    Sometimes the data doesn't need to be loaded as a HyperSpy signal,
    and it's better just to down-sample existing image data (such as for .tif
    files created by the Quanta SEM).

    Parameters
    ----------
    fname
        The filepath that will be resized. All formats supported by
        :py:func:`PIL.Image.open` can be used
    out_path
        A path to the desired thumbnail filename. All formats supported by
        :py:meth:`PIL.Image.Image.save` can be used.
    output_size
        A tuple of ints specifying the width and height of the output image.
        Either this argument or ``factor`` should be provided (not both).
    factor
        The multiple of the image size to reduce by (i.e. a value of 2
        results in an image that is 50% of each original dimension). Either
        this argument or ``output_size`` should be provided (not both).
    """
    if output_size is None and factor is None:
        msg = "One of output_size or factor must be provided"
        raise ValueError(msg)
    if output_size is not None and factor is not None:
        msg = "Only one of output_size or factor should be provided"
        raise ValueError(msg)

    image = Image.open(fname)
    size = image.size

    if output_size is not None:
        resized = output_size
    else:
        resized = tuple(s // factor for s in size)

    if "I" in image.mode:
        image = image.point(lambda i: i * (1.0 / 256)).convert("L")

    image.thumbnail(resized, resample=_LANCZOS)
    image.save(out_path)
    _pad_to_square(out_path, new_width=500)

    plt.rcParams["image.cmap"] = "gray"
    f = plt.figure()
    f.gca().imshow(image)

    return f


class ImagePreviewGenerator:
    """
    Preview generator for standard image files.

    This generator creates square thumbnail previews from image files
    (PNG, JPEG, TIFF, BMP, GIF) using PIL/Pillow.
    """

    name = "image_preview"
    priority = 100
    supported_extensions: ClassVar = {
        "png",
        "jpg",
        "jpeg",
        "tiff",
        "tif",
        "bmp",
        "gif",
    }

    def supports(self, context: ExtractionContext) -> bool:
        """
        Check if this generator supports the given file.

        Parameters
        ----------
        context
            The extraction context containing file information

        Returns
        -------
        bool
            True if file extension is a supported image format
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension in self.supported_extensions

    def generate(self, context: ExtractionContext, output_path: Path) -> bool:
        """
        Generate a square thumbnail preview from an image file.

        Parameters
        ----------
        context
            The extraction context containing file information
        output_path
            Path where the preview image should be saved

        Returns
        -------
        bool
            True if preview was successfully generated, False otherwise
        """
        try:
            logger.debug("Generating image preview for: %s", context.file_path)

            # Generate the thumbnail using the local function
            return image_to_square_thumbnail(
                context.file_path,
                output_path,
                output_size=500,
            )

        except Exception as e:
            logger.warning(
                "Failed to generate image preview for %s: %s",
                context.file_path,
                e,
            )
            return False
