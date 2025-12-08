"""Text file preview generator."""

import logging
import textwrap
from pathlib import Path
from typing import Union

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from PIL import Image

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


def text_to_thumbnail(
    f: Path,
    out_path: Path,
    output_size: int = 500,
) -> Union[Figure, bool]:
    """
    Generate a preview thumbnail from a text file.

    For a text file, the contents will be formatted and written to a 500x500
    pixel jpg image of size 5 in by 5 in.

    If the text file has many newlines, it is probably data and the first 42
    characters of each of the first 20 lines of the text file will be written
    to the image.

    If the text file has a few (or fewer) newlines, it is probably a manually
    generated note and the text will be written to a 42 column, 18 row box
    until the space is exhausted.

    Parameters
    ----------
    f
        The path of a text file for which a thumbnail should be generated.
    out_path
        A path to the desired thumbnail filename. All formats supported by
        :py:meth:`~matplotlib.figure.Figure.savefig` can be used.
    output_size : int
        The pixel width (and height, since the image is padded to square) of
        the saved image file.

    Returns
    -------
    f : :py:class:`matplotlib.figure.Figure` or bool
        Handle to a matplotlib Figure, or the value False if a preview could not be
        generated
    """
    # close all currently open plots to ensure we don't leave a mess behind
    # in memory
    plt.close("all")
    plt.rcParams["image.cmap"] = "gray"

    # some instruments produce text files with different encodings, so we try a few
    # of the common ones. Also, escape "$" pattern that matplotlib
    # will interpret as a math formula and replace "\\t" with spaces for neat display
    textlist = None
    for enc in ["utf-8", "windows-1250", "windows-1252"]:
        try:
            with Path.open(f, encoding=enc) as textfile:
                textlist = (
                    textfile.read()
                    .replace("$", r"\\$")
                    .replace("\\t", "   ")
                    .splitlines()
                )
            break
        except UnicodeDecodeError as exc:
            logger.warning(
                "no preview generated; could not decode text file with encoding %s: %s",
                enc,
                str(exc),
            )
        finally:
            logger.info("opening the file with encoding: %s ", str(enc))

    if textlist is None:
        # textlist being None means that none of the encodings used could open the
        # text file, so we should just return False to indicate no preview was generated
        logger.warning(
            "Could not generate preview of text file with any available encoding",
        )
        return False

    textfig = plt.figure()
    # 5 x 5" is a good size
    size_inches = 5
    textfig.set_size_inches(size_inches, size_inches)
    dpi = output_size / size_inches
    plt.axis("off")

    # Number of newlines to distinguish between data-like and note-like text
    paragraph_check = 15
    num_lines_in_image = 19

    if len(textlist) <= paragraph_check:
        wrapped_text = []
        for i in textlist:
            wrapped_text = wrapped_text + textwrap.wrap(i, width=42)
        lines_printed = 0
        while lines_printed <= num_lines_in_image and lines_printed < len(wrapped_text):
            textfig.text(
                0.02,
                0.9 - lines_printed / 18,
                wrapped_text[lines_printed],
                fontsize=12,
                fontfamily="monospace",
            )
            lines_printed = lines_printed + 1
        # textfile is assumed to be hand-typed notes in paragraph format
        # we will wrap text until we run out of space

    else:
        # 17 is the maximum number of lines that will fit in this size image
        for i in range(17):
            textfig.text(
                0.02,
                0.9 - i / 18,
                textlist[i][0:48],
                fontsize=12,
                fontfamily="monospace",
            )
        # textfile is assumed to be some form of column data.
        # we will essentially create an image of the top left corner of the
        # text file.

    textfig.tight_layout()
    textfig.savefig(out_path, dpi=dpi)
    _pad_to_square(out_path, output_size)
    return textfig


class TextPreviewGenerator:
    """
    Preview generator for text files.

    This generator creates thumbnail previews of text files by rendering
    the first few lines of text as an image.
    """

    name = "text_preview"
    priority = 100

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
            True if file extension is .txt
        """
        extension = context.file_path.suffix.lower().lstrip(".")
        return extension == "txt"

    def generate(self, context: ExtractionContext, output_path: Path) -> bool:
        """
        Generate a thumbnail preview from a text file.

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
            logger.debug(
                "Generating text preview for: %s", context.file_path
            )

            # Generate the thumbnail using the local function
            text_to_thumbnail(
                context.file_path,
                output_path,
                output_size=500,
            )

            return output_path.exists()
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Failed to generate text preview for %s: %s",
                context.file_path,
                e,
            )
            return False
