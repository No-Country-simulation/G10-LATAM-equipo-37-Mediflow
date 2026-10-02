"""
agent/tests/test_urgencia.py

Cubre el "Listo cuando" de N1-06:
  - El caso TEP (hallazgo crítico en un tipo de la lista) dispara urgencia
  - GS-01, GS-04, GS-24, GS-25 (frases de alarma en receta/epicrisis/certificado)
    NO disparan urgencia -> prueba directa de la Regla A (ADR-002)
  - Alto riesgo farmacológico solo en recetas, con coincidencia por inclusión
"""

from agent.nodes.urgencia import detectar_urgencia


def _state(texto="", tipo_documento="", nivel_prioridad=None, medicamentos=None):
    clasificacion = {"tipo_documento": tipo_documento}
    if nivel_prioridad:
        clasificacion["nivel_prioridad"] = nivel_prioridad
    return {
        "texto": texto,
        "clasificacion": clasificacion,
        "datos_extraidos": {"medicamentos": medicamentos or []},
        "trace": [],
    }


# ---------------------------------------------------------------------------
# Fuente 1: hallazgos críticos, restringidos por la Regla A
# ---------------------------------------------------------------------------

def test_hallazgo_critico_en_informe_laboratorio_dispara_urgencia():
    """Caso TEP del brief: hallazgo crítico en un tipo de la lista aplica_a."""
    state = _state(
        texto="Se evidencia tromboembolismo pulmonar bilateral.",
        tipo_documento="Informe de Estudio por Imagenes",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is True
    assert any("tromboembolismo" in m for m in resultado["urgencia"]["motivos"])


def test_hallazgo_critico_en_receta_no_dispara_urgencia():
    """Regla A (ADR-002): en receta, las fuentes automáticas 1/2/4 NO aplican.
    Corresponde al patrón de GS-01/GS-04/GS-24/GS-25 del golden set.
    """
    state = _state(
        texto="Antecedente de sepsis hace 3 meses, actualmente en tratamiento de mantenimiento.",
        tipo_documento="Receta Medica",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False


def test_palabra_urgencia_en_epicrisis_no_dispara_urgencia():
    """Regla A: 'de urgencia' en una epicrisis de alta no debe disparar nada."""
    state = _state(
        texto="Paciente acudió de urgencia hace una semana, hoy egresa estable.",
        tipo_documento="Epicrisis",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False


def test_palabra_urgencia_en_orden_procedimiento_si_dispara():
    """Orden de Solicitud de Procedimiento SÍ está en aplica_a."""
    state = _state(
        texto="Solicito estudio de forma urgente por sospecha clínica.",
        tipo_documento="Orden de Solicitud de Procedimiento",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is True


# ---------------------------------------------------------------------------
# Fuente 3: juicio del modelo — la única que aplica a TODOS los tipos
# ---------------------------------------------------------------------------

def test_modelo_urgente_en_receta_si_dispara():
    """Fuente 3 aplica incluso en receta, a diferencia de las fuentes 1/2/4."""
    state = _state(texto="", tipo_documento="Receta Medica", nivel_prioridad="Urgente")
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is True
    assert "prioridad del modelo: Urgente" in resultado["urgencia"]["motivos"]


def test_modelo_no_urgente_no_dispara_por_si_solo():
    state = _state(texto="", tipo_documento="Receta Medica", nivel_prioridad="Rutina")
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False


# ---------------------------------------------------------------------------
# Fuente 4: valores críticos de laboratorio
# ---------------------------------------------------------------------------

def test_valor_critico_potasio_alto_dispara_urgencia():
    state = _state(
        texto="Potasio: 7.2 mmol/L, resto de electrolitos dentro de parámetros normales.",
        tipo_documento="Informe de Laboratorio",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is True
    assert any("potasio" in m for m in resultado["urgencia"]["motivos"])


def test_valor_normal_no_dispara():
    state = _state(
        texto="Potasio: 4.1 mmol/L, valores normales.",
        tipo_documento="Informe de Laboratorio",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False


def test_valor_critico_en_receta_no_aplica_por_regla_a():
    """Aunque el texto mencione un valor crítico, en receta la fuente 4 no aplica."""
    state = _state(
        texto="Potasio: 7.2 mmol/L",
        tipo_documento="Receta Medica",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False


def test_troponina_elevada_operador_texto():
    state = _state(
        texto="Troponina elevada, se solicita interconsulta con cardiología.",
        tipo_documento="Informe de Laboratorio",
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is True


# ---------------------------------------------------------------------------
# Alto riesgo farmacológico: coincidencia por inclusión, solo en recetas
# ---------------------------------------------------------------------------

def test_alto_riesgo_por_coincidencia_de_substring():
    """rules.yaml: 'insulina' debe detectar 'insulina glargina' (coincidencia por
    inclusión). Este test falla con la lógica invertida del stub anterior."""
    state = _state(
        tipo_documento="Receta Medica",
        medicamentos=[{"nombre": "insulina glargina", "dosis": "10 UI"}],
    )
    resultado = detectar_urgencia(state)
    assert "insulina glargina" in resultado["urgencia"]["alto_riesgo_farmacologico"]


def test_alto_riesgo_no_aplica_fuera_de_receta():
    """Contrato: alto riesgo farmacológico solo en recetas."""
    state = _state(
        tipo_documento="Epicrisis",
        medicamentos=[{"nombre": "insulina glargina", "dosis": "10 UI"}],
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["alto_riesgo_farmacologico"] == []


def test_medicamento_comun_no_es_alto_riesgo():
    state = _state(
        tipo_documento="Receta Medica",
        medicamentos=[{"nombre": "amoxicilina", "dosis": "500 mg"}],
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["alto_riesgo_farmacologico"] == []


def test_alto_riesgo_no_confunde_con_emergencia():
    """Alto riesgo farmacológico nunca debe verse reflejado en 'motivos' de urgencia:
    va a Farmacia con auditoría, no a Emergencia (contrato, sección 4)."""
    state = _state(
        tipo_documento="Receta Medica",
        medicamentos=[{"nombre": "morfina", "dosis": "10 mg"}],
    )
    resultado = detectar_urgencia(state)
    assert resultado["urgencia"]["detectada"] is False
    assert "morfina" in resultado["urgencia"]["alto_riesgo_farmacologico"]


def test_traza_registra_el_nodo():
    state = _state(tipo_documento="Receta Medica")
    resultado = detectar_urgencia(state)
    assert resultado["trace"][-1]["nodo"] == "detectar_urgencia"
