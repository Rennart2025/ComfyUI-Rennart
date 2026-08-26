import { app } from "/scripts/app.js";

// Вспомогательная функция позиционирования инпута ровно по координатам ноды
function positionElementAtNode(node, element) {
    const canvasEl = app.canvas.ds.element;
    const canvasBox = canvasEl.getBoundingClientRect();

    // Текущий зум и сдвиг холста
    const zoom = app.canvas.ds.scale;
    const offset = app.canvas.ds.offset;

    const [nodeX, nodeY] = node.pos;

    // Вычисляем абсолютные координаты ноды на экране
    let screenX = canvasBox.left + (nodeX + offset[0]) * zoom;
    let screenY = canvasBox.top + (nodeY + offset[1]) * zoom;

    element.style.position = "fixed";
    element.style.zIndex = "99999";
    element.style.left = `${screenX}px`;
    element.style.top = `${screenY}px`;
    element.style.width = `${node.size[0] * zoom}px`;
    element.style.height = `${node.size[1] * zoom}px`;
}

// Вынесенная функция привязки кнопки к виджету
function setupColorPickerButton(node) {
    const isTargetNode = 
        node.comfyClass === "RennartColorPalette" || 
        node.comfyClass === "RennartColorPicker" || 
        node.title?.includes("🎨");

    if (isTargetNode) {
        const widget = node.widgets?.find((w) => w.name === "base_color" || w.name === "color");
        
        // Защита от создания дубликатов кнопки
        const hasPickerButton = node.widgets?.some((w) => w.name === "Выбрать цвет 🎨");

        if (widget && !hasPickerButton) {
            node.addWidget("button", "Выбрать цвет 🎨", null, (b, canvas, n, pos) => {
                // 1. Удаляем предыдущий инпут, если он остался
                const existingInput = document.getElementById("rennart-temp-color-picker");
                if (existingInput) {
                    existingInput.remove();
                }

                // 2. Создаем нативный инпут цвета
                const input = document.createElement("input");
                input.id = "rennart-temp-color-picker";
                input.type = "color";
                input.value = widget.value || "#3498DB";
                
                input.style.opacity = "0";
                input.style.pointerEvents = "auto";
                input.style.cursor = "pointer";

                // 3. Точно позиционируем его прямо на ноду
                positionElementAtNode(node, input);
                document.body.appendChild(input);

                // 4. Синхронизируем цвет при выборе в градиентной палитре
                input.addEventListener("input", (e) => {
                    widget.value = e.target.value.toUpperCase();
                    if (node.graph) {
                        node.graph._version++;
                    }
                    app.canvas.setDirty(true, true);
                });

                // 5. Автоматическое удаление при завершении выбора
                const cleanup = () => {
                    if (input && input.parentNode) {
                        input.remove();
                    }
                };

                input.addEventListener("change", cleanup);
                input.addEventListener("blur", cleanup);

                // 6. Запускаем вызов палитры
                requestAnimationFrame(() => {
                    input.focus();
                    input.click();
                });
            });
        }
    }
}

app.registerExtension({
    name: "Rennart.ColorPicker",
    async nodeCreated(node) {
        setupColorPickerButton(node);
    },
    async loadedGraphNode(node) {
        setupColorPickerButton(node);
    }
});