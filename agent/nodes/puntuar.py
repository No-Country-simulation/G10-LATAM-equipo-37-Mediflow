"""Score de confianza compuesto.

Cuatro señales ponderadas: legibilidad, validaciones superadas, confianza declarada por el modelo y
acuerdo con el segundo modelo.

- Los pesos se leen de `pesos_score` en rules.yaml cuando el bloque existe, y del valor por defecto
  de acá cuando no. Así el score se recalibra sin tocar código, que es la promesa del proyecto.
- El acuerdo es **neutro** cuando no hubo segunda opinión (`acuerdo` en None): no se castiga ni se
  premia un documento por algo que no se midió. Un desacuerdo real, en cambio, baja el score, y eso
  es lo que hace que un documento con franja media termine en revisión humana.
- El umbral de decisión no vive acá: `enrutar` compara el score con `rules.yaml`.
"""
from agent.nodes.common import step
from agent.state import TriageState
from agent.traza import umbrales

# Pesos por defecto. Son los que corren si rules.yaml no trae `pesos_score`.
PESOS = {"legibilidad": 0.25, "validacion": 0.30, "modelo": 0.25, "acuerdo": 0.20}

# Cuánto resta cada problema de validación (campo faltante o conflicto), con piso en 0.
PENALIZACION_POR_PROBLEMA = 0.25


def _pesos_efectivos() -> dict[str, float]:
    """Pesos del score: los de rules.yaml si están, los por defecto si no."""
    try:
        from agent.rules.loader import load_rules

        configurados = load_rules().get("pesos_score") or {}
    except Exception:  # noqa: BLE001 - sin reglas se usan los pesos por defecto
        configurados = {}
    return {clave: float(configurados.get(clave, valor)) for clave, valor in PESOS.items()}


def puntuar(state: TriageState) -> dict:
    """Calcula el score compuesto y deja el desglose completo en la traza."""
    legibilidad = state.get("legibilidad", 0.0)
    validacion = state.get("validacion", {})
    campos_faltantes = validacion.get("campos_faltantes", [])
    conflictos = validacion.get("conflictos", [])
    errores = validacion.get("errores", [])
    n_problemas = len(campos_faltantes) + len(conflictos) + len(errores)
    score_validacion = max(0.0, 1.0 - PENALIZACION_POR_PROBLEMA * n_problemas)

    score_modelo = state.get("clasificacion", {}).get("score_confianza_clasificacion", 0.0)
    segunda = state.get("segunda_opinion", {}) or {}
    acuerdo = segunda.get("acuerdo")
    score_acuerdo = 1.0 if acuerdo is None else (1.0 if acuerdo else 0.0)

    pesos = _pesos_efectivos()
    componentes = {
        "legibilidad": legibilidad,
        "validacion": score_validacion,
        "modelo": score_modelo,
        "acuerdo": score_acuerdo,
    }
    score = round(min(1.0, max(0.0, sum(pesos[clave] * valor for clave, valor in componentes.items()))), 3)

    umbral = umbrales()
    detalle = {
        **componentes,
        "score": score,
        "pesos": pesos,
        "penalizacion_por_problema": PENALIZACION_POR_PROBLEMA,
        "problemas_validacion": n_problemas,
        "campos_faltantes": campos_faltantes,
        "conflictos": conflictos,
        "umbrales": umbral,
        "franja": _franja(score, umbral),
        "segunda_opinion": {
            "pedida": bool(segunda),
            "disponible": segunda.get("disponible"),
            "acuerdo": acuerdo,
            "modelo": segunda.get("modelo"),
            "campos_en_desacuerdo": segunda.get("campos_en_desacuerdo", []),
        },
        "modelo_utilizado": state.get("modelo_utilizado"),
    }
    return {"score": score, "trace": step(state, "puntuar", detalle, modelo=state.get("modelo_utilizado"))}


def _franja(score: float, umbral: dict[str, float]) -> str:
    """En qué franja de decisión cae el score, con los nombres que usa el README."""
    if score >= umbral["automatico"]:
        return "automatico"
    if score >= umbral["revision"]:
        return "segunda_opinion"
    return "revision_humana"


__all__ = ["PENALIZACION_POR_PROBLEMA", "PESOS", "puntuar"]
