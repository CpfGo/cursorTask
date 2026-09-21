from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable

from ashare2026.config import load_settings
from ashare2026.paths import user_dir
from ashare2026.timeutil import cn_tz, now_cn

log = logging.getLogger(__name__)

AUCTION_FIRE_TIME = time(9, 25, 30)
SNAPSHOT_CAPTURE_TIMES = (time(9, 15, 0), time(9, 20, 0), time(9, 25, 0))
SCHEDULER_NAME = "auction-report-scheduler"
CAPTURE_SCHEDULER_NAME = "auction-seal-capture"


def parse_fire_time(value: str | None = None) -> time:
    text = value or load_settings().auction_report.fire_time
    parts = [int(p) for p in text.split(":")]
    hour, minute = parts[0], parts[1]
    second = parts[2] if len(parts) > 2 else 0
    return time(hour, minute, second)


def holiday_set() -> set[str]:
    return {item.strip() for item in load_settings().calendar.holidays if item and item.strip()}


def is_trading_day(moment: datetime | None = None, holidays: set[str] | None = None) -> bool:
    moment = moment or now_cn()
    if moment.weekday() >= 5:
        return False
    days = holidays if holidays is not None else holiday_set()
    return moment.strftime("%Y-%m-%d") not in days


def next_run_at(moment: datetime | None = None, holidays: set[str] | None = None) -> datetime:
    """Next 09:25:30 Asia/Shanghai on a weekday that is not in calendar.holidays."""
    return _next_at(parse_fire_time(), moment, holidays)


def next_capture_at(moment: datetime | None = None, holidays: set[str] | None = None) -> datetime:
    """Next 09:15 / 09:20 / 09:25 Asia/Shanghai capture on a trading day."""
    moment = moment or now_cn()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=cn_tz())
    days = holidays if holidays is not None else holiday_set()
    cursor = moment
    for _ in range(400):
        for fire in SNAPSHOT_CAPTURE_TIMES:
            candidate = datetime.combine(cursor.date(), fire, tzinfo=moment.tzinfo)
            if is_trading_day(candidate, days) and candidate > moment:
                return candidate
        cursor = datetime.combine(cursor.date() + timedelta(days=1), time(0, 0), tzinfo=moment.tzinfo)
    raise RuntimeError("unable to find next auction-seal capture")


def _next_at(fire: time, moment: datetime | None = None, holidays: set[str] | None = None) -> datetime:
    moment = moment or now_cn()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=cn_tz())
    days = holidays if holidays is not None else holiday_set()
    cursor = moment
    for _ in range(400):
        candidate = datetime.combine(cursor.date(), fire, tzinfo=moment.tzinfo)
        if is_trading_day(candidate, days) and candidate > moment:
            return candidate
        cursor = datetime.combine(cursor.date() + timedelta(days=1), time(0, 0), tzinfo=moment.tzinfo)
    raise RuntimeError("unable to find next auction-report run")


class AuctionScheduler:
    def __init__(
        self,
        generate: Callable[[], Path | None],
        *,
        now_fn: Callable[[], datetime] = now_cn,
        sleep_chunk: float = 30.0,
        next_fn: Callable[..., datetime] | None = None,
        name: str = SCHEDULER_NAME,
    ) -> None:
        self.generate = generate
        self.now_fn = now_fn
        self.sleep_chunk = sleep_chunk
        self.next_fn = next_fn or next_run_at
        self.name = name
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> threading.Thread:
        if self.thread and self.thread.is_alive():
            return self.thread
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name=self.name, daemon=True)
        self.thread.start()
        return self.thread

    def stop(self) -> None:
        self.stop_event.set()

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            target = self.next_fn(self.now_fn())
            if not _wait_until(target, self.stop_event, self.now_fn, self.sleep_chunk):
                return
            if self.stop_event.is_set():
                return
            try:
                path = self.generate()
                log.info("auction report generated: %s", path)
            except Exception:
                log.exception("auction report scheduler failed")
            # skip past the fire second so we do not loop immediately
            self.stop_event.wait(1.0)


def _wait_until(
    target: datetime,
    stop_event: threading.Event,
    now_fn: Callable[[], datetime],
    sleep_chunk: float,
) -> bool:
    while not stop_event.is_set():
        delay = (target - now_fn()).total_seconds()
        if delay <= 0:
            return True
        if stop_event.wait(min(delay, sleep_chunk)):
            return False
    return False


def default_generate() -> Path:
    from ashare2026.pipeline.auction_report import run_auction_report
    from ashare2026.report.auction_html import render_auction_html

    result = run_auction_report()
    html = render_auction_html(result)
    day = now_cn().strftime("%Y%m%d")
    out = user_dir() / "reports" / f"auction-{day}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def default_capture() -> Path | None:
    from ashare2026.data.auction_seal import capture_seal_snapshot

    return capture_seal_snapshot()


def make_capture_scheduler(
    capture: Callable[[], Path | None] | None = None,
    *,
    now_fn: Callable[[], datetime] = now_cn,
    sleep_chunk: float = 30.0,
) -> AuctionScheduler:
    return AuctionScheduler(
        capture or default_capture,
        now_fn=now_fn,
        sleep_chunk=sleep_chunk,
        next_fn=next_capture_at,
        name=CAPTURE_SCHEDULER_NAME,
    )
