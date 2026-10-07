"""Tests del nodo de segunda opinión.

No llaman a ningún modelo real: mockean el adaptador. Cubren las decisiones de diseño del nodo:

- elige otro modelo y compara campo por campo,
- tolera diferencias de formato (tildes, mayúsculas, orden de medicamentos),
- no trata la diferencia de cobertura como desacuerdo,
- nunca deja el grafo sin respuesta ni lo rompe,
- y el desacuerdo baja el score, que es para lo que sirve.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agent.llm.adapter import LLMResult
from agent.nodes import segunda_opinion as nodo

DATOS_PRIMERO = {
    "paciente": {"nome": "Carlos Eduardo Mendes", "edad": 52},
    "medico_solicitante": {"nombre": "Dra. Renata Silveira", "matricula": "145892"},
    "estudio_realizado": "Tomografia de Torax con contraste",
    "diagnostico_principal": "Tromboembolismo Pulmonar Agudo",
    "cie10_sugerido": "I26.9",
    "medicamentos": [],
}


def _estado(**extra) -> dict:
    """Estado mínimo para llegar al nodo: es lo que deja `extraer` antes de puntuar."""
    estado = {
        "documento_id": "DOC-SO-1",
        "texto": "INFORME DE ESTUDIO. Paciente: Carlos Eduardo Mendes, 52 anos.",
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
        "datos_extraidos": DATOS_PRIMERO,
        "modelo_utilizado": "gemini/gemini-2.5-flash",
        "trace": [],
    }
    estado.update(extra)
    return estado


def _respuesta(datos: dict, modelo: str = "groq/llama-4-scout") -> LLMResult:
    return LLMResult(text=json.dumps({"datos_extraidos": datos}), model=modelo, latency_ms=210)


@pytest.fixture
def llm_activo(monkeypatch):
    """Activa el camino con LLM: en tests el default del repo es USE_LLM=false."""
    monkeypatch.setattr(nodo, "USE_LLM", True)


@pytest.fixture
def cadena(monkeypatch):
    """Cadena de modelos conocida, para que la elección del respaldo sea predecible."""
    monkeypatch.setattr(nodo.adapter, "PRIMARY", "gemini/gemini-2.5-flash")
    monkeypatch.setattr(nodo.adapter, "FALLBACKS", ["groq/llama-4-scout", "mistral/mistral-small-latest"])


# --------------------------------------------------------------------------- camino feliz


def test_usa_otro_modelo_y_no_el_que_ya_respondio(llm_activo, cadena):
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(DATOS_PRIMERO)) as llamada:
        salida = nodo.segunda_opinion(_estado())

    assert llamada.call_args.kwargs["modelo"] == "groq/llama-4-scout"
    opinion = salida["segunda_opinion"]
    assert opinion["disponible"] is True
    assert opinion["acuerdo"] is True
    assert opinion["modelo_primario"] == "gemini/gemini-2.5-flash"
    assert opinion["campos_en_desacuerdo"] == []
    assert opinion["campos_comparados"] >= 4
    assert salida["trace"][-1]["modelo"] == "groq/llama-4-scout"


def test_registra_el_modelo_que_respondio_aunque_no_sea_el_pedido(llm_activo, cadena):
    respuesta = _respuesta(DATOS_PRIMERO, modelo="mistral/mistral-small-latest")
    with patch.object(nodo.adapter, "complete", return_value=respuesta):
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]
    assert opinion["modelo"] == "mistral/mistral-small-latest"


# --------------------------------------------------------------------------- comparación


def test_desacuerdo_campo_por_campo(llm_activo, cadena):
    otro = json.loads(json.dumps(DATOS_PRIMERO))
    otro["paciente"]["nome"] = "Carlos Eduardo Mendes Silva"
    otro["diagnostico_principal"] = "Neumonia adquirida en la comunidad"
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(otro)):
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]

    assert opinion["acuerdo"] is False
    assert set(opinion["campos_en_desacuerdo"]) == {"paciente.nome", "diagnostico_principal"}
    assert "paciente.nome" in opinion["motivo"]


def test_diferencias_de_formato_no_son_desacuerdo(llm_activo, cadena):
    otro = json.loads(json.dumps(DATOS_PRIMERO))
    otro["paciente"]["nome"] = "  CARLOS   Eduardo Mendes "
    otro["estudio_realizado"] = "tomografía de tórax con contraste."
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(otro)):
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]

    assert opinion["acuerdo"] is True


def test_cobertura_distinta_no_es_desacuerdo(llm_activo, cadena):
    otro = json.loads(json.dumps(DATOS_PRIMERO))
    otro["conclusion"] = "Cuadro compatible con TEP agudo."
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(otro)):
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]

    assert opinion["acuerdo"] is True
    assert "conclusion" in opinion["campos_solo_en_un_modelo"]


def test_medicamentos_en_otro_orden_no_es_desacuerdo(llm_activo, cadena):
    primero = json.loads(json.dumps(DATOS_PRIMERO))
    primero["medicamentos"] = [{"nombre": "Enoxaparina"}, {"nombre": "Morfina"}]
    otro = json.loads(json.dumps(DATOS_PRIMERO))
    otro["medicamentos"] = [{"nombre": "morfina"}, {"nombre": "ENOXAPARINA"}]
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(otro)):
        opinion = nodo.segunda_opinion(_estado(datos_extraidos=primero))["segunda_opinion"]

    assert opinion["acuerdo"] is True


# --------------------------------------------------------------------------- degradación segura


def test_sin_texto_ni_imagenes_no_llama_al_modelo(llm_activo, cadena):
    with patch.object(nodo.adapter, "complete", side_effect=AssertionError("no debía llamar")) as llamada:
        opinion = nodo.segunda_opinion(_estado(texto=""))["segunda_opinion"]

    assert llamada.call_count == 0
    assert opinion["disponible"] is False
    assert "No hay texto" in opinion["motivo"]


def test_use_llm_desactivado_no_llama(monkeypatch, cadena):
    monkeypatch.setattr(nodo, "USE_LLM", False)
    with patch.object(nodo.adapter, "complete", side_effect=AssertionError("no debía llamar")) as llamada:
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]

    assert llamada.call_count == 0
    assert "USE_LLM" in opinion["motivo"]


def test_modelo_caido_no_rompe_el_grafo(llm_activo, cadena):
    with patch.object(nodo.adapter, "complete", side_effect=RuntimeError("Todos los modelos fallaron")):
        salida = nodo.segunda_opinion(_estado())

    opinion = salida["segunda_opinion"]
    assert opinion["disponible"] is False
    assert opinion["acuerdo"] is None
    assert "RuntimeError" in opinion["motivo"]
    assert salida["trace"][-1]["nodo"] == "segunda_opinion"


def test_json_invalido_no_rompe_el_grafo(llm_activo, cadena):
    respuesta = LLMResult(text="no soy json", model="groq/llama-4-scout", latency_ms=10)
    with patch.object(nodo.adapter, "complete", return_value=respuesta):
        opinion = nodo.segunda_opinion(_estado())["segunda_opinion"]

    assert opinion["disponible"] is False
    assert "JSON" in opinion["motivo"]


def test_no_repite_si_ya_hay_una_segunda_opinion(llm_activo, cadena):
    with patch.object(nodo.adapter, "complete", side_effect=AssertionError("no debía llamar")) as llamada:
        salida = nodo.segunda_opinion(_estado(segunda_opinion={"acuerdo": True}))

    assert salida == {}
    assert llamada.call_count == 0


def test_la_traza_lleva_el_veredicto_y_no_la_extraccion(llm_activo, cadena):
    with patch.object(nodo.adapter, "complete", return_value=_respuesta(DATOS_PRIMERO)):
        salida = nodo.segunda_opinion(_estado())

    detalle = salida["trace"][-1]["detalle"]
    assert "datos" not in detalle
    assert detalle["acuerdo"] is True
    # La extracción del segundo modelo no se pierde: viaja en el estado para el auditor.
    assert salida["segunda_opinion"]["datos"]["paciente"]["nome"] == "Carlos Eduardo Mendes"


# --------------------------------------------------------------------------- efecto en el grafo


def test_el_grafo_no_pide_la_segunda_opinion_dos_veces():
    from agent.graph import _tras_urgencia

    assert _tras_urgencia({"score": 0.70}) == "segunda_opinion"
    assert _tras_urgencia({"score": 0.70, "segunda_opinion": {"acuerdo": True}}) == "enrutar"


def test_la_urgencia_no_pide_segunda_opinion():
    from agent.graph import _tras_urgencia

    assert _tras_urgencia({"score": 0.70, "urgencia": {"detectada": True}}) == "enrutar"


def test_el_desacuerdo_baja_el_score():
    from agent.nodes.puntuar import puntuar

    base = {
        "legibilidad": 0.75,
        "validacion": {"campos_faltantes": [], "conflictos": [], "errores": []},
        "clasificacion": {"score_confianza_clasificacion": 0.9},
        "trace": [],
    }
    sin_opinion = puntuar(dict(base))
    con_desacuerdo = puntuar({**base, "segunda_opinion": {"acuerdo": False}})

    assert con_desacuerdo["score"] < sin_opinion["score"]
    assert con_desacuerdo["trace"][-1]["detalle"]["franja"] in {"revision_humana", "segunda_opinion"}
    assert sin_opinion["trace"][-1]["detalle"]["segunda_opinion"]["pedida"] is False