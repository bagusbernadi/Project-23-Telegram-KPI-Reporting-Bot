# Definisi KPI, isi pesan, dan perintah bot

Semua KPI dihitung di view DuckDB (`code/1-data-preparation/sql/01_views.sql`); bot, dashboard, dan cek silang memakai view yang sama.

| KPI | Rumus | View |
|---|---|---|
| Yield stasiun (FPY) | `ok_first_pass / input_qty` per stasiun, semua model dan shift pada hari itu | `v_station_daily` |
| NG rate stasiun | `1 - FPY` | `v_station_daily` |
| Yield lini | unit OK di Packing ÷ unit masuk Frame Welding | `v_line_daily` |
| Rework rate | unit masuk rework (menurut `date_in`, `station_origin`) ÷ `input_qty` stasiun; lini: total rework ÷ unit masuk lini | `v_kpi_station_daily` |
| Scrap | unit rework dengan `result = 'scrap'` | `v_rework_station_daily` |
| Top NG | jumlah `qty` per nama defect, hari itu dan 7 hari kerja berdata terakhir | `v_defect_daily` |
| On-time delivery | laporan harian terkirim paling lambat 07:15 (asumsi) | `delivery_log` |

Aliran: unit NG di sebuah stasiun keluar dari aliran, sehingga `input` stasiun berikutnya = `ok_first_pass` stasiun sebelumnya. Rework tidak dimasukkan kembali ke aliran (penyederhanaan).

## Pesan harian (contoh dari dry-run)

```
Laporan 27 Mar 2026
Yield lini 88,1% (+0,4 pp vs 7 hari sebelumnya) · Unit OK 1239 dari 1407
Rework lini 8,3% · NG total 168 unit
Yield terendah: Frame Painting 96,2%
Top NG hari ini: Cat tipis (22), Cat berkulit jeruk (19), Celah panel tidak rata (14)
Top NG 7 hari: Cat tipis (150), Cat berkulit jeruk (130), Gores panel body (78)
```

Dikirim sebagai foto (grafik tren 14 hari + yield stasiun) dengan teks sebagai caption. Pembanding "7 hari sebelumnya" = yield gabungan 7 hari kerja berdata sebelum hari yang dilaporkan. Jika ada alert, pesan kedua (`ALERT ...`) dikirim langsung setelahnya.

## Perintah

`/yield`, `/top_ng`, `/trend 7d` (juga `14d`, `30d`; 2 sampai 60 hari), `/help`. Perintah lain dijawab "Perintah tidak dikenal" disertai daftar perintah.

## Aturan alert dan data hilang

Didefinisikan di `config/alert_rules.yaml`, dimuat ke tabel `alert_rule`. Aturan aktif: R1 yield lini, R2 yield stasiun, R3 lonjakan defect (parameter dan alasan pemilihan: `results/2-analysis/alert_eval_*.csv`). Aturan tidak aktif R4 dan R5 disimpan sebagai pembanding.

Data hilang: jika kedua shift belum tiba saat run, bot mengirim `no_data` ("belum masuk") dan mengecek ulang tiap jam sampai 14:00. Data tiba → laporan dikirim bertanda "terlambat". Sampai 14:00 tidak tiba → `no_data` kedua dan berhenti. Run ulang pada hari yang sama tidak mengirim ganda.

## Keamanan

Token dan chat id hanya dari environment (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; GitHub secrets). Token disamarkan dari pesan error. Data pabrik tidak dipakai; semua data simulasi.
