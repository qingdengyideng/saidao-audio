import wave
from pathlib import Path

import numpy as np

from saidao_audio.vad import has_speech


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def test_has_speech_rejects_silent_audio(tmp_path):
    path = tmp_path / "silence.wav"
    write_wav(path, np.zeros(16000, dtype=np.float32))

    assert has_speech(path, min_speech_ratio=0.1) is False


def test_has_speech_accepts_voice_like_tone(tmp_path):
    path = tmp_path / "tone.wav"
    t = np.linspace(0, 1, 16000, endpoint=False)
    samples = 0.4 * np.sin(2 * np.pi * 180 * t)
    write_wav(path, samples.astype(np.float32))

    assert has_speech(path, min_speech_ratio=0.01, aggressiveness=0) is True
