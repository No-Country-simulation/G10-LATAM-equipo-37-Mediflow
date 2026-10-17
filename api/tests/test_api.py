import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
EJEMPLO = json.loads((Path(__file__).parents[2] / "docs" / "examples" / "triage_request.json").read_text())


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_triage_ejemplo():
    r = client.post("/triage", json=EJEMPLO)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["documento_id"] == EJEMPLO["documento_id"]
    assert cuerpo["decision_enrutamiento"]["destino_principal"] == "Cola_Emergencia_Medica"
    assert set(cuerpo) >= {"status", "clasificacion", "datos_extraidos", "decision_enrutamiento", "almacenamiento_oci"}
