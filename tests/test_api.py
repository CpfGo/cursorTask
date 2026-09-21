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
    api_app._LATEST_AUCTION_HTML = ""
    api_app._LATEST_AUCTION_JSON = None
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "A股2026主线识别系统" in home.text
    assert home.text.index("生成集合竞价报告") < home.text.index("生成今日报告")
    analyze = client.post("/api/v1/analyze")
    assert analyze.status_code == 200
    report = client.get("/api/v1/report")
    assert report.status_code == 200
    assert report.text.startswith("<!DOCTYPE html>")
    avail = client.get("/api/v1/availability")
    assert avail.status_code == 200
    assert "availability" in avail.json()


def test_auction_report_endpoint(monkeypatch):
    from ashare2026.pipeline.auction_report import run_auction_report as real_run
    from tests.fixtures_data import make_bundle as bundle_fn

    auction = real_run(bundle_fn())

    def fake_auction():
        return auction

    monkeypatch.setattr(api_app, "run_auction_report", fake_auction)
    api_app._LATEST_AUCTION_HTML = ""
    api_app._LATEST_AUCTION_JSON = None
    client = TestClient(create_app(enable_scheduler=False))
    posted = client.post("/api/v1/auction-analyze")
    assert posted.status_code == 200
    page = client.get("/api/v1/auction-report")
    assert page.status_code == 200
    assert "A股集合竞价报告" in page.text
    assert "竞价最强方向" in page.text
    assert client.get("/").text.index("生成集合竞价报告") < client.get("/").text.index("生成今日报告")
