#!/usr/bin/env python3
"""Fetch nginx, redis, nsq versions and append daily row to markdown report."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen

from packaging import version

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "ztx" / "中间件版本信息.md"

USER_AGENT = "cursorTask-middleware-version-tracker/2.0"

HEADERS = [
    "日期",
    "nginx",
    "上一版本是否存在漏洞",
    "是否需要修复",
    "修复方法",
    "redis",
    "上一版本是否存在漏洞",
    "是否需要修复",
    "修复方法",
    "nsq",
    "上一版本是否存在漏洞",
    "是否需要修复",
    "修复方法",
]


class VulnerabilityRule(NamedTuple):
    line_minimums: dict[tuple[int, ...], str]
    default_minimum: str
    cves: tuple[str, ...]
    fix_method: str


VULNERABILITY_RULES: dict[str, VulnerabilityRule] = {
    "nginx": VulnerabilityRule(
        line_minimums={
            (1, 31): "1.31.2",
            (1, 30): "1.30.3",
            (1, 29): "1.29.7",
            (1, 28): "1.28.3",
        },
        default_minimum="1.31.2",
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
        line_minimums={
            (6, 2): "6.2.22",
            (7, 2): "7.2.14",
            (7, 4): "7.4.9",
            (8, 2): "8.2.6",
            (8, 4): "8.4.3",
            (8, 6): "8.6.3",
            (8, 8): "8.8.0",
        },
        default_minimum="8.6.3",
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
        line_minimums={
            (1, 3): "1.3.0",
            (1, 2): "1.2.1",
        },
        default_minimum="1.3.0",
        cves=(),
        fix_method=(
            "当前最新版暂无公开 CVE；"
            "生产环境请启用 TLS、配置 nsqauth 认证并限制 nsqd 端口暴露。"
        ),
    ),
}

REPOS = {
    "nginx": "nginx/nginx",
    "redis": "redis/redis",
    "nsq": "nsqio/nsq",
}


@dataclass(frozen=True)
class ComponentVersions:
    latest: str
    previous: str | None


def http_get_json(url: str) -> object:
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


def fetch_release_versions(repo: str) -> list[str]:
    tags: list[str] = []
    page = 1
    while page <= 5:
        payload = http_get_json(
            f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        )
        if not isinstance(payload, list) or not payload:
            break
        for release in payload:
            tag = release.get("tag_name") or release.get("name") or ""
            if not tag:
                continue
            normalized = normalize_version(tag)
            if re.match(r"^\d", normalized):
                tags.append(normalized)
        page += 1

    if not tags:
        latest_payload = http_get_json(f"https://api.github.com/repos/{repo}/releases/latest")
        tag = latest_payload.get("tag_name") or latest_payload.get("name") or ""
        if tag:
            tags.append(normalize_version(tag))

    unique: dict[tuple[int, ...], str] = {}
    for tag in tags:
        parsed = version.parse(tag)
        key = (parsed.major, parsed.minor, parsed.micro, parsed.pre, parsed.post)
        existing = unique.get(key)
        if existing is None or len(tag) > len(existing):
            unique[key] = tag

    return sorted(unique.values(), key=version.parse, reverse=True)


def resolve_component_versions(component: str) -> ComponentVersions:
    versions = fetch_release_versions(REPOS[component])
    if not versions:
        raise RuntimeError(f"No releases found for {component}")
    latest = versions[0]
    previous = versions[1] if len(versions) > 1 else None
    return ComponentVersions(latest=latest, previous=previous)


def version_line_key(component_version: str) -> tuple[int, ...]:
    parsed = version.parse(component_version)
    if parsed.major == 1 and parsed.minor >= 28:
        return (parsed.major, parsed.minor)
    if parsed.major >= 6:
        return (parsed.major, parsed.minor)
    return (parsed.major, parsed.minor)


def minimum_safe_for(component: str, component_version: str) -> str:
    rule = VULNERABILITY_RULES[component]
    line_key = version_line_key(component_version)
    if line_key in rule.line_minimums:
        return rule.line_minimums[line_key]
    return rule.default_minimum


def assess_previous_version(component: str, previous: str | None) -> tuple[str, str, str]:
    if previous is None:
        return "否", "否", "无上一版本可评估。"

    rule = VULNERABILITY_RULES[component]
    minimum_safe = minimum_safe_for(component, previous)
    is_vulnerable = version.parse(previous) < version.parse(minimum_safe)

    if not is_vulnerable:
        return "否", "否", "上一版本已达到官方修复基线，无需修复。"

    cve_text = "、".join(rule.cves) if rule.cves else "已知安全问题"
    fix = f"上一版本 {previous} 存在 {cve_text}，{rule.fix_method}"
    return "是", "是", fix


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def parse_markdown_table(content: str) -> tuple[str, list[list[str]]]:
    lines = content.splitlines()
    if not lines:
        return "", []

    header_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("| 日期 |"):
            header_idx = idx
            break

    if header_idx is None:
        return content, []

    preamble = "\n".join(lines[:header_idx]).rstrip()
    body_lines = lines[header_idx + 2 :]
    rows: list[list[str]] = []
    for line in body_lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells:
            rows.append(cells)
    return preamble, rows


def render_markdown_table(preamble: str, rows: list[list[str]]) -> str:
    header_row = "| " + " | ".join(HEADERS) + " |"
    separator = "| " + " | ".join(["---"] * len(HEADERS)) + " |"
    body = []
    for row in rows:
        padded = row + [""] * (len(HEADERS) - len(row))
        body.append("| " + " | ".join(escape_markdown_cell(cell) for cell in padded[: len(HEADERS)]) + " |")

    sections = []
    if preamble:
        sections.append(preamble)
    sections.extend([header_row, separator, *body])
    return "\n".join(sections) + "\n"


def upsert_daily_row(path: Path, row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    today = row[0]

    if path.exists():
        preamble, rows = parse_markdown_table(path.read_text(encoding="utf-8"))
    else:
        preamble = (
            "# 中间件版本与漏洞信息\n\n"
            "每日自动抓取 nginx、redis、nsq 最新版本，并评估上一版本是否存在已知漏洞。\n"
        )
        rows = []

    updated = False
    for idx, existing in enumerate(rows):
        if existing and existing[0] == today:
            rows[idx] = row
            updated = True
            break
    if not updated:
        rows.append(row)

    path.write_text(render_markdown_table(preamble, rows), encoding="utf-8")


def build_row(today: str, components: dict[str, ComponentVersions]) -> list[str]:
    row = [today]
    for component in ("nginx", "redis", "nsq"):
        info = components[component]
        has_vuln, needs_fix, fix_method = assess_previous_version(component, info.previous)
        row.extend([info.latest, has_vuln, needs_fix, fix_method])
    return row


def main() -> int:
    try:
        components = {name: resolve_component_versions(name) for name in ("nginx", "redis", "nsq")}
    except (URLError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"Failed to fetch middleware versions: {exc}", file=sys.stderr)
        return 1

    today = date.today().isoformat()
    row = build_row(today, components)
    upsert_daily_row(OUTPUT_PATH, row)

    print(f"Wrote middleware version report to {OUTPUT_PATH}")
    for name, info in components.items():
        has_vuln, needs_fix, _ = assess_previous_version(name, info.previous)
        print(
            f"{name}: latest={info.latest}, previous={info.previous}, "
            f"vulnerable={has_vuln}, needs_fix={needs_fix}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
