#!/usr/bin/env python3
"""Fetch latest nginx, redis, nsq versions and append daily row to Excel."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen
import json

from openpyxl import Workbook, load_workbook
from packaging import version

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "ztx" / "中间件版本信息.xlsx"
HEADERS = ["日期", "nginx", "redis", "nsq", "是否存在漏洞", "修复方法"]

USER_AGENT = "cursorTask-middleware-version-tracker/1.0"


class MiddlewareInfo(NamedTuple):
    name: str
    version: str
    source: str


class VulnerabilityRule(NamedTuple):
    minimum_safe: str
    cves: tuple[str, ...]
    fix_method: str


VULNERABILITY_RULES: dict[str, VulnerabilityRule] = {
    "nginx": VulnerabilityRule(
        minimum_safe="1.31.2",
        cves=(
            "CVE-2026-42530",
            "CVE-2026-42055",
            "CVE-2026-48142",
        ),
        fix_method=(
            "升级 nginx 至 1.31.2（mainline）或 1.30.3（stable）；"
            "若暂无法升级且启用了 HTTP/3，可在 listen 中移除 quic 并设置 http3 off 以降低 CVE-2026-42530 风险。"
        ),
    ),
    "redis": VulnerabilityRule(
        minimum_safe="8.6.3",
        cves=(
            "CVE-2026-23479",
            "CVE-2026-25243",
            "CVE-2026-25588",
            "CVE-2026-25589",
            "CVE-2026-23631",
        ),
        fix_method=(
            "升级 Redis 至对应分支修复版本或更高：6.2.22、7.2.14、7.4.9、8.2.6、8.4.3、8.6.3；"
            "限制网络访问并启用强认证，禁用 replica-read-only=no 的非必要配置。"
        ),
    ),
    "nsq": VulnerabilityRule(
        minimum_safe="1.3.0",
        cves=(),
        fix_method=(
            "当前最新版 1.3.0 暂无公开 CVE；"
            "生产环境请启用 TLS、配置 nsqauth 认证并限制 nsqd 端口暴露。"
        ),
    ),
}


def http_get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_version(raw: str) -> str:
    cleaned = raw.strip()
    for prefix in ("release-", "v", "V"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    match = re.search(r"\d+(?:\.\d+)*", cleaned)
    if not match:
        raise ValueError(f"Unable to parse version from: {raw!r}")
    return match.group(0)


def fetch_github_latest(repo: str) -> MiddlewareInfo:
    payload = http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    tag = payload.get("tag_name") or payload.get("name") or ""
    if not tag:
        raise RuntimeError(f"No release tag found for {repo}")
    return MiddlewareInfo(name=repo.split("/")[-1], version=normalize_version(tag), source=tag)


def fetch_nginx_latest() -> MiddlewareInfo:
    info = fetch_github_latest("nginx/nginx")
    return MiddlewareInfo("nginx", info.version, info.source)


def fetch_redis_latest() -> MiddlewareInfo:
    info = fetch_github_latest("redis/redis")
    return MiddlewareInfo("redis", info.version, info.source)


def fetch_nsq_latest() -> MiddlewareInfo:
    info = fetch_github_latest("nsqio/nsq")
    return MiddlewareInfo("nsq", info.version, info.source)


def is_version_safe(component: str, current_version: str) -> bool:
    rule = VULNERABILITY_RULES[component]
    return version.parse(current_version) >= version.parse(rule.minimum_safe)


def build_vulnerability_assessment(versions: dict[str, str]) -> tuple[str, str]:
    vulnerable: list[str] = []
    fixes: list[str] = []

    for component, current in versions.items():
        rule = VULNERABILITY_RULES[component]
        if is_version_safe(component, current):
            continue
        cve_text = "、".join(rule.cves) if rule.cves else "已知安全问题"
        vulnerable.append(f"{component} {current}（{cve_text}）")
        fixes.append(f"{component}: {rule.fix_method}")

    if vulnerable:
        return "是", "；".join(fixes)
    return "否", "当前最新版本均已达到官方修复基线，无需额外修复。"


def ensure_workbook(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return load_workbook(path)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "中间件版本"
    sheet.append(HEADERS)
    return workbook


def today_exists(sheet, today: str) -> bool:
    for row in sheet.iter_rows(min_row=2, max_col=1, values_only=True):
        if row[0] == today:
            return True
    return False


def append_daily_row(path: Path, row: list[str]) -> None:
    workbook = ensure_workbook(path)
    sheet = workbook.active
    today = row[0]

    if today_exists(sheet, today):
        for idx, existing in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if existing[0] == today:
                for col_idx, value in enumerate(row, start=1):
                    sheet.cell(row=idx, column=col_idx, value=value)
                break
    else:
        sheet.append(row)

    workbook.save(path)


def main() -> int:
    try:
        nginx = fetch_nginx_latest()
        redis_info = fetch_redis_latest()
        nsq = fetch_nsq_latest()
    except (URLError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"Failed to fetch middleware versions: {exc}", file=sys.stderr)
        return 1

    versions = {
        "nginx": nginx.version,
        "redis": redis_info.version,
        "nsq": nsq.version,
    }
    has_vuln, fix_method = build_vulnerability_assessment(versions)
    today = date.today().isoformat()

    row = [
        today,
        nginx.version,
        redis_info.version,
        nsq.version,
        has_vuln,
        fix_method,
    ]

    append_daily_row(OUTPUT_PATH, row)

    print(f"Wrote middleware version report to {OUTPUT_PATH}")
    print(
        f"日期={today}, nginx={nginx.version} ({nginx.source}), "
        f"redis={redis_info.version} ({redis_info.source}), "
        f"nsq={nsq.version} ({nsq.source}), 是否存在漏洞={has_vuln}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
