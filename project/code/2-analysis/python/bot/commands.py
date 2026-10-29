"""Perintah bot: /yield, /top_ng, /trend 7d, /help. Fungsi murni: (con, teks, as_of) -> (balasan, path_grafik_atau_None)."""
import pandas as pd

from .report import _iso, available_dates, load_kpis, pct, pp, render_chart, tgl

HELP = ("Perintah:\n/yield - yield lini dan tiap stasiun hari terakhir\n/top_ng - 3 defect teratas hari ini dan 7 hari\n"
        "/trend 7d - tren yield lini 7 hari (juga 14d, 30d)\n/help - daftar perintah")


def handle(con, text, as_of, chart_path=None):
    parts = text.strip().split()
    cmd = parts[0].lower().split("@")[0] if parts else ""
    dates = available_dates(con, as_of)
    if cmd in ("/help", "/start"):
        return HELP, None
    if not dates:
        return "Belum ada data.", None
    d = dates[-1]
    if cmd == "/yield":
        k = load_kpis(con, d)
        rows = "\n".join(f"{r.station}: {pct(r.fpy)}" for r in k["stations"].itertuples())
        return f"Yield {tgl(d)}\nLini {pct(k['line_yield'])}\n{rows}", chart_path and render_chart(con, d, chart_path)
    if cmd == "/top_ng":
        k = load_kpis(con, d)
        f = lambda df: "\n".join(f"{i}. {r.defect_name} - {r.station}: {int(r.q)}" for i, r in enumerate(df.itertuples(), 1))
        return f"Top NG {tgl(d)}\n{f(k['top_day'])}\n\nTop NG 7 hari\n{f(k['top_7d'])}", None
    if cmd == "/trend":
        arg = parts[1].lower() if len(parts) > 1 else "7d"
        if not (arg.endswith("d") and arg[:-1].isdigit() and 2 <= int(arg[:-1]) <= 60):
            return "Format: /trend 7d (2 sampai 60 hari)", None
        n = int(arg[:-1])
        ts = con.execute("SELECT strftime(date,'%Y-%m-%d') AS d, line_yield FROM v_line_daily WHERE date <= ? ORDER BY date", [_iso(d)]).df().tail(n)
        lines = "\n".join(f"{tgl(r.d)}: {pct(r.line_yield)}" for r in ts.itertuples())
        return f"Tren yield lini {len(ts)} hari\n{lines}\nSelisih awal-akhir: {pp(ts['line_yield'].iloc[-1] - ts['line_yield'].iloc[0])}", None
    return "Perintah tidak dikenal.\n" + HELP, None
