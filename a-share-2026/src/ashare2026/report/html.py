from __future__ import annotations

from html import escape

from ashare2026.constants import DATA_INSUFFICIENT_BANNER, DATA_MISSING
from ashare2026.formatting import fmt_num, pct, signed_pct, yi
from ashare2026.models.report import PipelineResult


def render_html(result: PipelineResult) -> str:
    body = "\n".join(
        [
            _nav(),
            _hero(result),
            _availability(result),
            _auction(result),
            _market(result),
            _roadmap(result),
            _boards(result),
            _flows(result),
            _continuity(result),
            _scarcity(result),
            _leaders(result),
            _money(result),
            _etf(result),
            _cycles(result),
            _scores(result),
            _weak(result),
            _position(result),
            _falsify(result),
            _oneliner(result),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>A股主线识别日报</title>
<style>{_CSS}</style>
</head>
<body>
<header class="top">
  <div>
    <p class="kicker">机构交易台 · 主线识别</p>
    <h1>A股主线识别日报</h1>
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
        ("auction", "集合竞价"),
        ("market", "市场状态"),
        ("roadmap", "资金路线图"),
        ("boards", "成交额排名"),
        ("flows", "即时资金"),
        ("continuity", "资金连续性"),
        ("scarcity", "产业链卡点"),
        ("leaders", "龙头梯队"),
        ("money", "赚钱效应"),
        ("etf", "ETF资金"),
        ("cycles", "周期阶段"),
        ("scores", "主线评分"),
        ("weak", "最弱方向"),
        ("position", "仓位"),
        ("falsify", "反证条件"),
        ("oneliner", "一句话结论"),
    ]
    lis = "".join(f'<a href="#{i}">{escape(n)}</a>' for i, n in items)
    return f'<nav class="sidenav" id="sidenav">{lis}</nav>'


def _hero(result: PipelineResult) -> str:
    banner = ""
    if result.meta.insufficient:
        banner = f'<div class="banner missing">{escape(DATA_INSUFFICIENT_BANNER)}</div>'
    h = result.headline
    return f"""
<section id="hero" class="hero">
{banner}
<div class="cards">
  {_stat("集合竞价最强板块", h.auction_strongest, "gold")}
  {_stat("市场第一主线", h.first_chain, "gold")}
  {_stat("市场最弱方向", h.weakest, "down")}
  {_stat("当前市场状态", h.market_state, "up" if h.market_state=="主升浪" else "")}
  {_stat("推荐仓位", f"{result.position.position} {result.position.range}", "")}
</div>
</section>
"""


def _availability(result: PipelineResult) -> str:
    rows = []
    for r in result.availability:
        rows.append(
            [
                r.item,
                r.preferred_source,
                _ok(r.available),
                _m(r.timestamp),
                _m(r.actual_source),
                r.impact or "—",
            ]
        )
    notes = "".join(f"<li>{escape(n)}</li>" for n in result.source_notes)
    table = _table(
        ["数据项", "首选来源", "是否可用", "时间戳", "实际来源", "缺失影响"],
        rows,
        numeric=[],
    )
    return _section("availability", "数据源与可用性", table + f'<ul class="notes">{notes}</ul>')


def _auction(result: PipelineResult) -> str:
    a = result.auction
    note = f'<p class="note">{escape(a.note)}</p>' if a.note else ""
    split = f'<p class="missing-inline">{escape(a.split_missing or DATA_MISSING)}</p>'
    env = _kv(
        [
            ("上证指数竞价涨跌幅", signed_pct(a.shanghai_open_pct)),
            ("深证成指竞价涨跌幅", signed_pct(a.shenzhen_open_pct)),
            ("创业板指竞价涨跌幅", signed_pct(a.chi_next_open_pct)),
            ("全A高开家数", _m(a.high_open_count)),
            ("全A低开家数", _m(a.low_open_count)),
            ("涨停开盘家数", _m(a.limit_up_open)),
            ("跌停开盘家数", _m(a.limit_down_open)),
            ("一字板家数", _m(a.one_word)),
            ("连板高开家数", _m(a.consecutive_high_open)),
            ("连板低开家数", _m(a.consecutive_low_open)),
            ("开盘环境", a.open_environment or DATA_MISSING),
            ("开盘可参与度", a.participation or DATA_MISSING),
        ]
    )
    body = []
    for s in a.board_scores:
        cls = ""
        if a.strongest and s.board == a.strongest.board:
            cls = "hl-strong"
        if a.weakest and s.board == a.weakest.board:
            cls = "hl-weak"
        body.append(
            (
                [
                    s.board,
                    fmt_num(s.change_score, 1),
                    fmt_num(s.high_open_score, 1),
                    fmt_num(s.limit_score, 1),
                    fmt_num(s.leader_score, 1),
                    fmt_num(s.flow_score, 1),
                    fmt_num(s.continuity_score, 1),
                    fmt_num(s.penalty, 1),
                    fmt_num(s.total, 1),
                    str(s.rank),
                    s.rating,
                ],
                cls,
            )
        )
    table = _table_cls(
        ["板块", "涨幅分", "高开分", "涨停分", "龙头分", "资金分", "连续性分", "负反馈扣分", "总分", "排名", "评级"],
        body,
        numeric=list(range(1, 10)),
    )
    extreme = _table(
        ["类型", "板块", "强弱评分", "竞价龙头", "竞价涨幅", "竞价成交额", "即时资金流", "3日资金连续性", "判断依据"],
        [
            _extreme("最强", a.strongest),
            _extreme("第二强", a.second),
            _extreme("第三强", a.third),
            _extreme("最弱", a.weakest),
        ],
        numeric=[2],
    )
    return _section("auction", "集合竞价强弱", note + split + env + table + extreme)


def _extreme(kind, row) -> list[str]:
    if row is None:
        return [kind, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING, DATA_MISSING]
    return [
        kind,
        row.board,
        fmt_num(row.total, 1),
        row.leader or DATA_MISSING,
        signed_pct(row.change_pct),
        yi(row.amount),
        yi(row.net_inflow),
        row.continuity or DATA_MISSING,
        row.reason or DATA_MISSING,
    ]


def _market(result: PipelineResult) -> str:
    m = result.market
    kv = _kv(
        [
            ("全市场成交额", yi(m.total_amount)),
            ("沪深300涨跌幅", signed_pct(m.hs300_pct)),
            ("创业板涨跌幅", signed_pct(m.chi_next_pct)),
            ("中证1000涨跌幅", signed_pct(m.zz1000_pct)),
            ("上涨家数", _m(m.up_count)),
            ("下跌家数", _m(m.down_count)),
            ("涨停家数", _m(m.limit_up)),
            ("跌停家数", _m(m.limit_down)),
            ("连板家数", _m(m.consecutive)),
            ("20cm家数", _m(m.cm20)),
            ("市场状态", m.state),
            ("判断依据", m.reason),
        ]
    )
    return _section("market", "市场状态总览", kv)


def _roadmap(result: PipelineResult) -> str:
    r = result.roadmap
    kv = _kv(
        [
            ("竞价资金攻击", r.auction_attack),
            ("盘中资金流向", r.intraday_flow),
            ("正在扩散到", r.spreading_to),
            ("正在回避", r.avoiding),
        ]
    )
    return _section("roadmap", "今日资金路线图", kv)


def _boards(result: PipelineResult) -> str:
    ind = _table(
        ["排名", "行业", "涨跌幅", "成交额", "上涨家数", "下跌家数", "领涨股"],
        [
            [
                str(i),
                b.name,
                signed_pct(b.change_pct),
                yi(b.amount),
                _m(b.up_count),
                _m(b.down_count),
                b.leader_name or DATA_MISSING,
            ]
            for i, b in enumerate(result.industries, 1)
        ],
        numeric=[0, 2, 3, 4, 5],
    )
    con = _table(
        ["排名", "概念", "涨跌幅", "成交额", "上涨家数", "下跌家数", "领涨股"],
        [
            [
                str(i),
                b.name,
                signed_pct(b.change_pct),
                yi(b.amount),
                _m(b.up_count),
                _m(b.down_count),
                b.leader_name or DATA_MISSING,
            ]
            for i, b in enumerate(result.concepts, 1)
        ],
        numeric=[0, 2, 3, 4, 5],
    )
    return _section("boards", "行业/概念成交额排名", "<h3>行业成交额/涨幅 TOP20</h3>" + ind + "<h3>概念成交额/涨幅 TOP20</h3>" + con)


def _flows(result: PipelineResult) -> str:
    table = _table(
        ["排名", "概念", "即时净流入", "涨跌幅", "主买额", "主卖额", "资金强度"],
        [
            [
                str(i),
                f.name,
                yi(f.instant_inflow),
                signed_pct(f.change_pct),
                yi(f.main_buy),
                yi(f.main_sell),
                fmt_num(f.strength, 2),
            ]
            for i, f in enumerate(result.concept_flows, 1)
        ],
        numeric=[0, 2, 3, 4, 5, 6],
    )
    return _section("flows", "概念即时资金流排名", table)


def _continuity(result: PipelineResult) -> str:
    table = _table(
        ["概念", "即时净流入排名", "3日流入排名", "5日流入排名", "连续性评级"],
        [
            [
                c.name,
                _m(c.instant_rank),
                _m(c.rank_3d),
                _m(c.rank_5d),
                c.rating or DATA_MISSING,
            ]
            for c in result.continuity
        ],
        numeric=[1, 2, 3],
    )
    chain_table = _table(
        ["排名", "产业链", "行业/概念映射", "成交额", "占全市场成交额比例", "即时净流入", "3日资金连续性", "5日资金连续性"],
        [
            [
                str(i),
                c.name,
                "、".join(c.mapped_boards[:6]) or DATA_MISSING,
                yi(c.amount),
                pct(c.amount_share),
                yi(c.net_inflow),
                c.continuity_3d or DATA_MISSING,
                c.continuity_5d or DATA_MISSING,
            ]
            for i, c in enumerate(result.chains[:20], 1)
        ],
        numeric=[0, 3, 4, 5],
    )
    return _section("continuity", "概念3日/5日资金连续性", table + "<h3>成交额主线排名</h3>" + chain_table)


def _scarcity(result: PipelineResult) -> str:
    table = _table(
        ["产业链", "当前最稀缺环节", "稀缺原因", "资金是否认可", "证据强度"],
        [[s.chain, s.scarce_link, s.reason, s.fund_recognized, s.evidence] for s in result.scarcity],
        numeric=[],
    )
    return _section("scarcity", "产业链卡点判断", table)


def _leaders(result: PipelineResult) -> str:
    t1 = _table(
        ["产业链", "龙头", "涨跌幅", "成交额", "个股净流入", "是否涨停/连板", "是否新高", "稀缺环节位置"],
        [
            [x.chain, x.name, signed_pct(x.change_pct), yi(x.amount), yi(x.net_inflow), x.limit_flag, x.new_high, x.position]
            for x in result.leaders
        ],
        numeric=[2, 3, 4],
    )
    t2 = _table(
        ["产业链", "个股", "涨跌幅", "成交额", "个股净流入", "产业链位置"],
        [
            [x.chain, x.name, signed_pct(x.change_pct), yi(x.amount), yi(x.net_inflow), x.position]
            for x in result.mids
        ],
        numeric=[2, 3, 4],
    )
    t3 = _table(
        ["产业链", "个股", "涨跌幅", "成交额", "个股净流入", "补涨逻辑"],
        [
            [x.chain, x.name, signed_pct(x.change_pct), yi(x.amount), yi(x.net_inflow), x.logic or DATA_MISSING]
            for x in result.follows
        ],
        numeric=[2, 3, 4],
    )
    return _section("leaders", "龙头梯队", "<h3>第一梯队：总龙头</h3>" + t1 + "<h3>第二梯队：中军</h3>" + t2 + "<h3>第三梯队：补涨</h3>" + t3)


def _money(result: PipelineResult) -> str:
    ech = _table(
        ["产业链", "龙头", "中军数量", "补涨数量", "涨停数量", "连板数量", "梯队结构", "完整度评分"],
        [
            [e.chain, e.leader, str(e.mid_count), str(e.follow_count), str(e.limit_up_count), str(e.consecutive_count), e.structure, fmt_num(e.completeness, 1)]
            for e in result.echelons
        ],
        numeric=[2, 3, 4, 5, 7],
    )
    mon = _table(
        ["产业链", "涨停", "20cm", "连板", ">10%", "跌停", "大跌>7%", "赚钱效应评分"],
        [
            [m.chain, str(m.limit_up), str(m.cm20), str(m.consecutive), str(m.over_10), str(m.limit_down), str(m.dump_7), fmt_num(m.score, 2)]
            for m in result.money
        ],
        numeric=list(range(1, 8)),
    )
    return _section("money", "赚钱效应", "<h3>梯队完整性</h3>" + ech + mon)


def _etf(result: PipelineResult) -> str:
    table = _table(
        ["产业链", "代表ETF", "ETF成交额", "ETF成交额占比", "ETF涨跌幅", "5日资金流", "10日资金流", "20日资金流", "净申购排名"],
        [
            [
                e.chain,
                e.etf_name or DATA_MISSING,
                yi(e.amount),
                pct(e.amount_share),
                signed_pct(e.change_pct),
                yi(e.flow_5d) if e.flow_5d is not None else DATA_MISSING,
                yi(e.flow_10d) if e.flow_10d is not None else DATA_MISSING,
                DATA_MISSING if e.flow_20d is None else yi(e.flow_20d),
                e.purchase_rank or DATA_MISSING,
            ]
            for e in result.etfs
        ],
        numeric=[2, 3, 4, 5, 6],
    )
    return _section("etf", "ETF资金分析", table)


def _cycles(result: PipelineResult) -> str:
    table = _table(
        ["产业链", "产业周期阶段", "资金运作阶段", "数据理由"],
        [[c.chain, c.industry_cycle, c.fund_stage, c.reason] for c in result.cycles],
        numeric=[],
    )
    return _section("cycles", "产业周期与资金运作阶段", table)


def _scores(result: PipelineResult) -> str:
    body = []
    top = result.scores[0].chain if result.scores else None
    for s in result.scores:
        cls = "hl-top" if s.chain == top else ""
        body.append(
            (
                [
                    s.chain,
                    fmt_num(s.turnover_score, 1),
                    fmt_num(s.flow_score, 1),
                    fmt_num(s.continuity_score, 1),
                    fmt_num(s.leader_score, 1),
                    fmt_num(s.echelon_score, 1),
                    fmt_num(s.etf_score, 1),
                    fmt_num(s.money_score, 1),
                    fmt_num(s.total, 1),
                    str(s.rank),
                    s.level,
                ],
                cls,
            )
        )
    table = _table_cls(
        ["产业链", "成交额分", "即时资金分", "连续性分", "龙头分", "梯队分", "ETF分", "赚钱效应分", "总分", "排名", "级别"],
        body,
        numeric=list(range(1, 10)),
    )
    return _section("scores", "主线评分", table)


def _weak(result: PipelineResult) -> str:
    table = _table(
        ["排名", "弱势板块/产业链", "跌幅", "资金流出", "跌停/大跌数量", "负反馈个股", "弱势原因"],
        [
            [str(w.rank), w.name, signed_pct(w.change_pct), yi(w.outflow), _m(w.dump_count), w.negative_stocks, w.reason]
            for w in result.weakest
        ],
        numeric=[0, 2, 3, 4],
    )
    return _section("weak", "最弱方向", table)


def _position(result: PipelineResult) -> str:
    p = result.position
    kv = _kv([(k, v) for k, v in p.factors.items()] + [("仓位", f"{p.position} {p.range}"), ("触发条件", p.trigger)])
    return _section("position", "仓位判断", kv)


def _falsify(result: PipelineResult) -> str:
    table = _table(
        ["主线", "当前判断", "反证条件"],
        [[f.chain, f.current, "；".join(f.conditions)] for f in result.falsify],
        numeric=[],
    )
    h = result.headline
    cards = f"""
    <h3>最终结论</h3>
    <div class="grid2">
      <article><h4>集合竞价结论</h4>
        <p>竞价最强板块：{_m(h.auction_strongest)}</p>
        <p>竞价第二强板块：{_m(h.auction_second)}</p>
        <p>竞价第三强板块：{_m(h.auction_third)}</p>
        <p>竞价最弱板块：{_m(h.auction_weakest)}</p>
        <p>开盘市场状态：{_m(h.open_state)}</p>
        <p>开盘可参与度：{_m(h.participation)}</p>
      </article>
      {_mainline_article("市场第一主线", result.first)}
      {_mainline_article("市场第二主线", result.second)}
      {_mainline_article("市场第三主线", result.third)}
    </div>
    """
    return _section("falsify", "反证条件", table + cards)


def _mainline_article(title, card) -> str:
    return f"""<article><h4>{escape(title)}</h4>
      <p>产业链：{_m(card.chain)}</p>
      <p>产业周期阶段：{_m(card.cycle)}</p>
      <p>资金运作阶段：{_m(card.fund_stage)}</p>
      <p>核心稀缺环节：{_m(card.scarce_link)}</p>
      <p>即时资金依据：{_m(card.instant_flow)}</p>
      <p>3日/5日资金连续性：{_m(card.continuity)}</p>
      <p>总龙头：{_m(card.leader)}</p>
      <p>中军：{_m(card.mids)}</p>
      <p>补涨：{_m(card.follows)}</p>
      <p>反证条件：{_m(card.falsify)}</p>
    </article>"""


def _oneliner(result: PipelineResult) -> str:
    o = result.one_liner
    kv = _kv(
        [
            ("今天集合竞价最强板块是", o.auction_strongest),
            ("今天真正吸引增量资金的产业链是", o.incremental_chain),
            ("当前资金运作阶段是", o.fund_stage),
            ("最弱回避方向是", o.weakest),
            ("是否值得继续配置", o.worth_holding),
        ]
    )
    return _section("oneliner", "一句话结论", kv + '<p class="note">仅基于当前资金强度回答，不给买卖指令。</p>')


def _section(sid: str, title: str, inner: str) -> str:
    return f'<section id="{sid}" class="mod"><h2 class="mod-title">{escape(title)}</h2><div class="mod-body">{inner}</div></section>'


def _stat(label: str, value: str, cls: str) -> str:
    return f'<article class="stat {cls}"><span>{escape(label)}</span><strong>{_m(value)}</strong></article>'


def _kv(pairs: list[tuple[str, str]]) -> str:
    rows = "".join(
        f"<tr><th>{escape(k)}</th><td>{_m(v)}</td></tr>" for k, v in pairs
    )
    return f'<div class="scroll"><table class="kv">{rows}</table></div>'


def _ok(flag: bool) -> str:
    return "可用" if flag else DATA_MISSING


def _m(value) -> str:
    text = "" if value is None else str(value)
    if text in ("", DATA_MISSING) or DATA_MISSING in text:
        return f'<span class="miss">{escape(text or DATA_MISSING)}</span>'
    if text.startswith("+") or (text.endswith("%") and not text.startswith("-") and _looks_up(text)):
        return f'<span class="up">{escape(text)}</span>'
    if text.startswith("-"):
        return f'<span class="down">{escape(text)}</span>'
    return escape(text)


def _looks_up(text: str) -> bool:
    try:
        return float(text.replace("%", "").replace("+", "").replace("亿", "")) > 0
    except ValueError:
        return False


def _table(headers: list[str], rows: list[list[str]], numeric: list[int]) -> str:
    body = [(row, "") for row in rows]
    return _table_cls(headers, body, numeric)


def _table_cls(headers: list[str], rows: list[tuple[list[str], str]], numeric: list[int]) -> str:
    th = "".join(
        f'<th data-col="{i}" class="{"num" if i in numeric else ""}">{escape(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = []
    for row, cls in rows:
        tds = []
        for i, cell in enumerate(row):
            tds.append(f'<td class="{"num" if i in numeric else ""}">{_m(cell)}</td>')
        body.append(f'<tr class="{cls}">{"".join(tds)}</tr>')
    inner = "".join(body) or f'<tr><td colspan="{len(headers)}">{_m(DATA_MISSING)}</td></tr>'
    return f'<div class="scroll"><table class="data" data-sortable="1"><thead><tr>{th}</tr></thead><tbody>{inner}</tbody></table></div>'


_CSS = """
:root{--bg:#070b10;--card:#10171f;--line:#243142;--txt:#e8eef6;--muted:#8b9bb0;--red:#ff5a5f;--green:#3dd68c;--gold:#f5c542;--miss:#8a93a3;}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);font-family:ui-sans-serif,system-ui,-apple-system,"PingFang SC","Noto Sans SC",sans-serif;}
a{color:var(--gold);text-decoration:none}
.top{padding:24px 28px 8px;border-bottom:1px solid var(--line)}
.kicker{color:var(--gold);letter-spacing:.18em;font-size:12px;margin:0}
h1{margin:6px 0;font-size:28px}
.meta{color:var(--muted);margin:0}
main{padding:16px 28px 80px;max-width:1400px}
.sidenav{position:fixed;right:12px;top:90px;display:flex;flex-direction:column;gap:6px;background:rgba(16,23,31,.92);border:1px solid var(--line);padding:10px;border-radius:10px;max-height:70vh;overflow:auto;z-index:20;min-width:108px}
.sidenav a{color:var(--muted);font-size:12px}
.sidenav a:hover{color:var(--gold)}
.hero .cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.stat{background:var(--card);border:1px solid var(--line);padding:14px;border-radius:12px;min-height:96px}
.stat span{display:block;color:var(--muted);font-size:12px}
.stat strong{display:block;margin-top:8px;font-size:20px}
.stat.gold{box-shadow:inset 0 0 0 1px var(--gold)}
.stat.down strong{color:var(--green)}
.stat.up strong{color:var(--red)}
.mod{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:16px 0}
.mod-title{margin:0;padding:14px 16px;border-bottom:1px solid var(--line);cursor:pointer}
.mod-title:after{content:" 折叠";color:var(--muted);font-size:12px;font-weight:400}
.mod.collapsed .mod-body{display:none}
.mod-body{padding:12px 16px 18px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:720px}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;font-size:13px}
th{color:var(--muted);font-weight:600;cursor:pointer;white-space:nowrap}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:hover{background:#182230}
.hl-top{background:#2a210c}
.hl-strong{background:#1d2a18}
.hl-weak{background:#2a1518}
.up{color:var(--red)}
.down{color:var(--green)}
.miss{color:var(--miss);background:#1b222c;border-radius:4px;padding:1px 6px;font-size:12px}
.banner{padding:12px 14px;border:1px solid var(--miss);border-radius:10px;margin-bottom:12px;color:var(--miss)}
.note,.notes{color:var(--muted);font-size:13px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
article{background:#0c1218;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
h3,h4{color:var(--gold)}
.kv{min-width:480px}
@media (max-width:900px){
  .hero .cards{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
  .sidenav{position:static;flex-direction:row;flex-wrap:wrap;max-height:none;margin:8px}
  main{padding:12px}
  .stat strong{font-size:16px}
}
"""

_JS = """
document.querySelectorAll('.mod-title').forEach(h=>{
  h.addEventListener('click',()=>h.parentElement.classList.toggle('collapsed'));
});
document.querySelectorAll('table.data').forEach(table=>{
  table.querySelectorAll('th').forEach((th,idx)=>{
    th.addEventListener('click',()=>{
      const tbody=table.tBodies[0];
      const rows=[...tbody.rows];
      const desc=th.dataset.dir!=='desc';
      rows.sort((a,b)=>{
        const av=a.cells[idx].innerText.replace(/[+,%亿]/g,'').replace('DATA_MISSING','-Infinity');
        const bv=b.cells[idx].innerText.replace(/[+,%亿]/g,'').replace('DATA_MISSING','-Infinity');
        const an=parseFloat(av), bn=parseFloat(bv);
        if(!isNaN(an)&&!isNaN(bn)) return desc?bn-an:an-bn;
        return desc?bv.localeCompare(av):av.localeCompare(bv);
      });
      rows.forEach(r=>tbody.appendChild(r));
      th.dataset.dir=desc?'desc':'asc';
    });
  });
});
"""
