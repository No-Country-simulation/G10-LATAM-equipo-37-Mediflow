"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad."""
from agent.nodes.common import step
from agent.state import TriageState


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")
    legibilidad = state.get("legibilidad")
    if legibilidad is None:
        legibilidad = 1.0 if texto else 0.0
        if tipo in ("PDF", "IMAGEN") and not texto:
            legibilidad = 0.0

    return {
        "texto": texto,
        "imagenes": state.get("imagenes", []),
        "legibilidad": legibilidad,
        "trace": step(
            state,
            "normalizar",
            {"tipo_archivo": tipo, "legibilidad": legibilidad, "imagenes": len(state.get("imagenes", []))},
        ),
    }
