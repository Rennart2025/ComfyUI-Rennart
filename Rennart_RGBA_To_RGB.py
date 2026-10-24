"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_RGBA_To_RGB.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart RGBA to RGB (отбрасывает альфа-канал + отдаёт альфу отдельно)
# ==============================================

import torch


class RennartRGBAToRGB:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "image_alpha")
    FUNCTION = "convert"

    def convert(self, image):
        channels = image.shape[-1]
        B, H, W = image.shape[0], image.shape[1], image.shape[2]

        if channels == 3:
            # Уже RGB — пропускаем, альфа = полностью непрозрачная
            rgb = image
            alpha = torch.ones((B, H, W), dtype=image.dtype, device=image.device)

        elif channels == 4:
            # Отбрасываем альфа-канал, но возвращаем его как MASK
            rgb = image[..., :3]
            alpha = image[..., 3]

        elif channels == 1:
            # Grayscale → RGB (дублируем канал), альфа = полностью непрозрачная
            rgb = image.repeat(1, 1, 1, 3)
            alpha = torch.ones((B, H, W), dtype=image.dtype, device=image.device)

        else:
            # Нестандартное число каналов: берём первые 3 как RGB,
            # альфа — 4-й канал, если он есть, иначе полностью непрозрачная
            rgb = image[..., :3]
            if channels > 3:
                alpha = image[..., 3]
            else:
                alpha = torch.ones((B, H, W), dtype=image.dtype, device=image.device)

        return (rgb, alpha)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartRGBAToRGB": RennartRGBAToRGB,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartRGBAToRGB": "🎨 Rennart RGBA to RGB",
}