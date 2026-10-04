"""
Rennart nodes for Comfyui
Файл и путь: ComfyUI\custom_nodes\ComfyUI-Rennart\Rennart_Audio_Concatenate.py
Категория: Rennart/Audio
"""

import torch


def _create_silence(sample_rate, duration_seconds, channels, dtype, device):
    """Создаёт тензор тишины нужной длительности."""
    num_samples = int(sample_rate * duration_seconds)
    if num_samples <= 0:
        return None
    # Форма: [batch=1, channels, samples]
    return torch.zeros((1, channels, num_samples), dtype=dtype, device=device)


class RennartAudioConcatenate:
    @classmethod
    def INPUT_TYPES(cls):
        # Генерируем имена всех возможных входов для валидации ComfyUI
        all_options = [f"audio_{i}" for i in range(1, 31)]
        return {
            "required": {
                "number_of_inputs": ("INT", {
                    "default": 2, "min": 2, "max": 30, "step": 1,
                    "tooltip": "Количество аудио для склейки (от 2 до 30)."
                }),
                "pause_seconds": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 60.0, "step": 0.1,
                    "tooltip": "Длительность паузы между склейками в секундах (0 = без пауз)."
                }),
                "audio_1": ("AUDIO",),
                "audio_2": ("AUDIO",),
            },
            "optional": {f"audio_{i}": ("AUDIO",) for i in range(3, 31)},
        }

    CATEGORY = "Rennart/Audio"
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "concatenate"
    DESCRIPTION = "Concatenates multiple audio inputs in order (audio_1 → audio_2 → ...) with optional silence between them."

    def concatenate(self, number_of_inputs, pause_seconds, **kwargs):
        audio_list = []
        for i in range(1, number_of_inputs + 1):
            value = kwargs.get(f"audio_{i}")
            if value is not None:
                audio_list.append(value)

        if not audio_list:
            raise ValueError("[Rennart] Не подано ни одного аудио на вход.")

        if len(audio_list) == 1:
            return (audio_list[0],)

        # Проверка sample_rate
        sample_rates = set(a["sample_rate"] for a in audio_list)
        if len(sample_rates) > 1:
            raise ValueError(
                f"[Rennart] Частоты дискретизации не совпадают: {sample_rates}."
            )
        sample_rate = sample_rates.pop()

        # Проверка числа каналов
        channels = set(a["waveform"].shape[1] for a in audio_list)
        if len(channels) > 1:
            raise ValueError(
                f"[Rennart] Число каналов не совпадает: {channels}."
            )
        num_channels = channels.pop()

        # Берём dtype и device из первого аудио
        first_waveform = audio_list[0]["waveform"]
        dtype = first_waveform.dtype
        device = first_waveform.device

        # Создаём тишину (если пауза > 0)
        silence = None
        if pause_seconds > 0:
            silence = _create_silence(
                sample_rate=sample_rate,
                duration_seconds=pause_seconds,
                channels=num_channels,
                dtype=dtype,
                device=device,
            )

        # Склеиваем: audio_1 + тишина + audio_2 + тишина + audio_3 + ...
        parts = []
        for idx, audio in enumerate(audio_list):
            parts.append(audio["waveform"])
            # Пауза добавляется между аудио, но не после последнего
            if idx < len(audio_list) - 1 and silence is not None:
                parts.append(silence)

        concatenated = torch.cat(parts, dim=2)

        return ({"waveform": concatenated, "sample_rate": sample_rate},)


# ==============================================
# Регистрация ноды
# ==============================================

NODE_CLASS_MAPPINGS = {
    "RennartAudioConcatenate": RennartAudioConcatenate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartAudioConcatenate": "🎵 Rennart Audio Concatenate",
}