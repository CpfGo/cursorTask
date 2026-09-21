from __future__ import annotations

from html import escape

from ashare2026.constants import DATA_MISSING
from ashare2026.formatting import fmt_num, signed_pct, yi
from ashare2026.models.report import AuctionDailyReport
from ashare2026.report.html import (
    _CSS,
    _JS,
    _extreme,
    _kv,
    _m,
    _section,
    _stat,
    _table,
)


REQUIRED_MODULES = (
    "竞价最强方向",
    "竞价最弱方向",
    "竞价最强方向一字板数量",
    "竞价抢筹方向",
    "竞价成交量爆量股",
)


def render_auction_html(result: AuctionDailyReport) -> str:
    title = result.meta.title or "A股集合竞价报告"
    body = "\n".join(
        [
            _nav(),
            _hero(result),
            _availability(result),
            _strongest(result),
            _weakest(result),
            _one_word(result),
            _scramble(result),
            _spikes(result),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<header class="top">
  <div>
    <p class="kicker">机构交易台 · 集合竞价</p>
    <h1>{escape(title)}</h1>
    <p class="meta">生成时间 {escape(result.meta.generated_at)} · 行情时间戳 {escape(result.meta.quote_timestamp)} · V{escape(result.meta.version)}</p>
  </div>
</header>
<main>
{body}
</main>
<script>{_JS}</script>
</body>
</html>
"""


def _nav() -> str:
    items = [
        ("hero", "首屏"),
        ("availability", "数据源"),
        ("strongest", "竞价最强方向"),
        ("weakest", "竞价最弱方向"),
        ("oneword", "一字板数量"),
        ("scramble", "抢筹方向"),
        ("spikes", "成交量爆量股"),
    ]
    lis = "".join(f'<a href="#{i}">{escape(n)}</a>' for i, n in items)
    return f'<nav class="sidenav" id="sidenav">{lis}</nav>'


def _hero(result: AuctionDailyReport) -> str:
    a = result.auction
    count = DATA_MISSING if result.one_word_count is None else str(result.one_word_count)
    scramble = result.scramble[0].board if result.scramble_available and result.scramble else DATA_MISSING
    spike = (
        f"{result.volume_spikes[0].name} 量比{fmt_num(result.volume_spikes[0].volume_ratio, 2)}"
        if result.volume_ratio_available and result.volume_spikes
        else DATA_MISSING
    )
    return f"""
<section id="hero" class="hero">
<div class="cards">
  {_stat("竞价最强方向", a.strongest.board if a.strongest else DATA_MISSING, "gold")}
  {_stat("竞价最弱方向", a.weakest.board if a.weakest else DATA_MISSING, "down")}
  {_stat("竞价最强方向一字板数量", count, "")}
  {_stat("竞价抢筹方向", scramble, "gold")}
  {_stat("竞价成交量爆量股", spike, "")}
</div>
</section>
"""


def _availability(result: AuctionDailyReport) -> str:
    from ashare2026.report.html import _ok

    rows = [
        [
            r.item,
            r.preferred_source,
            _ok(r.available),
            r.timestamp or DATA_MISSING,
            r.actual_source or DATA_MISSING,
            r.impact or "—",
        ]
        for r in result.availability
    ]
    notes = "".join(f"<li>{escape(n)}</li>" for n in result.source_notes)
    table = _table(
        ["数据项", "首选来源", "是否可用", "时间戳", "实际来源", "缺失影响"],
        rows,
        numeric=[],
    )
    split = f'<p class="missing-inline">{escape(result.auction.split_missing or DATA_MISSING)}</p>'
    note = f'<p class="note">{escape(result.auction.note)}</p>' if result.auction.note else ""
    return _section("availability", "数据源与可用性", note + split + table + f'<ul class="notes">{notes}</ul>')


def _strongest(result: AuctionDailyReport) -> str:
    a = result.auction
    table = _table(
        ["类型", "板块", "强弱评分", "竞价龙头", "竞价涨幅", "竞价成交额", "即时资金流", "3日资金连续性", "判断依据"],
        [_extreme("最强", a.strongest), _extreme("第二强", a.second), _extreme("第三强", a.third)],
        numeric=[2],
    )
    return _section("strongest", "竞价最强方向", table)


def _weakest(result: AuctionDailyReport) -> str:
    table = _table(
        ["类型", "板块", "强弱评分", "竞价龙头", "竞价涨幅", "竞价成交额", "即时资金流", "3日资金连续性", "判断依据"],
        [_extreme("最弱", result.auction.weakest)],
        numeric=[2],
    )
    return _section("weakest", "竞价最弱方向", table)


def _one_word(result: AuctionDailyReport) -> str:
    count = DATA_MISSING if result.one_word_count is None else str(result.one_word_count)
    board = result.strongest.board if result.strongest else DATA_MISSING
    summary = _kv(
        [
            ("竞价最强方向", board),
            ("一字板数量", count),
        ]
    )
    rows = [
        [
            r.code,
            r.name,
            r.board or DATA_MISSING,
            str(r.consecutive_boards),
            r.first_board_time or DATA_MISSING,
            signed_pct(r.change_pct),
        ]
        for r in result.one_word_stocks
    ]
    table = _table(
        ["代码", "名称", "所属方向", "连板", "首次封板", "涨跌幅"],
        rows,
        numeric=[3],
    )
    empty = "" if rows else f'<p class="missing-inline">{escape(DATA_MISSING)}</p>'
    return _section("oneword", "竞价最强方向一字板数量", summary + table + empty)


def _scramble(result: AuctionDailyReport) -> str:
    if not result.scramble_available:
        inner = f'<p class="missing-inline">{escape(DATA_MISSING)}：无法用开盘涨幅与净流入验证抢筹方向</p>'
        return _section("scramble", "竞价抢筹方向", inner)
    if not result.scramble:
        inner = f'<p class="note">已验证开盘与资金字段，没有符合抢筹条件的板块。</p>'
        return _section("scramble", "竞价抢筹方向", inner)
    rows = [
        [
            r.board,
            r.kind,
            str(r.scramble_count),
            yi(r.amount),
            yi(r.net_inflow),
            r.leader or DATA_MISSING,
            signed_pct(r.change_pct),
            r.reason or DATA_MISSING,
        ]
        for r in result.scramble
    ]
    table = _table(
        ["板块", "类型", "抢筹股数", "抢筹成交额", "净流入", "代表股", "板块涨跌幅", "判断依据"],
        rows,
        numeric=[2, 3, 4],
    )
    return _section("scramble", "竞价抢筹方向", table)


def _spikes(result: AuctionDailyReport) -> str:
    if not result.volume_ratio_available:
        inner = f'<p class="missing-inline">{escape(DATA_MISSING)}：量比不可用，不把成交额冒充爆量</p>'
        return _section("spikes", "竞价成交量爆量股", inner)
    if not result.volume_spikes:
        inner = f'<p class="note">量比可用，但没有达到爆量阈值的股票；列表为空不等于编造。</p>'
        return _section("spikes", "竞价成交量爆量股", inner)
    rows = [
        [
            r.code,
            r.name,
            fmt_num(r.volume_ratio, 2),
            yi(r.amount),
            signed_pct(r.open_pct),
            r.board or DATA_MISSING,
        ]
        for r in result.volume_spikes
    ]
    table = _table(
        ["代码", "名称", "量比", "成交额", "开盘涨跌幅", "板块"],
        rows,
        numeric=[2, 3, 4],
    )
    return _section("spikes", "竞价成交量爆量股", table)
