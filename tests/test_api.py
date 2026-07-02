from fastapi.testclient import TestClient

from saidao_audio import api


class FakeManager:
    def __init__(self):
        self.request = None

    def start(self, request):
        return self.upsert(request, job_id=None)

    def upsert(self, request, job_id=None):
        self.request = request
        self.job_id = job_id
        return type(
            "Job",
            (),
            {
                "id": job_id or "job-1",
                "status": "running",
                "request": request,
                "last_event": None,
                "error": None,
            },
        )()

    def list(self):
        return []

    def get(self, job_id):
        return None

    def stop(self, job_id):
        return False


def test_create_job_accepts_stream_and_callback(monkeypatch):
    fake_manager = FakeManager()
    monkeypatch.setattr(api, "manager", fake_manager)
    client = TestClient(api.app)

    response = client.post(
        "/jobs",
        json={
            "stream_url": "https://example.com/live.flv?sign=abc",
            "callback_url": "https://callback.example.com/audio",
            "chunk_seconds": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "job-1"
    assert fake_manager.request.stream_url == "https://example.com/live.flv?sign=abc"
    assert fake_manager.request.callback_url == "https://callback.example.com/audio"
    assert fake_manager.request.chunk_dir is None
    assert fake_manager.request.delete_chunks is True


def test_create_job_passes_optional_job_id(monkeypatch):
    fake_manager = FakeManager()
    monkeypatch.setattr(api, "manager", fake_manager)
    client = TestClient(api.app)

    response = client.post(
        "/jobs",
        json={
            "job_id": "room-1",
            "stream_url": "https://example.com/live.flv?sign=abc",
            "callback_url": "https://callback.example.com/audio",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "room-1"
    assert fake_manager.job_id == "room-1"
