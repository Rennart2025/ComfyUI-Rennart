import json
import colorsys


class RennartArtColorWheel:
    """
    Color Harmony Wheel node.

    Вся "тяжёлая" логика (рисование круга, перетаскивание маркеров,
    подсчёт HEX по H/S/V) живёт в JS-виджете (web/js/rennart_art_color_wheel.js).
    Python-часть только:
      - объявляет входы (тип палитры, количество цветов, скрытое поле с
        данными от JS-виджета);
      - парсит JSON со списком HEX-цветов, который записал JS-виджет;
      - отдаёт цвета на выход ноды.

    Логика "гармонии" (жёсткая связка маркеров лучами + расчёт HEX по
    художественному RYB-кругу) полностью живёт в JS-виджете. На бэкенде она
    не дублируется — Python лишь читает уже посчитанный список HEX.
    Таблица уровней "эхо" (saturation/brightness для повторных цветов на
    том же луче) в JS сейчас содержит только 2 подтверждённых уровня
    (66/67 и 50/50) и временную экстраполяцию дальше — актуальные значения
    можно будет просто заменить в JS, без изменений здесь.
    """

    PALETTE_TYPES = [
        "Complementary",
        "Analogous",
        "Triad",
        "Split-Complementary",
        "Double Split-Complementary",
        "Tetradic",
        "Monochromatic",
        "Custom",
    ]

    # Минимальное количество цветов для каждого типа палитры.
    # Используется JS-виджетом, чтобы ограничивать слайдер color_count,
    # и здесь как страховка на бэкенде.
    # Square убран — он дублировал Tetradic (оба давали 4 луча через 90°).
    MIN_COLORS = {
        "Complementary": 2,
        "Analogous": 3,
        "Triad": 3,
        "Split-Complementary": 3,
        "Double Split-Complementary": 5,
        "Tetradic": 4,
        "Monochromatic": 2,
        "Custom": 2,
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "palette_type": (cls.PALETTE_TYPES, {"default": "Triad"}),
                "color_count": ("INT", {"default": 3, "min": 2, "max": 10, "step": 1}),
                # Скрытое (спрятанное JS-виджетом) текстовое поле-хранилище.
                # JS кладёт сюда JSON-список HEX-кодов, например: ["#FF0000", "#00FFFF"]
                "wheel_data": ("STRING", {"default": "[]", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("colors_csv", "colors", "ideogram_json")
    OUTPUT_IS_LIST = (False, True, False)
    FUNCTION = "get_colors"
    CATEGORY = "Rennart/Color"

    def get_colors(self, palette_type, color_count, wheel_data):
        min_count = self.MIN_COLORS.get(palette_type, 2)
        color_count = max(min_count, min(10, color_count))

        colors = self._parse_wheel_data(wheel_data)

        if len(colors) >= color_count:
            colors = colors[:color_count]
        else:
            # Данных от виджета не хватает (например, нода запущена без
            # предварительного открытия UI) — подстрахуемся равномерной
            # раскладкой по кругу, чтобы нода не падала.
            colors = self._fallback_colors(color_count)

        colors_csv = ", ".join(colors)
        # Без внешних {} нарочно — пользователь подставляет эту строку внутрь
        # своего уже готового JSON/текста, где фигурные скобки уже есть.
        # json.dumps(colors) даёт корректно экранированный список в кавычках.
        ideogram_json = '"color_palette": ' + json.dumps(colors, ensure_ascii=False)
        return (colors_csv, colors, ideogram_json)

    @staticmethod
    def _parse_wheel_data(wheel_data):
        try:
            data = json.loads(wheel_data) if wheel_data else []
        except (json.JSONDecodeError, TypeError):
            data = []

        if not isinstance(data, list):
            return []

        result = []
        for item in data:
            if isinstance(item, str) and item.startswith("#") and len(item) in (4, 7):
                result.append(item.upper())
        return result

    @staticmethod
    def _fallback_colors(count):
        colors = []
        for i in range(count):
            hue = i / count
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            colors.append(
                "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))
            )
        return colors

    # TODO: когда придут формулы гармонии, добавить сюда (или в JS)
    # функцию вида:
    #   def apply_harmony(self, palette_type, root_hue) -> list[hue]
    # которая по типу палитры и опорному (root) маркеру считает углы
    # остальных маркеров на круге.


NODE_CLASS_MAPPINGS = {
    "RennartArtColorWheel": RennartArtColorWheel,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartArtColorWheel": "Rennart Art Color Wheel",
}
