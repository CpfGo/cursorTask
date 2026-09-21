from __future__ import annotations

import time
from typing import Any

import httpx

from ashare2026.config import load_settings
from ashare2026.data.hexin import generate_hexin_v


class HttpClient:
    def __init__(self) -> None:
        settings = load_settings()
        self.timeout = settings.http.timeout_sec
        self.retries = settings.http.retries
        self.user_agent = settings.http.user_agent
        self._client: httpx.Client | None = None
        self._hexin: str | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
        self._client = None

    def refresh_hexin(self, *, force: bool = False) -> str | None:
        if self._hexin and not force:
            return self._hexin
        self._hexin = generate_hexin_v()
        client = self._ensure_client()
        if self._hexin:
            client.cookies.set("v", self._hexin)
        return self._hexin

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        referer: str | None = None,
        ajax: bool = False,
    ) -> Any:
        text = self.get_text(url, headers=headers, params=params, referer=referer, ajax=ajax)
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
        ajax: bool = False,
        prefer_gbk: bool | None = None,
    ) -> str | None:
        merged = {
            "User-Agent": self.user_agent,
            "Accept": "text/html, */*; q=0.01" if ajax else "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if referer:
            merged["Referer"] = referer
        if ajax:
            merged["X-Requested-With"] = "XMLHttpRequest"
        if headers:
            merged.update(headers)
        ths = _is_ths(url)
        if prefer_gbk is None:
            prefer_gbk = _is_ths_gbk(url)
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                client = self._ensure_client()
                if ths:
                    hexin = self.refresh_hexin(force=attempt > 0)
                    if hexin:
                        merged["hexin-v"] = hexin
                resp = client.get(url, headers=merged, params=params)
                if resp.status_code >= 400:
                    last_exc = RuntimeError(f"HTTP {resp.status_code}")
                    continue
                return _decode(resp, prefer_gbk=prefer_gbk)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(0.4 * (attempt + 1))
        return None if last_exc else None


def _is_ths(url: str) -> bool:
    return "10jqka.com.cn" in url or "thsi.cn" in url


def _is_ths_gbk(url: str) -> bool:
    host = url.lower()
    return any(
        token in host
        for token in (
            "data.10jqka.com.cn",
            "q.10jqka.com.cn",
            "d.10jqka.com.cn",
            "stock.10jqka.com.cn",
        )
    )


def _decode(resp: httpx.Response, *, prefer_gbk: bool) -> str:
    ctype = (resp.headers.get("content-type") or "").lower()
    if "gbk" in ctype or "gb2312" in ctype or "gb18030" in ctype:
        return resp.content.decode("gb18030", errors="replace")
    if "utf-8" in ctype or "utf8" in ctype:
        return resp.content.decode("utf-8", errors="replace")
    if prefer_gbk:
        return resp.content.decode("gb18030", errors="replace")
    try:
        return resp.content.decode("utf-8")
    except UnicodeDecodeError:
        return resp.content.decode("gb18030", errors="replace")
