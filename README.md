# ComfyUI-Rennart Custom Nodes for ComfyUI
Set of custom nodes for ComfyUI

## Installation

install on ComfyUI-Manager, search ComfyUI-Rennart and install

## List of nodes
Rennart_Art_Color_Wheel<br>
Rennart_Date_String<br>
Rennart_Gradients<br>
Rennart_Image_Crop<br>
Rennart_Image_Size<br>
Rennart_Load_Image<br>
Rennart_Offset_Image<br>
Rennart_Palette_Extractor<br>
Rennart_Palette_Preview<br>
Rennart_Random_Number<br>
Rennart_Video_Crossfade<br>

## How To Use

## 🎨 Rennart Art Color Wheel (Beta-version)

An interactive color-wheel node built around a real artistic (RYB) hue wheel — the same "red opposite green" wheel painters use, not a plain HSB circle. Instead of picking one color and computing a palette, you work directly with color markers locked onto harmony rays right on the node.

- Pick a Harmony Type: Complementary, Analogous, Triad, Split-Complementary, Double Split-Complementary, Tetradic, Monochromatic, or fully free Custom — each type locks its markers onto rays at the correct classic angles (e.g. 180° for Complementary, 120° for Triad).
- Drag Markers on the Wheel: rotate the whole ray bundle by dragging any marker around the circle, or pull a marker along its ray to shift saturation — the main color's saturation move mirrors across the whole palette, bouncing off the 0%/100% edges instead of clipping.
- Fine-Tune with H/S/B Sliders: every swatch below the wheel has its own Hue/Saturation/Brightness sliders with live numeric readouts, so you can nudge overlapping markers apart or dial in an exact shade.
- Built-in Brightness Cascade: changing the main color's brightness shifts the whole palette together, with an automatic "jump" back into a bright/dark range once a shade gets too close to black or white — keeping generated palettes visually harmonious instead of washing out.
- Flexible Output: get the palette as a HEX list/CSV string, or as a ready-to-embed "color_palette": [...] JSON fragment (ideogram_json) for dropping straight into Ideogram-style prompts.

Pro Tip: drag any secondary marker's brightness independently and the node automatically switches to Custom mode, so you can freely break the harmony rules on individual colors without losing the rest of the setup.

Интерактивная нода с цветовым кругом, построенным на настоящем художественном (RYB) круге — том самом, где напротив красного находится зелёный, а не циановый, как в обычном HSB-круге. Вместо выбора одного цвета и расчёта палитры «за кадром» вы работаете прямо с маркерами цветов, жёстко посаженными на лучи гармонии, прямо на самой ноде.

- Выбор типа гармонии: Complementary, Analogous, Triad, Split-Complementary, Double Split-Complementary, Tetradic, Monochromatic, либо полностью свободный Custom — каждый тип фиксирует маркеры на лучах под классическими углами (например, 180° для Complementary, 120° для Triad).
- Перетаскивание маркеров по кругу: двигая любой маркер по дуге, вращаете весь пучок лучей целиком; двигая вдоль луча — меняете saturation, причём движение основного цвета зеркально сдвигает saturation всей палитры, «отскакивая» от границ 0%/100%, а не обрезаясь.
- Точная настройка слайдерами H/S/B: под кругом у каждого образца свои слайдеры Hue/Saturation/Brightness с цифровым значением рядом — удобно раздвинуть слипшиеся на круге маркеры или подобрать точный оттенок.
- Встроенный "переброс" brightness: изменение яркости основного цвета сдвигает всю палитру разом, а при приближении какого-то цвета к чёрному или белому происходит автоматический "переброс" в другой диапазон — палитра остаётся художественно гармоничной, а не вымывается в один тон.
- Гибкий вывод: HEX-список/CSV-строка, либо готовый для вставки JSON-фрагмент "color_palette": [...] (ideogram_json) — можно сразу подставлять в промпты в стиле Ideogram.

Лайфхак: двигая brightness любого вторичного маркера независимо от остальных, нода сама переключается в режим Custom — можно точечно нарушить правила гармонии для одного цвета, не теряя всю остальную настройку.
<img width="897" height="1227" alt="2026-09-08_05-58-35" src="https://github.com/user-attachments/assets/66e50d83-5ab7-4f40-8487-a4b1dabc80a3" />

<details>
<summary>🎨 Rennart Palette Extractor </summary>
  
## 🎨 Rennart Palette Extractor

Extracts a dominant color palette from a reference image and returns it as a JSON fragment ready to splice into a generation prompt, plus a visual swatch strip preview.

Five extraction strategies are available from a single dropdown, so you can pick the one that fits the image — from strict dominant-color extraction to aggressive rare-accent detection:

|Method	|What it does	|Best for
|---|---|---|
|K-Means (Original)	|Plain sklearn KMeans, clusters ordered by population	|General-purpose, balanced palettes
|Weighted Frequency	|KMeans with per-pixel weights that favour rare colors	|Small bright accents on busy backgrounds
|Farthest Point Sampling	|Greedily picks the most different colors	|Maximally diverse palettes
|Two-Pass Background + Accent	|KMeans for the background, then a second pass over the worst-explained pixels	|Landscapes and cityscapes with one strong accent
|Hue Peaks (HSB)	|Peaks in a saturation-weighted hue histogram, ranked by sharpness	|Images with distinct saturated hues

All methods share the same inputs and end with the same LAB Delta-E deduplication, so switching methods is a fair comparison.

Inputs

- `image` — reference IMAGE (first frame of a batch is used)
- `num_colors` — target palette size (2–16)
- `min_delta_e` — minimum perceptual distance between kept colors
- `method` — extraction strategy (see table above)

Outputs

- `palette_json` — bare JSON fragment "color_palette": ["#RRGGBB", ...], dominant color first, ready to drop into a larger prompt JSON
- `palette_preview` — horizontal swatch strip IMAGE
- `color_count` — number of colors actually returned after deduplication

Category: Rennart/Color

---

Извлекает доминирующую цветовую палитру из референсного изображения и возвращает её в виде JSON-фрагмента, готового к вставке в промпт генерации, плюс визуальное превью из свотчей.

Пять стратегий извлечения доступны из одного выпадающего списка — от строгого выделения доминирующих цветов до агрессивного поиска редких акцентов:

|Метод	|Что делает	|Для чего лучше
|---|---|---|
|K-Means (Original)	|Обычный sklearn KMeans, кластеры отсортированы по численности	|Универсальный, сбалансированные палитры
|Weighted Frequency	|KMeans с весами пикселей, отдающими приоритет редким цветам	|Мелкие яркие акценты на пёстром фоне
|Farthest Point Sampling	|Жадно выбирает максимально разные цвета	|Максимально разнообразные палитры
|Two-Pass Background + Accent	|KMeans для фона, затем второй проход по худше всего объяснённым пикселям	|Пейзажи и городские сцены с одним сильным акцентом
|Hue Peaks (HSB)	|Пики в гистограмме hue с весом по насыщенности, ранжированные по остроте	|Изображения с выраженными насыщенными оттенками

Все методы принимают одинаковые входы и заканчиваются одной и той же дедупликацией по LAB Delta-E, поэтому переключение между методами — это честное сравнение.

Входы

- `image` — референсное IMAGE (используется первый кадр батча)
- `num_colors` — целевой размер палитры (2–16)
- `min_delta_e` — минимальное перцептивное расстояние между оставляемыми цветами
- `method` — стратегия извлечения (см. таблицу)

Выходы

- `palette_json` — голый JSON-фрагмент "color_palette": ["#RRGGBB", ...], доминирующий цвет первым, готов к вставке в большой JSON промпта
- `palette_preview` — горизонтальная полоса свотчей в виде IMAGE
- `color_count` — сколько цветов реально вернулось после дедупликации

Категория: Rennart/Color

</details>
<details>
<summary>🎨 Rennart Color Preview </summary>
  
## 🎨 Rennart Color Preview
  
Dynamic visualizer node with an adaptive grid algorithm that neatly renders array-based hex strings onto the canvas.
<br>
<img width="889" height="659" alt="2026-08-26_18-53-07" src="https://github.com/user-attachments/assets/a7add16b-b49b-4e8d-89fe-e2aa85b4f750" />
</details>


<details>
<summary> 🧹 Rennart Denoise </summary>

## 🧹 Rennart Denoise

Нода **Rennart Denoise** применяет модель шумоподавления `1xDeNoise_realplksr_otf` к изображению. Модель автоматически скачивается с Hugging Face при первом использовании, если её нет в папке `upscale_models`. Обработка выполняется двумя проходами — обычным и со сдвигом на заданное смещение, после чего результаты смешиваются 50/50. Это помогает уменьшить видимые швы и артефакты при тайлинге.

**Входы:**
- `image` (IMAGE) — входное изображение (батч).
- `mode` — режим работы:
  - `auto` — автоматически подбирает `tile_size=512`, `overlap=tile/4`, `offset=(tile-overlap)/2`.
  - `tile_size` — задаётся только `tile_size`, остальные параметры вычисляются по формулам авторежима.
  - `manual` — все параметры задаются вручную.
- `tile_size` (INT) — размер тайла (64–4096), по умолчанию `512`.
- `overlap` (INT) — перекрытие соседних тайлов (0–512), по умолчанию `128`.
- `offset` (INT) — смещение для второго прохода (0–1024), по умолчанию `192`.

**Выходы:**
- `image` (IMAGE) — изображение после шумоподавления.

**Категория:** `Rennart/Image`

---

The **Rennart Denoise** node applies the `1xDeNoise_realplksr_otf` denoising model to an image. The model is automatically downloaded from Hugging Face on first use if it is not already present in the `upscale_models` folder. Processing runs in two passes — a normal one and a shifted one — whose results are then blended 50/50. This helps reduce visible seams and artifacts when tiling.

**Inputs:**
- `image` (IMAGE) — input image (batch).
- `mode` — operation mode:
  - `auto` — automatically picks `tile_size=512`, `overlap=tile/4`, `offset=(tile-overlap)/2`.
  - `tile_size` — only `tile_size` is set, the rest are derived using the auto formulas.
  - `manual` — all parameters are set manually.
- `tile_size` (INT) — tile size (64–4096), default `512`.
- `overlap` (INT) — overlap between adjacent tiles (0–512), default `128`.
- `offset` (INT) — shift for the second pass (0–1024), default `192`.

**Outputs:**
- `image` (IMAGE) — the denoised image.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🔄 Rennart Offset Image </summary>

## 🔄 Rennart Offset Image

Нода **Rennart Offset Image** выполняет циклический сдвиг изображения по горизонтали и вертикали. Сдвиг можно задавать двумя способами: в процентах от ширины и высоты либо в пикселях (с поддержкой отрицательных значений). Пиксели, выходящие за границу, «заворачиваются» на противоположную сторону (torch.roll). Полезно для бесшовных текстур, тайлинга и создания смещённых копий.

**Входы:**
- `pixels` (IMAGE) — входное изображение (батч).
- `offset_mode` — режим задания сдвига: `percentage` (в процентах) или `pixels` (в пикселях), по умолчанию `percentage`.
- `x_percent` (FLOAT) — горизонтальный сдвиг в процентах от ширины (0–100), по умолчанию `50.0` (используется в режиме `percentage`).
- `y_percent` (FLOAT) — вертикальный сдвиг в процентах от высоты (0–100), по умолчанию `50.0` (используется в режиме `percentage`).
- `x_pixels` (INT) — горизонтальный сдвиг в пикселях (−8192…8192), по умолчанию `0` (используется в режиме `pixels`).
- `y_pixels` (INT) — вертикальный сдвиг в пикселях (−8192…8192), по умолчанию `0` (используется в режиме `pixels`).

**Выходы:**
- `image` (IMAGE) — сдвинутое изображение.

**Категория:** `Rennart/Image`

---

The **Rennart Offset Image** node performs a cyclic shift of the image horizontally and vertically. The shift can be specified in two ways: as a percentage of width and height, or in pixels (including negative values). Pixels that go past the edge wrap around to the opposite side (torch.roll). Useful for seamless textures, tiling, and creating offset copies.

**Inputs:**
- `pixels` (IMAGE) — input image (batch).
- `offset_mode` — shift mode: `percentage` or `pixels`, default `percentage`.
- `x_percent` (FLOAT) — horizontal shift as a percentage of width (0–100), default `50.0` (used in `percentage` mode).
- `y_percent` (FLOAT) — vertical shift as a percentage of height (0–100), default `50.0` (used in `percentage` mode).
- `x_pixels` (INT) — horizontal shift in pixels (−8192…8192), default `0` (used in `pixels` mode).
- `y_pixels` (INT) — vertical shift in pixels (−8192…8192), default `0` (used in `pixels` mode).

**Outputs:**
- `image` (IMAGE) — the shifted image.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🔍 Rennart Image Upscale (Model) </summary>

## 🔍 Rennart Image Upscale (Model)

Нода **Rennart Image Upscale (Model)** объединяет загрузку модели апскейла и само увеличение изображения в одной ноде. Модель выбирается из папки `upscale_models` ComfyUI. Обработка выполняется тайлами с настраиваемым размером и перекрытием, что позволяет работать с большими изображениями на ограниченной VRAM. При нехватке видеопамяти (OOM) нода может автоматически уменьшать размер тайла и продолжать работу.

**Входы:**
- `model_name` — имя модели апскейла из списка файлов в папке `upscale_models`.
- `image` (IMAGE) — входное изображение (батч).
- `tile_size` (INT) — размер тайла (плитки) в пикселях (64–4096), по умолчанию `512`. Больше — быстрее, но требует больше VRAM.
- `overlap` (INT) — перекрытие между тайлами в пикселях (0–512), по умолчанию `32`. Помогает убрать видимые швы.
- `auto_reduce_on_oom` (BOOLEAN) — автоматически уменьшать размер тайла при нехватке VRAM, по умолчанию `True`.

**Выходы:**
- `image` (IMAGE) — увеличенное изображение.

**Категория:** `Rennart/Upscale`

---

The **Rennart Image Upscale (Model)** node combines upscale model loading and image upscaling into a single node. The model is selected from the ComfyUI `upscale_models` folder. Processing is performed in tiles with configurable size and overlap, allowing large images to be handled on limited VRAM. On out-of-memory (OOM) errors, the node can automatically reduce the tile size and continue.

**Inputs:**
- `model_name` — upscale model name from the list of files in the `upscale_models` folder.
- `image` (IMAGE) — input image (batch).
- `tile_size` (INT) — tile size in pixels (64–4096), default `512`. Larger is faster but requires more VRAM.
- `overlap` (INT) — overlap between tiles in pixels (0–512), default `32`. Helps remove visible seams.
- `auto_reduce_on_oom` (BOOLEAN) — automatically reduce tile size on VRAM shortage, default `True`.

**Outputs:**
- `image` (IMAGE) — the upscaled image.

**Category:** `Rennart/Upscale`
</details>

<details>
<summary> 🎵 Rennart Audio Concatenate </summary>

## 🎵 Rennart Audio Concatenate

Нода **Rennart Audio Concatenate** последовательно склеивает несколько аудиовходов (от 2 до 30) в один аудиопоток в порядке `audio_1 → audio_2 → audio_3 → ...`. Между склейками можно добавлять паузу заданной длительности (тишину). Все входные аудио должны иметь одинаковую частоту дискретизации и одинаковое число каналов — иначе нода выдаст ошибку с пояснением. Пауза не добавляется после последнего аудио.

**Входы:**
- `number_of_inputs` (INT) — количество аудио для склейки (2–30), по умолчанию `2`.
- `pause_seconds` (FLOAT) — длительность паузы между склейками в секундах (0–60), по умолчанию `1.0`. `0` — без паузы.
- `audio_1` (AUDIO) — первое аудио (обязательный).
- `audio_2` (AUDIO) — второе аудио (обязательный).
- `audio_3` … `audio_30` (AUDIO, опциональные) — дополнительные аудио, используются, если `number_of_inputs` больше 2.

**Выходы:**
- `audio` (AUDIO) — склеенный аудиопоток.

**Категория:** `Rennart/Audio`

---

The **Rennart Audio Concatenate** node concatenates multiple audio inputs (from 2 to 30) into a single audio stream, in the order `audio_1 → audio_2 → audio_3 → ...`. A silence pause of a chosen duration can be inserted between the joined clips. All input audios must share the same sample rate and the same number of channels — otherwise the node raises a descriptive error. No pause is added after the last audio.

**Inputs:**
- `number_of_inputs` (INT) — number of audios to concatenate (2–30), default `2`.
- `pause_seconds` (FLOAT) — pause duration between clips in seconds (0–60), default `1.0`. `0` means no pause.
- `audio_1` (AUDIO) — first audio (required).
- `audio_2` (AUDIO) — second audio (required).
- `audio_3` … `audio_30` (AUDIO, optional) — additional audios, used when `number_of_inputs` is greater than 2.

**Outputs:**
- `audio` (AUDIO) — the concatenated audio stream.

**Category:** `Rennart/Audio`
</details>

<details>
<summary> 🎨 Rennart RGBA to RGB </summary>

## 🎨 Rennart RGBA to RGB

Нода **Rennart RGBA to RGB** приводит изображение к трёхканальному виду (RGB), убирая альфа-канал и корректно обрабатывая другие варианты числа каналов. Если изображение уже RGB — возвращается без изменений; если RGBA или больше 4 каналов — берутся только первые три; если один канал (grayscale) — он дублируется в три, чтобы получить RGB. Полезно для пайплайнов, куда нужно подавать только RGB-тензоры.

**Входы:**
- `image` (IMAGE) — входное изображение (батч).

**Выходы:**
- `image` (IMAGE) — изображение с тремя каналами (RGB).

**Категория:** `Rennart/Image`

---

The **Rennart RGBA to RGB** node converts an image to a three-channel (RGB) representation by dropping the alpha channel and correctly handling other channel-count variants. If the image is already RGB, it is returned unchanged; if RGBA or more than 4 channels, only the first three are kept; if single-channel (grayscale), it is duplicated into three channels to produce RGB. Useful for pipelines that require RGB-only tensors.

**Inputs:**
- `image` (IMAGE) — input image (batch).

**Outputs:**
- `image` (IMAGE) — image with three channels (RGB).

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🎯 Rennart Pixel Drift Fix </summary>

## 🎯 Rennart Pixel Drift Fix

Нода **Rennart Pixel Drift Fix** выравнивает отредактированное изображение обратно к геометрии исходного изображения. Это полезно, когда после внешней обработки (inpainting, img2img, ручная правка и т.п.) картинка «уехала» относительно оригинала. Алгоритм находит общие ключевые точки через SIFT, сопоставляет их методом BFMatcher, фильтрует по критерию Лоу, вычисляет гомографию через RANSAC и деформирует отредактированное изображение обратно к исходной геометрии. Доступны два режима: быстрая глобальная перспективная коррекция `flat_4_points` и экспериментальная плотная нелинейная коррекция `mesh` (кусочно-аффинное преобразование).

**Входы:**
- `edited_image` (IMAGE) — изображение после редактирования (должно быть **первым** IMAGE-входом — при bypass ComfyUI пропускает именно его на выход).
- `source_image` (IMAGE) — исходное (эталонное) изображение, задающее целевую геометрию.
- `method` — метод выравнивания:
  - `flat_4_points` — быстрая глобальная перспективная коррекция (по умолчанию, даёт лучший результат).
  - `mesh` — экспериментальная плотная нелинейная коррекция на основе кусочно-аффинного преобразования.
- `max_mesh_points` (INT) — максимальное число точек для mesh-режима (100–10000), по умолчанию `400`. Большие значения повышают точность, но замедляют работу. Используется только при `method="mesh"`.

**Выходы:**
- `fixed_image` (IMAGE) — отредактированное изображение, приведённое к геометрии исходного.

**Категория:** `Rennart/Image`

---

The **Rennart Pixel Drift Fix** node aligns an edited image back to the geometry of the source image. This is useful when external processing (inpainting, img2img, manual edits, etc.) has shifted the picture relative to the original. The algorithm detects shared keypoints with SIFT, matches them with BFMatcher, filters matches using Lowe's ratio test, estimates a homography with RANSAC, and warps the edited image back to the source geometry. Two modes are available: fast global perspective correction `flat_4_points` and experimental dense non-linear correction `mesh` (piecewise affine transform).

**Inputs:**
- `edited_image` (IMAGE) — the edited image (must be the **first** IMAGE input — on bypass ComfyUI passes it straight to the output).
- `source_image` (IMAGE) — the source (reference) image that defines the target geometry.
- `method` — alignment method:
  - `flat_4_points` — fast global perspective correction (default, gives better results).
  - `mesh` — experimental dense non-linear correction based on piecewise affine transform.
- `max_mesh_points` (INT) — maximum number of points for mesh mode (100–10000), default `400`. Higher values increase accuracy but take longer. Only used when `method="mesh"`.

**Outputs:**
- `fixed_image` (IMAGE) — the edited image aligned to the source geometry.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 📅 Rennart Date String </summary>

## 📅 Rennart Date String

Нода **Rennart Date String** возвращает текущую дату и время в виде строки, отформатированной по заданному шаблону. Поддерживает стандартные директивы `strftime` (например, `%Y-%m-%d`, `%H:%M:%S`). Нода автоматически помечается как изменённая при каждом запуске workflow, что гарантирует получение актуального значения времени.

**Входы:**
- `format` (STRING) — строка формата даты/времени, по умолчанию `%Y-%m-%d`.

**Выходы:**
- `date_string` (STRING) — отформатированная строка с текущей датой и временем.

**Категория:** `Rennart/Utils`

---

The **Rennart Date String** node outputs the current date and time as a string formatted according to a user-defined template. It supports standard `strftime` directives (e.g. `%Y-%m-%d`, `%H:%M:%S`). The node is automatically marked as changed on every workflow run, ensuring an up-to-date timestamp is always returned.

**Inputs:**
- `format` (STRING) — date/time format string, default is `%Y-%m-%d`.

**Outputs:**
- `date_string` (STRING) — formatted string containing the current date and time.

**Category:** `Rennart/Utils`
</details>

<details>
<summary> 📐 Rennart Image Size </summary>

## 📐 Rennart Image Size

Нода **Rennart Image Size** возвращает размеры входного изображения (ширину и высоту), а также вычисляет длинную и короткую стороны. Дополнительно выдаёт текстовую строку с информацией о размерах. Изображение проходит через ноду без изменений.

**Входы:**
- `image` (IMAGE) — входное изображение.

**Выходы:**
- `image` (IMAGE) — исходное изображение без изменений.
- `width` (INT) — ширина изображения в пикселях.
- `height` (INT) — высота изображения в пикселях.
- `longest_side` (INT) — длина наибольшей стороны (`max(width, height)`).
- `shortest_side` (INT) — длина наименьшей стороны (`min(width, height)`).
- `info` (STRING) — строка с информацией, например `Width: 1024, Height: 768`.

**Категория:** `Rennart/Image`

---

The **Rennart Image Size** node returns the dimensions of the input image (width and height) and computes its longest and shortest sides. It also provides a text string with size information. The image itself passes through the node unchanged.

**Inputs:**
- `image` (IMAGE) — input image.

**Outputs:**
- `image` (IMAGE) — the original image, unchanged.
- `width` (INT) — image width in pixels.
- `height` (INT) — image height in pixels.
- `longest_side` (INT) — length of the longest side (`max(width, height)`).
- `shortest_side` (INT) — length of the shortest side (`min(width, height)`).
- `info` (STRING) — info string, e.g. `Width: 1024, Height: 768`.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🖼️ Rennart Load Image </summary>

## 🖼️ Rennart Load Image

Нода **Rennart Load Image** загружает изображение из входной папки ComfyUI и возвращает его тензор, маску (если есть альфа-канал или прозрачность), а также ширину, высоту и имя файла без расширения. Поддерживает многостраничные изображения (анимации), извлекая все кадры с одинаковыми размерами, и корректно обрабатывает EXIF-ориентацию.

**Входы:**
- `image` (IMAGE) — выбор изображения из списка файлов во входной директории (с возможностью загрузки через интерфейс).

**Выходы:**
- `image` (IMAGE) — загруженное изображение (или батч кадров для анимаций).
- `mask` (MASK) — маска на основе альфа-канала или прозрачности; если их нет — нулевая маска по размеру изображения.
- `width` (INT) — ширина изображения в пикселях.
- `height` (INT) — высота изображения в пикселях.
- `filename` (STRING) — имя файла без расширения.

**Категория:** `Rennart/Image`

---

The **Rennart Load Image** node loads an image from the ComfyUI input folder and returns its tensor, a mask (if an alpha channel or transparency is present), as well as its width, height, and filename without extension. It supports multi-frame images (animations) by extracting all frames of equal size, and correctly handles EXIF orientation.

**Inputs:**
- `image` (IMAGE) — image selected from the list of files in the input directory (with an upload option in the UI).

**Outputs:**
- `image` (IMAGE) — the loaded image (or a batch of frames for animations).
- `mask` (MASK) — mask derived from the alpha channel or transparency; a zero mask sized to the image if neither is present.
- `width` (INT) — image width in pixels.
- `height` (INT) — image height in pixels.
- `filename` (STRING) — filename without extension.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🔄 Rennart Offset Image </summary>

## 🔄 Rennart Offset Image

Нода **Rennart Offset Image** выполняет циклический сдвиг изображения по горизонтали и вертикали на заданный процент от ширины и высоты. Пиксели, выходящие за границу, «заворачиваются» на противоположную сторону (torch.roll). Полезно для бесшовных текстур, тайлинга и создания смещённых копий.

**Входы:**
- `pixels` (IMAGE) — входное изображение (батч).
- `x_percent` (FLOAT) — горизонтальный сдвиг в процентах от ширины (0–100), по умолчанию `50.0`.
- `y_percent` (FLOAT) — вертикальный сдвиг в процентах от высоты (0–100), по умолчанию `50.0`.

**Выходы:**
- `image` (IMAGE) — сдвинутое изображение.

**Категория:** `Rennart/Image`

---

The **Rennart Offset Image** node performs a cyclic shift of the image horizontally and vertically by a given percentage of its width and height. Pixels that go past the edge wrap around to the opposite side (torch.roll). Useful for seamless textures, tiling, and creating offset copies.

**Inputs:**
- `pixels` (IMAGE) — input image (batch).
- `x_percent` (FLOAT) — horizontal shift as a percentage of width (0–100), default `50.0`.
- `y_percent` (FLOAT) — vertical shift as a percentage of height (0–100), default `50.0`.

**Outputs:**
- `image` (IMAGE) — the shifted image.

**Category:** `Rennart/Image`
</details>

<details>
<summary> 🎲 Rennart Random Number </summary>

## 🎲 Rennart Random Number

Нода **Rennart Random Number** генерирует случайное число заданного типа (целое, дробное или булево) в указанном диапазоне с использованием seed для воспроизводимости. Поддерживает опциональное округление до кратного значения (например, 1, 5, 10, 16, 64). Возвращает результат сразу в нескольких форматах: INT, FLOAT, NUMBER, STRING и сам seed.

**Входы:**
- `number_type` — тип генерируемого числа: `integer`, `float` или `bool` (по умолчанию `integer`).
- `minimum` (FLOAT) — минимальное значение диапазона, по умолчанию `0`.
- `maximum` (FLOAT) — максимальное значение диапазона, по умолчанию `100`.
- `enable_rounding` (BOOLEAN) — включить округление числа, по умолчанию `False`.
- `round_to` (INT) — шаг округления (1, 5, 10, 16, 64 и т.д.), по умолчанию `1`.
- `seed` (INT) — seed генератора случайных чисел для воспроизводимости, по умолчанию `0`.

**Выходы:**
- `int` (INT) — результат в виде целого числа.
- `float` (FLOAT) — результат в виде дробного числа.
- `number` (NUMBER) — результат в исходном типе (INT или FLOAT).
- `string` (STRING) — строковое представление результата.
- `seed` (INT) — использованный seed.

**Категория:** `Rennart/Utils`

---

The **Rennart Random Number** node generates a random number of a chosen type (integer, float, or bool) within a specified range, using a seed for reproducibility. It optionally supports rounding to a multiple (e.g. 1, 5, 10, 16, 64). The result is returned in several formats at once: INT, FLOAT, NUMBER, STRING, along with the seed used.

**Inputs:**
- `number_type` — type of the generated number: `integer`, `float`, or `bool` (default `integer`).
- `minimum` (FLOAT) — minimum of the range, default `0`.
- `maximum` (FLOAT) — maximum of the range, default `100`.
- `enable_rounding` (BOOLEAN) — enable number rounding, default `False`.
- `round_to` (INT) — rounding step (1, 5, 10, 16, 64, etc.), default `1`.
- `seed` (INT) — random generator seed for reproducibility, default `0`.

**Outputs:**
- `int` (INT) — result as an integer.
- `float` (FLOAT) — result as a float.
- `number` (NUMBER) — result in its original type (INT or FLOAT).
- `string` (STRING) — string representation of the result.
- `seed` (INT) — the seed used.

**Category:** `Rennart/Utils`
</details>

<details>
<summary> ✂️ Rennart Image Crop </summary>

## ✂️ Rennart Image Crop

Нода **Rennart Image Crop** обрезает изображение от центра так, чтобы его ширина и высота стали кратны заданному числу (например, 8, 16, 32, 64). Это полезно для подготовки изображений к моделям, требующим размеров, кратных определённому значению (VAE, апскейлеры, пайплайны SD). Дополнительно возвращает новые размеры и длины сторон.

**Входы:**
- `image` (IMAGE) — входное изображение (батч).
- `multiple` (INT) — число, которому должны быть кратны ширина и высота после обрезки (1–512), по умолчанию `16`.

**Выходы:**
- `image` (IMAGE) — обрезанное изображение.
- `width` (INT) — новая ширина в пикселях.
- `height` (INT) — новая высота в пикселях.
- `longest_side` (INT) — длина наибольшей стороны (`max(width, height)`).
- `shortest_side` (INT) — длина наименьшей стороны (`min(width, height)`).

**Категория:** `Rennart/Image`

---

The **Rennart Image Crop** node crops the image from the center so that its width and height become multiples of a given number (e.g. 8, 16, 32, 64). This is useful for preparing images for models that require dimensions divisible by a certain value (VAE, upscalers, SD pipelines). It also returns the new dimensions and side lengths.

**Inputs:**
- `image` (IMAGE) — input image (batch).
- `multiple` (INT) — number that the width and height must be multiples of after cropping (1–512), default `16`.

**Outputs:**
- `image` (IMAGE) — the cropped image.
- `width` (INT) — new width in pixels.
- `height` (INT) — new height in pixels.
- `longest_side` (INT) — length of the longest side (`max(width, height)`).
- `shortest_side` (INT) — length of the shortest side (`min(width, height)`).

**Category:** `Rennart/Image`
</details>


## 📜 License
MIT License. Use at your own risk without any warranties. See the [LICENSE](LICENSE) file for details

## ✌️ Thanks
Some nodes and utils in this package were copied, forked, refined or remastered from:<br>
[WAS Node Suite](https://github.com/WASasquatch/was-node-suite-comfyui/)<br>
[ComfyUI-Ideogram-Palette-and-Prompt-Tools](https://github.com/SurrealByDesign/ComfyUI-Ideogram-Palette-and-Prompt-Tools)<br>

Thanks to ComfyUI community for inspiration and support.<br>
Special thanks to [Raykosan](https://github.com/Raykosan) and [Art-xmaster](https://github.com/Art-xmaster) for inspiration and support.<br>
If you like this node, don't forget to star on GitHub!  

## 📧 Contact
https://t.me/rinatmaksutov
