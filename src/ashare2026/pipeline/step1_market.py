from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.market import MarketSnapshot
from ashare2026.models.report import MarketEnv


def run_step1(snapshot: MarketSnapshot) -> MarketEnv:
    hs = snapshot.indices.get("000300")
    cy = snapshot.indices.get("399006")
    zz = snapshot.indices.get("000852")
    up = snapshot.up_count
    down = snapshot.down_count
    lu = snapshot.limit_up_count
    ld = snapshot.limit_down_count or 0
    consec = snapshot.consecutive_count or 0
    cm20 = snapshot.cm20_count or 0
    hs_pct = hs.change_pct if hs else None
    cy_pct = cy.change_pct if cy else None
    state, reason = _state(up, down, lu, ld, consec, cm20, hs_pct, cy_pct, snapshot.total_amount)
    return MarketEnv(
        total_amount=snapshot.total_amount,
        hs300_pct=hs_pct,
        chi_next_pct=cy_pct,
        zz1000_pct=zz.change_pct if zz else None,
        up_count=up,
        down_count=down,
        limit_up=lu,
        limit_down=ld,
        consecutive=consec,
        cm20=cm20,
        state=state,
        reason=reason,
    )


def _state(up, down, lu, ld, consec, cm20, hs_pct, cy_pct, amount) -> tuple[str, str]:
    parts = [
        f"上涨{up if up is not None else DATA_MISSING}",
        f"下跌{down if down is not None else DATA_MISSING}",
        f"涨停{lu if lu is not None else DATA_MISSING}",
        f"跌停{ld}",
        f"连板{consec}",
        f"20cm{cm20}",
        f"沪深300 {hs_pct}%",
        f"创业板 {cy_pct}%",
        f"成交额{amount}",
    ]
    reason = "；".join(parts)
    if up is None or down is None:
        return "震荡轮动", reason + f"；部分指数结构{DATA_MISSING}，不升级为更强状态"
    if (hs_pct is not None and hs_pct <= -2.0) or (down > up * 1.8 and ld >= 20):
        return "系统风险", reason
    if up > down * 1.4 and (lu or 0) >= 50 and consec >= 8 and (cy_pct or 0) >= 1:
        return "主升浪", reason
    if (lu or 0) <= 20 and ld >= 8 and (up < down):
        return "高位退潮", reason
    if (lu or 0) >= 40 and consec >= 5 and up > down:
        return "主升浪", reason
    if ld >= 10 and (lu or 0) < 30:
        return "高位退潮", reason
    return "震荡轮动", reason
