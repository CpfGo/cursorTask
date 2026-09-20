from __future__ import annotations

from pydantic import BaseModel, Field


class IndexQuote(BaseModel):
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    open_pct: float | None = None
    amount: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    flat_count: int | None = None
    source: str = ""


class StockQuote(BaseModel):
    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    open_pct: float | None = None
    amount: float | None = None
    turnover: float | None = None
    net_inflow: float | None = None
    market_cap: float | None = None
    high: float | None = None
    open: float | None = None
    prev_close: float | None = None
    industry: str | None = None
    concepts: list[str] = Field(default_factory=list)
    chain: str | None = None
    is_limit_up: bool = False
    is_limit_down: bool = False
    consecutive_boards: int = 0
    is_one_word: bool = False
    is_20cm: bool = False
    is_new_high: bool | None = None
    limit_reason: str | None = None
    source: str = ""


class LimitStock(BaseModel):
    code: str
    name: str
    change_pct: float | None = None
    amount: float | None = None
    consecutive_boards: int = 0
    first_board_time: str | None = None
    industry: str | None = None
    reason: str | None = None
    fund: float | None = None
    is_one_word: bool = False
    is_20cm: bool = False


class EtfQuote(BaseModel):
    code: str
    name: str
    change_pct: float | None = None
    amount: float | None = None
    net_inflow_5d: float | None = None
    net_inflow_10d: float | None = None
    net_inflow_20d: float | None = None
    source: str = ""


class MarketSnapshot(BaseModel):
    indices: dict[str, IndexQuote] = Field(default_factory=dict)
    stocks: list[StockQuote] = Field(default_factory=list)
    limit_up: list[LimitStock] = Field(default_factory=list)
    limit_down: list[LimitStock] = Field(default_factory=list)
    etfs: list[EtfQuote] = Field(default_factory=list)
    total_amount: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    consecutive_count: int | None = None
    cm20_count: int | None = None
    source_notes: list[str] = Field(default_factory=list)
