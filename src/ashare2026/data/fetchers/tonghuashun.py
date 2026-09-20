from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.data.fetchers.base import FetcherResult
from ashare2026.data.http import HttpClient
from ashare2026.formatting import to_float, to_int
from ashare2026.models.market import IndexQuote, MarketSnapshot


THS_INDEX = {
    "000001": ("hs_1A0001", "上证指数"),
    "399001": ("hs_399001", "深证成指"),
    "399006": ("hs_399006", "创业板指"),
    "000300": ("hs_1B0300", "沪深300"),
}


class TonghuashunFetcher:
    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch(self) -> FetcherResult:
        notes: list[str] = []
        snapshot = MarketSnapshot()
        snapshot.indices = self._indices()
        if snapshot.indices:
            notes.append("同花顺指数行情可用：d.10jqka.com.cn")
            sh = snapshot.indices.get("000001")
            sz = snapshot.indices.get("399001")
            if sh and sz and sh.amount and sz.amount:
                snapshot.total_amount = sh.amount + sz.amount
            if sh and sz:
                snapshot.up_count = (sh.up_count or 0) + (sz.up_count or 0)
                snapshot.down_count = (sh.down_count or 0) + (sz.down_count or 0)
        else:
            notes.append("同花顺指数行情不可用")

        flash_ok = self._flash_ok()
        if flash_ok:
            notes.append("同花顺7x24消息接口可用，仅作催化验证，不作为强弱主依据")
        else:
            notes.append("同花顺7x24消息接口不可用")

        probe_ids = {"ths_zdfph", "ths_concept", "ths_concept_flow", "ths_concept_flow_3d"}
        blocked = []
        for src in self.settings.data_sources:
            if src.id not in probe_ids:
                continue
            text = self.http.get_text(src.url, referer="https://q.10jqka.com.cn/")
            if text is None or _looks_blocked(text):
                blocked.append(src.name)
        if blocked:
            notes.append(
                "同花顺优先数据源不可用：" + "、".join(blocked) + "。将切换其他可用行情源并标注来源。"
            )

        return FetcherResult(
            snapshot=snapshot,
            industries=[],
            concepts=[],
            notes=notes,
            flow_3d_ok=False,
            flow_5d_ok=False,
        )

    def _indices(self) -> dict[str, IndexQuote]:
        out: dict[str, IndexQuote] = {}
        for code, (ths_code, name) in THS_INDEX.items():
            url = f"https://d.10jqka.com.cn/v2/realhead/{ths_code}/last.js"
            data = self.http.get_json(url, referer="http://q.10jqka.com.cn/")
            items = (data or {}).get("items") if isinstance(data, dict) else None
            if not items:
                continue
            price = to_float(items.get("10"))
            open_px = to_float(items.get("7"))
            amount = to_float(items.get("19"))
            out[code] = IndexQuote(
                code=code,
                name=name,
                price=price,
                open_pct=None,
                amount=amount,
                up_count=to_int(items.get("38")),
                down_count=to_int(items.get("39")),
                source="tonghuashun",
            )
        return out

    def _flash_ok(self) -> bool:
        url = "https://news.10jqka.com.cn/app/flash/flashnews/v1/list?seq=0&tagId=62857"
        data = self.http.get_json(url, referer="https://news.10jqka.com.cn/")
        return bool(data and data.get("status_code") == 0)


def _looks_blocked(text: str) -> bool:
    head = text[:400].lower()
    return any(token in head for token in ("403", "401", "forbidden", "unauthorized", "验证", "访问被拒绝"))
