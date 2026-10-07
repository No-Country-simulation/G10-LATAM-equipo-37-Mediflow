"""Tests del adaptador de modelos con cadena de respaldo y reintentos.

Usa mock para simular proveedores que fallan, sin llamar al LLM real.
Verifica:
- Cambio al respaldo cuando el primario falla.
- Reintentos con backoff ante errores recuperables (429, 5xx).
- Excepción clara cuando todos los modelos fallan.
"""
import os
from unittest.mock import patch

import pytest

# Forzar 1 reintento para que los tests no esperen con backoff.
os.environ["LLM_REINTENTOS"] = "1"
os.environ["LLM_BACKOFF_BASE"] = "0.01"

# Importar DESPUÉS de setear las variables (porque el módulo las lee al importar).
import importlib  # noqa: E402

import agent.llm.adapter as adapter_mod  # noqa: E402

importlib.reload(adapter_mod)

from agent.llm.adapter import LLMResult, complete  # noqa: E402

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


def _respuesta_ok(texto: str = '{"ok": true}'):
    """Devuelve una respuesta simulada de litellm."""
    return _FakeResponse(texto)


# =============================================================================
# Tests: cadena de respaldo
# =============================================================================


def test_usa_primario_si_funciona(monkeypatch):
    """Si el primario funciona, no llama a los fallbacks."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        return _respuesta_ok('{"modelo": "primario"}')

    with patch("litellm.completion", side_effect=fake_completion):
        resultado = complete("prompt de prueba", json_mode=False)

    assert resultado.model == "mock/primario"
    assert resultado.text == '{"modelo": "primario"}'
    assert llamadas == ["mock/primario"]


def test_usa_respaldo_si_primario_falla(monkeypatch):
    """Si el primario falla, usa el respaldo."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        if model == "mock/primario":
            raise RuntimeError("Error del primario")
        return _respuesta_ok('{"modelo": "respaldo"}')

    with patch("litellm.completion", side_effect=fake_completion):
        resultado = complete("prompt de prueba", json_mode=False)

    assert resultado.model == "mock/respaldo"
    assert resultado.text == '{"modelo": "respaldo"}'
    assert llamadas == ["mock/primario", "mock/respaldo"]


def test_usa_segundo_respaldo_si_primario_y_primero_fallan(monkeypatch):
    """Si el primario y el primer respaldo fallan, usa el segundo."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo1", "mock/respaldo2"])

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        if model in ("mock/primario", "mock/respaldo1"):
            raise RuntimeError(f"Error en {model}")
        return _respuesta_ok('{"modelo": "respaldo2"}')

    with patch("litellm.completion", side_effect=fake_completion):
        resultado = complete("prompt de prueba", json_mode=False)

    assert resultado.model == "mock/respaldo2"
    assert llamadas == ["mock/primario", "mock/respaldo1", "mock/respaldo2"]


# =============================================================================
# Tests: errores recuperables (reintentos)
# =============================================================================


def test_reintenta_en_error_429(monkeypatch):
    """Con 429, reintenta el mismo modelo antes de pasar al respaldo."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])
    monkeypatch.setattr(adapter_mod, "REINTENTOS_POR_MODELO", 3)

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        if model == "mock/primario" and llamadas.count("mock/primario") < 3:
            raise RuntimeError("429 Too Many Requests")
        return _respuesta_ok('{"modelo": "primario"}')

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = complete("prompt", json_mode=False)

    assert resultado.model == "mock/primario"
    assert llamadas.count("mock/primario") == 3
    assert "mock/respaldo" not in llamadas


def test_reintenta_en_error_500(monkeypatch):
    """Con 500, reintenta el mismo modelo."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", [])
    monkeypatch.setattr(adapter_mod, "REINTENTOS_POR_MODELO", 3)

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        if len(llamadas) < 2:
            raise RuntimeError("500 Internal Server Error")
        return _respuesta_ok('{"ok": true}')

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = complete("prompt", json_mode=False)

    assert resultado.model == "mock/primario"
    assert len(llamadas) == 2


def test_no_reintenta_en_error_no_recuperable(monkeypatch):
    """Con un error no recuperable (401), pasa directo al respaldo sin reintentar."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])
    monkeypatch.setattr(adapter_mod, "REINTENTOS_POR_MODELO", 3)

    llamadas = []

    def fake_completion(model, **kwargs):
        llamadas.append(model)
        if model == "mock/primario":
            raise RuntimeError("401 Unauthorized")
        return _respuesta_ok('{"modelo": "respaldo"}')

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        resultado = complete("prompt", json_mode=False)

    assert resultado.model == "mock/respaldo"
    assert llamadas.count("mock/primario") == 1  # solo un intento, no reintentó


# =============================================================================
# Tests: todos los modelos fallan
# =============================================================================


def test_todos_los_modelos_fallan(monkeypatch):
    """Si todos los modelos fallan, levanta RuntimeError con el detalle."""
    monkeypatch.setattr(adapter_mod, "PRIMARY", "mock/primario")
    monkeypatch.setattr(adapter_mod, "FALLBACKS", ["mock/respaldo"])
    monkeypatch.setattr(adapter_mod, "REINTENTOS_POR_MODELO", 1)

    def fake_completion(model, **kwargs):
        raise RuntimeError(f"Error en {model}")

    with patch("litellm.completion", side_effect=fake_completion), \
         patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            complete("prompt", json_mode=False)

    mensaje = str(exc_info.value)
    assert "mock/primario" in mensaje
    assert "mock/respaldo" in mensaje
    assert "Todos los modelos fallaron" in mensaje


# =============================================================================
# Tests: LLMResult
# =============================================================================


def test_llmresult_tiene_intentos():
    """LLMResult incluye el campo `intentos`."""
    r = LLMResult(text="hola", model="mock", latency_ms=100)
    assert r.intentos == 1

    r2 = LLMResult(text="hola", model="mock", latency_ms=100, intentos=3)
    assert r2.intentos == 3


# =============================================================================
# Tests: detección de errores recuperables
# =============================================================================


@pytest.mark.parametrize("mensaje,esperado", [
    ("429 Too Many Requests", True),
    ("500 Internal Server Error", True),
    ("502 Bad Gateway", True),
    ("503 Service Unavailable", True),
    ("504 Gateway Timeout", True),
    ("Timeout connecting to API", True),
    ("401 Unauthorized", False),
    ("403 Forbidden", False),
    ("404 Not Found", False),
    ("Invalid API key", False),
])
def test_es_error_recuperable(mensaje, esperado):
    """La detección de errores recuperables funciona."""
    exc = RuntimeError(mensaje)
    assert adapter_mod._es_error_recuperable(exc) is esperado