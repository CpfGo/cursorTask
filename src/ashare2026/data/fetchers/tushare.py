from __future__ import annotations

import os
from dataclasses import dataclass

from ashare2026.config import load_settings
from ashare2026.data.http import HttpClient
from ashare2026.formatting import to_float

TUSHARE_FIELDS = "ts_code,trade_date,vol,price,amount,pre_close,turnover_rate,volume_ratio,float_share"
TOKEN_ENV = "TUSHARE_TOKEN"


@dataclass
class TushareAuctionPrint:
    ts_code: str
    code: str
    trade_date: str = ""
    vol: float | None = None
    price: float | None = None
    amount: float | None = None
    pre_close: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    float_share: float | None = None


def token_from_env() -> str:
    return (os.environ.get(TOKEN_ENV) or "").strip()


def parse_stk_auction_payload(payload: dict) -> list[TushareAuctionPrint]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    fields = data.get("fields") or []
    items = data.get("items") or []
    if not isinstance(fields, list) or not isinstance(items, list):
        return []
    index = {str(name): i for i, name in enumerate(fields)}
    out: list[TushareAuctionPrint] = []
    for row in items:
        if not isinstance(row, (list, tuple)):
            continue
        ts_code = str(_cell(row, index, "ts_code") or "").strip()
        if not ts_code:
            continue
        code = ts_code.split(".")[0]
        out.append(
            TushareAuctionPrint(
                ts_code=ts_code,
                code=code,
                trade_date=str(_cell(row, index, "trade_date") or ""),
                vol=to_float(_cell(row, index, "vol")),
                price=to_float(_cell(row, index, "price")),
                amount=to_float(_cell(row, index, "amount")),
                pre_close=to_float(_cell(row, index, "pre_close")),
                turnover_rate=to_float(_cell(row, index, "turnover_rate")),
                volume_ratio=to_float(_cell(row, index, "volume_ratio")),
                float_share=to_float(_cell(row, index, "float_share")),
            )
        )
    return out


def _cell(row: list | tuple, index: dict[str, int], name: str):
    pos = index.get(name)
    if pos is None or pos >= len(row):
        return None
    return row[pos]


class TushareFetcher:
    """pro.stk_auction — matched auction print, available 09:26–09:29. Not 封单额."""

    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch_stk_auction(self, trade_date: str) -> tuple[list[TushareAuctionPrint], str]:
        token = token_from_env()
        if not token:
            return [], "DATA_MISSING：未设置环境变量 TUSHARE_TOKEN，无法取 stk_auction 开盘换手"
        body = {
            "api_name": "stk_auction",
            "token": token,
            "params": {"trade_date": trade_date},
            "fields": TUSHARE_FIELDS,
        }
        payload = self.http.post_json(self.settings.auction_report.tushare_api, json_body=body)
        if not isinstance(payload, dict):
            return [], "DATA_MISSING：Tushare stk_auction 无响应"
        code = payload.get("code")
        if code not in (None, 0, "0"):
            msg = payload.get("msg") or payload.get("detail") or str(code)
            return [], f"DATA_MISSING：Tushare stk_auction 不可用（{msg}）"
        rows = parse_stk_auction_payload(payload)
        if not rows:
            return [], "DATA_MISSING：Tushare stk_auction 当日无行（接口 9:26–9:29 才有当日数据）"
        return rows, "Tushare stk_auction"


def fetch_stk_auction(trade_date: str) -> tuple[list[TushareAuctionPrint], str]:
    return TushareFetcher().fetch_stk_auction(trade_date)
