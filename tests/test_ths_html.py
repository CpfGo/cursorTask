from ashare2026.data.hexin import generate_hexin_v
from ashare2026.data.manager import _overlay_ths_flow
from ashare2026.data.ths_html import (
    ajax_url_candidates,
    extract_article_links,
    looks_waf,
    parse_fund_table,
    parse_limit_reasons,
)
from ashare2026.models.board import BoardQuote
from ashare2026.pipeline.step2_boards import run_step2
from tests.fixtures_data import board, stock


FUND_HTML = """
<table class="m-table J-ajax-table">
  <thead>
    <tr>
      <th>序号</th>
      <th>行业</th>
      <th>公司家数</th>
      <th>阶段涨跌幅</th>
      <th>流入资金(亿)</th>
      <th>流出资金(亿)</th>
      <th>净额(亿)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td><a href="http://q.10jqka.com.cn/gn/detail/code/300900/">融资融券</a></td>
      <td>3870</td>
      <td>4.72%</td>
      <td>5810.04</td>
      <td>5181.60</td>
      <td>628.44</td>
    </tr>
    <tr>
      <td>2</td>
      <td><a href="http://q.10jqka.com.cn/gn/detail/code/301085/">芯片概念</a></td>
      <td>930</td>
      <td>6.39%</td>
      <td>3083.18</td>
      <td>2508.59</td>
      <td>574.60</td>
    </tr>
  </tbody>
</table>
"""

RADAR_HTML = """
<html><head><title>涨停雷达：焦炭+炭黑+化工涨价 金能科技触及涨停</title></head>
<body>
<div class="news-content-parsed">
<p>今日走势：<a href="https://stockpage.10jqka.com.cn/603113">金能科技（603113）</a>今日触及涨停板。</p>
</div>
</body></html>
"""

FUPAN_HTML = """
<html><head><title>涨停复盘：半导体板块涨幅居前</title></head>
<body>
<div class="list-con">
<a href="http://yuanchuang.10jqka.com.cn/20260918/c680057188.shtml">涨停复盘：半导体板块涨幅居前</a>
<a href="http://yuanchuang.10jqka.com.cn/20260819/c679081496.shtml">涨停雷达：焦炭+炭黑+化工涨价 金能科技触及涨停</a>
</div>
<div class="news-content-parsed">
<p><a href="https://q.10jqka.com.cn/thshy/detail/code/885598">新股与次新股（885598）</a>
板块持续上扬，<a href="https://stockpage.10jqka.com.cn/301689">电科思仪（301689）</a>涨停。
<a href="https://q.10jqka.com.cn/thshy/detail/code/881121">半导体（881121）</a>
板块表现强势，<a href="https://stockpage.10jqka.com.cn/002185">华天科技（002185）</a>等股涨停，
<a href="https://stockpage.10jqka.com.cn/688261">东微半导（688261）</a>涨幅居前。</p>
<p><a href="https://stockpage.10jqka.com.cn/1A0001">上证指数（1A0001）</a>涨0.94%</p>
</div>
</body></html>
"""

WAF_HTML = "<html><script>window.location.href='/'; chameleon 401</script></html>"


def test_ajax_url_candidates_include_free():
    url = "https://data.10jqka.com.cn/funds/gnzjl/board/3/field/buy/order/desc/ajax/1/"
    cands = ajax_url_candidates(url)
    assert url in cands or url.rstrip("/") + "/" in cands
    assert any(item.endswith("free/1/") for item in cands)


def test_parse_fund_table_3d_yi():
    rows = parse_fund_table(FUND_HTML, kind="concept", horizon="3d")
    assert len(rows) == 2
    assert rows[0].name == "融资融券"
    assert rows[0].code == "300900"
    assert rows[0].net_inflow_3d == 628.44 * 1e8
    assert rows[0].net_inflow is None
    assert rows[1].net_inflow_3d == 574.60 * 1e8


def test_looks_waf_ignores_success_table():
    assert looks_waf(WAF_HTML) is True
    assert looks_waf(FUND_HTML) is False


def test_parse_radar_title_reason():
    rows = parse_limit_reasons(RADAR_HTML)
    assert len(rows) == 1
    assert rows[0].code == "603113"
    assert rows[0].name == "金能科技"
    assert rows[0].reason == "焦炭+炭黑+化工涨价"


def test_parse_fupan_only_limit_up_near_board():
    rows = {x.code: x for x in parse_limit_reasons(FUPAN_HTML)}
    assert rows["002185"].reason == "半导体"
    assert rows["301689"].reason == "新股与次新股"
    assert "688261" not in rows
    assert "1A0001" not in rows


def test_extract_article_links():
    links = extract_article_links(FUPAN_HTML)
    titles = [t for t, _ in links]
    assert any(t.startswith("涨停雷达") for t in titles)
    assert any(t.startswith("涨停复盘") for t in titles)


def test_step2_ranks_3d_without_inventing_missing():
    members = [stock("300308", "中际旭创", 8.2, 1e10, 1e9, concepts=["CPO"])]
    concepts = [
        board("1", "CPO概念", "concept", 4.8, 4e10, 8e9, members, flow3=3e9, flow5=1e10),
        board("2", "银行", "concept", -1.8, 9e9, -3e9, [], flow3=None, flow5=-6e9),
    ]
    _, _, _, continuity = run_step2([], concepts, True, True)
    cpo = next(r for r in continuity if r.name == "CPO概念")
    bank = next(r for r in continuity if r.name == "银行")
    assert cpo.rank_3d == 1
    assert bank.rank_3d is None
    assert cpo.rating in {"强连续", "趋势资金", "短线攻击", "一日游"}


def test_hexin_v_from_vendored_ths_js():
    value = generate_hexin_v()
    assert value
    assert len(value) > 10


def test_overlay_keeps_amount_adds_3d():
    em = [
        BoardQuote(code="1", name="芯片概念", kind="concept", amount=1e10, net_inflow=1e8, source="eastmoney")
    ]
    ths = [
        BoardQuote(code="301085", name="芯片概念", kind="concept", net_inflow_3d=5e9, source="tonghuashun")
    ]
    out = _overlay_ths_flow(em, ths)
    assert out[0].amount == 1e10
    assert out[0].net_inflow_3d == 5e9
    assert out[0].net_inflow == 1e8

