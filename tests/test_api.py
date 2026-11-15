"""Tests for the API without real NASA datasets."""
from fastapi.testclient import TestClient
import firechronos.api as api


def test_api_reports_not_ready_without_files(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT", tmp_path)
    client = TestClient(api.app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "data_ready": False}
    missing = client.get("/summary")
    assert missing.status_code == 503
