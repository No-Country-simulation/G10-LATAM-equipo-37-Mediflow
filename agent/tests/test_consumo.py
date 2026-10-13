"""Tests del registro de consumo: tokens, costo y modelo de cada llamada al modelo.

Sirven para estimar cuánto cuesta procesar un documento y cuántos documentos por día entran en el
límite gratuito de cada proveedor. No llaman a ningún modelo real: simulan las respuestas de LiteLLM.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import patch

os.environ["USE_LLM"] = "true"

import agent.nodes.clasificar as clasificar_mod  # noqa: E402
import agent.nodes.extraer as extraer_mod  # noqa: E402
from agent.llm import adapter as adapter_mod  # noqa: E402
from agent.llm.adapter import LLMResult, _uso, complete  # noqa: E402
from evals.run import Caso, Resultado, _consumo, _metricas_consumo  # noqa: E402

importlib.reload(clasificar_mod)
importlib.reload(extraer_mod)


class _Uso:
    def __init__(self, entrada, salida):
        self.prompt_tokens = entrada
        self.completion_tokens = salida


class _Respuesta:
    def __init__(self, texto: str, entrada: int | None = None, salida: int | None = None, usage=None):
        self.choices = [type("C", (), {"message": type("M", (), {"content": texto})()})()]
        self.usage = usage if usage is not None else (_Uso(entrada, salida) if entrada is not None else None)


# --------------------------------------------------------------------------- adaptador
def test_complete_devuelve_tokens_y_costo(monkeypatch):
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", [])
    with patch("litellm.completion", return_value=_Respuesta('{"ok": true}', 1200, 300)), \
         patch("litellm.completion_cost", return_value=0.00042):
        r = complete("prompt", json_mode=False)
    assert (r.tokens_entrada, r.tokens_salida, r.costo_usd) == (1200, 300, 0.00042)
    assert r.consumo("clasificar") == {"nodo": "clasificar", "modelo": "mock/primario", "tokens_entrada": 1200,
                                       "tokens_salida": 300, "costo_usd": 0.00042, "latencia_ms": r.latency_ms}


def test_cuenta_solo_la_llamada_que_respondio(monkeypatch):
    """Si el primario falla y responde el respaldo, los tokens son los del respaldo."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])

    def fake(model, **kwargs):
        if model == "mock/primario":
            raise ValueError("400 Bad Request: este modelo no recibe imágenes")
        return _Respuesta("{}", 800, 100)

    with patch("litellm.completion", side_effect=fake), patch("litellm.completion_cost", return_value=0.0001):
        r = complete("prompt", json_mode=False)
    assert r.model == "mock/respaldo" and (r.tokens_entrada, r.tokens_salida) == (800, 100)


def test_sin_precio_conocido_el_costo_queda_vacio():
    with patch("litellm.completion_cost", side_effect=Exception("modelo sin precio")):
        assert _uso(_Respuesta("{}", 10, 5), "nvidia_nim/algo") == (10, 5, None)


def test_uso_tolera_respuestas_sin_usage_o_como_diccionario():
    with patch("litellm.completion_cost", return_value=None):
        assert _uso(_Respuesta("{}"), "x") == (0, 0, None)
        assert _uso(_Respuesta("{}", usage={"prompt_tokens": 7, "completion_tokens": 3}), "x") == (7, 3, None)


def test_llmresult_sigue_funcionando_sin_los_campos_nuevos():
    r = LLMResult(text="hola", model="mock", latency_ms=100)
    assert (r.tokens_entrada, r.tokens_salida, r.costo_usd) == (0, 0, None)


# --------------------------------------------------------------------------- nodos
def _resultado(texto, modelo, entrada, salida, costo):
    return LLMResult(text=texto, model=modelo, latency_ms=50, tokens_entrada=entrada, tokens_salida=salida,
                     costo_usd=costo)


def test_clasificar_y_extraer_acumulan_el_consumo():
    clasificacion = ('{"tipo_documento": "Receta Medica", "especialidad": "Clínica", '
                     '"nivel_prioridad": "Rutina", "score_confianza_clasificacion": 0.9}')
    respuesta = _resultado(clasificacion, "m/a", 900, 80, 0.001)
    with patch.object(clasificar_mod.adapter, "complete", return_value=respuesta):
        salida = clasificar_mod.clasificar({"texto": "Receta: amoxicilina 500 mg", "trace": []})
    assert [c["nodo"] for c in salida["consumo"]] == ["clasificar"]

    estado = {"texto": "Receta: amoxicilina 500 mg", "trace": [], **salida}
    with patch.object(extraer_mod.adapter, "complete",
                      return_value=_resultado('{"datos_extraidos": {}}', "m/b", 1500, 400, 0.002)):
        salida_extraer = extraer_mod.extraer(estado)
    consumo = salida_extraer["consumo"]
    assert [(c["nodo"], c["modelo"], c["tokens_entrada"]) for c in consumo] == [("clasificar", "m/a", 900),
                                                                                 ("extraer", "m/b", 1500)]


def test_sin_modelo_no_hay_consumo(monkeypatch):
    monkeypatch.setattr(clasificar_mod, "USE_LLM", False)
    salida = clasificar_mod.clasificar({"texto": "Receta: amoxicilina 500 mg", "trace": []})
    assert "consumo" not in salida or salida["consumo"] == []


# --------------------------------------------------------------------------- evaluación
def test_consumo_de_un_documento_suma_las_dos_llamadas():
    estado = {"modelo_utilizado": "deepseek/deepseek-chat", "consumo": [
        {"nodo": "clasificar", "tokens_entrada": 900, "tokens_salida": 80, "costo_usd": 0.001},
        {"nodo": "extraer", "tokens_entrada": 1500, "tokens_salida": 400, "costo_usd": 0.002},
    ]}
    assert _consumo(estado) == {"modelo": "deepseek/deepseek-chat", "llamadas_modelo": 2, "tokens_entrada": 2400,
                                "tokens_salida": 480, "costo_usd": 0.003}


def test_costo_sin_dato_si_alguna_llamada_no_tiene_precio():
    estado = {"consumo": [{"costo_usd": 0.001, "tokens_entrada": 1}, {"costo_usd": None, "tokens_entrada": 1}]}
    assert _consumo(estado)["costo_usd"] is None
    assert _consumo({})["llamadas_modelo"] == 0 and _consumo({})["costo_usd"] is None


def _r(obtenido):
    caso = Caso.__new__(Caso)
    return Resultado(caso=caso, clase="base", archivo="x.txt", segundos=1.0, obtenido=obtenido)


def test_metricas_de_consumo_por_documento():
    hechos = [
        _r({"modelo": "deepseek/deepseek-chat", "llamadas_modelo": 2, "tokens_entrada": 2400, "tokens_salida": 600,
            "costo_usd": 0.004}),
        _r({"modelo": "mistral/mistral-small-latest", "llamadas_modelo": 2, "tokens_entrada": 2600,
            "tokens_salida": 800, "costo_usd": 0.002}),
        _r({"modelo": "", "llamadas_modelo": 0, "tokens_entrada": 0, "tokens_salida": 0, "costo_usd": None}),
    ]
    m = _metricas_consumo(hechos)
    assert m["documentos_con_modelo"] == 2
    assert m["tokens_por_documento"] == "2500 de entrada y 700 de salida"
    assert m["costo_por_documento"] == "US$ 0.00300" and m["costo_total_usd"] == "US$ 0.0060"
    assert m["modelos_usados"] == {"deepseek/deepseek-chat": 1, "mistral/mistral-small-latest": 1}


def test_metricas_de_consumo_sin_modelo_ni_precio():
    assert _metricas_consumo([])["tokens_por_documento"] == "sin datos"
    sin_precio = [_r({"modelo": "x", "llamadas_modelo": 2, "tokens_entrada": 10, "tokens_salida": 5,
                      "costo_usd": None})]
    assert _metricas_consumo(sin_precio)["costo_por_documento"] == "sin precio conocido (0 de 1 con precio)"
