from __future__ import annotations

from dataclasses import dataclass

from ashare2026.config import load_settings
from ashare2026.data.http import HttpClient
from ashare2026.formatting import to_float

TDX_UA = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 TdxW"
)

# HQServ JJQC row layout published with the public TdxW HQServ client:
# 代码, 名称, 昨收, 今开, 开盘金额, 抢筹幅度, 抢筹委托金额, 抢筹成交金额, 最新价, ...
# 昨收/今开 are 万分之一元。开盘金额/抢筹委托金额/抢筹成交金额 are 元。
# 抢筹委托金额 is unmatched buy during auction; for 涨停开盘 it is 封单额.
# 开盘金额 and 抢筹成交金额 are matched prints — never treat them as 封单额.


@dataclass
class TdxAuctionRow:
    code: str
    name: str
    prev_close: float | None = None
    open: float | None = None
    open_amount: float | None = None
    scramble_pct: float | None = None
    seal_amount: float | None = None
    scramble_trade_amount: float | None = None
    last: float | None = None
    is_limit_up: bool = False


def limit_up_threshold(code: str) -> float:
    if code.startswith(("300", "301", "688", "689")):
        return 19.0
    if code.startswith(("8", "4", "92")):
        return 29.0
    return 9.5


def parse_jjqc_datas(datas: list) -> list[TdxAuctionRow]:
    rows: list[TdxAuctionRow] = []
    if not isinstance(datas, list):
        return rows
    for item in datas:
        if not isinstance(item, (list, tuple)) or len(item) < 7:
            continue
        code = str(item[0] or "").strip()
        name = str(item[1] or "").strip()
        if not code or not name:
            continue
        prev_raw = to_float(item[2])
        open_raw = to_float(item[3])
        prev_close = None if prev_raw is None else prev_raw / 10000.0
        open_px = None if open_raw is None else open_raw / 10000.0
        scramble_ratio = to_float(item[5])
        scramble_pct = None if scramble_ratio is None else scramble_ratio * 100.0
        if scramble_pct is None and prev_close and open_px:
            scramble_pct = (open_px / prev_close - 1.0) * 100.0
        is_limit = scramble_pct is not None and scramble_pct >= limit_up_threshold(code)
        rows.append(
            TdxAuctionRow(
                code=code,
                name=name,
                prev_close=prev_close,
                open=open_px,
                open_amount=to_float(item[4]),
                scramble_pct=scramble_pct,
                seal_amount=to_float(item[6]),
                scramble_trade_amount=to_float(item[7]) if len(item) > 7 else None,
                last=None if len(item) < 9 else (None if to_float(item[8]) is None else to_float(item[8])),
                is_limit_up=is_limit,
            )
        )
    return rows


class TongdaxinFetcher:
    """Public Tongdaxin HQServ (excalc.icfqs.com) — 竞价抢筹 JJQC."""

    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch_jjqc(self, *, period: int = 0, count: int = 200) -> tuple[list[TdxAuctionRow], str]:
        cfg = self.settings.auction_report
        payload = [
            {
                "funcId": 20,
                "offset": 0,
                "count": count,
                "sort": 1,
                "period": period,
                "Token": cfg.tdx_hqserv_token,
                "modname": "JJQC",
            }
        ]
        data = self.http.post_json(
            cfg.tdx_hqserv_url,
            json_body=payload,
            headers={"User-Agent": TDX_UA},
            referer="http://excalc.icfqs.com:7616/",
        )
        if not isinstance(data, dict):
            return [], "DATA_MISSING：通达信 HQServ JJQC 无响应"
        datas = data.get("datas")
        rows = parse_jjqc_datas(datas if isinstance(datas, list) else [])
        if not rows:
            return [], "DATA_MISSING：通达信 HQServ JJQC 未返回可解析行"
        return rows, "通达信 HQServ JJQC"


def fetch_jjqc() -> tuple[list[TdxAuctionRow], str]:
    return TongdaxinFetcher().fetch_jjqc()
