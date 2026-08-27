"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Load_Image.py
Категория: Rennart/Image
"""

# ==============================================
# Rennart Image Load (с выходами ширины и высоты)
# ==============================================

import os
import hashlib
import numpy as np
import torch
from PIL import Image, ImageSequence, ImageOps
import folder_paths
import node_helpers

class RennartImageLoad:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {"required": {"image": (sorted(files), {"image_upload": True})}}

    CATEGORY = "Rennart/Image"
    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT", "STRING")
    RETURN_NAMES = ("image", "mask", "width", "height", "filename")
    FUNCTION = "load_image"

    def load_image(self, image):
        image_path = folder_paths.get_annotated_filepath(image)
        filename, _ = os.path.splitext(os.path.basename(image_path))
        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None
        excluded_formats = ['MPO']

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)
            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            image_rgb = i.convert("RGB")

            if len(output_images) == 0:
                w, h = image_rgb.size

            if image_rgb.size[0] != w or image_rgb.size[1] != h:
                continue

            img_np = np.array(image_rgb).astype(np.float32) / 255.0
            output_images.append(torch.from_numpy(img_np)[None,])

            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            elif i.mode == 'P' and 'transparency' in i.info:
                mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                # Используем реальные размеры изображения
                mask = torch.zeros((h, w), dtype=torch.float32, device="cpu")
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1 and img.format not in excluded_formats:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        return (output_image, output_mask, w, h, filename)

    @classmethod
    def IS_CHANGED(s, image):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(s, image):
        if not folder_paths.exists_annotated_filepath(image):
            return f"Invalid image file: {image}"
        return True


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartImageLoad": RennartImageLoad,
}

NODE_DISPLAY_NAME_MAPPINGS = {
     "RennartImageLoad": "🖼️ Rennart Load Image",
}