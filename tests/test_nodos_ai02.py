"""Tests unitarios de los nodos de clasificación y extracción (Carlos, AI-02).

Estos tests NO llaman al LLM real. Verifican:
- La interfaz de los nodos (claves que devuelven al grafo).
- El fallback de reglas de clasificar.
- El fallback de regex de extraer.
- El comportamiento con USE_LLM=false.
- El comportamiento con USE_LLM=true (mockeando el adapter).
- Casos borde: documento vacío, tipo desconocido, texto raro.

Los tests de integración con LLM real viven en agent/tests/test_graph.py.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agent.llm.adapter import LLMResult
from agent.nodes.clasificar import _clasificar_por_reglas, clasificar
from agent.nodes.extraer import _extraer_por_regex, extraer

TEXTO_BRIEF = (
    "HOSPITAL SANTA LUCIA - INFORME DE ESTUDIO RADIOLOGICO. "
    "Paciente: Carlos Eduardo Mendes, 52 anos. "
    "Medico Solicitante: Dra. Renata Silveira MP 145892. "
    "Estudio: Tomografia de Torax con contraste. "
    "Indicacion: Sospecha de embolia pulmonar aguda, disnea subita. "
    "Hallazgos: Defecto de llenado en arteria pulmonar principal derecha "
    "compatible con TEP agudo. "
    "CONCLUSION: Cuadro compatible con Tromboembolismo Pulmonar Agudo."
)

TEXTO_RECETA = (
    "RECETA MEDICA. Paciente: Maria Lopez, 35 anos. "
    "Medico: Dr. Juan Perez MP 12345. "
    "Rx: Amoxicilina 500 mg cada 8 horas por 7 dias."
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_complete_clasificar():
    """Mockea adapter.complete para devolver una clasificación fija."""
    def _fake_complete(prompt, images=None, json_mode=True, timeout=60):
        respuesta = {
            "tipo_documento": "Informe de Estudio por Imagenes",
            "especialidad": "Radiología",
            "nivel_prioridad": "Urgente",
            "idioma": "es",
            "legible": True,
            "confianza": 0.95,
            "justificacion": "TEP agudo, riesgo vital.",
        }
        return LLMResult(
            text=json.dumps(respuesta),
            model="mock/deepseek-chat",
            latency_ms=100,
        )
    with patch("agent.nodes.clasificar.adapter.complete", side_effect=_fake_complete):
        yield


@pytest.fixture
def mock_complete_extraer():
    """Mockea adapter.complete para devolver una extracción fija."""
    def _fake_complete(prompt, images=None, json_mode=True, timeout=60):
        respuesta = {
            "datos_extraidos": {
                "paciente": {"nombre": "Carlos Eduardo Mendes", "edad": 52},
                "medico_solicitante": {
                    "nombre": "Dra. Renata Silveira",
                    "matricula": "145892",
                },
                "estudio_realizado": "Tomografia de Torax con contraste",
                "diagnostico_principal": "Tromboembolismo Pulmonar Agudo (TEP)",
                "cie10_sugerido": "I26.9",
                "medicamentos": [],
                "estudios_solicitados": [],
            },
            "evidencias": [
                {
                    "campo": "paciente.nombre",
                    "fragmento": "Paciente: Carlos Eduardo Mendes, 52 anos.",
                    "valor_extraido": "Carlos Eduardo Mendes",
                }
            ],
            "hallazgo_critico_detectado": "tromboembolismo pulmonar",
            "ambiguedad_detectada": None,
            "justificacion_ambiguedad": None,
        }
        return LLMResult(
            text=json.dumps(respuesta),
            model="mock/deepseek-chat",
            latency_ms=200,
        )
    with patch("agent.nodes.extraer.adapter.complete", side_effect=_fake_complete):
        yield


# =============================================================================
# TESTS DEL NODO CLASIFICAR · fallback de reglas
# =============================================================================


def test_clasificar_por_reglas_detecta_informe():
    """El fallback de reglas clasifica el brief como Informe de Imagenes."""
    resultado = _clasificar_por_reglas(TEXTO_BRIEF)
    assert resultado["tipo_documento"] == "Informe de Estudio por Imagenes"
    # Las reglas no detectan urgencia, siempre devuelven Rutina.
    assert resultado["nivel_prioridad"] == "Rutina"
    assert resultado["score_confianza_clasificacion"] >= 0.8


def test_clasificar_por_reglas_detecta_receta():
    """El fallback de reglas reconoce una receta por la pista 'receta'."""
    resultado = _clasificar_por_reglas(TEXTO_RECETA)
    assert resultado["tipo_documento"] == "Receta Medica"


def test_clasificar_por_reglas_documento_desconocido():
    """Un texto sin pistas cae en Otro con confianza baja."""
    resultado = _clasificar_por_reglas("texto sin pistas claras")
    assert resultado["tipo_documento"] == "Otro"
    assert resultado["score_confianza_clasificacion"] < 0.5


def test_clasificar_por_reglas_texto_vacio():
    """Un texto vacío cae en Otro."""
    resultado = _clasificar_por_reglas("")
    assert resultado["tipo_documento"] == "Otro"


# =============================================================================
# TESTS DEL NODO CLASIFICAR · interfaz con el grafo
# =============================================================================


def test_clasificar_devuelve_claves_del_grafo():
    """El nodo clasificar devuelve las claves que el grafo espera."""
    state = {"texto": TEXTO_BRIEF}
    resultado = clasificar(state)
    assert "clasificacion" in resultado
    assert "modelo_utilizado" in resultado
    assert "trace" in resultado


def test_clasificar_clasificacion_tiene_campos_del_contrato():
    """La clasificación devuelta tiene los 4 campos del contrato."""
    state = {"texto": TEXTO_BRIEF}
    resultado = clasificar(state)
    clasificacion = resultado["clasificacion"]
    assert "tipo_documento" in clasificacion
    assert "especialidad" in clasificacion
    assert "nivel_prioridad" in clasificacion
    assert "score_confianza_clasificacion" in clasificacion


def test_clasificar_sin_llm_marca_stub(monkeypatch):
    """Con USE_LLM=false, el nodo usa el fallback y marca modelo='stub'."""
    import agent.nodes.clasificar as mod
    monkeypatch.setattr(mod, "USE_LLM", False)

    state = {"texto": TEXTO_BRIEF}
    resultado = clasificar(state)
    assert resultado["modelo_utilizado"] == "stub"


def test_clasificar_trace_tiene_un_registro():
    """La traza devuelta tiene exactamente un registro con nodo='clasificar'."""
    state = {"texto": TEXTO_BRIEF, "trace": []}
    resultado = clasificar(state)
    assert len(resultado["trace"]) == 1
    assert resultado["trace"][0]["nodo"] == "clasificar"


# =============================================================================
# TESTS DEL NODO CLASIFICAR · con LLM mockeado
# =============================================================================


def test_clasificar_con_llm_usa_el_adapter(mock_complete_clasificar, monkeypatch):
    """Con USE_LLM=true, el nodo llama al adapter y usa el resultado."""
    # Forzar USE_LLM=true en el módulo ya importado.
    import agent.nodes.clasificar as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    state = {"texto": TEXTO_BRIEF}
    resultado = clasificar(state)

    assert resultado["modelo_utilizado"] == "mock/deepseek-chat"
    assert resultado["clasificacion"]["tipo_documento"] == "Informe de Estudio por Imagenes"
    assert resultado["clasificacion"]["nivel_prioridad"] == "Urgente"
    assert resultado["clasificacion"]["score_confianza_clasificacion"] == 0.95
    assert resultado["clasificacion"]["idioma"] == "es"
    assert resultado["clasificacion"]["legible"] is True


def test_clasificar_con_llm_incluye_justificacion(mock_complete_clasificar, monkeypatch):
    """La clasificación con LLM incluye justificación."""
    import agent.nodes.clasificar as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    state = {"texto": TEXTO_BRIEF}
    resultado = clasificar(state)
    assert "justificacion" in resultado["clasificacion"]
    assert "TEP" in resultado["clasificacion"]["justificacion"]


def test_clasificar_con_llm_falla_cae_al_fallback(monkeypatch):
    """Si el LLM falla, el nodo cae al fallback de reglas."""
    import agent.nodes.clasificar as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    def _fake_fail(*args, **kwargs):
        raise RuntimeError("Simulated LLM failure")

    with patch("agent.nodes.clasificar.adapter.complete", side_effect=_fake_fail):
        state = {"texto": TEXTO_BRIEF}
        resultado = clasificar(state)

    assert resultado["modelo_utilizado"] == "stub"
    assert resultado["clasificacion"]["tipo_documento"] == "Informe de Estudio por Imagenes"


# =============================================================================
# TESTS DEL NODO EXTRAER · fallback de regex
# =============================================================================


def test_extraer_por_regex_caso_brief():
    """El fallback de regex extrae los datos del brief."""
    resultado = _extraer_por_regex(TEXTO_BRIEF)
    assert resultado["paciente"]["nombre"] == "Carlos Eduardo Mendes"
    assert resultado["paciente"]["edad"] == 52
    assert resultado["medico_solicitante"]["nombre"] == "Dra. Renata Silveira"
    assert resultado["medico_solicitante"]["matricula"] == "145892"
    assert resultado["estudio_realizado"] == "Tomografia de Torax con contraste"


def test_extraer_por_regex_documento_sin_datos():
    """Un texto sin datos devuelve nulls, no inventa."""
    resultado = _extraer_por_regex("texto sin estructura clínica")
    assert resultado["paciente"]["nombre"] is None
    assert resultado["paciente"]["edad"] is None
    assert resultado["medico_solicitante"]["nombre"] is None


def test_extraer_por_regex_documento_vacio():
    """Un texto vacío no rompe, devuelve nulls."""
    resultado = _extraer_por_regex("")
    assert resultado["paciente"]["nombre"] is None


# =============================================================================
# TESTS DEL NODO EXTRAER · interfaz con el grafo
# =============================================================================


def test_extraer_devuelve_claves_del_grafo():
    """El nodo extraer devuelve las claves que el grafo espera."""
    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
    }
    resultado = extraer(state)
    assert "datos_extraidos" in resultado
    assert "modelo_utilizado" in resultado
    assert "trace" in resultado


def test_extraer_datos_tienen_campos_del_contrato():
    """Los datos extraídos tienen todos los campos del contrato."""
    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
    }
    resultado = extraer(state)
    datos = resultado["datos_extraidos"]
    assert "paciente" in datos
    assert "medico_solicitante" in datos
    assert "estudio_realizado" in datos
    assert "medicamentos" in datos
    assert "estudios_solicitados" in datos


def test_extraer_sin_llm_marca_stub(monkeypatch):
    """Con USE_LLM=false, el nodo usa regex y marca modelo='stub'."""
    import agent.nodes.extraer as mod
    monkeypatch.setattr(mod, "USE_LLM", False)

    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
    }
    resultado = extraer(state)
    assert resultado["modelo_utilizado"] == "stub"


def test_extraer_trace_tiene_un_registro():
    """La traza devuelta tiene exactamente un registro con nodo='extraer'."""
    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
        "trace": [],
    }
    resultado = extraer(state)
    assert len(resultado["trace"]) == 1
    assert resultado["trace"][0]["nodo"] == "extraer"


# =============================================================================
# TESTS DEL NODO EXTRAER · con LLM mockeado
# =============================================================================


def test_extraer_con_llm_usa_el_adapter(mock_complete_extraer, monkeypatch):
    """Con USE_LLM=true, el nodo extraer llama al adapter."""
    import agent.nodes.extraer as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
    }
    resultado = extraer(state)

    assert resultado["modelo_utilizado"] == "mock/deepseek-chat"
    assert resultado["datos_extraidos"]["paciente"]["nombre"] == "Carlos Eduardo Mendes"
    assert resultado["datos_extraidos"]["cie10_sugerido"] == "I26.9"


def test_extraer_con_llm_devuelve_hallazgo_critico(mock_complete_extraer, monkeypatch):
    """Si el LLM detecta un hallazgo crítico, se incluye en la salida."""
    import agent.nodes.extraer as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    state = {
        "texto": TEXTO_BRIEF,
        "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
    }
    resultado = extraer(state)

    assert "hallazgo_critico" in resultado
    assert "tromboembolismo" in resultado["hallazgo_critico"].lower()


def test_extraer_con_llm_falla_cae_al_fallback(monkeypatch):
    """Si el LLM falla, el nodo extraer cae al fallback de regex."""
    import agent.nodes.extraer as mod
    monkeypatch.setattr(mod, "USE_LLM", True)

    def _fake_fail(*args, **kwargs):
        raise RuntimeError("Simulated LLM failure")

    with patch("agent.nodes.extraer.adapter.complete", side_effect=_fake_fail):
        state = {
            "texto": TEXTO_BRIEF,
            "clasificacion": {"tipo_documento": "Informe de Estudio por Imagenes"},
        }
        resultado = extraer(state)

    assert resultado["modelo_utilizado"] == "stub"
    assert resultado["datos_extraidos"]["paciente"]["nombre"] == "Carlos Eduardo Mendes"


# =============================================================================
# TESTS DE INTEGRACIÓN ENTRE AMBOS NODOS
# =============================================================================


def test_clasificar_y_extraer_en_cadena(mock_complete_clasificar, monkeypatch):
    """Clasificar y extraer funcionan en cadena sobre el mismo state."""
    import agent.nodes.clasificar as mod_c
    monkeypatch.setattr(mod_c, "USE_LLM", True)

    state = {"texto": TEXTO_BRIEF}
    resultado_clasificar = clasificar(state)

    # Simular cómo el grafo fusiona la salida del nodo anterior.
    state_actualizado = {**state, **resultado_clasificar}
    assert state_actualizado["clasificacion"]["tipo_documento"] == "Informe de Estudio por Imagenes"

    # El nodo extraer puede leer la clasificación del state.
    resultado_extraer = extraer(state_actualizado)
    assert "datos_extraidos" in resultado_extraer