"""Tahap 3 / langkah 11: ringkas hasil menjadi CSV kecil untuk dashboard (tanpa perlu database).
Keluaran: results/3-presentation/dash_station_daily.csv, dash_line_daily.csv, dash_alerts.csv, dash_delivery.csv, dash_rules.csv
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import RES_ANALYSIS, RES_PRESENT  # noqa: E402


def main():
    pd.read_csv(RES_ANALYSIS / "kpi_station_daily.csv").to_csv(RES_PRESENT / "dash_station_daily.csv", index=False)
    pd.read_csv(RES_ANALYSIS / "kpi_line_daily.csv").to_csv(RES_PRESENT / "dash_line_daily.csv", index=False)
    pd.read_csv(RES_ANALYSIS / "alert_events.csv").to_csv(RES_PRESENT / "dash_alerts.csv", index=False)
    pd.read_csv(RES_ANALYSIS / "delivery_log.csv").to_csv(RES_PRESENT / "dash_delivery.csv", index=False)
    import duckdb
    from common import DB_PATH
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("SELECT rule_id, kpi, scope, method, threshold, window_days, min_count, active, note FROM alert_rule ORDER BY rule_id").df().to_csv(RES_PRESENT / "dash_rules.csv", index=False)
    print("dash_*.csv selesai")


if __name__ == "__main__":
    main()
