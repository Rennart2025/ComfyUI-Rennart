import os
import importlib

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Сканируем текущую папку (там, где лежит __init__.py)
current_folder = os.path.dirname(__file__)

for filename in os.listdir(current_folder):
    if filename.endswith(".py") and not filename.startswith("_") and filename != "__init__.py":
        module_name = filename[:-3]  # Убираем расширение .py
        try:
            mod = importlib.import_module(f".{module_name}", package=__package__)
            
            if hasattr(mod, "NODE_CLASS_MAPPINGS"):
                NODE_CLASS_MAPPINGS.update(mod.NODE_CLASS_MAPPINGS)
            if hasattr(mod, "NODE_DISPLAY_NAME_MAPPINGS"):
                NODE_DISPLAY_NAME_MAPPINGS.update(mod.NODE_DISPLAY_NAME_MAPPINGS)
        except Exception as e:
            print(f"[Rennart] ⚠️ Не удалось загрузить {module_name}: {e}")

WEB_DIRECTORY = "web"   # или "./web" — как вам удобнее

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]