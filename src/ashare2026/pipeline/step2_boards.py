from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.board import BoardFlow, BoardQuote, ContinuityRow


def run_step2(
    industries: list[BoardQuote],
    concepts: list[BoardQuote],
    flow_3d_ok: bool,
    flow_5d_ok: bool,
    top_n: int = 20,
) -> tuple[list[BoardQuote], list[BoardQuote], list[BoardFlow], list[ContinuityRow]]:
    ind = sorted(industries, key=lambda b: (b.amount or 0), reverse=True)[:top_n]
    con = sorted(concepts, key=lambda b: (b.amount or 0), reverse=True)[:top_n]
    flows: list[BoardFlow] = []
    flow_sorted = sorted(concepts, key=lambda b: (b.net_inflow or -1e99), reverse=True)
    for board in flow_sorted[:top_n]:
        strength = None
        if board.net_inflow is not None and board.amount:
            strength = board.net_inflow / board.amount * 100
        flows.append(
            BoardFlow(
                name=board.name,
                code=board.code,
                instant_inflow=board.net_inflow,
                change_pct=board.change_pct,
                main_buy=board.main_buy,
                main_sell=board.main_sell,
                strength=strength,
                source=board.source,
            )
        )
    instant_rank = {b.name: i for i, b in enumerate(flow_sorted, 1) if b.net_inflow is not None}
    rank3: dict[str, int] = {}
    if flow_3d_ok:
        ordered3 = sorted(concepts, key=lambda b: (b.net_inflow_3d or -1e99), reverse=True)
        rank3 = {b.name: i for i, b in enumerate(ordered3, 1) if b.net_inflow_3d is not None}
    rank5: dict[str, int] = {}
    if flow_5d_ok:
        ordered5 = sorted(concepts, key=lambda b: (b.net_inflow_5d or -1e99), reverse=True)
        rank5 = {b.name: i for i, b in enumerate(ordered5, 1) if b.net_inflow_5d is not None}

    names = []
    for src in (flow_sorted[:30], sorted(concepts, key=lambda b: b.amount or 0, reverse=True)[:20]):
        for b in src:
            if b.name not in names:
                names.append(b.name)

    continuity: list[ContinuityRow] = []
    for name in names[:40]:
        r1 = instant_rank.get(name)
        r3 = rank3.get(name)
        r5 = rank5.get(name)
        continuity.append(
            ContinuityRow(
                name=name,
                instant_rank=r1,
                rank_3d=r3,
                rank_5d=r5,
                rating=_rating(r1, r3, r5, flow_3d_ok, flow_5d_ok),
            )
        )
    return ind, con, flows, continuity


def _rating(
    instant: int | None,
    rank3: int | None,
    rank5: int | None,
    flow_3d_ok: bool,
    flow_5d_ok: bool,
) -> str:
    def top20(rank: int | None) -> bool:
        return rank is not None and rank <= 20

    def top10(rank: int | None) -> bool:
        return rank is not None and rank <= 10

    def weak(rank: int | None) -> bool:
        return rank is not None and rank > 40

    def not_strong(rank: int | None) -> bool:
        return rank is None or rank > 20

    if flow_3d_ok:
        if top20(instant) and top20(rank3) and (not flow_5d_ok or top20(rank5)):
            return "强连续"
        if top10(instant) and weak(rank3) and (not flow_5d_ok or rank5 is None or weak(rank5)):
            return "一日游"
        if top10(instant) and not_strong(rank3) and (not flow_5d_ok or not_strong(rank5)):
            return "短线攻击"
        if top20(rank3) and (instant is None or instant <= 40) and (
            not flow_5d_ok or top20(rank5) or (rank5 is not None and rank5 <= 40)
        ):
            return "趋势资金"
        if (instant is not None and instant > 40) and (rank3 is not None and rank3 > 40) and (
            not flow_5d_ok or rank5 is None or rank5 > 40
        ):
            return "资金退潮"
        return DATA_MISSING

    if instant is None and rank5 is None:
        return DATA_MISSING
    if instant is not None and instant <= 10 and rank5 is not None and rank5 > 40:
        return "短线攻击"
    if rank5 is not None and rank5 <= 20 and (instant is None or instant <= 40):
        return "趋势资金"
    if instant is not None and instant <= 10 and (rank5 is None or rank5 > 30):
        return "短线攻击"
    if (instant is not None and instant > 40) and (rank5 is not None and rank5 > 40):
        return "资金退潮"
    return DATA_MISSING
