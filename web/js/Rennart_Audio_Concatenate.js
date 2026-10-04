// Rennart_Audio_Concatenate.js
import { app } from "../../../scripts/app.js";

app.registerExtension({
    name: "Rennart.AudioConcatenate",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "RennartAudioConcatenate") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;

            nodeType.prototype.onNodeCreated = function() {
                if (onNodeCreated) {
                    onNodeCreated.apply(this, arguments);
                }

                if (!this.inputs) this.inputs = [];
                if (!this.widgets) this.widgets = [];

                // Функция для обновления динамических входов
                const updateInputs = () => {
                    const numWidget = this.widgets.find(w => w.name === "number_of_inputs");
                    if (!numWidget) return;

                    const num = Math.max(2, parseInt(numWidget.value) || 2);

                    // Оставляем только первые два обязательных входа
                    const staticInputs = this.inputs.filter(inp => 
                        inp.name === "audio_1" || inp.name === "audio_2"
                    );

                    // Создаём динамические входы для audio_3..audio_N
                    const dynamicInputs = [];
                    for (let i = 3; i <= num; i++) {
                        const name = `audio_${i}`;
                        let existing = this.inputs.find(inp => inp.name === name);
                        if (existing) {
                            dynamicInputs.push(existing);
                        } else {
                            dynamicInputs.push({
                                name: name,
                                type: "AUDIO",
                                link: null
                            });
                        }
                    }

                    // Объединяем статические и динамические входы
                    this.inputs = [...staticInputs, ...dynamicInputs];

                    // Обновляем размер ноды
                    this.setSize(this.computeSize());
                    app.graph.setDirtyCanvas(true, true);
                };

                // Перемещаем виджет number_of_inputs наверх и вешаем обработчик
                const numWidget = this.widgets.find(w => w.name === "number_of_inputs");
                if (numWidget) {
                    this.widgets = [numWidget, ...this.widgets.filter(w => w !== numWidget)];
                    const origCallback = numWidget.callback;
                    numWidget.callback = function() {
                        if (origCallback) {
                            origCallback.apply(this, arguments);
                        }
                        updateInputs();
                    };
                }

                // Первоначальная инициализация
                setTimeout(updateInputs, 10);
            };

            // Обработчик загрузки сохранённого workflow
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(nodeData) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                setTimeout(() => {
                    const numWidget = this.widgets.find(w => w.name === "number_of_inputs");
                    if (numWidget) {
                        const num = Math.max(2, parseInt(numWidget.value) || 2);
                        const staticInputs = this.inputs.filter(inp => 
                            inp.name === "audio_1" || inp.name === "audio_2"
                        );
                        const dynamicInputs = [];
                        for (let i = 3; i <= num; i++) {
                            const name = `audio_${i}`;
                            let existing = this.inputs.find(inp => inp.name === name);
                            if (existing) {
                                dynamicInputs.push(existing);
                            } else {
                                dynamicInputs.push({
                                    name: name,
                                    type: "AUDIO",
                                    link: null
                                });
                            }
                        }
                        this.inputs = [...staticInputs, ...dynamicInputs];
                        this.setSize(this.computeSize());
                        app.graph.setDirtyCanvas(true, true);
                    }
                }, 10);
            };
        }
    }
});