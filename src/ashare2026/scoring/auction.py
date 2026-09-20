from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.formatting import clamp
from ashare2026.models.board import BoardQuote
from ashare2026.models.report import AuctionBoardScore


def auction_rating(total: float) -> str:
    if total >= 85:
        return "竞价核心攻击方向"
    if total >= 75:
        return "强竞价方向"
    if total >= 65:
        return "可观察方向"
    if total >= 50:
        return "普通轮动"
    return "弱方向"


def score_auction_board(
    board: BoardQuote,
    *,
    change_score: float,
    high_open_score: float,
    limit_score: float,
    leader_score: float,
    flow_score: float,
    continuity_score: float,
    penalty: float,
) -> AuctionBoardScore:
    weights = load_settings().scoring.auction
    total = (
        change_score * weights.board_change / 100
        + high_open_score * weights.high_open_ratio / 100
        + limit_score * weights.limit_up / 100
        + leader_score * weights.leader / 100
        + flow_score * weights.instant_flow / 100
        + continuity_score * weights.continuity_3d / 100
        + penalty
    )
    total = clamp(total, 0, 100)
    return AuctionBoardScore(
        board=board.name,
        kind=board.kind,
        change_score=round(change_score, 1),
        high_open_score=round(high_open_score, 1),
        limit_score=round(limit_score, 1),
        leader_score=round(leader_score, 1),
        flow_score=round(flow_score, 1),
        continuity_score=round(continuity_score, 1),
        penalty=round(penalty, 1),
        total=round(total, 1),
        rating=auction_rating(total),
        change_pct=board.change_pct,
        leader=board.leader_name,
        amount=board.amount,
        net_inflow=board.net_inflow,
    )
