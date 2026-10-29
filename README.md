[← Back to portfolio](https://bagusbernadi.github.io/)

# Project 23: Telegram Bot Automated KPI Reporting

**Status: Selesai di branch `project-23-build` (menunggu review sebelum digabung ke `main`).**

Halaman rancangan dan Report: https://bagusbernadi.github.io/Project-23-Telegram-KPI-Reporting-Bot/

| | |
|---|---|
| Kategori | Manufaktur (perakitan sepeda motor) |
| Tingkat | Sulit |
| Data | Data simulasi buatan sendiri: 10 stasiun, 3 model, 2 shift, 75 hari kerja (struktur tabel seperti Project 3) |
| Tools | Python (pandas, matplotlib), DuckDB + SQL, GitHub Actions (workflow, belum dijalankan), Streamlit + Plotly, Excel (cek silang), Jupyter |

## 1. Problem

Bagaimana mengirim ringkasan KPI harian (yield, NG rate, rework rate per stasiun) beserta grafik ke Telegram secara otomatis, dengan alert yang menangkap masalah nyata tanpa terlalu banyak alarm palsu? Dipecah menjadi 12 pertanyaan (8 prioritas utama); jawabannya ada di tab Report pada halaman project.

## 2. Data

- Data simulasi dengan seed tetap (`project/code/1-data-preparation/python/01_generate_data.py`), v3. Kejadian yang ditanam: 3 penurunan yield, 2 hari data terlambat, 1 hari data kosong, 1 lonjakan satu defect, 2,5% baris kotor.
- 4.477 baris produksi mentah menjadi 4.440 bersih; semua 111 baris kotor ditemukan (presisi dan recall 100%). Detail: `project/docs/cleaning_log.md`.
- Pengiriman ke Telegram **tidak dilakukan sungguhan**: bot dijalankan dalam mode dry-run. Jeda dan kegagalan run terjadwal adalah simulasi (`runner_log`).

## 3. Analysis

- Yield lini rata-rata 87,7%. Stasiun yield terendah: Frame Painting (96,6%), penyumbang 28% dari semua NG.
- Aturan alert terpilih (`project/config/alert_rules.yaml`): R1 yield lini < rata-rata 20 hari − 2σ, R2 yield stasiun < rata-rata − 3,5σ, R3 lonjakan defect (Poisson, 20 hari). Pada replay: R1 3 dari 3 alert benar, R2 3 dari 3, R3 11 dari 12; ketiga penurunan yield tertangkap.
- Ambang tetap yield lini 86,5% menangkap ketiga penurunan tetapi dengan 5 alert palsu; aturan "naik > 50%" untuk defect menghasilkan 124 alert palsu dari 143 alert (`alert_eval_defect.csv`).
- Penurunan perlahan di Performance Test (Dyno) baru terdeteksi hari ke-5 dari 7 hari kejadian; dua penurunan mendadak terdeteksi di hari pertama.
- On-time delivery bot (data sudah ada saat run 07:00): 95,8%. Ujung ke ujung termasuk 2 hari data tiba siang: 93,2%.
- Cek silang pesan bot vs SQL vs Excel: 12 dari 12 tanggal sampel lulus. 8 dari 8 skenario dan 9 dari 9 uji perintah lulus. Token di repositori: 0 berkas, 0 di riwayat git.

## 4. Recommendation

Pakai R1 dan R2 sebagai alert utama dan R3 sebagai informasi tambahan; jangan memakai ambang tetap atau aturan persentase. Kirim pesan `no_data` saat data belum masuk dan cek ulang tiap jam sampai 14:00. Sebelum dipakai nyata: uji kirim ke grup Telegram sungguhan dan jalankan workflow di GitHub Actions.

## 5. Impact

Estimated: waktu manual 30 menit per laporan (asumsi, tidak diukur) digantikan pipeline otomatis (0,5 detik, terukur) ditambah 2 menit membaca pesan: sekitar 114 jam kerja per tahun. Belum dalam rupiah.

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
cd ../../2-analysis/python && for s in 04 05 06 07 08 09 10; do python ${s}_*.py; done
cd ../../3-presentation/python && for s in 11 12 13; do python ${s}_*.py; done
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
