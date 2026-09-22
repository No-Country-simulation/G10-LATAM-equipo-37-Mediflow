"""Detecta urgencia y alto riesgo desde tres fuentes: hallazgos críticos, palabras clave y juicio del modelo."""
from agent.nodes.common import step
from agent.rules.loader import load_rules
from agent.state import TriageState


def detectar_urgencia(state: TriageState) -> dict:
    reglas = load_rules()
    texto = state.get("texto", "").lower()
    motivos = []

    for hallazgo in reglas["hallazgos_criticos"]:
        if hallazgo.lower() in texto:
            motivos.append(f"hallazgo critico: {hallazgo}")
    for palabra in reglas["palabras_urgencia"]:
        if palabra.lower() in texto:
            motivos.append(f"palabra clave: {palabra}")
    if state.get("clasificacion", {}).get("nivel_prioridad") == "Urgente":
        motivos.append("prioridad del modelo: Urgente")

    alto_riesgo = [
        m["nombre"] for m in state.get("datos_extraidos", {}).get("medicamentos", [])
        if m.get("alto_riesgo") or m.get("nombre", "").lower() in reglas["medicamentos_alto_riesgo"]
    ]

    urgencia = {"detectada": bool(motivos), "motivos": motivos, "alto_riesgo_farmacologico": alto_riesgo}
    return {"urgencia": urgencia, "trace": step(state, "detectar_urgencia", urgencia)}
