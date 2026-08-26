# ==============================================
# Rennart Offset Image
# ==============================================

import torch

class RennartOffsetImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "pixels": ("IMAGE",),
                "x_percent": ("FLOAT", {"default": 50.0, "min": 0.0, "max": 100.0, "step": 1}),
                "y_percent": ("FLOAT", {"default": 50.0, "min": 0.0, "max": 100.0, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "Rennart/Image"

    def run(self, pixels, x_percent, y_percent):
        n, y, x, c = pixels.size()
        y_shift = round(y * y_percent / 100)
        x_shift = round(x * x_percent / 100)
        return (pixels.roll((y_shift, x_shift), (1, 2)),)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartOffsetImage": RennartOffsetImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartOffsetImage": "🔄 Rennart Offset Image",
}