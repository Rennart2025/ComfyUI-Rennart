"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Image_Upscale_With_Model.py
Категория: Rennart/Upscale
"""

# ==============================================
# Rennart Image Upscale (Load Model + Upscale в одной ноде)
# ==============================================

import logging
import torch
import comfy.utils
import comfy.model_management
import comfy.model_patcher
import folder_paths
from spandrel import ModelLoader, ImageModelDescriptor

try:
    from spandrel_extra_arches import EXTRA_REGISTRY
    from spandrel import MAIN_REGISTRY
    MAIN_REGISTRY.add(*EXTRA_REGISTRY)
    logging.info("Successfully imported spandrel_extra_arches: support for non commercial upscale models.")
except:
    pass


# ==============================================
# Вспомогательная функция: загрузка модели
# ==============================================

def _load_upscale_model(model_name):
    """Загружает модель апскейла из папки upscale_models."""
    model_path = folder_paths.get_full_path_or_raise("upscale_models", model_name)
    sd = comfy.utils.load_torch_file(model_path, safe_load=True)

    if "module.layers.0.residual_group.blocks.0.norm1.weight" in sd:
        sd = comfy.utils.state_dict_prefix_replace(sd, {"module.": ""})

    out = ModelLoader().load_from_state_dict(sd).eval()

    if not isinstance(out, ImageModelDescriptor):
        raise Exception("[Rennart] Upscale model must be a single-image model.")

    out.patcher = comfy.model_patcher.CoreModelPatcher(
        out.model,
        load_device=comfy.model_management.get_torch_device(),
        offload_device=comfy.model_management.unet_offload_device(),
    )
    return out


# ==============================================
# Rennart Image Upscale (Model)
# ==============================================

class RennartImageUpscaleWithModel:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": (folder_paths.get_filename_list("upscale_models"),),
                "image": ("IMAGE",),
                "tile_size": ("INT", {
                    "default": 512,
                    "min": 64,
                    "max": 4096,
                    "step": 64,
                    "tooltip": "Размер тайла (плитки) в пикселях. Больше = быстрее, но требует больше VRAM."
                }),
                "overlap": ("INT", {
                    "default": 32,
                    "min": 0,
                    "max": 512,
                    "step": 8,
                    "tooltip": "Перекрытие между тайлами в пикселях. Помогает убрать видимые швы."
                }),
                "auto_reduce_on_oom": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Yes",
                    "label_off": "No",
                    "tooltip": "Автоматически уменьшать размер тайла при нехватке VRAM."
                }),
            },
        }

    CATEGORY = "Rennart/Upscale"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "upscale"
    DESCRIPTION = "Loads an upscale model and upscales the image with configurable tile size and overlap."

    def upscale(self, model_name, image, tile_size, overlap, auto_reduce_on_oom):
        # --- 1. Загружаем модель ---
        upscale_model = _load_upscale_model(model_name)

        # --- 2. Проверяем память и загружаем на устройство ---
        device = upscale_model.patcher.load_device

        memory_required = (512 * 512 * 3) * image.element_size() * max(upscale_model.scale, 1.0) * 384.0
        memory_required += image.nelement() * image.element_size()
        comfy.model_management.load_models_gpu(
            [upscale_model.patcher],
            memory_required=memory_required,
            force_full_load=True,
        )

        in_img = image.movedim(-1, -3).to(device)

        # --- 3. Настройка тайлинга ---
        tile = tile_size
        current_overlap = overlap

        # Перекрытие не должно быть больше половины тайла
        if current_overlap >= tile // 2:
            current_overlap = max(0, tile // 4)

        output_device = comfy.model_management.intermediate_device()

        oom = True
        attempt = 0
        while oom:
            try:
                steps = in_img.shape[0] * comfy.utils.get_tiled_scale_steps(
                    in_img.shape[3], in_img.shape[2],
                    tile_x=tile, tile_y=tile, overlap=current_overlap,
                )
                pbar = comfy.utils.ProgressBar(steps)
                s = comfy.utils.tiled_scale(
                    in_img,
                    lambda a: upscale_model(a.float()),
                    tile_x=tile,
                    tile_y=tile,
                    overlap=current_overlap,
                    upscale_amount=upscale_model.scale,
                    pbar=pbar,
                    output_device=output_device,
                )
                oom = False
            except Exception as e:
                comfy.model_management.raise_non_oom(e)

                if not auto_reduce_on_oom:
                    raise e

                attempt += 1
                tile //= 2
                current_overlap = max(0, current_overlap // 2)

                if current_overlap >= tile // 2:
                    current_overlap = max(0, tile // 4)

                print(f"[Rennart] ⚠️ OOM. Уменьшаю тайл до {tile}, перекрытие до {current_overlap} (попытка {attempt})")

                if tile < 128:
                    print("[Rennart] ❌ Достигнут минимальный размер тайла. Прерываю.")
                    raise e

        s = torch.clamp(s.movedim(-3, -1), min=0, max=1.0).to(comfy.model_management.intermediate_dtype())

        # --- 4. Освобождаем модель (по желанию) ---
        # Если раскомментировать — модель выгрузится после апскейла, освободив VRAM.
        # del upscale_model
        # torch.cuda.empty_cache()

        return (s,)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImageUpscaleWithModel": RennartImageUpscaleWithModel,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartImageUpscaleWithModel": "🔍 Rennart Image Upscale (Model)",
}