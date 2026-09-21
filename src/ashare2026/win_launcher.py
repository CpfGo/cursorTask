from __future__ import annotations

"""Windows / frozen entry: start the FastAPI console and open the browser."""

import os
import sys
import threading
import time
import webbrowser

import uvicorn

from ashare2026.api.app import app
from ashare2026.paths import user_dir

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
CONSOLE_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def launch_console(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    run_server: bool = True,
) -> int:
    _configure_stdio()
    try:
        os.chdir(user_dir())
    except OSError:
        pass

    url = f"http://{host}:{port}"
    print("A股2026主线识别系统")
    print(f"控制台: {url}")
    print("关闭本窗口即停止服务。生成报告需要联网访问行情源。")

    if open_browser:
        def _open() -> None:
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    if not run_server:
        return 0

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
