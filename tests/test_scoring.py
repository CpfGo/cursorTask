from ashare2026.scoring.auction import auction_rating
from ashare2026.scoring.mainline import mainline_level, score_mainline
from ashare2026.scoring.money_effect import money_effect_score
from ashare2026.models.market import StockQuote
from ashare2026.formatting import clamp, minmax_score, rank_score


def test_auction_rating_buckets():
    assert auction_rating(90) == "竞价核心攻击方向"
    assert auction_rating(80) == "强竞价方向"
    assert auction_rating(70) == "可观察方向"
    assert auction_rating(55) == "普通轮动"
    assert auction_rating(10) == "弱方向"


def test_mainline_level_buckets():
    assert mainline_level(91) == "核心主线"
    assert mainline_level(85) == "强主线"
    assert mainline_level(72) == "副主线"
    assert mainline_level(61) == "轮动方向"
    assert mainline_level(10) == "非主流"


def test_mainline_weights_sum_to_100():
    item = score_mainline(
        "CPO/光模块",
        turnover_score=100,
        flow_score=100,
        continuity_score=100,
        leader_score=100,
        echelon_score=100,
        etf_score=100,
        money_score=100,
    )
    assert item.total == 100
    assert item.level == "核心主线"


def test_rank_and_minmax():
    assert rank_score(1, 5) == 100
    assert rank_score(5, 5) == 0
    assert minmax_score(10, [0, 5, 10]) == 100
    assert clamp(120) == 100


def test_money_effect_range():
    stocks = [
        StockQuote(code="1", name="A", is_limit_up=True, is_20cm=True, consecutive_boards=2, change_pct=20),
        StockQuote(code="2", name="B", change_pct=11),
        StockQuote(code="3", name="C", change_pct=-8, is_limit_down=True),
    ]
    stats, score = money_effect_score(stocks)
    assert stats["limit_up"] == 1
    assert 0 <= score <= 5
