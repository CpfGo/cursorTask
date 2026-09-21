from datetime import datetime

from ashare2026.constants import DATA_MISSING
from ashare2026.data.fetchers.em_seal import EM_SEAL_SOURCE, parse_zt_pool_seal, rows_from_limit_fund
from ashare2026.data.fetchers.ths_seal import THS_SEAL_SOURCE, parse_ths_limit_pool_payload, seal_amount_from_mapping
from ashare2026.data.ths_html import parse_seal_amount_table
from ashare2026.models.market import LimitStock
from ashare2026.models.report import AuctionSealRow
from ashare2026.pipeline.auction_report import run_auction_report
from ashare2026.report.auction_html import render_auction_html
from ashare2026.timeutil import cn_tz
from tests.fixtures_data import make_bundle


EM_XINHUA = {
    "data": {
        "pool": [
            {
                "c": "600825",
                "n": "新华传媒",
                "fund": 3_582_000_000,
                "amount": 12_531_822,
                "hs": 0.205,
                "hybk": "出版",
                "zdp": 9.98,
                "fbt": 92502,
            },
            {
                "c": "000001",
                "n": "平安银行",
                "fund": 50_000_000,
                "amount": 900_000_000,
                "hs": 1.2,
                "hybk": "银行",
                "zdp": 9.99,
            },
        ]
    }
}

THS_WITH_SEAL = {
    "status_code": 0,
    "data": {
        "info": [
            {
                "code": "600825",
                "name": "新华传媒",
                "order_amount": 3_580_000_000,
                "amount": 12_531_822,
                "hs": 0.205,
                "hybk": "出版",
                "change_rate": 0.0998,
            }
        ]
    },
}

THS_NO_SEAL = {
    "status_code": 0,
    "data": {
        "info": [
            {"code": "600825", "name": "新华传媒", "amount": 12_531_822, "hs": 0.205, "change_tag": "FIRST_LIMIT"}
        ]
    },
}


def _now():
    return datetime(2026, 9, 21, 9, 28, tzinfo=cn_tz())


def test_em_fund_is_seal_amount_never_amount_or_hs():
    rows = parse_zt_pool_seal(EM_XINHUA, min_yuan=1e8)
    assert len(rows) == 1
    row = rows[0]
    assert row.code == "600825"
    assert row.seal_amount == 3_582_000_000
    assert row.industry == "出版"
    assert row.open_turnover is None
    assert row.source == EM_SEAL_SOURCE
    html = render_auction_html(
        run_auction_report(
            make_bundle(),
            tdx_rows=[],
            tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
            tushare_rows=[],
            tushare_note="DATA_MISSING：未拉取 Tushare stk_auction",
            now=_now(),
            persist=False,
            tdx_exports={},
            ths_rows=[],
            ths_note="DATA_MISSING：同花顺无封单额字段",
            em_rows=rows,
            em_note=EM_SEAL_SOURCE,
        )
    )
    assert "35.82亿" in html
    assert "1253万" not in html
    assert "0.21%" not in html
    assert "getTopicZTPool" in html
    assert "数据源与可用性" not in html
    assert "竞价成交量爆量股" in html


def test_em_does_not_fill_0915_or_0920():
    em_rows = parse_zt_pool_seal(EM_XINHUA, min_yuan=1e8)
    result = run_auction_report(
        make_bundle(),
        tdx_rows=[],
        tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
        tushare_rows=[],
        tushare_note="DATA_MISSING：未设置环境变量 TUSHARE_TOKEN，无法取 stk_auction 开盘换手",
        now=_now(),
        persist=False,
        tdx_exports={},
        ths_rows=[],
        ths_note="DATA_MISSING：同花顺无封单额字段",
        em_rows=em_rows,
        em_note=EM_SEAL_SOURCE,
    )
    by_clock = {s.clock: s for s in result.seal_snapshots}
    assert set(by_clock) == {"09:15", "09:20", "09:25"}
    assert by_clock["09:15"].available is False
    assert by_clock["09:20"].available is False
    assert by_clock["09:25"].available is True
    assert by_clock["09:25"].rows[0].code == "600825"
    assert "不能用 09:25" in (by_clock["09:15"].note or "")
    assert DATA_MISSING in (by_clock["09:15"].note or "")


def test_fallback_order_tdx_beats_ths_beats_em():
    from ashare2026.data.fetchers.tongdaxin import TdxAuctionRow, TdxQuoteExport
    from pathlib import Path

    tdx_row = TdxAuctionRow(
        code="600825",
        name="新华传媒",
        seal_amount=3_580_000_000,
        is_limit_up=True,
        board="文化传媒",
        industry="出版",
        open_turnover=2.15,
    )
    export = TdxQuoteExport(
        clock="09:25",
        day="20260921",
        path=Path("涨停_20260921_0925.txt"),
        rows=[tdx_row],
        source="通达信本地涨停报价列表 涨停_20260921_0925.txt（封单额列，09:25）",
        captured_at=_now(),
        clock_from="filename",
    )
    ths = [
        AuctionSealRow(
            name="新华传媒",
            code="600825",
            industry="出版",
            seal_amount=1_110_000_000,
            source=THS_SEAL_SOURCE,
        )
    ]
    em = parse_zt_pool_seal(EM_XINHUA, min_yuan=1e8)
    result = run_auction_report(
        make_bundle(),
        tdx_rows=[],
        tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
        tushare_rows=[],
        tushare_note="Tushare stk_auction",
        now=_now(),
        persist=False,
        tdx_exports={"09:25": export},
        ths_rows=ths,
        ths_note=THS_SEAL_SOURCE,
        em_rows=em,
        em_note=EM_SEAL_SOURCE,
    )
    snap = {s.clock: s for s in result.seal_snapshots}["09:25"]
    assert snap.rows[0].seal_amount == 3_580_000_000
    assert "通达信" in snap.source
    assert "同花顺" not in snap.source
    assert "东方财富" not in snap.source

    result_ths = run_auction_report(
        make_bundle(),
        tdx_rows=[],
        tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
        tushare_rows=[],
        tushare_note="Tushare stk_auction",
        now=_now(),
        persist=False,
        tdx_exports={},
        ths_rows=ths,
        ths_note=THS_SEAL_SOURCE,
        em_rows=em,
        em_note=EM_SEAL_SOURCE,
    )
    snap_ths = {s.clock: s for s in result_ths.seal_snapshots}["09:25"]
    assert snap_ths.rows[0].seal_amount == 1_110_000_000
    assert "同花顺" in snap_ths.source
    assert "东方财富" not in snap_ths.source

    result_em = run_auction_report(
        make_bundle(),
        tdx_rows=[],
        tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
        tushare_rows=[],
        tushare_note="Tushare stk_auction",
        now=_now(),
        persist=False,
        tdx_exports={},
        ths_rows=[],
        ths_note="DATA_MISSING：同花顺公开接口未返回封单额",
        em_rows=em,
        em_note=EM_SEAL_SOURCE,
    )
    snap_em = {s.clock: s for s in result_em.seal_snapshots}["09:25"]
    assert snap_em.rows[0].seal_amount == 3_582_000_000
    assert "东方财富" in snap_em.source
    assert snap_em.rows[0].open_turnover is None


def test_ths_parses_order_amount_not_matched_amount():
    assert seal_amount_from_mapping({"amount": 12_531_822, "hs": 0.2}) is None
    assert seal_amount_from_mapping({"order_amount": 3.58e9, "amount": 12_531_822}) == 3.58e9
    rows = parse_ths_limit_pool_payload(THS_WITH_SEAL, min_yuan=1e8)
    assert rows[0].seal_amount == 3.58e9
    assert parse_ths_limit_pool_payload(THS_NO_SEAL, min_yuan=1e8) == []


def test_ths_html_needs_seal_column():
    html_ok = """
    <table><thead><tr><th>代码</th><th>名称</th><th>封单额</th><th>成交额</th></tr></thead>
    <tbody><tr><td>600825</td><td>新华传媒</td><td>35.8亿</td><td>1253万</td></tr></tbody></table>
    """
    html_amount_only = """
    <table><thead><tr><th>代码</th><th>名称</th><th>成交额</th></tr></thead>
    <tbody><tr><td>600825</td><td>新华传媒</td><td>35.8亿</td></tr></tbody></table>
    """
    rows = parse_seal_amount_table(html_ok)
    assert rows[0]["code"] == "600825"
    assert rows[0]["seal_amount"] == 3.58e9
    assert parse_seal_amount_table(html_amount_only) == []


def test_limit_stock_amount_is_not_used_as_seal():
    items = [
        LimitStock(code="600825", name="新华传媒", amount=12_531_822, fund=None, industry="出版"),
        LimitStock(code="000607", name="华媒控股", amount=99_000_000, fund=374_564_409, industry="出版"),
    ]
    rows = rows_from_limit_fund(items, min_yuan=1e8)
    assert [r.code for r in rows] == ["000607"]
    assert rows[0].seal_amount == 374_564_409


def test_data_missing_only_after_all_sources_fail():
    result = run_auction_report(
        make_bundle(),
        tdx_rows=[],
        tdx_note="DATA_MISSING：通达信 HQServ JJQC 未返回可解析行",
        tushare_rows=[],
        tushare_note="DATA_MISSING：未设置环境变量 TUSHARE_TOKEN，无法取 stk_auction 开盘换手",
        now=_now(),
        persist=False,
        tdx_exports={},
        ths_rows=[],
        ths_note="DATA_MISSING：同花顺公开接口未返回封单额",
        em_rows=[],
        em_note="DATA_MISSING：东方财富 getTopicZTPool 无响应",
    )
    by_clock = {s.clock: s for s in result.seal_snapshots}
    assert by_clock["09:15"].available is False
    assert by_clock["09:20"].available is False
    assert by_clock["09:25"].available is False
    note = by_clock["09:25"].note or ""
    assert note.startswith(DATA_MISSING)
    assert "同花顺" in note
    assert "东方财富" in note
    html = render_auction_html(result)
    assert "数据源与可用性" not in html
    assert "竞价成交量爆量股" in html
    assert html.count("09:15 涨停封单额超过1亿") >= 1
    assert html.count("09:20 涨停封单额超过1亿") >= 1
    assert html.count("09:25 涨停封单额超过1亿") >= 1
