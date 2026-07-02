from __future__ import annotations

from pathlib import Path
import subprocess


def build_extract_command(
    source: str,
    output: Path,
    start: str | None = None,
    duration: int | None = None,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "warning"]
    if start:
        command.extend(["-ss", start])
    command.extend(["-i", source])
    if duration:
        command.extend(["-t", str(duration)])
    command.extend([
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-y",
        str(output),
    ])
    return command


def extract_sample(
    source: str,
    output: str | Path,
    start: str | None = None,
    duration: int | None = None,
) -> None:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        build_extract_command(source, target, start=start, duration=duration),
        check=True,
    )
