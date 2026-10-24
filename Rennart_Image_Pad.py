"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Image_Pad.py
Категория: Rennart/Image
"""

import torch
import numpy as np


COLOR_MAP = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "gray": (128, 128, 128),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "orange": (255, 165, 0),
    "transparent": (0, 0, 0),
}


def _ceil_to_multiple(size, multiple):
    if multiple <= 1:
        return size
    return ((size + multiple - 1) // multiple) * multiple


def _compute_pad_axis(size, multiple, mode):
    new_size = _ceil_to_multiple(size, multiple)
    diff = new_size - size
    if diff == 0:
        return 0, 0
    if mode == "start":
        return 0, diff
    elif mode == "end":
        return diff, 0
    else:  # center
        before = diff // 2
        return before, diff - before


_POSITION_MAP = {
    "center":       ("center", "center"),
    "top-left":     ("start",  "start"),
    "top-right":    ("end",    "start"),
    "bottom-left":  ("start",  "end"),
    "bottom-right": ("end",    "end"),
}


def _pad_mask(mask, pad_left, pad_right, pad_top, pad_bottom, mode):
    """Паддинг маски [B, H, W] до нового размера."""
    m = mask.unsqueeze(1)  # [B, 1, H, W]
    try:
        if mode == "constant":
            # constant для маски: 1.0 — чтобы режим "not masked" давал непрозрачный паддинг
            return torch.nn.functional.pad(
                m, (pad_left, pad_right, pad_top, pad_bottom),
                mode="constant", value=1.0
            ).squeeze(1)
        else:
            return torch.nn.functional.pad(
                m, (pad_left, pad_right, pad_top, pad_bottom), mode=mode
            ).squeeze(1)
    except (RuntimeError, ValueError):
        print(f"[Rennart] ⚠️ pad_mode='{mode}' для маски невозможен, использую 'replicate'.")
        return torch.nn.functional.pad(
            m, (pad_left, pad_right, pad_top, pad_bottom), mode="replicate"
        ).squeeze(1)


class RennartImagePad:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "multiple": ("INT", {
                    "default": 32, "min": 1, "max": 512, "step": 1,
                    "tooltip": (
                        "Кратность, до которой размеры округляются ВВЕРХ.\n"
                        "Пример: сторона 1648, multiple=32 → 1664 (добавляется 16 px)."
                    )
                }),
                "pad_mode": (["constant", "edge", "reflect", "symmetric"], {
                    "default": "edge",
                    "tooltip": (
                        "Режим заполнения паддинга:\n"
                        "• constant  — сплошной цвет (см. background_color)\n"
                        "• edge      — наращивание краевых пикселей\n"
                        "• reflect   — зеркальное отражение без повтора края\n"
                        "• symmetric — зеркальное отражение с повтором края"
                    )
                }),
                "resize_position": (
                    ["center", "top-left", "top-right", "bottom-left", "bottom-right"],
                    {
                        "default": "center",
                        "tooltip": (
                            "Как распределяется паддинг вокруг изображения:\n"
                            "• center — поровну\n"
                            "• top-left — паддинг справа и снизу\n"
                            "• top-right — паддинг слева и снизу\n"
                            "• bottom-left — паддинг справа и сверху\n"
                            "• bottom-right — паддинг слева и сверху"
                        )
                    }
                ),
                "masking": (["masked", "not masked"], {
                    "default": "masked",
                    "tooltip": (
                        "• masked     — паддинг прозрачный (alpha=0)\n"
                        "• not masked — паддинг непрозрачный (alpha=1)"
                    )
                }),
            },
            "optional": {
                "mask": ("MASK", {
                    "tooltip": (
                        "Входящая альфа/маска прозрачности оригинала.\n"
                        "Если не подана — используется альфа-канал изображения (если RGBA),\n"
                        "иначе всё изображение считается непрозрачным."
                    )
                }),
                "background_color": (list(COLOR_MAP.keys()), {
                    "default": "gray",
                    "tooltip": "Цвет фона. Используется только при pad_mode = constant."
                }),
                "feathering": ("INT", {
                    "default": 0, "min": 0, "max": 512, "step": 1,
                    "tooltip": (
                        "Радиус растушёвки границы паддинга.\n"
                        "0 = резкая граница."
                    )
                }),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "width", "height")
    FUNCTION = "pad"

    def pad(self, image, multiple, pad_mode, resize_position, masking,
            mask=None, background_color="gray", feathering=0):
        B, H, W, C = image.shape

        # --- RGB-часть ---
        if C >= 3:
            rgb = image[..., :3]
        else:
            rgb = image.repeat(1, 1, 1, 3)[..., :3]

        # --- Распределение паддинга ---
        h_mode, v_mode = _POSITION_MAP.get(resize_position, ("center", "center"))
        pad_left, pad_right = _compute_pad_axis(W, multiple, h_mode)
        pad_top, pad_bottom = _compute_pad_axis(H, multiple, v_mode)

        H2 = H + pad_top + pad_bottom
        W2 = W + pad_left + pad_right

        # --- Цвет фона для constant ---
        fill = np.array(COLOR_MAP.get(background_color, (128, 128, 128))) / 255.0

        # --- Паддинг RGB ---
        rgb_np = rgb.cpu().numpy()
        padded_np = np.empty((B, H2, W2, 3), dtype=np.float32)

        for i in range(B):
            arr = rgb_np[i]
            try:
                if pad_mode == "constant":
                    padded_np[i] = np.pad(
                        arr,
                        ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)),
                        mode="constant",
                        constant_values=fill,
                    )
                else:
                    padded_np[i] = np.pad(
                        arr,
                        ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)),
                        mode=pad_mode,
                    )
            except ValueError:
                print(f"[Rennart] ⚠️ pad_mode='{pad_mode}' невозможен при паддинге больше стороны, использую 'edge'.")
                padded_np[i] = np.pad(
                    arr,
                    ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)),
                    mode="edge",
                )

        padded_rgb = torch.from_numpy(padded_np).to(image.device, dtype=image.dtype)

        # --- Паддинг-маска (1 = паддинг, 0 = оригинал) ---
        pad_mask = torch.ones((B, H2, W2), dtype=image.dtype, device=image.device)
        pad_mask[:, pad_top:pad_top + H, pad_left:pad_left + W] = 0.0

        if feathering > 0:
            f = feathering
            pm = pad_mask.unsqueeze(1)
            pm = torch.nn.functional.pad(pm, (f, f, f, f), mode="replicate")
            pm = torch.nn.functional.avg_pool2d(pm, kernel_size=f * 2 + 1, stride=1)
            pad_mask = pm.squeeze(1)

        # --- Входящая альфа ---
        if mask is not None:
            input_alpha = mask.to(image.device, dtype=image.dtype)
            if input_alpha.ndim == 4:
                input_alpha = input_alpha.squeeze(-1)
            # Проверка размера
            if input_alpha.shape[1] != H or input_alpha.shape[2] != W:
                raise ValueError(
                    f"[Rennart] Размер маски {input_alpha.shape[1:]} не совпадает с изображением {(H, W)}."
                )
            # Проверка батча
            if input_alpha.shape[0] != B:
                if input_alpha.shape[0] == 1:
                    input_alpha = input_alpha.expand(B, -1, -1)
                else:
                    raise ValueError(
                        f"[Rennart] Батч маски ({input_alpha.shape[0]}) не совпадает с батчем изображения ({B})."
                    )
        elif C >= 4:
            input_alpha = image[..., 3].to(image.device, dtype=image.dtype)
        else:
            input_alpha = torch.ones((B, H, W), dtype=image.dtype, device=image.device)

        # --- Паддинг входящей альфы ---
        padded_input_alpha = _pad_mask(
            input_alpha, pad_left, pad_right, pad_top, pad_bottom, pad_mode
        )

        # --- Паддинг-альфа (1 = видимо, 0 = прозрачно) ---
        if masking == "masked":
            padding_alpha = 1.0 - pad_mask
        else:
            padding_alpha = torch.ones_like(pad_mask)

        # --- Итоговая альфа = входящая × паддинг-альфа ---
        output_alpha = padded_input_alpha * padding_alpha

        # --- Собираем RGBA ---
        rgba = torch.cat([padded_rgb, output_alpha.unsqueeze(-1)], dim=-1)

        return (rgba, pad_mask, W2, H2)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImagePad": RennartImagePad,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartImagePad": "🖼️ Rennart Image Pad",
}