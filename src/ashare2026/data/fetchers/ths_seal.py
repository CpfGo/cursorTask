from __future__ import annotations

from ashare2026.config import load_settings
from ashare2026.constants import DATA_MISSING
from ashare2026.data.fetchers.tongdaxin import limit_up_threshold, normalize_code
from ashare2026.data.http import HttpClient
from ashare2026.data.ths_html import ajax_url_candidates, looks_waf, parse_seal_amount_table
from ashare2026.formatting import parse_cn_money, to_float
from ashare2026.models.report import AuctionSealRow

THS_SEAL_SOURCE = "同花顺公开涨停接口（封单额字段）"
GNZJL_PARENT = "https://data.10jqka.com.cn/funds/gnzjl/"
RADAR_LIST = "https://yuanchuang.10jqka.com.cn/mrnxgg_list/"

# Keys that actually mean unmatched 封单额 on 同花顺 zt JSON. Do not invent aliases from 成交.
THS_SEAL_KEYS = {
    "order_amount",
    "limit_up_fund",
    "high_fund_amount",
    "fengdan_amount",
    "seal_amount",
    "buy_lock_amount",
    "fd_amount",
    "fdmoney",
    "fengdan",
    "fund",
    "封单额",
    "封单金额",
    "封单",
}
# Matched prints / session turnover — never 封单额, never 开盘换手.
THS_NOT_SEAL_KEYS = {
    "amount",
    "turnover_amount",
    "latest_amount",
    "open_amount",
    "deal_amount",
    "成交额",
    "成交金额",
    "开盘金额",
    "总金额",
    "currency_value",
    "hs",
    "turnover_rate",
    "turnover",
    "change_rate",
    "zdp",
}

JSON_URLS = (
    "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?filter=HS,GEM2STAR&order_field=first_limit_up_time&order_type=0&limit=200",
    "https://eq.10jqka.com.cn/open/api/limit_up/limit_up_pool?filter=HS,GEM2STAR&order_field=order_amount&order_type=0&limit=200",
)
HTML_URLS = (
    "https://data.10jqka.com.cn/rank/limitup/field/continue_num/order/desc/ajax/1/",
    "https://q.10jqka.com.cn/index/index/board/all/field/zdf/order/desc/page/1/ajax/1/",
)


def _norm_key(key: object) -> str:
    return str(key or "").strip().lower().replace(" ", "").replace("%", "")


def seal_amount_from_mapping(row: dict) -> float | None:
    """Return 封单额 only from a real 封单 field. Never 成交额 / amount / hs."""
    if not isinstance(row, dict):
        return None
    found: float | None = None
    for key, val in row.items():
        k = _norm_key(key)
        raw = str(key or "")
        if k in THS_NOT_SEAL_KEYS or "成交" in raw:
            continue
        if k in THS_SEAL_KEYS or "封单" in raw:
            money = parse_cn_money(val)
            if money is not None:
                found = money
                break
    return found


def parse_ths_limit_pool_payload(
    payload: dict | list | None,
    *,
    min_yuan: float,
    board_of: dict[str, str] | None = None,
    industry_of: dict[str, str] | None = None,
) -> list[AuctionSealRow]:
    board_of = board_of or {}
    industry_of = industry_of or {}
    items = _limit_items(payload)
    out: list[AuctionSealRow] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        code = normalize_code(str(row.get("code") or row.get("stock_code") or row.get("c") or ""))
        name = str(row.get("name") or row.get("stock_name") or row.get("n") or "").strip()
        if not code or not name:
            continue
        zdp = to_float(row.get("change_rate") or row.get("zdp") or row.get("change_pct"))
        if zdp is not None and abs(zdp) < 1:
            zdp = zdp * 100.0
        if zdp is not None and zdp < limit_up_threshold(code):
            continue
        seal = seal_amount_from_mapping(row)
        if seal is None or seal <= min_yuan:
            continue
        industry = str(row.get("hybk") or row.get("industry") or row.get("concept") or "").strip() or None
        out.append(
            AuctionSealRow(
                name=name,
                code=code,
                board=board_of.get(code),
                industry=industry or industry_of.get(code),
                open_turnover=None,
                seal_amount=seal,
                source=THS_SEAL_SOURCE,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


def _limit_items(payload: dict | list | None) -> list:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("info", "list", "pool", "stock_list"):
            items = data.get(key)
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
    for key in ("info", "list", "pool"):
        items = payload.get(key)
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def rows_from_seal_table(
    html: str,
    *,
    min_yuan: float,
    board_of: dict[str, str] | None = None,
    industry_of: dict[str, str] | None = None,
) -> list[AuctionSealRow]:
    board_of = board_of or {}
    industry_of = industry_of or {}
    out: list[AuctionSealRow] = []
    for item in parse_seal_amount_table(html):
        code = normalize_code(item.get("code") or "")
        name = str(item.get("name") or "").strip()
        seal = item.get("seal_amount")
        if not code or not name or seal is None or seal <= min_yuan:
            continue
        out.append(
            AuctionSealRow(
                name=name,
                code=code,
                board=board_of.get(code) or item.get("board"),
                industry=item.get("industry") or industry_of.get(code),
                open_turnover=None,
                seal_amount=seal,
                source=THS_SEAL_SOURCE,
            )
        )
    out.sort(key=lambda r: r.seal_amount or 0, reverse=True)
    return out


class TonghuashunSealFetcher:
    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch_seal_rows(self, *, min_yuan: float | None = None) -> tuple[list[AuctionSealRow], str]:
        threshold = self.settings.auction_report.seal_min_yuan if min_yuan is None else min_yuan
        self.http.get_text(GNZJL_PARENT, referer="https://data.10jqka.com.cn/")
        notes: list[str] = []
        for url in JSON_URLS:
            payload = self.http.get_json(url, referer=GNZJL_PARENT, ajax=True)
            rows = parse_ths_limit_pool_payload(payload if isinstance(payload, (dict, list)) else None, min_yuan=threshold)
            if rows:
                return rows, f"{THS_SEAL_SOURCE} {url.split('?')[0]}"
            if isinstance(payload, dict) and payload.get("status_code") in (0, "0"):
                notes.append(f"{url.split('?')[0]} 无封单额字段")
        for url in HTML_URLS:
            for cand in ajax_url_candidates(url):
                text = self.http.get_text(cand, referer=GNZJL_PARENT, ajax=True, prefer_gbk=True)
                if not text or looks_waf(text):
                    self.http.refresh_hexin(force=True)
                    text = self.http.get_text(cand, referer=GNZJL_PARENT, ajax=True, prefer_gbk=True)
                if not text or looks_waf(text):
                    continue
                rows = rows_from_seal_table(text, min_yuan=threshold)
                if rows:
                    return rows, f"{THS_SEAL_SOURCE} HTML {cand}"
        radar = self.http.get_text(RADAR_LIST, referer="https://yuanchuang.10jqka.com.cn/")
        if radar and not looks_waf(radar):
            rows = rows_from_seal_table(radar, min_yuan=threshold)
            if rows:
                return rows, f"{THS_SEAL_SOURCE} 涨停雷达 HTML"
        detail = "；".join(notes) if notes else "未解析到封单额列"
        return [], f"{DATA_MISSING}：同花顺公开接口未返回封单额（{detail}；不把成交额冒充封单）"


def fetch_ths_seal_rows(*, min_yuan: float | None = None) -> tuple[list[AuctionSealRow], str]:
    return TonghuashunSealFetcher().fetch_seal_rows(min_yuan=min_yuan)
