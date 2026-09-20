from __future__ import annotations

from pydantic import BaseModel, Field

from ashare2026.models.board import BoardFlow, BoardQuote, ContinuityRow
from ashare2026.models.chain import (
    ChainBucket,
    ChainScore,
    CycleRow,
    EchelonRow,
    EtfChainRow,
    LeaderRow,
    MoneyEffectRow,
    ScarcityRow,
    WeakRow,
)
from ashare2026.models.common import AvailabilityRow
from ashare2026.models.market import MarketSnapshot


class AuctionBoardScore(BaseModel):
    board: str
    kind: str = ""
    change_score: float = 0.0
    high_open_score: float = 0.0
    limit_score: float = 0.0
    leader_score: float = 0.0
    flow_score: float = 0.0
    continuity_score: float = 0.0
    penalty: float = 0.0
    total: float = 0.0
    rank: int = 0
    rating: str = ""
    change_pct: float | None = None
    leader: str | None = None
    amount: float | None = None
    net_inflow: float | None = None
    continuity: str | None = None
    reason: str = ""


class AuctionResult(BaseModel):
    realtime: bool = False
    note: str = ""
    split_missing: str | None = None
    shanghai_open_pct: float | None = None
    shenzhen_open_pct: float | None = None
    chi_next_open_pct: float | None = None
    high_open_count: int | None = None
    low_open_count: int | None = None
    limit_up_open: int | None = None
    limit_down_open: int | None = None
    one_word: int | None = None
    consecutive_high_open: int | None = None
    consecutive_low_open: int | None = None
    open_environment: str = ""
    board_scores: list[AuctionBoardScore] = Field(default_factory=list)
    strongest: AuctionBoardScore | None = None
    second: AuctionBoardScore | None = None
    third: AuctionBoardScore | None = None
    weakest: AuctionBoardScore | None = None
    participation: str = ""


class MarketEnv(BaseModel):
    total_amount: float | None = None
    hs300_pct: float | None = None
    chi_next_pct: float | None = None
    zz1000_pct: float | None = None
    up_count: int | None = None
    down_count: int | None = None
    limit_up: int | None = None
    limit_down: int | None = None
    consecutive: int | None = None
    cm20: int | None = None
    state: str = ""
    reason: str = ""


class PositionResult(BaseModel):
    position: str
    range: str
    factors: dict[str, str] = Field(default_factory=dict)
    trigger: str = ""


class FalsifyRow(BaseModel):
    chain: str
    current: str
    conditions: list[str] = Field(default_factory=list)


class Headline(BaseModel):
    auction_strongest: str = ""
    first_chain: str = ""
    weakest: str = ""
    market_state: str = ""
    position: str = ""
    auction_second: str = ""
    auction_third: str = ""
    auction_weakest: str = ""
    open_state: str = ""
    participation: str = ""


class MainlineCard(BaseModel):
    chain: str = ""
    cycle: str = ""
    fund_stage: str = ""
    scarce_link: str = ""
    instant_flow: str = ""
    continuity: str = ""
    leader: str = ""
    mids: str = ""
    follows: str = ""
    falsify: str = ""


class FundRoadmap(BaseModel):
    auction_attack: str = ""
    intraday_flow: str = ""
    spreading_to: str = ""
    avoiding: str = ""


class OneLiner(BaseModel):
    auction_strongest: str = ""
    incremental_chain: str = ""
    fund_stage: str = ""
    weakest: str = ""
    worth_holding: str = ""


class ReportMeta(BaseModel):
    generated_at: str
    quote_timestamp: str
    title: str = "A股主线识别日报"
    version: str = "6.7.0"
    insufficient: bool = False


class PipelineResult(BaseModel):
    meta: ReportMeta
    availability: list[AvailabilityRow] = Field(default_factory=list)
    snapshot: MarketSnapshot
    auction: AuctionResult
    market: MarketEnv
    industries: list[BoardQuote] = Field(default_factory=list)
    concepts: list[BoardQuote] = Field(default_factory=list)
    concept_flows: list[BoardFlow] = Field(default_factory=list)
    continuity: list[ContinuityRow] = Field(default_factory=list)
    chains: list[ChainBucket] = Field(default_factory=list)
    scarcity: list[ScarcityRow] = Field(default_factory=list)
    leaders: list[LeaderRow] = Field(default_factory=list)
    mids: list[LeaderRow] = Field(default_factory=list)
    follows: list[LeaderRow] = Field(default_factory=list)
    echelons: list[EchelonRow] = Field(default_factory=list)
    money: list[MoneyEffectRow] = Field(default_factory=list)
    etfs: list[EtfChainRow] = Field(default_factory=list)
    cycles: list[CycleRow] = Field(default_factory=list)
    scores: list[ChainScore] = Field(default_factory=list)
    weakest: list[WeakRow] = Field(default_factory=list)
    position: PositionResult
    falsify: list[FalsifyRow] = Field(default_factory=list)
    headline: Headline
    first: MainlineCard
    second: MainlineCard
    third: MainlineCard
    weak_card: WeakRow | None = None
    roadmap: FundRoadmap
    one_liner: OneLiner
    source_notes: list[str] = Field(default_factory=list)
