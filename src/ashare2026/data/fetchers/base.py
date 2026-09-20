from __future__ import annotations

from dataclasses import dataclass, field

from ashare2026.models.board import BoardQuote
from ashare2026.models.market import MarketSnapshot


@dataclass
class FetcherResult:
    snapshot: MarketSnapshot = field(default_factory=MarketSnapshot)
    industries: list[BoardQuote] = field(default_factory=list)
    concepts: list[BoardQuote] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flow_3d_ok: bool = False
    flow_5d_ok: bool = False
