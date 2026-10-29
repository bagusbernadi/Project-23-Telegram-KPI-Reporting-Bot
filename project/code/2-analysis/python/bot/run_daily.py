"""Satu proses harian bot: cek data masuk, susun laporan + alert, kirim, atau beri tahu data hilang.

process_day() murni terhadap `now` yang diberikan, jadi sama persis dipakai di produksi (now = jam sekarang) dan di simulasi
(now = jam simulasi). Pesan 'no_data' dikirim sekali saat data belum masuk, dan sekali lagi saat batas give_up terlewati.
Pemakaian nyata:  python -m bot.run_daily --date 2026-03-30 --sender dryrun|telegram
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from bot.report import build_alert_message, build_message, evaluate_alerts, load_kpis, render_chart, tgl  # noqa: E402


def arrival_time(con, d):
    """Waktu data tanggal d lengkap (kedua shift) tersedia, atau None bila tidak ada baris kedatangan."""
    rows = con.execute("SELECT arrived_at_next_day FROM data_arrival_log WHERE strftime(date,'%Y-%m-%d') = ?", [d]).fetchall()
    if len(rows) < 2:
        return None
    hhmm = str(max(r[0] for r in rows))[:5]          # DuckDB bisa mengembalikan tipe TIME; ambil HH:MM
    return datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1, hours=int(hhmm[:2]), minutes=int(hhmm[3:]))


def process_day(con, d, now, sender, state, rules, cfg, outdir):
    """Satu percobaan pada waktu `now` untuk tanggal produksi d. state: dict per tanggal {'sent','notified','gave_up'}."""
    s = state.setdefault(d, dict(sent=False, notified=False, gave_up=False))
    if s["sent"] or s["gave_up"]:
        return s
    arr = arrival_time(con, d)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    if arr is not None and arr <= now:
        k = load_kpis(con, d)
        al = evaluate_alerts(con, d, rules)
        chart = render_chart(con, d, Path(outdir) / f"chart_{d}.png")
        late = s["notified"]
        sender.send(build_message(k, al, late=late), "daily", stamp, d, photo=chart)
        if al:
            sender.send(build_alert_message(k, al), "alert", stamp, d)
        s["sent"], s["alerts"], s["sent_at"] = True, len(al), stamp
        return s
    if not s["notified"]:
        sender.send(f"Data {tgl(d)} belum masuk. Laporan dikirim otomatis begitu data tiba (dicek tiap jam).", "no_data", stamp, d)
        s["notified"] = True
    give_up = datetime.strptime(now.strftime("%Y-%m-%d ") + cfg["give_up_at"], "%Y-%m-%d %H:%M")
    if now >= give_up:
        sender.send(f"Data {tgl(d)} tidak tiba sampai {cfg['give_up_at']}. Laporan hari ini tidak dibuat; cek sumber data.", "no_data", stamp, d)
        s["gave_up"] = True
    return s


def attempt_times(run_date, delay_min, main_failed, cfg):
    """Jam percobaan pada run_date: run utama 07:00 + delay Actions; bila gagal/tak ada data, ulang tiap jam 08:00..give_up."""
    base = datetime.strptime(run_date, "%Y-%m-%d")
    first = base + timedelta(hours=7, minutes=delay_min)
    gu = int(cfg["give_up_at"][:2])
    return first, [base + timedelta(hours=h) for h in range(8, gu + 1)]


def simulate(con, sender, runner, rules, cfg, outdir, status_log=None):
    """Putar ulang seluruh periode. runner: DataFrame(date, started_at, status). Kembalikan state per tanggal."""
    state = {}
    for r in runner.itertuples():
        d = pd.Timestamp(r.date).strftime("%Y-%m-%d")
        run_date = (pd.Timestamp(d) + pd.offsets.BDay(1)).strftime("%Y-%m-%d")
        delay = int(str(r.started_at)[3:5])
        first, retries = attempt_times(run_date, delay, r.status == "failed", cfg)
        if r.status == "failed":
            stamp = first.strftime("%Y-%m-%d %H:%M:%S")
            sender.log.append(dict(sent_at=stamp, message_type="daily", status="failed", latency_s=0,
                                   error="workflow run gagal (simulasi runner_log)", report_date=d))
            attempts = retries
        else:
            attempts = [first] + retries
        for t in attempts:
            process_day(con, d, t, sender, state, rules, cfg, outdir)
            if state[d]["sent"] or state[d]["gave_up"]:
                break
    return state


def main():  # pragma: no cover - jalur produksi/CLI
    import duckdb

    from common import ALERT_RULES, DB_PATH
    import yaml
    from bot.sender import DryRunSender, TelegramSender
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="tanggal produksi yang dilaporkan (YYYY-MM-DD)")
    ap.add_argument("--sender", choices=["dryrun", "telegram"], default="dryrun")
    a = ap.parse_args()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    cfg = yaml.safe_load(ALERT_RULES.read_text(encoding="utf-8"))["missing_data"]
    rules = con.execute("SELECT * FROM alert_rule").df()
    sender = TelegramSender() if a.sender == "telegram" else DryRunSender()
    out = Path("outbox"); out.mkdir(exist_ok=True)
    st = process_day(con, a.date, datetime.now(), sender, {}, rules, cfg, out)
    print(st, sender.log)


if __name__ == "__main__":
    main()
