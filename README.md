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

image — reference IMAGE (first frame of a batch is used)
num_colors — target palette size (2–16)
min_delta_e — minimum perceptual distance between kept colors
method — extraction strategy (see table above)

Outputs

palette_json — bare JSON fragment "color_palette": ["#RRGGBB", ...], dominant color first, ready to drop into a larger prompt JSON
palette_preview — horizontal swatch strip IMAGE
color_count — number of colors actually returned after deduplication

Category: Rennart/Color

Извлекает доминирующую цветовую палитру из референсного изображения и возвращает её в виде JSON-фрагмента, готового к вставке в промпт генерации, плюс визуальное превью из свотчей.

Пять стратегий извлечения доступны из одного выпадающего списка — от строгого выделения доминирующих цветов до агрессивного поиска редких акцентов:

|Метод	|Что делает	|Для чего лучше
|K-Means (Original)	|Обычный sklearn KMeans, кластеры отсортированы по численности	|Универсальный, сбалансированные палитры
|Weighted Frequency	|KMeans с весами пикселей, отдающими приоритет редким цветам	|Мелкие яркие акценты на пёстром фоне
|Farthest Point Sampling	|Жадно выбирает максимально разные цвета	|Максимально разнообразные палитры
|Two-Pass Background + Accent	|KMeans для фона, затем второй проход по худше всего объяснённым пикселям	|Пейзажи и городские сцены с одним сильным акцентом
|Hue Peaks (HSB)	|Пики в гистограмме hue с весом по насыщенности, ранжированные по остроте	|Изображения с выраженными насыщенными оттенками

Все методы принимают одинаковые входы и заканчиваются одной и той же дедупликацией по LAB Delta-E, поэтому переключение между методами — это честное сравнение.

Входы

image — референсное IMAGE (используется первый кадр батча)
num_colors — целевой размер палитры (2–16)
min_delta_e — минимальное перцептивное расстояние между оставляемыми цветами
method — стратегия извлечения (см. таблицу)

Выходы

palette_json — голый JSON-фрагмент "color_palette": ["#RRGGBB", ...], доминирующий цвет первым, готов к вставке в большой JSON промпта
palette_preview — горизонтальная полоса свотчей в виде IMAGE
color_count — сколько цветов реально вернулось после дедупликации

Категория: Rennart/Color



## 🎨 Rennart Color Preview
Dynamic visualizer node with an adaptive grid algorithm that neatly renders array-based hex strings onto the canvas.
<br>
<img width="889" height="659" alt="2026-08-26_18-53-07" src="https://github.com/user-attachments/assets/a7add16b-b49b-4e8d-89fe-e2aa85b4f750" />

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
