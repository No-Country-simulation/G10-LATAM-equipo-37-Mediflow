"""Entradas vacías se rechazan antes de ejecutar el grafo; AMB-5 está en #35."""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.mark.parametrize("tipo", ["TEXTO", "JSON"])
@pytest.mark.parametrize("texto", ["", "   ", "\t\n", None])
def test_entrada_vacia_422_sin_ejecutar_grafo(monkeypatch, tipo, texto):
    import api.main as modulo
    def no_ejecutar(*args, **kwargs):
        pytest.fail("Una entrada vacía no debe ejecutar el agente")
    monkeypatch.setattr(modulo, "run_triage", no_ejecutar)
    r = TestClient(app).post("/triage", json={"documento_id": "CB", "tipo_archivo": tipo,
                                               "documento_texto": texto})
    assert r.status_code == 422
