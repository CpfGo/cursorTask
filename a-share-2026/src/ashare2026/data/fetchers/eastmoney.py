from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ashare2026.config import load_settings
from ashare2026.data.fetchers.base import FetcherResult
from ashare2026.data.http import HttpClient
from ashare2026.formatting import to_float, to_int
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import EtfQuote, IndexQuote, LimitStock, MarketSnapshot, StockQuote
from ashare2026.timeutil import now_cn


EM_DELAY = "https://push2delay.eastmoney.com"
EM_ZT = "https://push2ex.eastmoney.com/getTopicZTPool"
EM_DT = "https://push2ex.eastmoney.com/getTopicDTPool"
UT = "7eea3edcaed734bea9cbfc24409ed989"

INDEX_SECIDS = {
    "000001": ("1.000001", "上证指数"),
    "399001": ("0.399001", "深证成指"),
    "399006": ("0.399006", "创业板指"),
    "000300": ("1.000300", "沪深300"),
    "000852": ("1.000852", "中证1000"),
}


class EastmoneyFetcher:
    def __init__(self) -> None:
        self.http = HttpClient()
        self.settings = load_settings()

    def fetch(self) -> FetcherResult:
        notes: list[str] = ["东方财富作为同花顺不可用时的备用行情源"]
        snapshot = MarketSnapshot()
        snapshot.indices = self._indices()
        industries = self._boards("industry")
        concepts = self._boards("concept")
        snapshot.stocks = self._top_stocks()
        snapshot.etfs = self._etfs()
        date = self._trade_date()
        snapshot.limit_up = self._limit_pool(EM_ZT, date, down=False)
        snapshot.limit_down = self._limit_pool(EM_DT, date, down=True)
        self._attach_constituents(industries, concepts)
        self._summarize(snapshot)
        flow_5d_ok = any(b.net_inflow_5d is not None for b in concepts)
        if not snapshot.indices:
            notes.append("东方财富指数接口失败")
        return FetcherResult(
            snapshot=snapshot,
            industries=industries,
            concepts=concepts,
            notes=notes,
            flow_3d_ok=False,
            flow_5d_ok=flow_5d_ok,
        )

    def _get(self, url: str, params: dict | None = None) -> dict | None:
        data = self.http.get_json(url, params=params, referer="https://quote.eastmoney.com/")
        return data if isinstance(data, dict) else None

    def _clist(self, fs: str, fields: str, fid: str, pz: int = 100, pn: int = 1) -> list[dict]:
        url = f"{EM_DELAY}/api/qt/clist/get"
        params = {
            "pn": pn,
            "pz": pz,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": fid,
            "fs": fs,
            "fields": fields,
        }
        data = self._get(url, params)
        if not data or not data.get("data"):
            return []
        diff = data["data"].get("diff") or []
        return [x for x in diff if isinstance(x, dict)]

    def _indices(self) -> dict[str, IndexQuote]:
        secids = ",".join(v[0] for v in INDEX_SECIDS.values())
        url = f"{EM_DELAY}/api/qt/ulist.np/get"
        params = {
            "fltt": 2,
            "secids": secids,
            "fields": "f2,f3,f4,f6,f12,f14,f17,f18,f104,f105,f106",
        }
        data = self._get(url, params)
        out: dict[str, IndexQuote] = {}
        rows = ((data or {}).get("data") or {}).get("diff") or []
        for row in rows:
            code = str(row.get("f12") or "")
            meta = INDEX_SECIDS.get(code)
            name = (meta[1] if meta else row.get("f14")) or code
            price = to_float(row.get("f2"))
            prev = to_float(row.get("f18"))
            open_px = to_float(row.get("f17"))
            open_pct = None
            if open_px is not None and prev:
                open_pct = (open_px / prev - 1) * 100
            out[code] = IndexQuote(
                code=code,
                name=name,
                price=price,
                change_pct=to_float(row.get("f3")),
                open_pct=open_pct,
                amount=to_float(row.get("f6")),
                up_count=to_int(row.get("f104")),
                down_count=to_int(row.get("f105")),
                flat_count=to_int(row.get("f106")),
                source="eastmoney",
            )
        return out

    def _boards(self, kind: str) -> list[BoardQuote]:
        fs = "m:90+t:2+f:!50" if kind == "industry" else "m:90+t:3+f:!50"
        fields = "f12,f14,f2,f3,f6,f62,f66,f72,f104,f105,f128,f136,f140,f164,f174,f184"
        rows = self._clist(fs, fields, fid="f6", pz=100)
        boards: list[BoardQuote] = []
        for row in rows:
            name = str(row.get("f14") or "")
            if not name:
                continue
            inflow = to_float(row.get("f62"))
            main_buy = to_float(row.get("f66"))
            main_sell = None
            if inflow is not None and main_buy is not None:
                main_sell = main_buy - inflow
            boards.append(
                BoardQuote(
                    code=str(row.get("f12") or ""),
                    name=name,
                    kind=kind,
                    change_pct=to_float(row.get("f3")),
                    amount=to_float(row.get("f6")),
                    up_count=to_int(row.get("f104")),
                    down_count=to_int(row.get("f105")),
                    leader_name=_clean_leader(row.get("f140") or row.get("f128")),
                    leader_code=_code_only(row.get("f128")),
                    leader_change_pct=to_float(row.get("f136")),
                    net_inflow=inflow,
                    net_inflow_5d=to_float(row.get("f164")),
                    net_inflow_10d=to_float(row.get("f174")),
                    main_buy=main_buy,
                    main_sell=main_sell,
                    source="eastmoney",
                )
            )
        boards.sort(key=lambda b: (b.amount or 0), reverse=True)
        return boards

    def _top_stocks(self) -> list[StockQuote]:
        fields = "f12,f14,f2,f3,f6,f8,f15,f17,f18,f20,f62"
        n = self.settings.pipeline.stock_amount_top_n
        rows = self._clist(
            "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81",
            fields,
            fid="f6",
            pz=min(n, 200),
        )
        stocks = [self._stock_from_row(row) for row in rows]
        extra = self._clist(
            "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            fields,
            fid="f3",
            pz=80,
        )
        seen = {s.code for s in stocks}
        for row in extra:
            stock = self._stock_from_row(row)
            if stock.code not in seen:
                stocks.append(stock)
                seen.add(stock.code)
        return [s for s in stocks if s.code]

    def _stock_from_row(self, row: dict) -> StockQuote:
        code = str(row.get("f12") or "")
        prev = to_float(row.get("f18"))
        open_px = to_float(row.get("f17"))
        open_pct = None
        if open_px is not None and prev:
            open_pct = (open_px / prev - 1) * 100
        change = to_float(row.get("f3"))
        return StockQuote(
            code=code,
            name=str(row.get("f14") or ""),
            price=to_float(row.get("f2")),
            change_pct=change,
            open_pct=open_pct,
            amount=to_float(row.get("f6")),
            turnover=to_float(row.get("f8")),
            net_inflow=to_float(row.get("f62")),
            market_cap=to_float(row.get("f20")),
            high=to_float(row.get("f15")),
            open=open_px,
            prev_close=prev,
            is_20cm=_is_20cm(code),
            is_limit_up=_is_limit_up(code, change),
            is_limit_down=_is_limit_down(code, change),
            source="eastmoney",
        )

    def _etfs(self) -> list[EtfQuote]:
        fields = "f12,f14,f2,f3,f6,f62,f164,f174"
        rows = self._clist("b:MK0021,b:MK0022,b:MK0023,b:MK0024", fields, fid="f6", pz=80)
        etfs: list[EtfQuote] = []
        for row in rows:
            etfs.append(
                EtfQuote(
                    code=str(row.get("f12") or ""),
                    name=str(row.get("f14") or ""),
                    change_pct=to_float(row.get("f3")),
                    amount=to_float(row.get("f6")),
                    net_inflow_5d=to_float(row.get("f164")),
                    net_inflow_10d=to_float(row.get("f174")),
                    source="eastmoney",
                )
            )
        return etfs

    def _trade_date(self) -> str:
        moment = now_cn()
        if moment.weekday() >= 5:
            shift = moment.weekday() - 4
            moment = moment - timedelta(days=shift)
        return moment.strftime("%Y%m%d")

    def _limit_pool(self, url: str, date: str, down: bool) -> list[LimitStock]:
        params = {
            "ut": UT,
            "dpt": "wz.ztzt",
            "Pageindex": 0,
            "pagesize": 200,
            "sort": "fbt:asc",
            "date": date,
        }
        data = self._get(url, params)
        pool = ((data or {}).get("data") or {}).get("pool") or []
        out: list[LimitStock] = []
        for row in pool:
            code = str(row.get("c") or "")
            zdp = to_float(row.get("zdp"))
            fbt = row.get("fbt")
            one_word = str(fbt) in {"92500", "925", "9:25"} or fbt == 92500
            lbc = to_int(row.get("lbc")) or 0
            out.append(
                LimitStock(
                    code=code,
                    name=str(row.get("n") or ""),
                    change_pct=zdp,
                    amount=to_float(row.get("amount")),
                    consecutive_boards=lbc,
                    first_board_time=str(fbt) if fbt is not None else None,
                    industry=str(row.get("hybk") or "") or None,
                    reason=None,
                    fund=to_float(row.get("fund")),
                    is_one_word=one_word,
                    is_20cm=_is_20cm(code) or (zdp is not None and zdp >= 15),
                )
            )
        return out

    def _attach_constituents(self, industries: list[BoardQuote], concepts: list[BoardQuote]) -> None:
        limit = self.settings.pipeline.constituent_limit
        n_boards = self.settings.pipeline.constituent_boards
        picked: list[BoardQuote] = []
        picked.extend(sorted(concepts, key=lambda b: (b.amount or 0), reverse=True)[: n_boards // 2 + 4])
        picked.extend(sorted(industries, key=lambda b: (b.amount or 0), reverse=True)[: max(6, n_boards // 3)])
        seen_codes: set[str] = set()
        for board in picked:
            if not board.code or board.code in seen_codes:
                continue
            seen_codes.add(board.code)
            fields = "f12,f14,f2,f3,f6,f8,f17,f18,f20,f62"
            rows = self._clist(f"b:{board.code}+f:!50", fields, fid="f6", pz=limit)
            stocks = [self._stock_from_row(row) for row in rows]
            for stock in stocks:
                stock.industry = board.name if board.kind == "industry" else stock.industry
                if board.kind == "concept":
                    stock.concepts = list({*stock.concepts, board.name})
            board.constituents = stocks

    def _summarize(self, snapshot: MarketSnapshot) -> None:
        sh = snapshot.indices.get("000001")
        sz = snapshot.indices.get("399001")
        amounts = [i.amount for i in (sh, sz) if i and i.amount]
        snapshot.total_amount = sum(amounts) if amounts else None
        ups = [i.up_count for i in (sh, sz) if i and i.up_count is not None]
        downs = [i.down_count for i in (sh, sz) if i and i.down_count is not None]
        snapshot.up_count = sum(ups) if ups else None
        snapshot.down_count = sum(downs) if downs else None
        snapshot.limit_up_count = len(snapshot.limit_up) if snapshot.limit_up else None
        snapshot.limit_down_count = len(snapshot.limit_down) if snapshot.limit_down else 0
        snapshot.consecutive_count = sum(1 for x in snapshot.limit_up if x.consecutive_boards >= 2)
        snapshot.cm20_count = sum(1 for x in snapshot.limit_up if x.is_20cm)
        limit_map = {x.code: x for x in snapshot.limit_up}
        for stock in snapshot.stocks:
            hit = limit_map.get(stock.code)
            if hit:
                stock.is_limit_up = True
                stock.consecutive_boards = hit.consecutive_boards
                stock.is_one_word = hit.is_one_word
                stock.is_20cm = hit.is_20cm or stock.is_20cm
                stock.industry = stock.industry or hit.industry
                stock.limit_reason = hit.reason


def _is_20cm(code: str) -> bool:
    return code.startswith(("300", "301", "688", "689"))


def _limit_threshold(code: str) -> float:
    if code.startswith(("300", "301", "688", "689")):
        return 19.0
    if code.startswith(("8", "4", "92")):
        return 29.0
    return 9.5


def _is_limit_up(code: str, change: float | None) -> bool:
    return change is not None and change >= _limit_threshold(code)


def _is_limit_down(code: str, change: float | None) -> bool:
    return change is not None and change <= -_limit_threshold(code)


def _clean_leader(value) -> str | None:
    if value in (None, "", "-", 0, "0"):
        return None
    text = str(value)
    return text if not text.isdigit() else None


def _code_only(value) -> str | None:
    text = str(value or "")
    m = re.search(r"(\d{6})", text)
    return m.group(1) if m else None
