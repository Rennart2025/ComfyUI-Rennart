"""Rennart Palette Preview node for ComfyUI.

Takes a JSON array of HEX colors (e.g. the `palette_json` output of
IdeogramPaletteExtractor) or a free-form text containing HEX codes, and renders
a horizontal swatch strip with HEX labels underneath — identical in format to
the preview produced by IdeogramPaletteExtractor.

Файл и путь: ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Palette_Preview.py
Категория: Rennart
"""

import json
import re

import torch

try:
    from .utils.color_grid_render import render_swatch_strip
except ImportError:
    # Fallback for standalone / direct-import test runs.
    from utils.color_grid_render import render_swatch_strip


# Regex for extracting HEX codes from free-form text (#RGB or #RRGGBB).
_HEX_PATTERN = re.compile(r"#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})\b")

FALLBACK_HEX = "#808080"


def _parse_input(text: str):
    """Best-effort parsing of the input string into a list of HEX colors.

    Accepts:
      - JSON array of hex strings: '["#FF5733", "#C70039"]'
      - A bare hex string:        '#FF5733'
      - Free-form text with hex codes anywhere: 'colors: #fff, #000000'
    """
    if not text or not str(text).strip():
        return []

    raw = str(text).strip()

    # 1) Try JSON first — this is what palette_json outputs.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(c) for c in parsed if c]
        if isinstance(parsed, str):
            raw = parsed  # fall through to regex below
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) Fall back to regex extraction from free-form text.
    matches = _HEX_PATTERN.findall(raw)
    cleaned = []
    for m in matches:
        if len(m) == 3:
            m = "".join(c * 2 for c in m)
        cleaned.append("#" + m.upper())
    return cleaned


class RennartPalettePreview:
    """Renders a horizontal swatch strip from HEX colors.

    Inputs:
        hex_string: JSON array of hex strings, or free-form text with hex codes.
        swatch_size: width/height of each color block in pixels.
        show_labels: draw the HEX code under each swatch.

    Outputs:
        IMAGE: the rendered swatch strip (ComfyUI IMAGE tensor).
        COLOR_COUNT: number of colors actually drawn.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "hex_string": ("STRING", {"multiline": True, "default": ""}),
                "swatch_size": ("INT", {"default": 100, "min": 32, "max": 512, "step": 8}),
                "show_labels": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("IMAGE", "COLOR_COUNT")
    FUNCTION = "render_preview"
    CATEGORY = "Rennart"

    def render_preview(self, hex_string, swatch_size, show_labels=True):
        colors = _parse_input(hex_string)

        if not colors:
            colors = [FALLBACK_HEX]

        swatch = render_swatch_strip(
            colors,
            swatch_size=int(swatch_size),
            show_labels=bool(show_labels),
        )
        img_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (img_tensor, len(colors))


NODE_CLASS_MAPPINGS = {
    "RennartPalettePreview": RennartPalettePreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartPalettePreview": "🎨 Rennart Palette Preview",
}