#!/usr/bin/env python3
"""Fetch nginx, redis, nsq latest versions and append daily vulnerability summary."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_MD = ROOT / "ztx" / "中间件版本信息.md"

GITHUB_API = "https://api.github.com/repos/{repo}/releases"
USER_AGENT = "cursorTask-middleware-version-tracker/1.0"


@dataclass
class MiddlewareInfo:
    name: str
    latest: str
    previous: str
    prev_vulnerable: bool
    needs_fix: bool
    fix_method: str


# Minimum versions that include all currently known security fixes (official advisories).
KNOWN_PATCHED_MINIMUM = {
    "nginx": "1.31.2",
    "redis": "8.6.3",
}

# NSQ has no recent official CVE requiring upgrade; track version only.
NSQ_HAS_KNOWN_CVE = False

NGINX_PREV_VULNS = (
    "CVE-2026-42530 (HTTP/3 use-after-free), "
    "CVE-2026-42055 (proxy_v2/grpc buffer overflow), "
    "CVE-2026-48142 (charset buffer overread)"
)

REDIS_PREV_VULNS = (
    "CVE-2026-23479, CVE-2026-25243, CVE-2026-23631, "
    "CVE-2026-25588, CVE-2026-25589 (RCE)"
)

NSQ_FIX = (
    "无已知高危 CVE；建议启用 TLS（--tls-required）、配置 auth-http 认证，"
    "并将 nsqadmin 置于反向代理后"
)


def _fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _parse_version(version: str) -> tuple:
    cleaned = version.lstrip("v").replace("release-", "")
    parts: list = []
    for part in re.split(r"[.-]", cleaned):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    return tuple(parts)


def _version_lt(left: str, right: str) -> bool:
    return _parse_version(left) < _parse_version(right)


def _normalize_tag(tag: str) -> str:
    return tag.lstrip("v").replace("release-", "")


def _github_releases(repo: str, limit: int = 20) -> list[dict]:
    url = f"{GITHUB_API.format(repo=repo)}?per_page={limit}"
    data = _fetch_json(url)
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected GitHub response for {repo}")
    return [r for r in data if not r.get("prerelease")]


def _latest_release(releases: list[dict]) -> dict:
    return max(releases, key=lambda r: _parse_version(_normalize_tag(r["tag_name"])))


def _previous_release(releases: list[dict], latest_tag: str) -> dict:
    latest_ver = _parse_version(_normalize_tag(latest_tag))
    older = [
        r for r in releases
        if _parse_version(_normalize_tag(r["tag_name"])) < latest_ver
    ]
    if not older:
        return releases[0]
    return max(older, key=lambda r: _parse_version(_normalize_tag(r["tag_name"])))


def _nginx_stable_version() -> Optional[str]:
    try:
        html = urllib.request.urlopen(
            urllib.request.Request("https://nginx.org/en/download.html", headers={"User-Agent": USER_AGENT}),
            timeout=30,
        ).read().decode()
        match = re.search(r"nginx-(\d+\.\d+\.\d+)\s+stable", html, re.I)
        if match:
            return match.group(1)
    except urllib.error.URLError:
        pass
    return None


def _fetch_middleware(repo: str, name: str, vuln_detail: str, fix_hint: str) -> MiddlewareInfo:
    releases = _github_releases(repo)
    if not releases:
        raise RuntimeError(f"No releases found for {repo}")

    latest_release = _latest_release(releases)
    latest_tag = latest_release["tag_name"]
    latest = _normalize_tag(latest_tag)

    if name == "nginx":
        stable = _nginx_stable_version()
        if stable and _version_lt(latest, stable):
            latest = stable

    prev_release = _previous_release(releases, latest_tag)
    previous = _normalize_tag(prev_release["tag_name"])
    if name == "nsq":
        prev_vulnerable = NSQ_HAS_KNOWN_CVE and _version_lt(previous, latest)
        needs_fix = prev_vulnerable
        fix_method = fix_hint if prev_vulnerable else "无需修复"
    else:
        patched_min = KNOWN_PATCHED_MINIMUM[name]
        prev_vulnerable = _version_lt(previous, patched_min)
        needs_fix = prev_vulnerable
        if prev_vulnerable:
            fix_method = (
                f"将 {name} 从 {previous} 升级至 {latest}（或不低于 {patched_min}）。"
                f"漏洞：{vuln_detail}。{fix_hint}"
            )
        else:
            fix_method = "无需修复"

    return MiddlewareInfo(
        name=name,
        latest=latest,
        previous=previous,
        prev_vulnerable=prev_vulnerable,
        needs_fix=needs_fix,
        fix_method=fix_method,
    )


def _aggregate_fix(methods: list[str]) -> str:
    actionable = [m for m in methods if m and m != "无需修复"]
    if not actionable:
        return "无需修复"
    return "；".join(actionable)


def _build_row(today: str, items: list[MiddlewareInfo]) -> str:
    any_vuln = any(i.prev_vulnerable for i in items)
    any_fix = any(i.needs_fix for i in items)
    vuln_text = "是" if any_vuln else "否"
    fix_text = "是" if any_fix else "否"
    fix_method = _aggregate_fix([i.fix_method for i in items if i.prev_vulnerable])

    nginx, redis, nsq = items
    return (
        f"| {today} | {nginx.latest} | {redis.latest} | {nsq.latest} | "
        f"{vuln_text} | {fix_text} | {fix_method} |"
    )


def _read_existing_rows(content: str) -> list[str]:
    rows = []
    for line in content.splitlines():
        if line.startswith("| 20") and line.count("|") >= 7:
            rows.append(line)
    return rows


def _upsert_markdown(today: str, row: str) -> None:
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# 中间件版本与漏洞追踪\n\n"
        "每日自动抓取 nginx、redis、nsq 最新版本，并对比上一发布版本是否存在已知漏洞。\n\n"
        "| 日期 | nginx | redis | nsq | 上一版本是否存在漏洞 | 是否需要修复 | 修复方法 |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
    )

    if OUTPUT_MD.exists():
        existing = OUTPUT_MD.read_text(encoding="utf-8")
        rows = _read_existing_rows(existing)
        rows = [r for r in rows if not r.startswith(f"| {today} ")]
        rows.insert(0, row)
        body = header + "\n".join(rows) + "\n"
    else:
        body = header + row + "\n"

    footer = (
        "\n---\n\n"
        "**说明**\n\n"
        "- 上一版本：GitHub 上当前最新正式版的前一个正式版。\n"
        "- 漏洞基准：nginx ≥ 1.31.2 / 1.30.3（[官方安全公告](https://nginx.org/en/security_advisories.html)）；"
        "redis ≥ 8.6.3（[安全公告](https://redis.io/blog/security-advisory-cve202623479-cve202625243-cve-2026-25588-cve202625589-cve-2026-23631/)）；"
        "nsq 暂无近期高危 CVE。\n"
        "- 数据来源：GitHub Releases、nginx.org、Redis 官方公告。\n"
    )

    OUTPUT_MD.write_text(body + footer, encoding="utf-8")
    print(f"Updated {OUTPUT_MD}")


def main() -> None:
    today = date.today().isoformat()

    nginx = _fetch_middleware(
        "nginx/nginx",
        "nginx",
        NGINX_PREV_VULNS,
        "参考 https://nginx.org/en/download.html 下载并平滑 reload。",
    )
    redis = _fetch_middleware(
        "redis/redis",
        "redis",
        REDIS_PREV_VULNS,
        "参考 https://redis.io/docs/latest/operate/oss_and_stack/ 升级并重启实例。",
    )
    nsq = _fetch_middleware(
        "nsqio/nsq",
        "nsq",
        "无近期官方 CVE",
        NSQ_FIX,
    )

    row = _build_row(today, [nginx, redis, nsq])
    _upsert_markdown(today, row)

    summary = {
        "date": today,
        "nginx": nginx.latest,
        "redis": redis.latest,
        "nsq": nsq.latest,
        "vulnerable": any(i.prev_vulnerable for i in [nginx, redis, nsq]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
