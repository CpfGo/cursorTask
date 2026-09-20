from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.formatting import clamp
from ashare2026.models.chain import ChainScore


def mainline_level(total: float) -> str:
    if total >= 90:
        return "核心主线"
    if total >= 80:
        return "强主线"
    if total >= 70:
        return "副主线"
    if total >= 60:
        return "轮动方向"
    return "非主流"


def score_mainline(
    chain: str,
    *,
    turnover_score: float,
    flow_score: float,
    continuity_score: float,
    leader_score: float,
    echelon_score: float,
    etf_score: float,
    money_score: float,
) -> ChainScore:
    w = load_settings().scoring.mainline
    total = (
        turnover_score * w.turnover_share / 100
        + flow_score * w.instant_flow / 100
        + continuity_score * w.continuity / 100
        + leader_score * w.leader / 100
        + echelon_score * w.echelon / 100
        + etf_score * w.etf / 100
        + money_score * w.money_effect / 100
    )
    total = clamp(total, 0, 100)
    return ChainScore(
        chain=chain,
        turnover_score=round(turnover_score, 1),
        flow_score=round(flow_score, 1),
        continuity_score=round(continuity_score, 1),
        leader_score=round(leader_score, 1),
        echelon_score=round(echelon_score, 1),
        etf_score=round(etf_score, 1),
        money_score=round(money_score, 1),
        total=round(total, 1),
        level=mainline_level(total),
    )
