from __future__ import annotations

from ashare2026.constants import DATA_MISSING
from ashare2026.models.chain import ChainBucket, LeaderRow, ScarcityRow


def run_step4(
    chains: list[ChainBucket],
    scarcity: list[ScarcityRow],
) -> tuple[list[LeaderRow], list[LeaderRow], list[LeaderRow]]:
    scarce_map = {s.chain: s.scarce_link for s in scarcity}
    leaders: list[LeaderRow] = []
    mids: list[LeaderRow] = []
    follows: list[LeaderRow] = []
    for chain in [c for c in chains if not c.name.startswith("其他")][:10]:
        ranked = sorted(
            chain.stocks,
            key=lambda s: (
                (s.amount or 0),
                (s.net_inflow or 0),
                (s.market_cap or 0),
                (s.consecutive_boards or 0),
            ),
            reverse=True,
        )
        if not ranked:
            continue
        head = ranked[0]
        leaders.append(_row(chain.name, head, scarce_map.get(chain.name, DATA_MISSING), "总龙头"))
        for stock in ranked[1:4]:
            if (stock.amount or 0) >= (head.amount or 1) * 0.18 or (stock.market_cap or 0) >= (head.market_cap or 1) * 0.5:
                mids.append(_row(chain.name, stock, "中军", "中军"))
            elif (stock.change_pct or 0) >= 3:
                follows.append(
                    _row(
                        chain.name,
                        stock,
                        "补涨",
                        "补涨",
                        logic="跟随龙头成交额与资金方向的补涨，非独立主线",
                    )
                )
        for stock in ranked[4:8]:
            if (stock.change_pct or 0) >= 5 or stock.is_limit_up:
                follows.append(
                    _row(
                        chain.name,
                        stock,
                        "补涨",
                        "补涨",
                        logic="梯队扩散补涨",
                    )
                )
    return leaders, mids, follows


def _row(chain: str, stock, position: str, role: str, logic: str = "") -> LeaderRow:
    flag = DATA_MISSING
    if stock.is_limit_up:
        flag = f"涨停/{stock.consecutive_boards}板" if stock.consecutive_boards else "涨停"
    elif stock.change_pct is not None:
        flag = "未涨停"
    new_high = DATA_MISSING if stock.is_new_high is None else ("是" if stock.is_new_high else "否")
    return LeaderRow(
        chain=chain,
        name=stock.name,
        code=stock.code,
        change_pct=stock.change_pct,
        amount=stock.amount,
        net_inflow=stock.net_inflow,
        limit_flag=flag,
        new_high=new_high,
        position=position,
        logic=logic,
    )
