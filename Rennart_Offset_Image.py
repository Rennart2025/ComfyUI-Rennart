"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Offset_Image.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart Offset Image
# ==============================================

import torch


class RennartOffsetImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pixels": ("IMAGE",),
                "offset_mode": (["percentage", "pixels"], {"default": "percentage"}),
                "x_percent": ("FLOAT", {"default": 50.0, "min": 0.0, "max": 100.0, "step": 1}),
                "y_percent": ("FLOAT", {"default": 50.0, "min": 0.0, "max": 100.0, "step": 1}),
                "x_pixels": ("INT", {"default": 0, "min": -8192, "max": 8192, "step": 1}),
                "y_pixels": ("INT", {"default": 0, "min": -8192, "max": 8192, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "Rennart/Image"

    def run(self, pixels, offset_mode, x_percent, y_percent, x_pixels, y_pixels):
        n, y, x, c = pixels.size()

        if offset_mode == "percentage":
            y_shift = round(y * y_percent / 100)
            x_shift = round(x * x_percent / 100)
        else:  # pixels
            y_shift = y_pixels
            x_shift = x_pixels

        return (pixels.roll((y_shift, x_shift), (1, 2)),)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartOffsetImage": RennartOffsetImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartOffsetImage": "🔄 Rennart Offset Image",
}