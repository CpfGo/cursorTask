from __future__ import annotations

import argparse
from pathlib import Path

from ashare2026.paths import user_dir
from ashare2026.pipeline.engine import run_pipeline
from ashare2026.report.html import render_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ashare2026", description="A股2026主线识别系统")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_report = sub.add_parser("report", help="生成 HTML 日报")
    p_report.add_argument("-o", "--output", default="")
    p_report.add_argument("--json", dest="json_path", default="")
    p_serve = sub.add_parser("serve", help="启动 API 与网页")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("check", help="检查数据源可用性")
    args = parser.parse_args(argv)

    if args.cmd == "report":
        result = run_pipeline()
        html = render_html(result)
        out = Path(args.output) if args.output else user_dir() / "reports" / "daily.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        if args.json_path:
            Path(args.json_path).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(out)
        return 0
    if args.cmd == "check":
        result = run_pipeline()
        for row in result.availability:
            flag = "OK" if row.available else "MISSING"
            print(f"{flag}\t{row.item}\t{row.actual_source or ''}\t{row.impact}")
        return 0
    if args.cmd == "serve":
        import uvicorn

        from ashare2026.api.app import app

        uvicorn.run(app, host=args.host, port=args.port, reload=False)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
