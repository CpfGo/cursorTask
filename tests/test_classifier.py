from ashare2026.classify.classifier import classify_chains, classify_text
from tests.fixtures_data import make_bundle


def test_keyword_classification():
    assert classify_text("CPO概念") == "CPO/光模块"
    assert classify_text("人形机器人") == "机器人"
    assert classify_text("银行") == "银行"
    assert classify_text("没有标签") == "其他"


def test_one_stock_one_chain():
    bundle = make_bundle()
    chains = classify_chains(bundle.snapshot, bundle.industries, bundle.concepts, bundle.snapshot.total_amount)
    seen = {}
    for chain in chains:
        for stock in chain.stocks:
            assert stock.code not in seen
            seen[stock.code] = chain.name
    names = {c.name for c in chains}
    assert "CPO/光模块" in names
    assert "机器人" in names
    assert "银行" in names
