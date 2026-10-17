"""
Rennart Exposure Fusion
Слияние экспозиций (по мотивам Mertens et al., 2007) для коррекции света:
высветлить недосветы и затемнить пересветы — без масок по яркости и без ореолов.

Как работает:
  1. Из снимка строятся виртуальные экспозиции: светлее (+1, +2 … EV) и темнее (−1 … EV),
     честным сдвигом в линейном свете.
  2. Каждой версии в каждом пикселе даётся вес «насколько тон близок к середине».
     Светлые версии участвуют только в тенях исходника, тёмные — только в его светах,
     причём тёмные — только там, где в светах есть детали (плоское небо/белая стена не сереют).
  3. Версии склеиваются через пирамиды Лапласа — переходы плавные.
  4. Меняется только яркость L (LAB), цвет остаётся от исходника.
  Против ореолов: веса уточняются guided-фильтром по краям изображения, глубина пирамиды
  ограничивается, а тени рядом с источниками света (фонари, фары) не вытягиваются.

Только numpy — дополнительных зависимостей нет.
"""

import numpy as np
import torch


# ---------------- цвет ----------------

def _srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


_M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                       [0.2126729, 0.7151522, 0.0721750],
                       [0.0193339, 0.1191920, 0.9503041]], np.float32)
_M_XYZ2RGB = np.linalg.inv(_M_RGB2XYZ).astype(np.float32)
_WHITE = np.array([0.95047, 1.0, 1.08883], np.float32)


def _rgb_to_lab(rgb):
    xyz = _srgb_to_linear(rgb) @ _M_RGB2XYZ.T / _WHITE
    d = 6 / 29
    f = np.where(xyz > d ** 3, np.cbrt(xyz), xyz / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1).astype(np.float32)


def _lab_to_rgb(lab):
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], -1)
    d = 6 / 29
    xyz = np.where(f > d, f ** 3, 3 * d * d * (f - 4 / 29)) * _WHITE
    return _linear_to_srgb(xyz @ _M_XYZ2RGB.T).astype(np.float32)


def _shift_ev(rgb, ev):
    """Сдвиг экспозиции на ev ступеней в линейном свете (с обрезкой, как у настоящей камеры)."""
    return _linear_to_srgb(_srgb_to_linear(rgb) * (2.0 ** ev)).astype(np.float32)


# ---------------- пирамиды ----------------
_K = np.array([1, 4, 6, 4, 1], np.float32) / 16


def _blur(x):
    """Сепарабельный фильтр 5x5 (как cv2.pyrDown), отражение по краям."""
    extra = ((0, 0),) * (x.ndim - 2)
    p = np.pad(x, ((2, 2), (0, 0)) + extra, mode='reflect')
    x = sum(_K[i] * p[i:i + x.shape[0]] for i in range(5))
    p = np.pad(x, ((0, 0), (2, 2)) + extra, mode='reflect')
    return sum(_K[i] * p[:, i:i + x.shape[1]] for i in range(5))


def _down(x):
    return _blur(x)[::2, ::2]


def _up(x, shape):
    out = np.zeros(tuple(shape[:2]) + x.shape[2:], np.float32)
    out[::2, ::2] = x
    return _blur(out) * 4


def _levels(h, w):
    return int(np.log2(max(1, min(h, w)))) + 1


def _gauss_pyr(x, n):
    pyr = [x]
    for _ in range(n - 1):
        pyr.append(_down(pyr[-1]))
    return pyr


def _lap_pyr(x, n):
    g = _gauss_pyr(x, n)
    return [g[i] - _up(g[i + 1], g[i].shape) for i in range(n - 1)] + [g[-1]]


def _collapse(pyr):
    x = pyr[-1]
    for lev in reversed(pyr[:-1]):
        x = lev + _up(x, lev.shape)
    return x


def _box_mean(x, r):
    """Среднее в окне (2r+1)^2 через интегральное изображение."""
    p = np.pad(x, r + 1, mode='reflect').astype(np.float64)
    c = p.cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return (s / (k * k))[:x.shape[0], :x.shape[1]].astype(np.float32)


def _local_std(x, r):
    m = _box_mean(x, r)
    return np.sqrt(np.maximum(_box_mean(x * x, r) - m * m, 0))


def _guided(I, p, r, eps):
    """Guided filter (He et al.): сглаживает p, сохраняя края изображения-гида I."""
    mI = _box_mean(I, r); mp = _box_mean(p, r)
    cov = _box_mean(I * p, r) - mI * mp
    var = _box_mean(I * I, r) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return _box_mean(a, r) * I + _box_mean(b, r)


def _wide_blur(x, levels):
    """Сильное размытие через пирамиду (дёшево для больших радиусов)."""
    g = _gauss_pyr(x[..., None].astype(np.float32), levels + 1)
    s = g[-1]
    for lev in reversed(g[:-1]):
        s = _up(s, lev.shape)
    return s[..., 0]


# ---------------- алгоритм ----------------

def _ramp(x, a, b):
    """0 при x<=a, 1 при x>=b, плавно между (smoothstep). Если a>b — обратная рампа."""
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def exposure_fusion(img, shadows_ev, shadows_range, highlights_ev, highlights_range, highlight_detail,
                    mid_tone, sigma, contrast_weight, saturation_weight, luminance_only, protect_tones,
                    strength, halo_control=0.5, protect_lights=0.5):
    """img: HxWx3 float32 [0..1]. Возвращает (результат, превью весов)."""
    luma_in = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)

    # маски участия (по исходнику): тени для светлых копий, света для тёмных
    m_sh = _ramp(luma_in, shadows_range + 0.1, shadows_range - 0.1)
    m_hl = _ramp(luma_in, highlights_range - 0.1, highlights_range)
    if highlight_detail > 0:
        # деталь в светах: локальный разброс яркости; плоские белые зоны не трогаем
        # яркость слегка размыта, чтобы зерно/шум JPEG не считались деталями
        thr = 0.03 * highlight_detail
        smooth = _up(_down(luma_in[..., None]), luma_in.shape + (1,))[..., 0]
        m_hl = m_hl * _ramp(_local_std(smooth, 6), 0.5 * thr, thr)

    if protect_lights > 0:
        # источники света (почти белые) и их окрестность: тени рядом с ними не вытягиваем,
        # иначе слабое свечение вокруг фонаря раздувается в большой светлый диск
        h0, w0 = luma_in.shape
        src = _ramp(luma_in, 0.90, 0.98)
        lv = max(1, int(np.log2(max(8, min(h0, w0) / 12))))  # радиус ~1/12 кадра
        glow = _wide_blur(src, lv)
        glow = glow / (glow.max() + 1e-6)
        m_sh = m_sh * (1 - protect_lights * _ramp(glow, 0.02, 0.3))

    # набор экспозиций: (изображение, маска участия, цвет превью)
    stack = [(img, None, (0.5, 0.5, 0.5))]
    n_sh = int(np.ceil(shadows_ev - 1e-6))
    for k in range(1, n_sh + 1):
        ev = shadows_ev * k / n_sh
        stack.append((_shift_ev(img, ev), m_sh, (1.0, 0.95 - 0.25 * k / n_sh, 0.1)))
    n_hl = int(np.ceil(highlights_ev - 1e-6))
    for k in range(1, n_hl + 1):
        ev = -highlights_ev * k / n_hl
        stack.append((_shift_ev(img, ev), m_hl, (0.15, 0.55 - 0.3 * k / n_hl, 1.0)))

    if len(stack) == 1:
        return img.copy(), np.full_like(img, 0.5)

    # веса
    weights = []
    for k, (im, mask, _) in enumerate(stack):
        luma = im @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        w = np.exp(-((luma - mid_tone) ** 2) / (2 * sigma * sigma)).astype(np.float32)
        if contrast_weight > 0:
            p = np.pad(luma, 1, mode='reflect')
            lap = np.abs(p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] - 4 * luma)
            w = w * (lap + 1e-3) ** contrast_weight
        if saturation_weight > 0:
            w = w * (im.std(axis=-1) + 1e-3) ** saturation_weight
        if mask is not None:
            w = w * mask
        if k == 0:
            w = w + 1e-4  # исходник всегда остаётся запасным вариантом
        weights.append(w)
    W = np.stack(weights)
    if halo_control > 0:
        # веса следуют за краями изображения и не перетекают через границы «свет / тень»
        r = max(2, int(round(min(img.shape[:2]) / 60)))
        refined = []
        for wk, (_, mask, _) in zip(W, stack):
            q = np.maximum(_guided(luma_in, wk, r, 1e-3), 0)
            if mask is not None:
                q = q * mask  # фильтр не должен расширять зону участия копии (иначе сереют фонари)
            refined.append(q)
        W = np.stack(refined) + 1e-12
        W[0] += 1e-4
    W /= W.sum(0, keepdims=True)

    # слияние: только яркость L (быстрее в 3 раза) или все каналы
    n = _levels(*img.shape[:2])
    if halo_control > 0:
        # ограничение глубины пирамиды: меньше «дальнобойность» протекания весов
        n = max(5, int(round(n - halo_control * (n - 6))))
    lab_in = _rgb_to_lab(img)
    if luminance_only:
        planes = [lab_in[..., :1] / 100.0] + [_rgb_to_lab(im)[..., :1] / 100.0 for im, _, _ in stack[1:]]
    else:
        planes = [im for im, _, _ in stack]
    acc = None
    for pl, wk in zip(planes, W):
        gw = _gauss_pyr(wk[..., None], n)
        part = [a * b for a, b in zip(_lap_pyr(pl.astype(np.float32), n), gw)]
        acc = part if acc is None else [a + b for a, b in zip(acc, part)]
    fused = _collapse(acc)

    if luminance_only:
        Lf = np.clip(fused[..., 0] * 100.0, 0, 100)
        ab = lab_in[..., 1:]
    else:
        lab_f = _rgb_to_lab(np.clip(fused, 0, 1))
        Lf, ab = lab_f[..., 0], lab_f[..., 1:]

    Li = lab_in[..., 0]
    if protect_tones:
        # тени не темнее исходника, света не ярче исходника (плавно по яркости исходника)
        p_sh = _ramp(Li, 60, 30)
        p_hl = _ramp(Li, 40, 70)
        Lf = Lf + p_sh * np.maximum(0, Li - Lf) - p_hl * np.maximum(0, Lf - Li)

    L = Li + strength * (Lf - Li)
    out = _lab_to_rgb(np.concatenate([L[..., None], ab], -1))

    # превью весов, слегка сглаженное
    preview = sum(W[k][..., None] * np.array(c, np.float32) for k, (_, _, c) in enumerate(stack))
    g = _gauss_pyr(preview.astype(np.float32), min(3, n))
    sm = g[-1]
    for lev in reversed(g[:-1]):
        sm = _up(sm, lev.shape)
    return np.clip(out, 0, 1), np.clip(sm, 0, 1).astype(np.float32)


def _info_text(shape, shadows_ev, shadows_range, highlights_ev, highlights_range, highlight_detail,
               mid_tone, sigma, contrast_weight, saturation_weight, halo_control, protect_lights,
               luminance_only, protect_tones, strength):
    """Многострочный текст для Show Text / Show Any: что делает нода и с какими настройками отработала."""
    n_sh = int(np.ceil(shadows_ev - 1e-6))
    n_hl = int(np.ceil(highlights_ev - 1e-6))
    sh = ", ".join(f"+{shadows_ev * k / n_sh:g}" for k in range(1, n_sh + 1)) or "—"
    hl = ", ".join(f"-{highlights_ev * k / n_hl:g}" for k in range(1, n_hl + 1)) or "—"
    b, h, w = shape[0], shape[1], shape[2]
    lines = [
        "🌗 Rennart Exposure Fusion",
        "Exposure fusion (Mertens 2007): shadows from brighter virtual exposures,",
        "highlights with detail from darker ones, midtones stay untouched. No neural networks.",
        "",
        f"Image: {w} x {h}" + (f", batch {b}" if b > 1 else ""),
        f"Brighter copies (EV): {sh}   — only where source luma < {shadows_range:g} (±0.1)",
        f"Darker copies (EV):   {hl}   — only where source luma > {highlights_range:g}",
        f"Highlight detail: {highlight_detail:g}   Halo control: {halo_control:g}   Protect lights: {protect_lights:g}",
        f"Mid tone: {mid_tone:g}   Sigma: {sigma:g}   Contrast w: {contrast_weight:g}   Saturation w: {saturation_weight:g}",
        f"Color via LAB (luminance only): {'on — a/b from source' if luminance_only else 'off — RGB fused'}",
        f"Protect tones: {'on' if protect_tones else 'off'}   Strength: {strength:g}",
    ]
    if n_sh == 0 and n_hl == 0:
        lines.append("Note: shadows_ev = 0 and highlights_ev = 0 — image passed through unchanged.")
    return "\n".join(lines)


class RennartExposureFusion:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "shadows_ev": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.1,
                    "tooltip": "Насколько можно высветлить тени (EV). Строятся копии +1, +2 … до этого значения. 0 — тени не трогать.",
                }),
                "shadows_range": ("FLOAT", {
                    "default": 0.35, "min": 0.05, "max": 0.8, "step": 0.01,
                    "tooltip": "Что считать тенями: яркость исходника ниже этого значения (0..1, мягкая граница ±0.1).",
                }),
                "highlights_ev": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 3.0, "step": 0.1,
                    "tooltip": "Насколько можно затемнить пересветы (EV). 0 — света не трогать.",
                }),
                "highlights_range": ("FLOAT", {
                    "default": 0.85, "min": 0.5, "max": 1.0, "step": 0.01,
                    "tooltip": "Что считать светами: яркость исходника выше этого значения (мягкий переход начинается на 0.1 ниже).",
                }),
                "highlight_detail": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 2.0, "step": 0.05,
                    "tooltip": "Затемнять света только там, где есть детали. 0 — затемнять все света; больше — плоские белые зоны (небо, стена) не трогаются.",
                }),
                "mid_tone": ("FLOAT", {
                    "default": 0.5, "min": 0.2, "max": 0.8, "step": 0.01,
                    "tooltip": "К какому тону стремиться (0.5 — середина).",
                }),
                "sigma": ("FLOAT", {
                    "default": 0.2, "min": 0.05, "max": 0.6, "step": 0.01,
                    "tooltip": "Строгость выбора: меньше — сильнее тянет к mid_tone, больше — мягче.",
                }),
                "contrast_weight": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 2.0, "step": 0.1,
                    "tooltip": "Предпочитать версии с бо́льшим локальным контрастом. Может усиливать шум в тенях.",
                }),
                "saturation_weight": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 2.0, "step": 0.1,
                    "tooltip": "Предпочитать более насыщенные версии.",
                }),
                "halo_control": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Подавление ореолов: веса следуют за краями (guided filter) и меньше протекают на соседние зоны. "
                               "0 — классическое слияние; 1 — максимум (яркие источники могут слегка посереть).",
                }),
                "protect_lights": ("FLOAT", {
                    "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Не вытягивать тени рядом с источниками света (фонари, фары), чтобы свечение вокруг них не раздувалось в диск.",
                }),
                "luminance_only": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Менять только яркость L (LAB), цвет оставить от исходника. Также ускоряет работу в 3 раза.",
                }),
                "protect_tones": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Тени не делать темнее исходника, света — не ярче.",
                }),
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Сила эффекта: смешивание яркости с исходником.",
                }),
            },

        }

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("image", "weights_preview", "info")
    FUNCTION = "fuse"
    DESCRIPTION = (
        "Слияние экспозиций: тени из светлых версий, пересветы с деталями — из тёмных, середина остаётся.\n"
        "weights_preview: серый — исходник, жёлтый/оранжевый — светлые копии, голубой/синий — тёмные копии.\n"
        "info: краткое описание ноды и текущих настроек (для Show Text / Show Any)."
    )

    def fuse(self, image, shadows_ev, shadows_range, highlights_ev, highlights_range, highlight_detail,
             mid_tone, sigma, contrast_weight, saturation_weight, halo_control, protect_lights,
             luminance_only, protect_tones, strength):
        print(
            f"[Rennart] Exposure Fusion: shadows={shadows_ev}EV<{shadows_range}, "
            f"highlights={highlights_ev}EV>{highlights_range}, detail={highlight_detail}, "
            f"halo={halo_control}, lights={protect_lights}, strength={strength}"
        )
        imgs = image.detach().cpu().float().numpy()
        outs, previews = [], []
        for b in range(imgs.shape[0]):
            o, p = exposure_fusion(
                imgs[b, ..., :3], shadows_ev, shadows_range, highlights_ev, highlights_range, highlight_detail,
                mid_tone, sigma, contrast_weight, saturation_weight, luminance_only, protect_tones, strength,
                halo_control, protect_lights,
            )
            outs.append(torch.from_numpy(np.ascontiguousarray(o)))
            previews.append(torch.from_numpy(np.ascontiguousarray(p)))
        info = _info_text(imgs.shape, shadows_ev, shadows_range, highlights_ev, highlights_range, highlight_detail,
                          mid_tone, sigma, contrast_weight, saturation_weight, halo_control, protect_lights,
                          luminance_only, protect_tones, strength)
        return (torch.stack(outs), torch.stack(previews), info)


NODE_CLASS_MAPPINGS = {
    "RennartExposureFusion": RennartExposureFusion,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartExposureFusion": "🌗 Rennart Exposure Fusion",
}
