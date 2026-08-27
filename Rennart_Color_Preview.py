"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Color_Preview.py
Категория: 
"""

# ==============================================
# Rennart_Color_Preview
# ==============================================

import re
import torch
import numpy as np

class RennartColorPreview:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "hex_string": ("STRING", {"multiline": True, "default": ""}),
                "swatch_size": ("INT", {"default": 128, "min": 32, "max": 512, "step": 8}),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("IMAGE", "COLOR_COUNT")
    FUNCTION = "render_preview"
    CATEGORY = "Rennart"

    def parse_hex_colors(self, text):
        hex_pattern = r'#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})\b'
        matches = re.findall(hex_pattern, text)
        
        cleaned_colors = []
        for m in matches:
            if len(m) == 3:
                m = ''.join([c*2 for c in m])
            cleaned_colors.append("#" + m.upper())
            
        return cleaned_colors

    def calculate_grid_dimensions(self, total_colors):
        if total_colors <= 0:
            return 1, 1, []

        if total_colors <= 3:
            cols = total_colors
        elif total_colors == 4:
            cols = 2
        elif total_colors in (8, 12, 16):
            cols = 4
        else:
            cols = 3

        rows_count = (total_colors + cols - 1) // cols
        remainder = total_colors % cols

        rows_pattern = []
        if remainder != 0 and total_colors not in (4, 8, 12, 16):
            num_short_rows = cols - remainder
            for _ in range(num_short_rows):
                rows_pattern.append(cols - 1)
            for _ in range(rows_count - num_short_rows):
                rows_pattern.append(cols)
        else:
            full_rows = total_colors // cols
            for _ in range(full_rows):
                rows_pattern.append(cols)
            if remainder > 0:
                rows_pattern.append(remainder)

        max_cols = max(rows_pattern) if rows_pattern else 1
        return len(rows_pattern), max_cols, rows_pattern

    def render_preview(self, hex_string, swatch_size):
        colors = self.parse_hex_colors(hex_string)
        total_colors = len(colors)

        if total_colors == 0:
            colors = ["#000000"]
            total_colors = 1

        num_rows, max_cols, rows_pattern = self.calculate_grid_dimensions(total_colors)

        # Общая ширина холста определяется базовой шириной полной строки
        total_width = max_cols * swatch_size
        total_height = num_rows * swatch_size

        grid_data = np.zeros((total_height, total_width, 3), dtype=np.float32)

        color_idx = 0
        for row_idx, items_in_row in enumerate(rows_pattern):
            # Динамически высчитываем ширину одной плашки для ТЕКУЩЕЙ строки,
            # чтобы вся сумма элементов строки идеально заполнила total_width
            row_swatch_width = total_width / items_in_row

            for col_idx in range(items_in_row):
                if color_idx >= total_colors:
                    break
                
                hex_code = colors[color_idx].lstrip('#')
                r, g, b = tuple(int(hex_code[i:i+2], 16) / 255.0 for i in (0, 2, 4))

                # Высота фиксирована по высотам строк
                y_start = row_idx * swatch_size
                y_end = (row_idx + 1) * swatch_size

                # Ширина каждой плашки в этой строке рассчитывается индивидуально
                x_start = int(round(col_idx * row_swatch_width))
                # Для последнего элемента строки принудительно берем край, чтобы избежать 1px погрешности округления
                x_end = total_width if col_idx == items_in_row - 1 else int(round((col_idx + 1) * row_swatch_width))

                grid_data[y_start:y_end, x_start:x_end] = [r, g, b]
                color_idx += 1

        img_tensor = torch.from_numpy(grid_data).unsqueeze(0)

        return (img_tensor, total_colors)


NODE_CLASS_MAPPINGS = {
    "RennartColorPreview": RennartColorPreview
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartColorPreview": "🎨 Rennart Color Preview"
}