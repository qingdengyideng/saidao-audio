# Saidao Audio Speaker Recognition

Python MVP for identifying who is speaking in a livestream URL, such as m3u8 or flv.

## What it does

- Extracts mono 16 kHz audio chunks from an m3u8/flv stream with ffmpeg.
- Filters chunks with WebRTC VAD so silence is skipped.
- Builds a local speaker voiceprint database from enrollment audio.
- Identifies live chunks by comparing speaker embeddings locally.

No third-party embedding API is required. The default embedding backend uses `resemblyzer`.

## Install

Install ffmpeg first and make sure `ffmpeg` is available in `PATH`.

```powershell
cd C:\pycode\saidao-audio
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install in order to avoid webrtcvad compilation issues
pip install --no-deps resemblyzer
pip install numpy soundfile webrtcvad-wheels librosa scipy pytest torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
pip install --no-deps -e .
```

**Note on Python versions:** Python 3.10-3.13 are supported. On Windows, use `torch==2.6.0+cpu` from PyTorch CPU-only index to avoid VC++ runtime conflicts. The `resemblyzer` dependency requires `webrtcvad`, which has compilation issues on Windows—install `webrtcvad-wheels` instead (provides the same module without needing a C compiler).

## Prepare enrollment audio

Put clean speech samples under `data\enroll\<person>\`.

Important wording:

- `data\enroll\<person>\*.wav` stores original audio samples for registration.
- `data\speakers.json` is the generated voiceprint database.
- The program reads the `.wav` samples, extracts speaker embeddings, and writes `data\speakers.json`.

Example:

```text
data/enroll/
  zhangsan/
    sample1.wav
    sample2.wav
  lisi/
    sample1.wav
```

Recommended sample length: 30 seconds to 2 minutes per person.

For better accuracy, provide multiple samples per person. The speaker database keeps multiple embeddings for each speaker and uses the best matching vector at recognition time.

Good layout:

```text
data/enroll/
  zhangsan/
    clean_mic.wav
    live_room.wav
    noisy_background.wav
  lisi/
    clean_mic.wav
    live_room.wav
```

Try to cover different realistic conditions: normal speaking, louder speaking, actual livestream audio, background noise, and different microphones. Avoid files where multiple people talk over each other.

The required sample format is:

- WAV
- mono
- 16 kHz
- PCM 16-bit
- mostly one person's clean speech

## Extract enrollment audio from video, m3u8, or flv

From a local video:

```powershell
saidao-audio extract-sample --source C:\videos\zhangsan.mp4 --start 00:01:20 --duration 60 --output data\enroll\zhangsan\sample_001.wav
```

From an m3u8 or flv stream:

```powershell
saidao-audio extract-sample --source "https://example.com/live.m3u8" --duration 60 --output data\enroll\zhangsan\sample_001.wav
```

You can also use ffmpeg directly:

```powershell
ffmpeg -i C:\videos\zhangsan.mp4 -ss 00:01:20 -t 60 -vn -acodec pcm_s16le -ac 1 -ar 16000 data\enroll\zhangsan\sample_001.wav
```

## Build speaker database

```powershell
python -m saidao_audio enroll --input data\enroll --output data\speakers.json
```

## Identify a local audio file

```powershell
python -m saidao_audio identify-file --audio data\chunks\chunk_000001.wav --db data\speakers.json
```

## Identify a livestream URL

```powershell
python -m saidao_audio watch --url "https://example.com/live.m3u8" --db data\speakers.json --chunk-seconds 5
```

FLV stream URLs also work as long as ffmpeg can open them:

```powershell
python -m saidao_audio watch --url "https://example.com/live.flv?expires=xxx&sign=yyy" --db data\speakers.json --chunk-seconds 5
```

The stream watcher writes short wav chunks to `data\chunks` and prints JSON lines with the best speaker match.
Processed chunks are deleted by default. Add `--keep-chunks` if you need to keep wav files for debugging.

Example output:

```json
{"time":"2026-07-02 14:00:10","audio":"data\\chunks\\chunk_000001.wav","status":"speech","speaker":"ya","known":true,"score":0.8123,"best_name":"ya"}
```

## Run as FastAPI service

Start the API server:

```powershell
uvicorn saidao_audio.api:app --host 0.0.0.0 --port 8000
```

Create a stream listening job:

```powershell
curl -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -d "{\"stream_url\":\"https://example.com/live.flv?sign=abc\",\"callback_url\":\"https://your-service.example.com/audio-callback\",\"db_path\":\"data/speakers.json\",\"chunk_seconds\":5}"
```

You can pass `job_id` as an idempotency key:

- Same `job_id` and same `stream_url`: returns the existing job, no internal changes.
- Same `job_id` and different `stream_url`: stops the old stream and starts parsing the new stream with the same `job_id`.
- No `job_id`: creates a new UUID job.

```powershell
curl -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -d "{\"job_id\":\"room-1001\",\"stream_url\":\"https://example.com/live.flv\",\"callback_url\":\"https://your-service.example.com/audio-callback\"}"
```

For concurrent streams, just create multiple jobs. If `chunk_dir` is omitted, each job automatically gets an isolated directory under `data/chunks/<job_id>`, so streams do not delete or read each other's chunk files.

```powershell
curl -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -d "{\"stream_url\":\"https://example.com/live1.flv\",\"callback_url\":\"https://your-service.example.com/audio-callback\"}"

curl -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -d "{\"stream_url\":\"https://example.com/live2.flv\",\"callback_url\":\"https://your-service.example.com/audio-callback\"}"
```

When speech is identified, the service POSTs JSON to `callback_url`:

```json
{
  "time": "2026-07-02 14:00:10",
  "job_id": "job uuid",
  "audio": "data\\chunks\\chunk_000047.wav",
  "status": "speech",
  "speaker": "ya",
  "known": true,
  "score": 0.8123,
  "best_name": "ya"
}
```

FastAPI job endpoints:

```text
GET    /health
POST   /jobs
GET    /jobs
GET    /jobs/{job_id}
DELETE /jobs/{job_id}
```

API jobs also delete processed chunks by default. Send `"delete_chunks": false` in `POST /jobs` only when you need debug audio files. Send `chunk_dir` only if you intentionally want to control where a specific job writes audio chunks.

## Docker deployment

See [docs/deploy-docker.md](docs/deploy-docker.md) for Alibaba Cloud / Docker deployment commands.

## Notes for low-spec servers

- Keep one Python process alive; do not reload the model for every chunk.
- Use 5-second chunks first. Lower latency costs more CPU.
- Start with one stream per 2C2G server.
- If `webrtcvad` is unavailable, the code falls back to a lightweight energy gate.
- If local inference is too slow, keep this project as the audio cutting/VAD layer and replace `VoiceEmbedder` with a third-party API call.
