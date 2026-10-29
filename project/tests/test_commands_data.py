import json

import pandas as pd
from bot import commands
from common import GROUND_TRUTH, RAW_DIR, RES_PREP


def test_commands(con):
    assert "/yield" in commands.handle(con, "/help", "2026-04-10")[0]
    assert commands.handle(con, "/trend 1d", "2026-04-10")[0].startswith("Format")
    assert commands.handle(con, "/trend 7d", "2026-04-10")[0].count("\n") >= 7
    assert commands.handle(con, "/xyz", "2026-04-10")[0].startswith("Perintah tidak dikenal")


def test_ground_truth_events_present(con):
    gt = json.loads(GROUND_TRUTH.read_text())
    assert len(gt["yield_drops"]) == 3 and len(gt["late_data"]) == 2 and len(gt["empty_data"]) == 1
    day = gt["empty_data"][0]["date"]
    assert con.execute("SELECT COUNT(*) FROM production_daily WHERE strftime(CAST(date AS DATE),'%Y-%m-%d') = ?", [day]).fetchone()[0] == 0


def test_dirty_detection_complete():
    det = pd.read_csv(RES_PREP / "dirty_detection.csv")
    assert (det.recall == 1).all() and (det.precision == 1).all()


def test_dirty_share_2_to_3_percent():
    raw = pd.read_csv(RAW_DIR / "production_daily.csv")
    n = len(pd.read_csv(RAW_DIR / "ground_truth_dirty.csv"))
    assert 0.02 <= n / len(raw) <= 0.03
