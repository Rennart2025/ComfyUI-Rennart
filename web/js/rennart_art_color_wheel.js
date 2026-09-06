import { app } from "../../../../scripts/app.js";

const NODE_NAME = "RennartArtColorWheel";

// Минимум цветов по типу палитры — должно совпадать с MIN_COLORS в Python.
// Square убран (дублировал Tetradic — оба давали 4 луча через 90°).
const MIN_COLORS = {
    "Complementary": 2,
    "Analogous": 3,
    "Triad": 3,
    "Split-Complementary": 3,
    "Double Split-Complementary": 5,
    "Tetradic": 4,
    "Monochromatic": 2,
    "Custom": 2,
};

// Углы лучей (в градусах на "художественном" круге) для каждого типа
// палитры. Первый луч всегда 0 — это "root"-луч, за который цепляются все
// остальные при вращении. Подтверждено пользователем: Complementary 180°,
// Triad 120°, Tetradic 90°. Double Split-Complementary = лучи
// Split-Complementary (0,150,210) + два луча-продолжения C2 и C3 на
// противоположную сторону (150+180=330, 210+180=30).
const RAY_OFFSETS_DEG = {
    "Complementary": [0, 180],
    "Analogous": [0, 30, -30],
    "Triad": [0, 120, 240],
    "Split-Complementary": [0, 150, 210],
    "Double Split-Complementary": [0, 150, 210, 330, 30],
    "Tetradic": [0, 90, 180, 270],
    "Monochromatic": [0],
};

// ---------- generic fallback для типов, для которых ещё нет точных стартовых
// таблиц (сейчас это только Analogous — пользователь подтвердил, что
// нынешнее поведение по этой палитре уже устраивает, менять не нужно).
const ECHO_LEVELS = [
    { s: 0.66, v: 0.67 },
    { s: 0.50, v: 0.50 },
];

function echoLevelFor(generation) {
    const idx = generation - 1;
    if (idx < ECHO_LEVELS.length) return ECHO_LEVELS[idx];
    const last = ECHO_LEVELS[ECHO_LEVELS.length - 1];
    const extraSteps = idx - ECHO_LEVELS.length + 1;
    const decay = Math.pow(0.8, extraSteps);
    return { s: Math.max(0.15, last.s * decay), v: Math.max(0.2, last.v * decay) };
}

// ---------- точные стартовые S/B (п.4) и таблицы "переброса" brightness (п.5) ----------
// Формат стартов: [saturation%, brightness%] по каждому цвету (индекс = позиция, 0 = C1).
// Формат jumpDown: значение (в %), на которое "перебрасывается" вторичный цвет
// (индекс = позиция СРЕДИ вторичных, 0 = первый цвет после primary-лучей),
// когда при каскаде от C1 его brightness опускается до lowThresh.
// jumpTargetAlways — для Monochromatic, где переброс всегда идёт на 100%
// независимо от позиции цвета.

const COMPLEMENTARY_START = {
    2: [[100, 100], [100, 100]],
    3: [[100, 100], [100, 100], [66, 67]],
    4: [[100, 100], [100, 100], [66, 67], [50, 50]],
    5: [[100, 100], [100, 100], [75, 75], [66, 67], [50, 50]],
    6: [[100, 100], [100, 100], [75, 75], [66, 67], [50, 50], [33, 33]],
    7: [[100, 100], [100, 100], [80, 80], [75, 75], [60, 60], [50, 50], [40, 40]],
    8: [[100, 100], [100, 100], [80, 80], [75, 75], [60, 60], [50, 50], [40, 40], [25, 25]],
    9: [[100, 100], [100, 100], [84, 84], [80, 80], [66, 67], [60, 60], [50, 50], [40, 40], [33, 33]],
    10: [[100, 100], [100, 100], [84, 84], [80, 80], [66, 67], [60, 60], [50, 50], [40, 40], [33, 33], [20, 20]],
};
const COMPLEMENTARY_JUMP_DOWN = {
    3: [86],
    4: [86, 100],
    5: [69, 86, 100],
    6: [35, 27, 100, 100],
    7: [59, 67, 100, 100, 100],
    8: [59, 67, 100, 100, 100, 100],
    9: [53, 59, 86, 100, 100, 100, 100],
    10: [53, 59, 86, 100, 100, 100, 100, 100],
};

const TRIAD_START = {
    3: [[100, 100], [100, 100], [100, 100]],
    4: [[100, 100], [100, 100], [100, 100], [75, 75]],
    5: [[100, 100], [100, 100], [100, 100], [66, 67], [50, 50]],
    6: [[100, 100], [100, 100], [100, 100], [66, 67], [50, 50], [50, 50]],
    7: [[100, 100], [100, 100], [100, 100], [75, 75], [66, 67], [66, 67], [50, 50]],
    8: [[100, 100], [100, 100], [100, 100], [75, 75], [66, 67], [66, 67], [50, 50], [33, 33]],
    9: [[100, 100], [100, 100], [100, 100], [75, 75], [66, 67], [66, 67], [50, 50], [33, 33], [33, 33]],
    10: [[100, 100], [100, 100], [100, 100], [80, 80], [75, 75], [75, 75], [60, 60], [50, 50], [50, 50], [40, 40]],
};
const TRIAD_JUMP_DOWN = {
    4: [86],
    5: [86, 100],
    6: [86, 100, 100],
    7: [69, 86, 86, 100],
    8: [69, 86, 86, 100, 100],
    9: [69, 86, 86, 100, 100, 100],
    10: [59, 69, 69, 100, 100, 100, 100],
};

const SPLIT_COMPLEMENTARY_START = {
    3: [[100, 100], [100, 100], [100, 100]],
    4: [[100, 100], [100, 100], [100, 100], [50, 50]],
    5: [[100, 100], [100, 100], [100, 100], [50, 50], [50, 50]],
    6: [[100, 100], [100, 100], [100, 100], [50, 50], [50, 50], [50, 50]],
    7: [[100, 100], [100, 100], [100, 100], [66, 67], [66, 67], [66, 67], [33, 33]],
    8: [[100, 100], [100, 100], [100, 100], [66, 67], [66, 67], [66, 67], [33, 33], [33, 33]],
    9: [[100, 100], [100, 100], [100, 100], [66, 67], [66, 67], [66, 67], [33, 33], [33, 33], [33, 33]],
    10: [[100, 100], [100, 100], [100, 100], [75, 75], [75, 75], [75, 75], [50, 50], [50, 50], [50, 50], [25, 25]],
};
const SPLIT_COMPLEMENTARY_JUMP_DOWN = {
    4: [100],
    5: [100, 100],
    6: [100, 100, 100],
    7: [86, 86, 86, 100],
    8: [86, 86, 86, 100, 100],
    9: [86, 86, 86, 100, 100, 100],
    10: [59, 86, 100, 100, 100, 100, 100],
};

const DOUBLE_SPLIT_COMPLEMENTARY_START = {
    5: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100]],
    6: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100], [50, 50]],
    7: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100], [50, 50], [50, 50]],
    8: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100], [50, 50], [50, 50], [50, 50]],
    9: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100], [50, 50], [50, 50], [50, 50], [50, 50]],
    10: [[100, 100], [100, 100], [100, 100], [100, 100], [100, 100], [50, 50], [50, 50], [50, 50], [50, 50], [50, 50]],
};
const DOUBLE_SPLIT_COMPLEMENTARY_JUMP_DOWN = {
    6: [100],
    7: [100, 100],
    8: [100, 100, 100],
    9: [100, 100, 100, 100],
    10: [100, 100, 100, 100, 100],
};

const TETRADIC_START = {
    4: [[100, 100], [100, 100], [100, 100], [100, 100]],
    5: [[100, 100], [100, 100], [100, 100], [100, 100], [66, 67]],
    6: [[100, 100], [100, 100], [100, 100], [100, 100], [66, 67], [50, 50]],
    7: [[100, 100], [100, 100], [100, 100], [100, 100], [66, 67], [50, 50], [50, 50]],
    8: [[100, 100], [100, 100], [100, 100], [100, 100], [66, 67], [50, 50], [50, 50], [50, 50]],
    9: [[100, 100], [100, 100], [100, 100], [100, 100], [75, 75], [66, 67], [66, 67], [66, 67], [50, 50]],
    10: [[100, 100], [100, 100], [100, 100], [100, 100], [75, 75], [66, 67], [66, 67], [66, 67], [50, 50], [50, 50]],
};
const TETRADIC_JUMP_DOWN = {
    5: [86],
    6: [100, 100],
    7: [100, 100, 100],
    8: [86, 86, 86, 86],
    9: [69, 86, 86, 86, 100],
    10: [86, 100, 100, 100, 100, 100],
};

// Monochromatic: 1 луч, поэтому ВСЕ цвета кроме C1 формально "вторичные".
// У пользователя отдельный (более низкий) порог переброса — 10%, а не 20% —
// и цель переброса всегда 100%, независимо от позиции цвета.
const MONOCHROMATIC_START = {
    2: [[100, 100], [50, 50]],
    3: [[100, 100], [66, 67], [33, 33]],
    4: [[100, 100], [75, 75], [50, 50], [25, 25]],
    5: [[100, 100], [80, 80], [60, 60], [40, 40], [20, 20]],
    6: [[100, 100], [84, 84], [66, 67], [50, 50], [33, 33], [16, 20]],
    7: [[100, 100], [86, 86], [71, 71], [58, 57], [43, 43], [29, 29], [14, 20]],
    8: [[100, 100], [87, 87], [75, 75], [62, 62], [50, 50], [38, 38], [25, 25], [12, 20]],
    9: [[100, 100], [89, 89], [78, 78], [66, 67], [56, 56], [44, 44], [33, 33], [23, 22], [12, 20]],
    10: [[100, 100], [90, 90], [80, 80], [70, 70], [60, 60], [50, 50], [40, 40], [30, 30], [20, 20], [10, 20]],
};

// Реестр всех типов с точными данными. Analogous сюда намеренно не входит —
// работает через generic-фолбэк (echoLevelFor), пользователь подтвердил,
// что текущее поведение по нему устраивает.
const PALETTE_DATA = {
    "Complementary": { start: COMPLEMENTARY_START, jumpDown: COMPLEMENTARY_JUMP_DOWN, lowThresh: 0.20 },
    "Triad": { start: TRIAD_START, jumpDown: TRIAD_JUMP_DOWN, lowThresh: 0.20 },
    "Split-Complementary": { start: SPLIT_COMPLEMENTARY_START, jumpDown: SPLIT_COMPLEMENTARY_JUMP_DOWN, lowThresh: 0.20 },
    "Double Split-Complementary": { start: DOUBLE_SPLIT_COMPLEMENTARY_START, jumpDown: DOUBLE_SPLIT_COMPLEMENTARY_JUMP_DOWN, lowThresh: 0.20 },
    "Tetradic": { start: TETRADIC_START, jumpDown: TETRADIC_JUMP_DOWN, lowThresh: 0.20 },
    "Monochromatic": { start: MONOCHROMATIC_START, jumpDown: null, jumpTargetAlways: 1.00, lowThresh: 0.10 },
};

const LOW_THRESH_DEFAULT = 0.20;
const HIGH_THRESH = 1.00;

function clamp01(x) {
    return Math.max(0, Math.min(1, x));
}

function paletteData(type) {
    return PALETTE_DATA[type] || null;
}

// По типу/количеству/позиции цвета вернуть стартовые {s, v} (0..1).
function startLevelFor(type, count, index, rayCount) {
    const data = paletteData(type);
    if (data && data.start && data.start[count]) {
        const [s, v] = data.start[count][index];
        return { s: s / 100, v: v / 100 };
    }
    // Generic fallback (Analogous и любой ещё не описанный тип).
    const generation = Math.floor(index / rayCount);
    return generation === 0 ? { s: 1, v: 1 } : echoLevelFor(generation);
}

// ---------- цветовая математика ----------
//
// Порт artisticToScientificSmooth из tinted/lib/src/util.js: кусочно-линейное
// отображение "художественного" угла на круге (красный/жёлтый/синий как
// первичные, зелёный строго напротив красного) в "научный" HSV-hue.

function mapRange(value, fromRange, toRange) {
    const [fromLower, fromUpper] = fromRange;
    const [toLower, toUpper] = toRange;
    return toLower + (value - fromLower) * ((toUpper - toLower) / (fromUpper - fromLower));
}

function normalizeHueDeg(hue) {
    hue = hue % 360;
    if (hue < 0) hue += 360;
    return hue;
}

function artisticToScientificSmooth(hue) {
    hue = normalizeHueDeg(hue);
    if (hue < 60) return hue * (35 / 60);
    if (hue < 122) return mapRange(hue, [60, 122], [35, 60]);
    if (hue < 165) return mapRange(hue, [122, 165], [60, 120]);
    if (hue < 218) return mapRange(hue, [165, 218], [120, 180]);
    if (hue < 275) return mapRange(hue, [218, 275], [180, 240]);
    if (hue < 330) return mapRange(hue, [275, 330], [240, 300]);
    return mapRange(hue, [330, 360], [300, 360]);
}

function hsvToRgb(h, s, v) {
    let r, g, b;
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);
    switch (((i % 6) + 6) % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

const ARTISTIC_HUE_TABLE = (() => {
    const table = new Float32Array(360);
    for (let deg = 0; deg < 360; deg++) {
        table[deg] = normalizeHueDeg(artisticToScientificSmooth(deg)) / 360;
    }
    return table;
})();

function artisticToStdHue01(h01) {
    const deg = ((Math.round(h01 * 360) % 360) + 360) % 360;
    return ARTISTIC_HUE_TABLE[deg];
}

function rgbToHex(r, g, b) {
    const toHex = (x) => x.toString(16).padStart(2, "0");
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase();
}

function markerHex(m) {
    const stdHue = artisticToStdHue01(m.hue);
    const [r, g, b] = hsvToRgb(stdHue, m.sat, m.val);
    return rgbToHex(r, g, b);
}

app.registerExtension({
    name: "Rennart.ArtColorWheel",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            setupColorWheelWidget(this);
            return r;
        };
    },
});

function setupColorWheelWidget(node) {
    const WHEEL_SIZE = 220;
    const MARKER_RADIUS = 8;
    const cx = WHEEL_SIZE / 2;
    const cy = WHEEL_SIZE / 2;
    const wheelRadius = WHEEL_SIZE / 2 - MARKER_RADIUS - 2;

    const dataWidget = node.widgets.find((w) => w.name === "wheel_data");
    const countWidget = node.widgets.find((w) => w.name === "color_count");
    const typeWidget = node.widgets.find((w) => w.name === "palette_type");

    if (dataWidget) {
        dataWidget.type = "hidden";
        dataWidget.computeSize = () => [0, -4];
    }

    // ---- DOM ----
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.flexDirection = "column";
    container.style.alignItems = "center";
    container.style.gap = "6px";
    container.style.padding = "4px 2px 8px";
    container.style.width = "100%";
    container.style.boxSizing = "border-box";

    const canvas = document.createElement("canvas");
    canvas.width = WHEEL_SIZE;
    canvas.height = WHEEL_SIZE;
    canvas.style.width = "100%";
    canvas.style.maxWidth = `${WHEEL_SIZE}px`;
    canvas.style.aspectRatio = "1 / 1";
    canvas.style.borderRadius = "50%";
    canvas.style.cursor = "grab";
    canvas.style.touchAction = "none";
    container.appendChild(canvas);

    const swatchesEl = document.createElement("div");
    swatchesEl.style.display = "flex";
    swatchesEl.style.flexDirection = "column";
    swatchesEl.style.width = "100%";
    swatchesEl.style.gap = "8px";
    swatchesEl.style.marginTop = "6px";
    container.appendChild(swatchesEl);

    const ctx = canvas.getContext("2d");

    // ---- state ----
    // markers: [{ hue: 0..1, sat, val, ray, gen, satDir }]
    let markers = [];
    let rowRefs = [];
    let rootAngleFrac = 0;
    let dragIndex = -1;
    let wheelBgCache = null;

    function isCustom() {
        return (typeWidget?.value ?? "Custom") === "Custom";
    }

    function rayOffsets() {
        return RAY_OFFSETS_DEG[typeWidget?.value] || [0];
    }

    function currentMinCount() {
        return MIN_COLORS[typeWidget?.value] ?? 2;
    }

    function clampCount(n) {
        return Math.max(currentMinCount(), Math.min(10, Math.round(n)));
    }

    // Переключение в Custom "на лету" (п.4.3), без сброса текущей раскладки —
    // просто снимаем жёсткую связку, дальше каждый маркер независим.
    function forceCustomMode() {
        if (!typeWidget || typeWidget.value === "Custom") return;
        typeWidget.value = "Custom";
        node.setDirtyCanvas(true, true);
    }

    // Пересобрать маркеры под текущий тип палитры / количество цветов.
    function initMarkers(count) {
        if (isCustom()) {
            const prev = markers;
            const next = [];
            for (let i = 0; i < count; i++) {
                if (prev[i]) {
                    next.push(prev[i]);
                } else {
                    next.push({ hue: (i / count) % 1, sat: 1, val: 1, ray: i, gen: 0, satDir: 1 });
                }
            }
            markers = next;
            return;
        }

        const offsets = rayOffsets();
        const rayCount = offsets.length;
        const next = [];
        for (let i = 0; i < count; i++) {
            const rayIndex = i % rayCount;
            const generation = Math.floor(i / rayCount);
            const angleFrac = (rootAngleFrac + offsets[rayIndex] / 360 + 1) % 1;
            const level = startLevelFor(typeWidget?.value, count, i, rayCount);
            next.push({
                hue: angleFrac,
                sat: level.s,
                val: level.v,
                ray: rayIndex,
                gen: generation,
                satDir: 1,
            });
        }
        markers = next;
    }

    // Пересчитать только углы существующих маркеров под новый rootAngleFrac.
    function reapplyRotation() {
        const offsets = rayOffsets();
        markers.forEach((m) => {
            m.hue = (rootAngleFrac + offsets[m.ray] / 360 + 1) % 1;
        });
    }

    // ---------- п.4.5: saturation C1 -> зеркальный сдвиг всех остальных, с
    // "отскоком" от границ 0/100 для каждого маркера независимо ----------
    function applySaturationDeltaFromC1(delta) {
        markers.forEach((mm, idx) => {
            if (idx === 0) {
                mm.sat = clamp01(mm.sat + delta);
                return;
            }
            const dir = mm.satDir ?? 1;
            let newVal = mm.sat + delta * dir;
            if (newVal < 0) {
                newVal = -newVal;
                mm.satDir = -dir;
            } else if (newVal > 1) {
                newVal = 2 - newVal;
                mm.satDir = -dir;
            }
            mm.sat = clamp01(newVal);
        });
    }

    // ---------- п.4.1/4.2/п.6: brightness C1 -> сдвиг всех остальных на ту же
    // величину; у вторичных цветов при выходе за порог — "переброс" по
    // таблице (пока только для Complementary, см. COMPLEMENTARY_JUMP_DOWN) ----------
    function applyBrightnessDeltaFromPrimary(delta) {
        const type = typeWidget?.value;
        const count = countWidget ? countWidget.value : markers.length;
        const offsets = rayOffsets();
        const rayCount = offsets.length;
        const data = paletteData(type);
        const lowThresh = data?.lowThresh ?? LOW_THRESH_DEFAULT;
        const jumpTable = data?.jumpDown ? data.jumpDown[count] : null;
        const alwaysJumpTo = data?.jumpTargetAlways; // Monochromatic: всегда 100%
        const hasJumpRule = !!jumpTable || alwaysJumpTo !== undefined;

        markers.forEach((mm, i) => {
            if (mm.gen === 0) {
                mm.val = clamp01(mm.val + delta);
                return;
            }
            const newVal = mm.val + delta;
            if (newVal <= lowThresh) {
                const secondaryIdx = i - rayCount;
                if (alwaysJumpTo !== undefined) {
                    mm.val = alwaysJumpTo;
                } else if (jumpTable && jumpTable[secondaryIdx] !== undefined) {
                    mm.val = jumpTable[secondaryIdx] / 100;
                } else {
                    // TODO: для Analogous и любых будущих типов без таблицы —
                    // просто клампим, ждём точных данных.
                    mm.val = clamp01(newVal);
                }
            } else if (newVal >= HIGH_THRESH && hasJumpRule) {
                mm.val = lowThresh;
            } else {
                mm.val = clamp01(newVal);
            }
        });
    }

    function drawWheelBackground() {
        if (wheelBgCache) {
            ctx.putImageData(wheelBgCache, 0, 0);
            return;
        }
        const img = ctx.createImageData(WHEEL_SIZE, WHEEL_SIZE);
        for (let y = 0; y < WHEEL_SIZE; y++) {
            for (let x = 0; x < WHEEL_SIZE; x++) {
                const dx = x - cx;
                const dy = y - cy;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const idx = (y * WHEEL_SIZE + x) * 4;
                if (dist > wheelRadius) {
                    img.data[idx + 3] = 0;
                    continue;
                }
                const angle = Math.atan2(dy, dx);
                const artisticHue = (angle / (Math.PI * 2) + 0.5 + 1) % 1;
                const sat = Math.min(1, dist / wheelRadius);
                const stdHue = artisticToStdHue01(artisticHue);
                const [r, g, b] = hsvToRgb(stdHue, sat, 1);
                img.data[idx] = r;
                img.data[idx + 1] = g;
                img.data[idx + 2] = b;
                img.data[idx + 3] = 255;
            }
        }
        wheelBgCache = img;
        ctx.putImageData(img, 0, 0);
    }

    function markerPos(m) {
        const angle = (m.hue - 0.5) * Math.PI * 2;
        const r = m.sat * wheelRadius;
        return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
    }

    function drawRays() {
        if (isCustom()) return;
        const offsets = rayOffsets();
        ctx.save();
        ctx.strokeStyle = "rgba(255,255,255,0.35)";
        ctx.lineWidth = 1;
        offsets.forEach((offDeg) => {
            const angleFrac = (rootAngleFrac + offDeg / 360 + 1) % 1;
            const angle = (angleFrac - 0.5) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + Math.cos(angle) * wheelRadius, cy + Math.sin(angle) * wheelRadius);
            ctx.stroke();
        });
        ctx.restore();
    }

    function drawMarkers() {
        drawWheelBackground();
        drawRays();
        markers.forEach((m, i) => {
            const { x, y } = markerPos(m);
            ctx.beginPath();
            ctx.arc(x, y, MARKER_RADIUS, 0, Math.PI * 2);
            ctx.fillStyle = markerHex(m);
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = m.gen === 0 ? "#ffffff" : "rgba(0,0,0,0.6)";
            ctx.stroke();

            ctx.font = "9px sans-serif";
            ctx.fillStyle = "rgba(0,0,0,0.55)";
            ctx.textAlign = "center";
            ctx.fillText(String(i + 1), x, y + 3);
        });
    }

    // ---------- панель образцов ----------
    // Разделено на "полную пересборку DOM" (buildSwatchRows — вызывается
    // только когда меняется количество/структура цветов) и "лёгкое
    // обновление" (syncSwatchRows — вызывается на каждый тик драга/слайдера).
    // Это важно: если пересоздавать <input type=range> прямо во время его
    // собственного drag'а, браузер обрывает захват указателя и ползунок
    // "залипает" после первого пикселя.

    function makeSliderRow(tagText, min, max, value, title) {
        const row = document.createElement("div");
        row.style.display = "flex";
        row.style.alignItems = "center";
        row.style.gap = "5px";

        const tag = document.createElement("span");
        tag.textContent = tagText;
        tag.style.width = "11px";
        tag.style.flex = "0 0 auto";
        tag.style.opacity = "0.65";
        tag.style.fontSize = "10px";

        const valueLabel = document.createElement("span");
        valueLabel.textContent = String(value);
        valueLabel.style.width = "26px";
        valueLabel.style.flex = "0 0 auto";
        valueLabel.style.fontSize = "10px";
        valueLabel.style.fontFamily = "monospace";
        valueLabel.style.textAlign = "right";
        valueLabel.style.opacity = "0.85";

        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = String(min);
        slider.max = String(max);
        slider.step = "1";
        slider.value = String(value);
        slider.title = title;
        slider.style.flex = "1 1 auto";
        slider.style.minWidth = "40px";
        slider.addEventListener("pointerdown", (e) => e.stopPropagation());
        slider.addEventListener("input", () => {
            valueLabel.textContent = slider.value;
        });

        row.appendChild(tag);
        row.appendChild(valueLabel);
        row.appendChild(slider);
        return { row, slider, valueLabel };
    }

    function createSwatchRow(i) {
        const m = markers[i];

        const wrap = document.createElement("div");
        wrap.style.display = "flex";
        wrap.style.alignItems = "stretch";
        wrap.style.gap = "8px";
        wrap.style.paddingBottom = "6px";
        wrap.style.borderBottom = "1px solid rgba(255,255,255,0.08)";

        const swatch = document.createElement("div");
        swatch.style.width = "48px";
        swatch.style.height = "48px";
        swatch.style.flex = "0 0 auto";
        swatch.style.borderRadius = "5px";
        swatch.style.border = "1px solid rgba(0,0,0,0.4)";

        const rightCol = document.createElement("div");
        rightCol.style.display = "flex";
        rightCol.style.flexDirection = "column";
        rightCol.style.gap = "2px";
        rightCol.style.flex = "1 1 auto";
        rightCol.style.minWidth = "0";
        rightCol.style.justifyContent = "center";

        const label = document.createElement("span");
        label.style.fontFamily = "monospace";
        label.style.fontSize = "12px";
        label.style.color = "var(--fg-color, #ccc)";
        label.style.marginBottom = "2px";

        const { row: hRow, slider: hSlider, valueLabel: hValueLabel } = makeSliderRow(
            "H", 0, 359, Math.round(m.hue * 360) % 360, "Hue"
        );
        const { row: sRow, slider: sSlider, valueLabel: sValueLabel } = makeSliderRow(
            "S", 0, 100, Math.round(m.sat * 100), "Saturation"
        );
        const { row: bRow, slider: bSlider, valueLabel: bValueLabel } = makeSliderRow(
            "B", 0, 100, Math.round(m.val * 100), "Brightness"
        );

        hSlider.addEventListener("input", () => {
            const newHueFrac = (Number(hSlider.value) % 360) / 360;
            if (isCustom()) {
                markers[i].hue = newHueFrac;
            } else {
                const offsets = rayOffsets();
                rootAngleFrac = (newHueFrac - offsets[markers[i].ray] / 360 + 1) % 1;
                reapplyRotation();
            }
            drawMarkers();
            syncSwatchRows();
            syncData();
        });

        sSlider.addEventListener("input", () => {
            const newVal = Number(sSlider.value) / 100;
            if (i === 0 && !isCustom()) {
                const delta = newVal - markers[0].sat;
                applySaturationDeltaFromC1(delta);
            } else {
                markers[i].sat = newVal;
            }
            drawMarkers();
            syncSwatchRows();
            syncData();
        });

        bSlider.addEventListener("input", () => {
            const newVal = Number(bSlider.value) / 100;
            if (isCustom()) {
                markers[i].val = newVal;
            } else if (markers[i].gen === 0) {
                const delta = newVal - markers[i].val;
                applyBrightnessDeltaFromPrimary(delta);
            } else {
                markers[i].val = newVal;
                forceCustomMode();
            }
            drawMarkers();
            syncSwatchRows();
            syncData();
        });

        rightCol.appendChild(label);
        rightCol.appendChild(hRow);
        rightCol.appendChild(sRow);
        rightCol.appendChild(bRow);
        wrap.appendChild(swatch);
        wrap.appendChild(rightCol);
        swatchesEl.appendChild(wrap);

        return { swatch, label, hSlider, sSlider, bSlider, hValueLabel, sValueLabel, bValueLabel };
    }

    function buildSwatchRows() {
        swatchesEl.innerHTML = "";
        rowRefs = markers.map((_, i) => createSwatchRow(i));
        syncSwatchRows();
        fitNodeHeight();
    }

    function syncSwatchRows() {
        markers.forEach((m, i) => {
            const ref = rowRefs[i];
            if (!ref) return;
            const hex = markerHex(m);
            ref.swatch.style.background = hex;
            ref.label.textContent = hex;

            const hDeg = Math.round(m.hue * 360) % 360;
            const sPct = Math.round(m.sat * 100);
            const bPct = Math.round(m.val * 100);

            ref.hSlider.value = String(hDeg);
            ref.sSlider.value = String(sPct);
            ref.bSlider.value = String(bPct);
            ref.hValueLabel.textContent = String(hDeg);
            ref.sValueLabel.textContent = String(sPct);
            ref.bValueLabel.textContent = String(bPct);
        });
    }

    function syncData() {
        const hexList = markers.map((m) => markerHex(m));
        if (dataWidget) {
            dataWidget.value = JSON.stringify(hexList);
        }
    }

    function refresh() {
        drawMarkers();
        buildSwatchRows();
        syncData();
    }

    function eventToCanvasXY(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = WHEEL_SIZE / rect.width;
        const scaleY = WHEEL_SIZE / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY,
        };
    }

    // ---- перетаскивание по кругу ----
    canvas.addEventListener("pointerdown", (e) => {
        const { x: mx, y: my } = eventToCanvasXY(e);
        let closest = -1;
        let closestDist = MARKER_RADIUS + 6;
        markers.forEach((m, i) => {
            const { x, y } = markerPos(m);
            const d = Math.hypot(mx - x, my - y);
            if (d < closestDist) {
                closestDist = d;
                closest = i;
            }
        });
        if (closest >= 0) {
            dragIndex = closest;
            canvas.style.cursor = "grabbing";
            canvas.setPointerCapture(e.pointerId);
            e.stopPropagation();
            e.preventDefault();
        }
    });

    canvas.addEventListener("pointermove", (e) => {
        if (dragIndex < 0) return;
        const { x: mx, y: my } = eventToCanvasXY(e);
        const dx = mx - cx;
        const dy = my - cy;
        const angle = Math.atan2(dy, dx);
        const pointerHue = (angle / (Math.PI * 2) + 0.5 + 1) % 1;

        if (isCustom()) {
            // Полностью свободный маркер: и угол, и радиус (saturation)
            // независимы от остальных.
            const dist = Math.min(wheelRadius, Math.hypot(dx, dy));
            markers[dragIndex].hue = pointerHue;
            markers[dragIndex].sat = wheelRadius === 0 ? 0 : dist / wheelRadius;
        } else {
            // Угол — всегда вращает весь пучок лучей разом (п.2).
            const m = markers[dragIndex];
            const offsets = rayOffsets();
            rootAngleFrac = (pointerHue - offsets[m.ray] / 360 + 1) % 1;
            reapplyRotation();

            // Радиус (saturation): только C1 (индекс 0) двигает всех
            // остальных зеркально с отскоком (п.4.5). Любой другой маркер —
            // независимо (п.4.4).
            const dist = Math.min(wheelRadius, Math.hypot(dx, dy));
            const targetSat = wheelRadius === 0 ? 0 : dist / wheelRadius;
            if (dragIndex === 0) {
                const delta = targetSat - m.sat;
                if (delta !== 0) applySaturationDeltaFromC1(delta);
            } else {
                m.sat = targetSat;
            }
        }

        drawMarkers();
        syncSwatchRows();
        syncData();
        e.stopPropagation();
        e.preventDefault();
    });

    function endDrag(e) {
        if (dragIndex < 0) return;
        dragIndex = -1;
        canvas.style.cursor = "grab";
        try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    // ---- реакция на нативные виджеты ноды ----
    if (countWidget) {
        const origCallback = countWidget.callback;
        countWidget.callback = function (value, ...rest) {
            const clamped = clampCount(value);
            if (clamped !== value) {
                this.value = clamped;
            }
            origCallback?.call(this, this.value, ...rest);
            initMarkers(this.value);
            refresh();
        };
    }

    if (typeWidget) {
        const origCallback = typeWidget.callback;
        typeWidget.callback = function (value, ...rest) {
            if (markers[0]) rootAngleFrac = markers[0].hue;

            origCallback?.call(this, value, ...rest);

            const min = MIN_COLORS[value] ?? 2;
            if (countWidget && countWidget.value < min) {
                countWidget.value = min;
            }
            initMarkers(countWidget ? countWidget.value : markers.length);
            refresh();
        };
    }

    // ---- п.1: нода должна вырасти под контент DOM-виджета ----
    const domWidget = node.addDOMWidget("rennart_color_wheel", "custom", container, {
        serialize: false,
    });

    function fitNodeHeight() {
        requestAnimationFrame(() => {
            const contentHeight = container.scrollHeight + 16;
            domWidget.computeSize = () => [WHEEL_SIZE + 24, contentHeight];
            const newSize = node.computeSize();
            node.setSize([Math.max(node.size[0], newSize[0]), newSize[1]]);
            node.setDirtyCanvas(true, true);
        });
    }

    if (typeof ResizeObserver !== "undefined") {
        new ResizeObserver(() => fitNodeHeight()).observe(container);
    }

    // ---- init ----
    initMarkers(clampCount(countWidget ? countWidget.value : 3));
    refresh();
}
