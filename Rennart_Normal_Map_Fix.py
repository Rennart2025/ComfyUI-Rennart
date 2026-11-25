r"""
Rennart nodes for ComfyUI
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Normal_Map_Fix.py
Категория: Rennart/Image

[RU] Утилита для исправления карт нормалей из разных источников.
Переворачивает каналы R/G/B под конвенции DirectX и OpenGL (Marigold обычно
отдаёт DirectX — зелёный «вниз», многие генераторы — OpenGL), ослабляет
силу рельефа (сдвиг к плоской нормали) и перенормализует векторы до
единичной длины. Полезна для подготовки чужих normal map под любые ноды,
ожидающие конкретную конвенцию, и для 3D-пайплайнов.
Репозиторий: https://github.com/Rennart2025/ComfyUI-Rennart

[EN] Utility node for fixing normal maps from different sources.
Flips the R/G/B channels to match DirectX and OpenGL conventions (Marigold
usually outputs DirectX — green "down", many generators output OpenGL),
weakens the relief strength (shifts normals toward the flat normal) and
renormalizes vectors to unit length. Useful for preparing third-party
normal maps for any node that expects a specific convention, and for
3D pipelines.
Repository: https://github.com/Rennart2025/ComfyUI-Rennart
"""

import torch


class RennartNormalMapFix:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "normal_map": ("IMAGE",),
                "flip_red": ("BOOLEAN", {"default": False}),
                "flip_green": ("BOOLEAN", {"default": False}),
                "flip_blue": ("BOOLEAN", {"default": False}),
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Сила рельефа: 1.0 — как в исходной карте, "
                               "0.0 — плоская нормаль (рельеф убран)"}),
                "normalize": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Перенормализовать векторы до единичной "
                               "длины (рекомендуется держать включённым)"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("normal_map",)
    FUNCTION = "process"
    CATEGORY = "Rennart/Image"

    def process(self, normal_map, flip_red, flip_green, flip_blue,
                strength, normalize):
        # HWC, [0..1] -> векторы [-1..1]
        n = normal_map * 2.0 - 1.0

        # Перевороты каналов под конвенции DirectX/OpenGL
        if flip_red:
            n = torch.cat([-n[..., 0:1], n[..., 1:2], n[..., 2:3]], dim=-1)
        if flip_green:
            n = torch.cat([n[..., 0:1], -n[..., 1:2], n[..., 2:3]], dim=-1)
        if flip_blue:
            n = torch.cat([n[..., 0:1], n[..., 1:2], -n[..., 2:3]], dim=-1)

        # Ослабление рельефа: сдвиг к плоской нормали (0, 0, 1)
        if strength < 1.0:
            flat = torch.zeros_like(n)
            flat[..., 2] = 1.0
            n = flat + (n - flat) * strength

        # Перенормализация до единичной длины
        if normalize:
            length = torch.linalg.norm(n, dim=-1, keepdim=True)
            n = n / torch.clamp(length, min=1e-6)

        # Обратно в [0..1]
        result = torch.clamp(n * 0.5 + 0.5, 0.0, 1.0)
        return (result,)


# ==============================================
# Регистрация ноды
# ==============================================
NODE_CLASS_MAPPINGS = {
    "RennartNormalMapFix": RennartNormalMapFix,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartNormalMapFix": "Rennart Normal Map Fix",
}
