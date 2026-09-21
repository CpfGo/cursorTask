from __future__ import annotations

from ashare2026.data.fetchers.base import FetcherResult
from ashare2026.data.fetchers.eastmoney import EastmoneyFetcher
from ashare2026.data.fetchers.tonghuashun import TonghuashunFetcher
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import MarketSnapshot
from ashare2026.timeutil import isoformat_cn


class DataBundle:
    def __init__(
        self,
        snapshot: MarketSnapshot,
        industries: list[BoardQuote],
        concepts: list[BoardQuote],
        source_map: dict[str, str],
        notes: list[str],
        flow_3d_ok: bool,
        flow_5d_ok: bool,
        reasons_ok: bool,
        tags_ok: bool,
        new_high_ok: bool,
        etf_share_ok: bool,
        quote_timestamp: str,
    ) -> None:
        self.snapshot = snapshot
        self.industries = industries
        self.concepts = concepts
        self.source_map = source_map
        self.notes = notes
        self.flow_3d_ok = flow_3d_ok
        self.flow_5d_ok = flow_5d_ok
        self.reasons_ok = reasons_ok
        self.tags_ok = tags_ok
        self.new_high_ok = new_high_ok
        self.etf_share_ok = etf_share_ok
        self.quote_timestamp = quote_timestamp


class DataManager:
    """优先同花顺，失败后切换其他可用行情源并标注来源。"""

    def __init__(self) -> None:
        self.ths = TonghuashunFetcher()
        self.em = EastmoneyFetcher()

    def fetch(self) -> DataBundle:
        notes: list[str] = []
        source_map: dict[str, str] = {}
        ths = self.ths.fetch()
        em = self.em.fetch()
        notes.extend(ths.notes)
        notes.extend(em.notes)

        snapshot = MarketSnapshot()
        industries: list[BoardQuote] = []
        concepts: list[BoardQuote] = []

        if ths.snapshot.indices:
            snapshot.indices.update(ths.snapshot.indices)
            source_map["indices"] = "同花顺 d.10jqka.com.cn"
        if em.snapshot.indices:
            for code, idx in em.snapshot.indices.items():
                if code not in snapshot.indices:
                    snapshot.indices[code] = idx
            source_map.setdefault("indices", "东方财富 push2delay")
            if "indices" in source_map and "同花顺" in source_map["indices"] and em.snapshot.indices:
                notes.append("指数补充字段来自东方财富（开盘涨跌幅/成交额交叉校验）")

        if ths.industries:
            if em.industries:
                industries = _overlay_ths_flow(em.industries, ths.industries)
                source_map["industry"] = "东方财富行业成交额 + 同花顺行业资金"
            else:
                industries = ths.industries
                source_map["industry"] = "同花顺行业板块"
        elif em.industries:
            industries = em.industries
            source_map["industry"] = "东方财富行业板块（同花顺不可用，已切换）"
            notes.append("行业板块：同花顺接口不可用，已使用东方财富并标注来源")

        if ths.concepts:
            if em.concepts:
                concepts = _overlay_ths_flow(em.concepts, ths.concepts)
                source_map["concept"] = "东方财富概念成交额 + 同花顺概念资金"
            else:
                concepts = ths.concepts
                source_map["concept"] = "同花顺概念板块"
            if any(b.net_inflow is not None for b in ths.concepts):
                source_map["concept_flow"] = "同花顺概念即时流入"
            elif em.concepts:
                source_map["concept_flow"] = "东方财富概念主力净流入（同花顺即时流入未解析到行）"
        elif em.concepts:
            concepts = em.concepts
            source_map["concept"] = "东方财富概念板块（同花顺不可用，已切换）"
            source_map["concept_flow"] = "东方财富概念主力净流入（同花顺不可用，已切换）"
            notes.append("概念板块/资金流：同花顺接口不可用，已使用东方财富并标注来源")

        if em.snapshot.limit_up or em.snapshot.limit_up_count is not None:
            snapshot.limit_up = em.snapshot.limit_up
            snapshot.limit_down = em.snapshot.limit_down
            source_map["limits"] = "东方财富涨停池"
            if ths.snapshot.limit_up:
                notes.append("涨停/连板以东方财富涨停池为准，涨停原因叠加同花顺雷达/复盘原文")
            else:
                notes.append("涨停/连板：同花顺涨停雷达未提供完整池，已使用东方财富涨停池")
        elif ths.snapshot.limit_up:
            snapshot.limit_up = ths.snapshot.limit_up
            snapshot.limit_down = ths.snapshot.limit_down
            source_map["limits"] = "同花顺涨停雷达"

        snapshot.stocks = ths.snapshot.stocks or em.snapshot.stocks
        if ths.snapshot.stocks:
            source_map["quotes"] = "同花顺全A行情"
        elif em.snapshot.stocks:
            source_map["quotes"] = "东方财富全A行情（同花顺不可用，已切换）"
            notes.append("全A个股：同花顺涨跌幅排行不可用，已使用东方财富")

        snapshot.etfs = ths.snapshot.etfs or em.snapshot.etfs
        if snapshot.etfs:
            source_map["etf"] = "东方财富ETF行情" if not ths.snapshot.etfs else "同花顺ETF"
        snapshot.total_amount = _first(ths.snapshot.total_amount, em.snapshot.total_amount)
        snapshot.up_count = _first(ths.snapshot.up_count, em.snapshot.up_count)
        snapshot.down_count = _first(ths.snapshot.down_count, em.snapshot.down_count)
        snapshot.limit_up_count = _first(
            ths.snapshot.limit_up_count, em.snapshot.limit_up_count, len(snapshot.limit_up) or None
        )
        snapshot.limit_down_count = _first(
            ths.snapshot.limit_down_count, em.snapshot.limit_down_count, len(snapshot.limit_down) or None
        )
        snapshot.consecutive_count = _first(ths.snapshot.consecutive_count, em.snapshot.consecutive_count)
        snapshot.cm20_count = _first(ths.snapshot.cm20_count, em.snapshot.cm20_count)
        snapshot.source_notes = notes
        _apply_limit_reasons(snapshot, ths.snapshot.limit_up)

        if any(s.net_inflow is not None for s in snapshot.stocks):
            source_map["stock_fund"] = source_map.get("quotes", "东方财富个股主力净流入")

        flow_3d_ok = bool(ths.flow_3d_ok) or any(b.net_inflow_3d is not None for b in concepts)
        flow_5d_ok = bool(ths.flow_5d_ok or em.flow_5d_ok) or any(
            b.net_inflow_5d is not None for b in concepts
        )
        if ths.flow_5d_ok:
            source_map["flow_5d"] = "同花顺概念5日流入"
        elif em.flow_5d_ok:
            source_map["flow_5d"] = "东方财富概念5日主力净流入（同花顺不可用，已切换）"
        if flow_3d_ok:
            source_map["flow_3d"] = "同花顺概念3日流入"

        tags_ok = any(s.concepts or s.industry for s in snapshot.stocks) or any(
            b.constituents for b in concepts + industries
        )
        if tags_ok:
            source_map["tags"] = "板块成分股映射（东方财富/同花顺可用标签）"

        reasons_ok = any(x.reason for x in snapshot.limit_up)
        if reasons_ok:
            if any(x.reason for x in ths.snapshot.limit_up):
                source_map["limit_reason"] = "同花顺涨停雷达/复盘原文"
            else:
                source_map["limit_reason"] = "涨停原因"

        new_high_ok = any(s.is_new_high is not None for s in snapshot.stocks)
        if new_high_ok:
            source_map["new_high"] = "阶段新高"

        etf_share_ok = any(
            e.net_inflow_5d is not None or e.net_inflow_10d is not None for e in snapshot.etfs
        )
        if etf_share_ok:
            source_map["etf_share"] = "ETF资金流字段"

        quote_timestamp = isoformat_cn()
        return DataBundle(
            snapshot=snapshot,
            industries=industries,
            concepts=concepts,
            source_map=source_map,
            notes=notes,
            flow_3d_ok=flow_3d_ok,
            flow_5d_ok=flow_5d_ok,
            reasons_ok=reasons_ok,
            tags_ok=tags_ok,
            new_high_ok=new_high_ok,
            etf_share_ok=etf_share_ok,
            quote_timestamp=quote_timestamp,
        )


def _first(*values):
    for v in values:
        if v is not None:
            return v
    return None


def _overlay_ths_flow(base: list[BoardQuote], extra: list[BoardQuote]) -> list[BoardQuote]:
    if not extra:
        return base
    by_name = {b.name: b for b in extra}
    seen = {b.name for b in base}
    for board in base:
        hit = by_name.get(board.name)
        if hit is None:
            continue
        if hit.net_inflow is not None:
            board.net_inflow = hit.net_inflow
            if hit.main_buy is not None:
                board.main_buy = hit.main_buy
            if hit.main_sell is not None:
                board.main_sell = hit.main_sell
        if hit.net_inflow_3d is not None:
            board.net_inflow_3d = hit.net_inflow_3d
        if hit.net_inflow_5d is not None:
            board.net_inflow_5d = hit.net_inflow_5d
    for hit in extra:
        if hit.name not in seen:
            base.append(hit)
            seen.add(hit.name)
    return base


def _apply_limit_reasons(snapshot: MarketSnapshot, ths_limits: list) -> None:
    reason_map = {x.code: x.reason for x in ths_limits if getattr(x, "reason", None)}
    if not reason_map:
        return
    for item in snapshot.limit_up:
        if not item.reason and item.code in reason_map:
            item.reason = reason_map[item.code]
    for stock in snapshot.stocks:
        if not stock.limit_reason and stock.code in reason_map:
            stock.limit_reason = reason_map[stock.code]
