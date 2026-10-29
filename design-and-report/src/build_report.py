"""Membuat design-and-report/index.html (Report Project versi 2) dari page_v1.html dan CSV hasil.

- Pane Design diambil apa adanya dari page_v1.html (dicek identik).
- Semua angka di Report berasal dari project/results/*.csv lewat helper I/D/P (report_lib.py) dan diaudit di akhir.
Jalankan dari folder mana saja:  python design-and-report/src/build_report.py
"""
import json
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "project" / "code"))
sys.path.insert(0, HERE.as_posix())
from common import DB_PATH, GROUND_TRUTH, RES_ANALYSIS, RES_PREP, RES_PRESENT, result  # noqa: E402
from report_lib import (BLUE, D, cs, GREY, HI, I, NO, OK, P, PART, SOFT, audit, bars, esc, gbars, hbars,  # noqa: E402
                        legend, lines, pareto_svg, pill, qa, table)

R = lambda n: pd.read_csv(result(n))
PRIO = {1: "Utama", 2: "Utama", 3: "Pendukung", 4: "Utama", 5: "Utama", 6: "Pendukung", 7: "Utama", 8: "Utama", 9: "Pendukung", 10: "Utama", 11: "Tambahan", 12: "Utama"}
QT = {1: "Berapa yield, NG rate, dan rework rate per stasiun kemarin, dan stasiun mana yang terburuk?",
      2: "Defect apa yang menjadi 3 teratas kemarin dan dalam 7 hari terakhir?",
      3: "Bagaimana kondisi 7 hari terakhir dibanding 7 hari sebelumnya?",
      4: "Ambang yield berapa yang menangkap semua penurunan nyata dengan alert palsu paling sedikit?",
      5: "Berapa lama jeda dari kejadian sampai alert diterima?",
      6: "Aturan lonjakan NG mana yang paling tepat, misalnya naik lebih dari 50% dari rata-rata 7 hari?",
      7: "Berapa persen laporan harian yang terkirim tepat waktu?",
      8: "Apa yang dilakukan bot saat data terlambat atau kosong?",
      9: "Apakah token dan data tersimpan aman, tanpa secret di kode atau repositori?",
      10: "Berapa menit penyusunan laporan manual yang digantikan per laporan?",
      11: "Berapa jam kerja per tahun yang bisa dihemat?",
      12: "Apakah angka di pesan bot sama dengan query SQL dan hitungan manual Excel?"}
WARN = set()


def Q(n, ans, warn=False):
    if warn:
        WARN.add(n)
    return qa(f"Q{n}", QT[n], PRIO[n], ans, "Terjawab dengan catatan" if warn else "Terjawab", warn)


mk = lambda *a: "".join(a)
MONTH = {"03": "Mar", "04": "Apr", "05": "Mei", "06": "Jun"}
TGL = lambda s: f"{I(int(str(s)[8:10]))} {MONTH[str(s)[5:7]]}"
HM = lambda s: str(s)[11:16]                       # jam:menit dari "YYYY-MM-DD HH:MM:SS"
note = lambda t: f'<p class="note">{t}</p>'

# ---------------------------------------------------------------- data
dq, chk, gaps, dbt = R("dirty_detection.csv"), R("clean_checks.csv").set_index("check")["value"], R("data_gaps.csv"), R("db_tables.csv").set_index("object")["rows"]
kd, kl, kp, par = R("kpi_station_daily.csv"), R("kpi_line_daily.csv"), R("kpi_station_period.csv"), R("pareto_period.csv")
p7, pday, pcmp = R("pareto_latest_7d.csv"), R("pareto_by_day_sample.csv"), R("period_compare_daily.csv")
el, es, ed = R("alert_eval_line.csv"), R("alert_eval_station.csv"), R("alert_eval_defect.csv")
ae, ap, lag = R("alert_events.csv"), R("alert_rule_performance.csv").set_index("rule_id"), R("alert_lag.csv")
dlv, ds, dout = R("delivery_log.csv"), R("delivery_summary.csv").set_index("metric")["value"], R("day_outcomes.csv")
sc, ct, sec, cx = R("scenario_tests.csv"), R("command_tests.csv"), R("secret_scan.csv").set_index("check")["value"], R("crosscheck.csv")
imp, isc = R("impact_time.csv").set_index("item"), R("impact_scenarios.csv")
gt = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
con = duckdb.connect(str(DB_PATH), read_only=True)
rules = con.execute("SELECT * FROM alert_rule ORDER BY rule_id").df()
sample = con.execute("""SELECT strftime(date,'%Y-%m-%d'), shift, station, model, input_qty, ok_first_pass, ng_qty FROM production_daily
                        WHERE strftime(date,'%Y-%m-%d') = '2026-03-30' AND model = 'Bebek 125' AND shift = 'Shift 1' ORDER BY rowid LIMIT 10""").fetchall()
con.close()

last = kl.date.iloc[-1]
kl_last = kl[kl.date == last].iloc[0]
kd_last = kd[kd.date == last].sort_values("seq")
w_last = kd_last.sort_values("fpy").iloc[0]
low_days = kd.loc[kd.groupby("date").fpy.idxmin()].station.value_counts()
n_days = len(kl)
tot_in, tot_ok = kl.start_qty.sum(), kl.good_qty.sum()
y_avg = tot_ok / tot_in
rw_avg = kl.rework_qty.sum() / tot_in
wst = kp.sort_values("fpy").iloc[0]
ndays_cal = int(gaps.shape[0])
# alert terpilih
def pick(df, rule, **kw):
    q = df[df.rule == rule]
    for k, v in kw.items():
        q = q[q[k] == v]
    return q
fx = pick(el, "line_fixed")
fx_full = fx[fx.events_caught == 3].sort_values(["fp_days", "param"], ascending=[True, False]).iloc[0]       # ambang tetap terbaik yang menangkap ketiganya
rs_full = pick(el, "line_rolling_sigma")
rs_full = rs_full[rs_full.events_caught == 3].sort_values(["fp_days", "param"], ascending=[True, False]).iloc[0]
st_full = pick(es, "station_rolling_sigma")
st_full = st_full[st_full.events_caught == 3].sort_values(["fp_days", "param"], ascending=[True, False]).iloc[0]
dsel = ed[(ed.rule == "defect_poisson") & (ed.window == 20) & (ed.param == 4.0) & (ed.min_count == 5)].iloc[0]
dpct = ed[(ed.rule == "defect_pct") & (ed.window == 7) & (ed.param == 0.5) & (ed.min_count == 5)].iloc[0]
dpct20 = ed[(ed.rule == "defect_pct") & (ed.window == 20) & (ed.param == 0.5) & (ed.min_count == 5)].iloc[0]
dsig7 = ed[(ed.rule == "defect_sigma") & (ed.window == 7) & (ed.param == 5.0) & (ed.min_count == 5)].iloc[0]
ev_n = len(gt["yield_drops"])
ok_msgs = dlv[dlv.status == "sent"]
n_daily, n_alert, n_nodata = (int((ok_msgs.message_type == t).sum()) for t in ("daily", "alert", "no_data"))
n_fail = int((dlv.status == "failed").sum())
ready_n, ready_ok = int(ds["hari dengan data sudah ada saat run 07:00"]), int(ds["laporan tepat waktu di antara hari tsb"])
late_days = dout[dout.notified_missing & dout.report_sent]
empty_days = dout[dout.gave_up]
fail_days = dout[dout.runner_status == "failed"]
spike = gt["defect_spike"]
tw = dout[dout.on_time]

assert (dq.recall == 1).all() and (dq.precision == 1).all() and (sc.result == "lulus").all() and (ct.result == "lulus").all()
assert cx[["line_pass", "worst_pass", "top_pass"]].all().all() and sec.iloc[0] == 0 and sec.iloc[1] == 0
assert ap.loc["R1"].events_caught == 3 and ap.loc["R2"].events_caught == 3 and ap.loc["R3"].events_caught == ap.loc["R3"].events_total
assert ap.loc["R1"].false_alerts == 0 and ap.loc["R2"].false_alerts == 0 and ap.loc["R3"].false_alerts <= 2
assert bool(dsel.spike_caught) and dsel.drops_caught == 3 and rs_full.fp_days == 0 and fx_full.fp_days > 2
assert ready_ok / ready_n >= 0.95 and ds["on-time rate ujung ke ujung (hari dengan data tiba)"] < 95
assert len(late_days) == len(gt["late_data"]) and len(empty_days) == len(gt["empty_data"]) and len(fail_days) == len(gt["runner_failed_days"])

# ---------------------------------------------------------------- 1. data
kpc = lambda c, v, l, d: f'<div class="card kpi" style="--h:var(--{c}H)"><span class="v">{v}</span><span class="l">{l}</span><span class="d">{d}</span></div>'
rp1 = mk(
    '<div class="kpis">',
    kpc("navy", I(dbt.production_daily), "baris production_daily", f"Dari {I(chk['baris mentah'])} baris mentah. Satu baris = satu stasiun, model, shift, hari."),
    kpc("amber", I(dbt.defect_log), "baris defect_log", f"Jumlah satu kode defect per stasiun, model, shift, hari; {I(dbt.rework_log)} baris rework_log."),
    kpc("teal", I(n_days), "hari kerja ada data", f"Dari {I(ndays_cal)} hari kerja (Senin sampai Jumat, {TGL(gaps.date.iloc[0])} sampai {TGL(gaps.date.iloc[-1])} 2026). Satu hari kosong."),
    kpc("plum", I(dq.detected.sum()), "baris kotor ditemukan", f"{P(chk['persen baris kotor dari mentah'] / 100, 2)} dari baris mentah. Semua ditemukan dan dipulihkan."),
    kpc("rose", I(n_daily + n_alert + n_nodata), "pesan bot (dry-run)", f"{I(n_daily)} laporan harian, {I(n_alert)} alert, {I(n_nodata)} pemberitahuan data hilang. Tidak dikirim ke Telegram."),
    kpc("sky", I(dbt.alert_rule), "aturan alert", f"{I(rules.active.sum())} aktif, {I((~rules.active).sum())} pembanding yang ditolak."),
    '</div><h3>1.1 Data simulasi (mentah dan bersih)</h3>')
rp1 += '<div class="card"><h4>Cuplikan production_daily (30 Mar 2026, Shift 1, Bebek 125)</h4>' + table(
    ["date", "shift", "station", "model", "input_qty", "ok_first_pass", "ng_qty"],
    [[r[0], r[1], r[2], r[3], I(r[4]), I(r[5]), I(r[6])] for r in sample]) + \
    '<p>Contoh baris tabel bersih. Unit NG di sebuah stasiun keluar dari aliran, jadi <code>input_qty</code> stasiun berikutnya sama dengan <code>ok_first_pass</code> stasiun sebelumnya. Data dibuat skrip dengan seed tetap, sehingga cuplikan ini sama setiap dijalankan ulang.</p></div>'
kl_lab = {"duplikat": ("Baris ganda", "simpan baris pertama (semua ganda identik)"), "ng_negatif": ("ng_qty negatif", "pulihkan ng = input − ok"),
          "ok_ng_melebihi_input": ("OK + NG lebih dari input", "pulihkan ok = input − ng")}
rp1 += '<div class="card"><h4>Tabel 1.1. Data kotor: ditanam, ditemukan, dan perlakuan</h4>' + table(
    ["Jenis", "Perlakuan", "Ditanam", "Ditemukan", "Benar", "Salah", "Terlewat", "Recall"],
    [[kl_lab[r.kind][0], kl_lab[r.kind][1], I(r.ground_truth), I(r.detected), I(r.true_positive), I(r.false_positive), I(r.missed), P(r.recall, 0)] for r in dq.itertuples()]) + \
    f'<p>Total {I(dq.detected.sum())} baris kotor dari {I(chk["baris mentah"])} baris mentah ({P(chk["persen baris kotor dari mentah"] / 100, 2)}), sesuai rancangan 2–3%. Setelah pembersihan, {I(chk["baris bersih"])} baris bersih lolos semua pemeriksaan konsistensi (Tabel 1.2b).</p></div>'
rp1 += '<h3>1.2 Tabel di database (<code>kpi_bot.duckdb</code>)</h3><div class="card"><h4>Tabel 1.2a. Isi database</h4>' + table(
    ["Objek", "Baris", "Isi"],
    [["production_daily", I(dbt.production_daily), "Hasil harian per stasiun, model, shift (kolom operator_id tersedia)."],
     ["defect_log", I(dbt.defect_log), "Jumlah per kode defect; jumlahnya sama dengan ng_qty."],
     ["rework_log", I(dbt.rework_log), "Unit NG yang masuk rework, tanggal masuk dan keluar, hasil (lulus atau scrap)."],
     ["alert_rule", I(dbt.alert_rule), "Aturan alert dari <code>config/alert_rules.yaml</code>."],
     ["delivery_log", I(len(dlv)), "Satu baris per pesan; dibuat oleh bot saat replay dry-run (0 baris sebelum replay)."],
     ["data_arrival_log, runner_log", f"{I(dbt.data_arrival_log)} dan {I(dbt.runner_log)}", "Kedatangan data tiap shift, dan jadwal run (jeda dan kegagalan adalah simulasi)."],
     ["dim_defect, dim_station", f"{I(dbt.dim_defect)} dan {I(dbt.dim_station)}", "Referensi kode defect dan urutan stasiun."],
     ["v_station_daily, v_line_daily, v_defect_daily, v_rework_station_daily, v_kpi_station_daily", f"{I(dbt.v_station_daily)}, {I(dbt.v_line_daily)}, {I(dbt.v_defect_daily)}, {I(dbt.v_rework_station_daily)}, {I(dbt.v_kpi_station_daily)}", "View KPI: satu sumber rumus untuk bot, dashboard, dan cek silang."]]) + \
    '<h4>Tabel 1.2b. Pemeriksaan setelah pembersihan</h4>' + table(
    ["Pemeriksaan", "Hasil"],
    [[cs(k), OK("Lulus") if int(chk[k]) == 1 else NO("Gagal")] for k in chk.index if chk[k] in (0, 1) or k.startswith(("ng_qty", "input", "rework", "ok + ng", "tidak ada", "semua ganda"))]
    + [[f"Baris ganda dibuang / ng negatif dipulihkan / OK+NG melebihi input dipulihkan", f"{I(chk['baris ganda dibuang'])} / {I(chk['ng negatif dipulihkan'])} / {I(chk['ok+ng melebihi input dipulihkan'])}"]]) + '</div>'
FILES = {"dirty_detection": ("Deteksi data kotor vs ground truth", "Data"), "clean_checks": ("Pemeriksaan konsistensi setelah cleaning", "Data"),
         "data_gaps": ("Hari kerja, ada produksi, jam data tiba", "Q8"), "db_tables": ("Baris tiap tabel dan view", "Data"),
         "kpi_station_daily": ("KPI harian per stasiun", "Q1"), "kpi_line_daily": ("KPI harian lini", "Q1, Q3"), "kpi_station_period": ("KPI per stasiun, seluruh periode", "Q1"),
         "pareto_period": ("Pareto defect seluruh periode", "Q2"), "pareto_latest_7d": ("Top defect 7 hari terakhir", "Q2"), "pareto_by_day_sample": ("Top 3 defect pada hari contoh", "Q2"),
         "period_compare_daily": ("7 hari vs 7 hari sebelumnya, tiap hari", "Q3"), "alert_eval_line": ("Evaluasi ambang yield lini", "Q4"), "alert_eval_station": ("Evaluasi ambang yield stasiun", "Q4"),
         "alert_eval_defect": ("Evaluasi aturan lonjakan defect", "Q6"), "alert_events": ("Alert yang dikirim bot (aturan aktif) vs ground truth", "Q4, Q6"),
         "alert_rule_performance": ("Presisi dan kejadian tertangkap per aturan aktif", "Q4"), "alert_lag": ("Jeda kejadian sampai alert", "Q5"),
         "delivery_log": ("Log pengiriman hasil replay dry-run", "Q7, Q8"), "delivery_summary": ("Ringkasan pengiriman dan on-time rate", "Q7"), "day_outcomes": ("Hasil per hari produksi", "Q7, Q8"),
         "scenario_tests": ("Uji skenario data hilang dan gagal kirim", "Q8"), "command_tests": ("Uji perintah bot", "Q8"), "secret_scan": ("Pemeriksaan secret", "Q9"),
         "impact_time": ("Waktu otomatis (diukur) dan manual (estimasi)", "Q10, Q11"), "impact_scenarios": ("Jam dihemat menurut asumsi waktu manual", "Q11"), "crosscheck": ("Pesan bot vs SQL vs Excel", "Q12")}
resfiles = sorted(p for d in (RES_PREP, RES_ANALYSIS) for p in d.glob("*.csv"))
miss = [p.stem for p in resfiles if p.stem not in FILES]
assert not miss, f"CSV hasil belum didokumentasikan di FILES: {miss}"
rp1 += '<div class="card"><h4>Tabel 1.2c. Data hasil analisis (<code>project/results/</code>)</h4>' + table(
    ["File", "Isi", "Baris", "Menjawab"],
    [[f"<code>{p.stem}.csv</code>", FILES[p.stem][0], I(len(pd.read_csv(p))), FILES[p.stem][1]] for p in resfiles]) + \
    f'<p>{I(len(resfiles))} file CSV, ditambah <code>crosscheck.xlsx</code> dan {I(len(list(RES_PRESENT.glob("dash_*.csv"))))} CSV data dashboard.</p></div>'
rp1 += '<h3>1.3 Angka kunci (KPI)</h3><div class="card"><h4>Tabel 1.3. Lima KPI (definisi di <code>project/docs/kpi_and_messages.md</code>)</h4>' + table(
    ["KPI", "Rumus ringkas", "Hasil", "Jumlah data"],
    [["Yield lini", "unit OK di Packing ÷ unit masuk Frame Welding", f"rata-rata {P(y_avg, 1)}; {TGL(last)}: {P(kl_last.line_yield, 1)}", f"{I(tot_in)} unit masuk, {I(n_days)} hari"],
     ["Yield stasiun (FPY)", "OK pertama ÷ input", f"terendah {wst.station} {P(wst.fpy, 1)}; tertinggi {kp.sort_values('fpy').iloc[-1].station} {P(kp.fpy.max(), 1)}", f"{I(len(kp))} stasiun"],
     ["Rework rate", "unit masuk rework ÷ unit masuk lini", P(rw_avg, 1), f"{I(kl.rework_qty.sum())} unit rework"],
     ["On-time delivery bot", f"laporan terkirim paling lambat {cs('07:15')} (asumsi)", f"{P(ds['on-time delivery rate bot (data sudah ada)'] / 100, 1)} (hari dengan data sudah ada)", f"{I(ready_ok)} dari {I(ready_n)} hari"],
     ["Presisi dan recall alert", "alert benar ÷ semua alert; kejadian tertangkap ÷ kejadian", f"R1 {P(ap.loc['R1'].precision, 0)}, R2 {P(ap.loc['R2'].precision, 0)}, R3 {P(ap.loc['R3'].precision, 0)}; {I(ap.loc['R1'].events_caught)} dari {I(ev_n)} penurunan tertangkap", f"{I(len(ae))} alert pada replay"]]) + \
    f'<p>Rata-rata {P(y_avg, 1)} di sini jauh di bawah angka contoh pada halaman Design (95%): contoh itu hanya ilustrasi, bukan hasil data.</p></div>'

# ---------------------------------------------------------------- 2. business questions
hbest = lambda df, col, asc=False: df.sort_values(col, ascending=asc).iloc[0]
top_last = pday[(pday.date == last) & (pday.rnk <= 3)].sort_values("rnk")
tx = lambda df, c="qty": ", ".join(f"{r.defect_name} ({I(getattr(r, c))})" for r in df.itertuples())
s21 = mk('<h3 id="sec21">2.1 KPI harian dan Pareto defect <span class="qlist">Q1, Q2</span></h3><div class="card">',
         Q(1, f"\"Kemarin\" = hari terakhir data ({TGL(last)} 2026): yield lini {P(kl_last.line_yield, 1)} (NG {P(1 - kl_last.line_yield, 1)}, rework {P(kl_last.rework_rate, 1)}). "
              f"Stasiun terburuk hari itu {w_last.station}, yield {P(w_last.fpy, 1)}, NG rate {P(w_last.ng_rate, 1)}, rework rate {P(w_last.rework_rate, 1)}. "
              f"Sepanjang periode, {wst.station} yield terendah ({P(wst.fpy, 1)}) dan menyumbang {P(wst.share_of_line_ng, 0)} dari semua NG; stasiun itu terendah pada {I(low_days[wst.station])} dari {I(n_days)} hari. "
              f"Seluruh stasiun hari itu ada di Tabel 2.1b."),
         Q(2, f"Top 3 defect {TGL(last)}: {tx(top_last)}. Top 3 selama 7 hari kerja terakhir: {tx(p7.head(3))}. "
              f"Dua defect cat di Frame Painting memimpin seluruh periode ({P(par.share.iloc[0], 1)} dan {P(par.share.iloc[1], 1)} dari semua defect), sehingga Pareto harian hanya berubah jelas pada hari kejadian (Tabel 2.1d)."),
         '<h4>Grafik 2.1a. NG rate per stasiun, seluruh periode</h4>',
         bars([(r.station, r.ng_rate, HI if r.station == wst.station else BLUE, f"{r.station}: NG {P(r.ng_rate, 2)}, yield {P(r.fpy, 2)}, rework {P(r.rework_rate, 2)}") for r in kp.itertuples()],
              lambda v: P(v, 1), "NG rate per stasiun", rot=35),
         '<h4>Tabel 2.1b. KPI per stasiun: seluruh periode dan hari terakhir</h4>',
         table(["Stasiun", "Yield periode", "NG rate", "Rework rate", "Scrap rate", "Porsi NG lini", f"Yield {TGL(last)}", f"Rework {TGL(last)}"],
               [[r.station, P(r.fpy, 2), P(r.ng_rate, 2), P(r.rework_rate, 2), P(r.scrap_rate, 2), P(r.share_of_line_ng, 1),
                 P(kd_last[kd_last.station == r.station].fpy.iloc[0], 1), P(kd_last[kd_last.station == r.station].rework_rate.iloc[0], 1)] for r in kp.itertuples()]),
         '<h4>Grafik 2.1c. Pareto defect, 12 kode teratas (seluruh periode)</h4>',
         pareto_svg(list(par.defect_code[:12]), list(par.share[:12]), list(par.cum_share[:12]), [c <= 0.5 for c in par.cum_share[:12]],
                    [f"{r.defect_code} {r.defect_name} ({r.station}): {I(r.qty)} unit, {P(r.share, 1)}, kumulatif {P(r.cum_share, 1)}" for r in par[:12].itertuples()], "Pareto defect"),
         legend([(BLUE, "Sampai kumulatif 50%"), (SOFT, "Lainnya")]),
         '<h4>Tabel 2.1d. Tiga defect teratas pada lima hari contoh</h4>',
         table(["Tanggal", "Keterangan", "Teratas 1", "Teratas 2", "Teratas 3"],
               [[TGL(d), {"2026-03-27": "hari normal", "2026-03-30": "penurunan Engine Assembly", "2026-05-04": "penurunan Frame Painting", "2026-06-02": "penurunan perlahan Dyno", last: "hari terakhir"}[d],
                 *[f"{r.defect_name} ({I(r.qty)})" for r in g.sort_values("rnk").itertuples()]] for d, g in pday.groupby("date")]),
         '<p>Yield stasiun = OK pertama ÷ input. Rework rate = unit masuk rework ÷ input stasiun. "Kemarin" dihitung dari tanggal data terakhir, bukan tanggal hari ini.</p></div>')
dl_pc = pcmp.delta_pp
s22 = mk('<h3 id="sec22">2.2 Tujuh hari terakhir dibanding sebelumnya <span class="qlist">Q3</span></h3><div class="card">',
         Q(3, f"Pada {TGL(last)}, yield lini 7 hari terakhir {P(pcmp.yield_last7.iloc[-1], 1)} dibanding {P(pcmp.yield_prev7.iloc[-1], 1)} pada 7 hari sebelumnya, selisih {D(dl_pc.iloc[-1], 2)} poin. "
              f"Selama {I(len(pcmp))} hari yang bisa dibandingkan, selisih berkisar {D(dl_pc.min(), 2)} sampai {D(dl_pc.max(), 2)} poin; dua titik terendah jatuh pada minggu penurunan yield Engine Assembly dan Performance Test (Dyno). "
              f"Pesan harian memakai pembanding yang lebih sederhana: 7 hari kerja berdata sebelum hari yang dilaporkan."),
         '<h4>Grafik 2.2a. Selisih yield lini 7 hari terakhir vs 7 hari sebelumnya (poin persentase)</h4>',
         lines([TGL(d) for d in pcmp.date], [("Selisih (poin)", BLUE, 2.5, list(dl_pc))], lambda v: D(v, 1), "Selisih yield 7 hari"),
         legend([(BLUE, "Selisih yield 7 hari vs 7 hari sebelumnya, poin persentase")]),
         '<p>Dua periode dibandingkan sebagai gabungan (unit OK ÷ unit masuk), bukan rata-rata harian. Hari tanpa data tidak dihitung.</p></div>')
line_row = lambda r: [{"line_fixed": "Ambang tetap", "line_rolling_sigma": "Rata-rata 20 hari − kσ"}[r.rule], P(r.param, 1) if r.rule == "line_fixed" else D(r.param, 1) + "σ",
                      I(r.alert_days), I(r.tp_days), I(r.fp_days), f"{I(r.events_caught)} dari {I(ev_n)}"]
alert_idx = [i for i, d in enumerate(kl.date) if d in set(ae[ae.scope == "line"].report_date)]
s23 = mk('<h3 id="sec23">2.3 Ambang alert yield <span class="qlist">Q4</span></h3><div class="card">',
         Q(4, f"Tidak ada ambang tetap yang bersih. Ambang tetap terkecil yang menangkap ketiga penurunan adalah {P(fx_full.param, 1)}, dengan {I(fx_full.fp_days)} alert palsu dalam {I(len(kl) - 20)} hari (batas keberhasilan: 2). "
              f"Batas yang mengikuti rata-rata 20 hari (rata-rata − {D(rs_full.param, 1)}σ) menangkap {I(rs_full.events_caught)} dari {I(ev_n)} penurunan dengan {I(rs_full.fp_days)} alert palsu, dan untuk satu stasiun (−{D(st_full.param, 1)}σ) "
              f"{I(st_full.events_caught)} dari {I(ev_n)} dengan {I(st_full.fp_days)} palsu. Ambang itu dipilih dari data yang sama dengan yang dinilai dan hanya ada {I(ev_n)} kejadian, jadi hasilnya belum teruji pada data baru. "
              f"Alert yield baru aktif setelah 20 hari berdata (masa pemanasan).", warn=True),
         '<h4>Grafik 2.3a. Alert palsu per pilihan ambang yield lini (biru: menangkap ketiga penurunan)</h4>',
         hbars([(("Tetap " + P(r.param, 1)) if r.rule == "line_fixed" else f"Rata-rata − {D(r.param, 1)}σ", r.fp_days, BLUE if r.events_caught == ev_n else HI,
                 f"{'Tetap ' + P(r.param, 1) if r.rule == 'line_fixed' else 'Rolling ' + D(r.param, 1) + 'σ'}: {I(r.fp_days)} alert palsu, {I(r.events_caught)} dari {I(ev_n)} kejadian tertangkap") for r in el.itertuples()],
               lambda v: I(v), "Alert palsu per ambang", max(el.fp_days.max(), 1) + 1),
         legend([(BLUE, "Menangkap ketiga penurunan"), (HI, "Melewatkan minimal satu penurunan")]),
         '<h4>Tabel 2.3b. Yield lini: ambang tetap dan batas rolling (dinilai pada hari ke-21 dan seterusnya)</h4>',
         table(["Aturan", "Parameter", "Hari alert", "Alert benar", "Alert palsu", "Kejadian tertangkap"], [line_row(r) for r in el.itertuples()]),
         '<h4>Tabel 2.3c. Yield per stasiun (alert benar hanya bila stasiunnya sama dengan stasiun kejadian)</h4>',
         table(["Aturan", "Parameter", "Alert benar", "Alert palsu", "Kejadian tertangkap"],
               [[{"station_fixed": "Ambang tetap", "station_rolling_sigma": "Rata-rata 20 hari − kσ"}[r.rule], P(r.param, 0) if r.rule == "station_fixed" else D(r.param, 1) + "σ", I(r.tp_days), I(r.fp_days), f"{I(r.events_caught)} dari {I(ev_n)}"] for r in es.itertuples()]),
         '<h4>Grafik 2.3d. Yield lini harian dan hari alert R1 (area kuning)</h4>',
         lines([TGL(d) for d in kl.date], [("Yield lini", BLUE, 2.2, list(kl.line_yield))], lambda v: P(v, 0), "Yield lini harian dan hari alert", bands=alert_idx, band_label="Alert R1"),
         legend([(BLUE, "Yield lini harian")]),
         f'<p>Kejadian nyata: {I(ev_n)} jendela penurunan di <code>ground_truth.json</code>. Alert di luar jendela dihitung palsu. Contoh slider pada halaman Design memakai yield sekitar 95%; yield nyata data ini sekitar {P(y_avg, 0)}, jadi ambang contoh tidak berlaku.</p></div>')
lag_ok = lag.dropna(subset=["days_to_detect"])
s24 = mk('<h3 id="sec24">2.4 Jeda sampai alert diterima <span class="qlist">Q5</span></h3><div class="card">',
         Q(5, f"Alert diterima {D(lag_ok.hours_after_shift_end.min(), 1)} sampai {D(lag_ok.hours_after_shift_end.max(), 1)} jam setelah akhir hari produksi pada kejadian yang terdeteksi, atau {D(lag_ok.hours_earlier_than_manual.min(), 1)} sampai {D(lag_ok.hours_earlier_than_manual.max(), 1)} jam lebih awal daripada laporan manual. "
              f"Dua penurunan mendadak terdeteksi pada hari kejadian ({TGL(lag.first_alert_for.iloc[0])} dan {TGL(lag.first_alert_for.iloc[1])}). Penurunan perlahan di {lag.station.iloc[2]} baru terdeteksi pada hari ke-{I(lag.days_to_detect.iloc[2] + 1)} dari {I(lag.event_days.iloc[2])} hari kejadian "
              f"({TGL(lag.first_alert_for.iloc[2])}), sehingga jeda ini lebih ditentukan oleh bentuk penurunannya daripada oleh jadwal bot. "
              f"Jam akhir shift 2 ({cs('23:00')}) dan jam tiba laporan manual ({cs('12:00')}) adalah asumsi, bukan data.", warn=True),
         '<h4>Grafik 2.4a. Hari sampai alert pertama sejak kejadian dimulai (0 = hari yang sama)</h4>',
         hbars([(f"{r.station} ({TGL(r.event_start)})", r.days_to_detect, BLUE if r.days_to_detect == 0 else HI, f"{r.station}: alert pertama hari ke-{I(r.days_to_detect + 1)} dari {I(r.event_days)} hari kejadian") for r in lag_ok.itertuples()],
               lambda v: I(v), "Hari sampai alert pertama", max(lag_ok.days_to_detect.max(), 1) + 1),
         '<h4>Tabel 2.4b. Jeda tiap kejadian</h4>',
         table(["Kejadian", "Mulai", "Lama (hari)", "Alert pertama untuk tanggal", "Terkirim", "Jam setelah akhir hari (asumsi)", "Lebih awal dari manual (asumsi)"],
               [[r.station, TGL(r.event_start), I(r.event_days), TGL(r.first_alert_for), f"{TGL(r.alert_sent_at)} {cs(HM(r.alert_sent_at))}", D(r.hours_after_shift_end, 1), D(r.hours_earlier_than_manual, 1)] for r in lag_ok.itertuples()]),
         '<p>Pesan tertunda kecil karena jadwal Actions (simulasi 0 sampai 11 menit) dan, pada satu kejadian, run yang gagal diulang pukul 08:00.</p></div>')
ed5 = ed[ed.min_count == 5]
s25 = mk('<h3 id="sec25">2.5 Aturan lonjakan defect <span class="qlist">Q6</span></h3><div class="card">',
         Q(6, f"Aturan \"naik lebih dari 50% dari rata-rata 7 hari\" paling buruk: {I(dpct.alerts)} alert dengan {I(dpct.false_alerts)} palsu (presisi {P(dpct.precision, 0)}), dan dengan rata-rata 20 hari tetap {I(dpct20.false_alerts)} palsu dari {I(dpct20.alerts)}. "
              f"Aturan terbaik: jumlah satu kode > rata-rata 20 hari + 4 × akar rata-rata (sebaran Poisson), minimal 5 unit. Aturan itu memberi {I(dsel.alerts)} alert, {I(dsel.true_alerts)} benar dan {I(dsel.false_alerts)} palsu, menangkap lonjakan {spike['defect_code']} ({TGL(spike['date'])}) "
              f"serta {I(dsel.drops_caught)} dari {I(ev_n)} penurunan. Catatan temuan: aturan 7 hari berbasis simpangan baku (5σ) tampak bersih ({I(dsig7.false_alerts)} palsu) bila hanya dinilai setelah hari ke-20, tetapi menghasilkan {I(dsig7.false_alerts_warmup)} alert palsu pada masa pemanasan hari ke-8 sampai 20. "
              f"Karena itu window dinaikkan ke 20 hari."),
         '<h4>Grafik 2.5a. Alert palsu per aturan lonjakan (window 20 hari, minimal 5 unit; biru: aturan terpilih)</h4>',
         hbars([({"defect_pct": "Naik", "defect_sigma": "Rata-rata + kσ", "defect_poisson": "Poisson k ="}[r.rule] + (f" {P(r.param, 0)}" if r.rule == "defect_pct" else f" {D(r.param, 0)}"),
                 r.false_alerts, BLUE if (r.rule == "defect_poisson" and r.param == 4.0) else HI, f"{r.rule} param {D(r.param, 1)}: {I(r.false_alerts)} palsu dari {I(r.alerts)} alert") for r in ed5[ed5.window == 20].itertuples()],
               lambda v: I(v), "Alert palsu per aturan lonjakan", ed5[ed5.window == 20].false_alerts.max() + 10),
         '<h4>Tabel 2.5b. Aturan lonjakan defect (minimal 5 unit)</h4>',
         table(["Aturan", "Window (hari)", "Parameter", "Alert", "Benar", "Palsu", "Palsu masa pemanasan", "Lonjakan tertangkap", "Penurunan tertangkap"],
               [[{"defect_pct": "Naik di atas rata-rata", "defect_sigma": "Rata-rata + kσ", "defect_poisson": "Rata-rata + k·√rata-rata"}[r.rule], I(r.window), P(r.param, 0) if r.rule == "defect_pct" else D(r.param, 1),
                 I(r.alerts), I(r.true_alerts), I(r.false_alerts), I(r.false_alerts_warmup), OK("Ya") if r.spike_caught else NO("Tidak"), f"{I(r.drops_caught)} dari {I(ev_n)}"] for r in ed5.itertuples()]),
         '<p>Alert lonjakan dianggap benar bila kode defect berada di stasiun kejadian pada jendelanya, atau kode lonjakan pada harinya. Lonjakan yang ditanam tidak menurunkan yield lini (R1 tidak berbunyi hari itu), jadi hanya aturan defect yang bisa melihatnya.</p></div>')
kinds = {"ok": int(dout.on_time.sum()), "fail": len(fail_days), "late": len(late_days), "empty": len(empty_days)}
exc = []
for r in dout.itertuples():
    if r.runner_status == "failed":
        exc.append([TGL(r.report_date), "Run Actions gagal", f"{TGL(r.sent_at)} {cs(HM(r.sent_at))}", "Diulang pukul 08:00, terkirim"])
    elif r.notified_missing and r.report_sent:
        exc.append([TGL(r.report_date), "Data tiba siang", f"{TGL(r.sent_at)} {cs(HM(r.sent_at))}", "Pemberitahuan pukul 07:00, laporan setelah data tiba"])
    elif r.gave_up:
        exc.append([TGL(r.report_date), "Data kosong sehari penuh", "tidak ada laporan", "Pemberitahuan pukul 07:00 dan pesan akhir pukul 14:00"])
s26 = mk('<h3 id="sec26">2.6 Keandalan pengiriman dan keamanan <span class="qlist">Q7, Q8, Q9</span></h3><div class="card">',
         Q(7, f"{P(ds['on-time delivery rate bot (data sudah ada)'] / 100, 1)} ({I(ready_ok)} dari {I(ready_n)} hari) laporan terkirim paling lambat {cs('07:15')} pada hari ketika data sudah ada saat run 07:00; tiga hari lainnya run gagal dan terkirim pukul 08:00. "
              f"Termasuk dua hari data tiba siang, angkanya {P(ds['on-time rate ujung ke ujung (hari dengan data tiba)'] / 100, 1)} dari {I(ds['hari dengan data tiba'])} hari dengan data, atau {P(ds['on-time rate semua hari kerja (termasuk data hilang)'] / 100, 1)} dari {I(len(dout))} hari kerja. "
              f"Jeda jadwal dan kegagalan run berasal dari simulasi, bukan pengukuran GitHub Actions. Batas tepat waktu {cs('07:15')} adalah asumsi.", warn=True),
         Q(8, f"Bot tidak diam. Saat data belum masuk, bot mengirim pemberitahuan \"belum masuk\", mengecek ulang tiap jam, dan mengirim laporan bertanda terlambat begitu data tiba (dua hari data tiba siang). "
              f"Jika sampai pukul {cs('14:00')} tidak ada data (satu hari kosong), bot mengirim pesan akhir dan berhenti. Run ulang tidak mengirim ganda; pengiriman Telegram yang gagal diulang tiga kali lalu dicatat gagal. "
              f"{I((sc.result == 'lulus').sum())} dari {I(len(sc))} skenario lulus, tetapi pengiriman diuji dengan transport palsu, bukan ke Telegram sungguhan.", warn=True),
         Q(9, f"Tidak ada token atau secret di kode: {I(sec['berkas terlacak yang memuat pola token'])} berkas terlacak dan {I(sec['pola token di riwayat git (semua cabang)'])} temuan di riwayat git (semua cabang) cocok dengan pola token bot. "
              f"Workflow membaca token dari GitHub secrets, data mentah dan database masuk <code>.gitignore</code>, dan token disamarkan dari pesan error. Catatan: bot sungguhan belum pernah dibuat, jadi belum ada token yang bisa bocor; pemeriksaan ini hanya pola teks.", warn=True),
         '<h4>Grafik 2.6a. Hari kerja menurut hasil pengiriman</h4>',
         bars([("Tepat waktu", kinds["ok"], BLUE, f"{I(kinds['ok'])} hari: terkirim paling lambat 07:15"), ("Run gagal, terkirim 08:00", kinds["fail"], HI, f"{I(kinds['fail'])} hari"),
               ("Data tiba siang", kinds["late"], HI, f"{I(kinds['late'])} hari"), ("Data kosong", kinds["empty"], GREY, f"{I(kinds['empty'])} hari: tidak ada laporan")], lambda v: I(v), "Hari kerja menurut hasil pengiriman", rot=0, small=True),
         '<h4>Tabel 2.6b. Ringkasan pengiriman</h4>',
         table(["Ukuran", "Nilai"], [[cs(k), D(v, 1) if (v != int(v)) else I(v)] for k, v in ds.items()]),
         '<h4>Tabel 2.6c. Hari yang tidak tepat waktu</h4>',
         table(["Tanggal produksi", "Penyebab", "Laporan terkirim", "Perilaku bot"], exc),
         '<h4>Tabel 2.6d. Uji skenario (Q8)</h4>',
         table(["Skenario", "Diharapkan", "Hasil"], [[cs(r.scenario), cs(r.expected), OK("Lulus") if r.result == "lulus" else NO("Gagal")] for r in sc.itertuples()]),
         '<h4>Tabel 2.6e. Uji perintah bot</h4>',
         table(["Perintah", "Yang dicek", "Hasil"], [[f"<code>{esc(r.command)}</code>", cs(r.check), OK("Lulus") if r.result == "lulus" else NO("Gagal")] for r in ct.itertuples()]),
         '<h4>Tabel 2.6f. Pemeriksaan secret (Q9)</h4>',
         table(["Pemeriksaan", "Nilai"], [[cs(k), I(v)] for k, v in sec.items()]), '</div>')
s27 = mk('<h3 id="sec27">2.7 Waktu yang dihemat <span class="qlist">Q10, Q11</span></h3><div class="card">',
         Q(10, f"Sekitar {I(imp.loc['waktu manual per laporan (menit)'].value)} menit per laporan manual digantikan, dan setelah dikurangi {I(imp.loc['waktu baca pesan bot (menit)'].value)} menit membaca pesan bot, {I(imp.loc['menit dihemat per laporan'].value)} menit dihemat. "
               f"Angka manual adalah estimasi penulis (lima langkah, Tabel 2.7a), bukan hasil stopwatch; waktu otomatis diukur: median {D(imp.loc['waktu otomatis per laporan (detik)'].value, 2)} detik per laporan.", warn=True),
         Q(11, f"Sekitar {D(imp.loc['jam kerja dihemat per tahun'].value, 0)} jam kerja per tahun (estimated), dihitung {I(imp.loc['hari kerja per tahun'].value)} laporan × {I(imp.loc['menit dihemat per laporan'].value)} menit ÷ 60. "
               f"Bila waktu manual sebenarnya 15 sampai 40 menit, hasilnya {D(isc.hours_saved_per_year.min(), 0)} sampai {D(isc.hours_saved_per_year.max(), 0)} jam per tahun (Tabel 2.7b).", warn=True),
         '<h4>Tabel 2.7a. Waktu per laporan</h4>',
         table(["Ukuran", "Nilai", "Label"], [[cs(k), D(r.value, 2) if r.value != int(r.value) else I(r.value), cs(r.label)] for k, r in imp.iterrows()]),
         '<h4>Tabel 2.7b. Jam dihemat per tahun menurut asumsi waktu manual (estimated)</h4>',
         table(["Waktu manual (menit)", "Jam dihemat per tahun"], [[I(r.manual_minutes_per_report), D(r.hours_saved_per_year, 1)] for r in isc.itertuples()]),
         '<p>Semua angka dampak berlabel estimated. Dampak dalam rupiah tidak dihitung.</p></div>')
cx_pass = cx[["line_pass", "worst_pass", "top_pass"]].all(axis=1)
s28 = mk('<h3 id="sec28">2.8 Validitas angka pesan <span class="qlist">Q12</span></h3><div class="card">',
         Q(12, f"Ya. {I(cx_pass.sum())} dari {I(len(cx))} tanggal sampel lulus semua pemeriksaan: yield lini, yield stasiun terendah, dan defect teratas pada pesan bot sama dengan SQL independen (query langsung ke CSV bersih, tanpa view) dan dengan rumus Excel (SUMIFS). "
               f"Angka pesan dibulatkan satu desimal persen, sedangkan SQL dan Excel dicocokkan hingga 9 desimal. Rumus Excel dihitung ulang oleh LibreOffice, bukan Microsoft Excel."),
         '<h4>Tabel 2.8a. Cek silang pesan bot, SQL, dan Excel</h4>',
         table(["Tanggal", "Yield lini (pesan)", "SQL", "Excel", "Terendah (pesan)", "SQL", "Excel", "Defect teratas (pesan)", "Hasil"],
               [[TGL(r.date), P(r.bot_line, 1), P(r.sql_line, 3), P(r.excel_line, 3), P(r.bot_worst, 1), P(r.sql_worst, 3), P(r.excel_worst, 3), cs(r.bot_top),
                 OK("PASS") if (r.line_pass and r.worst_pass and r.top_pass) else NO("GAGAL")] for r in cx.itertuples()]),
         '<p>Sampel: hari kejadian, hari lonjakan, hari data terlambat, dan enam hari acak dengan seed tetap.</p></div>')
SEC = {1: "21", 2: "21", 3: "22", 4: "23", 5: "24", 6: "25", 7: "26", 8: "26", 9: "26", 10: "27", 11: "27", 12: "28"}
rp2_body = mk(s21, s22, s23, s24, s25, s26, s27, s28)
qn_all = sorted(int(x) for x in re.findall(r'<span class="qn">Q(\d+)</span>', rp2_body))
assert qn_all == list(range(1, 13)), qn_all
npr = {k: sum(1 for v in PRIO.values() if v == k) for k in ("Utama", "Pendukung", "Tambahan")}
nw = len(WARN)
wtxt = ", ".join(f"Q{n}" for n in sorted(WARN))
chips = mk('<div class="qchips">', "".join(f'<a class="qc{" w" if n in WARN else ""}" href="#sec{SEC[n]}" title="{esc(QT[n])}">Q{n}</a>' for n in range(1, 13)), '</div>')
rp2 = mk(f'<div class="card"><p><b>Jawaban singkat:</b> semua {len(QT)} pertanyaan terjawab ({npr["Utama"]} Utama, {npr["Pendukung"]} Pendukung, {npr["Tambahan"]} Tambahan). '
         f'{nw} jawaban dengan catatan (kuning): {wtxt}. Klik nomor pertanyaan untuk melompat ke pembahasannya. Pertanyaan utama project dijawab di bagian 7.</p>',
         chips, '<p class="report-note">Q hijau = terjawab, Q kuning = terjawab dengan catatan. Pembahasan dikelompokkan per grafik atau tabel bukti (2.1 sampai 2.8). Catatan kuning pada dasarnya satu hal: semua data, jeda run, dan pengiriman adalah simulasi.</p></div>', rp2_body)

# ---------------------------------------------------------------- 3-5. dataset, tools, alur
CODE_REL = "project/code/"
npy = len(list((REPO / CODE_REL).rglob("*.py")))
loc = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in (REPO / CODE_REL).rglob("*.py"))
nsql = len(list((REPO / CODE_REL).rglob("*.sql")))
ntest = len(list((REPO / "project/tests").glob("test_*.py")))
spike_row = kl[kl.date == spike["date"]].iloc[0]
spike_r1 = bool(((ae.rule_id == "R1") & (ae.report_date == spike["date"])).any())
spike_r3 = bool(((ae.rule_id == "R3") & (ae.report_date == spike["date"]) & (ae.subject == spike["defect_code"])).any())
assert not spike_r1 and spike_r3
gt_rows = [
    ("1", "Tiga penurunan yield: 2 hari Engine Assembly, 1 hari Frame Painting, penurunan perlahan ±1 minggu di Roller Test",
     f"Tertangkap {I(ap.loc['R1'].events_caught)} dari {I(ev_n)} oleh R1 (lini) dan oleh R2 (stasiun). \"Roller Test\" tidak ada di daftar 10 stasiun, jadi diganti Performance Test (Dyno), {I(lag.event_days.iloc[2])} hari turun perlahan", PART("Sesuai + penyesuaian")),
    ("2", "Dua hari data terlambat (tersedia siang)", f"{I(len(late_days))} hari data tiba pukul 12:00 sampai 13:30; bot memberi tahu lalu mengirim laporan setelah data tiba (S3)", OK("Sesuai")),
    ("3", "Satu hari data kosong", f"{I(len(empty_days))} hari tanpa baris sama sekali; bot mengirim dua pesan pemberitahuan dan berhenti (S4)", OK("Sesuai")),
    ("4", "Satu lonjakan NG pada satu defect yang tidak menurunkan yield lini secara besar", f"{spike['defect_code']} pada {TGL(spike['date'])}: R3 berbunyi, R1 tidak; yield lini hari itu {P(spike_row.line_yield, 1)} dibanding rata-rata {P(y_avg, 1)}", OK("Sesuai")),
    ("5", "Data kotor 2–3%: jumlah negatif, OK + NG melebihi input, baris ganda", f"{P(chk['persen baris kotor dari mentah'] / 100, 2)}; ketiga jenis ditemukan semua ({I(dq.detected.sum())} baris)", OK("Sesuai"))]
rp3 = mk('<div class="card"><p><b>Jawaban singkat:</b> dataset sesuai rancangan dan dibuat ulang dengan seed tetap. Perbedaannya: stasiun "Roller Test" diganti Performance Test (Dyno), log pengiriman bot dibuat oleh replay dry-run (bukan log pengiriman nyata), '
         'jeda dan kegagalan run adalah simulasi, dan contoh angka pada halaman Design (yield 95%) ternyata jauh dari yield data ini. Tidak ada masalah lisensi karena data buatan sendiri.</p></div>',
         table(["Aspek", "Rancangan", "Realisasi", "Verdict"], [
             ["Sumber", "Simulasi buatan sendiri, <code>scripts/generate_data.py</code>", "<code>01_generate_data.py</code>, seed tetap, hasil identik setiap dijalankan; naik dari v2 ke v3 untuk memuat semua kejadian rancangan", PART("Sesuai + penyesuaian")],
             ["Ukuran", "10 stasiun, 3 model, 2 shift, ±75 hari kerja", f"{I(dbt.dim_station)} stasiun, 3 model, 2 shift, {I(ndays_cal)} hari kerja ({I(n_days)} ada data)", OK("Sesuai")],
             ["production_daily", "±4.500 baris", f"{I(chk['baris mentah'])} mentah, {I(chk['baris bersih'])} bersih", OK("Sesuai")],
             ["defect_log", "±6.000 baris", f"{I(dbt.defect_log)} baris", OK("Sesuai")],
             ["Lima tabel", "production_daily, defect_log, rework_log, alert_rule, delivery_log", f"Kelimanya ada. rework_log {I(dbt.rework_log)} baris; delivery_log berisi {I(len(dlv))} baris hasil replay dry-run, bukan pengiriman nyata", PART("Sesuai + penyesuaian")],
             *[[f"Fakta {a}", b, cs(c), d] for a, b, c, d in gt_rows],
             ["Contoh pesan harian", "\"Laporan 3 Mar 2026 · Yield lini 95,1% ... Engine Assembly 92,3%\" (satu baris)", "Beberapa baris: yield lini, rework, stasiun terendah, top NG hari dan 7 hari; dikirim sebagai foto dengan teks sebagai caption. Angka contoh karangan, bukan hasil data", PART("Berubah")],
             ["Perintah bot", "/yield, /top_ng, /trend 7d, /help", f"Keempatnya, ditambah /trend 14d dan 30d; {I(len(ct))} uji perintah lulus", OK("Sesuai")],
             ["Log kedatangan data dan jadwal run", "Tidak disebut", f"Ditambah <code>data_arrival_log</code> ({I(dbt.data_arrival_log)} baris) dan <code>runner_log</code> ({I(dbt.runner_log)} baris) agar skenario data terlambat dan gagal kirim bisa diuji", PART("Tambahan")],
             ["Lisensi", "Tidak memakai data publik atau data perusahaan", "Tidak ada dataset pihak ketiga, tidak perlu dicek", OK("Tidak berlaku")]]))
rp4 = mk('<div class="card"><p><b>Jawaban singkat:</b> tools utama dipakai, dengan tiga perbedaan penting: python-telegram-bot diganti permintaan HTTP langsung ke Bot API, GitHub Actions baru berupa file workflow yang belum dijalankan, '
         'dan Streamlit belum di-deploy. Cek silang Excel dihitung ulang oleh LibreOffice.</p></div>',
         table(["Tool", "Rancangan", "Realisasi", "Verdict"], [
             ["Python (pandas, matplotlib)", "Query ke KPI, grafik tren dan Pareto, susun pesan", f"Modul bot (<code>report.py</code>, <code>alerts.py</code>, <code>commands.py</code>, <code>sender.py</code>, <code>run_daily.py</code>), grafik dua panel; {I(npy)} skrip dan modul, {I(loc)} baris", OK("Sesuai")],
             ["DuckDB + SQL", "Database dan view KPI", f"<code>kpi_bot.duckdb</code>; {I(nsql)} file SQL dengan {I(5)} view", OK("Sesuai")],
             ["python-telegram-bot", "Kirim pesan dan grafik, jawab perintah", "Tidak dipakai. <code>TelegramSender</code> memanggil Bot API (<code>sendMessage</code>, <code>sendPhoto</code>) lewat <code>requests</code> dengan retry; bisa diganti transport palsu untuk uji. Perintah dijawab oleh fungsi <code>handle()</code>, belum dihubungkan ke polling Telegram", PART("Berubah")],
             ["GitHub Actions", "Jadwal 07:00, simpan log, jalankan tes", "<code>.github/workflows/daily.yml</code>: cron 07:00 WIB, ulang tiap jam sampai 14:00, jalankan pytest, token dari secrets. Belum pernah dijalankan di GitHub", PART("Sebagian")],
             ["Streamlit", "Dashboard riwayat KPI, alert, log pengiriman", "<code>streamlit/app.py</code>, 3 halaman, filter tanggal dan jenis pesan; diuji dengan <code>AppTest</code>; belum di-deploy", PART("Sebagian")],
             ["GitHub + Markdown", "Kode, screenshot pesan, README", "Struktur dan README siap, contoh pesan berupa teks dan grafik hasil dry-run (bukan screenshot Telegram); di branch <code>project-23-build</code>, belum digabung ke <code>main</code>", PART("Sebagian")],
             ["Excel", "Cek silang angka pesan (langkah 10)", f"<code>crosscheck.xlsx</code>: rumus SUMIFS untuk {I(len(cx))} tanggal; dihitung ulang oleh LibreOffice, bukan Microsoft Excel", PART("Sesuai + penyesuaian")],
             ["Jupyter, pytest", "Tidak disebut", f"<code>analysis.ipynb</code> dieksekusi tanpa error; {I(ntest)} berkas tes pytest", PART("Tambahan")]]))
steps = [("1", "Menyepakati definisi KPI dan isi pesan", "<code>project/docs/kpi_and_messages.md</code>", OK("Sesuai"), ""),
         ("2", "Menyusun aturan alert awal", "<code>project/config/alert_rules.yaml</code>", PART("Sesuai + penyesuaian"), "Aturan awal diganti setelah evaluasi: ambang tetap ditolak, window defect 7 diganti 20 hari."),
         ("3", "Membuat data simulasi", "<code>01_generate_data.py</code>, <code>ground_truth.json</code>", PART("Sesuai + penyesuaian"), "Generator naik v2 ke v3; Roller Test diganti Dyno."),
         ("4", "Memuat data dan membuat view KPI", "<code>02_clean_data.py</code>, <code>03_build_db.py</code>, <code>01_views.sql</code>", OK("Sesuai"), ""),
         ("5", "Membuat bot dan grup uji", "<code>bot/sender.py</code>, <code>daily.yml</code>", PART("Sebagian"), "Bot tidak didaftarkan di BotFather dan tidak ada grup uji; kode pengirim hanya diuji dengan transport palsu."),
         ("6", "Membangun pipeline laporan harian", "<code>bot/report.py</code>, <code>04_kpi_report.py</code>", OK("Sesuai"), ""),
         ("7", "Mengevaluasi ambang alert", "<code>05_alert_eval.py</code>, <code>07_alert_review.py</code>", PART("Sesuai + tambahan"), "Ditambah evaluasi masa pemanasan dan aturan Poisson."),
         ("8", "Menambahkan perintah bot", "<code>bot/commands.py</code>, <code>08_scenario_tests.py</code>", PART("Sesuai + penyesuaian"), "Diuji sebagai fungsi, belum lewat Telegram."),
         ("9", "Menjadwalkan dan menguji skenario gagal", "<code>daily.yml</code>, <code>06_run_bot.py</code>, <code>08_scenario_tests.py</code>", PART("Sebagian"), "Jadwal diuji lewat replay dry-run; workflow belum dijalankan di GitHub."),
         ("10", "Cek silang angka dan menghitung dampak", "<code>09_crosscheck.py</code>, <code>10_impact.py</code>", OK("Sesuai"), "Waktu manual adalah estimasi."),
         ("11", "Membuat dashboard pendamping", "<code>streamlit/app.py</code>, <code>11_build_dashboard_data.py</code>", PART("Sebagian"), "Belum di-deploy."),
         ("12", "Menulis README dan finalisasi", "<code>README.md</code>, halaman ini", PART("Sebagian"), "Siap; digabung ke main setelah ditinjau.")]
renames = [("scripts/generate_data.py", CODE_REL + "1-data-preparation/python/01_generate_data.py"), ("bot/report.py", CODE_REL + "2-analysis/python/bot/report.py"),
           ("bot/commands.py", CODE_REL + "2-analysis/python/bot/commands.py"), ("config/alert_rules.yaml", "project/config/alert_rules.yaml"),
           ("docs/kpi_and_messages.md", "project/docs/kpi_and_messages.md"), ("data/ground_truth.json", "project/data/ground_truth.json"),
           ("notebooks/alert_evaluation.ipynb", "project/results/3-presentation/analysis.ipynb"), ("outputs/crosscheck.xlsx", "project/results/2-analysis/crosscheck.xlsx"),
           ("dashboard/app.py", CODE_REL + "3-presentation/streamlit/app.py"), ("docs/screenshots/", "project/docs/samples/ (teks dan grafik hasil dry-run)"),
           ("production.duckdb", "project/kpi_bot.duckdb (tidak di-commit)"), ("requirements.txt", "project/requirements.txt"), (".github/workflows/daily.yml", ".github/workflows/daily.yml"),
           ("(tidak ada)", ", ".join(("bot/alerts.py", "bot/sender.py", "bot/run_daily.py", "05_alert_eval.py", "07_alert_review.py", "08_scenario_tests.py", "09_crosscheck.py", "common.py")))]
for a, b in renames:
    for part in b.split(", "):
        part = part.split(" (")[0]
        if "*" in part or "/" not in part or "tidak di-commit" in b:
            continue
        if part in ("bot/alerts.py", "bot/sender.py", "bot/run_daily.py"):
            part = CODE_REL + "2-analysis/python/" + part
        assert (REPO / part).exists(), part
allpy = {p.name for p in (REPO / CODE_REL).rglob("*.py")}
assert {"alerts.py", "sender.py", "run_daily.py", "05_alert_eval.py", "07_alert_review.py", "08_scenario_tests.py", "09_crosscheck.py", "common.py"} <= allpy
rp5 = mk('<div class="card"><p><b>Jawaban singkat:</b> 12 langkah dijalankan sesuai urutan. Lima langkah baru sebagian (membuat bot nyata, menjadwalkan di GitHub, dashboard, finalisasi), karena tidak ada token, jaringan, atau deployment di sesi ini. '
         'Ada beberapa langkah tambahan: evaluasi masa pemanasan, uji skenario, dan cek silang pesan.</p></div>',
         table(["Langkah", "Rancangan", "Realisasi", "Verdict", "Catatan"], [[a, b, c, d, e] for a, b, c, d, e in steps]),
         '<div class="card"><h4>Penyesuaian dan improvisasi yang tidak ada di rancangan</h4><ul class="tight">',
         f'<li>Aturan alert awal diganti setelah dievaluasi. Ambang tetap menghasilkan {I(fx_full.fp_days)} alert palsu, dan aturan lonjakan 7 hari tampak bersih sampai masa pemanasan ikut dinilai ({I(dsig7.false_alerts_warmup)} alert palsu), sehingga window dinaikkan ke 20 hari.</li>',
         '<li>Kejadian rancangan "Roller Test" diganti Performance Test (Dyno) karena stasiun itu tidak ada pada daftar 10 stasiun.</li>',
         '<li>Pembanding "7 hari sebelumnya" pada pesan memakai 7 hari kerja berdata, sedangkan Q3 di laporan memakai dua jendela 7 hari yang digabung. Keduanya didefinisikan di <code>kpi_and_messages.md</code>.</li>',
         '<li>Pengiriman disimulasikan dengan <code>DryRunSender</code>; log pengiriman (<code>delivery_log</code>) dibuat dari replay seluruh periode memakai kode bot yang sama dengan kode produksi.</li>',
         f'<li>Uji skenario data hilang dan gagal kirim ({I(len(sc))} skenario), uji perintah ({I(len(ct))}), dan cek silang pesan bot vs SQL vs Excel ({I(len(cx))} tanggal) ditambahkan di luar rancangan.</li></ul></div>',
         '<div class="card"><h4>Perubahan nama dan lokasi file terhadap rancangan</h4>',
         table(["Rancangan", "Realisasi"], [[f"<code>{a}</code>" if a != "(tidak ada)" else "(tidak ada di rancangan)", ", ".join(f"<code>{x}</code>" for x in b.split(", "))] for a, b in renames]) + '</div>')

# ---------------------------------------------------------------- 6. output
chk_ = lambda rel: (REPO / rel).exists()
outs = [("Bot Telegram", "Utama", PART("Sebagian"), "Kode laporan harian, alert, dan perintah berjalan dan diuji dalam mode dry-run. Belum ada bot terdaftar, grup demo, atau screenshot Telegram nyata"),
        ("Pipeline terjadwal", "Utama", PART("Sebagian"), "<code>daily.yml</code> ditulis dan penanganan data terlambat, kosong, serta gagal kirim diuji lewat replay. Workflow belum dijalankan di GitHub"),
        ("Evaluasi aturan alert", "Utama", OK("Tercapai"), "<code>alert_eval_*.csv</code>, <code>alert_rule_performance.csv</code>, dan Bagian 2.3 sampai 2.5; rekomendasi ambang dengan alasannya"),
        ("Database & query SQL", "Utama", OK("Tercapai"), f"<code>kpi_bot.duckdb</code> (dibuat ulang, tidak di-commit) dan {I(nsql)} file SQL dengan view KPI"),
        ("Dashboard pendamping", "Utama", PART("Sebagian"), "<code>streamlit/app.py</code> (3 halaman) diuji lokal dengan AppTest. Link publik belum ada"),
        ("Laporan temuan & rekomendasi", "Utama", OK("Tercapai"), "<code>README.md</code> dan halaman ini; angka dampak berlabel estimated"),
        ("Repositori GitHub", "Utama", PART("Sebagian"), f"Kode, workflow, {I(ntest)} berkas tes, dan contoh pesan siap; di branch <code>project-23-build</code>, belum digabung ke <code>main</code>"),
        ("Slide presentasi", "Opsional", NO("Tidak dibuat"), "Opsional, tidak dibuat")]
nU = [o for o in outs if o[1] == "Utama"]
cnt = lambda s: sum(1 for o in nU if s in o[2])
docs = [("docs/kpi_and_messages.md", "Definisi KPI, isi pesan, perintah", "project/docs/kpi_and_messages.md"), ("config/alert_rules.yaml", "Aturan alert dan perilaku data hilang", "project/config/alert_rules.yaml"),
        ("scripts/generate_data.py", "Generator data", "project/code/1-data-preparation/python/01_generate_data.py"), ("data/raw/*.csv", "Data mentah (tidak di-commit)", "project/data/raw"),
        ("data/ground_truth.json", "Kejadian yang ditanam", "project/data/ground_truth.json"), ("production.duckdb", "File database (tidak di-commit)", "project/kpi_bot.duckdb"),
        ("bot/report.py", "Pipeline laporan harian dan alert", "project/code/2-analysis/python/bot/report.py"), ("bot/commands.py", "Perintah bot", "project/code/2-analysis/python/bot/commands.py"),
        (".github/workflows/daily.yml", "Jadwal harian", ".github/workflows/daily.yml"), ("notebooks/alert_evaluation.ipynb", "Notebook", "project/results/3-presentation/analysis.ipynb"),
        ("outputs/crosscheck.xlsx", "Cek silang", "project/results/2-analysis/crosscheck.xlsx"), ("dashboard/app.py", "Dashboard", "project/code/3-presentation/streamlit/app.py"),
        ("docs/screenshots/", "Contoh pesan bot (teks dan grafik dry-run)", "project/docs/samples"), ("requirements.txt", "Paket Python", "project/requirements.txt"),
        ("README.md", "Laporan temuan", "README.md"), ("index.html", "Pengalihan ke design-and-report/", "index.html"), ("slides/presentation.pdf", "Slide", "slides/presentation.pdf")]
stat_doc = lambda rel: PART("Tidak di-commit") if ("duckdb" in rel or rel.endswith("raw")) else (PART("Sebagian") if rel.endswith("samples") else (OK("Ada") if chk_(rel) else NO("Belum ada")))
rp6 = mk(f'<div class="card"><p><b>Jawaban singkat:</b> {I(cnt("Tercapai"))} dari {I(len(nU))} output Utama tercapai penuh dan {I(cnt("Sebagian"))} sebagian (bot Telegram nyata, pipeline di GitHub Actions, dashboard ter-deploy, dan merge ke main belum ada). '
         f'Slide Opsional tidak dibuat.</p></div>',
         table(["Output", "Label", "Status", "Bukti"], [[f"<b>{a}</b>", b, c, d] for a, b, c, d in outs]),
         '<div class="card"><h4>Daftar dokumen pada rancangan vs repositori</h4>',
         table(["Dokumen (rancangan)", "Isi", "Lokasi sekarang", "Status"], [[f"<code>{a}</code>", b, f"<code>{c}</code>", stat_doc(c)] for a, b, c in docs]),
         '<p>Data mentah, data bersih, dan <code>kpi_bot.duckdb</code> tidak di-commit karena bisa dibuat ulang oleh skrip. Hanya <code>ground_truth.json</code> di folder data yang di-commit.</p></div>')

# ---------------------------------------------------------------- 7. kesimpulan
crit = [("1. Kedelapan pertanyaan Utama terjawab dengan angka", OK("Tercapai"), "Q1, Q2, Q4, Q5, Q7, Q8, Q10, Q12 terjawab (bagian 2); beberapa dengan catatan"),
        ("2. Ambang terpilih menangkap ketiga kejadian dengan alert palsu paling banyak 2 dalam 3 bulan", OK("Tercapai"),
         f"R1 {I(ap.loc['R1'].false_alerts)} palsu, R2 {I(ap.loc['R2'].false_alerts)}, R3 {I(ap.loc['R3'].false_alerts)}; ketiga penurunan tertangkap. Dipilih dan dinilai pada data yang sama"),
        ("3. Laporan terkirim tepat waktu minimal 95% hari uji, dan bot memberi tahu saat data terlambat atau kosong", PART("Sebagian"),
         f"{P(ds['on-time delivery rate bot (data sudah ada)'] / 100, 1)} bila data sudah ada saat run, {P(ds['on-time rate ujung ke ujung (hari dengan data tiba)'] / 100, 1)} ujung ke ujung; jeda dan kegagalan adalah simulasi; pemberitahuan diuji"),
        ("4. Angka pesan bot sama dengan SQL dan Excel pada sampel", OK("Tercapai"), f"{I(cx_pass.sum())} dari {I(len(cx))} tanggal lulus"),
        ("5. Tidak ada token atau secret di kode dan riwayat repositori", OK("Tercapai"), f"{I(sec['berkas terlacak yang memuat pola token'])} temuan; belum ada token sungguhan"),
        ("6. Checklist standar (pertanyaan bisnis, cleaning, SQL, dashboard ter-deploy, README)", PART("Sebagian"), "Semua ada kecuali dashboard ter-deploy")]
ncr = sum(1 for c in crit if ">Tercapai<" in c[1])
rp7 = mk(
    '<div class="card"><h4>7.1 Hasil analisis: jawaban atas pertanyaan utama</h4>',
    '<p><i>Bagaimana mengirim ringkasan KPI harian (yield, NG rate, rework rate per stasiun) beserta grafik ke Telegram secara otomatis, dengan alert yang menangkap masalah nyata tanpa terlalu banyak alarm palsu?</i></p><ul class="tight">',
    f'<li><b>Laporan harian:</b> pipeline menghitung KPI dari view SQL, menyusun pesan dengan grafik, dan mengirimnya lewat pengirim yang bisa diganti. Pada replay {I(n_days)} hari, {I(n_daily)} laporan harian dan {I(n_alert)} alert dibuat dalam mode dry-run. Pengiriman ke Telegram sungguhan belum dilakukan.</li>',
    f'<li><b>Alert yang menangkap masalah nyata:</b> yield lini di bawah rata-rata 20 hari − {D(rs_full.param, 1)}σ (R1) dan yield stasiun di bawah rata-rata − {D(st_full.param, 1)}σ (R2) menangkap ketiga penurunan dengan 0 alert palsu; R3 (lonjakan defect) {I(ap.loc["R3"].true_alerts)} benar dari {I(ap.loc["R3"].alerts)}. Ambang tetap menghasilkan {I(fx_full.fp_days)} alert palsu.</li>',
    f'<li><b>Keandalan:</b> {P(ds["on-time delivery rate bot (data sudah ada)"] / 100, 1)} tepat waktu bila data sudah ada; data terlambat dan kosong ditangani dengan pemberitahuan, cek ulang tiap jam, dan batas {cs("14:00")}.</li>',
    f'<li><b>Angka benar:</b> {I(cx_pass.sum())} dari {I(len(cx))} tanggal sampel sama di pesan, SQL, dan Excel.</li></ul></div>',
    '<div class="card"><h4>7.2 Impact</h4><ul class="tight">',
    f'<li><b>Nilai praktis (estimated):</b> sekitar {I(imp.loc["menit dihemat per laporan"].value)} menit per laporan, atau {D(imp.loc["jam kerja dihemat per tahun"].value, 0)} jam kerja per tahun, bila penyusunan manual memang sekitar {I(imp.loc["waktu manual per laporan (menit)"].value)} menit. Alert datang di pagi hari berikutnya, sekitar {D(lag_ok.hours_earlier_than_manual.min(), 0)} jam lebih awal daripada laporan manual yang sampai siang (asumsi).</li>',
    '<li><b>Nilai analitis:</b> pemilihan ambang dari data menunjukkan bahwa ambang tetap tampak masuk akal tetapi menghasilkan banyak alarm palsu, dan bahwa evaluasi yang melewatkan masa pemanasan terlalu optimistis.</li>',
    '<li><b>Nilai portofolio:</b> pipeline lengkap dari data simulasi dengan ground truth sampai bot dry-run, evaluasi alert, uji skenario, cek silang tiga sumber, dashboard, dan notebook.</li>',
    '<li><b>Belum terukur:</b> dampak pada supervisor nyata, jumlah alarm yang diabaikan, dan waktu tanggap. Tidak ada data pabrik.</li></ul></div>')
rp7 += ('<div class="card"><h4>7.3 Success criteria</h4>' + table(["Kriteria (Design Project, bagian 8)", "Status", "Bukti"], [[a, b, c] for a, b, c in crit])
        + f'<p><b>Hasil:</b> {I(ncr)} dari {I(len(crit))} kriteria tercapai, {I(len(crit) - ncr)} sebagian.</p></div>')
rp7 += mk('<div class="card"><h4>7.4 Rekomendasi</h4><ul class="tight">',
          f'<li>Pakai batas yang mengikuti rata-rata 20 hari (R1 dan R2) sebagai alert utama, bukan ambang tetap; kirim R3 sebagai informasi tambahan karena presisinya {P(ap.loc["R3"].precision, 0)}.</li>',
          '<li>Jangan mengaktifkan alert yield atau defect sebelum 20 hari data tersedia; selama masa pemanasan kirim laporan harian saja.</li>',
          f'<li>Tetap kirim pesan walau data hilang: pemberitahuan "belum masuk" dan pesan akhir pukul {cs("14:00")} membedakan lini aman dari pipeline rusak.</li>',
          '<li>Sebelum dipakai nyata: daftarkan bot, jalankan workflow di GitHub Actions dengan secrets, dan uji ke grup Telegram sungguhan.</li></ul></div>')
rp7 += mk('<div class="card"><h4>7.5 Saran perbaikan</h4><ul class="tight">',
          '<li>Uji aturan alert pada kejadian yang tidak dipakai untuk memilih parameter (misalnya dengan seed data lain atau data pabrik) agar tidak in-sample.</li>',
          '<li>Ukur waktu penyusunan laporan manual dengan stopwatch pada beberapa hari, dan ukur jeda serta kegagalan GitHub Actions dari beberapa minggu run nyata.</li>',
          '<li>Hubungkan <code>handle()</code> ke polling Telegram dan tambah screenshot pesan nyata; tambah alert per jam untuk kejadian yang tidak perlu menunggu pagi.</li>',
          '<li>Deploy dashboard ke Streamlit Community Cloud dan baca data dari warehouse (Project 27) alih-alih CSV.</li></ul></div>')
rp7 += mk('<div class="card"><h4>7.6 Batasan</h4><ul class="tight">',
          '<li>Semua temuan berasal dari data simulasi; kejadian yang ditemukan adalah kejadian yang ditanam sendiri.</li>',
          f'<li>Hanya {I(ev_n)} penurunan yield dan satu lonjakan defect yang dipakai menilai alert; parameter dipilih dan dinilai pada data yang sama.</li>',
          '<li>Bot tidak pernah mengirim ke Telegram sungguhan; kode pengirim hanya diuji dengan transport palsu. Workflow GitHub Actions belum dijalankan dan dashboard belum di-deploy.</li>',
          '<li>Jeda run, kegagalan run, dan latency pengiriman adalah simulasi; batas tepat waktu, jam akhir shift, dan jam laporan manual adalah asumsi. Waktu manual per laporan adalah estimasi.</li>',
          '<li>Alert dicek sekali sehari, bukan real-time, dan hanya menunjukkan kapan yield turun, bukan penyebabnya. Cek silang Excel dihitung oleh LibreOffice, bukan Microsoft Excel.</li>',
          '<li>Tidak ada masalah lisensi dataset (data buatan sendiri). Slide presentasi (Opsional) tidak dibuat.</li></ul></div>')

evq = [("1", "rp1", "Data yang didapat", OK("Didapat"), f"{I(dbt.production_daily)} baris produksi, {I(dbt.defect_log)} baris defect, {I(dq.detected.sum())} baris kotor ditangani"),
       ("2", "rp2", "Business question terjawab?", OK(f"{len(QT)} dari {len(QT)}"), f"Semua terjawab ({npr['Utama']} Utama, {npr['Pendukung']} Pendukung, {npr['Tambahan']} Tambahan); {nw} dengan catatan ({wtxt})"),
       ("3", "rp3", "Dataset sesuai?", PART("Sesuai + penyesuaian"), "Data buatan sesuai rancangan; Roller Test diganti Dyno, log pengiriman hasil replay"),
       ("4", "rp4", "Tools sesuai?", PART("Sesuai + penyesuaian"), "python-telegram-bot diganti HTTP langsung; Actions dan Streamlit belum dijalankan"),
       ("5", "rp5", "Alur sesuai?", PART("Sesuai + penyesuaian"), "12 langkah dijalankan; 4 sebagian; evaluasi masa pemanasan ditambahkan"),
       ("6", "rp6", "Output tercapai?", PART(f"{cnt('Tercapai')} penuh, {cnt('Sebagian')} sebagian"), f"{cnt('Tercapai')} dari {len(nU)} output Utama penuh"),
       ("7", "rp7", "Kesimpulan", OK("Tersedia"), f"Hasil analisis, Impact, {len(crit)} kriteria sukses, rekomendasi, saran perbaikan, batasan")]
evq_html = '<div class="scroll"><table class="evq"><tr><th>No</th><th>Pertanyaan evaluasi</th><th>Verdict</th><th>Ringkasan</th></tr>' + "".join(
    f'<tr><td><span class="en">{n}</span></td><td><a href="#{h}">{t}</a></td><td>{v}</td><td>{s}</td></tr>' for n, h, t, v, s in evq) + "</table></div>"
H = lambda i, t, sm, body: f'\n<h2 id="rp{i}">{i}. {t}<small>{sm}</small></h2>\n{body}\n'
report = mk(
    '<div class="pane" id="report" data-tab="report" hidden>\n',
    f'<div class="callout g"><h4>Report Project versi 2: evaluasi hasil terhadap Design Project</h4><p>Halaman ini disusun sebagai 7 jawaban atas pertanyaan evaluasi. Tabel dan grafik dibuat otomatis dari hasil query SQL (DuckDB) dan skrip Python pada data simulasi. '
    f'Pesan bot dicek silang dengan SQL dan Excel ({I(cx_pass.sum())} dari {I(len(cx))} tanggal). Angka pada teks diaudit terhadap file di <code>project/results/</code>: @@AUDIT@@ angka diperiksa tanpa selisih. '
    'Semua angka bersumber dari data simulasi buatan sendiri dan menguji metode, bukan kondisi pabrik; bot tidak mengirim ke Telegram sungguhan. Rancangan lengkap ada di tab <a href="#design">Design Project</a>.</p></div>\n',
    evq_html,
    H(1, "Data yang berhasil didapatkan", "Isi data mentah, tabel di database, dan data hasil analisis", rp1),
    H(2, "Apakah business question terjawab?", f"{len(QT)} pertanyaan pada Design Project, dijawab dengan data", rp2),
    H(3, "Apakah dataset sesuai dengan Design Project?", "Perbandingan rancangan dengan realisasi", rp3),
    H(4, "Apakah tools yang digunakan sesuai?", "Perbandingan rancangan dengan eksekusi", rp4),
    H(5, "Apakah alur pengerjaan sesuai dengan Design Project?", f"{len(steps)} langkah rancangan vs yang dijalankan", rp5),
    H(6, "Apakah project output tercapai?", "Output pada Design Project, bagian 7", rp6),
    H(7, "Kesimpulan", "Hasil analisis, Impact, success criteria, rekomendasi, saran perbaikan, dan batasan", rp7),
    '</div>\n')

# ---------------------------------------------------------------- audit angka
STATIC = {str(i) for i in range(0, 32)} | {f"{i:02d}" for i in range(0, 60)} | {"100", "80", "60", "95", "75", "4.500", "6.000", "14", "50", "1,5", "2,0", "3,0", "0,05", "2026", "25", "20", "9", "7", "8", "13", "125", "92,3", "95,1"}   # 125 = nama model Bebek 125; 92,3 dan 95,1 = kutipan contoh dari halaman Design
STATIC |= {f"{a}.{b}" for a in range(1, 10) for b in range(1, 10)}
n_tok, bad = audit(report, STATIC)
manual = [("seluruh CSV hasil terdokumentasi", not miss), ("deteksi data kotor sempurna", (dq.recall == 1).all() and (dq.precision == 1).all()),
          ("cek silang semua PASS", bool(cx_pass.all())), ("semua skenario dan perintah lulus", (sc.result == "lulus").all() and (ct.result == "lulus").all()),
          ("R1 dan R2 tanpa alert palsu, ketiga penurunan tertangkap", ap.loc["R1"].false_alerts == 0 and ap.loc["R2"].false_alerts == 0 and ap.loc["R1"].events_caught == 3 and ap.loc["R2"].events_caught == 3),
          ("R3 menangkap lonjakan dan tiga penurunan", bool(dsel.spike_caught) and dsel.drops_caught == 3),
          ("ambang tetap terbaik melebihi batas 2 alert palsu", fx_full.fp_days > 2), ("aturan rolling terpilih tanpa alert palsu", rs_full.fp_days == 0),
          ("catatan hanya Q4, Q5, Q7, Q8, Q9, Q10, Q11", WARN == {4, 5, 7, 8, 9, 10, 11}), ("jumlah pertanyaan 12 (8 Utama, 3 Pendukung, 1 Tambahan)", len(QT) == 12 and npr == {"Utama": 8, "Pendukung": 3, "Tambahan": 1}),
          ("lonjakan tidak membunyikan R1", not spike_r1), ("langkah rancangan = 12", len(steps) == 12), ("jumlah pertanyaan unik pada bagian 2 = 12", qn_all == list(range(1, 13))),
          ("hari dengan data = 74 dari 75", n_days == 74 and ndays_cal == 75), ("tidak ada token di repositori", sec.iloc[0] == 0 and sec.iloc[1] == 0),
          ("semua laporan tepat waktu + pengecualian = hari kerja", int(dout.on_time.sum()) + len(fail_days) + len(late_days) + len(empty_days) == len(dout))]
assert all(v for _, v in manual), [k for k, v in manual if not v]
if bad:
    print("TOKEN TIDAK TERDAFTAR:", bad)
    sys.exit(1)
report = report.replace("@@AUDIT@@", I(n_tok) + f" (ditambah {I(len(manual))} klaim manual)")

# ---------------------------------------------------------------- rakit halaman
v1 = (HERE / "page_v1.html").read_text(encoding="utf-8")
a = v1.index('<div class="pane" id="report"')
b = v1.index("</main>")
design_pane = v1[v1.index('<div class="pane" id="design"'):a]
nav_old = re.search(r'<nav aria-label="Project navigation">.*?</nav>', v1, re.S).group(0)
btn = lambda t: re.search(rf'<button type="button" class="tab[^"]*" data-t="{t}".*?</button>', nav_old, re.S).group(0)
design_links = re.search(r'<div class="links" data-tab="design">.*?</div>', nav_old, re.S).group(0)
report_links = ('<div class="links" data-tab="report" hidden>' + "".join(f'<a href="#rp{i}">{t}</a>' for i, t in
               enumerate(["Data", "Business Questions", "Dataset", "Tools", "Alur Kerja", "Project Output", "Kesimpulan"], 1)) + "</div>")
nav_new = f'<nav aria-label="Project navigation">{btn("design")}{btn("report")}{design_links}{report_links}</nav>'
css = (HERE / "report.css").read_text(encoding="utf-8")
html = v1[:a] + report + v1[b:]
html = html.replace(nav_old, nav_new)
i = html.rindex("</style>")
html = html[:i] + css + html[i:]
out = REPO / "design-and-report" / "index.html"
out.write_text(html, encoding="utf-8")
assert design_pane == html[html.index('<div class="pane" id="design"'):html.index('<div class="pane" id="report"')], "pane Design berubah"
print(f"index.html {len(html) / 1024:.0f} KB; {n_tok} angka diaudit; {len(manual)} klaim manual; pane Design identik")
