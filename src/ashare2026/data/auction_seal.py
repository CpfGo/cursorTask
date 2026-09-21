from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Iterable

from ashare2026.config import load_settings
from ashare2026.constants import DATA_MISSING
from ashare2026.data.fetchers.tongdaxin import TdxAuctionRow, fetch_jjqc
from ashare2026.data.fetchers.tushare import TushareAuctionPrint, fetch_stk_auction
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import LimitStock, StockQuote
from ashare2026.models.report import AuctionSealRow, AuctionSealSnapshot
from ashare2026.paths import user_dir
from ashare2026.timeutil import cn_tz, isoformat_cn, now_cn

SEAL_CLOCKS = ("09:15", "09:20", "09:25")
OPEN_TURNOVER_CLOCK = "09:25"


def clock_for(moment: datetime) -> str | None:
    """Map Asia/Shanghai wall clock to a snapshot bucket. After 09:30: None."""
    t = moment.timetz().replace(tzinfo=None) if moment.tzinfo else moment.time()
    windows = (
        ("09:15", time(9, 15), time(9, 20)),
        ("09:20", time(9, 20), time(9, 25)),
        ("09:25", time(9, 25), time(9, 30)),
    )
    for clock, start, end in windows:
        if start <= t < end:
            return clock
    return None


def is_after_auction_match(moment: datetime) -> bool:
    t = moment.timetz().replace(tzinfo=None) if moment.tzinfo else moment.time()
    return t >= time(9, 25)


class SealSnapshotStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (user_dir() / "reports")

    def path_for(self, day: str) -> Path:
        return self.root / f"auction-seal-{day}.json"

    def load(self, day: str) -> dict:
        path = self.path_for(day)
        if not path.is_file():
            return {"trade_date": day, "clocks": {}}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"trade_date": day, "clocks": {}}
        if not isinstance(raw, dict):
            return {"trade_date": day, "clocks": {}}
        raw.setdefault("trade_date", day)
        raw.setdefault("clocks", {})
        if not isinstance(raw["clocks"], dict):
            raw["clocks"] = {}
        return raw

    def save_clock(self, day: str, clock: str, payload: dict) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        data = self.load(day)
        data["trade_date"] = day
        data.setdefault("clocks", {})[clock] = payload
        path = self.path_for(day)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def tdx_to_seal_rows(
    tdx_rows: Iterable[TdxAuctionRow],
    *,
    min_yuan: float,
    board_of: dict[str, str],
    industry_of: dict[str, str],
) -> list[AuctionSealRow]:
    out: list[AuctionSealRow] = []
    for item in tdx_rows:
        if not item.is_limit_up:
            continue
        if item.seal_amount is None:
            continue
        if item.seal_amount <= min_yuan:
            continue
        out.append(
            AuctionSealRow(
                name=item.name,
                code=item.code,
                board=board_of.get(item.code) or None,
                industry=industry_of.get(item.code) or None,
                open_turnover=None,
                seal_amount=item.seal_amount,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


def apply_open_turnover(rows: list[AuctionSealRow], prints: dict[str, TushareAuctionPrint], clock: str) -> None:
    """stk_auction is the 09:25 matched print. Do not copy it onto 09:15/09:20."""
    if clock != OPEN_TURNOVER_CLOCK:
        return
    for row in rows:
        hit = prints.get(row.code)
        if hit and hit.turnover_rate is not None:
            row.open_turnover = hit.turnover_rate


def board_maps(
    boards: list[BoardQuote],
    stocks: list[StockQuote],
    limit_up: list[LimitStock],
) -> tuple[dict[str, str], dict[str, str]]:
    board_of: dict[str, str] = {}
    industry_of: dict[str, str] = {}
    ranked = sorted(boards, key=lambda b: (b.amount or 0), reverse=True)
    for board in ranked:
        for stock in board.constituents:
            if board.kind == "concept":
                board_of.setdefault(stock.code, board.name)
            else:
                industry_of.setdefault(stock.code, board.name)
            if stock.industry:
                industry_of.setdefault(stock.code, stock.industry)
    for stock in stocks:
        if stock.concepts:
            board_of.setdefault(stock.code, stock.concepts[0])
        if stock.industry:
            industry_of.setdefault(stock.code, stock.industry)
    for item in limit_up:
        if item.industry:
            industry_of.setdefault(item.code, item.industry)
    return board_of, industry_of


def _rows_from_stored(payload: dict) -> list[AuctionSealRow]:
    rows = []
    for raw in payload.get("rows") or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or "")
        name = str(raw.get("name") or "")
        if not code or not name:
            continue
        rows.append(AuctionSealRow.model_validate(raw))
    return rows


def _missing(clock: str, note: str) -> AuctionSealSnapshot:
    return AuctionSealSnapshot(
        clock=clock,
        count=None,
        available=False,
        rows=[],
        source="",
        note=note,
    )


def _filled(clock: str, rows: list[AuctionSealRow], source: str, note: str) -> AuctionSealSnapshot:
    return AuctionSealSnapshot(
        clock=clock,
        count=len(rows),
        available=True,
        rows=rows,
        source=source,
        note=note,
    )


def build_seal_snapshots(
    *,
    tdx_rows: list[TdxAuctionRow] | None,
    tdx_note: str,
    tushare_rows: list[TushareAuctionPrint] | None,
    tushare_note: str,
    boards: list[BoardQuote],
    stocks: list[StockQuote],
    limit_up: list[LimitStock],
    now: datetime,
    store: SealSnapshotStore | None = None,
    persist: bool = True,
) -> list[AuctionSealSnapshot]:
    settings = load_settings()
    min_yuan = settings.auction_report.seal_min_yuan
    clocks = tuple(settings.auction_report.snapshot_clocks) or SEAL_CLOCKS
    day = now.strftime("%Y%m%d")
    board_of, industry_of = board_maps(boards, stocks, limit_up)
    prints = {row.code: row for row in (tushare_rows or [])}
    if persist:
        store = store or SealSnapshotStore()
        persisted = store.load(day)
    elif store is not None:
        persisted = store.load(day)
    else:
        persisted = {"clocks": {}}
    live_clock = clock_for(now)
    live_rows = tdx_to_seal_rows(tdx_rows or [], min_yuan=min_yuan, board_of=board_of, industry_of=industry_of)
    live_ok = tdx_rows is not None and not str(tdx_note).startswith(DATA_MISSING)

    snapshots: list[AuctionSealSnapshot] = []
    for clock in clocks:
        use_live = False
        if live_ok and live_clock == clock:
            use_live = True
        elif live_ok and clock == "09:25" and is_after_auction_match(now):
            # Morning JJQC after 09:25 is the 09:25 unmatched-at-limit print, not 09:15/09:20.
            use_live = True

        if use_live:
            rows = [r.model_copy(deep=True) for r in live_rows]
            apply_open_turnover(rows, prints, clock)
            source = "通达信 HQServ JJQC 抢筹委托金额（涨停开盘未匹配买单）"
            if persist:
                store = store or SealSnapshotStore()
                store.save_clock(
                    day,
                    clock,
                    {
                        "captured_at": isoformat_cn(now),
                        "source": source,
                        "rows": [r.model_dump() for r in rows],
                    },
                )
            note = source
            if clock == OPEN_TURNOVER_CLOCK:
                note = f"{source}；开盘换手来自 {tushare_note}" if prints else f"{source}；{tushare_note}"
            snapshots.append(_filled(clock, rows, source, note))
            continue

        stored = (persisted.get("clocks") or {}).get(clock)
        if isinstance(stored, dict) and stored.get("rows") is not None:
            rows = _rows_from_stored(stored)
            apply_open_turnover(rows, prints, clock)
            source = str(stored.get("source") or "已落盘的通达信竞价快照")
            snapshots.append(_filled(clock, rows, source, str(stored.get("captured_at") or source)))
            continue

        if clock in ("09:15", "09:20"):
            note = (
                f"{DATA_MISSING}：{clock} 封单额需在该时刻从通达信 HQServ 实时截取；"
                "不能用 09:25 撮合结果或 Tushare stk_auction.amount 回填"
            )
        else:
            note = tdx_note if tdx_note else f"{DATA_MISSING}：无法验证 {clock} 涨停封单额"
        snapshots.append(_missing(clock, note))
    return snapshots


def capture_seal_snapshot(
    *,
    now: datetime | None = None,
    store: SealSnapshotStore | None = None,
) -> Path | None:
    moment = now or now_cn()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=cn_tz())
    clock = clock_for(moment)
    if clock is None:
        return None
    tdx_rows, tdx_note = fetch_jjqc()
    settings = load_settings()
    min_yuan = settings.auction_report.seal_min_yuan
    rows = tdx_to_seal_rows(tdx_rows, min_yuan=min_yuan, board_of={}, industry_of={})
    store = store or SealSnapshotStore()
    day = moment.strftime("%Y%m%d")
    source = "通达信 HQServ JJQC 抢筹委托金额（涨停开盘未匹配买单）"
    if str(tdx_note).startswith(DATA_MISSING) and not rows:
        source = tdx_note
    return store.save_clock(
        day,
        clock,
        {
            "captured_at": isoformat_cn(moment),
            "source": source,
            "rows": [r.model_dump() for r in rows],
        },
    )


def load_live_seal_inputs(trade_date: str) -> tuple[list[TdxAuctionRow] | None, str, list[TushareAuctionPrint] | None, str]:
    tdx_rows, tdx_note = fetch_jjqc()
    tushare_rows, tushare_note = fetch_stk_auction(trade_date)
    return tdx_rows, tdx_note, tushare_rows, tushare_note
