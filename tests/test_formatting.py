from ashare2026.constants import DATA_MISSING
from ashare2026.formatting import money_cn, parse_cn_money


def test_money_cn_yi_and_wan():
    assert money_cn(1.23e8) == "1.23亿"
    assert money_cn(1e8) == "1.00亿"
    assert money_cn(8.5e7) == "8500万"
    assert money_cn(12_345) == "1.23万"
    assert money_cn(None) == DATA_MISSING
    assert money_cn(3.58e9) == "35.80亿"


def test_parse_cn_money_tdx_cells():
    assert parse_cn_money("35.8亿") == 3.58e9
    assert parse_cn_money("8500万") == 8.5e7
    assert parse_cn_money("3,582,823,461") == 3582823461
    assert parse_cn_money("-") is None
    assert parse_cn_money("") is None
