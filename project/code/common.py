"""Pengaturan bersama semua skrip Project 23. Semua jalur relatif terhadap folder project/."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # folder project/
DATA = ROOT / "data"
RAW_DIR = DATA / "raw"                                 # data simulasi mentah (tidak di-commit)
CLEAN_DIR = DATA / "clean"                             # data bersih (tidak di-commit)
GROUND_TRUTH = RAW_DIR / "ground_truth.json"
DB_PATH = ROOT / "kpi_bot.duckdb"
CODE = ROOT / "code"
SQL_PREP = CODE / "1-data-preparation" / "sql"
SQL_ANALYSIS = CODE / "2-analysis" / "sql"
BOT_DIR = CODE / "2-analysis" / "python" / "bot"
HTML_DIR = CODE / "3-presentation" / "html"
CONFIG_DIR = ROOT / "config"
ALERT_RULES = CONFIG_DIR / "alert_rules.yaml"
RES_PREP = ROOT / "results" / "1-data-preparation"
RES_ANALYSIS = ROOT / "results" / "2-analysis"
RES_PRESENT = ROOT / "results" / "3-presentation"
DOCS_DIR = ROOT / "docs"
for _d in (RAW_DIR, CLEAN_DIR, RES_PREP, RES_ANALYSIS, RES_PRESENT):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 23260302
DATA_VERSION = "v3"
START_DATE = "2026-03-02"      # Senin
N_DAYS = 75                    # hari kerja Senin-Jumat
SHIFTS = ["Shift 1", "Shift 2"]
MODELS = ["Matic 110", "Bebek 125", "Sport 150"]
STATIONS = ["Frame Welding", "Frame Painting", "Engine Assembly", "Wiring Harness Install",
            "Wheel & Suspension", "Body Panel Assembly", "Electrical Test", "Final Inspection",
            "Performance Test (Dyno)", "Packing"]
ON_TIME_LIMIT = "07:15"        # asumsi: laporan dianggap tepat waktu jika terkirim paling lambat jam ini


def result(name):
    """Cari CSV hasil di folder hasil per tahap."""
    for d in (RES_PREP, RES_ANALYSIS, RES_PRESENT):
        p = d / name
        if p.exists():
            return p
    raise FileNotFoundError(name)


def chdir_root():
    os.chdir(ROOT)
