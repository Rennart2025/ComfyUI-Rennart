"""Rennart Image Comparer node for ComfyUI.

Compares two images (or two batches) interactively in the UI.
Backend saves both inputs as temp previews and hands them to the frontend;
all comparison logic (Slider / Blink / Difference) lives in
web/js/Rennart_Image_Comparer.js.

Файл и путь: ComfyUI/custom_nodes/ComfyUI-Rennart/Rennart_Image_Comparer.py
Категория: Rennart/Image
"""

from nodes import PreviewImage


class RennartImageComparer(PreviewImage):
    """A node that compares two images in the UI (Slider / Blink / Difference)."""

    @classmethod
    def INPUT_TYPES(cls):  # pylint: disable=invalid-name
        return {
            "required": {},
            "optional": {
                "image_a": ("IMAGE",),
                "image_b": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "compare_images"
    CATEGORY = "Rennart/Image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Compares two images on top of each other. "
        "Modes: Slider (hover split), Blink (click toggles A/B), "
        "Difference (overlay with difference blending)."
    )

    def compare_images(self,
                       image_a=None,
                       image_b=None,
                       filename_prefix="rennart.compare.",
                       prompt=None,
                       extra_pnginfo=None):

        result = {"ui": {"a_images": [], "b_images": []}}

        if image_a is not None and len(image_a) > 0:
            result["ui"]["a_images"] = self.save_images(
                image_a, filename_prefix + "a_", prompt, extra_pnginfo
            )["ui"]["images"]

        if image_b is not None and len(image_b) > 0:
            result["ui"]["b_images"] = self.save_images(
                image_b, filename_prefix + "b_", prompt, extra_pnginfo
            )["ui"]["images"]

        # Сквозной выход: пробрасываем A, либо B, если A не подключён.
        result["result"] = (image_a if image_a is not None else image_b,)
        return result


NODE_CLASS_MAPPINGS = {
    "RennartImageComparer": RennartImageComparer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartImageComparer": "🔍 Rennart Image Comparer",
}
