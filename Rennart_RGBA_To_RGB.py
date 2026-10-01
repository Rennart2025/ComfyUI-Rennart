"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_RGBA_To_RGB.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart RGBA to RGB (отбрасывает альфа-канал)
# ==============================================

class RennartRGBAToRGB:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "convert"

    def convert(self, image):
        channels = image.shape[-1]

        if channels == 3:
            return (image,)

        if channels == 4:
            rgb_image = image[..., :3]
            return (rgb_image,)

        if channels == 1:
            rgb_image = image.repeat(1, 1, 1, 3)
            return (rgb_image,)

        if channels > 4:
            rgb_image = image[..., :3]
            return (rgb_image,)

        return (image,)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartRGBAToRGB": RennartRGBAToRGB,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartRGBAToRGB": "🎨 Rennart RGBA to RGB",
}