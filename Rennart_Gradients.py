"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Gradients.py
Категория: Rennart/Image
"""


import io
import numpy as np
import torch


# ==============================================
# Rennart Generate Posterize Gradient (ступенчатый градиент - ОПТИМИЗИРОВАНО)
# ==============================================

class RennartGeneratePosterizeGradient:
    @classmethod
    def INPUT_TYPES(cls):
        gradient_stops = "0:0,0,0\n25:255,255,255\n75:0,0,0"
        return {
            "required": {
                "width": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "height": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "direction": (["horizontal", "vertical"],),
                "gradient_stops": ("STRING", {"default": gradient_stops, "multiline": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate_posterize_gradient"
    CATEGORY = "Rennart/Image"

    def parse_stops(self, gradient_stops):
        colors_dict = {}
        stops = io.StringIO(gradient_stops.strip().replace(' ', ''))
        for stop in stops:
            if not stop.strip(): continue
            parts = stop.split(':')
            colors = parts[1].replace('\n', '').split(',')
            colors_dict[float(parts[0].replace('\n', ''))] = tuple(map(int, colors))
        return sorted(colors_dict.items())

    def generate_posterize_gradient(self, gradient_stops, width=512, height=512, direction='horizontal'):
        sorted_stops = self.parse_stops(gradient_stops)
        if not sorted_stops:
            return (torch.zeros((1, height, width, 3), dtype=torch.float32),)

        # Создаем карту позиций от 0 до 100
        if direction == 'horizontal':
            pos_line = np.linspace(0, 100, width, endpoint=False)
            pos_grid = np.tile(pos_line, (height, 1))
        else:
            pos_line = np.linspace(0, 100, height, endpoint=False)
            pos_grid = np.tile(pos_line[:, np.newaxis], (1, width))

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
# Rennart Generate Gradient (автономная версия - ОПТИМИЗИРОВАНО)
# ==============================================

class RennartGenerateGradient:
    @classmethod
    def INPUT_TYPES(cls):
        gradient_stops = "0:255,0,0\n25:255,255,255\n50:0,255,0\n75:0,0,255"
        return {
            "required": {
                "width": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "height": ("INT", {"default": 512, "max": 4096, "min": 64, "step": 1}),
                "direction": (["horizontal", "vertical"],),
                "tolerance": ("INT", {"default": 0, "max": 255, "min": 0, "step": 1}),
                "gradient_stops": ("STRING", {"default": gradient_stops, "multiline": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate_gradient"
    CATEGORY = "Rennart/Image"

    def parse_stops(self, gradient_stops):
        colors_dict = {}
        stops = io.StringIO(gradient_stops.strip().replace(' ', ''))
        for stop in stops:
            if not stop.strip(): continue
            parts = stop.split(':')
            colors = parts[1].replace('\n', '').split(',')
            colors_dict[float(parts[0].replace('\n', ''))] = tuple(map(int, colors))
        return sorted(colors_dict.items())

    def generate_gradient(self, gradient_stops, width=512, height=512, direction='horizontal', tolerance=0):
        sorted_stops = self.parse_stops(gradient_stops)
        if not sorted_stops:
            return (torch.zeros((1, height, width, 3), dtype=torch.float32),)

        if direction == 'horizontal':
            pos_line = np.linspace(0, 100, width)
            pos_grid = np.tile(pos_line, (height, 1))
        else:
            pos_line = np.linspace(0, 100, height)
            pos_grid = np.tile(pos_line[:, np.newaxis], (1, width))

        img_array = np.zeros((height, width, 3), dtype=np.float32)
        
        # Заливка краев до и после экстремальных точек
        img_array[pos_grid <= sorted_stops[0][0]] = np.array(sorted_stops[0][1]) / 255.0
        img_array[pos_grid >= sorted_stops[-1][0]] = np.array(sorted_stops[-1][1]) / 255.0

        # Интерполяция между контрольными точками
        for i in range(len(sorted_stops) - 1):
            start_pos, start_color = sorted_stops[i]
            end_pos, end_color = sorted_stops[i + 1]
            
            mask = (pos_grid >= start_pos) & (pos_grid <= end_pos)
            if not np.any(mask): continue
            
            denom = end_pos - start_pos
            ratio = (pos_grid[mask] - start_pos) / denom if denom != 0 else 0
            
            c_start = np.array(start_color) / 255.0
            c_end = np.array(end_color) / 255.0
            
            # Векторизованное смешивание цветов
            img_array[mask] = c_start + (c_end - c_start) * ratio[:, np.newaxis]

        # Применение tolerance (если нужно), имитирующее огрубление каналов
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