from __future__ import annotations

from ashare2026.models.chain import ChainScore, CycleRow
from ashare2026.models.report import FalsifyRow


CANDIDATES = [
    "竞价最强方向与盘中资金背离",
    "龙头成交额跌出板块前三",
    "个股净流入转为净流出",
    "概念即时资金转负",
    "3日/5日资金排名明显下降",
    "涨停/20cm扩散中断",
    "连板数量下降",
    "中军转弱且补涨无法接力",
    "板块成交额占比下降",
    "高位股亏钱效应扩散",
]


def run_step11(scores: list[ChainScore], cycles: list[CycleRow]) -> list[FalsifyRow]:
    rows: list[FalsifyRow] = []
    for item in scores[:3]:
        cycle = next((c for c in cycles if c.chain == item.chain), None)
        current = f"{item.level} / {cycle.fund_stage if cycle else 'DATA_MISSING'}"
        picked = list(CANDIDATES)
        if item.level in {"核心主线", "强主线"}:
            ordered = [
                CANDIDATES[0],
                CANDIDATES[1],
                CANDIDATES[3],
                CANDIDATES[5],
                CANDIDATES[7],
                CANDIDATES[8],
            ]
        else:
            ordered = [
                CANDIDATES[3],
                CANDIDATES[4],
                CANDIDATES[8],
                CANDIDATES[9],
                CANDIDATES[2],
            ]
        rows.append(FalsifyRow(chain=item.chain, current=current, conditions=ordered[:5]))
        _ = picked
    return rows
