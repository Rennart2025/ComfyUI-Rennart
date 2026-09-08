"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Video_Crossfade.py
Категория: Rennart/Video
"""

# ==============================================
# Rennart Video Crossfade (плавный переход между двумя видео)
# ==============================================

import torch
import math

class RennartVideoCrossfade:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_a": ("IMAGE",),
                "video_b": ("IMAGE",),
                "transition_frames": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 500,
                    "step": 1,
                    "tooltip": "Количество кадров в зоне перехода"
                }),
                "mode": (["linear", "ease_in", "ease_out", "ease_in_out", "sine"], {
                    "default": "linear",
                    "tooltip": "Кривая изменения прозрачности"
                }),
                "offset": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "step": 1,
                    "tooltip": "Сдвиг начала перехода в кадрах (пропустить первые N кадров видео B)"
                }),
            },
        }

    CATEGORY = "Rennart/Video"

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    FUNCTION = "create_crossfade"

    def get_alpha(self, i, total, mode):
        """Возвращает значение прозрачности (0-1) для шага i."""
        if total <= 1:
            return 0.0
        
        t = i / (total - 1)  # 0 -> 1
        
        if mode == "linear":
            alpha = t
        elif mode == "ease_in":
            alpha = t * t
        elif mode == "ease_out":
            alpha = 1 - (1 - t) * (1 - t)
        elif mode == "ease_in_out":
            alpha = t * t * (3 - 2 * t) if t < 0.5 else 1 - math.pow(-2 * t + 2, 2) / 2
        elif mode == "sine":
            alpha = (1 - math.cos(t * math.pi)) / 2
        else:
            alpha = t
        
        return min(max(alpha, 0.0), 1.0)

    def resize_images(self, image_a, image_b):
        """Приводит два батча к одинаковому разрешению."""
        if image_a.shape[1:] == image_b.shape[1:]:
            return image_a, image_b
        
        from torch.nn.functional import interpolate
        
        b_a, h_a, w_a, c_a = image_a.shape
        b_b, h_b, w_b, c_b = image_b.shape
        
        # Ресайзим image_b под размер image_a
        print(f"[Rennart] ⚠️ Разрешения не совпадают! A: {w_a}x{h_a}, B: {w_b}x{h_b}")
        print(f"[Rennart] 🔄 Ресайз B до {w_a}x{h_a}")
        
        image_b = image_b.permute(0, 3, 1, 2)  # [B, C, H, W]
        image_b = interpolate(image_b, size=(h_a, w_a), mode="bilinear", align_corners=False)
        image_b = image_b.permute(0, 2, 3, 1)  # [B, H, W, C]
        
        return image_a, image_b

    def create_crossfade(self, video_a, video_b, transition_frames=10, mode="linear", offset=0):
        # Проверяем, что батчи не пустые
        if video_a.shape[0] == 0 or video_b.shape[0] == 0:
            print("[Rennart] ❌ Одно из видео пустое!")
            return (video_a, 0)

        # Приводим к одинаковому разрешению
        video_a, video_b = self.resize_images(video_a, video_b)

        # Количество кадров в каждом видео
        len_a = video_a.shape[0]
        len_b = video_b.shape[0]

        print(f"[Rennart] 📹 Video A: {len_a} frames, Video B: {len_b} frames")

        # Определяем количество кадров, которые нужно взять из каждого видео
        # Если transition_frames больше, чем длина видео — используем всю длину
        transition = min(transition_frames, len_a, len_b)

        # Результат: кадры из видео A + переход + кадры из видео B
        result_frames = []

        # --- Часть 1: кадры из видео A ДО перехода ---
        frames_before = len_a - transition
        if frames_before > 0:
            result_frames.append(video_a[:frames_before])
            print(f"[Rennart] 📌 A (before): {frames_before} frames")

        # --- Часть 2: зона перехода ---
        # Берём последние transition кадров из A и первые transition кадров из B
        # С учётом offset (пропускаем первые offset кадров из B)
        end_a = len_a
        start_a = len_a - transition
        start_b = min(offset, len_b - transition)  # Не выходим за границы
        end_b = start_b + transition

        # Если offset слишком большой — корректируем
        if start_b >= len_b:
            print(f"[Rennart] ⚠️ Offset ({offset}) больше длины видео B ({len_b}). Обрезаем.")
            return (video_a, 0)

        frames_a_for_transition = video_a[start_a:end_a]
        frames_b_for_transition = video_b[start_b:end_b]

        print(f"[Rennart] 🎬 Transition: {transition} frames (A[{start_a}:{end_a}] → B[{start_b}:{end_b}])")

        # Создаём переход
        for i in range(transition):
            alpha = self.get_alpha(i, transition, mode)
            blended = (1 - alpha) * frames_a_for_transition[i] + alpha * frames_b_for_transition[i]
            result_frames.append(blended.unsqueeze(0))

        # --- Часть 3: кадры из видео B ПОСЛЕ перехода ---
        frames_after = len_b - end_b
        if frames_after > 0:
            result_frames.append(video_b[end_b:])
            print(f"[Rennart] 📌 B (after): {frames_after} frames")

        # Объединяем всё в один батч
        output_batch = torch.cat(result_frames, dim=0)

        print(f"[Rennart] ✅ Итоговое видео: {output_batch.shape[0]} frames")

        return (output_batch, output_batch.shape[0])



# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "Rennart Video Crossfade": RennartVideoCrossfade,    
}

NODE_DISPLAY_NAME_MAPPINGS = {    
    "Rennart Video Crossfade": "🎞️ Video Crossfade (Rennart)",
    
}