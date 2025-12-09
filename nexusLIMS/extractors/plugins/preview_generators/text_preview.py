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

# Constants for text preview formatting
_MAX_ROWS_NOTE = 18  # Maximum rows for note-style text
_MAX_ROWS_DATA = 17  # Maximum rows for data-style text
_MAX_COLS = 44  # Maximum columns for text display
_DEFAULT_SIZE = 5  # default size in inches for the preview


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
    plt.close("all")
    plt.rcParams["image.cmap"] = "gray"

    try:
        # Try to decode with common encodings
        raw_bytes = f.read_bytes()

        # Try encodings in order of preference
        encodings_to_try = ["utf-8", "windows-1250", "windows-1252"]
        content = None

        for encoding in encodings_to_try:
            try:
                content = raw_bytes.decode(encoding)
                logger.debug("Successfully decoded %s with %s encoding", f, encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            logger.warning(
                "Failed to decode text file %s with any supported encoding", f
            )
            return False

    except Exception as e:
        logger.warning("Failed to read text file %s: %s", f, e)
        return False

    # Normalize line endings (CRLF to LF) for consistent handling
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Expand tabs to spaces (tabs can render as black squares in matplotlib)
    content = content.expandtabs(tabsize=4)

    # Count newlines to determine if it's data or a note
    newline_count = content.count("\n")

    # Threshold to distinguish between data (many newlines) and notes (few newlines)
    # Using _MAX_ROWS_NOTE as threshold since notes are displayed in that many rows
    is_data = newline_count > _MAX_ROWS_NOTE

    if is_data:
        # Data mode: first _MAX_COLS characters of first _MAX_ROWS_DATA lines
        lines = content.split("\n")[:_MAX_ROWS_DATA]
        formatted_text = "\n".join(line[:_MAX_COLS] for line in lines)
    else:
        # Note mode: wrap to _MAX_COLS columns, up to _MAX_ROWS_NOTE rows
        # Wrap the text to _MAX_COLS columns
        wrapper = textwrap.TextWrapper(width=_MAX_COLS)
        wrapped_lines = []
        for line in content.split("\n"):
            if line.strip():  # Non-empty lines
                wrapped_lines.extend(wrapper.wrap(line))
            else:  # Preserve empty lines
                wrapped_lines.append("")

        # Take first _MAX_ROWS_NOTE rows
        formatted_text = "\n".join(wrapped_lines[:_MAX_ROWS_NOTE])

    # Escape special characters that matplotlib's mathtext parser might interpret
    # Replace $ with \$ to prevent mathtext parsing, and escape backslashes
    formatted_text = formatted_text.replace("\\", "\\\\").replace("$", r"\$")

    # Create a matplotlib figure with no frame
    fig = plt.figure(
        figsize=(_DEFAULT_SIZE, _DEFAULT_SIZE),
        dpi=output_size / _DEFAULT_SIZE,
    )

    plt.axis("off")

    # Add the text to the figure
    # Using monospace font and left-aligned at top
    # Use DejaVu Sans Mono for better Unicode/emoji support than generic monospace
    # This font is included with matplotlib and has wider character support
    fig.text(
        0.02,
        0.97,
        formatted_text,
        fontfamily="DejaVu Sans Mono",
        fontsize=12,
        verticalalignment="top",
        horizontalalignment="left",
        usetex=False,
        linespacing=1.7,  # Increase line spacing (default is 1.2)
    )

    fig.tight_layout()

    # Save the figure
    try:
        fig.savefig(out_path, dpi=output_size / _DEFAULT_SIZE)
        _pad_to_square(out_path, output_size)
    except Exception as e:
        logger.warning("Failed to save text thumbnail to %s: %s", out_path, e)
        plt.close(fig)
        return False
    else:
        plt.close(fig)
        return fig


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
            logger.debug("Generating text preview for: %s", context.file_path)

            # Generate the thumbnail using the local function
            text_to_thumbnail(
                context.file_path,
                output_path,
                output_size=500,
            )

            return output_path.exists()
        except Exception as e:
            logger.warning(
                "Failed to generate text preview for %s: %s",
                context.file_path,
                e,
            )
            return False
