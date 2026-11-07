"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Image_Text_Captions.py
Категория: Rennart/Image
"""

import os
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


_INTERPOLATION = {
    "nearest": Image.NEAREST,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
    "lanczos": Image.LANCZOS,
}


def _int_to_rgb(color_int):
    return ((color_int >> 16) & 0xFF, (color_int >> 8) & 0xFF, color_int & 0xFF)


def _find_font():
    candidates = [
        os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf"),
    ]
    try:
        from matplotlib import font_manager
        candidates.insert(0, font_manager.findfont(
            font_manager.FontProperties(family="DejaVu Sans")
        ))
    except Exception:
        pass
    try:
        import site
        for sp in site.getsitepackages():
            candidates.append(os.path.join(
                sp, "matplotlib", "mpl-data", "fonts", "ttf", "DejaVuSans.ttf"
            ))
    except Exception:
        pass
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _tensor_to_pil(image):
    arr = (image.cpu().numpy() * 255.0).clip(0, 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    if arr.shape[2] >= 4:
        return Image.fromarray(arr[..., :4], mode="RGBA")
    return Image.fromarray(arr[..., :3], mode="RGB")


def _pil_to_tensor(img):
    arr = np.array(img).astype(np.float32) / 255.0
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    return torch.from_numpy(arr)


def _wrap_text(text, font, max_width, measure_draw):
    """Разбивает текст на строки, укладывающиеся в max_width."""
    if not text.strip():
        return []
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word) if current else word
        bbox = measure_draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            # Слово само по себе шире max_width — режем по символам
            wb = measure_draw.textbbox((0, 0), word, font=font)
            if wb[2] - wb[0] > max_width:
                sub = ""
                for ch in word:
                    test2 = sub + ch
                    b2 = measure_draw.textbbox((0, 0), test2, font=font)
                    if b2[2] - b2[0] <= max_width:
                        sub = test2
                    else:
                        if sub:
                            lines.append(sub)
                        sub = ch
                current = sub
            else:
                current = word
    if current:
        lines.append(current)
    return lines


class RennartImageTextCaptions:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "target_width": ("INT", {
                    "default": 1024, "min": 1, "max": 8192, "step": 1,
                    "tooltip": "Габарит по ширине (не превышается при keep_aspect_ratio)"
                }),
                "target_height": ("INT", {
                    "default": 1024, "min": 1, "max": 8192, "step": 1,
                    "tooltip": "Габарит по высоте (не превышается при keep_aspect_ratio)"
                }),
                "keep_aspect_ratio": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Keep",
                    "label_off": "Stretch",
                    "tooltip": (
                        "On  — fit по большей оси, пропорции сохраняются, габарит не превышается\n"
                        "Off — ресайз точно до target_width × target_height (с искажением)"
                    )
                }),
                "resize_if_smaller": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Upscale",
                    "label_off": "Keep size",
                    "tooltip": (
                        "Off — если вход меньше target, размер не увеличивается\n"
                        "On  — увеличивать до target"
                    )
                }),
                "interpolation": (["nearest", "bilinear", "bicubic", "lanczos"], {
                    "default": "lanczos"
                }),
                "text_above": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": (
                        "Текст над изображением. Пусто → полоса не добавляется.\n"
                        "Длинный текст автоматически переносится по строкам."
                    )
                }),
                "text_under": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": (
                        "Текст под изображением. Пусто → полоса не добавляется.\n"
                        "Длинный текст автоматически переносится по строкам."
                    )
                }),
                "text_height": ("INT", {
                    "default": 12, "min": 1, "max": 200, "step": 1,
                    "tooltip": (
                        "Размер шрифта в пикселях.\n"
                        "Высота полосы = отступ + N_строк × text_height + отступ.\n"
                        "Отступы: text_height/2 от края и text_height/2 от изображения."
                    )
                }),
                "text_align": (["center", "left", "right"], {"default": "center"}),
                "text_color": ("INT", {
                    "default": 0x000000, "min": 0, "max": 0xFFFFFF, "step": 1,
                    "display": "color",
                    "tooltip": "Цвет текста"
                }),
                "background_color": ("INT", {
                    "default": 0xFFFFFF, "min": 0, "max": 0xFFFFFF, "step": 1,
                    "display": "color",
                    "tooltip": "Цвет фона полос и заливки RGBA"
                }),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    DESCRIPTION = (
        "Ресайзит изображение (fit по большей оси или точный размер), затем добавляет\n"
        "полосы с текстом сверху и/или снизу. Длинный текст переносится по строкам.\n"
        "RGBA-вход заливается background_color."
    )

    def run(self, image, target_width, target_height, keep_aspect_ratio, resize_if_smaller,
            interpolation, text_above, text_under, text_height, text_align,
            text_color, background_color):

        BG = _int_to_rgb(background_color)
        FG = _int_to_rgb(text_color)
        font_path = _find_font()
        resample = _INTERPOLATION[interpolation]

        if font_path:
            font = ImageFont.truetype(font_path, size=text_height)
        else:
            print("[Rennart] ⚠️ DejaVuSans.ttf не найден, использую встроенный шрифт PIL (размер не масштабируется).")
            font = ImageFont.load_default()

        # Измерительный draw
        measure_img = Image.new("RGB", (1, 1))
        measure_draw = ImageDraw.Draw(measure_img)

        # --- 1. Ресайз всех изображений батча ---
        resized = []
        for i in range(image.shape[0]):
            img = _tensor_to_pil(image[i])
            W0, H0 = img.size

            if keep_aspect_ratio:
                scale = min(target_width / W0, target_height / H0)
                if not resize_if_smaller and scale > 1.0:
                    scale = 1.0
                new_W = max(1, int(round(W0 * scale)))
                new_H = max(1, int(round(H0 * scale)))
            else:
                if not resize_if_smaller and target_width >= W0 and target_height >= H0:
                    new_W, new_H = W0, H0
                else:
                    new_W, new_H = target_width, target_height

            if (new_W, new_H) != (W0, H0):
                img = img.resize((new_W, new_H), resample)

            resized.append(img)

        # Проверка: у всех изображений батча должен быть одинаковый размер
        sizes = set(im.size for im in resized)
        if len(sizes) > 1:
            raise ValueError(
                f"[Rennart] Изображения батча после ресайза получились разного размера: {sizes}. "
                f"Используйте keep_aspect_ratio=False или подавайте изображения одинакового размера."
            )

        W, H = resized[0].size

        # --- 2. Разбиение текста на строки ---
        # Доступная ширина текста = ширина холста минус отступы слева/справа
        max_text_width = max(1, W - 2 * text_height)

        above_lines = _wrap_text(text_above, font, max_text_width, measure_draw) if text_above.strip() else []
        under_lines = _wrap_text(text_under, font, max_text_width, measure_draw) if text_under.strip() else []

        # --- 3. Высота полос ---
        pad_half = text_height // 2
        pad_gap = text_height - pad_half
        line_height = text_height

        strip_above_h = (pad_half + len(above_lines) * line_height + pad_gap) if above_lines else 0
        strip_under_h = (pad_half + len(under_lines) * line_height + pad_gap) if under_lines else 0

        total_H = strip_above_h + H + strip_under_h

        # --- 4. Обработка каждого изображения ---
        out_batch = []
        for img in resized:
            # RGBA → RGB с заливкой background_color
            if img.mode == "RGBA":
                base = Image.new("RGB", img.size, BG)
                base.paste(img, mask=img.split()[3])
                img = base
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Итоговый холст
            canvas = Image.new("RGB", (W, total_H), BG)
            y_img = strip_above_h
            canvas.paste(img, (0, y_img))

            draw = ImageDraw.Draw(canvas)

            def draw_lines(lines, strip_top):
                for i, line in enumerate(lines):
                    y = strip_top + pad_half + i * line_height
                    if text_align == "left":
                        draw.text((text_height, y), line, fill=FG, font=font, anchor="lt")
                    elif text_align == "right":
                        draw.text((W - text_height, y), line, fill=FG, font=font, anchor="rt")
                    else:
                        draw.text((W // 2, y), line, fill=FG, font=font, anchor="mt")

            if above_lines:
                draw_lines(above_lines, 0)
            if under_lines:
                draw_lines(under_lines, y_img + H)

            out_batch.append(_pil_to_tensor(canvas))

        out = torch.stack(out_batch, dim=0)
        return (out,)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImageTextCaptions": RennartImageTextCaptions,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartImageTextCaptions": "📝 Rennart Image Text Captions",
}