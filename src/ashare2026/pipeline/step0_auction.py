from __future__ import annotations

from ashare2026.constants import AUCTION_NOTE_AFTER_OPEN, AUCTION_SPLIT_MISSING, DATA_MISSING
from ashare2026.formatting import minmax_score
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import MarketSnapshot
from ashare2026.models.report import AuctionResult
from ashare2026.scoring.auction import score_auction_board
from ashare2026.timeutil import is_auction_window, now_cn


def run_step0(snapshot: MarketSnapshot, industries: list[BoardQuote], concepts: list[BoardQuote]) -> AuctionResult:
    moment = now_cn()
    realtime = is_auction_window(moment)
    note = "" if realtime else AUCTION_NOTE_AFTER_OPEN
    boards = _candidate_boards(concepts, industries)
    changes = [b.change_pct for b in boards]
    flows = [b.net_inflow for b in boards]
    flow5 = [b.net_inflow_5d for b in boards]
    scores = []
    for board in boards:
        high_open_score, high_ratio = _high_open(board)
        limit_score, limit_n, one_word = _limit(board, snapshot)
        leader_score = minmax_score(board.leader_change_pct or board.change_pct, [b.leader_change_pct or b.change_pct for b in boards])
        penalty = _penalty(board)
        continuity_score = minmax_score(board.net_inflow_5d, flow5)
        item = score_auction_board(
            board,
            change_score=minmax_score(board.change_pct, changes),
            high_open_score=high_open_score,
            limit_score=limit_score,
            leader_score=leader_score,
            flow_score=minmax_score(board.net_inflow, flows),
            continuity_score=continuity_score,
            penalty=penalty,
        )
        if board.net_inflow_3d is not None and board.net_inflow_5d is not None:
            item.continuity = "3日/5日资金可用"
        elif board.net_inflow_3d is not None:
            item.continuity = "3日资金可用，5日 DATA_MISSING"
        elif board.net_inflow_5d is not None:
            item.continuity = "5日资金可用，3日 DATA_MISSING"
        else:
            item.continuity = DATA_MISSING
        item.reason = (
            f"涨幅{board.change_pct}% / 高开占比{high_ratio} / 涨停{limit_n} "
            f"一字{one_word} / 资金{board.net_inflow}"
        )
        scores.append(item)
    scores.sort(key=lambda x: x.total, reverse=True)
    for i, row in enumerate(scores, 1):
        row.rank = i

    sh = snapshot.indices.get("000001")
    sz = snapshot.indices.get("399001")
    cy = snapshot.indices.get("399006")
    sampled = [s for b in boards for s in b.constituents]
    if not sampled:
        sampled = snapshot.stocks
    high_open = sum(1 for s in sampled if (s.open_pct or 0) > 0)
    low_open = sum(1 for s in sampled if (s.open_pct or 0) < 0)
    limit_up_open = sum(1 for s in sampled if s.is_one_word or ((s.open_pct or 0) >= 9.5 and s.is_limit_up))
    limit_down_open = sum(1 for s in sampled if (s.open_pct or 0) <= -9.5)
    one_word = sum(1 for s in sampled if s.is_one_word) + sum(1 for x in snapshot.limit_up if x.is_one_word)
    consec_high = sum(1 for x in snapshot.limit_up if x.consecutive_boards >= 2 and (x.change_pct or 0) > 0)
    consec_low = None

    env = _open_env(
        sh.open_pct if sh else None,
        high_open,
        low_open,
        limit_up_open,
        limit_down_open,
    )
    participation = {
        "强开盘": "竞价方向清晰，可跟踪最强方向的资金与龙头，不构成买卖指令",
        "正常开盘": "开盘中性，等待盘中资金与主线是否一致",
        "弱开盘": "开盘偏弱，降低攻击性，观察是否修复",
        "风险开盘": "开盘风险偏高，优先观察跌停与资金流出是否扩散",
    }.get(env, DATA_MISSING)

    strongest = scores[0] if scores else None
    weakest = min(scores, key=lambda x: x.total) if scores else None
    return AuctionResult(
        realtime=realtime,
        note=note,
        split_missing=AUCTION_SPLIT_MISSING,
        shanghai_open_pct=sh.open_pct if sh else None,
        shenzhen_open_pct=sz.open_pct if sz else None,
        chi_next_open_pct=cy.open_pct if cy else None,
        high_open_count=high_open if sampled else None,
        low_open_count=low_open if sampled else None,
        limit_up_open=limit_up_open if sampled else None,
        limit_down_open=limit_down_open if sampled else None,
        one_word=one_word or None,
        consecutive_high_open=consec_high or None,
        consecutive_low_open=consec_low,
        open_environment=env,
        board_scores=scores[:30],
        strongest=strongest,
        second=scores[1] if len(scores) > 1 else None,
        third=scores[2] if len(scores) > 2 else None,
        weakest=weakest,
        participation=participation,
    )


def _candidate_boards(concepts: list[BoardQuote], industries: list[BoardQuote]) -> list[BoardQuote]:
    top_c = sorted(concepts, key=lambda b: (b.amount or 0), reverse=True)[:15]
    top_i = sorted(industries, key=lambda b: (b.amount or 0), reverse=True)[:10]
    extra_c = sorted(concepts, key=lambda b: (b.change_pct or -999), reverse=True)[:8]
    extra_i = sorted(industries, key=lambda b: (b.change_pct or -999), reverse=True)[:6]
    seen: set[str] = set()
    out: list[BoardQuote] = []
    for board in [*top_c, *top_i, *extra_c, *extra_i]:
        if board.name in seen:
            continue
        seen.add(board.name)
        out.append(board)
    return out


def _high_open(board: BoardQuote) -> tuple[float, str]:
    if not board.constituents:
        return 0.0, DATA_MISSING
    n = len(board.constituents)
    high = sum(1 for s in board.constituents if (s.open_pct or 0) > 0)
    ratio = high / n if n else 0
    return round(ratio * 100, 1), f"{high}/{n}"


def _limit(board: BoardQuote, snapshot: MarketSnapshot) -> tuple[float, int, int]:
    names = {s.name for s in board.constituents}
    codes = {s.code for s in board.constituents}
    hits = [x for x in snapshot.limit_up if x.code in codes or x.name in names or x.industry == board.name]
    if not hits and board.constituents:
        hits_n = sum(1 for s in board.constituents if s.is_limit_up)
        one = sum(1 for s in board.constituents if s.is_one_word)
        score = min(100, hits_n * 25 + one * 15)
        return score, hits_n, one
    one = sum(1 for x in hits if x.is_one_word)
    score = min(100, len(hits) * 25 + one * 15)
    return score, len(hits), one


def _penalty(board: BoardQuote) -> float:
    if not board.constituents:
        return 0.0
    dumps = sum(1 for s in board.constituents if (s.change_pct or 0) <= -7 or s.is_limit_down)
    if dumps >= 3:
        return -15
    if dumps >= 1 and (board.change_pct or 0) < 0:
        return -8
    return 0.0


def _open_env(
    sh_open: float | None,
    high_open: int,
    low_open: int,
    limit_up_open: int,
    limit_down_open: int,
) -> str:
    if (sh_open is not None and sh_open <= -1.2) or limit_down_open >= 8:
        return "风险开盘"
    if (sh_open is not None and sh_open >= 0.5) and high_open > low_open and limit_up_open >= 5:
        return "强开盘"
    if (sh_open is not None and sh_open < 0) and low_open > high_open:
        return "弱开盘"
    if high_open > low_open * 1.3 and (sh_open or 0) >= 0:
        return "强开盘"
    if low_open > high_open * 1.3:
        return "弱开盘"
    return "正常开盘"
