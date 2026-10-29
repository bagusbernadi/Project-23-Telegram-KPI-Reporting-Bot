# Data

Semua data di project ini simulasi (karangan), dibuat oleh generator dengan seed tetap. Tidak ada dataset publik atau data perusahaan, jadi tidak ada masalah lisensi.

| | |
|---|---|
| Versi data | v3 |
| Tanggal dibuat | 29 Okt 2026 |
| Seed | 23260302 |
| Cara membuat ulang | `python3 code/1-data-preparation/python/01_generate_data.py` (dari folder `project/`) |
| Hasil v3 | 4.477 baris produksi mentah (111 kotor), 6.222 baris defect, 5.244 baris rework, 148 catatan kedatangan, 75 run terjadwal |

Isi `raw/` dan `clean/` tidak di-commit (lihat `.gitignore`). Jejak pembuatan (seed, commit, SHA-256 hasil) dicatat di repo `DataCenter`, folder `simulasi/`. Jika generator, seed, atau versi library berubah, hasil berubah dan versi data harus dinaikkan.

Perubahan v2 ke v3: ditambah `rework_log`, kejadian yield bertahap, dua hari data tiba siang, satu hari kosong, lonjakan satu defect, data kotor 2,5%, dan `runner_log` (menggantikan `bot_delivery_log`; log pengiriman kini dibuat oleh bot).
