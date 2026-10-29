"""Hitung KPI sebuah hari, susun pesan harian, grafik, dan evaluasi alert. Semua angka dari view DuckDB (satu sumber rumus)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .alerts import defect_alert, line_alert, station_alert  # noqa: E402

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + "%"


def pp(x, d=1):
    s = f"{x * 100:+.{d}f}".replace(".", ",").replace("-", "−")
    return s + " pp"


def tgl(d):
    d = pd.Timestamp(d)
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def _iso(d):
    return pd.Timestamp(d).strftime("%Y-%m-%d")


def available_dates(con, up_to):
    return [r[0] for r in con.execute("SELECT strftime(date,'%Y-%m-%d') FROM v_line_daily WHERE date <= ? ORDER BY date", [_iso(up_to)]).fetchall()]


def load_kpis(con, d):
    """KPI hari d + pembanding 7 hari kerja berdata sebelumnya. Kembalikan dict (angka mentah, belum diformat)."""
    d = _iso(d)
    dates = available_dates(con, d)
    if d not in dates:
        raise ValueError(f"tidak ada data untuk {d}")
    prev7 = dates[max(0, dates.index(d) - 7):dates.index(d)]
    line = con.execute("SELECT line_yield, start_qty, good_qty FROM v_line_daily WHERE date = ?", [d]).fetchone()
    base = con.execute("SELECT SUM(good_qty)*1.0/SUM(start_qty) FROM v_line_daily WHERE strftime(date,'%Y-%m-%d') IN (SELECT UNNEST(?))", [prev7]).fetchone()[0] if prev7 else None
    st = con.execute("SELECT station, seq, fpy, ng_rate, ng_qty, rework_rate, rework_qty FROM v_kpi_station_daily WHERE date = ? ORDER BY seq", [d]).df()
    # pembanding per stasiun: rata-rata yield stasiun pada 20 hari berdata sebelumnya
    prev20 = dates[max(0, dates.index(d) - 20):dates.index(d)]
    sb = con.execute("SELECT station, SUM(ok_qty)*1.0/SUM(input_qty) AS base FROM v_station_daily WHERE strftime(date,'%Y-%m-%d') IN (SELECT UNNEST(?)) GROUP BY 1", [prev20]).df() if prev20 else pd.DataFrame(columns=["station", "base"])
    st = st.merge(sb, on="station", how="left")
    st["delta"] = st["fpy"] - st["base"]
    rw = con.execute("SELECT SUM(rework_qty) FROM v_kpi_station_daily WHERE date = ?", [d]).fetchone()[0]
    top1 = con.execute("SELECT defect_name, station, SUM(qty) q FROM v_defect_daily WHERE date = ? GROUP BY 1,2 ORDER BY q DESC, defect_name LIMIT 3", [d]).df()
    top7 = con.execute("SELECT defect_name, station, SUM(qty) q FROM v_defect_daily WHERE strftime(date,'%Y-%m-%d') IN (SELECT UNNEST(?)) GROUP BY 1,2 ORDER BY q DESC, defect_name LIMIT 3", [(prev7 + [d])[-7:]]).df()
    return dict(date=d, line_yield=line[0], start_qty=line[1], good_qty=line[2], base7=base,
                delta7=None if base is None else line[0] - base, stations=st, rework_total=int(rw or 0),
                rework_rate=(rw or 0) / line[1], top_day=top1, top_7d=top7, n_prev=len(prev7))


def _top_text(df):
    return ", ".join(f"{r.defect_name} ({int(r.q)})" for r in df.itertuples()) or "-"


def build_message(k, alerts=None, late=False):
    st = k["stations"]
    worst = st.sort_values("fpy").iloc[0]
    drop = st.sort_values("delta").iloc[0] if st["delta"].notna().any() else None
    lines = [f"Laporan {tgl(k['date'])}" + (" (terlambat: data baru masuk)" if late else ""),
             f"Yield lini {pct(k['line_yield'])}" + (f" ({pp(k['delta7'])} vs 7 hari sebelumnya)" if k["delta7"] is not None else "")
             + f" · Unit OK {int(k['good_qty'])} dari {int(k['start_qty'])}",
             f"Rework lini {pct(k['rework_rate'])} · NG total {int(k['start_qty'] - k['good_qty'])} unit",
             f"Yield terendah: {worst.station} {pct(worst.fpy)}"]
    if drop is not None and drop.delta < -0.01:
        lines.append(f"Turun paling jauh vs rata-rata 20 hari: {drop.station} {pp(drop.delta)}")
    lines.append(f"Top NG hari ini: {_top_text(k['top_day'])}")
    lines.append(f"Top NG 7 hari: {_top_text(k['top_7d'])}")
    if alerts:
        lines.append("Ada alert, lihat pesan berikutnya.")
    return "\n".join(lines)


def evaluate_alerts(con, d, rules):
    """Evaluasi aturan aktif untuk hari d memakai data sampai d. rules: DataFrame alert_rule. Kembalikan list dict alert."""
    d = _iso(d)
    out = []
    dates = available_dates(con, d)
    for r in rules[rules["active"]].itertuples():
        w = int(r.window_days)
        if r.scope == "line":
            tail = con.execute("SELECT strftime(date,'%Y-%m-%d') AS date, line_yield FROM v_line_daily WHERE date <= ? ORDER BY date", [d]).df().tail(w + 1).reset_index(drop=True)
            a = line_alert(tail, r.method, r.threshold, w)
            if len(tail) == w + 1 and a.iloc[-1] and tail["date"].iloc[-1] == d:
                base = tail["line_yield"].iloc[:-1].mean()
                out.append(dict(rule_id=r.rule_id, scope="line", subject="Lini", value=tail["line_yield"].iloc[-1], baseline=base,
                                text=f"[{r.rule_id}] Yield lini {pct(tail['line_yield'].iloc[-1])} di bawah batas ({pp(tail['line_yield'].iloc[-1] - base)} vs rata-rata {w} hari {pct(base)})"))
        elif r.scope == "station":
            st = con.execute("SELECT strftime(date,'%Y-%m-%d') AS date, station, fpy, seq FROM v_station_daily WHERE date <= ? ORDER BY date, seq", [d]).df()
            st = st[st["date"].isin(dates[-(w + 1):])]
            a = station_alert(st, r.method, r.threshold, w)
            for x in a[(a["alert"]) & (a["date"] == d)].itertuples():
                v = st[(st.station == x.station) & (st.date == d)]["fpy"].iloc[0]
                out.append(dict(rule_id=r.rule_id, scope="station", subject=x.station, value=v, baseline=v + x.drop_pp / 100,
                                text=f"[{r.rule_id}] {x.station}: yield {pct(v)}, turun {str(round(x.drop_pp, 1)).replace('.', ',')} pp dari rata-rata {w} hari"))
        elif r.scope == "defect":
            dd = con.execute("SELECT strftime(date,'%Y-%m-%d') AS date, defect_code, qty FROM v_defect_daily WHERE date <= ?", [d]).df()
            use = dates[-(w + 1):]
            codes = con.execute("SELECT defect_code FROM dim_defect").df()["defect_code"].tolist()
            grid = pd.MultiIndex.from_product([use, codes], names=["date", "defect_code"])
            full = dd.set_index(["date", "defect_code"])["qty"].reindex(grid, fill_value=0).reset_index()
            a = defect_alert(full, r.method, r.threshold, int(r.min_count), w)
            names = dict(con.execute("SELECT defect_code, defect_name FROM dim_defect").fetchall())
            for x in a[(a["alert"]) & (a["date"] == d)].itertuples():
                out.append(dict(rule_id=r.rule_id, scope="defect", subject=x.defect_code, value=x.qty, baseline=x.baseline,
                                text=f"[{r.rule_id}] Lonjakan {names[x.defect_code]} ({x.defect_code}): {x.qty} unit vs rata-rata {w} hari {str(round(x.baseline, 1)).replace('.', ',')}"))
    return out


def build_alert_message(k, alerts):
    return f"ALERT {tgl(k['date'])}\n" + "\n".join(a["text"] for a in alerts) + "\nAlert menunjukkan kapan, bukan kenapa. Cek lapangan."


def render_chart(con, d, path, days=14):
    """Grafik 2 panel: tren yield lini (days hari) dan yield stasiun hari d vs rata-rata 20 hari sebelumnya."""
    d = _iso(d)
    k = load_kpis(con, d)
    ts = con.execute("SELECT strftime(date,'%m-%d') AS t, line_yield FROM v_line_daily WHERE date <= ? ORDER BY date", [d]).df().tail(days)
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.2, 1]})
    ax[0].plot(ts["t"], ts["line_yield"] * 100, marker="o", color="#1d4e89")
    ax[0].set_title(f"Yield lini {days} hari terakhir (%)", fontsize=10)
    ax[0].tick_params(axis="x", rotation=60, labelsize=7)
    ax[0].grid(alpha=.3)
    st = k["stations"]
    y = range(len(st))
    ax[1].barh(list(y), st["fpy"] * 100, color="#1d4e89")
    ax[1].scatter(st["base"] * 100, list(y), color="#e07b00", zorder=3, label="rata-rata 20 hari")
    ax[1].set_yticks(list(y)); ax[1].set_yticklabels(st["station"], fontsize=7); ax[1].invert_yaxis()
    ax[1].set_xlim(92, 100); ax[1].set_title("Yield stasiun hari ini (%)", fontsize=10); ax[1].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
