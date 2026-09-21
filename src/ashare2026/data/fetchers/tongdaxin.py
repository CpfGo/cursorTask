from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from ashare2026.config import load_settings
from ashare2026.data.http import HttpClient
from ashare2026.formatting import parse_cn_money, parse_pct_number, to_float
from ashare2026.paths import user_dir
from ashare2026.timeutil import cn_tz

TDX_UA = (
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 TdxW"
)

# HQServ JJQC row layout published with the public TdxW HQServ client:
# 代码, 名称, 昨收, 今开, 开盘金额, 抢筹幅度, 抢筹委托金额, 抢筹成交金额, 最新价, ...
# 昨收/今开 are 万分之一元。开盘金额/抢筹委托金额/抢筹成交金额 are 元。
# 抢筹委托金额 is unmatched buy during auction; for 涨停开盘 it is 封单额.
# 开盘金额 and 抢筹成交金额 are matched prints — never treat them as 封单额.

# Local 涨停报价列表 export: 代码, 名称, 二级行业, 细分行业, 封单额, 涨幅%, 现价,
# 总金额, 未匹配量, 开盘金额, 开盘换手Z, 买价, 总量, 换手%, 现量, 卖价.
# 封单额 is the displayed column (35.8亿 / 8500万). 开盘换手Z is free-float auction
# turnover, not Eastmoney hs. 二级行业 → 板块, 细分行业 → 细分行业.

EXPORT_SUFFIXES = {".txt", ".csv", ".tsv"}
DATE_IN_NAME = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")
# After YYYYMMDD / YYYY-MM-DD is stripped, clock tokens in the remainder.
CLOCK_IN_NAME = re.compile(
    r"(?:^|[^0-9])(?:t)?0?9[:\-_.]?([152][05])(?:[^0-9]|$)",
    re.IGNORECASE,
)
HEADER_ALIASES = {
    "代码": "code",
    "证券代码": "code",
    "品种代码": "code",
    "股票代码": "code",
    "名称": "name",
    "证券名称": "name",
    "品种名称": "name",
    "股票名称": "name",
    "二级行业": "board",
    "板块": "board",
    "细分行业": "industry",
    "行业": "industry",
    "封单额": "seal",
    "封单金额": "seal",
    "涨幅%": "pct",
    "涨幅％": "pct",
    "涨幅": "pct",
    "现价": "last",
    "最新价": "last",
    "总金额": "total_amount",
    "未匹配量": "unmatched",
    "开盘金额": "open_amount",
    "开盘换手z": "open_turnover",
    "开盘换手": "open_turnover",
    "买价": "bid",
    "总量": "volume",
    "换手%": "turnover",
    "换手％": "turnover",
    "现量": "last_vol",
    "卖价": "ask",
}


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
    board: str | None = None
    industry: str | None = None
    open_turnover: float | None = None


@dataclass
class TdxQuoteExport:
    clock: str
    day: str
    path: Path
    rows: list[TdxAuctionRow]
    source: str
    captured_at: datetime
    clock_from: str


def limit_up_threshold(code: str) -> float:
    if code.startswith(("300", "301", "688", "689")):
        return 19.0
    if code.startswith(("8", "4", "92")):
        return 29.0
    return 9.5


def normalize_code(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    text = text.replace(".", "").replace(":", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return digits[-6:]
    return digits or text


def parse_jjqc_datas(datas: list) -> list[TdxAuctionRow]:
    rows: list[TdxAuctionRow] = []
    if not isinstance(datas, list):
        return rows
    for item in datas:
        if not isinstance(item, (list, tuple)) or len(item) < 7:
            continue
        code = normalize_code(str(item[0] or ""))
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


def decode_tdx_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "cp936"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("gbk", errors="replace")


def _header_key(cell: str) -> str:
    text = str(cell or "").strip().lower().replace(" ", "").replace("\ufeff", "")
    text = text.replace("％", "%")
    return HEADER_ALIASES.get(text, HEADER_ALIASES.get(str(cell or "").strip(), ""))


def _is_header_row(cells: list[str]) -> bool:
    keys = {_header_key(c) for c in cells}
    return "code" in keys and ("seal" in keys or "name" in keys)


def _split_line(line: str) -> list[str]:
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    if line.count(",") >= 3:
        return next(csv.reader([line]))
    return re.split(r"\s{2,}", line.strip())


def _row_from_cells(cells: list[str], index: dict[str, int]) -> TdxAuctionRow | None:
    def cell(key: str) -> str:
        pos = index.get(key)
        if pos is None or pos >= len(cells):
            return ""
        return str(cells[pos] or "").strip()

    code = normalize_code(cell("code"))
    name = cell("name")
    if not code or not name:
        return None
    pct = parse_pct_number(cell("pct"))
    is_limit = True if pct is None else pct >= limit_up_threshold(code)
    board = cell("board") or None
    industry = cell("industry") or None
    return TdxAuctionRow(
        code=code,
        name=name,
        open_amount=parse_cn_money(cell("open_amount")),
        scramble_pct=pct,
        seal_amount=parse_cn_money(cell("seal")),
        last=to_float(cell("last")),
        is_limit_up=is_limit,
        board=board,
        industry=industry,
        open_turnover=parse_pct_number(cell("open_turnover")),
    )


def parse_tdx_quote_export(text: str) -> list[TdxAuctionRow]:
    """Parse a Tongdaxin 涨停报价列表 TXT/CSV export (GBK or UTF-8 text)."""
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    header_i = None
    header_cells: list[str] = []
    for i, line in enumerate(lines):
        if not line or line.startswith("#"):
            continue
        cells = _split_line(line)
        if _is_header_row(cells):
            header_i = i
            header_cells = cells
            break
    if header_i is None:
        return []
    index: dict[str, int] = {}
    for pos, cell in enumerate(header_cells):
        key = _header_key(cell)
        if key and key not in index:
            index[key] = pos
    if "code" not in index or "seal" not in index:
        return []
    rows: list[TdxAuctionRow] = []
    for line in lines[header_i + 1 :]:
        if not line or line.startswith("#"):
            continue
        cells = _split_line(line)
        if _is_header_row(cells):
            continue
        item = _row_from_cells(cells, index)
        if item:
            rows.append(item)
    return rows


def parse_tdx_quote_file(path: Path) -> list[TdxAuctionRow]:
    raw = path.read_bytes()
    return parse_tdx_quote_export(decode_tdx_bytes(raw))


def _clock_from_token(minute: str) -> str | None:
    if minute == "15":
        return "09:15"
    if minute == "20":
        return "09:20"
    if minute == "25":
        return "09:25"
    return None


def clock_from_filename(name: str) -> str | None:
    """Read 09:15/09:20/09:25 from a TDX export name after stripping the trade date."""
    leftover = DATE_IN_NAME.sub(" ", name)
    leftover = leftover.replace("YYYYMMDD", " ")
    hit = CLOCK_IN_NAME.search(leftover)
    if not hit:
        return None
    return _clock_from_token(hit.group(1))


def day_from_filename(name: str) -> str | None:
    hits = DATE_IN_NAME.findall(name)
    if not hits:
        return None
    year, month, day = hits[-1]
    return f"{year}{month}{day}"


def clock_from_mtime(mtime: datetime) -> str | None:
    t = mtime.timetz().replace(tzinfo=None) if mtime.tzinfo else mtime.time()
    windows = (
        ("09:15", time(9, 15), time(9, 20)),
        ("09:20", time(9, 20), time(9, 25)),
        ("09:25", time(9, 25), time(9, 30)),
    )
    for clock, start, end in windows:
        if start <= t < end:
            return clock
    return None


def infer_export_stamp(path: Path, *, now: datetime | None = None) -> tuple[str | None, str | None, str]:
    """Return (YYYYMMDD, HH:MM clock, how). Clock only if filename or auction-window mtime says so."""
    name = path.name
    day = day_from_filename(name)
    clock = clock_from_filename(name)
    origin = "filename" if clock else ""
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=(now.tzinfo if now and now.tzinfo else cn_tz()))
    if day is None:
        day = mtime.strftime("%Y%m%d")
    if clock is None:
        clock = clock_from_mtime(mtime)
        if clock:
            origin = "mtime"
    return day, clock, origin or "none"


def resolve_tdx_import_dir(raw: str | None = None) -> Path:
    settings = load_settings()
    text = raw if raw is not None else settings.auction_report.tdx_import_dir
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = user_dir() / path
    return path


def load_tdx_quote_exports(
    *,
    day: str,
    import_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, TdxQuoteExport]:
    """Load timestamped TDX 涨停报价列表 files. Never assign a later clock to an earlier one."""
    root = import_dir or resolve_tdx_import_dir()
    if not root.is_dir():
        return {}
    by_clock: dict[str, TdxQuoteExport] = {}
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in EXPORT_SUFFIXES:
            continue
        file_day, clock, origin = infer_export_stamp(path, now=now)
        if file_day != day or clock is None or origin == "none":
            continue
        try:
            rows = parse_tdx_quote_file(path)
        except OSError:
            continue
        stat = path.stat()
        captured = datetime.fromtimestamp(stat.st_mtime, tz=(now.tzinfo if now and now.tzinfo else cn_tz()))
        source = f"通达信本地涨停报价列表 {path.name}（封单额列，{clock}）"
        candidate = TdxQuoteExport(
            clock=clock,
            day=file_day,
            path=path,
            rows=rows,
            source=source,
            captured_at=captured,
            clock_from=origin,
        )
        previous = by_clock.get(clock)
        if previous is None:
            by_clock[clock] = candidate
            continue
        # Prefer an explicit filename clock over mtime; else the later file in-window.
        prev_rank = 1 if previous.clock_from == "filename" else 0
        new_rank = 1 if origin == "filename" else 0
        if new_rank > prev_rank or (new_rank == prev_rank and captured >= previous.captured_at):
            by_clock[clock] = candidate
    return by_clock


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
