from __future__ import annotations

from ashare2026.constants import CHAIN_SCARCITY_DEFAULT, DATA_MISSING, SCARCITY_KEYWORDS
from ashare2026.models.chain import ChainBucket, ScarcityRow


def run_step3(chains: list[ChainBucket]) -> list[ScarcityRow]:
    rows: list[ScarcityRow] = []
    active = [c for c in chains if not c.name.startswith("其他")][:12]
    for chain in active:
        scarce, reason = CHAIN_SCARCITY_DEFAULT.get(chain.name, ("DATA_MISSING", "资金持续流入"))
        keys = SCARCITY_KEYWORDS.get(chain.name, ())
        hit = None
        for stock in chain.stocks:
            blob = " ".join([stock.name, *(stock.concepts or []), stock.industry or ""])
            if any(k in blob for k in keys):
                hit = stock
                break
        if hit:
            scarce = f"{hit.name}附近环节"
        recognized = "是" if (chain.net_inflow or 0) > 0 and (chain.amount or 0) > 0 else "否"
        evidence = _evidence(chain)
        if evidence == "无":
            scarce = DATA_MISSING
            reason = DATA_MISSING
            recognized = DATA_MISSING
        rows.append(
            ScarcityRow(
                chain=chain.name,
                scarce_link=scarce,
                reason=reason if evidence != "无" else DATA_MISSING,
                fund_recognized=recognized,
                evidence=evidence,
            )
        )
    return rows


def _evidence(chain: ChainBucket) -> str:
    stocks = chain.stocks
    if not stocks:
        return "无"
    has_flow = chain.net_inflow is not None
    has_amount = chain.amount is not None
    leaders = stocks[:3]
    strong_leader = any((s.amount or 0) > 0 and (s.change_pct or 0) > 3 for s in leaders)
    spread = len([s for s in stocks if (s.change_pct or 0) > 3])
    cont = chain.rank_5d is not None and chain.rank_5d <= 20
    if has_flow and has_amount and strong_leader and spread >= 5 and cont:
        return "强"
    if has_amount and strong_leader:
        return "中"
    if any((s.change_pct or 0) > 5 for s in stocks[:8]):
        return "弱"
    return "无"
