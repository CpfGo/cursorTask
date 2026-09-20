from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.board import BoardQuote
from ashare2026.models.chain import ChainBucket, WeakRow


def run_step9(chains: list[ChainBucket], industries: list[BoardQuote], concepts: list[BoardQuote]) -> list[WeakRow]:
    boards = [*industries, *concepts]
    weak_boards = sorted(boards, key=lambda b: (b.change_pct if b.change_pct is not None else 0, b.net_inflow or 0))
    rows: list[WeakRow] = []
    seen: set[str] = set()
    for board in weak_boards:
        if board.name in seen:
            continue
        if (board.change_pct is None or board.change_pct > -1) and (board.net_inflow or 0) >= 0:
            continue
        seen.add(board.name)
        dumps = sum(1 for s in board.constituents if (s.change_pct or 0) <= -7 or s.is_limit_down)
        neg = [s.name for s in board.constituents if (s.change_pct or 0) <= -7][:4]
        reason = _reason(board, dumps)
        rows.append(
            WeakRow(
                rank=len(rows) + 1,
                name=board.name,
                change_pct=board.change_pct,
                outflow=board.net_inflow,
                dump_count=dumps if board.constituents else None,
                negative_stocks="、".join(neg) if neg else DATA_MISSING,
                reason=reason,
            )
        )
        if len(rows) >= 8:
            break
    if not rows:
        worst = sorted([c for c in chains if c.amount], key=lambda c: c.net_inflow or 0)
        for i, chain in enumerate(worst[:3], 1):
            rows.append(
                WeakRow(
                    rank=i,
                    name=chain.name,
                    change_pct=None,
                    outflow=chain.net_inflow,
                    dump_count=sum(1 for s in chain.stocks if (s.change_pct or 0) <= -7),
                    negative_stocks="、".join(s.name for s in chain.stocks if (s.change_pct or 0) <= -7)[:40] or DATA_MISSING,
                    reason="资金持续流出" if (chain.net_inflow or 0) < 0 else DATA_MISSING,
                )
            )
    return rows


def _reason(board: BoardQuote, dumps: int) -> str:
    if board.net_inflow is not None and board.net_inflow < 0 and (board.net_inflow_5d or 0) < 0:
        return "资金持续流出"
    if dumps >= 3:
        return "明确退潮"
    if (board.change_pct or 0) < -3 and (board.net_inflow or 0) < 0:
        return "高位兑现"
    if dumps >= 1:
        return "分歧加大"
    if (board.change_pct or 0) < 0:
        return "普通低开"
    return DATA_MISSING
