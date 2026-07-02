import numpy as np

from saidao_audio.speaker_db import SpeakerDatabase


def test_match_returns_best_speaker_when_score_meets_threshold():
    db = SpeakerDatabase(
        speakers={
            "alice": np.array([1.0, 0.0, 0.0], dtype=np.float32),
            "bob": np.array([0.0, 1.0, 0.0], dtype=np.float32),
        },
        threshold=0.75,
    )

    result = db.match(np.array([0.9, 0.1, 0.0], dtype=np.float32))

    assert result.name == "alice"
    assert result.known is True
    assert result.score > 0.99


def test_match_returns_unknown_when_best_score_is_below_threshold():
    db = SpeakerDatabase(
        speakers={"alice": np.array([1.0, 0.0], dtype=np.float32)},
        threshold=0.9,
    )

    result = db.match(np.array([0.1, 1.0], dtype=np.float32))

    assert result.name == "unknown"
    assert result.known is False
    assert result.best_name == "alice"


def test_from_enrollments_averages_and_normalizes_embeddings():
    db = SpeakerDatabase.from_enrollments(
        {
            "alice": [
                np.array([1.0, 0.0], dtype=np.float32),
                np.array([1.0, 1.0], dtype=np.float32),
            ]
        },
        threshold=0.6,
    )

    vectors = db.speakers["alice"]

    assert len(vectors) == 2
    assert all(np.isclose(np.linalg.norm(vector), 1.0) for vector in vectors)


def test_match_uses_best_vector_for_each_speaker():
    db = SpeakerDatabase(
        speakers={
            "alice": [
                np.array([1.0, 0.0], dtype=np.float32),
                np.array([0.0, 1.0], dtype=np.float32),
            ],
            "bob": [np.array([0.7, 0.7], dtype=np.float32)],
        },
        threshold=0.95,
    )

    result = db.match(np.array([0.0, 0.95], dtype=np.float32))

    assert result.name == "alice"
    assert result.known is True
    assert result.score > 0.99


def test_load_supports_legacy_single_vector_format(tmp_path):
    path = tmp_path / "speakers.json"
    path.write_text(
        """
        {
          "threshold": 0.7,
          "speakers": {
            "alice": [1.0, 0.0]
          }
        }
        """,
        encoding="utf-8",
    )

    db = SpeakerDatabase.load(path)

    assert len(db.speakers["alice"]) == 1
    assert db.match(np.array([1.0, 0.0], dtype=np.float32)).name == "alice"


def test_load_supports_utf8_bom_file(tmp_path):
    path = tmp_path / "speakers.json"
    path.write_text(
        """
        {
          "threshold": 0.78,
          "speakers": {
            "alice": [[1.0, 0.0]]
          }
        }
        """,
        encoding="utf-8-sig",
    )

    db = SpeakerDatabase.load(path)

    assert db.match(np.array([1.0, 0.0], dtype=np.float32)).name == "alice"
