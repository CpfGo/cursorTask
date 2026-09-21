import sys
from pathlib import Path

from ashare2026.config import load_settings
from ashare2026.paths import bundle_dir, resolve_config_path, user_dir
from ashare2026.win_launcher import CONSOLE_URL, DEFAULT_HOST, DEFAULT_PORT, launch_console
from ashare2026.__main__ import entry


def test_source_paths_find_settings():
    assert (bundle_dir() / "config" / "settings.yaml").is_file()
    assert resolve_config_path().is_file()
    assert user_dir() == bundle_dir()


def test_frozen_paths_and_settings(monkeypatch, tmp_path):
    meipass = tmp_path / "meipass"
    exe_dir = tmp_path / "dist"
    meipass.mkdir()
    exe_dir.mkdir()
    cfg_dir = meipass / "config"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text(
        "app:\n  name: frozen-pack\n  timezone: Asia/Shanghai\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "AShare2026.exe"), raising=False)
    load_settings.cache_clear()
    try:
        assert bundle_dir() == meipass
        assert user_dir() == exe_dir
        assert resolve_config_path() == cfg_dir / "settings.yaml"
        settings = load_settings()
        assert settings.app.name == "frozen-pack"
    finally:
        load_settings.cache_clear()


def test_user_config_overrides_bundle(monkeypatch, tmp_path):
    meipass = tmp_path / "meipass"
    exe_dir = tmp_path / "dist"
    (meipass / "config").mkdir(parents=True)
    (exe_dir / "config").mkdir(parents=True)
    (meipass / "config" / "settings.yaml").write_text("app:\n  name: bundled\n", encoding="utf-8")
    (exe_dir / "config" / "settings.yaml").write_text("app:\n  name: overlay\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "AShare2026.exe"), raising=False)
    load_settings.cache_clear()
    try:
        assert resolve_config_path() == exe_dir / "config" / "settings.yaml"
        assert load_settings().app.name == "overlay"
    finally:
        load_settings.cache_clear()


def test_launcher_does_not_require_server(capsys):
    assert launch_console(open_browser=False, run_server=False) == 0
    out = capsys.readouterr().out
    assert CONSOLE_URL in out
    assert str(DEFAULT_PORT) in out
    assert DEFAULT_HOST in out


def test_frozen_double_click_starts_console(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    called = {}

    def fake_launch(**_kwargs):
        called["yes"] = True
        return 0

    monkeypatch.setattr("ashare2026.win_launcher.launch_console", fake_launch)
    assert entry(["AShare2026.exe"]) == 0
    assert called["yes"] is True


def test_spec_bundles_config_and_onedir():
    spec = Path("ashare2026.spec").read_text(encoding="utf-8")
    assert "config/settings.yaml" in spec.replace("\\", "/") or "config" in spec
    assert 'name="AShare2026"' in spec
    assert "COLLECT" in spec
    assert "tzdata" in spec
    assert "uvloop" in spec
