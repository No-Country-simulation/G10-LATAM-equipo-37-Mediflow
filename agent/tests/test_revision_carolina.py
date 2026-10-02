"""Regresiones de la revisión de los adjuntos de María, sin servicios externos."""
import pytest

from agent.nodes.enrutar import enrutar
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


def test_nombre_llega_a_alerta():
    s = estado(datos_extraidos={"paciente": {"nombre": "Ana Perez"}}, urgencia={"detectada": True})
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


def test_campo_nome_no_se_acepta_en_alertas():
    s = estado(datos_extraidos={"paciente": {"nome": "Ana Perez"}}, urgencia={"detectada": True})
    mensaje = enrutar(s)["decision"]["notificacion_generada"]["mensaje"]
    assert "Ana Perez" not in mensaje
    assert "paciente sin identificar" in mensaje


@pytest.mark.parametrize("motivo, descripcion", [
    ("no_clinico", "Documento administrativo"),
    ("tipo_no_soportado", "Documento clínico que no es ninguno"),
    ("paciente_no_humano", "El paciente no es una persona"),
    ("idioma_no_soportado", "Documento en un idioma"),
    ("pide_diagnostico", "Pide interpretar o diagnosticar"),
])
@pytest.mark.parametrize("urgente", [False, True])
def test_amb6_conserva_motivo_y_no_fuerza_destino_clinico(motivo, descripcion, urgente):
    s = estado(validacion={"categoria_amb": "AMB-6", "motivo_fuera_de_alcance": motivo},
               urgencia={"detectada": urgente})
    d = enrutar(s)["decision"]
    assert d["destino_principal"] == "Cola_Revision_Humana"
    assert d["requiere_auditoria_humana"] is True
    assert d["notificacion_generada"] is None
    assert descripcion in d["justificacion_enrutamiento"]
    assert "AMB-6" in d["justificacion_enrutamiento"]


@pytest.mark.parametrize("motivo", [None, "Informe en inglés no soportado"])
def test_amb6_sin_codigo_conocido_explicita_motivo(motivo):
    s = estado(validacion={"categoria_amb": "AMB-6", "motivo_fuera_de_alcance": motivo})
    d = enrutar(s)["decision"]
    assert (motivo or "Motivo no especificado") in d["justificacion_enrutamiento"]
