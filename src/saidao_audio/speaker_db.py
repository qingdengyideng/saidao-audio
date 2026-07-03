from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MatchResult:
    name: str
    score: float
    known: bool
    best_name: str | None = None


def normalize(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        raise ValueError("embedding vector must not be zero")
    return values / norm


class SpeakerDatabase:
    def __init__(
        self,
        speakers: dict[str, np.ndarray | Iterable[np.ndarray]],
        threshold: float = 0.78,
    ):
        if not speakers:
            raise ValueError("speaker database requires at least one speaker")
        self.speakers = {
            name: self._normalize_vectors(vectors)
            for name, vectors in speakers.items()
        }
        self.threshold = threshold

    @staticmethod
    def _normalize_vectors(vectors: np.ndarray | Iterable[np.ndarray]) -> list[np.ndarray]:
        values = np.asarray(vectors, dtype=np.float32)
        if values.ndim == 1:
            return [normalize(values)]
        if values.ndim == 2:
            return [normalize(vector) for vector in values]
        normalized = [normalize(np.asarray(vector, dtype=np.float32)) for vector in vectors]
        if normalized:
            return normalized
        raise ValueError("speaker must have at least one embedding")

    @classmethod
    def from_enrollments(
        cls,
        enrollments: dict[str, Iterable[np.ndarray]],
        threshold: float = 0.78,
    ) -> "SpeakerDatabase":
        speakers: dict[str, list[np.ndarray]] = {}
        for name, vectors in enrollments.items():
            normalized = [normalize(vector) for vector in vectors]
            if not normalized:
                raise ValueError(f"speaker {name!r} has no embeddings")
            speakers[name] = normalized
        return cls(speakers=speakers, threshold=threshold)

    def match(self, embedding: np.ndarray) -> MatchResult:
        probe = normalize(embedding)
        best_name: str | None = None
        best_score = -1.0

        for name, vectors in self.speakers.items():
            score = max(float(np.dot(probe, vector)) for vector in vectors)
            if score > best_score:
                best_name = name
                best_score = score

        if best_name is not None and best_score >= self.threshold:
            return MatchResult(
                name=best_name,
                score=best_score,
                known=True,
                best_name=best_name,
            )

        return MatchResult(
            name="unknown",
            score=best_score,
            known=False,
            best_name=best_name,
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "threshold": self.threshold,
            "speakers": {
                name: [
                    vector.astype(float).tolist()
                    for vector in vectors
                ]
                for name, vectors in self.speakers.items()
            },
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("声纹数据库已保存 path=%s speakers=%d", target, len(self.speakers))

    @classmethod
    def load(cls, path: str | Path) -> "SpeakerDatabase":
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        speakers = {
            name: np.array(vector, dtype=np.float32)
            for name, vector in payload["speakers"].items()
        }
        logger.debug("声纹数据库已加载 path=%s speakers=%d threshold=%.2f", path, len(speakers), payload.get("threshold", 0.78))
        return cls(speakers=speakers, threshold=float(payload.get("threshold", 0.78)))
