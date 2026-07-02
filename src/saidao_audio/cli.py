from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import strftime

from .embedder import VoiceEmbedder
from .extract import extract_sample
from .service import process_chunk
from .speaker_db import SpeakerDatabase
from .stream import iter_completed_chunks, run_ffmpeg_segmenter
from .vad import has_speech


def build_enrollment_db(
    input_dir: Path,
    output: Path,
    threshold: float,
) -> None:
    embedder = VoiceEmbedder()
    enrollments = {}

    for speaker_dir in sorted(path for path in input_dir.iterdir() if path.is_dir()):
        vectors = []
        for audio_path in sorted(speaker_dir.glob("*.wav")):
            if has_speech(audio_path, min_speech_ratio=0.05):
                vectors.append(embedder.embed_file(audio_path))
        if vectors:
            enrollments[speaker_dir.name] = vectors

    if not enrollments:
        raise RuntimeError(f"no usable enrollment audio found under {input_dir}")

    SpeakerDatabase.from_enrollments(enrollments, threshold=threshold).save(output)
    print(f"saved speaker database: {output}")


def identify_audio_file(audio: Path, db_path: Path) -> dict:
    db = SpeakerDatabase.load(db_path)
    if not has_speech(audio):
        return {
            "time": strftime("%Y-%m-%d %H:%M:%S"),
            "audio": str(audio),
            "status": "silence",
        }

    embedder = VoiceEmbedder()
    result = db.match(embedder.embed_file(audio))
    return {
        "time": strftime("%Y-%m-%d %H:%M:%S"),
        "audio": str(audio),
        "status": "speech",
        "speaker": result.name,
        "known": result.known,
        "score": round(result.score, 4),
        "best_name": result.best_name,
    }


def watch_stream(
    url: str,
    db_path: Path,
    chunk_dir: Path,
    chunk_seconds: int,
    delete_chunks: bool,
) -> None:
    db = SpeakerDatabase.load(db_path)
    embedder = VoiceEmbedder()
    process = run_ffmpeg_segmenter(url, chunk_dir, chunk_seconds=chunk_seconds)

    print(
        json.dumps(
            {
                "time": strftime("%Y-%m-%d %H:%M:%S"),
                "status": "started",
                "pid": process.pid,
                "chunk_dir": str(chunk_dir),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    try:
        for chunk in iter_completed_chunks(chunk_dir):
            if process.poll() is not None:
                raise RuntimeError(f"ffmpeg exited with code {process.returncode}")
            try:
                event = process_chunk(
                    chunk=chunk,
                    db=db,
                    embedder=embedder,
                    job_id="cli",
                    callback_url="",
                    post_callback_func=lambda url, payload: None,
                    delete_chunk=delete_chunks,
                )
            except Exception as exc:
                event = {
                    "time": strftime("%Y-%m-%d %H:%M:%S"),
                    "audio": str(chunk),
                    "status": "chunk_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                print(json.dumps(event, ensure_ascii=False), flush=True)
                continue
            print(json.dumps(event, ensure_ascii=False), flush=True)
    finally:
        if process.poll() is None:
            process.terminate()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="saidao-audio")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enroll = subparsers.add_parser("enroll", help="build speaker database")
    enroll.add_argument("--input", type=Path, required=True)
    enroll.add_argument("--output", type=Path, required=True)
    enroll.add_argument("--threshold", type=float, default=0.78)

    identify = subparsers.add_parser("identify-file", help="identify a wav file")
    identify.add_argument("--audio", type=Path, required=True)
    identify.add_argument("--db", type=Path, required=True)

    extract = subparsers.add_parser(
        "extract-sample",
        help="extract a mono 16 kHz wav enrollment sample from video or m3u8",
    )
    extract.add_argument("--source", required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.add_argument("--start", help="start time, for example 00:01:30")
    extract.add_argument("--duration", type=int, default=60)

    watch = subparsers.add_parser(
        "watch",
        help="identify speakers in a livestream URL, such as m3u8 or flv",
    )
    watch.add_argument("--url", required=True)
    watch.add_argument("--db", type=Path, required=True)
    watch.add_argument("--chunk-dir", type=Path, default=Path("data/chunks"))
    watch.add_argument("--chunk-seconds", type=int, default=5)
    watch.add_argument(
        "--keep-chunks",
        action="store_true",
        help="keep processed wav chunks for debugging",
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "enroll":
            build_enrollment_db(args.input, args.output, args.threshold)
        elif args.command == "identify-file":
            print(
                json.dumps(
                    identify_audio_file(args.audio, args.db),
                    ensure_ascii=False,
                )
            )
        elif args.command == "extract-sample":
            extract_sample(
                source=args.source,
                output=args.output,
                start=args.start,
                duration=args.duration,
            )
            print(f"saved enrollment sample: {args.output}")
        elif args.command == "watch":
            watch_stream(
                args.url,
                args.db,
                args.chunk_dir,
                args.chunk_seconds,
                delete_chunks=not args.keep_chunks,
            )
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
