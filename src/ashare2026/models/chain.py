from __future__ import annotations

from pydantic import BaseModel, Field

from ashare2026.models.market import StockQuote


class ScarcityRow(BaseModel):
    chain: str
    scarce_link: str
    reason: str
    fund_recognized: str
    evidence: str


class LeaderRow(BaseModel):
    chain: str
    name: str
    code: str = ""
    change_pct: float | None = None
    amount: float | None = None
    net_inflow: float | None = None
    limit_flag: str = ""
    new_high: str = ""
    position: str = ""
    logic: str = ""


class EchelonRow(BaseModel):
    chain: str
    leader: str
    mid_count: int = 0
    follow_count: int = 0
    limit_up_count: int = 0
    consecutive_count: int = 0
    structure: str = ""
    completeness: float = 0.0


class MoneyEffectRow(BaseModel):
    chain: str
    limit_up: int = 0
    cm20: int = 0
    consecutive: int = 0
    over_10: int = 0
    limit_down: int = 0
    dump_7: int = 0
    score: float = 0.0


class EtfChainRow(BaseModel):
    chain: str
    etf_name: str
    etf_code: str = ""
    amount: float | None = None
    amount_share: float | None = None
    change_pct: float | None = None
    flow_5d: float | None = None
    flow_10d: float | None = None
    flow_20d: float | None = None
    purchase_rank: str | None = None
    note: str = ""


class CycleRow(BaseModel):
    chain: str
    industry_cycle: str
    fund_stage: str
    reason: str


class ChainScore(BaseModel):
    chain: str
    turnover_score: float = 0.0
    flow_score: float = 0.0
    continuity_score: float = 0.0
    leader_score: float = 0.0
    echelon_score: float = 0.0
    etf_score: float = 0.0
    money_score: float = 0.0
    total: float = 0.0
    rank: int = 0
    level: str = ""


class WeakRow(BaseModel):
    rank: int
    name: str
    change_pct: float | None = None
    outflow: float | None = None
    dump_count: int | None = None
    negative_stocks: str = ""
    reason: str = ""


class ChainBucket(BaseModel):
    name: str
    mapped_boards: list[str] = Field(default_factory=list)
    stocks: list[StockQuote] = Field(default_factory=list)
    amount: float | None = None
    amount_share: float | None = None
    net_inflow: float | None = None
    continuity_3d: str | None = None
    continuity_5d: str | None = None
    instant_rank: int | None = None
    rank_3d: int | None = None
    rank_5d: int | None = None
