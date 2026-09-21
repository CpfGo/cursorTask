from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.data.fetchers.eastmoney import EM_ZT, UT
from ashare2026.data.fetchers.tongdaxin import limit_up_threshold, normalize_code
from ashare2026.data.http import HttpClient
from ashare2026.formatting import to_float
from ashare2026.models.market import LimitStock
from ashare2026.models.report import AuctionSealRow

EM_SEAL_SOURCE = "东方财富 getTopicZTPool fund（涨停封单额）"
# Never treat these as 封单额. `hs` is session turnover, not 开盘换手.


def parse_zt_pool_seal(
    payload: dict | None,
    *,
    min_yuan: float,
    board_of: dict[str, str] | None = None,
    industry_of: dict[str, str] | None = None,
) -> list[AuctionSealRow]:
    """Parse Eastmoney 涨停池. 封单额 = `fund` only. Never `amount`. Never `hs` as 开盘换手."""
    board_of = board_of or {}
    industry_of = industry_of or {}
    pool = ((payload or {}).get("data") or {}).get("pool") or []
    out: list[AuctionSealRow] = []
    for row in pool:
        if not isinstance(row, dict):
            continue
        code = normalize_code(str(row.get("c") or row.get("code") or ""))
        name = str(row.get("n") or row.get("name") or "").strip()
        if not code or not name:
            continue
        # Pool membership is 涨停; still skip obvious non-limit rows.
        zdp = to_float(row.get("zdp"))
        if zdp is not None and zdp < limit_up_threshold(code):
            continue
        fund = to_float(row.get("fund"))
        if fund is None or fund <= min_yuan:
            continue
        hybk = str(row.get("hybk") or "").strip() or None
        out.append(
            AuctionSealRow(
                name=name,
                code=code,
                board=board_of.get(code),
                industry=hybk or industry_of.get(code),
                open_turnover=None,
                seal_amount=fund,
                source=EM_SEAL_SOURCE,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


def rows_from_limit_fund(
    limit_up: list[LimitStock],
    *,
    min_yuan: float,
    board_of: dict[str, str] | None = None,
    industry_of: dict[str, str] | None = None,
) -> list[AuctionSealRow]:
    """Use LimitStock.fund (EM zt 封单额). Never LimitStock.amount (成交额)."""
    board_of = board_of or {}
    industry_of = industry_of or {}
    out: list[AuctionSealRow] = []
    for item in limit_up:
        if item.fund is None or item.fund <= min_yuan:
            continue
        out.append(
            AuctionSealRow(
                name=item.name,
                code=item.code,
                board=board_of.get(item.code),
                industry=item.industry or industry_of.get(item.code),
                open_turnover=None,
                seal_amount=item.fund,
                source=EM_SEAL_SOURCE,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


class EastmoneySealFetcher:
    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch_zt_seal(self, trade_date: str, *, min_yuan: float | None = None) -> tuple[list[AuctionSealRow], str]:
        threshold = self.settings.auction_report.seal_min_yuan if min_yuan is None else min_yuan
        params = {
            "ut": UT,
            "dpt": "wz.ztzt",
            "Pageindex": 0,
            "pagesize": 200,
            "sort": "fund:desc",
            "date": trade_date,
        }
        data = self.http.get_json(EM_ZT, params=params, referer="https://quote.eastmoney.com/")
        if not isinstance(data, dict):
            return [], "DATA_MISSING：东方财富 getTopicZTPool 无响应"
        pool = ((data.get("data") or {}) if isinstance(data.get("data"), dict) else {}).get("pool")
        if not isinstance(pool, list):
            return [], "DATA_MISSING：东方财富 getTopicZTPool 未返回 pool"
        rows = parse_zt_pool_seal(data, min_yuan=threshold)
        return rows, EM_SEAL_SOURCE


def fetch_em_zt_seal(trade_date: str, *, min_yuan: float | None = None) -> tuple[list[AuctionSealRow], str]:
    return EastmoneySealFetcher().fetch_zt_seal(trade_date, min_yuan=min_yuan)
