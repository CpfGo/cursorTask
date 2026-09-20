from __future__ import annotations

from ashare2026.formatting import minmax_score
from ashare2026.models.chain import (
    ChainBucket,
    ChainScore,
    EchelonRow,
    EtfChainRow,
    LeaderRow,
    MoneyEffectRow,
)
from ashare2026.scoring.mainline import score_mainline


def run_step8(
    chains: list[ChainBucket],
    leaders: list[LeaderRow],
    echelons: list[EchelonRow],
    money: list[MoneyEffectRow],
    etfs: list[EtfChainRow],
    continuity_by_chain: dict[str, float],
) -> list[ChainScore]:
    active = [c for c in chains if not c.name.startswith("其他")][:12]
    amounts = [c.amount_share for c in active]
    flows = [c.net_inflow for c in active]
    leader_amt = []
    for c in active:
        lead = next((x for x in leaders if x.chain == c.name), None)
        leader_amt.append(lead.amount if lead else 0)
    ech_map = {e.chain: e.completeness for e in echelons}
    mon_map = {m.chain: m.score for m in money}
    etf_map = {e.chain: e.amount for e in etfs}
    etf_vals = [etf_map.get(c.name) for c in active]
    rows: list[ChainScore] = []
    for chain in active:
        lead = next((x for x in leaders if x.chain == chain.name), None)
        leader_score = 0.0
        if lead:
            leader_score = 0.5 * minmax_score(lead.amount, leader_amt) + 0.5 * minmax_score(
                lead.net_inflow, [x.net_inflow for x in leaders]
            )
            if "涨停" in (lead.limit_flag or ""):
                leader_score = min(100, leader_score + 12)
        ech_score = ech_map.get(chain.name, 0)
        money_score = (mon_map.get(chain.name, 0) / 5) * 100
        etf_score = minmax_score(etf_map.get(chain.name), etf_vals)
        if etf_map.get(chain.name) is None:
            etf_score = 0.0
        item = score_mainline(
            chain.name,
            turnover_score=minmax_score(chain.amount_share, amounts),
            flow_score=minmax_score(chain.net_inflow, flows),
            continuity_score=continuity_by_chain.get(chain.name, 0.0),
            leader_score=leader_score,
            echelon_score=ech_score,
            etf_score=etf_score,
            money_score=money_score,
        )
        rows.append(item)
    rows.sort(key=lambda x: x.total, reverse=True)
    for i, row in enumerate(rows, 1):
        row.rank = i
    return rows
