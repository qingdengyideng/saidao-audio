from __future__ import annotations

from pathlib import Path
import wave

import numpy as np

from .logging_config import get_logger

logger = get_logger(__name__)

try:
    import webrtcvad
except ImportError:  # pragma: no cover - depends on local installation
    webrtcvad = None
    logger.warning("webrtcvad 未安装，VAD 将降级为基于能量的检测方式")


def _read_pcm16_mono(path: str | Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        if channels != 1 or sample_width != 2:
            raise ValueError("VAD input must be mono PCM16 wav")
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError("VAD input sample rate must be 8k, 16k, 32k, or 48k")
        return wav.readframes(wav.getnframes()), sample_rate


def has_speech(
    path: str | Path,
    min_speech_ratio: float = 0.12,
    aggressiveness: int = 2,
    frame_ms: int = 30,
    energy_threshold: float = 0.015,
) -> bool:
    pcm, sample_rate = _read_pcm16_mono(path)
    bytes_per_sample = 2
    frame_size = int(sample_rate * frame_ms / 1000) * bytes_per_sample
    if frame_size <= 0:
        raise ValueError("frame size must be positive")

    if webrtcvad is None:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(samples * samples)))
        return rms >= energy_threshold

    vad = webrtcvad.Vad(aggressiveness)
    total = 0
    voiced = 0
    for offset in range(0, len(pcm) - frame_size + 1, frame_size):
        frame = pcm[offset : offset + frame_size]
        total += 1
        if vad.is_speech(frame, sample_rate):
            voiced += 1

    if total == 0:
        return False
    return (voiced / total) >= min_speech_ratio
