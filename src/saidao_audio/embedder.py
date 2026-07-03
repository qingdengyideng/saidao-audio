from __future__ import annotations

from pathlib import Path

import numpy as np

from .logging_config import get_logger

logger = get_logger(__name__)


class VoiceEmbedder:
    def __init__(self) -> None:
        from resemblyzer import VoiceEncoder

        logger.debug("正在加载 resemblyzer VoiceEncoder 模型")
        self._encoder = VoiceEncoder()
        logger.debug("VoiceEncoder 模型加载完成")

    def embed_file(self, path: str | Path) -> np.ndarray:
        from resemblyzer import preprocess_wav

        wav = preprocess_wav(Path(path))
        return self._encoder.embed_utterance(wav).astype(np.float32)
