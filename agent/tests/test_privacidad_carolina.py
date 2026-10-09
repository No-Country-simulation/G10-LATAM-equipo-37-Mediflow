"""N2-10: controles de minimización, sin datos reales ni proveedores remotos."""
import json
from copy import deepcopy

import pytest

from agent.nodes.common import step
from agent.privacidad import detalle_seguro, seudonimizar


def test_hmac_normaliza_y_cambia_con_clave(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_CLAVE_SEUDONIMO", "clave-sintetica-de-test-1")
    anterior = seudonimizar("30.123.456")
    assert anterior == seudonimizar("30123456")
    assert seudonimizar("Diego Fernández Martínez") == seudonimizar("DIEGO FERNÁNDEZ MARTÍNEZ")
    monkeypatch.setenv("MEDIFLOW_CLAVE_SEUDONIMO", "clave-sintetica-de-test-2")
    assert anterior != seudonimizar("30123456")


def test_sin_clave_no_hay_secreto_por_defecto(monkeypatch):
    monkeypatch.delenv("MEDIFLOW_CLAVE_SEUDONIMO", raising=False)
    assert seudonimizar(None) is None
    assert seudonimizar("") == ""
    with pytest.raises(ValueError):
        seudonimizar("Nombre sintético")
    assert "paciente_ref" not in step({"datos_extraidos": {"paciente": {"nombre": "Nombre sintético"}}}, "validar")[0]


def test_traza_omite_texto_identificadores_y_rutas_sin_mutar_estado(monkeypatch):
    monkeypatch.setenv("MEDIFLOW_CLAVE_SEUDONIMO", "clave-sintetica-de-test")
    nombre, dni, historia = "Paciente Centinela Privacidad", "30123456", "HIST-SECRETA-001"
    datos = {"paciente": {"nombre": nombre, "dni": dni, "historia_clinica": historia}}
    detalle = {"justificacion": f"{nombre} {dni} {historia}", "paciente": datos["paciente"],
               "ruta_objeto": f"recibidos/{nombre}.pdf", "conflictos": [nombre],
               "categoria_amb": "AMB-2", "score": 0.7}
    state = {"datos_extraidos": datos, "trace": [{"nodo": "clasificar", "texto": nombre,
                                               "detalle": detalle, "modelo": nombre}]}
    original = deepcopy(state)
    traza = step(state, "validar", detalle)
    serializada = json.dumps(traza, ensure_ascii=False)
    assert all(dato not in serializada for dato in (nombre, dni, historia))
    assert traza[-1]["detalle"] == {"conflictos_cantidad": 1, "categoria_amb": "AMB-2", "score": 0.7}
    assert traza[-1]["paciente_ref"].startswith("P-")
    assert state == original


@pytest.mark.parametrize("valor", ["Paciente Centinela", 30123456, float("nan"), float("inf"), True])
def test_no_acepta_identificadores_como_score(valor):
    assert detalle_seguro({"score": valor, "tipo_documento": "Paciente Centinela"}) == {}


def test_logs_clasificacion_no_copian_respuesta_invalida(caplog):
    from agent.nodes.clasificar import _normalizar_respuesta
    _normalizar_respuesta({"tipo_documento": "Paciente Centinela", "nivel_prioridad": "DNI 30123456"})
    assert "Paciente Centinela" not in caplog.text
    assert "30123456" not in caplog.text


def test_error_adapter_no_expone_respuesta(caplog, monkeypatch):
    from agent.llm import adapter
    def fallo(*args, **kwargs):
        raise ValueError("Paciente Centinela DNI 30123456")
    monkeypatch.setattr(adapter, "_llamar_modelo", fallo)
    monkeypatch.setattr(adapter, "PRIMARY", "stub")
    monkeypatch.setattr(adapter, "FALLBACKS", [])
    with pytest.raises(RuntimeError) as exc:
        adapter.complete("entrada sintetica")
    assert "ValueError" in str(exc.value)
    assert "Paciente Centinela" not in str(exc.value) + caplog.text


def test_error_persistencia_no_expone_nombre_en_ruta(caplog, monkeypatch):
    from agent.nodes import persistir as modulo
    def fallo(*args, **kwargs):
        raise OSError("Paciente Centinela DNI 30123456")
    monkeypatch.setattr(modulo.storage, "upload_json", fallo)
    resultado = modulo.persistir({"documento_id": "Paciente Centinela", "decision": {}})
    assert resultado["almacenamiento"]["status_backup"] == "error"
    assert "Paciente Centinela" not in caplog.text + json.dumps(resultado["trace"])
