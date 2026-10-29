import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "2-analysis" / "python"))


@pytest.fixture(scope="session")
def con():
    """Bangun data dan database dari nol jika belum ada (deterministik, seed tetap)."""
    import duckdb
    from common import DB_PATH
    if not DB_PATH.exists():
        for s in ("01_generate_data.py", "02_clean_data.py", "03_build_db.py"):
            subprocess.run([sys.executable, str(ROOT / "code" / "1-data-preparation" / "python" / s)], check=True, capture_output=True)
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="session")
def rules(con):
    return con.execute("SELECT * FROM alert_rule").df()


@pytest.fixture(scope="session")
def cfg():
    import yaml
    from common import ALERT_RULES
    return yaml.safe_load(ALERT_RULES.read_text(encoding="utf-8"))["missing_data"]
