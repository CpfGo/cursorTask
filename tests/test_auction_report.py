from datetime import datetime, time
from pathlib import Path

from ashare2026.constants import DATA_MISSING
from ashare2026.pipeline.auction_report import run_auction_report
from ashare2026.report.auction_html import REQUIRED_MODULES, render_auction_html
from ashare2026.schedule.auction_job import AUCTION_FIRE_TIME, AuctionScheduler, is_trading_day, next_run_at, parse_fire_time
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


def test_scheduler_stop_does_not_fire():
    fired = []
    sched = AuctionScheduler(lambda: fired.append(1) or None, now_fn=lambda: datetime(2026, 9, 21, 9, 25, 29, tzinfo=cn_tz()), sleep_chunk=0.01)
    sched.start()
    sched.stop()
    sched.stop_event.wait(0.2)
    assert fired == []
