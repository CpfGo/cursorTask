from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.chain import ChainScore, CycleRow
from ashare2026.models.report import AuctionResult, MarketEnv, PositionResult


RANGES = {
    "激进": "80%-100%",
    "正常": "50%-80%",
    "谨慎": "20%-50%",
    "防守": "0%-20%",
}


def run_step10(
    auction: AuctionResult,
    market: MarketEnv,
    scores: list[ChainScore],
    cycles: list[CycleRow],
    continuity_label: str,
    money_label: str,
    leader_label: str,
    flow_label: str,
) -> PositionResult:
    first = scores[0] if scores else None
    stage = cycles[0].fund_stage if cycles else DATA_MISSING
    same_direction = False
    if auction.strongest and first:
        same_direction = auction.strongest.board in first.chain or first.chain in (auction.strongest.board or "")
        if not same_direction:
            same_direction = _overlap(auction.strongest.board, first.chain)
    factors = {
        "集合竞价强弱": auction.open_environment or DATA_MISSING,
        "主线集中度": first.level if first else DATA_MISSING,
        "即时资金流": flow_label,
        "3日/5日资金连续性": continuity_label,
        "龙头强度": leader_label,
        "赚钱效应": money_label,
        "资金运作阶段": stage,
    }
    position, trigger = _decide(auction, market, first, stage, same_direction, continuity_label, money_label)
    return PositionResult(position=position, range=RANGES[position], factors=factors, trigger=trigger)


def _overlap(board: str, chain: str) -> bool:
    return any(token and token in board for token in chain.replace("/", " ").split())


def _decide(auction, market, first, stage, same_direction, continuity_label, money_label) -> tuple[str, str]:
    strong_cont = continuity_label in {"强连续", "趋势资金"}
    weak_money = money_label in {"弱", "差"} or market.state in {"系统风险", "高位退潮"}
    if market.state == "系统风险" or stage == "高位震荡 / 出货" and weak_money:
        return "防守", "赚钱效应下降/主线退潮或系统风险，资金持续流出特征出现"
    if (
        same_direction
        and first
        and first.level in {"核心主线", "强主线"}
        and stage in {"拉升", "主升浪"}
        and strong_cont
        and auction.open_environment == "强开盘"
    ):
        return "激进", "竞价最强与盘中第一主线一致，阶段处于拉升或主升浪，即时与中短期资金均强"
    if first and first.level in {"核心主线", "强主线", "副主线"} and stage in {"建仓", "拉升", "主升浪"}:
        return "正常", "主线清晰但扩散可能不完整，即时资金不弱，阶段仍在建仓/拉升/主升早段"
    if (not same_direction) or stage in {"洗盘", "反复打压", "高位震荡", "高位震荡 / 出货"}:
        return "谨慎", "竞价与盘中不一致或处于洗盘/反复打压/高位震荡，龙头容易分化"
    return "谨慎", "不满足激进或正常的全部验证条件，按谨慎处理"
