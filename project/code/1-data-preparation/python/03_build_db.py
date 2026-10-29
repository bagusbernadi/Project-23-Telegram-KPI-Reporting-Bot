"""Tahap 1 / langkah 03: muat data bersih ke DuckDB, buat view KPI, muat tabel alert_rule dari YAML.

Keluaran: kpi_bot.duckdb (tidak di-commit); results/1-data-preparation/db_tables.csv
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import ALERT_RULES, CLEAN_DIR, DB_PATH, RES_PREP, SQL_PREP  # noqa: E402

TABLES = ["production_daily", "defect_log", "rework_log", "dim_defect", "dim_station", "data_arrival_log", "runner_log"]


def load_alert_rules():
    cfg = yaml.safe_load(ALERT_RULES.read_text(encoding="utf-8"))
    rows = [(r["rule_id"], r["kpi"], r["scope"], r["method"], float(r["threshold"]), int(r["window_days"]),
             int(r["min_count"]), bool(r["active"]), r["note"]) for r in cfg["rules"]]
    return pd.DataFrame(rows, columns=["rule_id", "kpi", "scope", "method", "threshold", "window_days", "min_count", "active", "note"])


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    for t in TABLES:
        con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto('{CLEAN_DIR / (t + '.csv')}')")
    rules = load_alert_rules()
    con.register("rules_df", rules)
    con.execute("CREATE TABLE alert_rule AS SELECT * FROM rules_df")
    con.execute("CREATE TABLE delivery_log (sent_at TIMESTAMP, message_type VARCHAR, status VARCHAR, latency_s INTEGER, error VARCHAR, report_date DATE)")
    con.execute((SQL_PREP / "01_views.sql").read_text(encoding="utf-8"))
    out = []
    for t in TABLES + ["alert_rule", "delivery_log", "v_station_daily", "v_line_daily", "v_defect_daily", "v_rework_station_daily", "v_kpi_station_daily"]:
        out.append([t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]])
    pd.DataFrame(out, columns=["object", "rows"]).to_csv(RES_PREP / "db_tables.csv", index=False)
    print(pd.DataFrame(out, columns=["object", "rows"]).to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
