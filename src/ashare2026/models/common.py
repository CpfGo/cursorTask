from __future__ import annotations

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    id: str
    name: str
    url: str
    available: bool = False
    timestamp: str | None = None
    error: str | None = None
    used_fallback: str | None = None


class AvailabilityRow(BaseModel):
    item: str
    preferred_source: str
    available: bool = False
    timestamp: str | None = None
    impact: str = ""
    actual_source: str | None = None
