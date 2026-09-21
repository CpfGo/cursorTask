from __future__ import annotations

from html import escape

from ashare2026.constants import DATA_MISSING
from ashare2026.formatting import fmt_num, money_cn, signed_pct
from ashare2026.models.report import AuctionDailyReport, AuctionSealSnapshot
from ashare2026.report.html import (
    _CSS,
    _JS,
    _kv,
    _section,
    _stat,
    _table,
)


REQUIRED_MODULES = (
    "竞价最强方向",
    "竞价最弱方向",
    "竞价最强方向一字板数量",
    "竞价抢筹方向",
    "09:15 涨停封单额超过1亿",
    "09:20 涨停封单额超过1亿",
    "09:25 涨停封单额超过1亿",
)


def render_auction_html(result: AuctionDailyReport) -> str:
    title = result.meta.title or "A股集合竞价报告"
    body = "\n".join(
        [
            _nav(),
            _hero(result),
            *[_seal(snap) for snap in _snapshots(result)],
            _strongest(result),
            _weakest(result),
            _one_word(result),
            _scramble(result),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<style>{_CSS}
.hero .cards{{grid-template-columns:repeat(4,1fr)}}
</style>
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


def _snapshots(result: AuctionDailyReport) -> list[AuctionSealSnapshot]:
    have = {s.clock: s for s in result.seal_snapshots}
    return [
        have.get(
            clock,
            AuctionSealSnapshot(clock=clock, count=None, available=False, note=DATA_MISSING),
        )
        for clock in ("09:15", "09:20", "09:25")
    ]


def _nav() -> str:
    items = [
        ("hero", "首屏"),
        ("seal-0915", "09:15 封单超过1亿"),
        ("seal-0920", "09:20 封单超过1亿"),
        ("seal-0925", "09:25 封单超过1亿"),
        ("strongest", "竞价最强方向"),
        ("weakest", "竞价最弱方向"),
        ("oneword", "一字板数量"),
        ("scramble", "抢筹方向"),
    ]
    lis = "".join(f'<a href="#{i}">{escape(n)}</a>' for i, n in items)
    return f'<nav class="sidenav" id="sidenav">{lis}</nav>'


def _hero(result: AuctionDailyReport) -> str:
    a = result.auction
    count = DATA_MISSING if result.one_word_count is None else str(result.one_word_count)
    scramble = result.scramble[0].board if result.scramble_available and result.scramble else DATA_MISSING
    return f"""
<section id="hero" class="hero">
<div class="cards">
  {_stat("竞价最强方向", a.strongest.board if a.strongest else DATA_MISSING, "gold")}
  {_stat("竞价最弱方向", a.weakest.board if a.weakest else DATA_MISSING, "down")}
  {_stat("竞价最强方向一字板数量", count, "")}
  {_stat("竞价抢筹方向", scramble, "gold")}
</div>
</section>
"""


def _seal(snap: AuctionSealSnapshot) -> str:
    section_id = f"seal-{snap.clock.replace(':', '')}"
    title = f"{snap.clock} 涨停封单额超过1亿"
    count = DATA_MISSING if snap.count is None else str(snap.count)
    summary = _kv(
        [
            ("时点", snap.clock),
            ("封单额>1亿家数", count),
            ("来源", snap.source or DATA_MISSING),
        ]
    )
    if not snap.available:
        inner = (
            summary
            + f'<p class="missing-inline">{escape(snap.note or DATA_MISSING)}</p>'
        )
        return _section(section_id, title, inner)
    rows = [
        [
            r.name,
            r.code,
            r.board or DATA_MISSING,
            r.industry or DATA_MISSING,
            DATA_MISSING if r.open_turnover is None else f"{r.open_turnover:.2f}%",
            money_cn(r.seal_amount),
        ]
        for r in snap.rows
    ]
    table = _table(
        ["名称", "代码", "板块", "细分行业", "开盘换手", "封单额"],
        rows,
        numeric=[4, 5],
    )
    empty = ""
    if not rows:
        empty = '<p class="note">已验证该时点涨停封单额，没有超过 1 亿的股票。</p>'
    note = f'<p class="note">{escape(snap.note)}</p>' if snap.note else ""
    return _section(section_id, title, summary + note + table + empty)


def _extreme(kind, row) -> list[str]:
    if row is None:
        return [kind, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING]
    return [
        kind,
        row.board,
        fmt_num(row.total, 1),
        row.leader or DATA_MISSING,
        signed_pct(row.change_pct),
        money_cn(row.amount),
        money_cn(row.net_inflow),
        row.continuity or DATA_MISSING,
        row.reason or DATA_MISSING,
    ]


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
            money_cn(r.amount),
            money_cn(r.net_inflow),
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
