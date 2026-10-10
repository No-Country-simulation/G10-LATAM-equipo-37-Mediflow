"""Tests del nodo clasificar (AI-02, Carlos Zunino).

Cubren el mapeo de la respuesta del LLM al estado del grafo, en especial
el campo `motivo_fuera_de_alcance` (N2-04, sección 11.3 del contrato).

No llaman al LLM real: simulan la respuesta con `unittest.mock`.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import patch

# USE_LLM se lee al importar el módulo, así que se setea antes.
os.environ["USE_LLM"] = "true"

# Importar DESPUÉS de setear la variable.
import agent.nodes.clasificar as clasificar_mod  # noqa: E402

importlib.reload(clasificar_mod)

from agent.nodes.clasificar import clasificar  # noqa: E402

# =============================================================================
# Helpers: respuestas falsas de litellm
# =============================================================================


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


def _respuesta_ok(texto: str) -> _FakeResponse:
    """Devuelve una respuesta simulada de litellm."""
    return _FakeResponse(texto)


# =============================================================================
# Tests: motivo_fuera_de_alcance
# =============================================================================


def test_clasificar_emite_motivo_pide_diagnostico(monkeypatch):
    """Si el LLM devuelve `Otro` + `pide_diagnostico`, el estado lo refleja.

    Simula el caso FA-06: un documento que pide un diagnóstico o una
    interpretación, y por lo tanto queda fuera de alcance.
    """
    respuesta_llm = (
        '{"tipo_documento": "Otro", "especialidad": null, "nivel_prioridad": "Rutina", '
        '"idioma": "es", "legible": true, "confianza": 0.9, '
        '"justificacion": "El documento pide un diagnóstico.", '
        '"motivo_fuera_de_alcance": "pide_diagnostico"}'
    )

    def fake_completion(model, **kwargs):
        return _respuesta_ok(respuesta_llm)

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = clasificar({"texto": "Doctor, ¿qué enfermedad tiene este paciente?"})

    clasificacion = resultado["clasificacion"]
    assert clasificacion["tipo_documento"] == "Otro"
    assert clasificacion["motivo_fuera_de_alcance"] == "pide_diagnostico"


def test_clasificar_ignora_motivo_si_tipo_no_es_otro(monkeypatch):
    """Si el tipo no es `Otro`, el motivo se ignora (queda en None)."""
    respuesta_llm = (
        '{"tipo_documento": "Receta Medica", "especialidad": null, "nivel_prioridad": "Rutina", '
        '"idioma": "es", "legible": true, "confianza": 0.9, '
        '"justificacion": "Es una receta.", '
        '"motivo_fuera_de_alcance": "pide_diagnostico"}'
    )

    def fake_completion(model, **kwargs):
        return _respuesta_ok(respuesta_llm)

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = clasificar({"texto": "Receta: Amoxicilina 500 mg"})

    clasificacion = resultado["clasificacion"]
    assert clasificacion["tipo_documento"] == "Receta Medica"
    assert clasificacion["motivo_fuera_de_alcance"] is None


def test_clasificar_motivo_invalido_queda_none(monkeypatch):
    """Si el motivo no es uno de los 5 válidos, se ignora (queda en None)."""
    respuesta_llm = (
        '{"tipo_documento": "Otro", "especialidad": null, "nivel_prioridad": "Rutina", '
        '"idioma": "es", "legible": true, "confianza": 0.9, '
        '"justificacion": "No es un documento clínico.", '
        '"motivo_fuera_de_alcance": "motivo_inventado"}'
    )

    def fake_completion(model, **kwargs):
        return _respuesta_ok(respuesta_llm)

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = clasificar({"texto": "Factura de luz"})

    clasificacion = resultado["clasificacion"]
    assert clasificacion["tipo_documento"] == "Otro"
    assert clasificacion["motivo_fuera_de_alcance"] is None


def test_clasificar_fallback_no_emite_motivo(monkeypatch):
    """Con USE_LLM=false, el fallback de reglas no emite motivo (queda en None)."""
    monkeypatch.setattr(clasificar_mod, "USE_LLM", False)

    resultado = clasificar({"texto": "Doctor, ¿qué enfermedad tiene este paciente?"})

    clasificacion = resultado["clasificacion"]
    assert clasificacion["motivo_fuera_de_alcance"] is None