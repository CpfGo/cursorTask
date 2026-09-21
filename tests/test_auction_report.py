from datetime import datetime, time
from pathlib import Path

from ashare2026.constants import DATA_MISSING
from ashare2026.data.auction_seal import SealSnapshotStore, clock_for
from ashare2026.data.fetchers.tongdaxin import parse_jjqc_datas
from ashare2026.data.fetchers.tushare import TushareAuctionPrint, parse_stk_auction_payload
from ashare2026.formatting import money_cn
from ashare2026.pipeline.auction_report import run_auction_report
from ashare2026.report.auction_html import REQUIRED_MODULES, render_auction_html
from ashare2026.report.html import render_html
from ashare2026.pipeline.engine import run_pipeline
from ashare2026.schedule.auction_job import (
    AUCTION_FIRE_TIME,
    SNAPSHOT_CAPTURE_TIMES,
    AuctionScheduler,
    is_trading_day,
    next_capture_at,
    next_run_at,
    parse_fire_time,
)
from ashare2026.timeutil import cn_tz
from tests.fixtures_data import make_bundle


def test_auction_report_modules_present():
    html = render_auction_html(run_auction_report(make_bundle()))
    assert html.startswith("<!DOCTYPE html>")
    assert "A股集合竞价报告" in html
    assert "A股主线识别日报" not in html
    for name in REQUIRED_MODULES:
        assert name in html
    assert "https://cdn" not in html.lower()
    assert "数据源与可用性" not in html
    assert 'id="availability"' not in html
    assert "09:15 涨停封单额超过1亿" in html
    assert "09:20 涨停封单额超过1亿" in html
    assert "09:25 涨停封单额超过1亿" in html


def test_daily_report_keeps_availability_section():
    html = render_html(run_pipeline(make_bundle()))
    assert "数据源与可用性" in html
    assert 'id="availability"' in html


def test_one_word_count_on_strongest_direction():
    bundle = make_bundle()
    bundle.snapshot.limit_up[0].is_one_word = True
    bundle.snapshot.limit_up[0].first_board_time = "92500"
    for board in bundle.concepts:
        for stock in board.constituents:
            if stock.code == "300394":
                stock.is_one_word = True
    result = run_auction_report(bundle)
    html = render_auction_html(result)
    assert "竞价最强方向一字板数量" in html
    if result.strongest and result.strongest.board in {"CPO概念", "光模块", "通信设备"}:
        assert result.one_word_count is not None
        assert result.one_word_count >= 1
        assert any(x.code == "300394" for x in result.one_word_stocks)


def test_volume_spike_missing_without_ratio():
    result = run_auction_report(make_bundle())
    assert result.volume_ratio_available is False
    assert result.volume_spikes == []
    html = render_auction_html(result)
    assert "量比不可用" in html


def test_volume_spike_uses_ratio_not_amount():
    bundle = make_bundle()
    bundle.snapshot.stocks[0].volume_ratio = 9.2
    bundle.snapshot.stocks[1].volume_ratio = 1.1
    result = run_auction_report(bundle)
    assert result.volume_ratio_available is True
    assert result.volume_spikes
    assert result.volume_spikes[0].code == bundle.snapshot.stocks[0].code
    assert all((row.volume_ratio or 0) >= 5 for row in result.volume_spikes)


def test_scramble_from_open_and_inflow():
    result = run_auction_report(make_bundle())
    assert result.scramble_available is True
    assert result.scramble
    html = render_auction_html(result)
    assert "竞价抢筹方向" in html


def test_does_not_invent_one_word_when_unverified():
    bundle = make_bundle()
    bundle.snapshot.limit_up = []
    for stock in bundle.snapshot.stocks:
        stock.is_one_word = False
    for board in bundle.concepts + bundle.industries:
        for stock in board.constituents:
            stock.is_one_word = False
    result = run_auction_report(bundle)
    html = render_auction_html(result)
    assert "竞价最强方向一字板数量" in html
    if result.one_word_count is None:
        assert DATA_MISSING in html
    else:
        assert result.one_word_count == 0


def test_cli_auction_report_command_registered():
    text = Path("src/ashare2026/cli.py").read_text(encoding="utf-8")
    assert "auction-report" in text
    assert "--no-scheduler" in text
    assert "enable_scheduler" in Path("src/ashare2026/api/app.py").read_text(encoding="utf-8")


def test_scheduler_hook_exists():
    assert AUCTION_FIRE_TIME == time(9, 25, 30)
    assert parse_fire_time() == time(9, 25, 30)
    assert hasattr(AuctionScheduler, "start")
    assert callable(next_run_at)
    assert is_trading_day(datetime(2026, 9, 21, 9, 0, tzinfo=cn_tz())) is True
    assert is_trading_day(datetime(2026, 9, 19, 9, 0, tzinfo=cn_tz())) is False


def test_next_run_skips_weekend_and_holiday():
    tz = cn_tz()
    monday_morning = datetime(2026, 9, 21, 8, 0, tzinfo=tz)
    assert next_run_at(monday_morning).isoformat()[:19] == "2026-09-21T09:25:30"
    monday_late = datetime(2026, 9, 21, 9, 26, tzinfo=tz)
    assert next_run_at(monday_late).date().isoformat() == "2026-09-22"
    saturday = datetime(2026, 9, 19, 8, 0, tzinfo=tz)
    nxt = next_run_at(saturday)
    assert nxt.weekday() == 0
    assert nxt.timetz().replace(tzinfo=None) == time(9, 25, 30)
    holiday = next_run_at(monday_morning, holidays={"2026-09-21"})
    assert holiday.date().isoformat() == "2026-09-22"


def test_snapshot_capture_times_and_clock_buckets():
    assert SNAPSHOT_CAPTURE_TIMES == (time(9, 15), time(9, 20), time(9, 25))
    tz = cn_tz()
    assert clock_for(datetime(2026, 9, 21, 9, 15, tzinfo=tz)) == "09:15"
    assert clock_for(datetime(2026, 9, 21, 9, 19, 59, tzinfo=tz)) == "09:15"
    assert clock_for(datetime(2026, 9, 21, 9, 20, tzinfo=tz)) == "09:20"
    assert clock_for(datetime(2026, 9, 21, 9, 25, 30, tzinfo=tz)) == "09:25"
    assert clock_for(datetime(2026, 9, 21, 10, 0, tzinfo=tz)) is None
    monday_morning = datetime(2026, 9, 21, 8, 0, tzinfo=tz)
    assert next_capture_at(monday_morning).isoformat()[:19] == "2026-09-21T09:15:00"
    after_open = datetime(2026, 9, 21, 9, 16, tzinfo=tz)
    assert next_capture_at(after_open).isoformat()[:19] == "2026-09-21T09:20:00"


def test_jjqc_seal_uses_unmatched_order_not_open_amount():
    datas = [
        ["000607", "华媒控股", 41200, 45300, 29_723_219, 0.0995, 374_564_409, 18_003_656, 4.53, 0, 1, 1],
        ["603230", "内蒙新华", 10000, 11000, 95_747_166, 0.1001, 75_400_169, 10_000_000, 11.0, 0, 1, 0],
        ["600000", "浦发银行", 10000, 10100, 500_000_000, 0.01, 400_000_000, 1_000_000, 10.1, 0, 1, 0],
    ]
    rows = parse_jjqc_datas(datas)
    by_code = {r.code: r for r in rows}
    assert by_code["000607"].is_limit_up is True
    assert by_code["000607"].seal_amount == 374_564_409
    assert by_code["000607"].open_amount == 29_723_219
    assert by_code["603230"].is_limit_up is True
    assert by_code["603230"].seal_amount == 75_400_169
    assert by_code["600000"].is_limit_up is False


def test_three_seal_snapshots_and_money_format(tmp_path):
    tz = cn_tz()
    now = datetime(2026, 9, 21, 9, 26, tzinfo=tz)
    tdx = parse_jjqc_datas(
        [
            ["000607", "华媒控股", 41200, 45300, 29_723_219, 0.0995, 374_564_409, 18_003_656, 4.53],
            ["603230", "内蒙新华", 10000, 11000, 200_000_000, 0.1001, 75_400_169, 10_000_000, 11.0],
        ]
    )
    tushare = [
        TushareAuctionPrint(ts_code="000607.SZ", code="000607", turnover_rate=1.23, amount=99_000_000),
        TushareAuctionPrint(ts_code="603230.SH", code="603230", turnover_rate=0.5, amount=888_000_000),
    ]
    store = SealSnapshotStore(tmp_path)
    store.save_clock(
        "20260921",
        "09:15",
        {
            "captured_at": "2026-09-21 09:15:02 CST",
            "source": "通达信 HQServ JJQC 抢筹委托金额（涨停开盘未匹配买单）",
            "rows": [
                {
                    "name": "华瓷股份",
                    "code": "001216",
                    "board": "陶瓷",
                    "industry": "陶瓷",
                    "open_turnover": None,
                    "seal_amount": 283_581_122,
                }
            ],
        },
    )
    result = run_auction_report(
        make_bundle(),
        tdx_rows=tdx,
        tdx_note="通达信 HQServ JJQC",
        tushare_rows=tushare,
        tushare_note="Tushare stk_auction",
        now=now,
        store=store,
        persist=False,
    )
    by_clock = {s.clock: s for s in result.seal_snapshots}
    assert set(by_clock) == {"09:15", "09:20", "09:25"}
    assert by_clock["09:15"].available is True
    assert by_clock["09:15"].count == 1
    assert by_clock["09:15"].rows[0].code == "001216"
    assert by_clock["09:15"].rows[0].open_turnover is None
    assert by_clock["09:20"].available is False
    assert by_clock["09:20"].count is None
    assert by_clock["09:25"].available is True
    codes_925 = {r.code for r in by_clock["09:25"].rows}
    assert "000607" in codes_925
    assert "603230" not in codes_925
    row = next(r for r in by_clock["09:25"].rows if r.code == "000607")
    assert row.seal_amount == 374_564_409
    assert row.open_turnover == 1.23
    html = render_auction_html(result)
    assert "数据源与可用性" not in html
    assert "3.75亿" in html
    assert "2.84亿" in html
    assert money_cn(374_564_409) == "3.75亿"
    assert "99" + "000000" not in html.replace(",", "")
    assert html.count("09:15 涨停封单额超过1亿") >= 1
    assert "不能用 09:25" in by_clock["09:20"].note or DATA_MISSING in (by_clock["09:20"].note or "")


def test_tushare_amount_is_not_seal():
    payload = {
        "code": 0,
        "data": {
            "fields": ["ts_code", "trade_date", "vol", "price", "amount", "pre_close", "turnover_rate", "volume_ratio", "float_share"],
            "items": [["000607.SZ", "20260921", 1000, 4.53, 88_000_000, 4.12, 1.5, 2.0, 10000]],
        },
    }
    rows = parse_stk_auction_payload(payload)
    assert rows[0].amount == 88_000_000
    assert rows[0].turnover_rate == 1.5
    html = render_auction_html(
        run_auction_report(
            make_bundle(),
            tdx_rows=[],
            tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
            tushare_rows=rows,
            tushare_note="Tushare stk_auction",
            now=datetime(2026, 9, 21, 9, 28, tzinfo=cn_tz()),
            persist=False,
        )
    )
    assert "8800万" not in html
    assert "0.88亿" not in html


def test_scheduler_stop_does_not_fire():
    fired = []
    sched = AuctionScheduler(lambda: fired.append(1) or None, now_fn=lambda: datetime(2026, 9, 21, 9, 25, 29, tzinfo=cn_tz()), sleep_chunk=0.01)
    sched.start()
    sched.stop()
    sched.stop_event.wait(0.2)
    assert fired == []
