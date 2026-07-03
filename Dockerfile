FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# 日志级别，可选 DEBUG/INFO/WARNING/ERROR，运行时可通过 -e LOG_LEVEL=DEBUG 覆盖
ENV LOG_LEVEL=INFO

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && pip install --no-deps resemblyzer==0.1.4 \
    && pip install \
        "numpy>=1.24" \
        "soundfile>=0.12" \
        "webrtcvad-wheels>=2.0.10" \
        "librosa>=0.9.1" \
        "scipy>=1.2.1" \
        "fastapi>=0.111" \
        "uvicorn[standard]>=0.30" \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-deps -e .

RUN mkdir -p /app/data/enroll /app/data/chunks

EXPOSE 8000

CMD ["uvicorn", "saidao_audio.api:app", "--host", "0.0.0.0", "--port", "8000", "--access-log"]
