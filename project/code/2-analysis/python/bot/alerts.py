"""Aturan alert sebagai fungsi murni di atas pandas (mudah dites). Parameter dibaca dari config/alert_rules.yaml.

Semua aturan hanya memakai data SEBELUM dan PADA hari yang dinilai (tidak melihat masa depan).
"""
import numpy as np
import pandas as pd


def _baseline(series, idx, window):
    """Rata-rata dan simpangan baku `window` hari kerja sebelum posisi idx (None jika belum cukup)."""
    if idx < window:
        return None, None
    prev = series.iloc[idx - window:idx]
    return float(prev.mean()), float(prev.std(ddof=1))


def line_alert(line, method, param, window=20):
    """line: DataFrame(date, line_yield) urut tanggal. Kembalikan Series boolean per baris (alert atau tidak)."""
    y = line["line_yield"].reset_index(drop=True)
    out = []
    for i in range(len(y)):
        if method == "fixed":
            out.append(bool(y[i] < param))
        else:
            m, s = _baseline(y, i, window)
            out.append(False if m is None else bool(y[i] < m - param * s))
    return pd.Series(out, index=line.index)


def station_alert(st, method, param, window=20):
    """st: DataFrame(date, station, fpy). Kembalikan DataFrame(date, station, alert, drop_pp)."""
    rows = []
    for station, g in st.sort_values("date").groupby("station", sort=False):
        y = g["fpy"].reset_index(drop=True)
        for i in range(len(y)):
            if method == "fixed":
                a, base = bool(y[i] < param), param
            else:
                m, s = _baseline(y, i, window)
                a, base = (False, np.nan) if m is None else (bool(y[i] < m - param * s), m)
            rows.append([g["date"].iloc[i], station, a, (base - y[i]) * 100 if base == base else np.nan])
    return pd.DataFrame(rows, columns=["date", "station", "alert", "drop_pp"])


def defect_alert(df, method, param, min_count, window=7):
    """df: DataFrame(date, defect_code, qty) harian lengkap. method 'pct': qty > (1+param)*rata-rata window hari;
    'sigma': qty > mean + param*std; 'poisson': qty > mean + param*sqrt(mean). Syarat qty >= min_count. Kembalikan DataFrame(date, defect_code, qty, baseline, alert)."""
    rows = []
    for code, g in df.sort_values("date").groupby("defect_code"):
        q = g["qty"].reset_index(drop=True)
        for i in range(len(q)):
            m, s = _baseline(q, i, window)
            if m is None:
                a = False
                m = np.nan
            elif method == "poisson":
                a = bool(q[i] > m + param * np.sqrt(max(m, 1.0)) and q[i] >= min_count)
            elif method == "pct":
                a = bool(q[i] > (1 + param) * m and q[i] >= min_count)
            else:
                a = bool(q[i] > m + param * s and q[i] >= min_count)
            rows.append([g["date"].iloc[i], code, int(q[i]), m, a])
    return pd.DataFrame(rows, columns=["date", "defect_code", "qty", "baseline", "alert"])
