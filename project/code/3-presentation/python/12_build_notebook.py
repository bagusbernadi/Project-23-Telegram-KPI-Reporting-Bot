"""Tahap 3 / langkah 12: buat dan jalankan notebook analisis Q1-Q12 (results/3-presentation/analysis.ipynb) dari CSV hasil."""
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import common as C  # noqa: E402

M, K = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
    M("# Project 23: Telegram Bot Automated KPI Reporting\n\nAnalisis Q1-Q12. Semua tabel dibaca dari `results/` (hasil skrip SQL dan Python). Data adalah simulasi buatan sendiri; "
      "pengiriman ke Telegram tidak dilakukan sungguhan (dry-run)."),
    K("""from pathlib import Path
import pandas as pd, matplotlib.pyplot as plt
ROOT = Path.cwd()
while not (ROOT / 'results').exists():
    ROOT = ROOT.parent
R = lambda f: pd.read_csv(next((ROOT / 'results' / d / f) for d in ('1-data-preparation', '2-analysis', '3-presentation') if (ROOT / 'results' / d / f).exists()))
pd.options.display.float_format = '{:.4f}'.format
plt.rcParams.update({'figure.figsize': (9, 3.6), 'axes.spines.top': False, 'axes.spines.right': False})
BLUE, GREY, ORANGE = '#1A73E8', '#9AA0A6', '#E8710A'"""),
    M("## Data bersih\nBaris kotor ditemukan dan dipulihkan (`dirty_detection.csv`), lalu pemeriksaan konsistensi."),
    K("display(R('dirty_detection.csv')); R('clean_checks.csv')"),
    M("## Q1. KPI per stasiun (seluruh periode) dan stasiun terburuk"),
    K("R('kpi_station_period.csv')"),
    K("l = R('kpi_line_daily.csv'); plt.plot(pd.to_datetime(l.date), l.line_yield * 100, color=BLUE); plt.ylabel('yield lini (%)'); plt.title('Yield lini harian'); plt.show()"),
    M("## Q2. Pareto defect (seluruh periode, 7 hari terakhir, hari contoh)"),
    K("display(R('pareto_period.csv').head(8)); display(R('pareto_latest_7d.csv')); R('pareto_by_day_sample.csv')"),
    M("## Q3. 7 hari terakhir vs 7 hari sebelumnya"),
    K("c = R('period_compare_daily.csv'); display(c.tail(5)); plt.bar(pd.to_datetime(c.date), c.delta_pp, color=BLUE); plt.axhline(0, color=GREY); plt.ylabel('selisih (pp)'); plt.show()"),
    M("## Q4. Ambang yield lini dan stasiun\nKejadian nyata = 3 jendela penurunan yield pada `ground_truth.json`; hari alert di luar jendela = alert palsu."),
    K("display(R('alert_eval_line.csv').drop(columns='fp_dates')); R('alert_eval_station.csv').drop(columns='fp_dates')"),
    M("## Q6. Aturan lonjakan defect\nTermasuk alert palsu di masa pemanasan (`false_alerts_warmup`): aturan window 7 hari tampak bersih bila masa pemanasan dibuang."),
    K("R('alert_eval_defect.csv')"),
    M("## Aturan terpilih: performa pada replay bot dan jeda (Q5)"),
    K("display(R('alert_rule_performance.csv')); R('alert_lag.csv')"),
    M("## Q7. Pengiriman tepat waktu"),
    K("display(R('delivery_summary.csv')); R('day_outcomes.csv').query('not on_time')"),
    M("## Q8-Q9. Skenario data hilang, perintah, dan pemeriksaan secret"),
    K("display(R('scenario_tests.csv')[['scenario', 'result']]); display(R('command_tests.csv')[['command', 'result']]); R('secret_scan.csv')"),
    M("## Q10-Q11. Waktu yang dihemat (waktu manual adalah estimasi)"),
    K("display(R('impact_time.csv')); R('impact_scenarios.csv')"),
    M("## Q12. Cek silang pesan bot vs SQL vs Excel"),
    K("x = R('crosscheck.csv'); print(f\"{int(x[['line_pass','worst_pass','top_pass']].all(axis=1).sum())} dari {len(x)} tanggal lulus semua\"); x"),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
out = C.RES_PRESENT / "analysis.ipynb"
NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(C.ROOT)}}).execute()
nbf.write(nb, out)
errs = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.output_type == "error"]
print("notebook", out.name, len(nb.cells), "sel;", len(errs), "error")
assert not errs
