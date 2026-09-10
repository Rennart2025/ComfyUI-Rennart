"""Rennart Palette Extractor node for ComfyUI.

Extracts a perceptually distinct color palette from an image via k-means
clustering, deduplicated using Delta-E distance in LAB space, and returns
the result as a JSON hex array plus a swatch preview image.

Port of Ideogram's IdeogramPaletteExtractor, adapted for the Rennart package:
uses the local `utils/color_palette_extract.py` and `utils/color_grid_render.py`.

Файл и путь: ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Palette_Extractor.py
Категория: Rennart
"""

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
        palette_json: JSON array of hex strings, dominant color first.
        palette_preview: horizontal swatch strip IMAGE of the extracted colors.
        color_count: number of colors actually returned after deduplication.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "num_colors": ("INT", {"default": 6, "min": 2, "max": 16}),
                "min_delta_e": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0, "step": 0.5}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("palette_json", "palette_preview", "color_count")
    FUNCTION = "extract"
    CATEGORY = "Rennart"

    def extract(self, image, num_colors, min_delta_e):
        try:
            pil_image = _tensor_to_pil(image)
            hex_colors = _extract_palette(pil_image, num_colors, min_delta_e)
            if not hex_colors:
                hex_colors = [FALLBACK_HEX]
        except Exception:
            hex_colors = [FALLBACK_HEX]

        palette_json = json.dumps(hex_colors)
        swatch = render_swatch_strip(hex_colors)
        preview_tensor = torch.from_numpy(swatch).unsqueeze(0)

        return (palette_json, preview_tensor, len(hex_colors))


NODE_CLASS_MAPPINGS = {
    "RennartPaletteExtractor": RennartPaletteExtractor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartPaletteExtractor": "🎨 Rennart Palette Extractor",
}