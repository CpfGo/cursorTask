from fastapi.testclient import TestClient

import ashare2026.api.app as api_app
from ashare2026.api.app import create_app
from ashare2026.pipeline.engine import run_pipeline
from tests.fixtures_data import make_bundle


def test_health_and_report(monkeypatch):
    result = run_pipeline(make_bundle())

    def fake_run():
        return result

    monkeypatch.setattr(api_app, "run_pipeline", fake_run)
    api_app._LATEST_HTML = ""
    api_app._LATEST_JSON = None
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "A股2026主线识别系统" in home.text
    analyze = client.post("/api/v1/analyze")
    assert analyze.status_code == 200
    report = client.get("/api/v1/report")
    assert report.status_code == 200
    assert report.text.startswith("<!DOCTYPE html>")
    avail = client.get("/api/v1/availability")
    assert avail.status_code == 200
    assert "availability" in avail.json()
