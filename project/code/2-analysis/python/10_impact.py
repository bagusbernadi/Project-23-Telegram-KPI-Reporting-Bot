"""Tahap 2 / langkah 10: dampak waktu (Q10, Q11). Waktu otomatis DIUKUR (jalankan pipeline satu hari); waktu manual adalah ESTIMASI
asumsi penulis (tidak diukur dengan stopwatch). Keluaran: results/2-analysis/{impact_time.csv, impact_scenarios.csv}
"""
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot.report import build_alert_message, build_message, evaluate_alerts, load_kpis, render_chart  # noqa: E402
from common import ALERT_RULES, DB_PATH, RES_ANALYSIS  # noqa: E402

MANUAL_STEPS = {"unduh dan rapikan data": 8, "hitung yield/NG/rework di Excel": 10, "buat grafik": 5, "periksa angka": 4, "tulis dan kirim pesan": 3}   # menit, ESTIMASI
REVIEW_MIN = 2            # menit engineer membaca pesan bot (ESTIMASI)
WORKDAYS_YEAR = 245       # asumsi hari kerja per tahun (52 minggu x 5 - libur)


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rules = con.execute("SELECT * FROM alert_rule").df()
    dates = [r[0] for r in con.execute("SELECT strftime(date,'%Y-%m-%d') FROM v_line_daily ORDER BY date").fetchall()][20:]
    tmp = Path(tempfile.mkdtemp())
    times = []
    for d in dates:
        t0 = time.perf_counter()
        k = load_kpis(con, d); al = evaluate_alerts(con, d, rules)
        build_message(k, al); build_alert_message(k, al) if al else None; render_chart(con, d, tmp / f"{d}.png")
        times.append(time.perf_counter() - t0)
    s = pd.Series(times)
    manual = sum(MANUAL_STEPS.values())
    imp = pd.DataFrame([
        ["waktu otomatis per laporan (detik)", round(s.median(), 2), "diukur: median dari %d laporan, laptop/container ini" % len(s)],
        ["waktu otomatis maks (detik)", round(s.max(), 2), "diukur"],
        ["waktu manual per laporan (menit)", manual, "ESTIMASI: " + "; ".join(f"{k} {v}" for k, v in MANUAL_STEPS.items())],
        ["waktu baca pesan bot (menit)", REVIEW_MIN, "ESTIMASI"],
        ["menit dihemat per laporan", manual - REVIEW_MIN, "estimasi"],
        ["hari kerja per tahun", WORKDAYS_YEAR, "asumsi"],
        ["jam kerja dihemat per tahun", round((manual - REVIEW_MIN) * WORKDAYS_YEAR / 60, 1), "estimasi"],
    ], columns=["item", "value", "label"])
    imp.to_csv(RES_ANALYSIS / "impact_time.csv", index=False)
    sc = pd.DataFrame([(m, round((m - REVIEW_MIN) * WORKDAYS_YEAR / 60, 1)) for m in (15, 20, 30, 40)], columns=["manual_minutes_per_report", "hours_saved_per_year"])
    sc.to_csv(RES_ANALYSIS / "impact_scenarios.csv", index=False)
    print(imp.to_string(index=False)); print(sc.to_string(index=False))


if __name__ == "__main__":
    main()
