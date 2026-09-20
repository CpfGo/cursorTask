from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from ashare2026.config import load_settings


def now_cn() -> datetime:
    tz = ZoneInfo(load_settings().timezone)
    return datetime.now(tz)


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def is_auction_window(moment: datetime | None = None) -> bool:
    moment = moment or now_cn()
    settings = load_settings()
    start = parse_hhmm(settings.auction.start)
    open_t = parse_hhmm(settings.auction.open)
    t = moment.timetz().replace(tzinfo=None) if moment.tzinfo else moment.time()
    return start <= t < open_t


def is_after_open(moment: datetime | None = None) -> bool:
    moment = moment or now_cn()
    open_t = parse_hhmm(load_settings().auction.open)
    t = moment.timetz().replace(tzinfo=None) if moment.tzinfo else moment.time()
    return t >= open_t


def is_weekday(moment: datetime | None = None) -> bool:
    moment = moment or now_cn()
    return moment.weekday() < 5


def isoformat_cn(moment: datetime | None = None) -> str:
    moment = moment or now_cn()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(load_settings().timezone))
    return moment.strftime("%Y-%m-%d %H:%M:%S %Z")
