"""Tahap 3 / langkah 13: buat README.md di root repo; semua angka dibaca dari CSV hasil."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import ROOT, result  # noqa: E402

R = lambda n: pd.read_csv(result(n))
f = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")
n = lambda v: f"{int(round(v)):,}".replace(",", ".")

dq, chk = R("dirty_detection.csv"), R("clean_checks.csv").set_index("check")["value"]
sp, par, lag = R("kpi_station_period.csv"), R("pareto_period.csv"), R("alert_lag.csv")
perf, ev = R("alert_rule_performance.csv").set_index("rule_id"), R("alert_eval_line.csv")
ds = R("delivery_summary.csv").set_index("metric")["value"]
cx, sc, ct, sec = R("crosscheck.csv"), R("scenario_tests.csv"), R("command_tests.csv"), R("secret_scan.csv").set_index("check")["value"]
imp = R("impact_time.csv").set_index("item")["value"]
line = R("kpi_line_daily.csv")
w = sp.sort_values("fpy").iloc[0]
fp_fix = ev[(ev.rule == "line_fixed") & (ev.param == 0.865)].iloc[0]
pct50 = R("alert_eval_defect.csv").query("rule == 'defect_pct' and param == 0.5 and window == 20 and min_count == 5").iloc[0]
ok_cx = int(cx[["line_pass", "worst_pass", "top_pass"]].all(axis=1).sum())

md = f"""[← Back to portfolio](https://bagusbernadi.github.io/)

# Project 23: Telegram Bot Automated KPI Reporting

**Status: Selesai di branch `project-23-build` (menunggu review sebelum digabung ke `main`).**

Halaman rancangan dan Report: https://bagusbernadi.github.io/project-23-telegram-kpi-reporting-bot/

| | |
|---|---|
| Kategori | Manufaktur (perakitan sepeda motor) |
| Tingkat | Sulit |
| Data | Data simulasi buatan sendiri: 10 stasiun, 3 model, 2 shift, 75 hari kerja (struktur tabel seperti Project 3) |
| Tools | Python (pandas, matplotlib), DuckDB + SQL, GitHub Actions (workflow, belum dijalankan), Streamlit + Plotly, Excel (cek silang), Jupyter |

## 1. Problem

Bagaimana mengirim ringkasan KPI harian (yield, NG rate, rework rate per stasiun) beserta grafik ke Telegram secara otomatis, dengan alert yang menangkap masalah nyata tanpa terlalu banyak alarm palsu? Dipecah menjadi 12 pertanyaan (8 prioritas utama); jawabannya ada di tab Report pada halaman project.

## 2. Data

- Data simulasi dengan seed tetap (`project/code/1-data-preparation/python/01_generate_data.py`), v3. Kejadian yang ditanam: 3 penurunan yield, 2 hari data terlambat, 1 hari data kosong, 1 lonjakan satu defect, {f(chk['persen baris kotor dari mentah'], 1)}% baris kotor.
- {n(chk['baris mentah'])} baris produksi mentah menjadi {n(chk['baris bersih'])} bersih; semua {n(dq.detected.sum())} baris kotor ditemukan (presisi dan recall {f(dq.recall.min() * 100, 0)}%). Detail: `project/docs/cleaning_log.md`.
- Pengiriman ke Telegram **tidak dilakukan sungguhan**: bot dijalankan dalam mode dry-run. Jeda dan kegagalan run terjadwal adalah simulasi (`runner_log`).

## 3. Analysis

- Yield lini rata-rata {f(line.good_qty.sum() / line.start_qty.sum() * 100, 1)}%. Stasiun yield terendah: {w.station} ({f(w.fpy * 100, 1)}%), penyumbang {f(w.share_of_line_ng * 100, 0)}% dari semua NG.
- Aturan alert terpilih (`project/config/alert_rules.yaml`): R1 yield lini < rata-rata 20 hari − 2σ, R2 yield stasiun < rata-rata − 3,5σ, R3 lonjakan defect (Poisson, 20 hari). Pada replay: R1 {n(perf.loc['R1'].true_alerts)} dari {n(perf.loc['R1'].alerts)} alert benar, R2 {n(perf.loc['R2'].true_alerts)} dari {n(perf.loc['R2'].alerts)}, R3 {n(perf.loc['R3'].true_alerts)} dari {n(perf.loc['R3'].alerts)}; ketiga penurunan yield tertangkap.
- Ambang tetap yield lini 86,5% menangkap ketiga penurunan tetapi dengan {n(fp_fix.fp_days)} alert palsu; aturan "naik > 50%" untuk defect menghasilkan {n(pct50.false_alerts)} alert palsu dari {n(pct50.alerts)} alert (`alert_eval_defect.csv`).
- Penurunan perlahan di Performance Test (Dyno) baru terdeteksi hari ke-{n(lag.days_to_detect.max() + 1)} dari 7 hari kejadian; dua penurunan mendadak terdeteksi di hari pertama.
- On-time delivery bot (data sudah ada saat run 07:00): {f(ds['on-time delivery rate bot (data sudah ada)'], 1)}%. Ujung ke ujung termasuk 2 hari data tiba siang: {f(ds['on-time rate ujung ke ujung (hari dengan data tiba)'], 1)}%.
- Cek silang pesan bot vs SQL vs Excel: {ok_cx} dari {len(cx)} tanggal sampel lulus. {int((sc.result == 'lulus').sum())} dari {len(sc)} skenario dan {int((ct.result == 'lulus').sum())} dari {len(ct)} uji perintah lulus. Token di repositori: {int(sec['berkas terlacak yang memuat pola token'])} berkas, {int(sec['pola token di riwayat git (semua cabang)'])} di riwayat git.

## 4. Recommendation

Pakai R1 dan R2 sebagai alert utama dan R3 sebagai informasi tambahan; jangan memakai ambang tetap atau aturan persentase. Kirim pesan `no_data` saat data belum masuk dan cek ulang tiap jam sampai 14:00. Sebelum dipakai nyata: uji kirim ke grup Telegram sungguhan dan jalankan workflow di GitHub Actions.

## 5. Impact

Estimated: waktu manual {n(imp['waktu manual per laporan (menit)'])} menit per laporan (asumsi, tidak diukur) digantikan pipeline otomatis ({f(imp['waktu otomatis per laporan (detik)'], 1)} detik, terukur) ditambah {n(imp['waktu baca pesan bot (menit)'])} menit membaca pesan: sekitar {f(imp['jam kerja dihemat per tahun'], 0)} jam kerja per tahun. Belum dalam rupiah.

## Batasan

- Data simulasi; hasil membuktikan metode, bukan kondisi pabrik. Evaluasi alert memakai 3 kejadian dan data yang sama dengan pemilihan parameter (in-sample).
- Bot belum pernah mengirim ke Telegram sungguhan; kode `TelegramSender` hanya diuji dengan transport palsu. Workflow GitHub Actions belum dijalankan; dashboard belum di-deploy.
- Alert dicek sekali sehari, bukan real-time. Alert menunjukkan kapan yield turun, bukan penyebabnya.
- Waktu manual per laporan adalah estimasi. Cek silang Excel dihitung ulang oleh LibreOffice, bukan Microsoft Excel.

## Menjalankan

```
pip install -r project/requirements.txt
cd project
python -m pytest tests -q
cd code/1-data-preparation/python && python 01_generate_data.py && python 02_clean_data.py && python 03_build_db.py
cd ../../2-analysis/python && for s in 04 05 06 07 08 09 10; do python ${{s}}_*.py; done
cd ../../3-presentation/python && for s in 11 12 13; do python ${{s}}_*.py; done
streamlit run ../streamlit/app.py
python design-and-report/src/build_report.py   # dari root repo
```

Pakai bot sungguhan: isi secrets `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` di GitHub (jangan di kode), lalu jalankan workflow `.github/workflows/daily.yml`.

## Struktur repository

```
index.html                 Pengalihan ke design-and-report/
design-and-report/         Halaman Design dan Report (src/ berisi generator)
.github/workflows/         Jadwal harian (daily.yml)
project/
  code/1-data-preparation  Generator, cleaning, database (python, sql)
  code/2-analysis          KPI, evaluasi alert, bot (python/bot), cek silang, dampak
  code/3-presentation      Data dashboard, notebook, README, Streamlit
  config/                  Aturan alert (alert_rules.yaml)
  results/                 CSV hasil per tahap, crosscheck.xlsx, notebook
  docs/                    KPI dan pesan, kamus data, log cleaning, contoh pesan
  tests/                   pytest
  data/                    README (data mentah dan bersih tidak di-commit)
```
"""
(ROOT.parent / "README.md").write_text(md, encoding="utf-8")
print("README.md ditulis")
