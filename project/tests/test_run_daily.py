import tempfile
from datetime import datetime
from pathlib import Path

from bot.run_daily import process_day
from bot.sender import DryRunSender

TMP = Path(tempfile.mkdtemp())


def _run(con, rules, cfg, d, times):
    s, st = DryRunSender(), {}
    for t in times:
        process_day(con, d, t, s, st, rules, cfg, TMP)
    return s, st


def test_normal_day(con, rules, cfg):
    s, _ = _run(con, rules, cfg, "2026-03-27", [datetime(2026, 3, 30, 7, 5)])
    assert [m["kind"] for m in s.messages] == ["daily"] and s.messages[0]["photo"]


def test_alert_day(con, rules, cfg):
    s, _ = _run(con, rules, cfg, "2026-03-30", [datetime(2026, 3, 31, 7, 5)])
    assert [m["kind"] for m in s.messages] == ["daily", "alert"]


def test_late_data_then_report(con, rules, cfg):
    times = [datetime(2026, 3, 24, h, 0) for h in (7, 8, 9, 10, 11, 12, 13, 14)]
    s, st = _run(con, rules, cfg, "2026-03-23", times)
    assert [m["kind"] for m in s.messages][:2] == ["no_data", "daily"] and not st["2026-03-23"]["gave_up"]


def test_empty_day_gives_up(con, rules, cfg):
    times = [datetime(2026, 4, 17, h, 0) for h in range(7, 16)]
    s, st = _run(con, rules, cfg, "2026-04-16", times)
    assert [m["kind"] for m in s.messages] == ["no_data", "no_data"] and st["2026-04-16"]["gave_up"]


def test_idempotent(con, rules, cfg):
    s, _ = _run(con, rules, cfg, "2026-03-27", [datetime(2026, 3, 30, h, 5) for h in (7, 8, 9)])
    assert len(s.messages) == 1
