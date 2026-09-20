from __future__ import annotations

from ashare2026.models.chain import ChainBucket, EchelonRow, LeaderRow, MoneyEffectRow
from ashare2026.scoring.money_effect import money_effect_score


def run_step5(
    chains: list[ChainBucket],
    leaders: list[LeaderRow],
    mids: list[LeaderRow],
    follows: list[LeaderRow],
) -> tuple[list[EchelonRow], list[MoneyEffectRow]]:
    leader_map = {x.chain: x.name for x in leaders}
    echelons: list[EchelonRow] = []
    money: list[MoneyEffectRow] = []
    for chain in [c for c in chains if not c.name.startswith("其他")][:10]:
        mid_n = sum(1 for x in mids if x.chain == chain.name)
        fol_n = sum(1 for x in follows if x.chain == chain.name)
        lu = sum(1 for s in chain.stocks if s.is_limit_up)
        consec = sum(1 for s in chain.stocks if s.consecutive_boards >= 2)
        structure, completeness = _structure(mid_n, fol_n, consec, lu, len(chain.stocks))
        echelons.append(
            EchelonRow(
                chain=chain.name,
                leader=leader_map.get(chain.name, ""),
                mid_count=mid_n,
                follow_count=fol_n,
                limit_up_count=lu,
                consecutive_count=consec,
                structure=structure,
                completeness=completeness,
            )
        )
        stats, score = money_effect_score(chain.stocks)
        money.append(
            MoneyEffectRow(
                chain=chain.name,
                limit_up=stats["limit_up"],
                cm20=stats["cm20"],
                consecutive=stats["consecutive"],
                over_10=stats["over_10"],
                limit_down=stats["limit_down"],
                dump_7=stats["dump_7"],
                score=score,
            )
        )
    return echelons, money


def _structure(mid_n: int, fol_n: int, consec: int, lu: int, n: int) -> tuple[str, float]:
    if n == 0:
        return "无主线结构", 0
    if consec >= 3 and lu >= 3:
        return "连板带动", 70
    if mid_n >= 2 and fol_n >= 2 and lu >= 2:
        return "龙头 + 中军 + 补涨扩散", 90
    if mid_n >= 1 and lu >= 1:
        return "龙头 + 中军共振", 75
    if lu >= 1 and mid_n == 0:
        return "龙头独涨", 45
    if lu == 0 and mid_n == 0:
        return "无主线结构", 20
    if fol_n == 0 and mid_n >= 1:
        return "分歧退潮", 35
    return "龙头独涨", 40
