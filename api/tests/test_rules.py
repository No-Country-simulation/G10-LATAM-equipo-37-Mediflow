import copy

import pytest
from fastapi.testclient import TestClient

from agent import graph
from agent.rules import loader
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_temporal(tmp_path, monkeypatch):
    """Las pruebas escriben el override en una carpeta temporal, nunca en data/ ni en rules.yaml."""
    monkeypatch.setattr(loader, "OVERRIDE_PATH", tmp_path / "rules.override.yaml")
    loader._cache["marca"] = None
    yield
    loader._cache["marca"] = None


def _reglas():
    return copy.deepcopy(client.get("/rules").json())


def test_put_valido_actualiza_y_get_lo_devuelve():
    nuevas = _reglas()
    nuevas["umbrales"]["segunda_opinion"] = 0.55
    r = client.put("/rules", json=nuevas)
    assert r.status_code == 200
    assert r.json() == {"actualizado": True}
    assert client.get("/rules").json()["umbrales"]["segunda_opinion"] == 0.55


def test_put_invalido_devuelve_422_con_errores_y_no_guarda():
    antes = _reglas()
    malas = _reglas()
    malas["umbrales"]["automatico"] = 0.3  # queda por debajo de segunda_opinion
    r = client.put("/rules", json=malas)
    assert r.status_code == 422
    assert r.json()["detail"]["errores"]
    assert client.get("/rules").json() == antes
    assert not loader.OVERRIDE_PATH.exists()


def test_put_sin_claves_obligatorias_es_422():
    r = client.put("/rules", json={"version": "x"})
    assert r.status_code == 422
    assert any("umbrales" in e for e in r.json()["detail"]["errores"])


def test_criterio_del_plan_cambiar_umbral_cambia_la_decision_siguiente():
    estado = {"score": 0.70, "urgencia": {"detectada": False}, "validacion": {"conflictos": []}}
    assert graph._tras_urgencia(estado) == "segunda_opinion"  # 0.70 >= segunda_opinion (0.60)

    nuevas = _reglas()
    nuevas["umbrales"]["segunda_opinion"] = 0.80
    assert client.put("/rules", json=nuevas).status_code == 200

    assert graph._tras_urgencia(estado) == "enrutar"  # ahora 0.70 < 0.80, sin reiniciar nada