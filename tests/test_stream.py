import threading
import time

from saidao_audio.stream import (
    build_ffmpeg_segment_command,
    clean_chunk_dir,
    iter_completed_chunks,
)


def test_build_ffmpeg_segment_command_accepts_signed_flv_url():
    url = (
        "https://d1.example.com/live-bvc/276291/live_room_2500.flv"
        "?expires=1782978290&qn=250&sign=abc123&media_type=0"
    )

    command = build_ffmpeg_segment_command(
        url=url,
        output_pattern="data/chunks/chunk_%06d.wav",
        chunk_seconds=10,
    )

    assert url in command
    assert command[command.index("-i") + 1] == url
    assert "-f" in command
    assert "segment" in command


def test_iter_completed_chunks_skips_empty_files(tmp_path):
    empty = tmp_path / "chunk_000000.wav"
    empty.write_bytes(b"")

    results = []

    def collect_one():
        for chunk in iter_completed_chunks(
            tmp_path,
            poll_seconds=0.01,
            stable_seconds=0.01,
        ):
            results.append(chunk)
            break

    thread = threading.Thread(target=collect_one, daemon=True)
    thread.start()
    time.sleep(0.05)

    valid = tmp_path / "chunk_000001.wav"
    valid.write_bytes(b"not-empty")
    thread.join(timeout=1)

    assert results == [valid]


def test_clean_chunk_dir_removes_old_chunks_only(tmp_path):
    old_chunk = tmp_path / "chunk_000000.wav"
    old_chunk.write_bytes(b"old")
    other = tmp_path / "keep.txt"
    other.write_text("keep", encoding="utf-8")

    clean_chunk_dir(tmp_path)

    assert not old_chunk.exists()
    assert other.exists()
