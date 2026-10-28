[← Back to portfolio](https://bagusbernadi.github.io/)

# Project 23: Telegram Bot Automated KPI Reporting

**Status: Design (rancangan).**

**Tujuan:** Membangun pipeline yang setiap pagi menghitung KPI produksi (yield, NG rate, rework rate per stasiun) lalu mengirim ringkasan dan grafiknya ke Telegram, serta mengirim alert saat yield turun di bawah ambang, sehingga supervisor tahu kondisi lini tanpa menunggu laporan manual.


| | |
|---|---|
| Kategori | Manufaktur (perakitan sepeda motor) |
| Tingkat | Sulit |
| Data | Simulasi: data produksi 10 stasiun, 3 model (struktur sama dengan Project 3) + log pengiriman bot |
| Tools | Python (pandas, matplotlib, python-telegram-bot), DuckDB + SQL, GitHub Actions, Streamlit |

## 1. Problem
Bagaimana mengirim ringkasan KPI harian (yield, NG rate, rework rate per stasiun) beserta grafik ke Telegram secara otomatis, dengan alert yang menangkap masalah nyata tanpa terlalu banyak alarm palsu?

## 2. Data
Data produksi simulasi dibuat oleh `scripts/generate_data.py` (seed tetap). Perkiraan ±4.500 baris produksi harian. Tiga kejadian penurunan yield, data terlambat, dan data kosong sengaja ditanam untuk menguji alert. Pesan hanya dikirim ke grup demo.

Versi data: v1. Tanggal dibuat: 28 Okt 2026. Seed: 23260302. Generator: `scripts/generate_data.py`. Hasil v1: 4.440 baris produksi, 6.584 baris defect.

## 3. Analysis
Rencana: KPI harian per stasiun, Pareto defect, evaluasi ambang alert (precision dan recall), on-time delivery bot. Belum dikerjakan.

## 4. Recommendation
Belum dikerjakan.

## 5. Impact
Belum dikerjakan. Angka dampak akan diberi label `estimated` / `simulated`.

## Batasan yang sudah diketahui
- Alert dicek sekali sehari, belum real-time.
- Jadwal GitHub Actions bisa tertunda beberapa menit.
- Data perusahaan di aplikasi chat perlu izin; project ini hanya memakai data simulasi.

## Struktur repository (rencana)
```
docs/            # definisi KPI, isi pesan, screenshot
config/          # aturan alert
scripts/         # generator data simulasi
bot/             # laporan harian, alert, perintah
.github/workflows/  # jadwal harian
notebooks/       # evaluasi alert
dashboard/       # dashboard pendamping
index.html       # halaman rancangan (GitHub Pages)
README.md
```
