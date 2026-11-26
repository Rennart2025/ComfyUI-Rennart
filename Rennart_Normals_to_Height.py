# -*- coding: utf-8 -*-
"""
================================================================================
Файл и путь : Rennart_Normals_to_Height.py
              ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Normals_to_Height.py
Пакет       : https://github.com/Rennart2025/ComfyUI-Rennart
Категория   : Rennart/Textures
================================================================================

[RU] Rennart Normals to Height
------------------------------
Восстанавливает карту высот (height map) из карты нормалей интегрированием
поля наклонов — решение уравнения Пуассона. Два решателя:

  * relief/tileable ВЫКЛ — глобальный DCT-решатель с граничными условиями
    Неймана (backward-разностная дивергенция, согласованная со спектром
    DCT-Лапласиана). Нет wrap-around проблемы FFT на границах, нет швов
    тайловых схем — вся детализация поля наклонов сохраняется.
  * tileable ВКЛ — периодический FFT-решатель для бесшовных текстур:
    левый край стыкуется с правым, верх с низом (шаг через шов равен
    обычному шагу между пикселями).

Флаги:
  * relief  ВКЛ (по умолчанию) — высокочастотный фильтр h - blur(h, detail):
    ровный серый фон и равномерно читаемый локальный рельеф (визуально как
    у тайловых решателей типа Chord, но без швов).
    ВЫКЛ — честная глобальная высота со всей крупной формой.
  * tileable ВКЛ — режим зацикленных текстур (FFT + кольцевое размытие).

Нормализация результата (normalize_mode):
  * soft (по умолчанию) — перцентильная шкала 0.5-99.5 + плавный ролл-офф
    tanh: экстремумы асимптотически стремятся к 0/1, плоских участков
    (чистых 0/255) нет — карта пригодна как displacement в 3D-редакторах;
  * percentile — жёсткий клип 0.5-99.5;
  * minmax — по абсолютным мин/макс поля.

Прочее: detail — радиус фильтра relief в px на рабочем разрешении
(32 — резкая деталь, 64-96 — мягче); smooth — сглаживание нормалей перед
интегрированием (0 = выкл.); invert — светлое = углублено;
flip_red/flip_green/flip_blue — смена конвенции карты нормалей
(OpenGL/DirectX); work_size — внутреннее рабочее разрешение по длинной
стороне (0 = родной размер кадра).

Зависимости: numpy, scipy (есть в requirements.txt пакета).

[EN] Rennart Normals to Height
------------------------------
Reconstructs a height map from a normal map by integrating the slope
field (Poisson equation). Two solvers: a global DCT solver with Neumann
boundary conditions (no FFT wrap-around, no tile seams) and, with
tileable enabled, a periodic FFT solver for seamless looping textures
(left edge wraps to right, top to bottom).

  * relief  ON (default) — high-pass h - blur(h, detail): flat gray
    background, uniformly readable local relief (Chord-like look, but
    seamless). OFF — the honest global height with all large-scale form.
  * tileable ON — periodic mode (FFT solver + wrap-aware blur).

normalize_mode: soft (percentile scale + tanh roll-off — extremes
approach 0/1 asymptotically, no flat pure-black/white areas, ideal for
displacement), percentile (hard 0.5-99.5 clip), minmax (true extremes).

Dependencies: numpy, scipy (see the pack's requirements.txt).
"""

import numpy as np
import torch
import torch.nn.functional as F
from scipy.fft import dctn, idctn, fft2, ifft2, fftfreq
from scipy.ndimage import gaussian_filter


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _get_normals(nm_rgb01, H, W, flip_red, flip_green, flip_blue):
    """RGB normal map [0,1] -> unit normals (x right, y up, z to camera),
    resized to HxW."""
    nm = nm_rgb01.astype(np.float32)
    if nm.shape[:2] != (H, W):
        t = torch.from_numpy(nm).permute(2, 0, 1)[None]
        t = F.interpolate(t, size=(H, W), mode='bilinear',
                          align_corners=False)
        nm = t[0].permute(1, 2, 0).numpy()
    n = nm * 2.0 - 1.0
    if flip_red:
        n[:, :, 0] = -n[:, :, 0]
    if flip_green:
        n[:, :, 1] = -n[:, :, 1]
    if flip_blue:
        n[:, :, 2] = -n[:, :, 2]
    norm = np.linalg.norm(n, axis=2, keepdims=True)
    return n / np.maximum(norm, 1e-6)


def _gauss(x, sigma, wrap=False):
    if sigma <= 0:
        return x.copy()
    return gaussian_filter(x, sigma, mode='wrap' if wrap else 'reflect')


# ---------------------------------------------------------------------
# Poisson solvers
# ---------------------------------------------------------------------

def _poisson_dct(p, q):
    """Least-squares height h from slopes (p = dh/dcol, q = dh/drow).

    Solves laplacian(h) = div(p, q) with Neumann boundary conditions.
    The backward-difference divergence is consistent with the DCT
    Laplacian eigenvalues, so a globally consistent slope field is
    reconstructed exactly; real (noisy, non-integrable) fields get the
    least-squares surface. Zero-mean result.
    """
    H, W = p.shape
    div = np.zeros((H, W), np.float64)
    div[:, 1:] = p[:, 1:] - p[:, :-1]
    div[:, 0] = p[:, 0]
    div[1:, :] += q[1:, :] - q[:-1, :]
    div[0, :] += q[0, :]
    fy = np.arange(H)[:, None]
    fx = np.arange(W)[None, :]
    den = 2 * np.cos(np.pi * fy / H) + 2 * np.cos(np.pi * fx / W) - 4
    den[0, 0] = 1.0
    d = dctn(div, norm='ortho') / den
    d[0, 0] = 0.0
    return idctn(d, norm='ortho')


def _poisson_fft_periodic(p, q):
    """Periodic Poisson solver (Frankot-Chellappa style) for tileable
    textures: the result wraps seamlessly — the step across the edge
    equals a normal interior pixel step. Zero-mean result."""
    H, W = p.shape
    P = fft2(p)
    Q = fft2(q)
    u = 2j * np.pi * fftfreq(W)[None, :]
    v = 2j * np.pi * fftfreq(H)[:, None]
    den = u * u + v * v
    den[0, 0] = 1.0
    # laplacian(h) = div(p,q) -> H = -(uP+vQ)/(kx^2+ky^2), а поскольку
    # u^2+v^2 = -(kx^2+ky^2) для u=2j*pi*f (конвенция numpy FFT),
    # итоговая формула — с плюсом (проверено численно: corr = 1.0)
    Z = (u * P + v * Q) / den
    Z[0, 0] = 0.0
    return np.real(ifft2(Z))


# ---------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------

def normals_to_height(nm_rgb01,
                      relief=True,
                      tileable=False,
                      detail=48,
                      smooth=0.0,
                      invert=False,
                      normalize_mode='soft',
                      flip_red=False,
                      flip_green=False,
                      flip_blue=False,
                      work_size=1024):
    """Height map [0,1] (HxWx3) from a normal map (HxWx3 float [0,1])."""
    H, W = nm_rgb01.shape[:2]
    if work_size and work_size > 0:
        scale = work_size / float(max(H, W))
        hw = (max(16, int(round(H * scale))), max(16, int(round(W * scale))))
    else:
        hw = (H, W)
    n = _get_normals(nm_rgb01, hw[0], hw[1],
                     flip_red, flip_green, flip_blue)

    if smooth > 0:
        n = np.dstack([_gauss(n[:, :, c], float(smooth), wrap=tileable)
                       for c in range(3)])
        norm = np.linalg.norm(n, axis=2, keepdims=True)
        n = n / np.maximum(norm, 1e-6)

    eps = 1e-6
    nz = np.where(np.abs(n[:, :, 2]) > eps, n[:, :, 2], eps)
    # surface normal (-dh/dx, -dh/dy_up, 1); image rows go down,
    # so dh/dcol = -nx/nz and dh/drow = +ny/nz
    p = (-n[:, :, 0] / nz).astype(np.float64)
    q = (n[:, :, 1] / nz).astype(np.float64)

    if tileable:
        height = _poisson_fft_periodic(p, q)
    else:
        height = _poisson_dct(p, q)

    if relief:
        sigma = max(float(detail), 1.0)
        height = height - _gauss(height, sigma, wrap=tileable)

    if normalize_mode == 'minmax':
        lo, hi = float(height.min()), float(height.max())
        height = np.clip((height - lo) / max(hi - lo, 1e-8), 0.0, 1.0)
    else:
        lo, hi = np.percentile(height, 0.5), np.percentile(height, 99.5)
        z = (height - lo) / max(hi - lo, 1e-8)
        if normalize_mode == 'soft':
            # tanh roll-off: экстремумы асимптотически к 0/1,
            # плоских участков (чистых 0/255) не возникает
            height = 0.5 * (1.0 + np.tanh(3.0 * (z - 0.5)))
        else:  # 'percentile' — жёсткий клип
            height = np.clip(z, 0.0, 1.0)
    if invert:
        height = 1.0 - height

    if hw != (H, W):
        t = torch.from_numpy(height.astype(np.float32))[None, None]
        t = F.interpolate(t, size=(H, W), mode='bilinear',
                          align_corners=False)
        height = t[0, 0].numpy()
    return np.dstack([height.astype(np.float32)] * 3)


# ---------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------

class RennartNormalsToHeight:
    """Normal map -> height map (Poisson integration). См. шапку файла."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'normal_map': ('IMAGE', {
                    'tooltip': 'Карта нормалей / Normal map (RGB)'
                }),
                'relief': ('BOOLEAN', {
                    'default': True,
                    'tooltip': 'ВКЛ: ровный фон + локальный рельеф '
                               '(high-pass, как Chord, но без швов). '
                               'ВЫКЛ: честная глобальная высота со всей '
                               'крупной формой / ON: flat background + '
                               'local relief; OFF: true global height'
                }),
                'tileable': ('BOOLEAN', {
                    'default': False,
                    'tooltip': 'ВКЛ: бесшовная зацикленная текстура '
                               '(периодический FFT-решатель, края '
                               'стыкуются) / ON: seamless tileable '
                               'texture (periodic FFT solver)'
                }),
                'detail': ('INT', {
                    'default': 48, 'min': 8, 'max': 256, 'step': 1,
                    'tooltip': 'Радиус фильтра в режиме relief (px на '
                               'рабочем разрешении): 32 — резкая деталь, '
                               '64-96 — мягче, больше средней формы / '
                               'High-pass radius for relief mode'
                }),
                'smooth': ('FLOAT', {
                    'default': 0.0, 'min': 0.0, 'max': 20.0, 'step': 0.5,
                    'tooltip': 'Сглаживание нормалей перед '
                               'интегрированием, 0 — выкл. / Pre-blur of '
                               'the normals (noise suppression), 0 = off'
                }),
                'normalize_mode': (['soft', 'percentile', 'minmax'], {
                    'tooltip': 'soft — перцентиль + tanh ролл-офф: нет '
                               'плоских чистых 0/255, для displacement; '
                               'percentile — жёсткий клип 0.5-99.5; '
                               'minmax — по абсолютным экстремумам / '
                               'soft = tanh roll-off (no flat spots), '
                               'percentile = hard clip, minmax = true '
                               'extremes'
                }),
                'invert': ('BOOLEAN', {
                    'default': False,
                    'tooltip': 'ВЫКЛ: светлое = выступает; ВКЛ: светлое '
                               '= углублено / OFF: bright = protruding, '
                               'ON: bright = recessed'
                }),
                'flip_red': ('BOOLEAN', {
                    'default': False,
                    'tooltip': 'Инвертировать красный канал нормал-карты '
                               '/ Invert the red channel (X)'
                }),
                'flip_green': ('BOOLEAN', {
                    'default': False,
                    'tooltip': 'Инвертировать зелёный канал (DirectX-'
                               'стиль; для Marigold не нужно — она '
                               'OpenGL) / Invert the green channel (Y, '
                               'DirectX-style)'
                }),
                'flip_blue': ('BOOLEAN', {
                    'default': False,
                    'tooltip': 'Инвертировать синий канал (если карта '
                               'кодирует z от камеры) / Invert the blue '
                               'channel (Z)'
                }),
                'work_size': ('INT', {
                    'default': 1024, 'min': 0, 'max': 8192, 'step': 64,
                    'tooltip': 'Внутреннее рабочее разрешение по длинной '
                               'стороне: 1024 — быстро и достаточно для '
                               'рельефа; 0 — родной размер кадра '
                               '(максимум деталей, медленнее) / Internal '
                               'working resolution, 0 = native size'
                }),
            },
        }

    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('height',)
    FUNCTION = 'process'
    CATEGORY = 'Rennart/Textures'
    DESCRIPTION = ('Normal map -> height map: интегрирование Пуассона '
                   '(DCT, Neumann BC) или периодический FFT для бесшовных '
                   'текстур. relief — ровный фон + локальный рельеф, '
                   'иначе честная глобальная высота. soft-нормализация '
                   'без плоских участков для displacement. '
                   'Зависимости: numpy, scipy.')

    def process(self, normal_map, relief, tileable, detail, smooth,
                normalize_mode, invert, flip_red, flip_green, flip_blue,
                work_size):
        outs = []
        for i in range(normal_map.shape[0]):
            src = np.clip(normal_map[i].cpu().numpy(), 0.0, 1.0)
            out = normals_to_height(
                src, relief=relief, tileable=tileable, detail=detail,
                smooth=smooth, invert=invert, normalize_mode=normalize_mode,
                flip_red=flip_red, flip_green=flip_green,
                flip_blue=flip_blue, work_size=work_size)
            outs.append(torch.from_numpy(out))
        return (torch.stack(outs),)


NODE_CLASS_MAPPINGS = {
    'RennartNormalsToHeight': RennartNormalsToHeight,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'RennartNormalsToHeight': 'Rennart Normals to Height',
}
