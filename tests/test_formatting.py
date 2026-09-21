from ashare2026.constants import DATA_MISSING
from ashare2026.formatting import money_cn


def test_money_cn_yi_and_wan():
    assert money_cn(1.23e8) == "1.23亿"
    assert money_cn(1e8) == "1.00亿"
    assert money_cn(8.5e7) == "8500万"
    assert money_cn(12_345) == "1.23万"
    assert money_cn(None) == DATA_MISSING
