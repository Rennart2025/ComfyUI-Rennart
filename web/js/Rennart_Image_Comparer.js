// Rennart_Image_Comparer.js
// Фронтенд для ноды RennartImageComparer.
// Режимы: Slider (линия за курсором), Blink (переключение A/B по клику),
// Difference (наложение с blend-режимом "difference").
//
// Файл и путь: ComfyUI/custom_nodes/ComfyUI-Rennart/web/js/Rennart_Image_Comparer.js

import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const MODES = ["Slider", "Blink", "Difference"];
const CLICK_DRAG_TOLERANCE = 6; // px: движение больше — это уже drag, а не клик

function imageDataToUrl(data) {
    return api.apiURL(
        `/view?filename=${encodeURIComponent(data.filename)}` +
        `&type=${data.type}&subfolder=${data.subfolder}` +
        `${app.getPreviewFormatParam()}${app.getRandParam()}`
    );
}

function getModeWidget(node) {
    return node.widgets?.find((w) => w.name === "mode");
}

function getMode(node) {
    return getModeWidget(node)?.value || "Slider";
}

// Клик отслеживаем через rAF и app.canvas.pointer_is_down (проверенный паттерн rgthree),
// потому что надёжного node-level onMouseUp в litegraph нет.
function trackClick(node) {
    if (node._clickTracking) return;
    node._clickTracking = true;

    const step = () => {
        const candidate = node._clickCandidate;
        if (!candidate) {
            node._clickTracking = false;
            return;
        }
        if (!app.canvas.pointer_is_down) {
            // Кнопку отпустили: если не было drag'а и клик пришёлся на область картинки — моргаем.
            if (candidate.valid && getMode(node) === "Blink") {
                const widget = node.comparerWidget;
                if (widget && candidate.y > widget.imageAreaY && widget.getSelectedPair().length > 1) {
                    node.blinkIndex = node.blinkIndex === 1 ? 0 : 1;
                    node.setDirtyCanvas(true, false);
                }
            }
            node._clickCandidate = null;
            node._clickTracking = false;
            return;
        }
        // Кнопка ещё зажата: следим, не превратился ли клик в drag.
        const mouse = app.canvas.graph_mouse;
        const localX = mouse[0] - node.pos[0];
        const localY = mouse[1] - node.pos[1];
        if (Math.abs(localX - candidate.x) > CLICK_DRAG_TOLERANCE ||
            Math.abs(localY - candidate.y) > CLICK_DRAG_TOLERANCE) {
            candidate.valid = false;
        }
        requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

class RennartComparerWidget {
    constructor(name, node) {
        this.name = name;
        this.type = "rennart_comparer";
        this.node = node;
        this.value = { images: [] };
        this.hitAreas = {};      // кликабельные чипсы кадров батча
        this.imageAreaY = 0;     // y-координата начала области картинки (node-local)
        this.lastY = 0;
    }

    computeSize(width) {
        return [width, 20];
    }

    setImages(images) {
        this.value = { images };
        this.ensureImages();
    }

    // Лениво создаём HTMLImageElement для каждой записи (и после десериализации workflow).
    ensureImages() {
        for (const item of this.value.images) {
            if (!item.img) {
                const img = new Image();
                img.src = item.url;
                img.onload = () => this.node.setDirtyCanvas(true, true);
                item.img = img;
            }
        }
    }

    getSelectedPair() {
        const selected = this.value.images.filter((d) => d.selected);
        if (selected.length >= 2) return selected.slice(0, 2);
        if (selected.length === 1 && this.value.images.length > 1) {
            return [selected[0], this.value.images.find((d) => d !== selected[0])];
        }
        return selected.length ? selected : this.value.images.slice(0, 1);
    }

    selectImage(data) {
        const pair = this.getSelectedPair().slice(0, 2);
        while (pair.length < 2) pair.push(pair[0]);
        if (data.name.startsWith("A")) {
            pair[0] = data;
        } else if (data.name.startsWith("B")) {
            pair[1] = data;
        }
        for (const d of this.value.images) d.selected = false;
        pair[0].selected = true;
        pair[1].selected = true;
    }

    // Рамка вписывания картинки (сохранение пропорций) в область [y, nodeHeight].
    computeFrame(img, nodeWidth, areaY, areaHeight) {
        const imageAspect = img.naturalWidth / img.naturalHeight;
        const widgetAspect = nodeWidth / areaHeight;
        let targetWidth, targetHeight, offsetX;
        if (imageAspect > widgetAspect) {
            targetWidth = nodeWidth;
            targetHeight = nodeWidth / imageAspect;
            offsetX = 0;
        } else {
            targetHeight = areaHeight;
            targetWidth = areaHeight * imageAspect;
            offsetX = (nodeWidth - targetWidth) / 2;
        }
        return {
            x: (nodeWidth - targetWidth) / 2,
            y: areaY + (areaHeight - targetHeight) / 2,
            width: targetWidth,
            height: targetHeight,
            offsetX,
        };
    }

    drawImageFit(ctx, image, areaY, frame = null, cropX = null) {
        const img = image?.img;
        if (!img?.naturalWidth || !img?.naturalHeight) return null;

        const [nodeWidth, nodeHeight] = this.node.size;
        const areaHeight = nodeHeight - areaY;
        const f = frame || this.computeFrame(img, nodeWidth, areaY, areaHeight);

        ctx.save();
        if (cropX != null) {
            const destWidth = cropX - f.x;
            if (destWidth <= 0) { ctx.restore(); return f; }
            ctx.beginPath();
            ctx.rect(f.x, f.y, Math.min(destWidth, f.width), f.height);
            ctx.clip();
        }
        ctx.drawImage(img, f.x, f.y, f.width, f.height);

        // Вертикальная линия разделения в режиме Slider.
        if (cropX != null && cropX >= f.x && cropX <= f.x + f.width) {
            ctx.beginPath();
            ctx.moveTo(cropX, f.y);
            ctx.lineTo(cropX, f.y + f.height);
            const prev = ctx.globalCompositeOperation;
            ctx.globalCompositeOperation = "difference";
            ctx.strokeStyle = "rgba(255,255,255,1)";
            ctx.stroke();
            ctx.globalCompositeOperation = prev;
        }
        ctx.restore();
        return f;
    }

    drawLabel(ctx, text, x, y) {
        ctx.save();
        ctx.font = "12px Arial";
        const w = ctx.measureText(text).width + 12;
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.beginPath();
        ctx.roundRect(x, y, w, 18, 4);
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(text, x + 6, y + 9);
        ctx.restore();
    }

    draw(ctx, node, widgetWidth, y, widgetHeight) {
        this.lastY = y;
        this.hitAreas = {};
        this.ensureImages();

        const images = this.value.images;
        const [nodeWidth, nodeHeight] = node.size;
        let areaY = y;

        // Чипсы выбора кадров батча (только если картинок больше одной).
        if (images.length > 1) {
            ctx.save();
            ctx.textAlign = "left";
            ctx.textBaseline = "top";
            ctx.font = "14px Arial";
            const spacing = 8;
            const drawData = [];
            let x = 0;
            for (const item of images) {
                const w = ctx.measureText(item.name).width;
                drawData.push({ item, width: w });
                x += w + spacing;
            }
            x = (nodeWidth - (x - spacing)) / 2;
            for (const d of drawData) {
                ctx.fillStyle = d.item.selected
                    ? "rgba(180,180,180,1)"
                    : "rgba(180,180,180,0.5)";
                ctx.fillText(d.item.name, x, areaY + 3);
                this.hitAreas[d.item.name] = { bounds: [x, areaY, d.width, 18], data: d.item };
                x += d.width + spacing;
            }
            ctx.restore();
            areaY += 22;
        }

        this.imageAreaY = areaY;

        const pair = this.getSelectedPair();
        if (!pair.length || !pair[0]?.img?.naturalWidth) {
            ctx.save();
            ctx.fillStyle = "rgba(180,180,180,0.5)";
            ctx.font = "13px Arial";
            ctx.textAlign = "center";
            ctx.fillText("Queue a prompt to compare images", nodeWidth / 2, areaY + 20);
            ctx.restore();
            return;
        }

        const mode = getMode(node);

        if (mode === "Blink") {
            const current = pair[Math.min(node.blinkIndex || 0, pair.length - 1)];
            this.drawImageFit(ctx, current, areaY);
            if (pair.length > 1) {
                this.drawLabel(ctx, current.name, 8, areaY + 8);
            }
        } else if (mode === "Difference") {
            // Рамку берём по изображению A и в неё же рисуем B — иначе difference
            // при разных пропорциях теряет смысл.
            const frame = this.drawImageFit(ctx, pair[0], areaY);
            if (frame && pair[1]?.img?.naturalWidth) {
                ctx.save();
                ctx.globalCompositeOperation = "difference";
                ctx.drawImage(pair[1].img, frame.x, frame.y, frame.width, frame.height);
                ctx.restore();
            }
            if (pair.length > 1) {
                this.drawLabel(ctx, `|${pair[0].name} − ${pair[1].name}|`, 8, areaY + 8);
            }
        } else {
            // Slider: A целиком, поверх — B, обрезанный по позиции курсора.
            this.drawImageFit(ctx, pair[0], areaY);
            if (node.isPointerOver && pair[1]) {
                this.drawImageFit(ctx, pair[1], areaY, null, node.pointerOverPos[0]);
            }
        }
    }

    // Сериализация без HTMLImageElement (иначе workflow не сохранится).
    serializeValue(node, index) {
        return {
            images: this.value.images.map((d) => ({
                name: d.name,
                selected: d.selected,
                url: d.url,
            })),
        };
    }
}

app.registerExtension({
    name: "Rennart.ImageComparer",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RennartImageComparer") return;

        // --- Создание ноды: виджет режима + canvas-виджет сравнения ---
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            this.blinkIndex = 0;
            this.isPointerOver = false;
            this.pointerOverPos = [0, 0];

            this.addWidget("combo", "mode", "Slider", () => {
                this.setDirtyCanvas(true, true);
            }, { values: MODES });

            this.comparerWidget = this.addCustomWidget(
                new RennartComparerWidget("rennart_comparer", this)
            );

            const size = this.computeSize();
            this.setSize([Math.max(512, size[0]), Math.max(460, size[1])]);
            this.setDirtyCanvas(true, true);
        };

        // --- Результат выполнения: собираем список картинок A/B ---
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (output) {
            onExecuted?.apply(this, arguments);
            if (!this.comparerWidget) return;

            const aImages = output?.a_images || [];
            const bImages = output?.b_images || [];
            const multiple = aImages.length + bImages.length > 2;
            const images = [];

            aImages.forEach((d, i) => images.push({
                name: aImages.length > 1 || multiple ? `A${i + 1}` : "A",
                selected: i === 0,
                url: imageDataToUrl(d),
            }));
            bImages.forEach((d, i) => images.push({
                name: bImages.length > 1 || multiple ? `B${i + 1}` : "B",
                selected: i === 0,
                url: imageDataToUrl(d),
            }));

            this.comparerWidget.setImages(images);
            this.blinkIndex = 0;
            this.setDirtyCanvas(true, true);
        };

        // --- Мышь ---
        const onMouseDown = nodeType.prototype.onMouseDown;
        nodeType.prototype.onMouseDown = function (event, pos, canvas) {
            const r = onMouseDown?.apply(this, arguments);
            const widget = this.comparerWidget;

            // 1) Чипсы кадров батча — приоритет выше всего.
            if (widget) {
                for (const key of Object.keys(widget.hitAreas)) {
                    const area = widget.hitAreas[key];
                    const [x, y, w, h] = area.bounds;
                    if (pos[0] >= x && pos[0] <= x + w && pos[1] >= y && pos[1] <= y + h) {
                        widget.selectImage(area.data);
                        this.setDirtyCanvas(true, true);
                        return true; // consume: не начинаем drag ноды
                    }
                }
            }

            // 2) Кандидат на клик для режима Blink (подтвердится на отпускании кнопки).
            this._clickCandidate = { x: pos[0], y: pos[1], valid: true };
            trackClick(this);
            return r;
        };

        const onMouseEnter = nodeType.prototype.onMouseEnter;
        nodeType.prototype.onMouseEnter = function (event) {
            onMouseEnter?.apply(this, arguments);
            this.isPointerOver = true;
            this.setDirtyCanvas(true, false);
        };

        const onMouseLeave = nodeType.prototype.onMouseLeave;
        nodeType.prototype.onMouseLeave = function (event) {
            onMouseLeave?.apply(this, arguments);
            this.isPointerOver = false;
            this.setDirtyCanvas(true, false);
        };

        const onMouseMove = nodeType.prototype.onMouseMove;
        nodeType.prototype.onMouseMove = function (event, pos, canvas) {
            onMouseMove?.apply(this, arguments);
            this.pointerOverPos = [...pos];
            if (getMode(this) === "Slider") {
                this.setDirtyCanvas(true, false);
            }
        };
    },
});
