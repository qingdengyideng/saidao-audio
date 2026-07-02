# Docker Deployment

The host Python version does not matter when running with Docker. The image uses Python 3.11 inside the container.

## Server prerequisites

- Docker is installed and running.
- Port `8000` is allowed in the Alibaba Cloud security group and server firewall.
- The server can access the livestream URLs and callback URL.
- At least 2 GB RAM is available. One stream on 2C2G is the recommended starting point.

## Build image on the server

Upload or clone this project to the server, then run:

```bash
cd /path/to/saidao-audio
docker build -t saidao-audio:latest .
```

The build downloads CPU PyTorch and may take several minutes.

## Prepare voiceprint database

Option A: copy an existing `data/speakers.json` from your local machine to the server.

Option B: mount enrollment audio and generate it inside the container:

```bash
docker run --rm \
  -v "$PWD/data:/app/data" \
  saidao-audio:latest \
  saidao-audio enroll --input /app/data/enroll --output /app/data/speakers.json
```

## Run API service

```bash
docker run -d \
  --name saidao-audio \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "$PWD/data:/app/data" \
  saidao-audio:latest
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

API docs:

```text
http://SERVER_IP:8000/docs
```

## Create a stream job

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "room-1001",
    "stream_url": "https://example.com/live.flv",
    "callback_url": "https://your-service.example.com/audio-callback",
    "db_path": "/app/data/speakers.json",
    "chunk_seconds": 5
  }'
```

## Logs

```bash
docker logs -f saidao-audio
```

Expected startup logs after creating a job:

```text
[saidao-audio] starting job=room-1001 chunk_dir=data/chunks/room-1001 chunk_seconds=5
Loaded the voice encoder model on cpu in ...
[saidao-audio] ffmpeg started job=room-1001 pid=...
```

## Update container

```bash
docker stop saidao-audio
docker rm saidao-audio
docker build -t saidao-audio:latest .
docker run -d \
  --name saidao-audio \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "$PWD/data:/app/data" \
  saidao-audio:latest
```
