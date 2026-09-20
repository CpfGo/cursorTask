from pathlib import Path

from ashare2026.config import load_settings
from ashare2026.timeutil import is_after_open, is_auction_window
from datetime import datetime
from zoneinfo import ZoneInfo


def test_settings_load_urls():
    settings = load_settings()
    assert settings.app.report_title == "A股主线识别日报"
    assert len(settings.data_sources) == 10
    assert settings.scoring.mainline.turnover_share == 25
    assert Path(settings.app.name)


def test_auction_window():
    tz = ZoneInfo("Asia/Shanghai")
    morning = datetime(2026, 9, 18, 9, 20, tzinfo=tz)
    after = datetime(2026, 9, 18, 10, 0, tzinfo=tz)
    assert is_auction_window(morning)
    assert is_after_open(after)
    assert not is_auction_window(after)
