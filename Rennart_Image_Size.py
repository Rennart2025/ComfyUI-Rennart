"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Image_Size.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart Image Size (с текстовым выходом)
# ==============================================

import torch

class RennartImageSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("image", "width", "height", "longest_side", "shortest_side", "info")
    FUNCTION = "get_image_size"

    def get_image_size(self, image):
        _, height, width, _ = image.shape
        longest_side = max(width, height)
        shortest_side = min(width, height)
        info = f"Width: {width}, Height: {height}"
        return (image, width, height, longest_side, shortest_side, info)

# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImageSize": RennartImageSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartImageSize": "📅 Rennart Image Size",
}