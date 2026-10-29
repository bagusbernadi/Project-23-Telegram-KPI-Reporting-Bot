"""Tahap 2 / langkah 05: evaluasi aturan alert terhadap kejadian yang ditanam (Q4, Q5, Q6).

Kejadian nyata = 3 penurunan yield di ground_truth.json (jendela tanggalnya). Hari alert di luar jendela = alert palsu.
Evaluasi hanya pada hari ke-21 dst (butuh 20 hari baseline); hari tanpa data tidak dinilai.
Keluaran: results/2-analysis/{alert_eval_line.csv, alert_eval_station.csv, alert_eval_defect.csv, alert_lag.csv}
"""
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot.alerts import defect_alert, line_alert, station_alert  # noqa: E402
from common import DB_PATH, GROUND_TRUTH, RES_ANALYSIS  # noqa: E402

WINDOW = 20


def event_windows(gt):
    wins = []
    for e in gt["yield_drops"]:
        days = pd.bdate_range(e["start"], e["end"]).strftime("%Y-%m-%d").tolist()
        wins.append(dict(station=e["station"], days=days))
    return wins


def score_days(alert_dates, wins, eval_dates):
    """Skor tingkat hari dan tingkat kejadian untuk himpunan tanggal alert."""
    alert_dates = set(alert_dates) & set(eval_dates)
    ev_days = {d for w in wins for d in w["days"]}
    fp = sorted(alert_dates - ev_days)
    tp_days = sorted(alert_dates & ev_days)
    caught = [bool(alert_dates & set(w["days"])) for w in wins]
    lags = [next((i for i, d in enumerate(w["days"]) if d in alert_dates), None) for w in wins]
    return dict(alert_days=len(alert_dates), tp_days=len(tp_days), fp_days=len(fp), events_caught=sum(caught),
                precision_day=round(len(tp_days) / len(alert_dates), 3) if alert_dates else None,
                lags=lags, fp_dates=",".join(fp))


def main():
    gt = json.loads(GROUND_TRUTH.read_text())
    wins = event_windows(gt)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    line = con.execute("SELECT strftime(date, '%Y-%m-%d') AS date, line_yield FROM v_line_daily ORDER BY date").df()
    st = con.execute("SELECT strftime(date, '%Y-%m-%d') AS date, station, fpy FROM v_station_daily ORDER BY date, seq").df()
    dd = con.execute("SELECT strftime(date, '%Y-%m-%d') AS date, station, defect_code, qty FROM v_defect_daily").df()
    eval_dates = line["date"].iloc[WINDOW:].tolist()

    # --- Q4: ambang yield lini
    rows = []
    for method, grid in [("fixed", [0.80, 0.82, 0.84, 0.85, 0.86, 0.855, 0.865, 0.87]), ("rolling_sigma", [1.5, 2.0, 2.5, 3.0, 3.5, 4.0])]:
        for p in grid:
            a = line_alert(line, method, p, WINDOW)
            r = score_days(line.loc[a, "date"], wins, eval_dates)
            rows.append(dict(rule="line_" + method, param=p, **r))
    L = pd.DataFrame(rows)
    # --- stasiun
    rows = []
    for method, grid in [("fixed", [0.93, 0.95, 0.96]), ("rolling_sigma", [2.0, 2.5, 3.0, 3.5, 4.0, 5.0])]:
        for p in grid:
            a = station_alert(st, method, p, WINDOW)
            hit = a[a["alert"]]
            dates = hit["date"].unique()
            # alert stasiun benar hanya jika stasiunnya sama dengan stasiun kejadian
            ev = {(w["station"], d) for w in wins for d in w["days"]}
            tp_pairs = {(r.station, r.date) for r in hit.itertuples() if (r.station, r.date) in ev}
            fp_pairs = {(r.station, r.date) for r in hit.itertuples() if (r.station, r.date) not in ev and r.date in set(eval_dates)}
            caught = [any((w["station"], d) in tp_pairs for d in w["days"]) for w in wins]
            r = score_days(dates, wins, eval_dates)
            r.update(tp_days=len(tp_pairs), fp_days=len(fp_pairs), events_caught=sum(caught),
                     alert_days=len(tp_pairs) + len(fp_pairs),
                     precision_day=round(len(tp_pairs) / max(1, len(tp_pairs) + len(fp_pairs)), 3),
                     fp_dates=",".join(sorted(f"{s}@{d}" for s, d in fp_pairs)))
            rows.append(dict(rule="station_" + method, param=p, **r))
    S = pd.DataFrame(rows)

    # --- Q6: lonjakan defect. Benar jika kode defect berada di stasiun kejadian pada jendelanya, atau kode spike pada harinya.
    spike = gt["defect_spike"]
    grid_days = pd.MultiIndex.from_product([line["date"], sorted(dd.defect_code.unique())], names=["date", "defect_code"])
    full = dd.set_index(["date", "defect_code"])["qty"].reindex(grid_days, fill_value=0).reset_index()
    code_station = dd.drop_duplicates("defect_code").set_index("defect_code")["station"].to_dict()
    ev_pairs = {(w["station"], d) for w in wins for d in w["days"]}
    all_dates = line["date"].tolist()
    rows = []
    for method, grid in [("pct", [0.5, 1.0, 2.0]), ("sigma", [3.0, 4.0, 5.0]), ("poisson", [3.0, 4.0, 5.0, 6.0])]:
        for w in (7, 20):
            for p in grid:
                for mc in (0, 5):
                    a = defect_alert(full, method, p, mc, w)
                    a = a[a["alert"]]
                    warm = a[a["date"].isin(all_dates[w:WINDOW])]          # masa pemanasan: tidak ada kejadian nyata -> semua palsu
                    a = a[a["date"].isin(eval_dates)]
                    def truth(r):
                        return (r.defect_code == spike["defect_code"] and r.date == spike["date"]) or (code_station[r.defect_code], r.date) in ev_pairs
                    a = a.assign(true=[truth(r) for r in a.itertuples()])
                    tp, fp = int(a["true"].sum()), int((~a["true"]).sum())
                    spike_caught = bool(((a.defect_code == spike["defect_code"]) & (a.date == spike["date"])).any())
                    caught = sum(bool(a[a["true"] & a.date.isin(w_["days"]) & (a.defect_code.map(code_station) == w_["station"])].shape[0]) for w_ in wins)
                    rows.append(dict(rule="defect_" + method, window=w, param=p, min_count=mc, alerts=len(a), true_alerts=tp, false_alerts=fp,
                                     false_alerts_warmup=len(warm), precision=round(tp / len(a), 3) if len(a) else None,
                                     spike_caught=spike_caught, drops_caught=caught))
    D = pd.DataFrame(rows)

    L.drop(columns=["lags"]).to_csv(RES_ANALYSIS / "alert_eval_line.csv", index=False)
    S.drop(columns=["lags"]).to_csv(RES_ANALYSIS / "alert_eval_station.csv", index=False)
    D.to_csv(RES_ANALYSIS / "alert_eval_defect.csv", index=False)
    print(L.drop(columns=["fp_dates"]).to_string()); print(S.drop(columns=["lags", "fp_dates"]).to_string()); print(D.to_string())


if __name__ == "__main__":
    main()
