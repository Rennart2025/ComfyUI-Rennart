"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Blend_Images_Multi.py
Категория: Rennart/Image
"""

import torch
import comfy.utils


BLEND_MODES = ["multiply", "screen", "darken", "lighten"]


class RennartBlendImagesMulti:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "blend_mode": (BLEND_MODES, {
                    "default": "multiply",
                    "tooltip": (
                        "Режим наложения (применяется последовательно: image_1 ⊕ image_2 ⊕ ...):\n"
                        "• multiply — произведение (a × b)\n"
                        "• screen   — 1 − (1−a)(1−b)\n"
                        "• darken   — min(a, b)\n"
                        "• lighten  — max(a, b)"
                    )
                }),
            },
            "optional": {
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "image_3": ("IMAGE",),
                "image_4": ("IMAGE",),
                "image_5": ("IMAGE",),
                "image_6": ("IMAGE",),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "blend"
    DESCRIPTION = (
        "Последовательное смешивание до 6 изображений выбранным режимом.\n"
        "Порядок: image_1 ⊕ image_2 ⊕ image_3 ⊕ ...\n"
        "Меньше 2 подключённых — изображение проходит насквозь без изменений."
    )

    # ----- Вспомогательные методы -----

    def _blend_pair(self, a, b, mode):
        if mode == "multiply":
            return a * b
        if mode == "screen":
            return 1.0 - (1.0 - a) * (1.0 - b)
        if mode == "darken":
            return torch.min(a, b)
        if mode == "lighten":
            return torch.max(a, b)
        return a  # fallback

    def _resize_to(self, img, target_h, target_w):
        """img: [B, H, W, C] → [B, target_h, target_w, C]."""
        if img.shape[1] == target_h and img.shape[2] == target_w:
            return img
        resized = comfy.utils.common_upscale(
            img.movedim(-1, 1), target_w, target_h, "lanczos", "disabled"
        )
        return resized.movedim(1, -1)

    def _match_batch(self, a, b):
        """Сводит батчи к общему размеру: одиночные расширяются, остальные обрезаются до минимума."""
        if a.shape[0] == b.shape[0]:
            return a, b
        if a.shape[0] == 1:
            return a.expand(b.shape[0], -1, -1, -1), b
        if b.shape[0] == 1:
            return a, b.expand(a.shape[0], -1, -1, -1)
        n = min(a.shape[0], b.shape[0])
        return a[:n], b[:n]

    def _match_channels(self, a, b):
        """Сводит число каналов к минимуму (лишние отбрасываются)."""
        if a.shape[-1] == b.shape[-1]:
            return a, b
        n = min(a.shape[-1], b.shape[-1])
        return a[..., :n], b[..., :n]

    # ----- Основной метод -----

    def blend(self, blend_mode,
              image_1=None, image_2=None, image_3=None,
              image_4=None, image_5=None, image_6=None):
        images = [
            img for img in
            [image_1, image_2, image_3, image_4, image_5, image_6]
            if img is not None
        ]

        if len(images) == 0:
            raise ValueError(
                "[Rennart Blend Images Multi] Не подключено ни одного изображения."
            )

        if len(images) == 1:
            print("[Rennart Blend Images Multi] Подключено 1 изображение — пропускаю насквозь.")
            return (images[0],)

        ref = images[0]
        ref_h, ref_w = int(ref.shape[1]), int(ref.shape[2])

        result = ref
        for img in images[1:]:
            img = self._resize_to(img, ref_h, ref_w)
            result, img = self._match_batch(result, img)
            result, img = self._match_channels(result, img)
            result = self._blend_pair(result, img, blend_mode)

        # Значения могут выйти за пределы 0..1 из-за float-арифметики — клампим
        result = torch.clamp(result, 0.0, 1.0)

        return (result,)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartBlendImagesMulti": RennartBlendImagesMulti,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartBlendImagesMulti": "🧩 Rennart Blend Images Multi",
}