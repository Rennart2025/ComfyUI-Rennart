"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Denoise.py
Категория: Rennart/Image
"""

import os
import torch
import comfy.utils
import comfy.model_management
import comfy.model_patcher
import folder_paths
from spandrel import ModelLoader, ImageModelDescriptor
from huggingface_hub import hf_hub_download


# ==============================================
# Загрузка модели (с авто-скачиванием)
# ==============================================

def _ensure_model_downloaded():
    """Скачивает модель из Hugging Face, если её ещё нет."""
    models_dir = folder_paths.get_folder_paths("upscale_models")[0]
    model_filename = "1xDeNoise_realplksr_otf.safetensors"
    model_path = os.path.join(models_dir, model_filename)

    if not os.path.exists(model_path):
        print(f"[Rennart] Модель не найдена. Скачиваю {model_filename}...")
        try:
            hf_hub_download(
                repo_id="Rennart/1xDeNoise_realplksr_otf",
                filename=model_filename,
                local_dir=models_dir,
                local_dir_symlinks=False,
            )
            print(f"[Rennart] Модель сохранена в {model_path}")
        except Exception as e:
            raise RuntimeError(f"[Rennart] Не удалось скачать модель: {e}")

    return model_path


def _load_upscale_model(model_path):
    """Загружает модель через spandrel (аналог UpscaleModelLoader)."""
    sd = comfy.utils.load_torch_file(model_path, safe_load=True)
    if "module.layers.0.residual_group.blocks.0.norm1.weight" in sd:
        sd = comfy.utils.state_dict_prefix_replace(sd, {"module.": ""})

    out = ModelLoader().load_from_state_dict(sd).eval()

    if not isinstance(out, ImageModelDescriptor):
        raise Exception("[Rennart] Модель должна быть single-image моделью.")

    out.patcher = comfy.model_patcher.CoreModelPatcher(
        out.model,
        load_device=comfy.model_management.get_torch_device(),
        offload_device=comfy.model_management.unet_offload_device(),
    )
    return out


# ==============================================
# Применение модели с тайлингом
# ==============================================

def _apply_model_tiled(image, model, tile_size, overlap):
    """
    Применяет модель к изображению с настраиваемым тайлингом.
    image: [B, H, W, C]
    Возвращает: [B, H, W, C]
    """
    # --- КРИТИЧНО: загружаем модель на GPU перед использованием ---
    memory_required = (512 * 512 * 3) * image.element_size() * max(model.scale, 1.0) * 384.0
    memory_required += image.nelement() * image.element_size()
    comfy.model_management.load_models_gpu(
        [model.patcher],
        memory_required=memory_required,
        force_full_load=True,
    )

    # После load_models_gpu модель уже на нужном устройстве
    device = model.patcher.load_device
    in_img = image.movedim(-1, -3).to(device)  # [B, C, H, W]

    scale = getattr(model, "scale", 1.0)
    output_device = comfy.model_management.intermediate_device()

    s = comfy.utils.tiled_scale(
        in_img,
        lambda a: model(a.float()),
        tile_x=tile_size,
        tile_y=tile_size,
        overlap=overlap,
        upscale_amount=scale,
        output_device=output_device,
    )
    s = torch.clamp(s.movedim(-3, -1), min=0, max=1.0).to(comfy.model_management.intermediate_dtype())
    return s


# ==============================================
# Нода Rennart Denoise
# ==============================================

class RennartDenoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "mode": (["auto", "tile_size", "manual"], {
                    "default": "auto",
                    "tooltip": (
                        "auto — tile_size=512, overlap=tile/4, offset=(tile-overlap)/2\n"
                        "tile_size — пользователь задаёт только tile_size\n"
                        "manual — все параметры задаются вручную"
                    )
                }),
                "tile_size": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 64}),
                "overlap": ("INT", {"default": 128, "min": 0, "max": 512, "step": 8}),
                "offset": ("INT", {"default": 192, "min": 0, "max": 1024, "step": 8}),
            },
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "denoise"
    DESCRIPTION = "Двойной проход модели денойза со сдвигом и смешиванием 50/50."

    def denoise(self, image, mode, tile_size, overlap, offset):
        # --- 1. Определяем параметры ---
        if mode == "auto":
            tile_size = 512
            overlap = tile_size // 4
            offset = (tile_size - overlap) // 2
        elif mode == "tile_size":
            overlap = tile_size // 4
            offset = (tile_size - overlap) // 2
        # mode == "manual" — используем как есть

        print(f"[Rennart] Denoise: mode={mode}, tile={tile_size}, overlap={overlap}, offset={offset}")

        # --- 2. Загружаем модель (с авто-скачиванием) ---
        model_path = _ensure_model_downloaded()
        model = _load_upscale_model(model_path)

        # --- 3. Первый проход (без сдвига) ---
        result1 = _apply_model_tiled(image, model, tile_size, overlap)

        # --- 4. Второй проход (со сдвигом) ---
        shifted = torch.roll(image, shifts=(offset, offset), dims=(1, 2))
        result2_shifted = _apply_model_tiled(shifted, model, tile_size, overlap)
        result2 = torch.roll(result2_shifted, shifts=(-offset, -offset), dims=(1, 2))

        # --- 5. Смешивание 50/50 ---
        output = result1 * 0.5 + result2 * 0.5

        return (output,)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartDenoise": RennartDenoise,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartDenoise": "🧹 Rennart Denoise",
}