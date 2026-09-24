"""Decide el destino, si requiere auditoría humana y la notificación."""
from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState


def _nombre_paciente(state: TriageState) -> str:
    """Acepta nombre y el campo legado nome durante la migración del contrato."""
    paciente = state.get("datos_extraidos", {}).get("paciente", {}) or {}
    return paciente.get("nombre") or paciente.get("nome") or "paciente sin identificar"


def enrutar(state: TriageState) -> dict:
    reglas = load_rules()
    umbrales = reglas["umbrales"]
    destinos = reglas["destinos"]
    revision = destinos["revision"]

    tipo = state.get("clasificacion", {}).get("tipo_documento", "Otro")
    score = state.get("score", 0.0)
    urgencia = state.get("urgencia", {})
    validacion = state.get("validacion", {})
    conflictos = bool(validacion.get("conflictos"))
    ambiguedad = bool(
        conflictos or validacion.get("campos_faltantes")
        or validacion.get("errores") or validacion.get("categoria_amb")
    )
    notificacion = None

    if state.get("legibilidad", 0.0) < umbrales["legibilidad_minima"]:
        destino, auditoria = revision, True
        justificacion = "Documento ilegible o sin texto. Solicitar nueva captura."

    elif urgencia.get("detectada"):
        destino = destinos["urgencia"]
        # Urgencia con ambigüedad: se atiende primero y se audita después. Un conflicto de datos no
        # frena la alerta, pero sí obliga a que un humano revise el caso.
        auditoria = ambiguedad or score < umbrales["segunda_opinion"]
        justificacion = "Urgencia detectada: " + "; ".join(urgencia.get("motivos", []))
        if ambiguedad:
            justificacion += ". Con datos ambiguos o incompletos: se enruta igual y queda para auditoría."
        notificacion = {
            "canal": "Alerta_Guardia_Medica",
            "mensaje": f"ALERTA URGENTE: {justificacion} para {_nombre_paciente(state)}.",
        }

    elif ambiguedad or score < umbrales["segunda_opinion"]:
        destino, auditoria = revision, True
        justificacion = "Confianza baja, datos ambiguos o incompletos. Requiere revisión humana."

    else:
        destino = destinos["por_tipo"].get(tipo, revision)
        # El alto riesgo farmacológico lo marca urgencia.py solo en recetas: va a Farmacia con
        # auditoría, nunca a Emergencia, porque no hay una urgencia clínica.
        auditoria = bool(urgencia.get("alto_riesgo_farmacologico")) or score < umbrales["automatico"]
        if destino == revision:
            justificacion = f"Tipo de documento sin destino definido ({tipo}). Requiere revisión humana."
        else:
            justificacion = f"Documento de tipo {tipo} con score {score}."

    # Regla transversal: nada llega a la cola de revisión humana sin la marca de auditoría; si no,
    # el panel del auditor muestra casos que el contrato declara como automáticos.
    if destino == revision:
        auditoria = True

    decision = {
        "destino_principal": destino,
        "requiere_auditoria_humana": auditoria,
        "justificacion_enrutamiento": justificacion,
        "notificacion_generada": notificacion,
    }
    return {"decision": decision, "trace": step(state, "enrutar", decision)}
