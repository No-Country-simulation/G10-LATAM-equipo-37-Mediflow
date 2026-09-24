"""Regresiones de la revisión de los adjuntos de María, sin servicios externos."""
import pytest

from agent.nodes.enrutar import enrutar
from agent.nodes.extraer import extraer
from agent.nodes.urgencia import detectar_urgencia


def estado(**cambios):
    base = {
        "legibilidad": 1.0, "score": 0.95,
        "clasificacion": {"tipo_documento": "Receta Medica"},
        "validacion": {}, "urgencia": {"detectada": False}, "trace": [],
    }
    base.update(cambios)
    return base


@pytest.mark.parametrize("validacion", [
    {"campos_faltantes": ["paciente.nombre"]},
    {"errores": ["formato inválido"]},
    {"categoria_amb": "AMB-4"},
])
@pytest.mark.parametrize("urgente", [False, True])
def test_ambiguedad_con_score_alto_requiere_auditoria(validacion, urgente):
    d = enrutar(estado(validacion=validacion, urgencia={"detectada": urgente}))["decision"]
    assert d["requiere_auditoria_humana"] is True
    assert d["destino_principal"] == ("Cola_Emergencia_Medica" if urgente else "Cola_Revision_Humana")
    assert (d["notificacion_generada"] is not None) is urgente


def test_nombre_extraido_por_version_actual_llega_a_alerta():
    s = estado(texto="Paciente: Ana Perez, 30 años.", urgencia={"detectada": True})
    s.update(extraer(s))
    assert "Ana Perez" in enrutar(s)["decision"]["notificacion_generada"]["mensaje"]


@pytest.mark.parametrize("texto, esperado", [
    ("Sin evidencia de tromboembolismo pulmonar.", False),
    ("No se observa tromboembolismo pulmonar.", False),
    ("Sin sepsis.", False),
    ("No se descarta tromboembolismo pulmonar.", True),
    ("Sin sepsis. Se observa tromboembolismo pulmonar.", True),
    ("Sin sepsis inicialmente. Sepsis confirmada posteriormente.", True),
])
def test_negaciones_directas_sin_ocultar_otras_menciones(texto, esperado):
    s = estado(texto=texto, clasificacion={"tipo_documento": "Informe de Estudio por Imagenes"})
    assert detectar_urgencia(s)["urgencia"]["detectada"] is esperado


def test_negacion_no_anula_prioridad_urgente_del_modelo():
    s = estado(texto="Sin sepsis.", clasificacion={
        "tipo_documento": "Informe de Laboratorio", "nivel_prioridad": "Urgente",
    })
    assert detectar_urgencia(s)["urgencia"]["detectada"] is True
