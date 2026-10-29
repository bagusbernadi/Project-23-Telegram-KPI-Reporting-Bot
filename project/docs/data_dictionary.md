# Kamus data

Satu hari = satu hari kerja (Senin–Jumat), 2026-03-02 sampai 2026-06-12 (75 hari). `date` pada semua tabel = tanggal produksi. Laporan tanggal D dikirim hari kerja berikutnya.

| Tabel | Isi satu baris | Kolom |
|---|---|---|
| `production_daily` | satu tanggal × shift × model × stasiun | date, shift, station, model, operator_id, input_qty, ok_first_pass, ng_qty |
| `defect_log` | jumlah satu kode defect pada satu tanggal × shift × model × stasiun | date, shift, station, model, defect_code, qty |
| `rework_log` | sekelompok unit NG yang masuk rework dan hasilnya | rework_id, date_in, date_out, station_origin, defect_code, qty, result (lulus / scrap) |
| `dim_defect` | satu kode defect | defect_code, defect_name, station, category |
| `dim_station` | satu stasiun | station, seq |
| `data_arrival_log` | kapan data satu shift tiba (hari kalender berikutnya) | date, shift, arrived_at_next_day |
| `runner_log` | satu run terjadwal (SIMULASI jeda dan kegagalan GitHub Actions) | date (tanggal produksi yang dilaporkan), scheduled_at, started_at (di hari kerja berikutnya), status |
| `alert_rule` | satu aturan alert (dari `config/alert_rules.yaml`) | rule_id, kpi, scope, method, threshold, window_days, min_count, active, note |
| `delivery_log` | satu pesan (dibuat bot saat replay dry-run) | sent_at, message_type (daily / alert / no_data), status, latency_s, error, report_date |

`ground_truth.json` dan `ground_truth_dirty.csv` (di `data/raw`) mencatat kejadian dan baris kotor yang ditanam; hanya dipakai untuk memeriksa hasil, tidak oleh bot.
