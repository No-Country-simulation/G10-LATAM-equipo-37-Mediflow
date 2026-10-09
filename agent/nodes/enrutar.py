"""Decide el destino, si requiere auditoría humana y la notificación."""
from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState


def enrutar(state: TriageState) -> dict:
    reglas = load_rules()
    umbrales = reglas["umbrales"]
    tipo = state.get("clasificacion", {}).get("tipo_documento", "Otro")
    score = state.get("score", 0.0)
    urgencia = state.get("urgencia", {})
    validacion = state.get("validacion", {})
    paciente = state.get("datos_extraidos", {}).get("paciente", {}).get("nome") or "paciente sin identificar"
    notificacion = None

    if state.get("legibilidad", 0.0) < umbrales["legibilidad_minima"]:
        destino, auditoria = reglas["destinos"]["revision"], True
        justificacion = "Documento ilegible o sin texto. Solicitar nueva captura."
    elif urgencia.get("detectada"):
        destino = reglas["destinos"]["urgencia"]
        auditoria = score < umbrales["segunda_opinion"]
        justificacion = "Urgencia detectada: " + "; ".join(urgencia.get("motivos", []))
        notificacion = {
            "canal": "Alerta_Guardia_Medica",
            "mensaje": f"ALERTA URGENTE: {justificacion} para {paciente}.",
        }
    elif validacion.get("conflictos") or score < umbrales["segunda_opinion"]:
        destino, auditoria = reglas["destinos"]["revision"], True
        justificacion = "Confianza baja o datos en conflicto. Requiere revisión humana."
    else:
        destino = reglas["destinos"]["por_tipo"].get(tipo, reglas["destinos"]["revision"])
        auditoria = bool(urgencia.get("alto_riesgo_farmacologico")) or score < umbrales["automatico"]
        justificacion = f"Documento de tipo {tipo} con score {score}."

    decision = {
        "destino_principal": destino,
        "requiere_auditoria_humana": auditoria,
        "justificacion_enrutamiento": justificacion,
        "notificacion_generada": notificacion,
    }
    return {"decision": decision, "trace": step(state, "enrutar", decision)}
