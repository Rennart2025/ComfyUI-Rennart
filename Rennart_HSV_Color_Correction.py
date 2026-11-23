"""
Rennart nodes for ComfyUI
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_HSV_Color_Correction.py
Категория: Rennart/Image

[RU] Продвинутая нода для коррекции цвета изображения (Тон, Насыщенность, Яркость, Контраст). 
Поддерживает 4 метода расчета насыщенности (включая HSL как в Photoshop и перцептивные видео-стандарты) 
и 4 режима изменения яркости. Предотвращает неестественные артефакты при глобальной цветокоррекции.
Репозиторий: https://github.com/Rennart2025/ComfyUI-Rennart

[EN] Advanced image color correction node (Hue, Saturation, Brightness, Contrast). 
Supports 4 saturation calculation methods (including Photoshop-like HSL and perceptual video standards) 
and 4 brightness adjustment modes. Prevents unnatural artifacts during global color grading.
Repository: https://github.com/Rennart2025/ComfyUI-Rennart
"""

import torch

class RennartHSVColorCorrection:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "hue": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "saturation": ("FLOAT", {"default": 0.0, "min": -100.0, "max": 100.0, "step": 1.0}),
                "saturation_method": (
                    [
                        "HSV (Max-Based Brightness)", 
                        "HSL (Average Lightness)", 
                        "BT.601 (SDTV)", 
                        "BT.709 (sRGB/HDTV)", 
                        "BT.2020 (HDR/Wide Gamut)"
                    ], 
                    {"default": "HSL (Average Lightness)"}
                ),
                "brightness": ("FLOAT", {"default": 0.0, "min": -100.0, "max": 100.0, "step": 1.0}),
                "brightness_mode": (
                    [
                        "Exposure (Linear)", 
                        "Gamma (Midtones)", 
                        "Offset (Additive)", 
                        "HSL Lightness (Classic)"
                    ], 
                    {"default": "Exposure (Linear)"}
                ),
                "contrast": ("FLOAT", {"default": 0.0, "min": -100.0, "max": 100.0, "step": 1.0}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "info")
    FUNCTION = "process"
    CATEGORY = "Rennart/Image"

    def process(self, image, hue, saturation, saturation_method, brightness, brightness_mode, contrast):
        device = image.device
        dtype = image.dtype
        
        # Коэффициенты для масштабирования
        sat_mult = 1.0 + (saturation / 100.0)
        hue_rad = torch.deg2rad(torch.tensor(hue, device=device, dtype=dtype))
        
        # 1. Коррекция Hue и Saturation
        if saturation_method == "HSV (Max-Based Brightness)":
            result = self._apply_hsv(image, hue_rad, sat_mult)
        elif saturation_method == "HSL (Average Lightness)":
            result = self._apply_hsl(image, hue_rad, sat_mult)
        else:
            coeffs = {
                "BT.601 (SDTV)":          (0.299,  0.587,  0.114),
                "BT.709 (sRGB/HDTV)":     (0.2126, 0.7152, 0.0722),
                "BT.2020 (HDR/Wide Gamut)": (0.2627, 0.6780, 0.0593),
            }
            kr, kg, kb = coeffs[saturation_method]
            result = self._apply_ycbcr(image, hue_rad, sat_mult, kr, kg, kb)
            
        # 2. Коррекция Brightness
        if brightness_mode == "Exposure (Linear)":
            # Линейное умножение: 0% -> 1.0, 100% -> 2.0, -100% -> 0.0
            exp_mult = 1.0 + (brightness / 100.0)
            result = result * exp_mult
        elif brightness_mode == "Gamma (Midtones)":
            # Гамма-коррекция: 0% -> 1.0, 100% -> 0.5 (осветление), -100% -> 1.5 (затемнение)
            gamma = 1.0 - (brightness / 100.0) * 0.5
            # Избегаем деления на ноль и отрицательных значений
            result = torch.pow(torch.clamp(result, min=1e-6), 1.0 / gamma)
        elif brightness_mode == "Offset (Additive)":
            # Аддитивный сдвиг: 0% -> 0.0, 100% -> 1.0, -100% -> -1.0
            offset = brightness / 100.0
            result = result + offset
        elif brightness_mode == "HSL Lightness (Classic)":
            # Изменение канала L в HSL
            result = self._adjust_hsl_lightness(result, brightness / 100.0)
            
        # 3. Коррекция Contrast
        if contrast != 0.0:
            contrast_mult = 1.0 + (contrast / 100.0)
            # Формула контраста: (x - 0.5) * mult + 0.5
            result = (result - 0.5) * contrast_mult + 0.5
            
        # Финальный климпинг в допустимый диапазон [0.0, 1.0]
        result = torch.clamp(result, 0.0, 1.0)
        
        # 4. Генерация строки info
        info_text = self._generate_info(hue, saturation, saturation_method, brightness, brightness_mode, contrast)
        
        return (result, info_text)

    def _apply_hsv(self, image, hue_rad, sat_mult):
        r, g, b = image[..., 0:1], image[..., 1:2], image[..., 2:3]
        cmax = torch.max(image, dim=-1, keepdim=True)[0]
        cmin = torch.min(image, dim=-1, keepdim=True)[0]
        delta = cmax - cmin
        
        h = torch.zeros_like(cmax)
        mask_r = (cmax == r) & (delta > 1e-6)
        mask_g = (cmax == g) & (delta > 1e-6)
        mask_b = (cmax == b) & (delta > 1e-6)
        
        h[mask_r] = (g[mask_r] - b[mask_r]) / delta[mask_r]
        h[mask_g] = 2.0 + (b[mask_g] - r[mask_g]) / delta[mask_g]
        h[mask_b] = 4.0 + (r[mask_b] - g[mask_b]) / delta[mask_b]
        h = (h / 6.0) % 1.0
        
        s = torch.where(cmax > 1e-6, delta / cmax, torch.zeros_like(cmax))
        v = cmax
        
        h = (h + (hue_rad / (2.0 * 3.14159265359))) % 1.0
        s = torch.clamp(s * sat_mult, 0.0, 1.0)
        
        return self._hsv_to_rgb(h, s, v)

    def _apply_hsl(self, image, hue_rad, sat_mult):
        r, g, b = image[..., 0:1], image[..., 1:2], image[..., 2:3]
        cmax = torch.max(image, dim=-1, keepdim=True)[0]
        cmin = torch.min(image, dim=-1, keepdim=True)[0]
        delta = cmax - cmin
        
        h = torch.zeros_like(cmax)
        mask_r = (cmax == r) & (delta > 1e-6)
        mask_g = (cmax == g) & (delta > 1e-6)
        mask_b = (cmax == b) & (delta > 1e-6)
        
        h[mask_r] = (g[mask_r] - b[mask_r]) / delta[mask_r]
        h[mask_g] = 2.0 + (b[mask_g] - r[mask_g]) / delta[mask_g]
        h[mask_b] = 4.0 + (r[mask_b] - g[mask_b]) / delta[mask_b]
        h = (h / 6.0) % 1.0
        
        l = (cmax + cmin) * 0.5
        s = torch.where((l > 1e-6) & (l < 1.0 - 1e-6), delta / (1.0 - torch.abs(2.0 * l - 1.0)), torch.zeros_like(cmax))
        
        h = (h + (hue_rad / (2.0 * 3.14159265359))) % 1.0
        s = torch.clamp(s * sat_mult, 0.0, 1.0)
        
        return self._hsl_to_rgb(h, s, l)

    def _apply_ycbcr(self, image, hue_rad, sat_mult, kr, kg, kb):
        r, g, b = image[..., 0:1], image[..., 1:2], image[..., 2:3]
        
        y = kr * r + kg * g + kb * b
        cb = (b - y) / (2.0 * (1.0 - kb) + 1e-6)
        cr = (r - y) / (2.0 * (1.0 - kr) + 1e-6)
        
        cb = cb * sat_mult
        cr = cr * sat_mult
        
        cos_h = torch.cos(hue_rad)
        sin_h = torch.sin(hue_rad)
        cr_new = cr * cos_h - cb * sin_h
        cb_new = cr * sin_h + cb * cos_h
        
        r_new = y + 2.0 * (1.0 - kr) * cr_new
        b_new = y + 2.0 * (1.0 - kb) * cb_new
        g_new = (y - kr * r_new - kb * b_new) / (kg + 1e-6)
        
        return torch.cat([r_new, g_new, b_new], dim=-1)

    def _adjust_hsl_lightness(self, image, amount):
        # Конвертация в HSL для изменения только канала L
        r, g, b = image[..., 0:1], image[..., 1:2], image[..., 2:3]
        cmax = torch.max(image, dim=-1, keepdim=True)[0]
        cmin = torch.min(image, dim=-1, keepdim=True)[0]
        delta = cmax - cmin
        
        h = torch.zeros_like(cmax)
        mask_r = (cmax == r) & (delta > 1e-6)
        mask_g = (cmax == g) & (delta > 1e-6)
        mask_b = (cmax == b) & (delta > 1e-6)
        
        h[mask_r] = (g[mask_r] - b[mask_r]) / delta[mask_r]
        h[mask_g] = 2.0 + (b[mask_g] - r[mask_g]) / delta[mask_g]
        h[mask_b] = 4.0 + (r[mask_b] - g[mask_b]) / delta[mask_b]
        h = (h / 6.0) % 1.0
        
        l = (cmax + cmin) * 0.5
        s = torch.where((l > 1e-6) & (l < 1.0 - 1e-6), delta / (1.0 - torch.abs(2.0 * l - 1.0)), torch.zeros_like(cmax))
        
        # Корректировка L по формуле Photoshop
        l_new = torch.where(amount > 0.0, l + (1.0 - l) * amount, l + l * amount)
        l_new = torch.clamp(l_new, 0.0, 1.0)
        
        return self._hsl_to_rgb(h, s, l_new)

    def _hsv_to_rgb(self, h, s, v):
        c = v * s
        x = c * (1.0 - torch.abs((h * 6.0) % 2.0 - 1.0))
        m = v - c
        
        h6 = h * 6.0
        r_out = torch.zeros_like(h)
        g_out = torch.zeros_like(h)
        b_out = torch.zeros_like(h)
        
        m0 = (h6 < 1);  r_out[m0] = c[m0]; g_out[m0] = x[m0]; b_out[m0] = 0
        m1 = (h6 >= 1) & (h6 < 2); r_out[m1] = x[m1]; g_out[m1] = c[m1]; b_out[m1] = 0
        m2 = (h6 >= 2) & (h6 < 3); r_out[m2] = 0;        g_out[m2] = c[m2]; b_out[m2] = x[m2]
        m3 = (h6 >= 3) & (h6 < 4); r_out[m3] = 0;        g_out[m3] = x[m3]; b_out[m3] = c[m3]
        m4 = (h6 >= 4) & (h6 < 5); r_out[m4] = x[m4]; g_out[m4] = 0;        b_out[m4] = c[m4]
        m5 = (h6 >= 5); r_out[m5] = c[m5]; g_out[m5] = 0;        b_out[m5] = x[m5]
        
        return torch.cat([r_out + m, g_out + m, b_out + m], dim=-1)

    def _hsl_to_rgb(self, h, s, l):
        c = (1.0 - torch.abs(2.0 * l - 1.0)) * s
        x = c * (1.0 - torch.abs((h * 6.0) % 2.0 - 1.0))
        m = l - c * 0.5
        
        h6 = h * 6.0
        r_out = torch.zeros_like(h)
        g_out = torch.zeros_like(h)
        b_out = torch.zeros_like(h)
        
        m0 = (h6 < 1);  r_out[m0] = c[m0]; g_out[m0] = x[m0]; b_out[m0] = 0
        m1 = (h6 >= 1) & (h6 < 2); r_out[m1] = x[m1]; g_out[m1] = c[m1]; b_out[m1] = 0
        m2 = (h6 >= 2) & (h6 < 3); r_out[m2] = 0;        g_out[m2] = c[m2]; b_out[m2] = x[m2]
        m3 = (h6 >= 3) & (h6 < 4); r_out[m3] = 0;        g_out[m3] = x[m3]; b_out[m3] = c[m3]
        m4 = (h6 >= 4) & (h6 < 5); r_out[m4] = x[m4]; g_out[m4] = 0;        b_out[m4] = c[m4]
        m5 = (h6 >= 5); r_out[m5] = c[m5]; g_out[m5] = 0;        b_out[m5] = x[m5]
        
        return torch.cat([r_out + m, g_out + m, b_out + m], dim=-1)

    def _generate_info(self, hue, saturation, sat_method, brightness, bright_mode, contrast):
        return f"""🎨 Rennart HSV Color Correction

Продвинутая нода для коррекции цвета изображения (Тон, Насыщенность, Яркость, Контраст). 
Поддерживает 4 метода расчета насыщенности (включая HSL как в Photoshop и перцептивные видео-стандарты) 
и 4 режима изменения яркости. Предотвращает неестественные артефакты при глобальной цветокоррекции.

📖 Методы:
• HSV (Max-Based Brightness) — Value = max(R,G,B). 
• HSL (Average Lightness) — L = (max+min)/2. Насыщенные цвета темнеют при обесцвечивании.
• BT.601 (SDTV) — перцептивная яркость.
• BT.709 (sRGB/HDTV) — перцептивная яркость, современный стандарт. Идеален для фото.
• BT.2020 (HDR/Wide Gamut) — для HDR и широкого цветового охвата.

• Exposure (Linear) — RGB × коэффициент. Чёрный остаётся чёрным.
• Gamma (Midtones) — "тянет" средние тона, не трогая чёрный/белый. Отрицательные значения вытягивают полутона вверх (осветляют), положительные — вниз (затемняют).
• Offset (Additive) — RGB + константа. Чёрный становится серым.
• HSL Lightness (Classic) — изменение канала L. Цвета уходят в белый.

🔗 https://github.com/Rennart2025/ComfyUI-Rennart"""


# ==============================================
# Регистрация ноды
# ==============================================
NODE_CLASS_MAPPINGS = {
    "RennartHSVColorCorrection": RennartHSVColorCorrection,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartHSVColorCorrection": "🎨 Rennart HSV Color Correction",
}