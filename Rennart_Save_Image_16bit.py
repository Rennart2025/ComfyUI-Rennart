# -*- coding: utf-8 -*-
"""
================================================================================
Файл и путь : Rennart_Save_Image_16bit.py
              ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Save_Image_16bit.py
Пакет       : https://github.com/Rennart2025/ComfyUI-Rennart
Категория   : Rennart/Image
================================================================================

[RU] Rennart Save Image 16bit
-----------------------------
Сохранение изображений в 16-битных форматах без потери градаций:
  * PNG 16-bit (grayscale или RGB, уровень сжатия 0-9, метаданные
    workflow встраиваются в файл — ComfyUI их читает);
  * TIFF 16-bit (grayscale или RGB, сжатие: lzw / deflate / packbits /
    без сжатия; workflow рядом отдельным .json).

Зачем: внутри ComfyUI изображения живут в float32, и лишь сохранение
квантует их в 8 бит (256 градаций). Для height/displacement/normal-карт
в 3D-графике этого мало — 16 бит (65536 градаций) убирают «лесенки»
на плавных градиентах. Конвертер 8->16 бит бессмысленен (градации не
восстановить), поэтому сохранять в 16 бит нужно прямо из графа.

color_mode:
  * auto — если все каналы совпадают (типично для height/normal-gray),
    пишется grayscale 16-bit (меньше файл, универсально читается);
  * grayscale — принудительно монохром (берётся первый канал);
  * rgb — принудительно цветной 16-bit.

Имя файла всегда с номером: префикс_001.png, префикс_002.png...;
batch сохраняется пачкой с тем же правилом. Опционально — подпапка
с датой (ГГГГ-ММ-ДД) и перезапись существующих файлов.

Зависимости: numpy; для TIFF — tifffile (сжатия lzw/packbits требуют
также imagecodecs; deflate и none работают без него) — всё есть в
requirements.txt пакета. PNG 16-bit пишется собственным записывателем
(zlib), внешних зависимостей не требует.

[EN] Rennart Save Image 16bit
-----------------------------
16-bit image saver (PNG 16-bit and TIFF 16-bit, grayscale or RGB) so
height/displacement/normal maps keep their full float32 precision from
the ComfyUI graph: 65536 levels instead of 256 — no banding on smooth
gradients. PNG is written by a built-in writer (zlib, compression 0-9,
workflow metadata embedded as iTXt chunks, readable by ComfyUI); TIFF
uses tifffile with selectable compression (lzw/deflate/packbits/none)
and a sidecar .json workflow. color_mode auto stores grayscale when all
channels are identical (typical for height maps). Files are numbered
prefix_001, prefix_002...; batch saving, dated subfolder and overwrite
options included.

Dependencies: numpy; TIFF requires tifffile (lzw/packbits also need
imagecodecs; deflate and none work without it) — see requirements.txt.
"""

import os
import re
import json
import struct
import zlib
from datetime import datetime

import numpy as np
import torch

try:
    import folder_paths
    _OUTPUT_DIR = folder_paths.get_output_directory()
except ImportError:  # standalone testing outside ComfyUI
    _OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output_test')


# ---------------------------------------------------------------------
# 16-bit PNG writer (grayscale / RGB, no external dependencies)
# ---------------------------------------------------------------------

def _png_chunk(tag, payload):
    return (struct.pack('>I', len(payload)) + tag + payload +
            struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _png_itxt(keyword, text):
    """iTXt chunk: keyword + uncompressed UTF-8 text (ComfyUI-readable)."""
    payload = (keyword.encode('latin-1') + b'\x00' + b'\x00' + b'\x00' +
               b'\x00' + b'\x00' + text.encode('utf-8'))
    return _png_chunk(b'iTXt', payload)


def save_png16(filepath, arr16, compress_level=6, texts=None):
    """Write a 16-bit PNG. arr16: HxW (grayscale) or HxWx3 (RGB) uint16.
    Scanlines are written big-endian with filter type 0 (none) — lossless
    by construction; compress_level is the zlib level 0-9."""
    if arr16.ndim == 2:
        color_type = 0
        h, w = arr16.shape
    else:
        color_type = 2
        h, w = arr16.shape[:2]
    be = np.ascontiguousarray(arr16.astype('>u2'))
    raw = b''.join(b'\x00' + be[i].tobytes() for i in range(h))
    ihdr = struct.pack('>IIBBBBB', w, h, 16, color_type, 0, 0, 0)
    parts = [b'\x89PNG\r\n\x1a\n', _png_chunk(b'IHDR', ihdr)]
    for key, value in (texts or {}).items():
        parts.append(_png_itxt(key, value))
    parts.append(_png_chunk(b'IDAT', zlib.compress(raw, compress_level)))
    parts.append(_png_chunk(b'IEND', b''))
    with open(filepath, 'wb') as f:
        f.write(b''.join(parts))


def save_tiff16(filepath, arr16, compression='lzw'):
    """Write a 16-bit TIFF via tifffile. arr16: HxW or HxWx3 uint16."""
    try:
        import tifffile
    except ImportError as e:
        raise ImportError(
            '[Rennart] Для сохранения TIFF 16-bit нужен пакет tifffile: '
            'pip install tifffile (уже прописан в requirements.txt '
            'пакета) / TIFF 16-bit requires the tifffile package') from e
    photometric = 'minisblack' if arr16.ndim == 2 else 'rgb'
    comp = None if compression == 'none' else compression
    tifffile.imwrite(filepath, arr16, photometric=photometric,
                     compression=comp, metadata=None)


# ---------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------

class RennartSaveImage16bit:
    """16-bit PNG/TIFF saver. Структура путей/нумерации — по образцу
    AGSoft Save Image. Подробности — в шапке файла."""

    def __init__(self):
        self.output_dir = _OUTPUT_DIR
        self.type = 'output'

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'images': ('IMAGE', {
                    'tooltip': 'Изображение(я) для сохранения / '
                               'Image(s) to save'
                }),
                'filename_prefix': ('STRING', {
                    'default': 'Rennart16',
                    'tooltip': 'Базовое имя файла без расширения / '
                               'Base filename without extension'
                }),
                'output_path': ('STRING', {
                    'default': '',
                    'tooltip': 'Опциональная подпапка в output '
                               '(например, "textures") / Optional '
                               'subdirectory in the output folder'
                }),
                'create_dated_subfolder': ('BOOLEAN', {
                    'default': False, 'label_on': 'Yes', 'label_off': 'No',
                    'tooltip': 'Создать подпапку с датой ГГГГ-ММ-ДД / '
                               'Create YYYY-MM-DD subfolder'
                }),
                'image_format': (['png', 'tiff'], {
                    'default': 'png',
                    'tooltip': 'Формат: PNG 16-bit или TIFF 16-bit / '
                               'Output format: PNG 16-bit or TIFF 16-bit'
                }),
                'color_mode': (['auto', 'grayscale', 'rgb'], {
                    'default': 'auto',
                    'tooltip': 'auto — grayscale, если все каналы '
                               'совпадают (height-карты), иначе RGB; '
                               'grayscale — принудительно монохром; '
                               'rgb — принудительно цвет / auto stores '
                               'grayscale when all channels are identical'
                }),
                'png_compression': ('INT', {
                    'default': 6, 'min': 0, 'max': 9, 'step': 1,
                    'display': 'slider',
                    'tooltip': 'Сжатие PNG: 0 — без сжатия (быстро, '
                               'большие файлы), 6 — баланс, 9 — '
                               'максимум (медленно) / PNG compression: '
                               '0 = none (fast), 9 = maximum (slow)'
                }),
                'tiff_compression': (['deflate', 'lzw', 'packbits',
                                      'none'], {
                    'default': 'deflate',
                    'tooltip': 'Сжатие TIFF (все — без потерь): deflate '
                               '(zip) — компактно, работает без '
                               'доп. пакетов; lzw — классика для '
                               '3D-софта; packbits — слабое, читается '
                               'везде (lzw/packbits требуют пакет '
                               'imagecodecs); none — без сжатия / TIFF '
                               'compression, all lossless'
                }),
                'overwrite_existing': ('BOOLEAN', {
                    'default': False, 'label_on': 'Yes', 'label_off': 'No',
                    'tooltip': 'Перезаписывать существующие файлы с тем '
                               'же именем / Overwrite existing files'
                }),
                'embed_workflow': ('BOOLEAN', {
                    'default': True, 'label_on': 'Yes', 'label_off': 'No',
                    'tooltip': 'PNG: метаданные встраиваются в файл '
                               '(читаются ComfyUI). TIFF: workflow рядом '
                               'отдельным .json / PNG: embed metadata; '
                               'TIFF: sidecar .json workflow'
                }),
            },
            'hidden': {
                'prompt': 'PROMPT',
                'extra_pnginfo': 'EXTRA_PNGINFO',
            },
        }

    RETURN_TYPES = ('IMAGE', 'STRING', 'STRING')
    RETURN_NAMES = ('images', 'saved_paths', 'saved_dir')
    FUNCTION = 'process'
    OUTPUT_NODE = True
    CATEGORY = 'Rennart/Image'
    DESCRIPTION = ('Сохранение в PNG 16-bit и TIFF 16-bit (grayscale/RGB) '
                   'без потери градаций: для height/displacement/normal '
                   'карт. Сжатие TIFF на выбор, workflow — в метаданных '
                   'PNG или рядом .json для TIFF. / 16-bit PNG/TIFF saver '
                   'for height/displacement maps.')

    # ------------------------- пути и имена -------------------------

    def process_output_path(self, user_path):
        try:
            if not user_path:
                return self.output_dir
            try:
                dated_path = datetime.now().strftime(user_path)
            except Exception:
                dated_path = user_path
            dated_path = dated_path.replace('/', os.sep).replace(
                '\\', os.sep)
            if os.path.isabs(dated_path):
                return os.path.normpath(dated_path)
            return os.path.normpath(os.path.join(self.output_dir,
                                                 dated_path))
        except Exception as e:
            print(f'[Rennart] Path processing error / Ошибка пути: {e}')
            return None

    def get_next_filename(self, directory, base_name, extension,
                          overwrite=False, is_batch=False,
                          batch_index=None):
        """Имя файла ВСЕГДА с номером: 001, 002, 003..."""
        try:
            if overwrite:
                idx = batch_index if (is_batch and batch_index) else 1
                return os.path.join(
                    directory, f'{base_name}_{idx:03d}.{extension}')

            if is_batch and batch_index is not None:
                base_with_index = f'{base_name}_{batch_index:03d}'
                pattern = re.compile(
                    rf'^{re.escape(base_with_index)}_(\d+)\.'
                    rf'{re.escape(extension)}$')
                max_num = 0
                if os.path.exists(directory):
                    for f in os.listdir(directory):
                        m = pattern.match(f)
                        if m:
                            max_num = max(max_num, int(m.group(1)))
                filename = (f'{base_with_index}_{max_num + 1:03d}'
                            f'.{extension}')
                return os.path.join(directory, filename)

            max_num = 0
            pattern = re.compile(rf'^{re.escape(base_name)}_(\d+)\.'
                                 rf'{re.escape(extension)}$')
            if os.path.exists(directory):
                for f in os.listdir(directory):
                    m = pattern.match(f)
                    if m:
                        max_num = max(max_num, int(m.group(1)))
            return os.path.join(
                directory, f'{base_name}_{max_num + 1:03d}.{extension}')

        except Exception as e:
            print(f'[Rennart] Filename generation error / Ошибка имени: '
                  f'{e}')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return os.path.join(directory,
                                f'{base_name}_{timestamp}.{extension}')

    # ------------------------- workflow -------------------------

    def save_workflow_json_file(self, image_path, prompt, extra_pnginfo):
        """Sidecar .json рядом с TIFF (как у AGSoft для jpg/webp)."""
        try:
            if extra_pnginfo and 'workflow' in extra_pnginfo:
                workflow_data = extra_pnginfo['workflow']
            else:
                workflow_data = {'prompt': prompt or {}}
            workflow_data.setdefault('extra', {})
            workflow_data['extra']['save_timestamp'] = \
                datetime.now().isoformat()
            workflow_data['extra']['image_file'] = os.path.basename(
                image_path)
            workflow_data['extra']['saved_by'] = \
                'Rennart Save Image 16bit'
            json_path = os.path.splitext(image_path)[0] + '.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, ensure_ascii=False, indent=2)
            return json_path
        except Exception as e:
            print(f'[Rennart] Workflow JSON save failed / Ошибка JSON: '
                  f'{e}')
            return ''

    # ------------------------- сохранение -------------------------

    def to_uint16(self, img_hwc, color_mode):
        """HxWxC float [0,1] -> HxW или HxWx3 uint16."""
        a = np.clip(img_hwc, 0.0, 1.0).astype(np.float32)
        if a.ndim == 2:
            a = a[..., None]
        if a.shape[-1] == 1:
            a = np.repeat(a, 3, axis=-1)
        a = a[..., :3]  # альфа отбрасываем
        if color_mode == 'grayscale' or (
                color_mode == 'auto' and
                np.array_equal(a[..., 0], a[..., 1]) and
                np.array_equal(a[..., 1], a[..., 2])):
            a = a[..., 0]
        return np.round(a * 65535.0).astype(np.uint16)

    def save_single_image(self, image_tensor, save_dir, base_filename,
                          image_format, color_mode, png_compression,
                          tiff_compression, overwrite, embed_workflow,
                          prompt=None, extra_pnginfo=None,
                          is_batch=False, batch_index=None):
        json_path = ''
        try:
            os.makedirs(save_dir, exist_ok=True)
            extension = 'png' if image_format == 'png' else 'tif'
            filepath = self.get_next_filename(
                save_dir, base_filename, extension, overwrite,
                is_batch, batch_index)

            arr16 = self.to_uint16(image_tensor.cpu().numpy(), color_mode)

            if image_format == 'png':
                texts = {}
                if embed_workflow:
                    if prompt:
                        texts['prompt'] = json.dumps(prompt)
                    if extra_pnginfo:
                        for key, value in extra_pnginfo.items():
                            try:
                                texts[key] = json.dumps(value)
                            except Exception:
                                pass
                level = min(9, max(0, int(png_compression)))
                save_png16(filepath, arr16, compress_level=level,
                           texts=texts)
                kind = 'grayscale' if arr16.ndim == 2 else 'RGB'
                print(f'[Rennart] PNG 16-bit ({kind}) saved: '
                      f'{os.path.basename(filepath)} '
                      f'(compression: {level}/9)')
            else:
                save_tiff16(filepath, arr16, compression=tiff_compression)
                if embed_workflow and (prompt or extra_pnginfo):
                    json_path = self.save_workflow_json_file(
                        filepath, prompt, extra_pnginfo)
                kind = 'grayscale' if arr16.ndim == 2 else 'RGB'
                print(f'[Rennart] TIFF 16-bit ({kind}) saved: '
                      f'{os.path.basename(filepath)} '
                      f'(compression: {tiff_compression})')

            return filepath, json_path

        except Exception as e:
            # убираем недописанный (битый) файл, если он успел создаться
            try:
                if 'filepath' in locals() and os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            print(f'[Rennart] Image save failed / Ошибка сохранения: {e}')
            return '', ''

    # ------------------------- основной метод -------------------------

    def process(self, images, filename_prefix, output_path,
                create_dated_subfolder, image_format, color_mode,
                png_compression, tiff_compression, overwrite_existing,
                embed_workflow, prompt=None, extra_pnginfo=None):
        saved_paths = []

        base_save_dir = self.process_output_path(output_path)
        if base_save_dir is None:
            base_save_dir = self.output_dir
        if create_dated_subfolder:
            base_save_dir = os.path.join(
                base_save_dir, datetime.now().strftime('%Y-%m-%d'))

        batch_size = images.shape[0]
        is_batch = batch_size > 1
        for i in range(batch_size):
            saved_path, _ = self.save_single_image(
                image_tensor=images[i],
                save_dir=base_save_dir,
                base_filename=filename_prefix,
                image_format=image_format,
                color_mode=color_mode,
                png_compression=png_compression,
                tiff_compression=tiff_compression,
                overwrite=overwrite_existing,
                embed_workflow=embed_workflow,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                is_batch=is_batch,
                batch_index=i + 1 if is_batch else None)
            if saved_path:
                saved_paths.append(saved_path)

        paths_string = ','.join(saved_paths) if saved_paths else ''
        return (images, paths_string, base_save_dir)


NODE_CLASS_MAPPINGS = {
    'RennartSaveImage16bit': RennartSaveImage16bit,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'RennartSaveImage16bit': '💾Rennart Save Image 16bit',
}
