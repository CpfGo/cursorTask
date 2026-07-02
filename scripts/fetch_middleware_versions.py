#!/usr/bin/env python3
"""Fetch nginx, redis, nsq latest versions and update middleware version Excel."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import requests
from openpyxl import Workbook, load_workbook
from packaging.version import Version, InvalidVersion

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = REPO_ROOT / "ztx" / "中间件版本信息.xlsx"
HEADERS = ["日期", "nginx", "redis", "nsq", "是否存在漏洞", "修复方法"]
USER_AGENT = "cursorTask-middleware-version-tracker/1.0"

# Minimum patched versions from official security advisories (2026).
KNOWN_PATCHED_MINIMUM = {
    "nginx": Version("1.30.3"),
    "redis": Version("8.6.3"),
    "nsq": Version("1.3.0"),
}

KNOWN_VULNERABILITIES = {
    "nginx": {
        "cves": ["CVE-2026-42055", "CVE-2026-48142", "CVE-2026-42530"],
        "fix": "升级至 nginx 1.30.3（stable）或 1.31.2（mainline）；下载地址 https://nginx.org/en/download.html",
    },
    "redis": {
        "cves": [
            "CVE-2026-23479",
            "CVE-2026-25243",
            "CVE-2026-25588",
            "CVE-2026-25589",
            "CVE-2026-23631",
        ],
        "fix": (
            "升级至 Redis 8.6.3 或更高版本（当前最新 8.8.0）；"
            "参考 https://redis.io/blog/security-advisory-cve202623479-cve202625243-cve-2026-25588-cve202625589-cve-2026-23631/"
        ),
    },
    "nsq": {
        "cves": [],
        "fix": (
            "启用 TLS（--tls-cert-file/--tls-key-file）、配置 nsqauth 认证、"
            "限制 nsqadmin/nsqlookupd 网络访问；参考 https://nsq.io/components/nsqd.html#tls"
        ),
    },
}


def http_get(url: str, timeout: int = 30) -> requests.Response:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    return response


def parse_version(raw: str) -> Version:
    cleaned = raw.strip().lstrip("v").replace("release-", "")
    match = re.search(r"(\d+(?:\.\d+)*)", cleaned)
    if not match:
        raise InvalidVersion(f"Cannot parse version from: {raw}")
    return Version(match.group(1))


def fetch_nginx_version() -> str:
    release = http_get("https://api.github.com/repos/nginx/nginx/releases/latest").json()
    mainline = parse_version(release["tag_name"])

    page = http_get("https://nginx.org/en/download.html").text
    stable_match = re.search(r"nginx-(\d+\.\d+\.\d+)", page)
    if not stable_match:
        return str(mainline)
    stable = parse_version(stable_match.group(1))
    return str(max(stable, mainline))


def fetch_redis_version() -> str:
    release = http_get("https://api.github.com/repos/redis/redis/releases/latest").json()
    return str(parse_version(release["tag_name"]))


def fetch_nsq_version() -> str:
    release = http_get("https://api.github.com/repos/nsqio/nsq/releases/latest").json()
    return str(parse_version(release["tag_name"]))


def assess_vulnerabilities(versions: dict[str, str]) -> tuple[str, str]:
    affected: list[str] = []
    fixes: list[str] = []

    for name, version_str in versions.items():
        try:
            version = parse_version(version_str)
        except InvalidVersion:
            affected.append(name)
            fixes.append(f"{name}: 无法解析版本 {version_str}，请人工确认并升级至最新版")
            continue

        minimum = KNOWN_PATCHED_MINIMUM.get(name)
        if minimum and version < minimum:
            affected.append(name)
            info = KNOWN_VULNERABILITIES[name]
            cve_text = "、".join(info["cves"]) if info["cves"] else "已知安全风险"
            fixes.append(f"{name}({version_str}) 存在 {cve_text}；{info['fix']}")

    if affected:
        return "是", "；".join(fixes)
    return "否", "当前最新版本无已知未修复漏洞，建议持续关注官方安全公告"


def ensure_workbook(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "中间件版本"
    sheet.append(HEADERS)
    workbook.save(path)


def upsert_daily_row(
    path: Path,
    row_date: date,
    nginx: str,
    redis_version: str,
    nsq: str,
    has_vuln: str,
    fix_method: str,
) -> None:
    ensure_workbook(path)
    workbook = load_workbook(path)
    sheet = workbook.active

    if sheet.max_row == 1 and sheet.cell(1, 1).value != HEADERS[0]:
        sheet.delete_rows(1, sheet.max_row)
        sheet.append(HEADERS)

    date_str = row_date.isoformat()
    existing_row = None
    for row_idx in range(2, sheet.max_row + 1):
        if str(sheet.cell(row_idx, 1).value) == date_str:
            existing_row = row_idx
            break

    values = [date_str, nginx, redis_version, nsq, has_vuln, fix_method]
    if existing_row:
        for col_idx, value in enumerate(values, start=1):
            sheet.cell(existing_row, col_idx, value)
    else:
        sheet.append(values)

    workbook.save(path)


def main() -> int:
    try:
        versions = {
            "nginx": fetch_nginx_version(),
            "redis": fetch_redis_version(),
            "nsq": fetch_nsq_version(),
        }
    except requests.RequestException as exc:
        print(f"Failed to fetch version information: {exc}", file=sys.stderr)
        return 1

    has_vuln, fix_method = assess_vulnerabilities(versions)
    today = date.today()

    upsert_daily_row(
        OUTPUT_FILE,
        today,
        versions["nginx"],
        versions["redis"],
        versions["nsq"],
        has_vuln,
        fix_method,
    )

    print(f"Updated {OUTPUT_FILE}")
    print(f"Date: {today.isoformat()}")
    print(f"nginx: {versions['nginx']}, redis: {versions['redis']}, nsq: {versions['nsq']}")
    print(f"是否存在漏洞: {has_vuln}")
    print(f"修复方法: {fix_method}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
