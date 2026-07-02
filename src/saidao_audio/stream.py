from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import subprocess
import time


def clean_chunk_dir(output_dir: str | Path) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for path in root.glob("chunk_*.wav"):
        path.unlink(missing_ok=True)


def build_ffmpeg_segment_command(
    url: str,
    output_pattern: str,
    chunk_seconds: int = 5,
) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        url,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        output_pattern,
    ]


def run_ffmpeg_segmenter(
    url: str,
    output_dir: str | Path,
    chunk_seconds: int = 5,
    clean: bool = True,
) -> subprocess.Popen:
    target = Path(output_dir)
    if clean:
        clean_chunk_dir(target)
    else:
        target.mkdir(parents=True, exist_ok=True)
    output_pattern = str(target / "chunk_%06d.wav")
    command = build_ffmpeg_segment_command(
        url=url,
        output_pattern=output_pattern,
        chunk_seconds=chunk_seconds,
    )
    return subprocess.Popen(command)


def iter_completed_chunks(
    output_dir: str | Path,
    poll_seconds: float = 1.0,
    stable_seconds: float = 1.5,
) -> Iterator[Path]:
    seen: set[Path] = set()
    root = Path(output_dir)
    while True:
        candidates = sorted(root.glob("chunk_*.wav"))
        now = time.time()
        for path in candidates:
            if path in seen:
                continue
            if path.stat().st_size == 0:
                continue
            age = now - path.stat().st_mtime
            if age >= stable_seconds:
                seen.add(path)
                yield path
        time.sleep(poll_seconds)
