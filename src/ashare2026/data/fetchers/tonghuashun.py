from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.data.fetchers.base import FetcherResult
from ashare2026.data.http import HttpClient
from ashare2026.data.ths_html import (
    ajax_url_candidates,
    extract_article_links,
    looks_waf,
    parse_fund_table,
    parse_limit_reasons,
)
from ashare2026.formatting import to_float, to_int
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import IndexQuote, LimitStock, MarketSnapshot


THS_INDEX = {
    "000001": ("hs_1A0001", "上证指数"),
    "399001": ("hs_399001", "深证成指"),
    "399006": ("hs_399006", "创业板指"),
    "000300": ("hs_1B0300", "沪深300"),
}

GNZJL_PARENT = "https://data.10jqka.com.cn/funds/gnzjl/"
HYZJL_PARENT = "https://data.10jqka.com.cn/funds/hyzjl/"
RADAR_LIST = "https://yuanchuang.10jqka.com.cn/mrnxgg_list/"

DEFAULT_URLS = {
    "ths_concept_flow": "https://data.10jqka.com.cn/funds/gnzjl/field/je/order/desc/ajax/1/",
    "ths_concept_flow_3d": "https://data.10jqka.com.cn/funds/gnzjl/board/3/field/buy/order/desc/ajax/1/",
    "ths_concept_flow_5d": "https://data.10jqka.com.cn/funds/gnzjl/board/5/field/buy/order/DESC/ajax/1/",
    "ths_industry_flow": "https://data.10jqka.com.cn/funds/hyzjl/field/je/order/desc/ajax/1/",
    "ths_industry_flow_3d": "https://data.10jqka.com.cn/funds/hyzjl/board/3/field/buy/order/desc/ajax/1/",
    "ths_industry_flow_5d": "https://data.10jqka.com.cn/funds/hyzjl/board/5/field/buy/order/DESC/ajax/1/",
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

        self.http.get_text(GNZJL_PARENT, referer="https://data.10jqka.com.cn/")

        concepts = self._merge_horizons(
            instant=self._fund_table(self._url("ths_concept_flow"), "concept", "instant", GNZJL_PARENT),
            flow_3d=self._fund_table(self._url("ths_concept_flow_3d"), "concept", "3d", GNZJL_PARENT),
            flow_5d=self._fund_table(self._url("ths_concept_flow_5d"), "concept", "5d", GNZJL_PARENT),
        )
        industries = self._merge_horizons(
            instant=self._fund_table(self._url("ths_industry_flow"), "industry", "instant", HYZJL_PARENT),
            flow_3d=self._fund_table(self._url("ths_industry_flow_3d"), "industry", "3d", HYZJL_PARENT),
            flow_5d=self._fund_table(self._url("ths_industry_flow_5d"), "industry", "5d", HYZJL_PARENT),
        )

        flow_3d_ok = any(b.net_inflow_3d is not None for b in concepts)
        flow_5d_ok = any(b.net_inflow_5d is not None for b in concepts)
        if any(b.net_inflow is not None for b in concepts):
            notes.append("同花顺概念即时资金表可用：data.10jqka.com.cn/funds/gnzjl")
        else:
            notes.append("同花顺概念即时资金表不可用")
        if flow_3d_ok:
            notes.append("同花顺概念3日资金表可用")
        else:
            notes.append("同花顺概念3日资金表不可用，3日连续性标记 DATA_MISSING，不用5日冒充")
        if flow_5d_ok:
            notes.append("同花顺概念5日资金表可用")
        else:
            notes.append("同花顺概念5日资金表不可用")

        snapshot.limit_up = self._limit_reasons()
        if snapshot.limit_up:
            notes.append(f"同花顺涨停雷达/复盘解析到{len(snapshot.limit_up)}条涨停原因（仅原文出现的股票+题材）")
        else:
            notes.append("同花顺涨停原因不可用：未从涨停雷达/复盘原文解析到股票题材")

        return FetcherResult(
            snapshot=snapshot,
            industries=industries,
            concepts=concepts,
            notes=notes,
            flow_3d_ok=flow_3d_ok,
            flow_5d_ok=flow_5d_ok,
        )

    def _url(self, sid: str) -> str:
        for src in self.settings.data_sources:
            if src.id == sid:
                return src.url
        return DEFAULT_URLS[sid]

    def _fund_table(self, url: str, kind: str, horizon: str, parent: str) -> list[BoardQuote]:
        self.http.get_text(parent, referer="https://data.10jqka.com.cn/")
        for cand in ajax_url_candidates(url):
            text = self.http.get_text(cand, referer=parent, ajax=True, prefer_gbk=True)
            if not text or looks_waf(text):
                self.http.refresh_hexin(force=True)
                text = self.http.get_text(cand, referer=parent, ajax=True, prefer_gbk=True)
            if not text or looks_waf(text):
                continue
            rows = parse_fund_table(text, kind=kind, horizon=horizon)
            if rows:
                return rows
        return []

    def _merge_horizons(
        self,
        *,
        instant: list[BoardQuote],
        flow_3d: list[BoardQuote],
        flow_5d: list[BoardQuote],
    ) -> list[BoardQuote]:
        by_name: dict[str, BoardQuote] = {}
        for row in instant:
            by_name[row.name] = row.model_copy()
        for row in flow_3d:
            cur = by_name.get(row.name)
            if cur is None:
                by_name[row.name] = row.model_copy()
            elif row.net_inflow_3d is not None:
                cur.net_inflow_3d = row.net_inflow_3d
        for row in flow_5d:
            cur = by_name.get(row.name)
            if cur is None:
                by_name[row.name] = row.model_copy()
            elif row.net_inflow_5d is not None:
                cur.net_inflow_5d = row.net_inflow_5d
        return list(by_name.values())

    def _limit_reasons(self) -> list[LimitStock]:
        html = self.http.get_text(RADAR_LIST, referer="https://yuanchuang.10jqka.com.cn/")
        if not html:
            return []
        links = extract_article_links(html, RADAR_LIST)
        radar = [item for item in links if item[0].startswith("涨停雷达")]
        fupan = [item for item in links if item[0].startswith("涨停复盘")]
        chosen = radar[:8] + fupan[:1]
        found: dict[str, LimitStock] = {}
        for _title, url in chosen:
            text = self.http.get_text(url, referer=RADAR_LIST)
            if not text:
                continue
            for item in parse_limit_reasons(text, url):
                if item.code not in found and item.reason:
                    found[item.code] = item
        return list(found.values())

    def _indices(self) -> dict[str, IndexQuote]:
        out: dict[str, IndexQuote] = {}
        for code, (ths_code, name) in THS_INDEX.items():
            url = f"https://d.10jqka.com.cn/v2/realhead/{ths_code}/last.js"
            data = self.http.get_json(url, referer="http://q.10jqka.com.cn/")
            items = (data or {}).get("items") if isinstance(data, dict) else None
            if not items:
                continue
            amount = to_float(items.get("19"))
            out[code] = IndexQuote(
                code=code,
                name=name,
                price=to_float(items.get("10")),
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
