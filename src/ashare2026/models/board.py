from __future__ import annotations

from pydantic import BaseModel, Field

from ashare2026.models.market import StockQuote


class BoardQuote(BaseModel):
    code: str
    name: str
    kind: str  # industry | concept
    change_pct: float | None = None
    amount: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    leader_name: str | None = None
    leader_code: str | None = None
    leader_change_pct: float | None = None
    net_inflow: float | None = None
    net_inflow_3d: float | None = None
    net_inflow_5d: float | None = None
    net_inflow_10d: float | None = None
    main_buy: float | None = None
    main_sell: float | None = None
    source: str = ""
    constituents: list[StockQuote] = Field(default_factory=list)


class BoardFlow(BaseModel):
    name: str
    code: str
    instant_inflow: float | None = None
    change_pct: float | None = None
    main_buy: float | None = None
    main_sell: float | None = None
    strength: float | None = None
    source: str = ""


class ContinuityRow(BaseModel):
    name: str
    instant_rank: int | None = None
    rank_3d: int | None = None
    rank_5d: int | None = None
    rating: str = ""
