from datetime import datetime
from zoneinfo import ZoneInfoNotFoundError

from fastapi.testclient import TestClient

import ashare2026.api.app as api_app
from ashare2026.api.app import create_app
from ashare2026.data.availability import build_availability
from ashare2026.pipeline.engine import run_pipeline
from ashare2026.timeutil import CN_OFFSET, cn_tz, isoformat_cn, now_cn
from tests.fixtures_data import make_bundle


def _missing_iana(*_args, **_kwargs):
    raise ZoneInfoNotFoundError("No time zone found with key Asia/Shanghai")


def test_cn_tz_falls_back_when_zoneinfo_missing(monkeypatch):
    monkeypatch.setattr("ashare2026.timeutil.ZoneInfo", _missing_iana)

    def no_local() -> None:
        raise OSError("local tz unavailable")

    monkeypatch.setattr("ashare2026.timeutil._local_tz", no_local)
    tz = cn_tz()
    assert tz is CN_OFFSET
    aware = datetime(2026, 9, 18, 10, 0, tzinfo=tz)
    assert aware.utcoffset().total_seconds() == 8 * 3600


def test_now_and_isoformat_survive_missing_tzdata(monkeypatch):
    monkeypatch.setattr("ashare2026.timeutil.ZoneInfo", _missing_iana)
    moment = now_cn()
    assert moment.tzinfo is not None
    text = isoformat_cn()
    assert text
    naive = isoformat_cn(datetime(2026, 9, 18, 15, 30))
    assert naive.startswith("2026-09-18 15:30:00")


def test_availability_survives_missing_tzdata(monkeypatch):
    monkeypatch.setattr("ashare2026.timeutil.ZoneInfo", _missing_iana)
    bundle = make_bundle()
    rows = build_availability(
        snapshot=bundle.snapshot,
        industries=bundle.industries,
        concepts=bundle.concepts,
        flow_3d_ok=False,
        flow_5d_ok=True,
        reasons_ok=False,
        tags_ok=True,
        new_high_ok=False,
        etf_share_ok=False,
        source_map=bundle.source_map,
        timestamp=None,
    )
    assert len(rows) == 14
    result = run_pipeline(bundle)
    assert result.availability
    assert result.meta.generated_at


def test_availability_endpoint_survives_missing_tzdata(monkeypatch):
    monkeypatch.setattr("ashare2026.timeutil.ZoneInfo", _missing_iana)
    result = run_pipeline(make_bundle())

    def fake_run():
        return result

    monkeypatch.setattr(api_app, "run_pipeline", fake_run)
    api_app._LATEST_HTML = ""
    api_app._LATEST_JSON = None
    client = TestClient(create_app())
    avail = client.get("/api/v1/availability")
    assert avail.status_code == 200
    body = avail.json()
    assert "availability" in body
    assert body["availability"]
