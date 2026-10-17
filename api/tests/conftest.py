import pytest


@pytest.fixture(autouse=True)
def usar_bd_temporaria(tmp_path, monkeypatch):
    db_path = tmp_path / "triage_results.sqlite3"
    monkeypatch.setenv("MEDIFLOW_TRIAGE_DB", str(db_path))
