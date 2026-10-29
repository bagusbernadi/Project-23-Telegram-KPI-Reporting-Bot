"""Tahap 1 / langkah 01: bangkitkan data simulasi lini perakitan sepeda motor (v3). Seed tetap.

Keluaran (data/raw/): production_daily.csv (sudah dikotori 2-3%), defect_log.csv, rework_log.csv,
data_arrival_log.csv, runner_log.csv, dim_defect.csv, dim_station.csv, ground_truth.json,
ground_truth_dirty.csv. Kejadian tertanam untuk menguji alert:
  - 3 penurunan yield (2 hari Engine Assembly, 1 hari Frame Painting, ±1 minggu turun perlahan di Performance Test),
  - 2 hari data tiba siang, 1 hari data kosong penuh,
  - 1 lonjakan satu kode defect (WRH-02) yang tidak menggeser yield lini,
  - 3 hari runner GitHub Actions gagal.
Jalankan dari folder project/: python3 code/1-data-preparation/python/01_generate_data.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import (DATA_VERSION, N_DAYS, RAW_DIR as OUT, SEED, SHIFTS, START_DATE, STATIONS, MODELS)  # noqa: E402

# kode defect: (kode, nama, indeks stasiun, kategori, bobot di stasiun)
DEFECTS = [
    ("FWD-01", "Porositas las", 0, "Las", 0.55),
    ("FWD-02", "Dimensi frame meleset", 0, "Las", 0.45),
    ("PNT-01", "Cat tipis", 1, "Cat", 0.45),
    ("PNT-02", "Cat berkulit jeruk", 1, "Cat", 0.35),
    ("PNT-03", "Debu pada cat", 1, "Cat", 0.20),
    ("ENG-01", "Torsi baut kurang", 2, "Mesin", 0.50),
    ("ENG-02", "Rembes oli", 2, "Mesin", 0.50),
    ("WRH-01", "Konektor tidak masuk penuh", 3, "Kelistrikan", 0.60),
    ("WRH-02", "Kabel terjepit", 3, "Kelistrikan", 0.40),
    ("WHL-01", "Velg oleng", 4, "Roda", 0.50),
    ("WHL-02", "Suspensi bocor", 4, "Roda", 0.50),
    ("BDY-01", "Gores panel body", 5, "Body", 0.55),
    ("BDY-02", "Celah panel tidak rata", 5, "Body", 0.45),
    ("ELT-01", "Lampu tidak menyala", 6, "Kelistrikan", 0.45),
    ("ELT-02", "Starter gagal", 6, "Kelistrikan", 0.55),
    ("FIN-01", "Cacat kosmetik", 7, "Kosmetik", 0.60),
    ("FIN-02", "Stiker salah", 7, "Kosmetik", 0.40),
    ("DYN-01", "Akselerasi di bawah spec", 8, "Performa", 0.50),
    ("DYN-02", "Rem tidak sesuai tes", 8, "Performa", 0.50),
    ("PKG-01", "Label atau kemasan rusak", 9, "Label", 1.00),
]
BASE_NG = [0.014, 0.040, 0.013, 0.011, 0.012, 0.015, 0.018, 0.010, 0.016, 0.003]
MODEL_FACTOR = {"Matic 110": 0.85, "Bebek 125": 1.00, "Sport 150": 1.25}
START_QTY = {"Matic 110": 300, "Bebek 125": 240, "Sport 150": 150}
OPERATOR = {(s, sh): f"OP{2 * s + j + 1:02d}" for s in range(len(STATIONS)) for j, sh in enumerate(SHIFTS)}
DATES = pd.bdate_range(START_DATE, periods=N_DAYS)
NG_SCALE = 0.82
REWORK_SHARE = 0.60            # porsi NG yang masuk rework; sisanya scrap

# kejadian yield: (stasiun, hari mulai, panjang hari, pengali puncak, ramp) ramp=True: naik perlahan
DROPS = [(2, 20, 2, 3.4, False), (1, 45, 1, 3.0, False), (8, 62, 7, 2.6, True)]
LATE_DAYS = [15, 51]                 # data tiba siang (12:00-13:30) pada pagi berikutnya
EMPTY_DAY = 33                       # tidak ada baris sama sekali (dua shift)
SPIKE = dict(day=38, code="WRH-02", weight_mult=9.0, station_mult=1.5)
RUNNER_FAIL = [22, 47, 66]


def extra(t, s, m, sh):
    f = 1.0
    for st, t0, n, peak, ramp in DROPS:
        if s == st and t0 <= t < t0 + n:
            f *= 1 + (peak - 1) * ((t - t0 + 1) / n if ramp else 1)
    if t == SPIKE["day"] and s == 3:
        f *= SPIKE["station_mult"]
    return f


def make_production(rng):
    """Satu baris per tanggal x shift x model x stasiun. Hasil: (prod, defect_log) bersih sebelum dikotori."""
    by_station = {s: [d for d in DEFECTS if d[2] == s] for s in range(len(STATIONS))}
    prod, dlog = [], []
    for t, day in enumerate(DATES):
        noise = np.exp(rng.normal(0, 0.15, len(STATIONS)))
        for m in MODELS:
            for sh in SHIFTS:
                qty = int(round(START_QTY[m] * rng.normal(1, 0.05)))
                for s, st in enumerate(STATIONS):
                    p = BASE_NG[s] * MODEL_FACTOR[m] * noise[s] * NG_SCALE * extra(t, s, m, sh)
                    ng = int(rng.binomial(qty, min(p, 0.5)))
                    cds = by_station[s]
                    w = np.array([c[4] * (SPIKE["weight_mult"] if (t == SPIKE["day"] and c[0] == SPIKE["code"]) else 1.0) for c in cds])
                    split = rng.multinomial(ng, w / w.sum())
                    prod.append([day.date(), sh, st, m, OPERATOR[(s, sh)], qty, qty - ng, ng])
                    for c, q in zip(cds, split):
                        if q:
                            dlog.append([day.date(), sh, st, m, c[0], int(q)])
                    qty -= ng
    cols = ["date", "shift", "station", "model", "operator_id", "input_qty", "ok_first_pass", "ng_qty"]
    return pd.DataFrame(prod, columns=cols), pd.DataFrame(dlog, columns=["date", "shift", "station", "model", "defect_code", "qty"])


def make_rework(rng, dlog):
    rows = []
    for i, r in enumerate(dlog.itertuples(index=False), 1):
        n_re = int(rng.binomial(r.qty, REWORK_SHARE))
        if n_re == 0:
            continue
        lag = int(rng.choice([0, 1, 1, 2]))
        d_in = pd.Timestamp(r.date)
        d_out = (d_in + pd.offsets.BDay(lag)).date() if lag else d_in.date()
        ok = int(rng.binomial(n_re, 0.88))
        for res, q in (("lulus", ok), ("scrap", n_re - ok)):
            if q:
                rows.append([d_in.date(), d_out, r.station, r.defect_code, q, res])
    out = pd.DataFrame(rows, columns=["date_in", "date_out", "station_origin", "defect_code", "qty", "result"])
    out.insert(0, "rework_id", [f"RW{i:05d}" for i in range(1, len(out) + 1)])
    return out


def dirty(rng, prod):
    """Kotori ±2,5% baris: ng negatif, ok+ng > input, duplikat persis. Kembalikan (prod_kotor, daftar_kotor)."""
    n = len(prod)
    k = int(round(n * 0.025))
    idx = rng.choice(n, size=k, replace=False)
    kinds = np.array(["ng_negatif"] * (k // 3) + ["ok_ng_melebihi_input"] * (k // 3) + ["duplikat"] * (k - 2 * (k // 3)))
    prod = prod.copy()
    dups, truth = [], []
    for i, kind in zip(idx, kinds):
        key = f"{prod.at[i,'date']}|{prod.at[i,'shift']}|{prod.at[i,'station']}|{prod.at[i,'model']}"
        if kind == "ng_negatif":
            prod.at[i, "ng_qty"] = -abs(int(prod.at[i, "ng_qty"])) - 1
        elif kind == "ok_ng_melebihi_input":
            prod.at[i, "ok_first_pass"] = int(prod.at[i, "input_qty"]) + int(rng.integers(5, 40))
        else:
            dups.append(prod.loc[i])
        truth.append([key, kind])
    if dups:
        prod = pd.concat([prod, pd.DataFrame(dups)], ignore_index=True)
    return prod, pd.DataFrame(truth, columns=["row_key", "kind"])


def main():
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    prod, dlog = make_production(rng)
    dead = {DATES[EMPTY_DAY].date()}
    prod = prod[~prod["date"].isin(dead)].reset_index(drop=True)
    dlog = dlog[~dlog["date"].isin(dead)].reset_index(drop=True)
    rework = make_rework(rng, dlog)
    prod, dirty_truth = dirty(rng, prod)

    late = {DATES[t].date() for t in LATE_DAYS}
    arr = []
    for day in DATES:
        if day.date() in dead:
            continue
        for sh in SHIFTS:
            minutes = int(rng.integers(330, 371))
            if day.date() in late:
                minutes = int(rng.integers(720, 811))
            arr.append([day.date(), sh, f"{minutes // 60:02d}:{minutes % 60:02d}"])
    arrival = pd.DataFrame(arr, columns=["date", "shift", "arrived_at_next_day"])

    runner = []
    for i, day in enumerate(DATES):
        delay = int(rng.integers(0, 12))
        runner.append([day.date(), "07:00", f"07:{delay:02d}", "failed" if i in RUNNER_FAIL else "success"])
    pd.DataFrame(runner, columns=["date", "scheduled_at", "started_at", "status"]).to_csv(OUT / "runner_log.csv", index=False)

    prod.to_csv(OUT / "production_daily.csv", index=False)
    dlog.to_csv(OUT / "defect_log.csv", index=False)
    rework.to_csv(OUT / "rework_log.csv", index=False)
    arrival.to_csv(OUT / "data_arrival_log.csv", index=False)
    dirty_truth.to_csv(OUT / "ground_truth_dirty.csv", index=False)
    pd.DataFrame([(d[0], d[1], STATIONS[d[2]], d[3]) for d in DEFECTS],
                 columns=["defect_code", "defect_name", "station", "category"]).to_csv(OUT / "dim_defect.csv", index=False)
    pd.DataFrame({"station": STATIONS, "seq": range(1, len(STATIONS) + 1)}).to_csv(OUT / "dim_station.csv", index=False)
    gt = {"seed": SEED, "version": DATA_VERSION, "start_date": START_DATE, "n_days": N_DAYS,
          "yield_drops": [{"station": STATIONS[s], "start": str(DATES[t0].date()), "end": str(DATES[t0 + n - 1].date()),
                           "peak_factor": f, "gradual": r} for s, t0, n, f, r in DROPS],
          "late_data": [{"date": str(DATES[t].date()), "note": "data tiba 12:00-13:30"} for t in LATE_DAYS],
          "empty_data": [{"date": str(DATES[EMPTY_DAY].date()), "note": "tidak ada baris dua shift"}],
          "defect_spike": {"date": str(DATES[SPIKE["day"]].date()), "defect_code": SPIKE["code"]},
          "runner_failed_days": [str(DATES[i].date()) for i in RUNNER_FAIL],
          "dirty_rows": int(len(dirty_truth)), "dirty_kinds": dirty_truth["kind"].value_counts().to_dict()}
    (OUT / "ground_truth.json").write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"production {len(prod)} baris (kotor {len(dirty_truth)}), defect {len(dlog)}, rework {len(rework)}, kedatangan {len(arrival)}")


if __name__ == "__main__":
    main()
