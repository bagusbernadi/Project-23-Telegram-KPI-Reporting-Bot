"""Dashboard Streamlit (3 halaman): KPI harian, Alert, Pengiriman bot. Semua data simulasi.
Jalankan dari folder project/:  streamlit run code/3-presentation/streamlit/app.py
Membaca CSV ringkas di results/3-presentation/ (tidak perlu database)."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RES = Path(__file__).resolve().parents[3] / "results" / "3-presentation"
st.set_page_config(page_title="Project 23: Telegram KPI Reporting Bot", layout="wide")
BLUE, ORANGE, GREY = "#1A73E8", "#E8710A", "#9AA0A6"


@st.cache_data
def load():
    return (pd.read_csv(RES / "dash_station_daily.csv", parse_dates=["date"]), pd.read_csv(RES / "dash_line_daily.csv", parse_dates=["date"]),
            pd.read_csv(RES / "dash_alerts.csv", parse_dates=["report_date"]), pd.read_csv(RES / "dash_delivery.csv", parse_dates=["sent_at", "report_date"]),
            pd.read_csv(RES / "dash_rules.csv"))


stn, line, alerts, deliv, rules = load()
st.sidebar.header("Filter")
dmin, dmax = line.date.min().date(), line.date.max().date()
rng = st.sidebar.date_input("Rentang tanggal produksi", (dmin, dmax), min_value=dmin, max_value=dmax)
page = st.sidebar.radio("Halaman", ["1. KPI harian", "2. Alert", "3. Pengiriman bot"])
st.sidebar.caption("Data simulasi buatan sendiri. Jeda run dan latency pengiriman adalah simulasi.")
if not (isinstance(rng, (tuple, list)) and len(rng) == 2):
    st.info("Pilih tanggal awal dan akhir."); st.stop()
a, b = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
L, S = line[(line.date >= a) & (line.date <= b)], stn[(stn.date >= a) & (stn.date <= b)]
if L.empty:
    st.warning("Tidak ada data pada rentang ini."); st.stop()
st.title("Project 23: Telegram Bot Automated KPI Reporting")
st.caption("Lini perakitan sepeda motor, 10 stasiun, 3 model, 2 shift. Hari tanpa data tidak muncul pada grafik.")

if page.startswith("1"):
    c = st.columns(4)
    y = L.good_qty.sum() / L.start_qty.sum()
    c[0].metric("Yield lini (periode)", f"{y:.1%}")
    c[1].metric("Rework lini", f"{L.rework_qty.sum() / L.start_qty.sum():.1%}")
    c[2].metric("Unit OK", f"{int(L.good_qty.sum()):,}".replace(",", "."))
    c[3].metric("Hari ada data", len(L))
    f = go.Figure(go.Scatter(x=L.date, y=L.line_yield, mode="lines+markers", line=dict(color=BLUE)))
    f.update_layout(title="Yield lini harian", yaxis_tickformat=".0%", height=360, margin=dict(t=50, b=20))
    st.plotly_chart(f, width="stretch")
    stations = list(S.sort_values("seq").station.unique())
    pick = st.multiselect("Stasiun", stations, default=stations[:3])
    f2 = go.Figure([go.Scatter(x=S[S.station == s].date, y=S[S.station == s].fpy, name=s, mode="lines") for s in pick])
    f2.update_layout(title="Yield per stasiun", yaxis_tickformat=".1%", height=360, margin=dict(t=50, b=20))
    st.plotly_chart(f2, width="stretch")
    agg = S.groupby(["station", "seq"]).agg(i=("input_qty", "sum"), o=("ok_qty", "sum"), r=("rework_qty", "sum")).reset_index().sort_values("seq")
    agg["Yield"], agg["Rework rate"] = (agg.o / agg.i).map("{:.2%}".format), (agg.r / agg.i).map("{:.2%}".format)
    st.dataframe(agg[["station", "Yield", "Rework rate"]], hide_index=True, width="stretch")
elif page.startswith("2"):
    A = alerts[(alerts.report_date >= a) & (alerts.report_date <= b)]
    c = st.columns(3)
    c[0].metric("Alert", len(A)); c[1].metric("Sesuai kejadian yang ditanam", int(A.true_event.sum())); c[2].metric("Alert palsu", int((~A.true_event).sum()))
    f = go.Figure(go.Scatter(x=L.date, y=L.line_yield, mode="lines", line=dict(color=GREY), name="Yield lini"))
    al = A[A.scope == "line"].merge(L, left_on="report_date", right_on="date")
    f.add_trace(go.Scatter(x=al.date, y=al.line_yield, mode="markers", marker=dict(color=ORANGE, size=11), name="Alert R1"))
    f.update_layout(title="Yield lini dan hari alert lini (R1)", yaxis_tickformat=".0%", height=360, margin=dict(t=50, b=20))
    st.plotly_chart(f, width="stretch")
    st.dataframe(A.assign(report_date=A.report_date.dt.date).rename(columns={"true_event": "kejadian nyata"}), hide_index=True, width="stretch")
    st.subheader("Aturan"); st.dataframe(rules, hide_index=True, width="stretch")
else:
    D = deliv[(deliv.report_date >= a) & (deliv.report_date <= b)]
    types = st.multiselect("Jenis pesan", sorted(D.message_type.unique()), default=sorted(D.message_type.unique()))
    D = D[D.message_type.isin(types)]
    c = st.columns(3)
    c[0].metric("Pesan terkirim", int((D.status == "sent").sum())); c[1].metric("Gagal", int((D.status == "failed").sum()))
    c[2].metric("Median latency (s)", float(D[D.status == "sent"].latency_s.median()) if (D.status == "sent").any() else 0)
    D2 = D[D.status == "sent"].copy()
    D2["jam kirim"] = D2.sent_at.dt.hour + D2.sent_at.dt.minute / 60
    f = go.Figure(go.Scatter(x=D2.report_date, y=D2["jam kirim"], mode="markers", marker=dict(color=BLUE)))
    f.add_hline(y=7.25, line_dash="dash", line_color=ORANGE, annotation_text="batas tepat waktu 07:15")
    f.update_layout(title="Jam pengiriman (tanggal produksi yang dilaporkan)", yaxis_title="jam", height=360, margin=dict(t=50, b=20))
    st.plotly_chart(f, width="stretch")
    st.dataframe(D.assign(report_date=D.report_date.dt.date), hide_index=True, width="stretch")
