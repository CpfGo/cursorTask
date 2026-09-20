from __future__ import annotations

import time
from typing import Any

import httpx

from ashare2026.config import load_settings


class HttpClient:
    def __init__(self) -> None:
        settings = load_settings()
        self.timeout = settings.http.timeout_sec
        self.retries = settings.http.retries
        self.user_agent = settings.http.user_agent

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> Any:
        text = self.get_text(url, headers=headers, params=params, referer=referer)
        if text is None:
            return None
        text = text.strip()
        if text.startswith("quotebridge") or "(" in text[:40] and text.endswith(")"):
            start = text.find("(")
            end = text.rfind(")")
            if start >= 0 and end > start:
                text = text[start + 1 : end]
        try:
            import json

            return json.loads(text)
        except Exception:
            return None

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> str | None:
        merged = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
        }
        if referer:
            merged["Referer"] = referer
        if headers:
            merged.update(headers)
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    resp = client.get(url, headers=merged, params=params)
                    if resp.status_code >= 400:
                        last_exc = RuntimeError(f"HTTP {resp.status_code}")
                        continue
                    return resp.text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(0.4 * (attempt + 1))
        return None if last_exc else None
