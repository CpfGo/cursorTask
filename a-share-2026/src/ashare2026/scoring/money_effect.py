from __future__ import annotations

from ashare2026.formatting import clamp
from ashare2026.models.market import StockQuote


def money_effect_score(stocks: list[StockQuote]) -> tuple[dict[str, int], float]:
    stats = {
        "limit_up": sum(1 for s in stocks if s.is_limit_up),
        "cm20": sum(1 for s in stocks if s.is_20cm and (s.is_limit_up or (s.change_pct or 0) >= 15)),
        "consecutive": sum(1 for s in stocks if s.consecutive_boards >= 2),
        "over_10": sum(1 for s in stocks if (s.change_pct or 0) >= 10),
        "limit_down": sum(1 for s in stocks if s.is_limit_down or (s.change_pct or 0) <= -9.5),
        "dump_7": sum(1 for s in stocks if (s.change_pct or 0) <= -7),
    }
    score = (
        stats["limit_up"] * 0.6
        + stats["cm20"] * 0.8
        + stats["consecutive"] * 0.7
        + stats["over_10"] * 0.25
        - stats["limit_down"] * 1.2
        - stats["dump_7"] * 0.5
    )
    score = clamp(score, 0, 5)
    return stats, round(score, 2)
