"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Date_String.py
Категория: Rennart/Utils
"""

# ==============================================
# Rennart Date String
# ==============================================

import datetime

class RennartDateString:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "format": ("STRING", {"default": "%Y-%m-%d", "multiline": False}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, format):
        return datetime.datetime.now().timestamp()

    CATEGORY = "Rennart/Utils"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("date_string",)
    FUNCTION = "get_date"

    def get_date(self, format):
        now = datetime.datetime.now()
        return (now.strftime(format),)

# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartDateString": RennartDateString,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartDateString": "📅 Rennart Date String",
}