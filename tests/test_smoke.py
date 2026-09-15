from pathlib import Path
import subprocess
import sys
import importlib.util
import pytest


def test_python_sources_compile():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-m", "compileall", "-q", "."], cwd=root)
    assert result.returncode == 0


def test_database_initializer_creates_expected_tables(tmp_path, monkeypatch):
    if importlib.util.find_spec("duckdb") is None:
        pytest.skip("duckdb is not installed in the isolated verification environment")
    root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    source = (root / "scripts" / "init_db.py").read_text(encoding="utf-8")
    namespace = {"__name__": "init_db_test"}
    exec(compile(source, str(root / "scripts" / "init_db.py"), "exec"), namespace)
    namespace["init"]()
    import duckdb
    con = duckdb.connect(str(tmp_path / "data" / "bank.duckdb"), read_only=True)
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    assert {"fact_transaction", "fact_txn_daily_summary", "metric_sla_thresholds"} <= tables
    assert con.execute("SELECT COUNT(*) FROM fact_transaction").fetchone()[0] == 100
    con.close()


def test_api_health():
    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai is not installed in the isolated verification environment")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    from fastapi.testclient import TestClient
    from api.main import app
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
