from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from ashare2026.config import load_settings
from ashare2026.pipeline.engine import run_pipeline
from ashare2026.report.html import render_html

_LATEST_HTML = ""
_LATEST_JSON: dict[str, Any] | None = None


DASHBOARD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>A股2026主线识别系统</title>
<style>
body{margin:0;background:#070b10;color:#e8eef6;font-family:ui-sans-serif,system-ui,"Noto Sans SC",sans-serif}
main{max-width:980px;margin:0 auto;padding:28px}
h1{margin-bottom:8px}
.muted{color:#8b9bb0}
.row{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
button,a.btn{background:#f5c542;color:#111;border:0;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer;text-decoration:none}
.card{background:#10171f;border:1px solid #243142;border-radius:12px;padding:16px}
table{width:100%;border-collapse:collapse}
td,th{border-bottom:1px solid #243142;padding:8px;text-align:left;font-size:13px}
.miss{color:#8a93a3}
.ok{color:#ff5a5f}
</style>
</head>
<body>
<main>
  <p class="muted">机构交易台</p>
  <h1>A股2026主线识别系统</h1>
  <p class="muted">同花顺数据增强 · 集合竞价强弱 · Serenity产业链卡点 · HTML网页报告</p>
  <div class="row">
    <button id="run">生成今日报告</button>
    <a class="btn" href="/api/v1/report" target="_blank">打开最新HTML报告</a>
    <button id="check">检查数据可用性</button>
  </div>
  <div class="card">
    <p id="status" class="muted">等待操作</p>
    <div id="avail"></div>
  </div>
</main>
<script>
async function check(){
  const r = await fetch('/api/v1/availability');
  const j = await r.json();
  document.getElementById('status').textContent = '行情时间戳 ' + (j.quote_timestamp||'');
  const rows = (j.availability||[]).map(x=>`<tr><td>${x.item}</td><td class="${x.available?'ok':'miss'}">${x.available?'可用':'DATA_MISSING'}</td><td>${x.actual_source||'DATA_MISSING'}</td></tr>`).join('');
  document.getElementById('avail').innerHTML = `<table><thead><tr><th>数据项</th><th>状态</th><th>来源</th></tr></thead><tbody>${rows}</tbody></table>`;
}
document.getElementById('check').onclick = check;
document.getElementById('run').onclick = async ()=>{
  document.getElementById('status').textContent = '正在拉取行情并识别主线...';
  const r = await fetch('/api/v1/analyze', {method:'POST'});
  if(!r.ok){document.getElementById('status').textContent='生成失败';return;}
  window.location.href = '/api/v1/report';
};
check();
</script>
</body>
</html>
"""


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title=settings.app.name, version=settings.app.version)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.app.version}

    @app.get("/api/v1/availability")
    def availability() -> JSONResponse:
        global _LATEST_JSON
        if _LATEST_JSON is None:
            _analyze()
        assert _LATEST_JSON is not None
        return JSONResponse(
            {
                "quote_timestamp": _LATEST_JSON.get("meta", {}).get("quote_timestamp"),
                "availability": _LATEST_JSON.get("availability", []),
            }
        )

    @app.post("/api/v1/analyze")
    def analyze() -> JSONResponse:
        result = _analyze()
        return JSONResponse({"ok": True, "headline": result["headline"], "meta": result["meta"]})

    @app.get("/api/v1/report", response_class=HTMLResponse)
    def report() -> str:
        global _LATEST_HTML
        if not _LATEST_HTML:
            _analyze()
        if not _LATEST_HTML:
            raise HTTPException(500, "report unavailable")
        return _LATEST_HTML

    @app.get("/api/v1/result")
    def result_json() -> JSONResponse:
        global _LATEST_JSON
        if _LATEST_JSON is None:
            _analyze()
        return JSONResponse(_LATEST_JSON or {})

    return app


def _analyze() -> dict[str, Any]:
    global _LATEST_HTML, _LATEST_JSON
    result = run_pipeline()
    _LATEST_HTML = render_html(result)
    _LATEST_JSON = result.model_dump()
    return _LATEST_JSON


app = create_app()
