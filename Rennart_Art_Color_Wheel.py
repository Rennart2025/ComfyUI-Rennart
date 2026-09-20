import json
import colorsys


class RennartArtColorWheel:
    """
    Color Harmony Wheel node.

    Вся "тяжёлая" логика (рисование круга, перетаскивание маркеров, расчёт
    HEX по H/S/V, механика гармонии/каскада brightness) живёт в JS-виджете
    (web/js/rennart_art_color_wheel.js). Python-часть только:
      - объявляет входы (тип палитры, количество цветов, два скрытых
        текстовых поля для обмена данными с JS);
      - парсит JSON со списком HEX-цветов, который записал JS-виджет;
      - отдаёт цвета на выход ноды в нескольких форматах.

    Скрытые поля:
      - wheel_data — JSON-список HEX-кодов текущей палитры (используется
        Python для формирования выходов ноды).
      - node_data  — JSON с полным состоянием круга (маркеры, поворот
        пучка лучей, тип палитры, количество цветов), которое JS
        использует, чтобы восстановить круг после перезагрузки страницы
        или переключения вкладки ComfyUI. Python это поле не читает —
        оно нужно только для того, чтобы round-trip'ом попасть в
        workflow-файл через сериализацию виджетов ноды.

    Оба поля скрыты от пользователя на уровне JS (widget.type = "hidden"),
    а не через опции INPUT_TYPES — ComfyUI не имеет специального ключа
    "hidden" внутри options словаря, поэтому здесь он не нужен.
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
                # Скрытые (спрятанные JS-виджетом) текстовые поля-хранилища.
                "wheel_data": ("STRING", {"default": "[]", "multiline": False}),
                "node_data": ("STRING", {"default": "{}", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("colors_csv", "colors", "ideogram_json")
    OUTPUT_IS_LIST = (False, True, False)
    FUNCTION = "get_colors"
    CATEGORY = "Rennart/Color"

    def get_colors(self, palette_type, color_count, wheel_data, node_data="{}"):
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


NODE_CLASS_MAPPINGS = {
    "RennartArtColorWheel": RennartArtColorWheel,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartArtColorWheel": "Rennart Art Color Wheel",
}
