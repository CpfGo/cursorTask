from __future__ import annotations

from datetime import datetime

from ashare2026.config import load_settings
from ashare2026.data.auction_seal import SealSnapshotStore, build_seal_snapshots, load_live_seal_inputs
from ashare2026.data.availability import build_availability
from ashare2026.data.fetchers.tongdaxin import TdxAuctionRow
from ashare2026.data.fetchers.tushare import TushareAuctionPrint
from ashare2026.data.manager import DataBundle, DataManager
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import LimitStock, MarketSnapshot, StockQuote
from ashare2026.models.report import (
    AuctionDailyReport,
    AuctionOneWordRow,
    AuctionScrambleRow,
    AuctionVolumeSpikeRow,
    ReportMeta,
)
from ashare2026.pipeline.step0_auction import run_step0
from ashare2026.timeutil import isoformat_cn, now_cn


def run_auction_report(
    bundle: DataBundle | None = None,
    *,
    tdx_rows: list[TdxAuctionRow] | None = None,
    tdx_note: str | None = None,
    tushare_rows: list[TushareAuctionPrint] | None = None,
    tushare_note: str | None = None,
    now: datetime | None = None,
    store: SealSnapshotStore | None = None,
    persist: bool | None = None,
) -> AuctionDailyReport:
    settings = load_settings()
    live = bundle is None
    bundle = bundle or DataManager().fetch()
    moment = now or now_cn()
    snapshot = bundle.snapshot
    auction = run_step0(snapshot, bundle.industries, bundle.concepts)
    boards = list(bundle.concepts) + list(bundle.industries)
    one_word_count, one_word_rows = _strongest_one_word(auction.strongest.board if auction.strongest else None, snapshot, boards)
    scramble, scramble_ok = _scramble_boards(boards, settings.auction_report.scramble_open_pct, settings.auction_report.scramble_volume_ratio)
    spikes, ratio_ok = _volume_spikes(snapshot, boards, settings.auction_report.volume_ratio_spike)
    availability = build_availability(
        snapshot=snapshot,
        industries=bundle.industries,
        concepts=bundle.concepts,
        flow_3d_ok=bundle.flow_3d_ok,
        flow_5d_ok=bundle.flow_5d_ok,
        reasons_ok=bundle.reasons_ok,
        tags_ok=bundle.tags_ok,
        new_high_ok=bundle.new_high_ok,
        etf_share_ok=bundle.etf_share_ok,
        source_map=bundle.source_map,
        timestamp=bundle.quote_timestamp,
    )
    if live and tdx_rows is None:
        fetched_tdx, fetched_tdx_note, fetched_ts, fetched_ts_note = load_live_seal_inputs(moment.strftime("%Y%m%d"))
        tdx_rows = fetched_tdx
        tdx_note = tdx_note if tdx_note is not None else fetched_tdx_note
        tushare_rows = fetched_ts if tushare_rows is None else tushare_rows
        tushare_note = tushare_note if tushare_note is not None else fetched_ts_note
    tdx_note = tdx_note or "DATA_MISSING：未拉取通达信 HQServ JJQC"
    tushare_note = tushare_note or "DATA_MISSING：未拉取 Tushare stk_auction"
    write_store = persist if persist is not None else live
    seal_snapshots = build_seal_snapshots(
        tdx_rows=tdx_rows,
        tdx_note=tdx_note,
        tushare_rows=tushare_rows,
        tushare_note=tushare_note,
        boards=boards,
        stocks=list(snapshot.stocks),
        limit_up=list(snapshot.limit_up),
        now=moment,
        store=store,
        persist=write_store,
    )
    notes = list(bundle.notes)
    notes.append("集合竞价报告复用 STEP0 评分；9:15-9:20 与 9:20-9:25 无法拆分时保持 DATA_MISSING")
    notes.append("09:15/09:20/09:25 涨停封单额来自通达信 HQServ JJQC 抢筹委托金额，不用成交额/Tushare amount 冒充")
    notes.append("开盘换手仅在 09:25 使用 Tushare stk_auction.turnover_rate（9:26–9:29 才有当日成交）")
    if not ratio_ok:
        notes.append("量比不可用：竞价成交量爆量股标记 DATA_MISSING，不用成交额冒充量比")
    return AuctionDailyReport(
        meta=ReportMeta(
            generated_at=isoformat_cn(moment),
            quote_timestamp=bundle.quote_timestamp,
            title=settings.auction_report.title,
            version=settings.app.version,
        ),
        availability=availability,
        auction=auction,
        strongest=auction.strongest,
        weakest=auction.weakest,
        one_word_count=one_word_count,
        one_word_stocks=one_word_rows,
        scramble=scramble,
        volume_spikes=spikes,
        seal_snapshots=seal_snapshots,
        volume_ratio_available=ratio_ok,
        scramble_available=scramble_ok,
        source_notes=notes,
    )


def _strongest_one_word(
    board_name: str | None,
    snapshot: MarketSnapshot,
    boards: list[BoardQuote],
) -> tuple[int | None, list[AuctionOneWordRow]]:
    if not board_name:
        return None, []
    board = next((b for b in boards if b.name == board_name), None)
    codes = {s.code for s in (board.constituents if board else [])}
    names = {s.name for s in (board.constituents if board else [])}
    verified = bool(snapshot.limit_up) or any(s.is_one_word for s in snapshot.stocks)
    if not verified and not (board and board.constituents):
        return None, []
    hits: dict[str, AuctionOneWordRow] = {}
    for item in snapshot.limit_up:
        if not item.is_one_word:
            continue
        if item.code in codes or item.name in names or item.industry == board_name:
            hits[item.code] = _one_word_row(item, board_name)
    if board:
        for stock in board.constituents:
            if stock.is_one_word and stock.code not in hits:
                hits[stock.code] = AuctionOneWordRow(
                    code=stock.code,
                    name=stock.name,
                    board=board_name,
                    consecutive_boards=stock.consecutive_boards,
                    change_pct=stock.change_pct or stock.open_pct,
                )
    return len(hits), list(hits.values())


def _one_word_row(item: LimitStock, board_name: str) -> AuctionOneWordRow:
    return AuctionOneWordRow(
        code=item.code,
        name=item.name,
        board=board_name,
        consecutive_boards=item.consecutive_boards,
        first_board_time=item.first_board_time,
        change_pct=item.change_pct,
    )


def _is_scramble(stock: StockQuote, open_min: float, ratio_min: float) -> bool:
    if stock.open_pct is None or stock.open_pct < open_min:
        return False
    if stock.net_inflow is None or stock.net_inflow <= 0:
        return False
    if stock.volume_ratio is not None and stock.volume_ratio < ratio_min:
        return False
    return True


def _scramble_boards(
    boards: list[BoardQuote],
    open_min: float,
    ratio_min: float,
) -> tuple[list[AuctionScrambleRow], bool]:
    rows: list[AuctionScrambleRow] = []
    any_open = False
    for board in boards:
        if not board.constituents:
            continue
        if any(s.open_pct is not None for s in board.constituents):
            any_open = True
        grabbed = [s for s in board.constituents if _is_scramble(s, open_min, ratio_min)]
        if not grabbed:
            continue
        amount = sum(s.amount or 0 for s in grabbed) or None
        inflow = sum(s.net_inflow or 0 for s in grabbed) if any(s.net_inflow is not None for s in grabbed) else None
        leader = max(grabbed, key=lambda s: (s.open_pct or 0, s.amount or 0))
        rows.append(
            AuctionScrambleRow(
                board=board.name,
                kind=board.kind,
                scramble_count=len(grabbed),
                amount=amount,
                net_inflow=inflow,
                leader=leader.name,
                change_pct=board.change_pct,
                reason=f"高开>={open_min:g}%且净流入为正的成分股{len(grabbed)}只",
            )
        )
    rows.sort(key=lambda r: (r.amount or 0), reverse=True)
    return rows[:20], any_open


def _volume_spikes(
    snapshot: MarketSnapshot,
    boards: list[BoardQuote],
    spike_min: float,
) -> tuple[list[AuctionVolumeSpikeRow], bool]:
    stocks = list(snapshot.stocks)
    for board in boards:
        stocks.extend(board.constituents)
    seen: set[str] = set()
    unique: list[StockQuote] = []
    for stock in stocks:
        if not stock.code or stock.code in seen:
            continue
        seen.add(stock.code)
        unique.append(stock)
    ratio_ok = any(s.volume_ratio is not None for s in unique)
    if not ratio_ok:
        return [], False
    board_of: dict[str, str] = {}
    for board in boards:
        for stock in board.constituents:
            board_of.setdefault(stock.code, board.name)
    spikes = []
    for stock in unique:
        if stock.volume_ratio is None or stock.volume_ratio < spike_min:
            continue
        spikes.append(
            AuctionVolumeSpikeRow(
                code=stock.code,
                name=stock.name,
                volume_ratio=stock.volume_ratio,
                amount=stock.amount,
                open_pct=stock.open_pct,
                board=board_of.get(stock.code) or stock.industry,
            )
        )
    spikes.sort(key=lambda r: (r.volume_ratio or 0, r.amount or 0), reverse=True)
    return spikes[:30], True

