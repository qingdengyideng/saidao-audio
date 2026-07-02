from __future__ import annotations

from pathlib import Path

import numpy as np


class VoiceEmbedder:
    def __init__(self) -> None:
        from resemblyzer import VoiceEncoder

        self._encoder = VoiceEncoder()

    def embed_file(self, path: str | Path) -> np.ndarray:
        from resemblyzer import preprocess_wav

        wav = preprocess_wav(Path(path))
        return self._encoder.embed_utterance(wav).astype(np.float32)
