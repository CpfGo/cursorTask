from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Iterable

from ashare2026.config import load_settings
from ashare2026.constants import DATA_MISSING
from ashare2026.data.fetchers.em_seal import EM_SEAL_SOURCE, fetch_em_zt_seal, rows_from_limit_fund
from ashare2026.data.fetchers.ths_seal import THS_SEAL_SOURCE, fetch_ths_seal_rows
from ashare2026.data.fetchers.tongdaxin import (
    TdxAuctionRow,
    TdxQuoteExport,
    fetch_jjqc,
    load_tdx_quote_exports,
    resolve_tdx_import_dir,
)
from ashare2026.data.fetchers.tushare import TushareAuctionPrint, fetch_stk_auction
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import LimitStock, StockQuote
from ashare2026.models.report import AuctionSealRow, AuctionSealSnapshot
from ashare2026.paths import user_dir
from ashare2026.timeutil import cn_tz, isoformat_cn, now_cn

SEAL_CLOCKS = ("09:15", "09:20", "09:25")
OPEN_TURNOVER_CLOCK = "09:25"
JJQC_SOURCE = "通达信 HQServ JJQC 抢筹委托金额（涨停开盘未匹配买单）"
TDX_EXPORT_SOURCE = "通达信本地涨停报价列表（封单额列）"


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
    source: str = JJQC_SOURCE,
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
                board=item.board or board_of.get(item.code) or None,
                industry=item.industry or industry_of.get(item.code) or None,
                open_turnover=item.open_turnover,
                seal_amount=item.seal_amount,
                source=source,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


def apply_open_turnover(rows: list[AuctionSealRow], prints: dict[str, TushareAuctionPrint], clock: str) -> None:
    """stk_auction is the 09:25 matched print. Do not copy it onto 09:15/09:20.
    Do not overwrite 开盘换手Z already taken from a TDX 涨停报价列表 export."""
    if clock != OPEN_TURNOVER_CLOCK:
        return
    for row in rows:
        if row.open_turnover is not None:
            continue
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


def _persist_clock(
    store: SealSnapshotStore | None,
    day: str,
    clock: str,
    now: datetime,
    source: str,
    rows: list[AuctionSealRow],
    persist: bool,
) -> None:
    if not persist:
        return
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


def _missing_note(clock: str, tried: list[str]) -> str:
    tried_txt = "；".join(x for x in tried if x) or "无可用源"
    if clock in ("09:15", "09:20"):
        return (
            f"{DATA_MISSING}：{clock} 封单额需该时刻的通达信涨停报价列表导出（文件名/保存时间对应 {clock}）"
            f"或当时 HQServ JJQC 截取（已尝试：{tried_txt}）。"
            "不能用 09:25/盘中封单、Tushare amount 或公开涨停池回填"
        )
    return (
        f"{DATA_MISSING}：无法验证 {clock} 涨停封单额（已尝试：{tried_txt}）。"
        "不用成交额/开盘金额/Tushare amount 冒充封单"
    )


def _turnover_note(clock: str, rows: list[AuctionSealRow], source: str, tushare_note: str, prints: dict) -> str:
    if clock != OPEN_TURNOVER_CLOCK:
        return source
    has_tdx_z = any(
        r.open_turnover is not None and (r.source or "").startswith("通达信本地") for r in rows
    )
    if has_tdx_z:
        return f"{source}；开盘换手来自通达信开盘换手Z"
    if any(r.open_turnover is not None for r in rows) and prints:
        return f"{source}；开盘换手来自 {tushare_note}"
    return f"{source}；{tushare_note}"


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
    import_dir: Path | None = None,
    tdx_exports: dict[str, TdxQuoteExport] | None = None,
    ths_rows: list[AuctionSealRow] | None = None,
    ths_note: str = "",
    em_rows: list[AuctionSealRow] | None = None,
    em_note: str = "",
    fetch_fallbacks: bool = False,
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
    live_rows = tdx_to_seal_rows(
        tdx_rows or [], min_yuan=min_yuan, board_of=board_of, industry_of=industry_of, source=JJQC_SOURCE
    )
    live_ok = tdx_rows is not None and not str(tdx_note).startswith(DATA_MISSING)
    exports = tdx_exports if tdx_exports is not None else load_tdx_quote_exports(
        day=day, import_dir=import_dir, now=now
    )

    ths_cache = ths_rows
    ths_cache_note = ths_note
    em_cache = em_rows
    em_cache_note = em_note

    def load_ths() -> tuple[list[AuctionSealRow], str]:
        nonlocal ths_cache, ths_cache_note
        if ths_cache is not None:
            return ths_cache, ths_cache_note
        if not fetch_fallbacks:
            return [], ths_cache_note
        ths_cache, ths_cache_note = fetch_ths_seal_rows(min_yuan=min_yuan)
        return ths_cache, ths_cache_note

    def load_em() -> tuple[list[AuctionSealRow], str]:
        nonlocal em_cache, em_cache_note
        if em_cache is not None:
            return em_cache, em_cache_note
        snapshot_rows = rows_from_limit_fund(
            limit_up, min_yuan=min_yuan, board_of=board_of, industry_of=industry_of
        )
        if snapshot_rows:
            em_cache, em_cache_note = snapshot_rows, EM_SEAL_SOURCE
            return em_cache, em_cache_note
        if not fetch_fallbacks:
            return [], em_cache_note
        em_cache, em_cache_note = fetch_em_zt_seal(day, min_yuan=min_yuan)
        return em_cache, em_cache_note

    snapshots: list[AuctionSealSnapshot] = []
    for clock in clocks:
        tried: list[str] = []
        exported = exports.get(clock)
        if exported is not None:
            source = exported.source or TDX_EXPORT_SOURCE
            rows = tdx_to_seal_rows(
                exported.rows,
                min_yuan=min_yuan,
                board_of=board_of,
                industry_of=industry_of,
                source=source,
            )
            apply_open_turnover(rows, prints, clock)
            _persist_clock(store, day, clock, exported.captured_at or now, source, rows, persist)
            snapshots.append(_filled(clock, rows, source, _turnover_note(clock, rows, source, tushare_note, prints)))
            continue
        tried.append(tdx_note or "通达信涨停报价列表无此时点文件")

        use_live = False
        if live_ok and live_clock == clock:
            use_live = True
        elif live_ok and clock == "09:25" and is_after_auction_match(now):
            # Morning JJQC after 09:25 is the 09:25 unmatched-at-limit print, not 09:15/09:20.
            use_live = True

        if use_live:
            rows = [r.model_copy(deep=True) for r in live_rows]
            apply_open_turnover(rows, prints, clock)
            source = JJQC_SOURCE
            _persist_clock(store, day, clock, now, source, rows, persist)
            snapshots.append(_filled(clock, rows, source, _turnover_note(clock, rows, source, tushare_note, prints)))
            continue
        tried.append(tdx_note or "通达信 HQServ JJQC")

        stored = (persisted.get("clocks") or {}).get(clock)
        if isinstance(stored, dict) and stored.get("rows") is not None:
            rows = _rows_from_stored(stored)
            apply_open_turnover(rows, prints, clock)
            source = str(stored.get("source") or "已落盘的通达信竞价快照")
            snapshots.append(_filled(clock, rows, source, str(stored.get("captured_at") or source)))
            continue
        tried.append("无该时点落盘快照")

        # 同花顺 / 东方财富公开涨停封单只填 09:25，避免把盘中封单抄到 09:15/09:20。
        if clock == "09:25" and is_after_auction_match(now):
            public_ths, public_ths_note = load_ths()
            if public_ths:
                rows = [r.model_copy(deep=True) for r in public_ths]
                apply_open_turnover(rows, prints, clock)
                source = public_ths_note or THS_SEAL_SOURCE
                _persist_clock(store, day, clock, now, source, rows, persist)
                snapshots.append(_filled(clock, rows, source, _turnover_note(clock, rows, source, tushare_note, prints)))
                continue
            if public_ths_note:
                tried.append(public_ths_note)
            else:
                tried.append("同花顺公开接口无封单额字段")
            public_em, public_em_note = load_em()
            if public_em:
                rows = [r.model_copy(deep=True) for r in public_em]
                apply_open_turnover(rows, prints, clock)
                source = public_em_note or EM_SEAL_SOURCE
                _persist_clock(store, day, clock, now, source, rows, persist)
                snapshots.append(_filled(clock, rows, source, _turnover_note(clock, rows, source, tushare_note, prints)))
                continue
            tried.append(public_em_note or "东方财富 getTopicZTPool fund 不可用")
        else:
            tried.append("同花顺/东方财富涨停池封单不用于 09:15/09:20")

        snapshots.append(_missing(clock, _missing_note(clock, tried)))
    return snapshots


def capture_seal_snapshot(
    *,
    now: datetime | None = None,
    store: SealSnapshotStore | None = None,
    import_dir: Path | None = None,
) -> Path | None:
    moment = now or now_cn()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=cn_tz())
    clock = clock_for(moment)
    if clock is None:
        return None
    day = moment.strftime("%Y%m%d")
    settings = load_settings()
    min_yuan = settings.auction_report.seal_min_yuan
    store = store or SealSnapshotStore()
    exports = load_tdx_quote_exports(day=day, import_dir=import_dir or resolve_tdx_import_dir(), now=moment)
    exported = exports.get(clock)
    if exported is not None:
        source = exported.source or TDX_EXPORT_SOURCE
        rows = tdx_to_seal_rows(
            exported.rows, min_yuan=min_yuan, board_of={}, industry_of={}, source=source
        )
        return store.save_clock(
            day,
            clock,
            {
                "captured_at": isoformat_cn(exported.captured_at),
                "source": source,
                "rows": [r.model_dump() for r in rows],
            },
        )
    tdx_rows, tdx_note = fetch_jjqc()
    rows = tdx_to_seal_rows(tdx_rows, min_yuan=min_yuan, board_of={}, industry_of={}, source=JJQC_SOURCE)
    source = JJQC_SOURCE
    if str(tdx_note).startswith(DATA_MISSING) and not rows:
        if clock == "09:25":
            ths_rows, ths_note = fetch_ths_seal_rows(min_yuan=min_yuan)
            if ths_rows:
                return store.save_clock(
                    day,
                    clock,
                    {
                        "captured_at": isoformat_cn(moment),
                        "source": ths_note or THS_SEAL_SOURCE,
                        "rows": [r.model_dump() for r in ths_rows],
                    },
                )
            em_rows, em_note = fetch_em_zt_seal(day, min_yuan=min_yuan)
            if em_rows:
                return store.save_clock(
                    day,
                    clock,
                    {
                        "captured_at": isoformat_cn(moment),
                        "source": em_note or EM_SEAL_SOURCE,
                        "rows": [r.model_dump() for r in em_rows],
                    },
                )
            source = f"{tdx_note}；{ths_note}；{em_note}"
        else:
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
