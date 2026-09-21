from __future__ import annotations

from pathlib import Path

from ashare2026.paths import bundle_dir


def _ths_js_path() -> Path | None:
    here = Path(__file__).resolve().parents[1] / "assets" / "ths.js"
    candidates = [
        here,
        bundle_dir() / "ashare2026" / "assets" / "ths.js",
        bundle_dir() / "assets" / "ths.js",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def generate_hexin_v() -> str | None:
    """Browser cookie/header `v` / `hexin-v` used by data.10jqka.com.cn ajax."""
    js_path = _ths_js_path()
    if js_path is None:
        return None
    try:
        from quickjs import Context
    except Exception:
        return None
    try:
        ctx = Context()
        ctx.eval(js_path.read_text(encoding="utf-8"))
        value = ctx.eval("v()")
        text = str(value or "").strip()
        return text or None
    except Exception:
        return None
