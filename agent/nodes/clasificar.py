"""Clasifica el tipo de documento, la especialidad y la prioridad."""
from agent.nodes.common import step
from agent.state import TriageState

# Stub determinístico para que el grafo corra sin claves. TODO sprint 2: reemplazar por agent.llm.adapter.complete
# con el prompt de agent/prompts/clasificar.md y validar la salida.
_PISTAS = [
    ("receta", "Receta Medica"),
    ("epicrisis", "Epicrisis"),
    ("informe de alta", "Epicrisis"),
    ("certificado", "Certificado Medico"),
    ("orden", "Orden de Solicitud de Procedimiento"),
    ("solicitud de procedimiento", "Orden de Solicitud de Procedimiento"),
    ("laboratorio", "Informe de Laboratorio"),
    ("informe", "Informe de Estudio por Imagenes"),
    ("tomografia", "Informe de Estudio por Imagenes"),
]


def clasificar(state: TriageState) -> dict:
    texto = state.get("texto", "").lower()
    tipo = "Otro"
    for pista, candidato in _PISTAS:
        if pista in texto:
            tipo = candidato
            break
    confianza = 0.9 if tipo != "Otro" else 0.3
    clasificacion = {
        "tipo_documento": tipo,
        "especialidad": None,
        "nivel_prioridad": "Rutina",
        "score_confianza_clasificacion": confianza,
    }
    return {
        "clasificacion": clasificacion,
        "modelo_utilizado": "stub",
        "trace": step(state, "clasificar", clasificacion, modelo="stub"),
    }
