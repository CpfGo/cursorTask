from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ashare2026.paths import resolve_config_path, user_dir


def __getattr__(name: str) -> Path:
    if name == "ROOT":
        return user_dir()
    if name == "CONFIG_PATH":
        return resolve_config_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class AuctionWeights(BaseModel):
    cancellable: int = 20
    locked: int = 50
    open_price: int = 30


class AuctionConfig(BaseModel):
    start: str = "09:15"
    lock: str = "09:20"
    open: str = "09:30"
    weights: AuctionWeights = AuctionWeights()


class AuctionScoreWeights(BaseModel):
    board_change: int = 20
    high_open_ratio: int = 15
    limit_up: int = 15
    leader: int = 20
    instant_flow: int = 15
    continuity_3d: int = 10
    negative_feedback: int = -15


class MainlineScoreWeights(BaseModel):
    turnover_share: int = 25
    instant_flow: int = 20
    continuity: int = 15
    leader: int = 15
    echelon: int = 10
    etf: int = 10
    money_effect: int = 5


class ScoringConfig(BaseModel):
    auction: AuctionScoreWeights = AuctionScoreWeights()
    mainline: MainlineScoreWeights = MainlineScoreWeights()


class PipelineConfig(BaseModel):
    industry_top_n: int = 20
    concept_top_n: int = 20
    chain_top_n: int = 12
    constituent_boards: int = 18
    constituent_limit: int = 40
    stock_amount_top_n: int = 120


class HttpConfig(BaseModel):
    timeout_sec: float = 12
    retries: int = 2
    user_agent: str = "Mozilla/5.0"


class AppMeta(BaseModel):
    name: str = "A股2026主线识别系统"
    report_title: str = "A股主线识别日报"
    version: str = "6.7.0"
    timezone: str = "Asia/Shanghai"


class DataSourceConfig(BaseModel):
    priority: int
    id: str
    name: str
    url: str
    usage: str


class Settings(BaseModel):
    app: AppMeta = AppMeta()
    http: HttpConfig = HttpConfig()
    auction: AuctionConfig = AuctionConfig()
    scoring: ScoringConfig = ScoringConfig()
    pipeline: PipelineConfig = PipelineConfig()
    data_sources: list[DataSourceConfig] = Field(default_factory=list)
    fallback_sources: dict[str, str] = Field(default_factory=dict)

    @property
    def timezone(self) -> str:
        return self.app.timezone


@lru_cache(maxsize=1)
def load_settings(path: Path | None = None) -> Settings:
    cfg_path = Path(path) if path else resolve_config_path()
    if not cfg_path.exists():
        return Settings()
    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
