import pandas as pd
from bot.report import load_kpis
from common import CLEAN_DIR


def test_line_yield_matches_independent_calc(con):
    prod = pd.read_csv(CLEAN_DIR / "production_daily.csv")
    for d in ("2026-03-30", "2026-05-04", "2026-06-02"):
        p = prod[prod.date == d]
        expected = p[p.station == "Packing"].ok_first_pass.sum() / p[p.station == "Frame Welding"].input_qty.sum()
        assert abs(load_kpis(con, d)["line_yield"] - expected) < 1e-12


def test_view_invariants(con):
    df = con.execute("SELECT * FROM v_station_daily").df()
    assert ((df.ok_qty + df.ng_qty) == df.input_qty).all()
    assert df.fpy.between(0, 1).all()


def test_flow_between_stations(con):
    d = con.execute("SELECT seq, SUM(input_qty) i, SUM(ok_qty) o FROM v_station_daily WHERE date = DATE '2026-04-06' GROUP BY seq ORDER BY seq").df()
    assert (d.o.iloc[:-1].values == d.i.iloc[1:].values).all()


def test_no_future_leak_in_comparison(con):
    k1 = load_kpis(con, "2026-04-06")
    assert k1["n_prev"] == 7 and k1["date"] == "2026-04-06"
