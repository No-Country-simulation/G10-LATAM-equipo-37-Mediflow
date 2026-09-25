"""Decide el destino, si requiere auditoría humana y la notificación.

El orden de decisión es el de rules.yaml y no se cambia acá: gana la primera regla que aplica.

Lo que agrega este archivo a la traza es **por qué**: qué regla disparó, con qué umbrales y con qué
categoría de ambigüedad. "Está en revisión" sin decir por qué no le sirve al auditor, y es lo que el
README promete en la respuesta (`docs/api-contract.md`, sección 6).
"""
from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState


def _nombre_paciente(datos: dict) -> str:
    """Nombre del paciente para el mensaje de alerta.

    El contrato usa `nome` y ADR-003 fijó `nombre` para todo el proyecto: mientras el equipo termina
    de unificar el campo, se aceptan los dos. Sin ninguno, la alerta igual sale, sin identificar.
    """
    paciente = datos.get("paciente") if isinstance(datos.get("paciente"), dict) else {}
    nombre = paciente.get("nombre") or paciente.get("nome")
    return str(nombre) if nombre else "paciente sin identificar"


def _categoria_ambiguedad(validacion: dict) -> str | None:
    """Categoría AMB-x del caso.

    Respeta la que haya calculado `validar`. Si no hay ninguna y falta un campo obligatorio, la
    categoría es AMB-1 por definición del contrato: sirve para que el auditor vea el motivo aunque
    `validar` todavía no la escriba.
    """
    categoria = validacion.get("categoria_amb") or validacion.get("categoria_ambiguedad")
    if categoria:
        return str(categoria)
    if validacion.get("campos_faltantes"):
        return "AMB-1"
    return None


def _motivo_ambiguedad(categoria: str | None, validacion: dict) -> str:
    """Texto del motivo que ve la persona, con el detalle de fuera de alcance cuando corresponde."""
    motivo = validacion.get("motivo_fuera_de_alcance")
    if categoria and motivo:
        return f" ({motivo})"
    return ""


def enrutar(state: TriageState) -> dict:
    reglas = load_rules()
    umbrales = reglas["umbrales"]
    tipo = state.get("clasificacion", {}).get("tipo_documento", "Otro")
    score = state.get("score", 0.0)
    urgencia = state.get("urgencia", {})
    validacion = state.get("validacion", {})
    paciente = _nombre_paciente(state.get("datos_extraidos", {}))
    categoria = _categoria_ambiguedad(validacion)
    notificacion = None

    if state.get("legibilidad", 0.0) < umbrales["legibilidad_minima"]:
        destino, auditoria = reglas["destinos"]["revision"], True
        regla = "ilegible"
        justificacion = "Documento ilegible o sin texto. Solicitar nueva captura."
    elif urgencia.get("detectada"):
        destino = reglas["destinos"]["urgencia"]
        auditoria = score < umbrales["segunda_opinion"]
        regla = "urgencia"
        justificacion = "Urgencia detectada: " + "; ".join(urgencia.get("motivos", []))
        notificacion = {
            "canal": "Alerta_Guardia_Medica",
            "mensaje": f"ALERTA URGENTE: {justificacion} para {paciente}.",
        }
    elif validacion.get("conflictos") or score < umbrales["segunda_opinion"]:
        destino, auditoria = reglas["destinos"]["revision"], True
        regla = "ambiguedad"
        justificacion = "Confianza baja o datos en conflicto. Requiere revisión humana."
        if categoria:
            justificacion = f"{categoria}{_motivo_ambiguedad(categoria, validacion)}. {justificacion}"
    else:
        destino = reglas["destinos"]["por_tipo"].get(tipo, reglas["destinos"]["revision"])
        auditoria = bool(urgencia.get("alto_riesgo_farmacologico")) or score < umbrales["automatico"]
        regla = "por_tipo"
        justificacion = f"Documento de tipo {tipo} con score {score}."

    decision = {
        "destino_principal": destino,
        "requiere_auditoria_humana": auditoria,
        "justificacion_enrutamiento": justificacion,
        "notificacion_generada": notificacion,
    }
    detalle = {
        **decision,
        "regla": regla,
        "categoria_amb": categoria,
        "score": score,
        "umbrales": {"automatico": umbrales["automatico"], "segunda_opinion": umbrales["segunda_opinion"]},
        "tipo_documento": tipo,
        "alto_riesgo_farmacologico": urgencia.get("alto_riesgo_farmacologico", []),
        "segunda_opinion": bool(state.get("segunda_opinion")),
        "modelo_utilizado": state.get("modelo_utilizado"),
    }
    return {"decision": decision, "trace": step(state, "enrutar", detalle, modelo=state.get("modelo_utilizado"))}


__all__ = ["enrutar"]
