"""Tahap 1 / langkah 02: deteksi dan perbaiki data kotor, bandingkan dengan ground truth, tulis data bersih.

Aturan (urutan penting):
  1. baris ganda pada kunci (date, shift, station, model): simpan baris pertama (semua ganda terbukti identik),
  2. ng_qty negatif: pulihkan ng = input - ok,
  3. ok + ng > input: pulihkan ok = input - ng.
Keluaran: data/clean/*.csv; results/1-data-preparation/{dirty_detection.csv, clean_checks.csv, data_gaps.csv}
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import CLEAN_DIR, RAW_DIR, RES_PREP, STATIONS  # noqa: E402

KEY = ["date", "shift", "station", "model"]


def main():
    prod = pd.read_csv(RAW_DIR / "production_daily.csv")
    dlog = pd.read_csv(RAW_DIR / "defect_log.csv")
    rework = pd.read_csv(RAW_DIR / "rework_log.csv")
    arrival = pd.read_csv(RAW_DIR / "data_arrival_log.csv")
    truth = pd.read_csv(RAW_DIR / "ground_truth_dirty.csv")
    n_raw = len(prod)

    # 1. ganda
    dup_mask = prod.duplicated(KEY, keep="first")
    dup_all = prod[prod.duplicated(KEY, keep=False)]
    identical = bool((dup_all.groupby(KEY).nunique().max() <= 1).all())
    found = [(f"{r.date}|{r.shift}|{r.station}|{r.model}", "duplikat") for r in prod[dup_mask].itertuples()]
    prod = prod[~dup_mask].reset_index(drop=True)
    # 2. ng negatif
    neg = prod["ng_qty"] < 0
    found += [(f"{r.date}|{r.shift}|{r.station}|{r.model}", "ng_negatif") for r in prod[neg].itertuples()]
    prod.loc[neg, "ng_qty"] = prod.loc[neg, "input_qty"] - prod.loc[neg, "ok_first_pass"]
    # 3. ok + ng > input
    over = (prod["ok_first_pass"] + prod["ng_qty"]) > prod["input_qty"]
    found += [(f"{r.date}|{r.shift}|{r.station}|{r.model}", "ok_ng_melebihi_input") for r in prod[over].itertuples()]
    prod.loc[over, "ok_first_pass"] = prod.loc[over, "input_qty"] - prod.loc[over, "ng_qty"]

    found = pd.DataFrame(found, columns=["row_key", "kind"])
    rows = []
    for kind in ["duplikat", "ng_negatif", "ok_ng_melebihi_input"]:
        t = set(truth.loc[truth.kind == kind, "row_key"])
        f = set(found.loc[found.kind == kind, "row_key"])
        tp = len(t & f)
        rows.append([kind, len(t), len(f), tp, len(f - t), len(t - f),
                     round(tp / len(f), 4) if f else None, round(tp / len(t), 4) if t else None])
    det = pd.DataFrame(rows, columns=["kind", "ground_truth", "detected", "true_positive", "false_positive",
                                      "missed", "precision", "recall"])
    det.to_csv(RES_PREP / "dirty_detection.csv", index=False)

    # pemeriksaan konsistensi setelah dibersihkan
    ds = dlog.groupby(KEY)["qty"].sum().rename("defect_qty")
    chk = prod.set_index(KEY).join(ds).fillna({"defect_qty": 0})
    p = prod.copy()
    p["seq"] = p["station"].map({s: i for i, s in enumerate(STATIONS)})
    p = p.sort_values(["date", "shift", "model", "seq"])
    nxt_in = p.groupby(["date", "shift", "model"])["input_qty"].shift(-1)
    flow_ok = ((p["ok_first_pass"] == nxt_in) | nxt_in.isna()).all()
    rw_ok = bool((pd.to_datetime(rework.date_out) >= pd.to_datetime(rework.date_in)).all())
    checks = pd.DataFrame([
        ["baris mentah", n_raw, ""],
        ["baris ganda dibuang", int(dup_mask.sum()), "kunci date-shift-station-model"],
        ["semua ganda identik", int(identical), "1 = ya"],
        ["ng negatif dipulihkan", int(neg.sum()), "ng = input - ok"],
        ["ok+ng melebihi input dipulihkan", int(over.sum()), "ok = input - ng"],
        ["baris bersih", len(prod), ""],
        ["persen baris kotor dari mentah", round(100 * len(found) / n_raw, 2), "target 2-3%"],
        ["ng_qty == jumlah defect_log", int((chk["ng_qty"] == chk["defect_qty"]).all()), "1 = ya, semua baris"],
        ["input stasiun berikut == ok stasiun sebelumnya", int(bool(flow_ok)), "1 = ya"],
        ["rework date_out >= date_in", int(rw_ok), "1 = ya"],
        ["ok + ng == input", int(((prod.ok_first_pass + prod.ng_qty) == prod.input_qty).all()), "1 = ya"],
        ["tidak ada nilai negatif", int((prod[["input_qty", "ok_first_pass", "ng_qty"]] >= 0).all().all()), "1 = ya"],
    ], columns=["check", "value", "note"])
    checks.to_csv(RES_PREP / "clean_checks.csv", index=False)

    # celah data per hari kerja: hari tanpa baris, kedatangan data
    days = pd.bdate_range(prod["date"].min(), prod["date"].max()).strftime("%Y-%m-%d")
    have = set(prod["date"])
    gap = pd.DataFrame({"date": days})
    gap["has_production"] = gap["date"].isin(have).astype(int)
    a = arrival.groupby("date")["arrived_at_next_day"].max().rename("last_arrival")
    gap = gap.merge(a, on="date", how="left")
    gap["arrival_minutes"] = gap["last_arrival"].map(lambda s: int(s[:2]) * 60 + int(s[3:]) if isinstance(s, str) else None)
    gap.to_csv(RES_PREP / "data_gaps.csv", index=False)

    prod.to_csv(CLEAN_DIR / "production_daily.csv", index=False)
    for name, df in [("defect_log", dlog), ("rework_log", rework), ("data_arrival_log", arrival)]:
        df.to_csv(CLEAN_DIR / f"{name}.csv", index=False)
    for name in ["dim_defect", "dim_station", "runner_log"]:
        pd.read_csv(RAW_DIR / f"{name}.csv").to_csv(CLEAN_DIR / f"{name}.csv", index=False)
    print(det.to_string(index=False))
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
