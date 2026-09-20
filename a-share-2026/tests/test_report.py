from ashare2026.pipeline.engine import run_pipeline
from ashare2026.report.html import render_html
from tests.fixtures_data import make_bundle

REQUIRED = [
    "A股主线识别日报",
    "数据源与可用性",
    "集合竞价强弱",
    "市场状态总览",
    "今日资金路线图",
    "行业/概念成交额排名",
    "概念即时资金流排名",
    "概念3日/5日资金连续性",
    "产业链卡点判断",
    "龙头梯队",
    "赚钱效应",
    "ETF资金分析",
    "产业周期与资金运作阶段",
    "主线评分",
    "最弱方向",
    "仓位判断",
    "反证条件",
    "一句话结论",
    "集合竞价最强板块",
    "市场第一主线",
    "DATA_MISSING",
]


def test_html_is_complete_document():
    html = render_html(run_pipeline(make_bundle()))
    assert html.startswith("<!DOCTYPE html>")
    assert html.strip().endswith("</html>")
    for token in REQUIRED:
        assert token in html
    assert "https://cdn" not in html.lower()
    assert "mod-title" in html
    assert "data-sortable" in html
    assert "sidenav" in html
    assert "hl-top" in html
