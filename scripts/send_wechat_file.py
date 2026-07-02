#!/usr/bin/env python3
"""Send a file to a WeChat contact via desktop UI automation."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

CONTACT_NAME = os.environ.get("WECHAT_CONTACT", "Mr.Spongebob🧽")
WECHAT_CMD = os.environ.get("WECHAT_CMD", "/opt/wechat/wechat")
WECHAT_LD_LIBRARY_PATH = os.environ.get("WECHAT_LD_LIBRARY_PATH", "/opt/wechat")
DISPLAY = os.environ.get("DISPLAY", ":1")
SEARCH_WAIT_SEC = 2.0
UI_WAIT_SEC = 1.5


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def ensure_wechat_running() -> None:
    result = run(["pgrep", "-f", "/opt/wechat/wechat"], check=False)
    if result.returncode != 0:
        env = os.environ.copy()
        env["DISPLAY"] = DISPLAY
        env["LD_LIBRARY_PATH"] = WECHAT_LD_LIBRARY_PATH
        subprocess.Popen(
            [WECHAT_CMD],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(5)


def focus_wechat_window() -> str:
    result = run(["xdotool", "search", "--onlyvisible", "--class", "wechat"], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        result = run(["xdotool", "search", "--onlyvisible", "--name", "微信"], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("未找到微信窗口，请先登录微信")
    window_id = result.stdout.strip().splitlines()[0]
    run(["xdotool", "windowactivate", "--sync", window_id])
    time.sleep(UI_WAIT_SEC)
    return window_id


def type_text(text: str) -> None:
    run(["xdotool", "type", "--delay", "80", "--", text])
    time.sleep(0.5)


def press_key(key: str) -> None:
    run(["xdotool", "key", key])
    time.sleep(0.5)


def open_contact_chat(contact: str) -> None:
    focus_wechat_window()
    press_key("ctrl+f")
    time.sleep(SEARCH_WAIT_SEC)
    run(["xdotool", "key", "ctrl+a"])
    time.sleep(0.2)
    press_key("BackSpace")
    type_text(contact)
    time.sleep(SEARCH_WAIT_SEC)
    press_key("Return")
    time.sleep(UI_WAIT_SEC)


def send_file(file_path: Path) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ensure_wechat_running()
    open_contact_chat(CONTACT_NAME)

    # WeChat Linux: drag-drop is unreliable; use clipboard paste path via file dialog.
    run(["xdotool", "key", "ctrl+shift+f"])
    time.sleep(2.0)
    type_text(str(file_path.resolve()))
    time.sleep(0.5)
    press_key("Return")
    time.sleep(1.0)
    press_key("Return")
    print(f"已尝试向 {CONTACT_NAME} 发送文件: {file_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="通过微信桌面客户端发送文件")
    parser.add_argument(
        "file",
        nargs="?",
        default=str(Path.home() / "Desktop" / "ztx" / "中间件版本信息.xlsx"),
        help="要发送的文件路径",
    )
    parser.add_argument(
        "--contact",
        default=CONTACT_NAME,
        help="微信联系人名称",
    )
    args = parser.parse_args()

    global CONTACT_NAME
    CONTACT_NAME = args.contact

    try:
        send_file(Path(args.file))
    except Exception as exc:
        print(f"发送失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
