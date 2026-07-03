from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from .logging_config import get_logger, setup_logging
from .service import StreamJob, StreamJobManager, StreamJobRequest

# 初始化日志系统
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Saidao Audio Speaker Recognition")
manager = StreamJobManager()

logger.info("FastAPI 应用已启动")


class CreateJobRequest(BaseModel):
    job_id: str | None = Field(default=None, description="Optional idempotency key")
    stream_url: str = Field(..., description="Livestream URL, such as m3u8 or flv")
    callback_url: HttpUrl
    db_path: str = "data/speakers.json"
    chunk_dir: str | None = None
    chunk_seconds: int = Field(default=5, ge=3, le=120)
    delete_chunks: bool = True


def serialize_job(job: StreamJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "stream_url": job.request.stream_url,
        "callback_url": job.request.callback_url,
        "db_path": str(job.request.db_path),
        "chunk_dir": str(job.request.chunk_dir),
        "chunk_seconds": job.request.chunk_seconds,
        "delete_chunks": job.request.delete_chunks,
        "last_event": job.last_event,
        "error": job.error,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs")
def create_job(payload: CreateJobRequest) -> dict:
    logger.info(
        "收到创建任务请求 job_id=%s stream_url=%s callback_url=%s chunk_seconds=%s",
        payload.job_id,
        payload.stream_url,
        payload.callback_url,
        payload.chunk_seconds,
    )
    job = manager.upsert(
        StreamJobRequest(
            stream_url=payload.stream_url,
            callback_url=str(payload.callback_url),
            db_path=Path(payload.db_path),
            chunk_dir=Path(payload.chunk_dir) if payload.chunk_dir else None,
            chunk_seconds=payload.chunk_seconds,
            delete_chunks=payload.delete_chunks,
        ),
        job_id=payload.job_id,
    )
    logger.info("任务已创建/更新 job=%s status=%s", job.id, job.status)
    return serialize_job(job)


@app.get("/jobs")
def list_jobs() -> list[dict]:
    jobs = manager.list()
    logger.debug("列出任务，当前任务数=%d", len(jobs))
    return [serialize_job(job) for job in jobs]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = manager.get(job_id)
    if job is None:
        logger.warning("查询任务未找到 job=%s", job_id)
        raise HTTPException(status_code=404, detail="job not found")
    return serialize_job(job)


@app.delete("/jobs/{job_id}")
def stop_job(job_id: str) -> dict:
    if not manager.stop(job_id):
        logger.warning("停止任务未找到 job=%s", job_id)
        raise HTTPException(status_code=404, detail="job not found")
    logger.info("任务停止请求已接受 job=%s", job_id)
    return {"id": job_id, "status": "stopping"}
