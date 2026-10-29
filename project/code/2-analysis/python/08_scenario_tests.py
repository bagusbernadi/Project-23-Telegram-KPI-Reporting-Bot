"""Tahap 2 / langkah 08: uji skenario (Q8), uji perintah bot, dan pemeriksaan secret (Q9). Semua memakai kode bot yang sama.

Skenario kirim ke Telegram memakai transport PALSU (tanpa token/jaringan): menguji logika retry, penyamaran token, dan pencatatan gagal,
bukan koneksi ke Telegram sungguhan.
Keluaran: results/2-analysis/{scenario_tests.csv, command_tests.csv, secret_scan.csv}
"""
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot import commands  # noqa: E402
from bot.report import load_kpis, pct  # noqa: E402
from bot.run_daily import process_day  # noqa: E402
from bot.sender import DryRunSender, SendError, TelegramSender  # noqa: E402
from common import ALERT_RULES, DB_PATH, RES_ANALYSIS, ROOT  # noqa: E402


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    cfg = yaml.safe_load(ALERT_RULES.read_text(encoding="utf-8"))
    mcfg = cfg["missing_data"]
    rules = con.execute("SELECT * FROM alert_rule").df()
    tmp = Path(tempfile.mkdtemp())
    res = []

    def rec(name, expected, observed, ok):
        res.append(dict(scenario=name, expected=expected, observed=observed, result="lulus" if ok else "GAGAL"))

    # 1 normal
    s, st = DryRunSender(), {}
    process_day(con, "2026-03-27", datetime(2026, 3, 30, 7, 5), s, st, rules, mcfg, tmp)
    rec("S1 hari normal", "1 pesan daily dengan foto, tanpa alert", f"{[m['kind'] for m in s.messages]}", [m["kind"] for m in s.messages] == ["daily"] and s.messages[0]["photo"])
    # 2 alert
    s, st = DryRunSender(), {}
    process_day(con, "2026-03-30", datetime(2026, 3, 31, 7, 5), s, st, rules, mcfg, tmp)
    rec("S2 hari penurunan yield", "daily + alert", f"{[m['kind'] for m in s.messages]}", [m["kind"] for m in s.messages] == ["daily", "alert"])
    # 3 data terlambat: 23 Mar data tiba siang
    s, st = DryRunSender(), {}
    for h, m in [(7, 5), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0)]:
        process_day(con, "2026-03-23", datetime(2026, 3, 24, h, m), s, st, rules, mcfg, tmp)
    kinds = [(m["kind"], m["sent_at"][11:16]) for m in s.messages]
    rec("S3 data terlambat (tiba siang)", "no_data jam 07:05, lalu daily setelah data tiba, tanpa pesan give-up",
        str(kinds), kinds[0] == ("no_data", "07:05") and kinds[1][0] == "daily" and "belum" in s.messages[0]["text"] and "terlambat" in s.messages[1]["text"] and not st["2026-03-23"]["gave_up"])
    # 4 data kosong: 16 Apr
    s, st = DryRunSender(), {}
    for h, m in [(7, 5), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0), (15, 0)]:
        process_day(con, "2026-04-16", datetime(2026, 4, 17, h, m), s, st, rules, mcfg, tmp)
    kinds = [m["kind"] for m in s.messages]
    rec("S4 data kosong sepanjang hari", "no_data 07:05 dan no_data final 14:00, tidak ada daily, berhenti setelah give-up",
        str(kinds), kinds == ["no_data", "no_data"] and st["2026-04-16"]["gave_up"])
    # 5 idempoten: run ulang tidak mengirim ganda
    s, st = DryRunSender(), {}
    for h in (7, 8, 9):
        process_day(con, "2026-03-27", datetime(2026, 3, 30, h, 5), s, st, rules, mcfg, tmp)
    rec("S5 run ulang pada hari yang sama", "tetap 1 pesan daily", f"{len(s.messages)} pesan", len(s.messages) == 1)
    # 6 telegram: gagal 2x lalu berhasil
    calls = []
    def flaky(url, data, files=None):
        calls.append(url)
        if len(calls) <= 2:
            raise SendError("HTTP 502 dari https://api.telegram.org/botSECRET123/sendMessage")
    waits = []
    import os
    os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = "SECRET123", "-100"
    ts = TelegramSender(post=flaky, sleep=waits.append)
    ok = ts.send("uji", "daily", "2026-03-30 07:00:00", "2026-03-27")
    rec("S6 Telegram error 2x lalu berhasil (transport palsu)", "3 percobaan, jeda 2 s lalu 5 s, status sent, token tidak bocor di log",
        f"{len(calls)} percobaan, jeda {waits}, ok={ok}", ok and len(calls) == 3 and waits == [2, 5] and ts.log[-1]["status"] == "sent" and "SECRET123" not in ts.log[-1]["error"])
    calls.clear(); waits.clear()
    def dead(url, data, files=None):
        raise SendError("HTTP 500 https://api.telegram.org/botSECRET123/sendMessage")
    ts = TelegramSender(post=dead, sleep=waits.append)
    ok = ts.send("uji", "daily", "2026-03-30 07:00:00", "2026-03-27")
    rec("S7 Telegram selalu error (transport palsu)", "gagal tercatat sebagai failed, token disamarkan, tidak crash",
        f"ok={ok}, status={ts.log[-1]['status']}, error='{ts.log[-1]['error']}'", (not ok) and ts.log[-1]["status"] == "failed" and "SECRET123" not in ts.log[-1]["error"])
    os.environ.pop("TELEGRAM_BOT_TOKEN"); os.environ.pop("TELEGRAM_CHAT_ID")
    try:
        TelegramSender(post=dead).send("x", "daily", "t", "d")
        rec("S8 token tidak diset", "melempar SendError", "tidak error", False)
    except SendError as e:
        rec("S8 token tidak diset", "melempar SendError yang jelas", str(e), "TELEGRAM_BOT_TOKEN" in str(e))
    pd.DataFrame(res).to_csv(RES_ANALYSIS / "scenario_tests.csv", index=False)
    print(pd.DataFrame(res)[["scenario", "result"]].to_string(index=False))

    # perintah bot: cek jawaban vs SQL langsung
    as_of = "2026-04-10"
    sql_yield = con.execute("SELECT line_yield FROM v_line_daily WHERE date = ?", [as_of]).fetchone()[0]
    ct = []
    def cmd(text, check, note):
        out, _ = commands.handle(con, text, as_of)
        ct.append(dict(command=text, as_of=as_of, check=note, result="lulus" if check(out) else "GAGAL", reply_first_line=out.splitlines()[0]))
    cmd("/yield", lambda o: f"Lini {pct(sql_yield)}" in o and o.count("%") == 11, "yield lini sama dengan view SQL, 10 stasiun tampil")
    cmd("/top_ng", lambda o: "Top NG 7 hari" in o and "1." in o, "ada top NG hari ini dan 7 hari")
    cmd("/trend 7d", lambda o: "7 hari" in o and o.count("Apr") + o.count("Mar") == 7, "7 baris tanggal")
    cmd("/trend 30d", lambda o: "30 hari" in o, "30 hari")
    cmd("/trend 99d", lambda o: o.startswith("Format"), "ditolak (di luar 2-60 hari)")
    cmd("/trend abc", lambda o: o.startswith("Format"), "argumen salah ditolak")
    cmd("/help", lambda o: "/yield" in o and "/top_ng" in o, "daftar perintah")
    cmd("/yield@kpi_bot", lambda o: o.startswith("Yield"), "perintah dengan nama bot")
    cmd("/hapus", lambda o: o.startswith("Perintah tidak dikenal"), "perintah asing")
    pd.DataFrame(ct).to_csv(RES_ANALYSIS / "command_tests.csv", index=False)
    print(pd.DataFrame(ct)[["command", "result"]].to_string(index=False))

    # pemeriksaan secret: pola token bot Telegram, TELEGRAM_BOT_TOKEN dengan nilai, di semua berkas terlacak dan riwayat git
    root = ROOT.parent
    pat = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
    files = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split()
    hits = []
    for f in files:
        p = root / f
        if p.suffix in {".png", ".pdf", ".xlsx", ".duckdb"} or not p.is_file():
            continue
        t = p.read_text(errors="ignore")
        for m in pat.finditer(t):
            hits.append((f, "pola token"))
        for m in re.finditer(r"TELEGRAM_BOT_TOKEN\s*[=:]\s*['\"]?[A-Za-z0-9:_-]{20,}", t):
            hits.append((f, "nilai token"))
    hist = subprocess.run(["git", "-C", str(root), "log", "--all", "-p", "--no-color"], capture_output=True, text=True).stdout
    hist_hits = len(pat.findall(hist))
    wf = (root / ".github/workflows/daily.yml")
    uses_secret = wf.exists() and "secrets.TELEGRAM_BOT_TOKEN" in wf.read_text()
    ign = (root / ".gitignore").read_text()
    sc = pd.DataFrame([["berkas terlacak yang memuat pola token", len(hits)], ["pola token di riwayat git (semua cabang)", hist_hits],
                       ["workflow memakai secrets.TELEGRAM_BOT_TOKEN", int(uses_secret)], ["data mentah dan .duckdb di .gitignore", int("project/data/raw/" in ign and "*.duckdb" in ign)]],
                      columns=["check", "value"])
    sc.to_csv(RES_ANALYSIS / "secret_scan.csv", index=False)
    print(sc.to_string(index=False))


if __name__ == "__main__":
    main()
