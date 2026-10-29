"""Tahap 2 / langkah 07: alert yang benar-benar dikirim bot (aturan aktif di config) dibandingkan dengan ground truth (Q4-Q6) + jeda (Q5).

Jeda dihitung dari tanggal kejadian ke pesan alert pertama untuk kejadian itu. Asumsi jam kerja (BUKAN data): Shift 1 mulai 07:00, Shift 2 selesai 23:00;
laporan manual dianggap sampai 12:00 hari kerja berikutnya (rujukan pada halaman Design: "baru sampai siang hari").
Keluaran: results/2-analysis/{alert_events.csv, alert_rule_performance.csv, alert_lag.csv}
"""
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot.report import evaluate_alerts  # noqa: E402
from common import DB_PATH, GROUND_TRUTH, RES_ANALYSIS  # noqa: E402


def main():
    gt = json.loads(GROUND_TRUTH.read_text())
    wins = [dict(station=e["station"], days=pd.bdate_range(e["start"], e["end"]).strftime("%Y-%m-%d").tolist()) for e in gt["yield_drops"]]
    spike = gt["defect_spike"]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rules = con.execute("SELECT * FROM alert_rule").df()
    station_of = dict(con.execute("SELECT defect_code, station FROM dim_defect").fetchall())
    dates = [r[0] for r in con.execute("SELECT strftime(date,'%Y-%m-%d') FROM v_line_daily ORDER BY date").fetchall()]
    ev = {(w["station"], d) for w in wins for d in w["days"]}
    ev_days = {d for w in wins for d in w["days"]}
    rows = []
    for d in dates:
        for a in evaluate_alerts(con, d, rules):
            if a["scope"] == "line":
                true = d in ev_days
            elif a["scope"] == "station":
                true = (a["subject"], d) in ev
            else:
                true = (station_of[a["subject"]], d) in ev or (a["subject"] == spike["defect_code"] and d == spike["date"])
            rows.append(dict(report_date=d, rule_id=a["rule_id"], scope=a["scope"], subject=a["subject"], value=round(float(a["value"]), 4),
                             baseline=round(float(a["baseline"]), 4), true_event=bool(true)))
    A = pd.DataFrame(rows)
    A.to_csv(RES_ANALYSIS / "alert_events.csv", index=False)

    perf = []
    for rid, g in A.groupby("rule_id"):
        if rid in ("R1", "R2"):
            caught = sum(bool(g[g.true_event & g.report_date.isin(w["days"]) & ((g.subject == w["station"]) | (rid == "R1"))].shape[0]) for w in wins)
            tot = len(wins)
        else:
            caught = sum(bool(g[g.true_event & g.report_date.isin(w["days"]) & (g.subject.map(station_of) == w["station"])].shape[0]) for w in wins)
            caught += int(bool(((g.subject == spike["defect_code"]) & (g.report_date == spike["date"])).any()))
            tot = len(wins) + 1
        perf.append(dict(rule_id=rid, alerts=len(g), true_alerts=int(g.true_event.sum()), false_alerts=int((~g.true_event).sum()),
                         precision=round(g.true_event.mean(), 3), events_caught=caught, events_total=tot,
                         false_dates=",".join(sorted(g[~g.true_event].report_date))))
    P = pd.DataFrame(perf)
    P.to_csv(RES_ANALYSIS / "alert_rule_performance.csv", index=False)

    dl = con.execute("SELECT strftime(report_date,'%Y-%m-%d') AS d, MIN(sent_at) AS sent FROM delivery_log WHERE message_type='alert' AND status='sent' GROUP BY 1").df().set_index("d")["sent"]
    lag = []
    for w in wins:
        first = next((d for d in w["days"] if d in set(A[A.scope.isin(["line", "station"])].report_date) and d in dl.index), None)
        start = pd.Timestamp(w["days"][0])
        if first is None:
            lag.append(dict(station=w["station"], event_start=w["days"][0], event_days=len(w["days"]), first_alert_for=None))
            continue
        sent = pd.Timestamp(dl[first])
        end_of_day = pd.Timestamp(first) + pd.Timedelta(hours=23)
        manual = pd.Timestamp(first) + pd.offsets.BDay(1) + pd.Timedelta(hours=12)
        lag.append(dict(station=w["station"], event_start=w["days"][0], event_days=len(w["days"]), first_alert_for=first,
                        days_to_detect=w["days"].index(first), alert_sent_at=str(sent),
                        hours_after_shift_end=round((sent - end_of_day).total_seconds() / 3600, 1),
                        hours_earlier_than_manual=round((manual - sent).total_seconds() / 3600, 1)))
    Lg = pd.DataFrame(lag)
    Lg.to_csv(RES_ANALYSIS / "alert_lag.csv", index=False)
    print(P.to_string(index=False)); print(Lg.to_string(index=False))


if __name__ == "__main__":
    main()
