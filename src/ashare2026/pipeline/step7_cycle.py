from __future__ import annotations

from ashare2026.models.chain import ChainBucket, CycleRow, EchelonRow, MoneyEffectRow


def run_step7(
    chains: list[ChainBucket],
    echelons: list[EchelonRow],
    money: list[MoneyEffectRow],
) -> list[CycleRow]:
    ech = {e.chain: e for e in echelons}
    mon = {m.chain: m for m in money}
    rows: list[CycleRow] = []
    for chain in [c for c in chains if not c.name.startswith("其他")][:10]:
        e = ech.get(chain.name)
        m = mon.get(chain.name)
        cycle, stage, reason = _judge(chain, e, m)
        rows.append(CycleRow(chain=chain.name, industry_cycle=cycle, fund_stage=stage, reason=reason))
    return rows


def _judge(chain: ChainBucket, echelon: EchelonRow | None, money: MoneyEffectRow | None) -> tuple[str, str, str]:
    inflow = chain.net_inflow or 0
    share = chain.amount_share or 0
    lu = money.limit_up if money else 0
    score = money.score if money else 0
    structure = echelon.structure if echelon else "无主线结构"
    mid = echelon.mid_count if echelon else 0
    fol = echelon.follow_count if echelon else 0
    rank5 = chain.rank_5d

    if score >= 3.5 and lu >= 3 and structure == "龙头 + 中军 + 补涨扩散" and inflow > 0:
        return "主升期", "主升浪", f"三层共振，涨停{lu}，赚钱效应{score}，即时流入为正"
    if score >= 2.5 and mid >= 1 and inflow > 0 and share > 0:
        return "主升期", "拉升", f"龙头中军跟随，成交额占比{share:.2f}%，流入{inflow}"
    if rank5 and rank5 <= 15 and lu <= 1 and inflow > 0:
        return "二波期", "建仓", f"5日资金排名{rank5}，涨停尚未扩散"
    if structure in {"分歧退潮", "龙头独涨"} and inflow > 0:
        return "高位震荡", "洗盘", "仍有资金但补涨减少、结构不完整"
    if structure == "分歧退潮" and inflow <= 0:
        return "退潮期", "高位震荡 / 出货", "资金转弱且梯队失败"
    if score <= 1 and inflow <= 0:
        return "防御期", "高位震荡 / 出货", "赚钱效应低且资金流出"
    if mid >= 1 and fol == 0:
        return "高位震荡", "反复打压", "中军仍在、补涨不足，成交未证明萎缩"
    if inflow > 0:
        return "二波期", "拉升", "资金仍在流入但扩散不完整"
    return "防御期", "建仓", "数据偏弱，仅给出可验证的保守阶段"
