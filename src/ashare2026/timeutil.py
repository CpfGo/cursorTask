from __future__ import annotations

from datetime import datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ashare2026.config import load_settings

# China Standard Time offset used when the IANA database is unavailable
# (typical on Windows without the `tzdata` package).
CN_OFFSET = timezone(timedelta(hours=8), "UTC+8")


def _local_tz() -> tzinfo | None:
    return datetime.now().astimezone().tzinfo


def cn_tz() -> tzinfo:
    name = load_settings().timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, OSError, ModuleNotFoundError, KeyError, ValueError):
        local = None
        try:
            local = _local_tz()
        except Exception:
            local = None
        if local is not None:
            return local
        return CN_OFFSET


def now_cn() -> datetime:
    return datetime.now(cn_tz())


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
        moment = moment.replace(tzinfo=cn_tz())
    return moment.strftime("%Y-%m-%d %H:%M:%S %Z")
