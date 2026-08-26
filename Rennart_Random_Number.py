# ==============================================
# Rennart Date String
# ==============================================

# ==============================================
# Rennart Random Number (с округлением и выходом string)
# ==============================================

import random
import hashlib

class RennartRandomNumber:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "number_type": (["integer", "float", "bool"], {"default": "integer"}),
                "minimum": ("FLOAT", {"default": 0, "min": -1e12, "max": 1e12, "step": 0.1}),
                "maximum": ("FLOAT", {"default": 100, "min": -1e12, "max": 1e12, "step": 0.1}),
                "enable_rounding": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Yes",
                    "label_off": "No",
                    "tooltip": "Включить округление числа"
                }),
                "round_to": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 1000,
                    "step": 1,
                    "tooltip": "Шаг округления (1, 5, 10, 16, 64 и т.д.)"
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "step": 1}),
            },
        }

    CATEGORY = "Rennart/Utils"

    RETURN_TYPES = ("INT", "FLOAT", "NUMBER", "STRING", "INT")
    RETURN_NAMES = ("int", "float", "number", "string", "seed")
    FUNCTION = "generate"

    def generate(self, number_type, minimum, maximum, enable_rounding, round_to, seed):
        random.seed(seed)
        
        # Генерируем случайное число
        if number_type == "integer":
            value = random.randint(int(minimum), int(maximum))
        elif number_type == "float":
            value = random.uniform(minimum, maximum)
        else:  # bool
            value = 1.0 if random.random() > 0.5 else 0.0
        
        # Сохраняем исходный seed для вывода
        seed_out = seed
        
        # Применяем округление, если включено
        if enable_rounding:
            if number_type == "bool":
                # Для bool округление не имеет смысла
                pass
            else:
                # Округляем до ближайшего кратного round_to
                if number_type == "integer":
                    rounded = int(round(value / round_to) * round_to)
                    value_float = float(rounded)
                    value_int = rounded
                else:  # float
                    rounded = round(value / round_to) * round_to
                    value_float = float(rounded)
                    value_int = int(rounded)
                return (value_int, value_float, rounded, str(rounded), seed_out)
        
        # Без округления
        if number_type == "integer":
            return (value, float(value), value, str(value), seed_out)
        elif number_type == "float":
            return (int(value), value, value, str(value), seed_out)
        else:  # bool
            bool_value = 1 if value else 0
            return (bool_value, float(value), value, str(value), seed_out)

    @classmethod
    def IS_CHANGED(cls, seed, **kwargs):
        m = hashlib.sha256()
        m.update(str(seed).encode())
        return m.digest().hex()


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "Rennart Random Number": RennartRandomNumber,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Rennart Random Number": "🎲 Rennart Random Number",
}
