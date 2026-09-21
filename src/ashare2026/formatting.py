from __future__ import annotations

from typing import Any

from ashare2026.constants import DATA_MISSING


def is_missing(value: Any) -> bool:
    return value is None or value == DATA_MISSING or value == ""


def missing_or(value: Any, fallback: str = DATA_MISSING) -> Any:
    return fallback if is_missing(value) else value


def to_float(value: Any) -> float | None:
    if is_missing(value) or value == "-":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return None if number is None else int(round(number))


def yi(value: float | None, digits: int = 2) -> str:
    if value is None:
        return DATA_MISSING
    return f"{value / 1e8:.{digits}f}亿"


def money_cn(value: float | None, *, yi_digits: int = 2) -> str:
    """Auction-report money: >=1亿 in 亿, otherwise 万. Never invent a number."""
    if value is None:
        return DATA_MISSING
    if abs(value) >= 1e8:
        return f"{value / 1e8:.{yi_digits}f}亿"
    wan = value / 1e4
    if abs(wan - round(wan)) < 1e-9:
        return f"{round(wan):.0f}万"
    return f"{wan:.2f}万"


def pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return DATA_MISSING
    return f"{value:.{digits}f}%"


def signed_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return DATA_MISSING
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}%"


def fmt_num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return DATA_MISSING
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def minmax_score(value: float | None, values: list[float | None], reverse: bool = False) -> float:
    clean = [v for v in values if v is not None]
    if value is None or not clean:
        return 0.0
    lo, hi = min(clean), max(clean)
    if hi == lo:
        return 50.0
    ratio = (value - lo) / (hi - lo)
    if reverse:
        ratio = 1 - ratio
    return clamp(ratio * 100)


def rank_score(rank: int | None, n: int) -> float:
    if rank is None or n <= 0:
        return 0.0
    if n == 1:
        return 100.0
    return clamp(100.0 * (n - rank) / (n - 1))
