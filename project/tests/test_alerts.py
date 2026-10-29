import pandas as pd
from bot.alerts import defect_alert, line_alert, station_alert


def _line(vals):
    return pd.DataFrame({"date": [f"2026-01-{i + 1:02d}" for i in range(len(vals))], "line_yield": vals})


def test_fixed_threshold():
    a = line_alert(_line([0.9, 0.8, 0.9]), "fixed", 0.85)
    assert a.tolist() == [False, True, False]


def test_rolling_sigma_silent_during_warmup():
    vals = [0.88] * 5 + [0.5]                      # penurunan besar tetapi baru 5 hari baseline
    assert not line_alert(_line(vals), "rolling_sigma", 2.0, window=20).any()


def test_rolling_sigma_fires_after_warmup():
    vals = [0.88 + 0.002 * ((i % 3) - 1) for i in range(20)] + [0.80]
    a = line_alert(_line(vals), "rolling_sigma", 2.0, window=20)
    assert a.iloc[-1] and not a.iloc[:-1].any()


def test_station_alert_only_flagged_station():
    rows = []
    for i in range(21):
        for s, base in (("A", 0.97), ("B", 0.99)):
            v = base + 0.001 * ((i % 3) - 1)
            if s == "B" and i == 20:
                v = 0.90
            rows.append((f"d{i:02d}", s, v))
    out = station_alert(pd.DataFrame(rows, columns=["date", "station", "fpy"]), "rolling_sigma", 3.5, 20)
    hit = out[out.alert]
    assert hit.station.tolist() == ["B"] and hit.date.tolist() == ["d20"]


def test_defect_poisson_min_count_blocks_small_counts():
    q = [1, 0, 2, 1, 0, 1, 2, 1, 0, 1] * 2 + [4]
    df = pd.DataFrame({"date": [f"d{i:02d}" for i in range(len(q))], "defect_code": "X", "qty": q})
    assert not defect_alert(df, "poisson", 4.0, 5, 20).alert.any()      # 4 < min_count 5
    assert defect_alert(df, "poisson", 1.0, 0, 20).alert.iloc[-1]      # tanpa min_count, ambang rendah -> alert
