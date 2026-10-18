"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\\custom_nodes\\ComfyUI-Rennart\\Rennart_Denoise.py
Категория: Rennart/Image

🧹 Rennart Denoise — весь шумодав Rennart (граф denoise_001) в одной ноде.

Схема:
  Delicate   — SCUNet PSNR и SCUNet GAN (двойной проход Rennart), по желанию DeBlur (1x_DeBLR:
               яркость L от DeBLR, цвет a/b от SCUNet), смешивание GAN ⟷ PSNR.
  Aggressive — RealPLKSR (прямой + по инвертированной картинке, 50/50)
               и RealESRGAN x2 → обратно к исходному размеру (прямой + инвертированный),
               смешивание RealPLKSR ⟷ RealESRGAN.
  Итог       — Delicate ⟷ Aggressive, затем Strength (смешивание с исходником).
  Все смешивания 8-битные, как LayerStyle (Image Blend, LAB через Pillow).

Модели ищутся в ComfyUI/models/upscale_models; если файла нет — скачиваются с Hugging Face (Rennart)
и проверяются по SHA256. Результаты веток кэшируются: при смене балансов, Strength и DeBlur
пересчитывается только то, что изменилось; ветки с нулевым весом не считаются.
"""

import hashlib
import os
import time
import urllib.request

import numpy as np
import torch
from PIL import Image

import comfy.model_management
import comfy.model_patcher
import comfy.utils
import folder_paths
from spandrel import ImageModelDescriptor, ModelLoader

TAG = "[Rennart Denoise]"

# ============================================================
# Модели
# ============================================================
MODELS = {
    "scunet_psnr": {
        "file": "scunet_color_real_psnr.pth",
        "repo": "Rennart/SCUNet-color-real-psnr-fp32",
        "sha256": "fa78899ba2caec9d235a900e91d96c689da71c42029230c2028b00f09f809c2e",
        "title": "SCUNet PSNR",
    },
    "scunet_gan": {
        "file": "scunet_color_real_gan.pth",
        "repo": "Rennart/SCUNet-color-real-gan-fp32",
        "sha256": "892c83f812c59173273b74f4f34a14ecaf57a2fdb68df056664589beb55c966e",
        "title": "SCUNet GAN",
    },
    "realplksr": {
        "file": "1xDeNoise_realplksr_otf.safetensors",
        "repo": "Rennart/1xDeNoise_realplksr_otf",
        "sha256": "0a3e22bdcb70dd790fce66f45df8d07e774e269b17c92a2835162b150d4a365c",
        "title": "RealPLKSR",
    },
    "deblur": {
        "file": "1x_DeBLR.pth",
        "repo": "Rennart/1x_models",
        "sha256": "33bacbe39bdd40fc41a8d080f2d10b7a2276689c3e983a26f7f3c4c02ad3bdff",
        "title": "DeBLR",
    },
    "esrgan": {
        "file": "RealESRGAN_x2plus.pth",
        "repo": "Rennart/realesrgan-x2",
        "sha256": "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb",
        "title": "RealESRGAN x2",
    },
}


def _find_local(filename):
    """Файл в любой из папок upscale_models (в том числе во вложенных папках)."""
    p = folder_paths.get_full_path("upscale_models", filename)
    if p and os.path.isfile(p):
        return p
    for rel in folder_paths.get_filename_list("upscale_models"):
        if os.path.basename(rel).lower() == filename.lower():
            p = folder_paths.get_full_path("upscale_models", rel)
            if p and os.path.isfile(p):
                return p
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_url(url, dst):
    """Запасной путь без huggingface_hub: скачивание по прямой ссылке с прогрессом в консоли."""
    tmp = dst + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-Rennart"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                if pct // 10 != last // 10:
                    print(f"{TAG}   {pct}%  ({done >> 20} / {total >> 20} MB)")
                    last = pct
    os.replace(tmp, dst)


def _model_path(key):
    spec = MODELS[key]
    p = _find_local(spec["file"])
    if p:
        return p
    models_dir = folder_paths.get_folder_paths("upscale_models")[0]
    os.makedirs(models_dir, exist_ok=True)
    dst = os.path.join(models_dir, spec["file"])
    print(f"{TAG} Модель {spec['file']} не найдена — скачиваю с huggingface.co/{spec['repo']}")
    try:
        from huggingface_hub import hf_hub_download
        got = hf_hub_download(repo_id=spec["repo"], filename=spec["file"], local_dir=models_dir)
        if os.path.abspath(got) != os.path.abspath(dst) and os.path.isfile(got):
            os.replace(got, dst)
    except ImportError:
        _download_url(f"https://huggingface.co/{spec['repo']}/resolve/main/{spec['file']}", dst)
    except Exception as e:
        raise RuntimeError(
            f"{TAG} Не удалось скачать {spec['file']} из {spec['repo']}: {e}\n"
            f"Скачайте файл вручную и положите в {models_dir}"
        )
    if not os.path.isfile(dst):
        raise RuntimeError(f"{TAG} Файл {spec['file']} не появился в {models_dir}")
    digest = _sha256(dst)
    if digest != spec["sha256"]:
        os.remove(dst)
        raise RuntimeError(f"{TAG} {spec['file']}: контрольная сумма не совпала (файл удалён). Попробуйте ещё раз.")
    print(f"{TAG} {spec['file']} скачана и проверена (SHA256 ок)")
    return dst


_LOADED = {}  # (key, fp16) → ImageModelDescriptor с patcher


def _get_model(key, fp16):
    """Загрузка через Spandrel — как в «Rennart Denoise (Select Model)». Модели держатся в памяти между запусками."""
    ck = (key, fp16)
    if ck in _LOADED:
        return _LOADED[ck]
    path = _model_path(key)
    sd = comfy.utils.load_torch_file(path, safe_load=True)
    if "module.layers.0.residual_group.blocks.0.norm1.weight" in sd:
        sd = comfy.utils.state_dict_prefix_replace(sd, {"module.": ""})
    model = ModelLoader().load_from_state_dict(sd).eval()
    if not isinstance(model, ImageModelDescriptor):
        raise RuntimeError(f"{TAG} {MODELS[key]['file']}: модель не распознана как single-image модель.")
    model.rd_half = bool(fp16 and getattr(model, "supports_half", False))
    if model.rd_half:
        model.model.half()
    model.patcher = comfy.model_patcher.CoreModelPatcher(
        model.model,
        load_device=comfy.model_management.get_torch_device(),
        offload_device=comfy.model_management.unet_offload_device(),
    )
    _LOADED[ck] = model
    return model


# ============================================================
# Тайлы (из «Rennart Denoise (Select Model)» — без изменений) и ImageUpscaleWithModel
# ============================================================
def _safe_pad(tensor_chw, pad):
    """Reflect padding; для слишком маленьких изображений — replicate."""
    try:
        return torch.nn.functional.pad(tensor_chw, (pad, pad, pad, pad), mode="reflect")
    except RuntimeError:
        return torch.nn.functional.pad(tensor_chw, (pad, pad, pad, pad), mode="replicate")


def _run(model):
    if model.rd_half:
        return lambda a: model(a.half()).float()
    return lambda a: model(a.float())


def _apply_model_tiled(image, model, tile_size, overlap, pad_for_edges, pbar):
    """IMAGE [B,H,W,C] тайлами через comfy.utils.tiled_scale."""
    B, H, W, C = image.shape
    if pad_for_edges and overlap > 0:
        pad = overlap
        img_padded = _safe_pad(image.movedim(-1, -3), pad).movedim(-3, -1)
    else:
        pad = 0
        img_padded = image

    memory_required = (512 * 512 * 3) * image.element_size() * max(model.scale, 1.0) * 384.0
    memory_required += img_padded.nelement() * img_padded.element_size()
    comfy.model_management.load_models_gpu([model.patcher], memory_required=memory_required, force_full_load=True)

    device = model.patcher.load_device
    output_device = comfy.model_management.intermediate_device()
    in_img = img_padded.movedim(-1, -3).to(device)
    result = comfy.utils.tiled_scale(
        in_img, _run(model),
        tile_x=tile_size, tile_y=tile_size, overlap=overlap,
        upscale_amount=model.scale, output_device=output_device, pbar=pbar,
    )
    result = torch.clamp(result.movedim(-3, -1), min=0, max=1.0).float().cpu()
    if pad > 0:
        result = result[:, pad:pad + H, pad:pad + W, :]
    return result


def _apply_model_tiled_shifted(image, model, tile_size, overlap, offset, pbar):
    """Второй проход: паддинг, сдвиг, обработка, обратный сдвиг, обрезка."""
    B, H, W, C = image.shape
    pad = max(offset, overlap)
    img_padded = _safe_pad(image.movedim(-1, -3), pad).movedim(-3, -1) if pad > 0 else image
    shifted = torch.roll(img_padded, shifts=(offset, offset), dims=(1, 2))
    result_shifted = _apply_model_tiled(shifted, model, tile_size, overlap, False, pbar)
    result = torch.roll(result_shifted, shifts=(-offset, -offset), dims=(1, 2))
    if pad > 0:
        result = result[:, pad:pad + H, pad:pad + W, :]
    return result


def _tile_params(tile_size):
    overlap = tile_size // 4
    return tile_size, overlap, (tile_size - overlap) // 2


def _rennart(image, model, tile_size, pbar):
    """Двойной проход Rennart: обычный + со сдвигом, 50/50."""
    tile, overlap, offset = _tile_params(tile_size)
    r1 = _apply_model_tiled(image, model, tile, overlap, True, pbar)
    r2 = _apply_model_tiled_shifted(image, model, tile, overlap, offset, pbar)
    return r1 * 0.5 + r2 * 0.5


def _upscale_with_model(image, model, pbar):
    """Как стандартная нода ImageUpscaleWithModel: тайл 512, overlap 32, при нехватке памяти тайл уменьшается."""
    tile = 512
    while True:
        try:
            return _apply_model_tiled(image, model, tile, 32, False, pbar)
        except comfy.model_management.OOM_EXCEPTION:
            tile //= 2
            if tile < 128:
                raise
            print(f"{TAG} Не хватает памяти видеокарты — тайл уменьшен до {tile}")
            comfy.model_management.soft_empty_cache()


def _steps_rennart(w, h, tile_size):
    tile, overlap, offset = _tile_params(tile_size)
    pad2 = max(offset, overlap)
    return (comfy.utils.get_tiled_scale_steps(w + 2 * overlap, h + 2 * overlap, tile, tile, overlap)
            + comfy.utils.get_tiled_scale_steps(w + 2 * pad2, h + 2 * pad2, tile, tile, overlap))


def _steps_upscale(w, h):
    return comfy.utils.get_tiled_scale_steps(w, h, 512, 512, 32)


# ============================================================
# 8-битные операции (как LayerStyle / AGSoft: tensor2pil — усечение до байта)
# ============================================================
_FILTERS = {"Lanczos": Image.LANCZOS, "Bicubic": Image.BICUBIC, "Box": Image.BOX}


def _to8(t):
    """[H,W,3] float tensor → uint8 (np.clip(255*x).astype(uint8), как tensor2pil)."""
    a = t.detach().cpu().float().numpy()
    return np.clip(255.0 * a, 0, 255).astype(np.uint8)


def _from8(a):
    return torch.from_numpy(a.astype(np.float32) / 255.0)


def _blend8(bg, layer, opacity):
    """LayerUtility: ImageBlend, normal, без маски: Image.blend(layer, background, 1 - opacity/100)."""
    if opacity >= 100:
        return layer
    if opacity <= 0:
        return bg
    out = Image.blend(Image.fromarray(layer), Image.fromarray(bg), 1.0 - float(opacity) / 100)
    return np.asarray(out)


def _mix8(bg, layer, opacity):
    """Смешивание, где одна из сторон может быть не посчитана (её вес 0)."""
    if bg is None:
        return layer
    if layer is None:
        return bg
    return _blend8(bg, layer, opacity)


def _lab_channels(a8):
    return Image.fromarray(a8).convert("RGBA").convert("LAB").split()


def _luma_from8(lum8, color8):
    """L — из lum8, a/b — из color8 (LayerStyle: ImageChannelSplit LAB ×2 → ImageChannelMerge LAB)."""
    L = _lab_channels(lum8)[0]
    _, a, b = _lab_channels(color8)
    return np.asarray(Image.merge("LAB", (L, a, b)).convert("RGB"))


def _resize8(a8, w, h, flt):
    return np.asarray(Image.fromarray(a8).resize((w, h), _FILTERS[flt]))


# ============================================================
# Кэш веток
# ============================================================
_CACHE = {}  # ключ изображения → словарь веток


def _image_key(img, tile_size, precision):
    h = hashlib.blake2b(digest_size=16)
    a = img.detach().cpu().contiguous().numpy()
    h.update(str(a.shape).encode())
    h.update(a.tobytes())
    return (h.hexdigest(), tile_size, precision)


def _needs(ad, psnr, esr, direct):
    dl, ag = ad < 100, ad > 0
    plk, re = ag and esr < 100, ag and esr > 0
    return {
        "d1": dl and psnr > 0,          # SCUNet PSNR
        "d2": dl and psnr < 100,        # SCUNet GAN
        "p": plk,                       # RealPLKSR прямой + инвертированный
        "r": re and direct > 0,         # RealESRGAN прямой
        "rinv": re and direct < 100,    # RealESRGAN инвертированный
    }


INFO = """🧹 Rennart Denoise — the whole Rennart denoise graph in one node.

Delicate   = SCUNet PSNR + SCUNet GAN (two-pass tiling), optional DeBlur (luminance from 1x_DeBLR, color from SCUNet).
Aggressive = RealPLKSR (direct + inverted, 50/50) + RealESRGAN x2 and back (direct + inverted).
Result     = Delicate ⟷ Aggressive, then Strength (blend with the source). All blends are 8-bit, like LayerStyle.

Sliders (percent = share of the right side):
  strength                  — 0 source … 100 full denoise
  delicate_aggressive       — Delicate ⟷ Aggressive
  delicate_gan_psnr         — inside Delicate: SCUNet GAN ⟷ SCUNet PSNR
  aggressive_plksr_esrgan   — inside Aggressive: RealPLKSR ⟷ RealESRGAN
  esrgan_inverted_direct    — RealESRGAN: inverted ⟷ direct pass
Branches with zero weight are not computed. Branch results are cached for the last image:
changing sliders, strength or deblur re-blends in seconds.

Outputs: image, delicate, aggressive (black if the group has zero weight), info, stat.
Models: ComfyUI/models/upscale_models, downloaded automatically from huggingface.co/Rennart on first run."""


class RennartDenoise:
    @classmethod
    def INPUT_TYPES(cls):
        pct = {"min": 0, "max": 100, "step": 1, "display": "slider"}
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("INT", dict(pct, default=100, tooltip=(
                    "Общая сила шумоподавления: смешивание результата с исходником. 0 — исходник, 100 — полный результат."))),
                "delicate_aggressive": ("INT", dict(pct, default=25, tooltip=(
                    "Delicate ⟷ Aggressive: доля Aggressive (RealPLKSR + RealESRGAN) поверх Delicate (SCUNet). "
                    "0 — Aggressive не считается, 100 — Delicate не считается."))),
                "delicate_gan_psnr": ("INT", dict(pct, default=25, tooltip=(
                    "Delicate: SCUNet GAN ⟷ SCUNet PSNR — доля PSNR поверх GAN."))),
                "aggressive_plksr_esrgan": ("INT", dict(pct, default=25, tooltip=(
                    "Aggressive: RealPLKSR ⟷ RealESRGAN — доля RealESRGAN (x2 и обратно) поверх RealPLKSR."))),
                "esrgan_inverted_direct": ("INT", dict(pct, default=50, tooltip=(
                    "RealESRGAN: инверсия ⟷ прямая — доля прямого прохода поверх прохода по инвертированной картинке."))),
                "deblur": ("BOOLEAN", {"default": True, "tooltip": (
                    "DeBlur для обеих веток SCUNet (Delicate): резкость только по яркости (1x_DeBLR), цвет от SCUNet.")}),
                "esrgan_downscale": (list(_FILTERS), {"default": "Lanczos", "tooltip": (
                    "Чем вернуть выход RealESRGAN x2 к исходному размеру (Pillow). В графе — Lanczos.")}),
                "tile_size": ("INT", {"default": 512, "min": 128, "max": 2048, "step": 64, "tooltip": (
                    "Тайл двойного прохода Rennart. overlap = tile/4, offset = (tile − overlap)/2. "
                    "512 — как в графе (overlap 128, offset 192).")}),
                "precision": (["fp32", "fp16"], {"default": "fp32", "tooltip": (
                    "fp32 — точно как в графе. fp16 — быстрее и меньше памяти, результат может чуть отличаться.")}),
            }
        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "delicate", "aggressive", "info", "stat")
    FUNCTION = "denoise"
    DESCRIPTION = (
        "Шумодав Rennart (граф denoise_001) в одной ноде: Delicate (SCUNet PSNR/GAN + DeBlur) и "
        "Aggressive (RealPLKSR + RealESRGAN x2, прямые и инвертированные проходы), 8-битные смешивания как LayerStyle.\n"
        "Модели скачиваются автоматически с huggingface.co/Rennart. Ветки кэшируются: ползунки пересчитываются за секунды."
    )

    def denoise(self, image, strength, delicate_aggressive, delicate_gan_psnr, aggressive_plksr_esrgan,
                esrgan_inverted_direct, deblur, esrgan_downscale, tile_size, precision):
        t_all = time.time()
        fp16 = precision == "fp16"
        need = _needs(delicate_aggressive, delicate_gan_psnr, aggressive_plksr_esrgan, esrgan_inverted_direct)
        B, H, W, _ = image.shape
        print(f"{TAG} strength={strength} D/A={delicate_aggressive} GAN/PSNR={delicate_gan_psnr} "
              f"PLKSR/ESRGAN={aggressive_plksr_esrgan} inv/direct={esrgan_inverted_direct} "
              f"deblur={deblur} downscale={esrgan_downscale} tile={tile_size} {precision}")

        # кэш: только изображения текущего пакета
        keys = [_image_key(image[b], tile_size, precision) for b in range(B)]
        for k in list(_CACHE):
            if k not in keys:
                del _CACHE[k]
        entries = [_CACHE.setdefault(k, {}) for k in keys]

        # план: сколько тайлов предстоит посчитать (для полосы прогресса)
        steps = 0
        rn, up = _steps_rennart(W, H, tile_size), _steps_upscale(W, H)
        for e in entries:
            for br, sc in (("d1", "a1"), ("d2", "a2")):
                if need[br]:
                    steps += (rn if sc not in e else 0) + (up if deblur and br + "_db" not in e else 0)
            if need["p"]:
                steps += (rn if "p" not in e else 0) + (rn if "pinv" not in e else 0)
            for br in ("r", "rinv"):
                if need[br] and e.get(br, (None,))[0] != esrgan_downscale:
                    steps += up
        pbar = comfy.utils.ProgressBar(max(1, steps))

        outs, dels, aggs, stat = [], [], [], []
        for b in range(B):
            e = entries[b]
            img = image[b:b + 1].float().cpu()
            log = []

            def timed(name, fn):
                comfy.model_management.throw_exception_if_processing_interrupted()
                t = time.time()
                r = fn()
                log.append(f"  {name}: computed, {time.time() - t:.1f} s")
                return r

            def delicate(scunet_key, a_key, br, title):
                # кэшируются выход SCUNet (float) и вариант с DeBlur — переключение галочки DeBlur мгновенное
                if not need[br]:
                    log.append(f"  {title}: skipped (weight 0)")
                    return None
                if a_key in e:
                    log.append(f"  {title}: cache")
                else:
                    e[a_key] = timed(title, lambda: _rennart(img, _get_model(scunet_key, fp16), tile_size, pbar))
                a = e[a_key]
                if not deblur:
                    return _to8(a[0])
                db_key = br + "_db"
                if db_key in e:
                    log.append(f"  {title} DeBlur: cache")
                else:
                    db = timed(f"{title} DeBlur", lambda: _upscale_with_model(a, _get_model("deblur", fp16), pbar))
                    e[db_key] = _luma_from8(_to8(db[0]), _to8(a[0]))
                return e[db_key]

            # ---------- Delicate ----------
            d1 = delicate("scunet_psnr", "a1", "d1", "SCUNet PSNR")
            d2 = delicate("scunet_gan", "a2", "d2", "SCUNet GAN")

            # ---------- Aggressive ----------
            p = pinv = None
            if need["p"]:
                if "p" in e:
                    log.append("  RealPLKSR: cache")
                else:
                    e["p"] = _to8(timed("RealPLKSR", lambda: _rennart(img, _get_model("realplksr", fp16), tile_size, pbar))[0])
                if "pinv" in e:
                    log.append("  RealPLKSR inverted: cache")
                else:
                    e["pinv"] = _to8(1.0 - timed("RealPLKSR inverted", lambda: _rennart(
                        1.0 - img, _get_model("realplksr", fp16), tile_size, pbar))[0])
                p, pinv = e["p"], e["pinv"]
            else:
                log.append("  RealPLKSR: skipped (weight 0)")

            def esrgan(br, inverted, title):
                if not need[br]:
                    log.append(f"  {title}: skipped (weight 0)")
                    return None
                if e.get(br, (None,))[0] == esrgan_downscale:
                    log.append(f"  {title}: cache")
                    return e[br][1]
                src = 1.0 - img if inverted else img
                o = timed(title, lambda: _upscale_with_model(src, _get_model("esrgan", fp16), pbar))
                o8 = _to8(1.0 - o[0] if inverted else o[0])
                res = _resize8(o8, W, H, esrgan_downscale)
                e[br] = (esrgan_downscale, res)
                return res

            r = esrgan("r", False, "RealESRGAN")
            rinv = esrgan("rinv", True, "RealESRGAN inverted")

            # ---------- смешивания (роли фон/слой — как в графе) ----------
            t_mix = time.time()
            del8 = _mix8(d2, d1, delicate_gan_psnr) if (d1 is not None or d2 is not None) else None
            plk8 = _blend8(pinv, p, 50) if p is not None else None
            re8 = _mix8(rinv, r, esrgan_inverted_direct) if (r is not None or rinv is not None) else None
            agg8 = _mix8(plk8, re8, aggressive_plksr_esrgan) if (plk8 is not None or re8 is not None) else None
            out8 = _mix8(del8, agg8, delicate_aggressive)
            if strength < 100:
                out8 = _blend8(_to8(img[0]), out8, strength)
            log.append(f"  blends: {time.time() - t_mix:.2f} s")

            black = np.zeros((H, W, 3), np.uint8)
            outs.append(_from8(out8))
            dels.append(_from8(del8 if del8 is not None else black))
            aggs.append(_from8(agg8 if agg8 is not None else black))
            stat.append((f"Image {b + 1}/{B} ({W} x {H}):" if B > 1 else f"Image {W} x {H}:"))
            stat.extend(log)

        comfy.model_management.soft_empty_cache()
        total = time.time() - t_all
        stat.append(f"Total: {total:.1f} s   (precision {precision}, tile {tile_size})")
        stat_text = "🧹 Rennart Denoise — stat\n" + "\n".join(stat)
        print(stat_text)
        return (torch.stack(outs), torch.stack(dels), torch.stack(aggs), INFO, stat_text)


NODE_CLASS_MAPPINGS = {
    "RennartDenoise": RennartDenoise,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartDenoise": "🧹 Rennart Denoise",
}
