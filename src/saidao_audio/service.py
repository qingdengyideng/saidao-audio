from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import subprocess
import threading
import traceback
from time import strftime
from typing import Callable
from urllib import request
from uuid import uuid4

from .embedder import VoiceEmbedder
from .logging_config import get_logger
from .speaker_db import SpeakerDatabase
from .stream import iter_completed_chunks, run_ffmpeg_segmenter
from .vad import has_speech

logger = get_logger(__name__)


@dataclass(frozen=True)
class StreamJobRequest:
    stream_url: str
    callback_url: str
    db_path: Path = Path("data/speakers.json")
    chunk_dir: Path | None = None
    chunk_seconds: int = 5
    delete_chunks: bool = True


@dataclass
class StreamJob:
    id: str
    request: StreamJobRequest
    status: str = "created"
    last_event: dict | None = None
    error: str | None = None
    process: subprocess.Popen | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


def post_callback(url: str, payload: dict, timeout: int = 5) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout):
            pass
        logger.debug("回调发送成功 url=%s job_id=%s", url, payload.get("job_id"))
    except Exception as exc:
        logger.error(
            "回调发送失败 url=%s job_id=%s error=%s: %s",
            url,
            payload.get("job_id"),
            type(exc).__name__,
            exc,
        )
        raise


def process_chunk(
    chunk: Path,
    db: SpeakerDatabase,
    embedder: VoiceEmbedder,
    job_id: str,
    callback_url: str,
    has_speech_func: Callable[[Path], bool] = has_speech,
    post_callback_func: Callable[[str, dict], None] = post_callback,
    delete_chunk: bool = True,
) -> dict:
    try:
        speech = has_speech_func(chunk)
        if not speech:
            logger.debug("音频块无语音(静音) job_id=%s audio=%s", job_id, chunk.name)
            event = {
                "time": strftime("%Y-%m-%d %H:%M:%S"),
                "job_id": job_id,
                "audio": str(chunk),
                "status": "silence",
            }
            return event

        result = db.match(embedder.embed_file(chunk))
        event = {
            "time": strftime("%Y-%m-%d %H:%M:%S"),
            "job_id": job_id,
            "audio": str(chunk),
            "status": "speech",
            "speaker": result.name,
            "known": result.known,
            "score": round(result.score, 4),
            "best_name": result.best_name,
        }
        logger.info(
            "识别结果 job_id=%s audio=%s speaker=%s known=%s score=%.4f",
            job_id,
            chunk.name,
            result.name,
            result.known,
            result.score,
        )
        post_callback_func(callback_url, event)
        return event
    finally:
        if delete_chunk:
            chunk.unlink(missing_ok=True)


class StreamJobManager:
    def __init__(self, chunk_root: str | Path = Path("data/chunks")) -> None:
        self._jobs: dict[str, StreamJob] = {}
        self._lock = threading.Lock()
        self._chunk_root = Path(chunk_root)

    def prepare_job(
        self,
        job_request: StreamJobRequest,
        job_id: str | None = None,
    ) -> StreamJob:
        job_id = job_id or str(uuid4())
        chunk_dir = job_request.chunk_dir or (self._chunk_root / job_id)
        prepared_request = StreamJobRequest(
            stream_url=job_request.stream_url,
            callback_url=job_request.callback_url,
            db_path=job_request.db_path,
            chunk_dir=chunk_dir,
            chunk_seconds=job_request.chunk_seconds,
            delete_chunks=job_request.delete_chunks,
        )
        return StreamJob(id=job_id, request=prepared_request)

    def start(self, job_request: StreamJobRequest) -> StreamJob:
        job = self.prepare_job(job_request)
        self._register_and_start(job)
        return job

    def upsert(self, job_request: StreamJobRequest, job_id: str | None = None) -> StreamJob:
        if not job_id:
            return self.start(job_request)

        existing = self.get(job_id)
        if (
            existing
            and existing.request.stream_url == job_request.stream_url
            and self._is_active(existing)
        ):
            return existing

        if existing:
            self.stop(job_id)

        job = self.prepare_job(job_request, job_id=job_id)
        self._register_and_start(job)
        return job

    @staticmethod
    def _is_active(job: StreamJob) -> bool:
        return job.status in {"created", "starting", "running", "stopping"}

    def _register_and_start(self, job: StreamJob) -> None:
        with self._lock:
            self._jobs[job.id] = job
        self._start_thread(job)

    def _start_thread(self, job: StreamJob) -> None:
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        job.thread = thread
        thread.start()

    def get(self, job_id: str) -> StreamJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[StreamJob]:
        with self._lock:
            return list(self._jobs.values())

    def stop(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        logger.info("正在停止任务 job=%s", job_id)
        job.stop_event.set()
        if job.process and job.process.poll() is None:
            job.process.terminate()
            logger.info("已发送终止信号给 ffmpeg 进程 job=%s pid=%s", job_id, job.process.pid)
        job.status = "stopping"
        return True

    def _run_job(self, job: StreamJob) -> None:
        job.status = "starting"
        try:
            if job.request.chunk_dir is None:
                raise RuntimeError("job chunk_dir was not prepared")
            logger.info(
                "任务启动 job=%s stream_url=%s chunk_dir=%s chunk_seconds=%s",
                job.id,
                job.request.stream_url,
                job.request.chunk_dir,
                job.request.chunk_seconds,
            )
            
            logger.debug("正在加载声纹数据库 job=%s db_path=%s", job.id, job.request.db_path)
            db = SpeakerDatabase.load(job.request.db_path)
            logger.info("声纹数据库加载完成 job=%s speakers=%d", job.id, len(db.speakers))
            
            logger.debug("正在初始化声纹嵌入器 job=%s", job.id)
            embedder = VoiceEmbedder()
            logger.debug("声纹嵌入器初始化完成 job=%s", job.id)
            
            job.process = run_ffmpeg_segmenter(
                job.request.stream_url,
                job.request.chunk_dir,
                chunk_seconds=job.request.chunk_seconds,
            )
            job.status = "running"
            logger.info("ffmpeg 进程已启动 job=%s pid=%s", job.id, job.process.pid)

            chunk_count = 0
            for chunk in iter_completed_chunks(job.request.chunk_dir):
                if job.stop_event.is_set():
                    logger.info("收到停止信号 job=%s 已处理音频块=%d", job.id, chunk_count)
                    job.status = "stopped"
                    break
                if job.process.poll() is not None:
                    logger.error(
                        "ffmpeg 进程异常退出 job=%s exit_code=%s 已处理音频块=%d",
                        job.id,
                        job.process.returncode,
                        chunk_count,
                    )
                    raise RuntimeError(
                        f"ffmpeg exited with code {job.process.returncode}"
                    )
                try:
                    chunk_count += 1
                    job.last_event = process_chunk(
                        chunk=chunk,
                        db=db,
                        embedder=embedder,
                        job_id=job.id,
                        callback_url=job.request.callback_url,
                        delete_chunk=job.request.delete_chunks,
                    )
                except Exception as exc:
                    logger.error(
                        "音频块处理失败 job=%s chunk=%s error=%s: %s",
                        job.id,
                        chunk.name,
                        type(exc).__name__,
                        exc,
                        exc_info=True,  # 输出完整的 traceback
                    )
                    job.last_event = {
                        "time": strftime("%Y-%m-%d %H:%M:%S"),
                        "job_id": job.id,
                        "audio": str(chunk),
                        "status": "chunk_error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    if job.request.delete_chunks:
                        chunk.unlink(missing_ok=True)
            else:
                logger.info("任务正常结束 job=%s 共处理音频块=%d", job.id, chunk_count)
                job.status = "stopped"
        except Exception as exc:
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "任务失败 job=%s error=%s",
                job.id,
                job.error,
                exc_info=True,  # 输出完整的 traceback
            )
        finally:
            if job.process and job.process.poll() is None:
                logger.debug("清理 ffmpeg 进程 job=%s pid=%s", job.id, job.process.pid)
                job.process.terminate()
