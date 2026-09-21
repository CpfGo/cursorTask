from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.common import AvailabilityRow
from ashare2026.models.market import MarketSnapshot
from ashare2026.models.board import BoardQuote
from ashare2026.timeutil import isoformat_cn


AVAIL_ITEMS = [
    ("全A实时行情", "全A涨跌幅排行", "quotes"),
    ("指数实时行情", "行情中心", "indices"),
    ("涨停/跌停/连板", "涨停雷达", "limits"),
    ("涨停原因", "涨停雷达", "limit_reason"),
    ("行业成交额", "行业板块", "industry"),
    ("概念成交额", "概念板块", "concept"),
    ("个股实时资金", "个股实时资金流", "stock_fund"),
    ("概念即时流入", "概念即时流入排行", "concept_flow"),
    ("概念3日流入", "概念3日流入排行", "flow_3d"),
    ("概念5日流入", "概念5日流入排行", "flow_5d"),
    ("ETF实时行情", "补充源", "etf"),
    ("ETF份额/资金流", "补充源", "etf_share"),
    ("个股主营/概念标签", "同花顺/补充源", "tags"),
    ("阶段新高数据", "补充源", "new_high"),
]


def build_availability(
    *,
    snapshot: MarketSnapshot,
    industries: list[BoardQuote],
    concepts: list[BoardQuote],
    flow_3d_ok: bool,
    flow_5d_ok: bool,
    reasons_ok: bool,
    tags_ok: bool,
    new_high_ok: bool,
    etf_share_ok: bool,
    source_map: dict[str, str],
    timestamp: str | None = None,
) -> list[AvailabilityRow]:
    ts = timestamp or isoformat_cn()
    flags = {
        "quotes": bool(snapshot.stocks) or snapshot.up_count is not None,
        "indices": bool(snapshot.indices),
        "limits": snapshot.limit_up_count is not None or bool(snapshot.limit_up),
        "limit_reason": reasons_ok,
        "industry": bool(industries),
        "concept": bool(concepts),
        "stock_fund": any(s.net_inflow is not None for s in snapshot.stocks),
        "concept_flow": any(b.net_inflow is not None for b in concepts),
        "flow_3d": flow_3d_ok,
        "flow_5d": flow_5d_ok,
        "etf": bool(snapshot.etfs),
        "etf_share": etf_share_ok,
        "tags": tags_ok,
        "new_high": new_high_ok,
    }
    impact = {
        "quotes": "无法统计涨跌分布与个股结构",
        "indices": "无法判断指数环境",
        "limits": "无法确认涨停/连板结构",
        "limit_reason": "涨停题材归因缺失，龙头板块属性只能用行业/概念标签",
        "industry": "行业成交额主线缺失",
        "concept": "概念成交额主线缺失",
        "stock_fund": "龙头资金确认能力下降",
        "concept_flow": "开盘/盘中攻击方向确认能力下降",
        "flow_3d": "无法完整判断一日游与3日连续性",
        "flow_5d": "中短期资金趋势判断能力下降",
        "etf": "无法用ETF成交验证机构交易热度",
        "etf_share": "无法判断ETF净申购",
        "tags": "产业链归类精度下降",
        "new_high": "无法验证主升/二波的新高证据",
    }
    rows: list[AvailabilityRow] = []
    for item, preferred, key in AVAIL_ITEMS:
        ok = flags.get(key, False)
        rows.append(
            AvailabilityRow(
                item=item,
                preferred_source=preferred,
                available=ok,
                timestamp=ts if ok else None,
                impact="" if ok else impact[key],
                actual_source=source_map.get(key) if ok else DATA_MISSING,
            )
        )
    return rows
