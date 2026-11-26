# -*- coding: utf-8 -*-
"""
================================================================================
Файл и путь : Rennart_Normals_to_Relief.py
              ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Normals_to_Relief.py
Пакет       : https://github.com/Rennart2025/ComfyUI-Rennart
Категория   : Rennart/Textures
================================================================================

[RU] Rennart Normals to Relief
------------------------------
Рендерит карту нормалей как серое «скульптурное» изображение (барельеф):
освещение Ламберта N·L на нейтральном 50%-сером фоне.

Параметры:
  * light_direction — направление виртуального света, 9 пресетов
    (front, top, top_left/right, side_left/right, bottom, bottom_left/right);
  * softness — размытие нормалей перед освещением в px, 0 = ВЫКЛ. (вся
    детализация чётких карт Marigold сохраняется; рост — «полировка»
    рельефа, уход шума и мелочи);
  * ambient — подъём теней к свету (0 = выкл.; впадины не проваливаются
    в чёрный);
  * contrast — крутизна рельефа вокруг среднего серого (1.0 = нейтрально);
  * flip_red/flip_green/flip_blue — смена конвенции карты нормалей
    (OpenGL/DirectX);
  * опциональный вход mask + mask_feather — барельеф только внутри
    области, снаружи ровный 50%-серый.

Зависимости: numpy, scipy (есть в requirements.txt пакета).

[EN] Rennart Normals to Relief
------------------------------
Renders a normal map as a gray sculptural bas-relief: Lambertian shading
(N·L) on a neutral 50%-gray background. 9 light-direction presets,
optional pre-blur of the normals (softness, 0 = off — keeps all detail
of crisp maps), ambient shadow lift, contrast around mid gray, channel
flip flags for OpenGL/DirectX conventions, and an optional mask
(relief only inside the region, flat gray outside).

Dependencies: numpy, scipy (see the pack's requirements.txt).
"""

import numpy as np
import torch
import torch.nn.functional as F
from scipy.ndimage import gaussian_filter


LIGHT_DIRECTIONS = {
    'front':        (0.0, 0.0, 1.0),
    'top':          (0.0, 0.7, 0.7),
    'top_left':     (-0.6, 0.6, 0.5),
    'top_right':    (0.6, 0.6, 0.5),
    'side_left':    (-0.9, 0.0, 0.4),
    'side_right':   (0.9, 0.0, 0.4),
    'bottom':       (0.0, -0.8, 0.6),
    'bottom_left':  (-0.5, -0.7, 0.5),
    'bottom_right': (0.5, -0.7, 0.5),
}


def _gauss(x, sigma):
    if sigma <= 0:
        return x.copy()
    return gaussian_filter(x, sigma, mode='reflect')


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


def _prep_region(region_mask, feather, H, W):
    if region_mask is None:
        return np.ones((H, W), np.float32)
    region = np.clip(region_mask.astype(np.float32), 0, 1)
    if region.shape != (H, W):
        t = torch.from_numpy(region)[None, None]
        t = F.interpolate(t, size=(H, W), mode='bilinear',
                          align_corners=False)
        region = t[0, 0].numpy()
    if feather > 0:
        region = np.clip(gaussian_filter(region, feather / 2,
                                         mode='reflect'), 0, 1)
    return region


def relief_from_normals(nm_rgb01,
                        light_direction='top_left',
                        softness=0,
                        ambient=0.0,
                        contrast=1.0,
                        flip_red=False,
                        flip_green=False,
                        flip_blue=False,
                        region_mask=None,
                        mask_feather=15):
    """Render the normal map as a gray bas-relief (Lambert N·L on a
    neutral 50%-gray background)."""
    H, W = nm_rgb01.shape[:2]
    n = _get_normals(nm_rgb01, H, W, flip_red, flip_green, flip_blue)

    if softness > 0:
        n = np.dstack([_gauss(n[:, :, c], float(softness))
                       for c in range(3)])
        norm = np.linalg.norm(n, axis=2, keepdims=True)
        n = n / np.maximum(norm, 1e-6)

    L = np.array(LIGHT_DIRECTIONS[light_direction], np.float32)
    L = L / np.linalg.norm(L)
    ndotl = (n * L).sum(axis=2)

    shade = 0.5 + 0.5 * ndotl
    if contrast != 1.0:
        shade = (shade - 0.5) * float(contrast) + 0.5
    if ambient > 0:
        shade = shade + float(ambient) * (1.0 - shade)  # lift shadows up
    shade = np.clip(shade, 0.0, 1.0).astype(np.float32)

    if region_mask is not None:
        region = _prep_region(region_mask, mask_feather, H, W)
        shade = 0.5 + (shade - 0.5) * region

    return np.dstack([shade] * 3).astype(np.float32)


class RennartNormalsToRelief:
    """Барельеф из карты нормалей (Ламберт N·L на сером фоне)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'normal_map': ('IMAGE', {
                    'tooltip': 'Карта нормалей / Normal map (RGB)'
                }),
                'light_direction': (list(LIGHT_DIRECTIONS.keys()), {
                    'tooltip': 'Направление виртуального света '
                               '(9 пресетов) / Light direction preset'
                }),
                'softness': ('INT', {
                    'default': 0, 'min': 0, 'max': 200, 'step': 1,
                    'tooltip': 'Размытие нормалей перед освещением (px): '
                               '0 — выкл., вся детализация карты; рост — '
                               '«полировка» рельефа / Pre-blur of the '
                               'normals, 0 = off'
                }),
                'ambient': ('FLOAT', {
                    'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.05,
                    'tooltip': 'Подъём теней к свету: 0 — выкл.; впадины '
                               'не проваливаются в чёрный / Shadow lift, '
                               '0 = off'
                }),
                'contrast': ('FLOAT', {
                    'default': 1.0, 'min': 0.0, 'max': 2.0, 'step': 0.05,
                    'tooltip': 'Крутизна рельефа вокруг среднего серого '
                               '(1.0 — нейтрально) / Relief contrast '
                               'around mid gray'
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
            },
            'optional': {
                'mask': ('MASK', {
                    'tooltip': 'Если задана — барельеф только внутри '
                               'области, снаружи ровный 50%-серый / '
                               'Relief only inside the mask, flat gray '
                               'outside'
                }),
                'mask_feather': ('INT', {
                    'default': 15, 'min': 0, 'max': 150, 'step': 1,
                    'tooltip': 'Растушёвка края области (px) / Mask edge '
                               'feather (px)'
                }),
            },
        }

    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('relief',)
    FUNCTION = 'process'
    CATEGORY = 'Rennart/Textures'
    DESCRIPTION = ('Скульптурный барельеф из normal map: освещение '
                   'Ламберта на сером фоне, 9 пресетов света, softness '
                   '(0 = выкл.), ambient, contrast, flip-флаги каналов, '
                   'опциональная маска области. Зависимости: numpy, scipy.')

    def process(self, normal_map, light_direction, softness, ambient,
                contrast, flip_red, flip_green, flip_blue,
                mask=None, mask_feather=15):
        outs = []
        for i in range(normal_map.shape[0]):
            src = np.clip(normal_map[i].cpu().numpy(), 0.0, 1.0)
            m = None
            if mask is not None:
                mi = np.squeeze(mask[i].cpu().numpy())
                if mi.ndim == 2:
                    m = mi.astype(np.float32)
            out = relief_from_normals(
                src, light_direction=light_direction, softness=softness,
                ambient=ambient, contrast=contrast,
                flip_red=flip_red, flip_green=flip_green,
                flip_blue=flip_blue, region_mask=m,
                mask_feather=mask_feather)
            outs.append(torch.from_numpy(out))
        return (torch.stack(outs),)


NODE_CLASS_MAPPINGS = {
    'RennartNormalsToRelief': RennartNormalsToRelief,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'RennartNormalsToRelief': 'Rennart Normals to Relief',
}
