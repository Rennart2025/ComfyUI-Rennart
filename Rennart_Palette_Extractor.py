"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Palette_Extractor.py
Категория: Rennart/Color
"""

# ==============================================
# Rennart_Palette_Extractor
# ==============================================

import json

import numpy as np
import torch
from PIL import Image

try:
    from .utils.color_grid_render import render_swatch_strip
    from .utils.color_palette_extract import extract_palette as _extract_palette
except ImportError:
    # Fallback for direct/standalone imports (e.g. local test runs) where this
    # module isn't loaded as part of the installed package's relative tree.
    from utils.color_grid_render import render_swatch_strip
    from utils.color_palette_extract import extract_palette as _extract_palette

FALLBACK_HEX = "#808080"


def _tensor_to_pil(image_tensor: torch.Tensor) -> Image.Image:
    """Convert a ComfyUI IMAGE tensor (B, H, W, C), float 0-1, to a PIL RGB image (first frame)."""
    img = image_tensor[0].cpu().numpy()
    img = np.clip(img, 0.0, 1.0)
    img = (img * 255.0).astype(np.uint8)
    return Image.fromarray(img, mode="RGB")


class RennartPaletteExtractor:
    """Extracts a dominant color palette from an image for use in generation prompts.

    Inputs:
        image: reference IMAGE to extract colors from.
        num_colors: target palette size (k-means cluster count).
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.

    Outputs:
        palette_json: JSON fragment of the form
            "color_palette": ["#RRGGBB", ...]
            (no surrounding braces), dominant color first. Designed to be spliced
            directly into a larger prompt JSON object by an LLM or a prompt
            assembler node without extra wrapping.
        palette_preview: horizontal swatch strip IMAGE of the extracted colors.
        color_count: number of colors actually returned after deduplication.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "num_colors": ("INT", {"default": 8, "min": 2, "max": 16}),
                "min_delta_e": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("palette_json", "palette_preview", "color_count")
    FUNCTION = "extract"
    CATEGORY = "Rennart/Color"

    def extract(self, image, num_colors, min_delta_e):
        try:
            pil_image = _tensor_to_pil(image)
            hex_colors = _extract_palette(pil_image, num_colors, min_delta_e)
            if not hex_colors:
                hex_colors = [FALLBACK_HEX]
        except Exception:
            hex_colors = [FALLBACK_HEX]

        # Emit a bare JSON key/value fragment: "color_palette": ["#RRGGBB", ...]
        # No surrounding braces, so it can be dropped straight into a larger
        # prompt JSON object without the LLM having to strip or add anything.
        palette_json = '"color_palette": ' + json.dumps(hex_colors)

        swatch = render_swatch_strip(hex_colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json, preview_tensor, len(hex_colors))


NODE_CLASS_MAPPINGS = {
    "RennartPaletteExtractor": RennartPaletteExtractor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartPaletteExtractor": "🎨 Rennart Palette Extractor",
}