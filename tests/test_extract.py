from pathlib import Path

from saidao_audio.extract import build_extract_command


def test_build_extract_command_converts_to_mono_16k_wav():
    command = build_extract_command(
        source="input.mp4",
        output=Path("data/enroll/alice/sample_001.wav"),
        start="00:01:00",
        duration=30,
    )

    assert command[:2] == ["ffmpeg", "-hide_banner"]
    assert "-ss" in command
    assert "00:01:00" in command
    assert "-t" in command
    assert "30" in command
    assert "-vn" in command
    assert command[-8:] == [
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-y",
        "data\\enroll\\alice\\sample_001.wav",
    ]
