"""Score de confianza compuesto. Los pesos y umbrales se calibran con el golden set en el sprint 3."""
from agent.nodes.common import step
from agent.state import TriageState

PESOS = {"legibilidad": 0.25, "validacion": 0.30, "modelo": 0.25, "acuerdo": 0.20}


def puntuar(state: TriageState) -> dict:
    legibilidad = state.get("legibilidad", 0.0)
    validacion = state.get("validacion", {})
    n_problemas = len(validacion.get("campos_faltantes", [])) + len(validacion.get("conflictos", []))
    score_validacion = max(0.0, 1.0 - 0.25 * n_problemas)
    score_modelo = state.get("clasificacion", {}).get("score_confianza_clasificacion", 0.0)
    acuerdo = state.get("segunda_opinion", {}).get("acuerdo")
    score_acuerdo = 1.0 if acuerdo is None else (1.0 if acuerdo else 0.0)

    score = (
        PESOS["legibilidad"] * legibilidad
        + PESOS["validacion"] * score_validacion
        + PESOS["modelo"] * score_modelo
        + PESOS["acuerdo"] * score_acuerdo
    )
    score = round(min(1.0, max(0.0, score)), 3)
    detalle = {
        "legibilidad": legibilidad,
        "validacion": score_validacion,
        "modelo": score_modelo,
        "acuerdo": score_acuerdo,
        "score": score,
    }
    return {"score": score, "trace": step(state, "puntuar", detalle)}
