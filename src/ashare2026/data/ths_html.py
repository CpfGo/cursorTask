from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ashare2026.formatting import to_float, to_int
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import LimitStock


YI = 1e8
STOCKPAGE_RE = re.compile(r"stockpage\.10jqka\.com\.cn/(\d{6})(?:/|$|\?|#)", re.I)
RADAR_TITLE_RE = re.compile(r"涨停雷达[：:](.+?)\s+(\S{2,20})触及涨停")


def looks_waf(text: str) -> bool:
    if "Nginx forbidden" in text:
        return True
    head = text[:800].lower()
    has_table = "<table" in text.lower() and "<tbody" in text.lower()
    if has_table:
        return False
    return "chameleon" in head and ("window.location.href" in head or "401" in head or "403" in head)


def ajax_url_candidates(url: str) -> list[str]:
    text = (url or "").strip()
    if not text:
        return []
    if not text.endswith("/"):
        text += "/"
    out: list[str] = []

    def add(item: str) -> None:
        if item not in out:
            out.append(item)

    add(text)
    if "/free/1/" not in text:
        add(text + "free/1/")
    if "/ajax/1/" in text and "/page/" not in text:
        add(text.replace("/ajax/1/", "/page/1/ajax/1/"))
        if "/free/1/" not in text:
            add(text.replace("/ajax/1/", "/page/1/ajax/1/free/1/"))
    return out


def parse_fund_table(html: str, *, kind: str = "concept", horizon: str = "instant") -> list[BoardQuote]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.m-table") or soup.find("table")
    if table is None:
        return []
    headers = [_norm_header(th.get_text(" ", strip=True)) for th in table.select("thead th")]
    body = table.find("tbody")
    if body is None:
        return []
    out: list[BoardQuote] = []
    for tr in body.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        values = [td.get_text(" ", strip=True) for td in tds]
        link = tr.find("a")
        name = (link.get_text(strip=True) if link else "") or _col(headers, values, "行业", "概念", "名称")
        if not name or name in {"--", "-"}:
            continue
        code = ""
        href = (link.get("href") if link else "") or ""
        m = re.search(r"/code/(\d+)/", href)
        if m:
            code = m.group(1)
        change = to_float(_col(headers, values, "阶段涨跌幅", "行业-涨跌幅", "涨跌幅"))
        buy = _yi(_col(headers, values, "流入资金", "流入资金(亿)", "流入资金(元)"))
        sell = _yi(_col(headers, values, "流出资金", "流出资金(亿)", "流出资金(元)"))
        net = _yi(_col(headers, values, "净额", "净额(亿)", "净额(元)", "资金流入净额"))
        leader = _col(headers, values, "领涨股")
        leader_pct = to_float(_col(headers, values, "领涨股-涨跌幅"))
        board = BoardQuote(
            code=code,
            name=name,
            kind=kind,
            change_pct=change,
            amount=None,
            up_count=to_int(_col(headers, values, "公司家数")),
            leader_name=leader or None,
            leader_change_pct=leader_pct,
            main_buy=buy,
            main_sell=sell,
            source="tonghuashun",
        )
        if horizon == "3d":
            board.net_inflow_3d = net
        elif horizon == "5d":
            board.net_inflow_5d = net
        else:
            board.net_inflow = net
        out.append(board)
    return out


def extract_article_links(html: str, page_url: str = "") -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.select("a[href]"):
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if not title.startswith(("涨停雷达", "涨停复盘")):
            continue
        href = urljoin(page_url, a.get("href") or "")
        if ".shtml" not in href and ".html" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        found.append((title, href))
    return found


def parse_limit_reasons(html: str, page_url: str = "") -> list[LimitStock]:
    """Extract stock + 涨停原因 text that actually appears on 涨停雷达 HTML."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    title_reason, title_name = _parse_radar_title(title)
    found: dict[str, LimitStock] = {}
    for a in soup.select("a[href]"):
        href = urljoin(page_url, a.get("href") or "")
        m = STOCKPAGE_RE.search(href)
        if not m:
            continue
        code = m.group(1)
        if not _is_ashare(code):
            continue
        name = a.get_text(strip=True)
        name = re.sub(r"[（(]\d{6}[）)]", "", name).strip()
        in_title = bool(title_name and name and (name in title_name or title_name in name))
        if not in_title and not _near_limit_up(a):
            continue
        reason = None
        if in_title and title_reason:
            reason = title_reason
        if not reason:
            reason = _nearby_board_name(a)
        if not reason:
            parent = a.find_parent(["p", "li", "div"])
            blob = parent.get_text(" ", strip=True) if parent else a.get_text(" ", strip=True)
            reason = _reason_from_blob(blob, name)
        if not reason:
            continue
        found[code] = LimitStock(code=code, name=name or code, reason=reason)
    return list(found.values())


def _parse_radar_title(title: str) -> tuple[str | None, str | None]:
    m = RADAR_TITLE_RE.search(title or "")
    if not m:
        return None, None
    return m.group(1).strip(), m.group(2).strip()


def _is_ashare(code: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    if code.startswith("399"):
        return False
    return code.startswith(("00", "30", "60", "68", "83", "43", "92"))


def _near_limit_up(anchor) -> bool:
    parent = anchor.find_parent("p") or anchor.find_parent("li") or anchor.find_parent("div")
    if parent is None:
        return "涨停" in (anchor.get_text() or "")
    name = anchor.get_text(strip=True)
    text = parent.get_text("", strip=True)
    if name and name[:2] in text:
        idx = text.find(name[:2] if len(name) < 2 else name[: min(4, len(name))])
        if idx >= 0:
            window = text[idx : idx + max(len(name), 4) + 28]
            if "涨停" in window:
                return True
    return False


def _nearby_board_name(anchor) -> str | None:
    parent = anchor.find_parent(["p", "li", "div", "td"])
    if parent is None:
        return None
    last = None
    for link in parent.find_all("a"):
        if link is anchor:
            break
        href = link.get("href") or ""
        if "/gn/detail/" in href or "/thshy/detail/" in href:
            text = link.get_text(strip=True)
            text = re.sub(r"[（(]\d+[）)]", "", text).strip()
            if text:
                last = text
    return last


def _reason_from_blob(blob: str, name: str) -> str | None:
    text = re.sub(r"\s+", "", blob)
    if name:
        text = text.replace(name, "")
    text = re.sub(r"\d{6}", "", text)
    m = re.search(r"(.{2,20}?)(?:板块|概念)?涨停", text)
    if m:
        reason = m.group(1).strip("，,。；;、:：")
        if 1 < len(reason) <= 20:
            return reason
    return None


def _norm_header(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("▲", "").replace("▼", "")


def _col(headers: list[str], values: list[str], *names: str) -> str:
    for name in names:
        for i, header in enumerate(headers):
            if name in header and i < len(values):
                return values[i]
    return ""


def _yi(text: str) -> float | None:
    value = to_float(text)
    if value is None:
        return None
    # 即时个股资金表用元；概念资金表表头带「亿」。
    if "亿" in (text or ""):
        return value * YI
    if abs(value) < 10000:
        return value * YI
    return value
