"""Tahap 2 / langkah 04: KPI harian, Pareto, dan perbandingan 7 hari (Q1, Q2, Q3). Semua dari view DuckDB.

Keluaran (results/2-analysis/): kpi_station_daily.csv, kpi_line_daily.csv, kpi_station_period.csv, pareto_period.csv,
pareto_latest_7d.csv, pareto_by_day_sample.csv, period_compare_daily.csv
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import DB_PATH, RES_ANALYSIS  # noqa: E402


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    q = lambda s: con.execute(s).df()
    q("SELECT strftime(date,'%Y-%m-%d') AS date, station, seq, input_qty, ok_qty, ng_qty, round(fpy,5) AS fpy, round(ng_rate,5) AS ng_rate, "
      "rework_qty, scrap_qty, round(rework_rate,5) AS rework_rate FROM v_kpi_station_daily ORDER BY date, seq").to_csv(RES_ANALYSIS / "kpi_station_daily.csv", index=False)
    line = q("""SELECT strftime(l.date,'%Y-%m-%d') AS date, l.start_qty, l.good_qty, round(l.line_yield,5) AS line_yield, l.ng_total,
                       r.rw AS rework_qty, round(r.rw*1.0/l.start_qty,5) AS rework_rate
                FROM v_line_daily l JOIN (SELECT date, SUM(rework_qty) rw FROM v_kpi_station_daily GROUP BY 1) r USING (date) ORDER BY 1""")
    line.to_csv(RES_ANALYSIS / "kpi_line_daily.csv", index=False)
    sp = q("""SELECT station, seq, SUM(input_qty) AS input_qty, SUM(ng_qty) AS ng_qty, round(SUM(ok_qty)*1.0/SUM(input_qty),5) AS fpy,
                     round(SUM(ng_qty)*1.0/SUM(input_qty),5) AS ng_rate, round(SUM(rework_qty)*1.0/SUM(input_qty),5) AS rework_rate,
                     round(SUM(scrap_qty)*1.0/SUM(input_qty),5) AS scrap_rate,
                     round(SUM(ng_qty)*1.0/(SELECT SUM(ng_qty) FROM v_kpi_station_daily),4) AS share_of_line_ng
              FROM v_kpi_station_daily GROUP BY 1,2 ORDER BY seq""")
    sp["rank_worst_fpy"] = sp["fpy"].rank().astype(int)
    sp.to_csv(RES_ANALYSIS / "kpi_station_period.csv", index=False)
    par = q("""SELECT defect_code, defect_name, station, SUM(qty) AS qty FROM v_defect_daily GROUP BY 1,2,3 ORDER BY qty DESC""")
    par["share"] = (par["qty"] / par["qty"].sum()).round(4)
    par["cum_share"] = par["share"].cumsum().round(4)
    par.to_csv(RES_ANALYSIS / "pareto_period.csv", index=False)
    dates = line["date"].tolist()
    last7 = dates[-7:]
    inlist = ",".join(f"'{d}'" for d in last7)
    q(f"SELECT defect_code, defect_name, station, SUM(qty) AS qty FROM v_defect_daily WHERE strftime(date,'%Y-%m-%d') IN ({inlist}) GROUP BY 1,2,3 ORDER BY qty DESC LIMIT 10"
      ).to_csv(RES_ANALYSIS / "pareto_latest_7d.csv", index=False)
    samp = ["2026-03-27", "2026-03-30", "2026-05-04", "2026-06-02"]
    inl = ",".join(f"'{d}'" for d in samp)
    q(f"""SELECT strftime(date,'%Y-%m-%d') AS date, defect_name, station, SUM(qty) AS qty,
                 ROW_NUMBER() OVER (PARTITION BY date ORDER BY SUM(qty) DESC, defect_name) AS rnk
          FROM v_defect_daily WHERE strftime(date,'%Y-%m-%d') IN ({inl}) GROUP BY date, defect_name, station""").query("rnk <= 3").to_csv(RES_ANALYSIS / "pareto_by_day_sample.csv", index=False)
    rows = []
    for i in range(14, len(dates)):
        cur, prev = dates[i - 6:i + 1], dates[i - 13:i - 6]
        yc = line[line.date.isin(cur)]; yp = line[line.date.isin(prev)]
        a, b = yc.good_qty.sum() / yc.start_qty.sum(), yp.good_qty.sum() / yp.start_qty.sum()
        rows.append(dict(date=dates[i], yield_last7=round(a, 5), yield_prev7=round(b, 5), delta_pp=round((a - b) * 100, 2)))
    pd.DataFrame(rows).to_csv(RES_ANALYSIS / "period_compare_daily.csv", index=False)
    print(sp.to_string(index=False)); print(par.head(5).to_string(index=False)); print(pd.DataFrame(rows).tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
