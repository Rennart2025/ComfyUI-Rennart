"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Color_Palette.py
Категория: 
"""

# ==============================================
# Rennart_Color_Palette
# ==============================================

import colorsys
import torch
import numpy as np

class RennartColorPalette:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "base_color": ("STRING", {"default": "#3498DB"}),
                "harmony_mode": ([
                    "Complementary", 
                    "Analogous", 
                    "Triadic", 
                    "Split-Complementary", 
                    "Tetradic", 
                    "Monochromatic"
                ], {"default": "Complementary"}),
                "tonal_key": ([
                    "Normal", 
                    "High Key", 
                    "Low Key"
                ], {"default": "Normal"}),
                "brightness_step": ("INT", {"default": 20, "min": 0, "max": 100, "step": 1}),
                "output_format": ([
                    "Simple (#HEX, #HEX)", 
                    "Quoted (\"#HEX\", \"#HEX\")", 
                    "Array [\"#HEX\", ...]", 
                    "Prompt Tags", 
                    "Custom"
                ], {"default": "Quoted (\"#HEX\", \"#HEX\")"}),
                "preview_size": ("INT", {"default": 100, "min": 16, "max": 2048, "step": 8}),
            },
            "optional": {
                "custom_template": ("STRING", {"default": "color_{index}: {color}"}),
                "custom_delimiter": ("STRING", {"default": ", "}),
            }
        }

    RETURN_TYPES = ("STRING", "IMAGE", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("BASE_COLOR", "IMAGE", "HEX_STRING", "VARIATIONS_IMAGE", "VARIATIONS_HEX")
    FUNCTION = "generate_palette"
    CATEGORY = "Rennart"

    def hex_to_hls(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) != 6:
            hex_str = "3498DB"  # Fallback
        r, g, b = tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return h, l, s

    def hls_to_hex(self, h, l, s):
        # Защита выходов за границы [0, 1]
        h = h % 1.0
        l = max(0.0, min(1.0, l))
        s = max(0.0, min(1.0, s))
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

    def apply_tonal_key(self, l, s, tonal_key):
        if tonal_key == "High Key":
            # Светлые, воздушные, пастельные тона
            l = 0.75 + (l * 0.20)
            s = s * 0.60
        elif tonal_key == "Low Key":
            # Тёмные, глубокие, нуарные тона
            l = 0.10 + (l * 0.25)
            s = min(1.0, s * 1.2)
        return l, s

    # Изменение яркости на динамический процент
    def adjust_lightness(self, hex_code, delta):
        h, l, s = self.hex_to_hls(hex_code)
        return self.hls_to_hex(h, l + delta, s)

    # Функция форматирования списка HEX в итоговую строку
    def format_hex_list(self, hex_list, output_format, custom_template, custom_delimiter):
        if output_format == "Simple (#HEX, #HEX)":
            return ", ".join(hex_list)
        elif output_format == "Quoted (\"#HEX\", \"#HEX\")":
            return ", ".join([f'"{code}"' for code in hex_list])
        elif output_format == "Array [\"#HEX\", ...]":
            return "[" + ", ".join([f'"{code}"' for code in hex_list]) + "]"
        elif output_format == "Prompt Tags":
            return "color palette: " + ", ".join(hex_list)
        elif output_format == "Custom":
            formatted_items = [
                custom_template.format(color=code, index=i+1) 
                for i, code in enumerate(hex_list)
            ]
            return custom_delimiter.join(formatted_items)
        else:
            return ", ".join(hex_list)

    def generate_palette(self, base_color, harmony_mode, tonal_key, brightness_step, output_format, preview_size, custom_template="{color}", custom_delimiter=", "):
        # Форматируем входной базовый цвет
        clean_base_color = base_color.strip().upper()
        if not clean_base_color.startswith("#"):
            clean_base_color = "#" + clean_base_color

        h, l, s = self.hex_to_hls(clean_base_color)
        
        # 1. Расчет углов Иттена (Hue shifts)
        hues = []
        if harmony_mode == "Complementary":
            hues = [h, (h + 0.5) % 1.0]
        elif harmony_mode == "Analogous":
            hues = [(h - 30/360) % 1.0, h, (h + 30/360) % 1.0]
        elif harmony_mode == "Triadic":
            hues = [h, (h + 120/360) % 1.0, (h + 240/360) % 1.0]
        elif harmony_mode == "Split-Complementary":
            hues = [h, (h + 150/360) % 1.0, (h + 210/360) % 1.0]
        elif harmony_mode == "Tetradic":
            hues = [h, (h + 90/360) % 1.0, (h + 180/360) % 1.0, (h + 270/360) % 1.0]
        elif harmony_mode == "Monochromatic":
            hues = [h, h, h, h]

        # 2. Основная палитра
        palette_hex = []
        if harmony_mode == "Monochromatic":
            l_steps = [0.2, 0.4, 0.6, 0.8] if tonal_key == "Normal" else [0.7, 0.78, 0.86, 0.94] if tonal_key == "High Key" else [0.08, 0.16, 0.24, 0.32]
            for idx, cur_h in enumerate(hues):
                cur_l, cur_s = self.apply_tonal_key(l_steps[idx], s, tonal_key)
                palette_hex.append(self.hls_to_hex(cur_h, cur_l, cur_s))
        else:
            for cur_h in hues:
                cur_l, cur_s = self.apply_tonal_key(l, s, tonal_key)
                palette_hex.append(self.hls_to_hex(cur_h, cur_l, cur_s))

        # 3. Дополнительная палитра с динамическим шагом яркости
        delta = brightness_step / 100.0
        variations_hex = []
        for code in palette_hex:
            light_code = self.adjust_lightness(code, +delta)
            dark_code = self.adjust_lightness(code, -delta)
            variations_hex.extend([light_code, dark_code])

        # 4. Форматирование выходных строк
        hex_string_main = self.format_hex_list(palette_hex, output_format, custom_template, custom_delimiter)
        hex_string_variations = self.format_hex_list(variations_hex, output_format, custom_template, custom_delimiter)

        # 5. Генерация основного изображения-палитры
        num_colors = len(palette_hex)
        bar_width = preview_size
        total_width = bar_width * num_colors
        height = preview_size

        img_data = np.zeros((height, total_width, 3), dtype=np.float32)
        for i, code in enumerate(palette_hex):
            h_str = code.lstrip('#')
            r, g, b = tuple(int(h_str[j:j+2], 16) / 255.0 for j in (0, 2, 4))
            img_data[:, i*bar_width:(i+1)*bar_width] = [r, g, b]

        img_tensor_main = torch.from_numpy(img_data).unsqueeze(0)

        # 6. Генерация изображения вариаций
        var_num_colors = len(variations_hex)
        var_total_width = bar_width * var_num_colors

        var_img_data = np.zeros((height, var_total_width, 3), dtype=np.float32)
        for i, code in enumerate(variations_hex):
            h_str = code.lstrip('#')
            r, g, b = tuple(int(h_str[j:j+2], 16) / 255.0 for j in (0, 2, 4))
            var_img_data[:, i*bar_width:(i+1)*bar_width] = [r, g, b]

        img_tensor_variations = torch.from_numpy(var_img_data).unsqueeze(0)

        return (clean_base_color, img_tensor_main, hex_string_main, img_tensor_variations, hex_string_variations)


NODE_CLASS_MAPPINGS = {
    "RennartColorPalette": RennartColorPalette
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartColorPalette": "🎨 Rennart Color Palette"
}