"""Horizontal swatch strip renderer for Rennart nodes.

Produces output identical to IdeogramPaletteExtractor's preview_utils:
a single horizontal row of color swatches, each with its HEX code drawn in a
dedicated dark band underneath.

The renderer is self-contained (only numpy + Pillow) so it can be imported by
any node inside the ComfyUI-Rennart package via relative import:

    from .utils.color_grid_render import render_swatch_strip
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- Layout constants (match IdeogramPaletteExtractor / preview_utils) ---
SWATCH_HEIGHT = 100
SWATCH_WIDTH = 100
LABEL_BAND_HEIGHT = 24
LABEL_BG = (24, 24, 24)
LABEL_FG = (235, 235, 235)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _load_font(size: int):
    """Load a readable TrueType font, falling back gracefully across environments."""
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        # Pillow >= 10 supports a scalable default font via the size kwarg.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hex_to_rgb(hex_str: str):
    """Convert '#RRGGBB' or '#RGB' to an (r, g, b) tuple of ints 0-255."""
    h = str(hex_str).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Bad hex color: {hex_str!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def render_swatch_strip(
    hex_colors,
    swatch_size: int = SWATCH_WIDTH,
    show_labels: bool = True,
) -> np.ndarray:
    """Render a horizontal strip of color swatches with HEX labels.

    Args:
        hex_colors: list of hex color strings, e.g. ["#FF5733", "#C70039"].
        swatch_size: width (and color-block height) in pixels of each swatch.
        show_labels: if True, draw a label band under each swatch with its exact
            hex code (the same value Ideogram consumes).

    Returns:
        numpy float32 array of shape (H, swatch_size * len(hex_colors), 3),
        values in 0-1 range, where H = swatch_size (+ label band if labels shown).
        Falls back to a single gray swatch if hex_colors is empty or invalid.
    """
    valid = []
    for h in hex_colors or []:
        try:
            valid.append((h, _hex_to_rgb(h)))
        except (ValueError, TypeError):
            continue

    if not valid:
        valid = [("#808080", (128, 128, 128))]

    width = swatch_size * len(valid)
    band = LABEL_BAND_HEIGHT if show_labels else 0
    total_height = swatch_size + band

    img = Image.new("RGB", (width, total_height), LABEL_BG)
    draw = ImageDraw.Draw(img)
    hex_font = _load_font(15)

    for i, (hex_str, rgb) in enumerate(valid):
        x0 = i * swatch_size
        draw.rectangle(
            [x0, 0, x0 + swatch_size - 1, swatch_size - 1],
            fill=rgb,
        )

        if show_labels:
            draw.text(
                (x0 + 6, swatch_size + 5),
                str(hex_str).upper(),
                fill=LABEL_FG,
                font=hex_font,
            )

    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr