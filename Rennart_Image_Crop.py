"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Image_Crop.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart Image Crop (обрезка от центра с учётом кратности)
# ==============================================

class RennartImageCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "multiple": ("INT", {"default": 16, "min": 1, "max": 512, "step": 1}),
            }
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height", "longest_side", "shortest_side")
    FUNCTION = "crop_image"

    def crop_image(self, image, multiple):
        _, height, width, _ = image.shape

        new_width = (width // multiple) * multiple
        new_height = (height // multiple) * multiple
        longest_side = max(new_width, new_height)
        shortest_side = min(new_width, new_height)

        left = (width - new_width) // 2
        top = (height - new_height) // 2
        right = left + new_width
        bottom = top + new_height

        cropped_image = image[:, top:bottom, left:right, :]
        return (cropped_image, new_width, new_height, longest_side, shortest_side)

# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImageCrop": RennartImageCrop,
}

NODE_DISPLAY_NAME_MAPPINGS = {
     "RennartImageCrop": "✂️ Rennart Image Crop",
}