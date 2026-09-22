"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad."""
from agent.nodes.common import step
from agent.state import TriageState


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")

    # TODO sprint 2: PDF con capa de texto → PyMuPDF; PDF escaneado o imagen → renderizar páginas
    # y calcular legibilidad (resolución, contraste, nitidez) más la autoevaluación del modelo.
    legibilidad = 1.0 if texto else 0.0
    if tipo in ("PDF", "IMAGEN") and not texto:
        legibilidad = 0.0

    return {
        "texto": texto,
        "legibilidad": legibilidad,
        "trace": step(state, "normalizar", {"tipo_archivo": tipo, "legibilidad": legibilidad}),
    }
