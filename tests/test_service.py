from pathlib import Path

import numpy as np

from saidao_audio.service import StreamJobManager, StreamJobRequest, process_chunk
from saidao_audio.speaker_db import SpeakerDatabase


class FakeEmbedder:
    def embed_file(self, path: Path) -> np.ndarray:
        return np.array([1.0, 0.0], dtype=np.float32)


def test_stream_job_request_defaults_delete_processed_chunks():
    request = StreamJobRequest(
        stream_url="https://example.com/live.flv",
        callback_url="https://callback.example.com/speaker",
    )

    assert request.chunk_seconds == 5
    assert request.delete_chunks is True
    assert request.chunk_dir is None


def test_prepare_job_assigns_unique_chunk_dir_when_not_provided(tmp_path):
    manager = StreamJobManager(chunk_root=tmp_path)

    first = manager.prepare_job(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        )
    )
    second = manager.prepare_job(
        StreamJobRequest(
            stream_url="https://example.com/live2.flv",
            callback_url="https://callback.example.com/speaker",
        )
    )

    assert first.request.chunk_dir != second.request.chunk_dir
    assert first.request.chunk_dir.parent == tmp_path
    assert second.request.chunk_dir.parent == tmp_path


def test_upsert_returns_existing_job_when_same_job_id_and_stream_url(tmp_path):
    manager = StreamJobManager(chunk_root=tmp_path)
    started = []

    def fake_start_thread(job):
        started.append(job.id)

    manager._start_thread = fake_start_thread

    first = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )
    second = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )

    assert first is second
    assert started == ["room-1"]
    assert second.request.stream_url == "https://example.com/live1.flv"


def test_upsert_restarts_inactive_job_even_when_stream_url_is_same(tmp_path):
    manager = StreamJobManager(chunk_root=tmp_path)
    started = []

    def fake_start_thread(job):
        started.append(job.id)

    manager._start_thread = fake_start_thread

    first = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )
    first.status = "failed"
    first.error = "old failure"

    second = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )

    assert first is not second
    assert second.id == "room-1"
    assert second.request.stream_url == "https://example.com/live1.flv"
    assert started == ["room-1", "room-1"]


def test_upsert_replaces_existing_job_when_same_job_id_and_new_stream_url(tmp_path):
    manager = StreamJobManager(chunk_root=tmp_path)
    started = []
    stopped = []

    def fake_start_thread(job):
        started.append((job.id, job.request.stream_url))

    def fake_stop(job_id):
        stopped.append(job_id)
        return True

    manager._start_thread = fake_start_thread
    manager.stop = fake_stop

    first = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live1.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )
    second = manager.upsert(
        StreamJobRequest(
            stream_url="https://example.com/live2.flv",
            callback_url="https://callback.example.com/speaker",
        ),
        job_id="room-1",
    )

    assert first is not second
    assert second.id == "room-1"
    assert second.request.stream_url == "https://example.com/live2.flv"
    assert stopped == ["room-1"]
    assert started == [
        ("room-1", "https://example.com/live1.flv"),
        ("room-1", "https://example.com/live2.flv"),
    ]


def test_process_chunk_posts_callback_and_deletes_chunk(tmp_path):
    chunk = tmp_path / "chunk_000001.wav"
    chunk.write_bytes(b"fake wav content")
    db = SpeakerDatabase(
        speakers={"alice": np.array([1.0, 0.0], dtype=np.float32)},
        threshold=0.7,
    )
    sent_payloads = []

    event = process_chunk(
        chunk=chunk,
        db=db,
        embedder=FakeEmbedder(),
        job_id="job-1",
        callback_url="https://callback.example.com/speaker",
        has_speech_func=lambda path: True,
        post_callback_func=lambda url, payload: sent_payloads.append((url, payload)),
        delete_chunk=True,
    )

    assert event["status"] == "speech"
    assert event["speaker"] == "alice"
    assert event["job_id"] == "job-1"
    assert sent_payloads == [("https://callback.example.com/speaker", event)]
    assert not chunk.exists()


def test_process_chunk_deletes_silent_chunk_without_callback(tmp_path):
    chunk = tmp_path / "chunk_000002.wav"
    chunk.write_bytes(b"fake wav content")
    db = SpeakerDatabase(
        speakers={"alice": np.array([1.0, 0.0], dtype=np.float32)},
        threshold=0.7,
    )
    sent_payloads = []

    event = process_chunk(
        chunk=chunk,
        db=db,
        embedder=FakeEmbedder(),
        job_id="job-1",
        callback_url="https://callback.example.com/speaker",
        has_speech_func=lambda path: False,
        post_callback_func=lambda url, payload: sent_payloads.append((url, payload)),
        delete_chunk=True,
    )

    assert event["status"] == "silence"
    assert sent_payloads == []
    assert not chunk.exists()
