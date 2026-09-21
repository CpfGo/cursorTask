from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Read-only assets: PyInstaller _MEIPASS, or the repo root."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_dir() -> Path:
    """Writable root: folder that contains the exe, or the repo root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_config_path() -> Path:
    user_cfg = user_dir() / "config" / "settings.yaml"
    if user_cfg.is_file():
        return user_cfg
    return bundle_dir() / "config" / "settings.yaml"
