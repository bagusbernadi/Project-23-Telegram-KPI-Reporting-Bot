# Log cleaning (`02_clean_data.py`)

| Urutan | Aturan | Perlakuan | Ditemukan | Ditanam |
|---|---|---|---|---|
| 1 | Baris ganda pada kunci (date, shift, station, model) | simpan baris pertama; semua ganda terbukti identik | 37 | 37 |
| 2 | `ng_qty` negatif | pulihkan `ng = input - ok` | 37 | 37 |
| 3 | `ok_first_pass + ng_qty > input_qty` | pulihkan `ok = input - ng` | 37 | 37 |

Total 111 baris kotor dari 4.477 baris mentah (2,48%); 4.440 baris bersih. Presisi dan recall deteksi 100% terhadap `ground_truth_dirty.csv` (`results/1-data-preparation/dirty_detection.csv`). Setelah cleaning: ok + ng = input pada semua baris, `ng_qty` = jumlah `defect_log`, input stasiun berikut = ok stasiun sebelumnya, tidak ada nilai negatif (`clean_checks.csv`).

Aturan pemulihan mengandalkan kolom lain yang masih benar; pada data nyata pemulihan seperti ini perlu dikonfirmasi ke pemilik data.
