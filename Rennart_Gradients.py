"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Gradients.py
Категория: Rennart/Image
"""


import io
import numpy as np
import torch


# ==============================================
# Общие утилиты для обеих нод
# ==============================================

RADIAL_DIRECTIONS = ["radial_corner", "radial_edge"]
ALL_DIRECTIONS = ["horizontal", "vertical", "radial_corner", "radial_edge"]


def _parse_stops(gradient_stops):
    """Парсит строку с остановками градиента в отсортированный список."""
    colors_dict = {}
    stops = io.StringIO(gradient_stops.strip().replace(' ', ''))
    for stop in stops:
        if not stop.strip():
            continue
        parts = stop.split(':')
        if len(parts) != 2:
            continue
        colors = parts[1].replace('\n', '').split(',')
        if len(colors) != 3:
            continue
        try:
            colors_dict[float(parts[0].replace('\n', ''))] = tuple(map(int, colors))
        except ValueError:
            continue
    return sorted(colors_dict.items())


def _build_pos_grid(width, height, direction, radial_center_x, radial_center_y):
    """Возвращает сетку позиций 0..100 для интерполяции цветов."""
    if direction == 'horizontal':
        pos_line = np.linspace(0, 100, width)
        return np.tile(pos_line, (height, 1))

    if direction == 'vertical':
        pos_line = np.linspace(0, 100, height)
        return np.tile(pos_line[:, np.newaxis], (1, width))

    # Радиальные режимы
    cx = float(radial_center_x) * (width - 1)
    cy = float(radial_center_y) * (height - 1)

    if direction == 'radial_corner':
        # Расстояние до самого дальнего угла
        dx = max(cx, (width - 1) - cx)
        dy = max(cy, (height - 1) - cy)
        max_dist = float(np.sqrt(dx * dx + dy * dy))
    else:  # radial_edge
        # Расстояние до ближайшей границы — вписанный круг
        max_dist = float(min(cx, (width - 1) - cx, cy, (height - 1) - cy))

    if max_dist <= 0:
        # Центр в углу/на границе — вырожденный случай
        return np.zeros((height, width), dtype=np.float32)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    # Нормируем в 0..100 и клампим за пределами max_dist
    return np.clip(dist / max_dist, 0.0, 1.0) * 100.0


# ==============================================
# Rennart Generate Posterize Gradient (ступенчатый градиент)
# ==============================================

class RennartGeneratePosterizeGradient:
    @classmethod
    def INPUT_TYPES(cls):
        gradient_stops = "0:0,0,0\n25:255,255,255\n75:0,0,0"
        return {
            "required": {
                "width": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "height": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "direction": (ALL_DIRECTIONS, {
                    "tooltip": (
                        "Тип градиента:\n"
                        "• horizontal — слева направо\n"
                        "• vertical — сверху вниз\n"
                        "• radial_corner — от центра к дальнему углу\n"
                        "• radial_edge — от центра к ближайшей границе (вписанный круг)"
                    )
                }),
                "gradient_stops": ("STRING", {"default": gradient_stops, "multiline": True}),
                "radial_center_x": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "X центра радиального градиента (доля ширины). Используется только в radial_* режимах."
                }),
                "radial_center_y": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Y центра радиального градиента (доля высоты). Используется только в radial_* режимах."
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate_posterize_gradient"
    CATEGORY = "Rennart/Image"

    def generate_posterize_gradient(self, gradient_stops, width=512, height=512,
                                    direction='horizontal',
                                    radial_center_x=0.5, radial_center_y=0.5):
        sorted_stops = _parse_stops(gradient_stops)
        if not sorted_stops:
            return (torch.zeros((1, height, width, 3), dtype=torch.float32),)

        pos_grid = _build_pos_grid(width, height, direction, radial_center_x, radial_center_y)

        # Массив для хранения результирующих RGB пикселей
        img_array = np.zeros((height, width, 3), dtype=np.uint8)

        # Заливаем базовым цветом (первым)
        img_array[:, :] = sorted_stops[0][1]

        # Применяем ступенчатые интервалы без циклов по пикселям
        for i in range(len(sorted_stops) - 1):
            start_pos, start_color = sorted_stops[i]
            end_pos, end_color = sorted_stops[i + 1]

            mask = (pos_grid > start_pos) & (pos_grid < end_pos)
            img_array[mask] = start_color

            mask_edge = (pos_grid == end_pos)
            img_array[mask_edge] = end_color

        # Для позиций за пределами последней остановки
        mask_last = (pos_grid >= sorted_stops[-1][0])
        img_array[mask_last] = sorted_stops[-1][1]

        tensor = torch.from_numpy(img_array.astype(np.float32) / 255.0).unsqueeze(0)
        return (tensor,)


# ==============================================
# Rennart Generate Gradient (плавный градиент)
# ==============================================

class RennartGenerateGradient:
    @classmethod
    def INPUT_TYPES(cls):
        gradient_stops = "0:255,0,0\n25:255,255,255\n50:0,255,0\n75:0,0,255"
        return {
            "required": {
                "width": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "height": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "direction": (ALL_DIRECTIONS, {
                    "tooltip": (
                        "Тип градиента:\n"
                        "• horizontal — слева направо\n"
                        "• vertical — сверху вниз\n"
                        "• radial_corner — от центра к дальнему углу\n"
                        "• radial_edge — от центра к ближайшей границе (вписанный круг)"
                    )
                }),
                "tolerance": ("INT", {
                    "default": 0, "max": 255, "min": 0, "step": 1,
                    "tooltip": "Огрубление каналов (бандинг). Работает во всех режимах. 0 = без огрубления."
                }),
                "gradient_stops": ("STRING", {"default": gradient_stops, "multiline": True}),
                "radial_center_x": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "X центра радиального градиента (доля ширины). Используется только в radial_* режимах."
                }),
                "radial_center_y": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "Y центра радиального градиента (доля высоты). Используется только в radial_* режимах."
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "generate_gradient"
    CATEGORY = "Rennart/Image"

    def generate_gradient(self, gradient_stops, width=512, height=512,
                          direction='horizontal', tolerance=0,
                          radial_center_x=0.5, radial_center_y=0.5):
        sorted_stops = _parse_stops(gradient_stops)
        if not sorted_stops:
            return (torch.zeros((1, height, width, 3), dtype=torch.float32),)

        pos_grid = _build_pos_grid(width, height, direction, radial_center_x, radial_center_y)

        img_array = np.zeros((height, width, 3), dtype=np.float32)

        # Заливка краёв до и после крайних остановок
        img_array[pos_grid <= sorted_stops[0][0]] = np.array(sorted_stops[0][1]) / 255.0
        img_array[pos_grid >= sorted_stops[-1][0]] = np.array(sorted_stops[-1][1]) / 255.0

        # Интерполяция между контрольными точками
        for i in range(len(sorted_stops) - 1):
            start_pos, start_color = sorted_stops[i]
            end_pos, end_color = sorted_stops[i + 1]

            mask = (pos_grid >= start_pos) & (pos_grid <= end_pos)
            if not np.any(mask):
                continue

            denom = end_pos - start_pos
            ratio = (pos_grid[mask] - start_pos) / denom if denom != 0 else 0

            c_start = np.array(start_color) / 255.0
            c_end = np.array(end_color) / 255.0

            # Векторизованное смешивание цветов
            img_array[mask] = c_start + (c_end - c_start) * ratio[:, np.newaxis]

        # Применение tolerance (огрубление каналов)
        if tolerance > 0:
            factor = 255.0 / max(tolerance, 1)
            img_array = np.round(img_array * factor) / factor

        tensor = torch.from_numpy(img_array.astype(np.float32)).unsqueeze(0)
        return (tensor,)


# ==============================================
# Регистрация нод
# ==============================================

NODE_CLASS_MAPPINGS = {
    "Rennart Generate Gradient": RennartGenerateGradient,
    "Rennart Generate Posterize Gradient": RennartGeneratePosterizeGradient,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Rennart Generate Gradient": "🎨 Generate Gradient (Rennart)",
    "Rennart Generate Posterize Gradient": "🎨 Generate Posterize Gradient (Rennart)",
}