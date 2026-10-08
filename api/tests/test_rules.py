import copy
import json

import pytest
from fastapi.testclient import TestClient

from agent import graph
from agent.rules import loader
from api.main import app

client = TestClient(app)
TOKEN = "clave-de-prueba"
CABECERAS = {"X-Admin-Token": TOKEN, "X-Editor": "camila"}


@pytest.fixture(autouse=True)
def entorno_temporal(tmp_path, monkeypatch):
    """Override y registro van a una carpeta temporal, nunca a data/ ni a rules.yaml."""
    monkeypatch.setattr(loader, "OVERRIDE_PATH", tmp_path / "rules.override.yaml")
    monkeypatch.setattr(loader, "AUDIT_PATH", tmp_path / "rules.audit.jsonl")
    monkeypatch.setenv("RULES_ADMIN_TOKEN", TOKEN)
    loader._cache["marca"] = None
    yield
    loader._cache["marca"] = None


def _reglas():
    return copy.deepcopy(client.get("/rules").json())


def _put(cuerpo, cabeceras=CABECERAS):
    return client.put("/rules", json=cuerpo, headers=cabeceras)


def test_put_valido_actualiza_y_get_lo_devuelve():
    nuevas = _reglas()
    nuevas["umbrales"]["segunda_opinion"] = 0.55
    r = _put(nuevas)
    assert r.status_code == 200
    assert r.json()["actualizado"] is True
    assert client.get("/rules").json()["umbrales"]["segunda_opinion"] == 0.55


def test_put_invalido_devuelve_422_con_errores_y_no_guarda():
    antes = _reglas()
    malas = _reglas()
    malas["umbrales"]["automatico"] = 0.3  # queda por debajo de segunda_opinion
    r = _put(malas)
    assert r.status_code == 422
    assert r.json()["detail"]["errores"]
    assert client.get("/rules").json() == antes
    assert not loader.OVERRIDE_PATH.exists()
    assert not loader.AUDIT_PATH.exists()


def test_put_sin_claves_obligatorias_es_422():
    r = _put({"version": "x"})
    assert r.status_code == 422
    assert any("umbrales" in e for e in r.json()["detail"]["errores"])


def test_sin_token_o_con_token_malo_es_401_y_no_guarda():
    nuevas = _reglas()
    nuevas["umbrales"]["segunda_opinion"] = 0.55
    assert client.put("/rules", json=nuevas, headers={"X-Editor": "camila"}).status_code == 401
    assert _put(nuevas, {"X-Admin-Token": "otra", "X-Editor": "camila"}).status_code == 401
    assert not loader.OVERRIDE_PATH.exists()


def test_sin_variable_de_entorno_la_edicion_queda_deshabilitada(monkeypatch):
    monkeypatch.delenv("RULES_ADMIN_TOKEN")
    assert _put(_reglas()).status_code == 503


def test_sin_editor_es_422():
    r = _put(_reglas(), {"X-Admin-Token": TOKEN})
    assert r.status_code == 422


def test_umbral_modificado_avisa_y_deja_registro():
    nuevas = _reglas()
    antes = nuevas["umbrales"]["segunda_opinion"]
    nuevas["umbrales"]["segunda_opinion"] = 0.55
    r = _put(nuevas).json()
    assert r["umbral_modificado"] is True
    assert "golden set" in r["aviso"]
    assert r["cambios"] == [{"campo": "umbrales.segunda_opinion", "antes": antes, "despues": 0.55}]

    lineas = loader.AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 1
    registro = json.loads(lineas[0])
    assert registro["quien"] == "camila"
    assert registro["fecha"]
    assert registro["umbral_modificado"] is True
    assert registro["cambios"][0]["campo"] == "umbrales.segunda_opinion"


def test_cambio_que_no_es_umbral_no_avisa_pero_se_registra():
    nuevas = _reglas()
    nuevas["version"] = "1.1"
    r = _put(nuevas).json()
    assert r["umbral_modificado"] is False
    assert r["aviso"] is None
    assert json.loads(loader.AUDIT_PATH.read_text(encoding="utf-8").splitlines()[0])["quien"] == "camila"


def test_put_sin_cambios_no_registra_nada():
    r = _put(_reglas()).json()
    assert r["cambios"] == []
    assert not loader.AUDIT_PATH.exists()


def test_criterio_del_plan_cambiar_umbral_cambia_la_decision_siguiente():
    estado = {"score": 0.70, "urgencia": {"detectada": False}, "validacion": {"conflictos": []}}
    assert graph._tras_urgencia(estado) == "segunda_opinion"  # 0.70 >= segunda_opinion (0.60)

    nuevas = _reglas()
    nuevas["umbrales"]["segunda_opinion"] = 0.80
    assert _put(nuevas).status_code == 200

    assert graph._tras_urgencia(estado) == "enrutar"  # ahora 0.70 < 0.80, sin reiniciar nada
