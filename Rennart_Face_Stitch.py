"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Face_Stitch.py
Категория: Rennart/Image
"""

import logging

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


# ==============================================
# Вспомогательные функции
# ==============================================

def _resize_tensor(tensor, width, height, method="lanczos"):
    """Ресайз [H,W,C] или [H,W] до (width, height)."""
    if tensor.ndim not in (2, 3):
        raise ValueError(f"Ожидался 2D/3D тензор, получен {tensor.ndim}D")
    ch, cw = tensor.shape[:2]
    if ch == height and cw == width:
        return tensor

    if method == "lanczos":
        arr = (tensor.cpu().numpy() * 255).astype(np.uint8)
        pil = Image.fromarray(arr)
        rp = pil.resize((width, height), Image.LANCZOS)
        return torch.from_numpy(np.array(rp).astype(np.float32) / 255.0).to(
            tensor.device, dtype=tensor.dtype
        )

    mode = {"nearest": "nearest", "bilinear": "bilinear", "bicubic": "bicubic"}.get(method, "bilinear")
    if tensor.ndim == 2:
        t4 = tensor.unsqueeze(0).unsqueeze(0)
        r4 = F.interpolate(t4, size=(height, width), mode=mode, align_corners=False)
        return r4.squeeze(0).squeeze(0)

    t4 = tensor.permute(2, 0, 1).unsqueeze(0)
    r4 = F.interpolate(t4, size=(height, width), mode=mode, align_corners=False)
    return r4.squeeze(0).permute(1, 2, 0)


def _match_channels_np(array, channels):
    """Выравнивает HWC-каналы под нужное число."""
    current = int(array.shape[2])
    if current == channels:
        return array
    if current == 1:
        return np.repeat(array, channels, axis=2)
    if channels == 1:
        return array[..., :1]
    if current > channels:
        return array[..., :channels]
    if channels == 4 and current == 3:
        alpha = np.ones((array.shape[0], array.shape[1], 1), dtype=array.dtype)
        return np.concatenate([array, alpha], axis=2)
    return np.repeat(array[..., :1], channels, axis=2)


def _border_weight(h, w, feather):
    """Вес 0..1: 0 у края окна, 1 в центре."""
    if feather <= 0:
        return np.ones((h, w), dtype=np.float32)
    yy = np.arange(h)[:, None].astype(np.float32)
    xx = np.arange(w)[None, :].astype(np.float32)
    dist = np.minimum(np.minimum(yy, h - 1 - yy), np.minimum(xx, w - 1 - xx))
    return np.clip(dist / feather, 0.0, 1.0)


def _to_rgb_u8(arr):
    """HWC float 0..1 -> HWC uint8 RGB. Для cv2.seamlessClone."""
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    return (np.clip(arr[..., :3], 0.0, 1.0) * 255).astype(np.uint8)


def _extract_bbox(bbox, bbox_index):
    """Достаёт (x, y, w, h) из bbox по индексу. Поддерживает список и одиночный кортеж."""
    if bbox is None:
        raise ValueError("[Rennart Face Stitch] bbox не подан.")

    # numpy-массив (бывает при некоторых типах выхода)
    if isinstance(bbox, np.ndarray):
        bbox = bbox.tolist()

    if isinstance(bbox, (list, tuple)) and len(bbox) > 0:
        # Одиночный кортеж из 4 чисел
        if len(bbox) == 4 and all(isinstance(v, (int, float, np.integer, np.floating)) for v in bbox):
            return tuple(int(v) for v in bbox)
        # Список кортежей
        if all(isinstance(item, (list, tuple, np.ndarray)) and len(item) == 4 for item in bbox):
            idx = max(0, min(int(bbox_index), len(bbox) - 1))
            return tuple(int(v) for v in bbox[idx])

    raise ValueError(f"[Rennart Face Stitch] Не удалось разобрать bbox: {type(bbox)}")


# ==============================================
# Нода Rennart Face Stitch
# ==============================================

class RennartFaceStitch:
    @classmethod
    def INPUT_TYPES(cls):
        blend_modes = ["paste", "feather_blend"]
        if CV2_AVAILABLE:
            blend_modes.append("poisson_blend")
        else:
            blend_modes.append("poisson_blend (недоступен)")
        return {
            "required": {
                "original_image": ("IMAGE", {
                    "tooltip": "Оригинал, куда вклеивается лицо. Берётся первый кадр."
                }),
                "cropped_image": ("IMAGE", {
                    "tooltip": "Обработанный кроп лица. Авто-ресайз до размера bbox."
                }),
                "bbox": ("BBOX", {
                    "tooltip": "Список (x, y, w, h) из AGSoft Crop Face. Выбор — через bbox_index."
                }),
                "bbox_index": ("INT", {
                    "default": 0, "min": 0, "max": 999, "step": 1,
                    "tooltip": "Какой bbox из списка использовать (0 = первый)."
                }),
                "blend_mode": (blend_modes, {
                    "default": "feather_blend",
                    "tooltip": (
                        "paste — жёсткая вставка\n"
                        "feather_blend — плавный шов по краям окна\n"
                        "poisson_blend — сохранение освещения (нужен opencv)"
                    )
                }),
                "feathering": ("INT", {
                    "default": 16, "min": 0, "max": 128, "step": 1,
                    "tooltip": "Ширина плавного шва для feather_blend."
                }),
            },
            "optional": {
                "face_mask": ("MASK", {
                    "tooltip": (
                        "Овал лица из AGSoft Crop Face (1 = вклеить, 0 = оставить оригинал). "
                        "Авто-ресайз до размера bbox."
                    )
                }),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "stitch"
    DESCRIPTION = (
        "Вклеивает обработанное лицо в оригинал по bbox из AGSoft Crop Face.\n"
        "Режимы: paste / feather_blend / poisson_blend."
    )

    def stitch(self, original_image, cropped_image, bbox, bbox_index=0,
               blend_mode="feather_blend", feathering=16, face_mask=None):
        # Нормализуем недоступный poisson
        if blend_mode == "poisson_blend (недоступен)":
            blend_mode = "paste"

        orig = original_image[0]
        inp = cropped_image[0]
        orig_h, orig_w = int(orig.shape[0]), int(orig.shape[1])

        x, y, w, h = _extract_bbox(bbox, bbox_index)
        x = max(0, min(x, orig_w - 1))
        y = max(0, min(y, orig_h - 1))
        w = max(1, min(w, orig_w - x))
        h = max(1, min(h, orig_h - y))

        # Авто-ресайз кропа до размера bbox (как в AGSoft)
        if inp.shape[0] != h or inp.shape[1] != w:
            inp = _resize_tensor(inp, w, h, "lanczos")

        channels = int(orig.shape[2])
        result = orig.clone()

        orig_region = orig[y:y + h, x:x + w, :].cpu().numpy()
        inp_region = inp[:h, :w, :].cpu().numpy()
        orig_region = _match_channels_np(orig_region, channels)
        inp_region = _match_channels_np(inp_region, channels)

        # Вес вклейки (1 = кроп, 0 = оригинал)
        mask_w = np.ones((h, w), dtype=np.float32)
        if face_mask is not None:
            m = face_mask[0] if face_mask.dim() == 3 else face_mask
            if m.shape[0] != h or m.shape[1] != w:
                m = _resize_tensor(m, w, h, "bilinear")
            mask_w = np.clip(m[:h, :w].cpu().numpy().astype(np.float32), 0.0, 1.0)

        # poisson_blend не сработает с пустой маской — уходим в paste
        if blend_mode == "poisson_blend" and mask_w.sum() < 1.0:
            logger.warning("[Rennart Face Stitch] маска пустая, poisson_blend невозможен, fallback на paste")
            blend_mode = "paste"

        if blend_mode == "poisson_blend" and CV2_AVAILABLE:
            try:
                src_u8 = _to_rgb_u8(inp_region)
                tgt_u8 = _to_rgb_u8(orig_region)
                mask_u8 = (mask_w * 255).astype(np.uint8)
                center = (w // 2, h // 2)
                blended = cv2.seamlessClone(src_u8, tgt_u8, mask_u8, center, cv2.NORMAL_CLONE)
                blended_np = blended.astype(np.float32) / 255.0
                if channels == 4:
                    blended_np = np.concatenate([blended_np, orig_region[..., 3:4]], axis=2)
                elif channels == 1:
                    blended_np = blended_np[..., :1]
            except Exception as e:
                logger.warning(f"[Rennart Face Stitch] poisson_blend упал, fallback на маску: {e}")
                weight = mask_w[..., None]
                blended_np = orig_region * (1.0 - weight) + inp_region * weight
        else:
            weight = mask_w
            if blend_mode == "feather_blend":
                weight = weight * _border_weight(h, w, feathering)
            weight = weight[..., None]
            blended_np = orig_region * (1.0 - weight) + inp_region * weight

        blended_tensor = torch.from_numpy(blended_np).to(
            device=orig.device, dtype=orig.dtype
        )
        result[y:y + h, x:x + w, :] = blended_tensor

        return (result.unsqueeze(0),)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartFaceStitch": RennartFaceStitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartFaceStitch": "🧵 Rennart Face Stitch",
}