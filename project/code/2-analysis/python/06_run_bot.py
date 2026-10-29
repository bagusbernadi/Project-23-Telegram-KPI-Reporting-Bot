"""Tahap 2 / langkah 06: putar ulang seluruh periode memakai kode bot yang sama (DryRunSender, tanpa Telegram).

Menghasilkan delivery_log (Q7), ringkasan pesan, serta contoh pesan untuk README/dashboard.
Keluaran: results/2-analysis/{delivery_log.csv, delivery_summary.csv, day_outcomes.csv}; docs/samples/*.txt|png
Catatan: runner_log (jeda dan kegagalan Actions) dan latency_s adalah SIMULASI, bukan pengukuran GitHub Actions/Telegram nyata.
"""
import shutil
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot.run_daily import simulate  # noqa: E402
from bot.sender import DryRunSender  # noqa: E402
from common import ALERT_RULES, DATA, DB_PATH, DOCS_DIR, RES_ANALYSIS, SEED  # noqa: E402


def main():
    con = duckdb.connect(str(DB_PATH))
    cfg = yaml.safe_load(ALERT_RULES.read_text(encoding="utf-8"))["missing_data"]
    rules = con.execute("SELECT * FROM alert_rule").df()
    runner = con.execute("SELECT date, scheduled_at, started_at, status FROM runner_log ORDER BY date").df()
    rng = np.random.default_rng(SEED + 6)
    sender = DryRunSender(latency_fn=lambda: int(rng.integers(2, 7)))
    out = DATA / "outbox"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    state = simulate(con, sender, runner, rules, cfg, out)

    log = pd.DataFrame(sender.log).sort_values(["sent_at", "report_date"]).reset_index(drop=True)
    log.to_csv(RES_ANALYSIS / "delivery_log.csv", index=False)
    con.execute("DELETE FROM delivery_log")
    con.execute("INSERT INTO delivery_log SELECT CAST(sent_at AS TIMESTAMP), message_type, status, latency_s, error, CAST(report_date AS DATE) FROM log")

    # hasil per hari produksi
    limit = cfg["on_time_limit"]
    rows = []
    for r in runner.itertuples():
        d = pd.Timestamp(r.date).strftime("%Y-%m-%d")
        s = state[d]
        has_arrival = con.execute("SELECT COUNT(*) FROM data_arrival_log WHERE strftime(date,'%Y-%m-%d') = ?", [d]).fetchone()[0] == 2
        sent_at = s.get("sent_at")
        on_time = bool(sent_at and sent_at[11:16] <= limit)
        rows.append(dict(report_date=d, runner_status=r.status, data_arrived=has_arrival, report_sent=s["sent"], sent_at=sent_at,
                         on_time=on_time, alerts=s.get("alerts", 0), notified_missing=s["notified"], gave_up=s["gave_up"]))
    days = pd.DataFrame(rows)
    days.to_csv(RES_ANALYSIS / "day_outcomes.csv", index=False)

    ok = log[log.status == "sent"]
    expected = days[days.data_arrived]                     # hari dengan data tiba (laporan seharusnya ada)
    ready = days[days.data_arrived & ~days.notified_missing]   # data sudah ada saat run 07:00 (keandalan bot sendiri)
    summ = pd.DataFrame([
        ["hari kerja dilaporkan", len(days)],
        ["pesan daily terkirim", int((ok.message_type == "daily").sum())],
        ["pesan alert terkirim", int((ok.message_type == "alert").sum())],
        ["pesan no_data terkirim", int((ok.message_type == "no_data").sum())],
        ["pengiriman gagal (run Actions)", int((log.status == "failed").sum())],
        [f"hari dengan data tiba, laporan terkirim <= {limit}", int(expected.on_time.sum())],
        ["hari dengan data tiba", len(expected)],
        ["on-time rate ujung ke ujung (hari dengan data tiba)", round(100 * expected.on_time.mean(), 1)],
        ["hari dengan data sudah ada saat run 07:00", len(ready)],
        ["laporan tepat waktu di antara hari tsb", int(ready.on_time.sum())],
        ["on-time delivery rate bot (data sudah ada)", round(100 * ready.on_time.mean(), 1)],
        ["on-time rate semua hari kerja (termasuk data hilang)", round(100 * days.on_time.mean(), 1)],
        ["median latency_s", float(ok.latency_s.median())],
        ["hari tanpa laporan harian", int((~days.report_sent).sum())],
    ], columns=["metric", "value"])
    summ.to_csv(RES_ANALYSIS / "delivery_summary.csv", index=False)
    print(summ.to_string(index=False))

    # contoh pesan untuk dokumentasi
    smp = DOCS_DIR / "samples"
    shutil.rmtree(smp, ignore_errors=True)
    smp.mkdir(parents=True)
    pick = {"normal": "2026-03-27", "alert_engine": "2026-03-30", "alert_painting": "2026-05-04", "alert_dyno_gradual": "2026-06-02"}
    for tag, d in pick.items():
        msgs = [m for m in sender.messages if m["report_date"] == d and m["kind"] in ("daily", "alert")]
        (smp / f"{tag}_{d}.txt").write_text("\n\n---\n\n".join(f"[{m['kind']}] {m['sent_at']}\n{m['text']}" for m in msgs), encoding="utf-8")
        shutil.copy(out / f"chart_{d}.png", smp / f"{tag}_{d}.png")
    for m in sender.messages:
        if m["kind"] == "no_data" and m["report_date"] in ("2026-04-21", "2026-04-17"):
            pass
    nd = [m for m in sender.messages if m["kind"] == "no_data"]
    (smp / "no_data_contoh.txt").write_text("\n\n---\n\n".join(f"[{m['kind']}] {m['sent_at']} (tanggal {m['report_date']})\n{m['text']}" for m in nd), encoding="utf-8")
    con.close()


if __name__ == "__main__":
    main()
