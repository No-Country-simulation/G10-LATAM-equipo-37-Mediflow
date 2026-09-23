"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad.

La ingesta (`agent/ingestion.py`) ya resolvió el formato y, para texto digital, la legibilidad.
Para imagen y PDF escaneado llega en `None` a propósito: la puerta de legibilidad vive aquí.

TODO N2-08 (Kevin): reemplazar `_legibilidad_provisional` por el score real a partir de resolución,
contraste y nitidez de la página, más la autoevaluación del modelo. Los umbrales están en
rules.yaml (`legibilidad.leve` 0,70 y `legibilidad.media` 0,40) y se calibran con las 12 imágenes
degradadas del conjunto de prueba.
"""
from agent.nodes.common import step
from agent.state import TriageState

# Medida provisional: cuánto texto sacó el OCR de la página. No es la definitiva, pero ordena los
# tres niveles del conjunto de prueba mejor que un 1.0 fijo, que dejaría pasar cualquier foto.
_TEXTO_SUFICIENTE = 200  # caracteres: la página se lee bien
_TEXTO_MINIMO = 40  # caracteres: se lee a medias, revisión humana con AMB-4


def _legibilidad_provisional(texto: str, imagenes: list) -> float:
    if len(texto) >= _TEXTO_SUFICIENTE:
        return 0.75
    if len(texto) >= _TEXTO_MINIMO:
        return 0.50
    # Sin texto util: si hay página renderizada, que la vea el modelo; si no, no hay nada que leer.
    return 0.30 if imagenes else 0.0


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")
    imagenes = state.get("imagenes", []) or []

    legibilidad = state.get("legibilidad")
    provisional = legibilidad is None
    if provisional:
        legibilidad = _legibilidad_provisional(texto, imagenes)

    return {
        "texto": texto,
        "imagenes": imagenes,
        "legibilidad": legibilidad,
        "trace": step(
            state,
            "normalizar",
            {
                "tipo_archivo": tipo,
                "legibilidad": legibilidad,
                "legibilidad_provisional": provisional,
                "imagenes": len(imagenes),
                "caracteres": len(texto),
            },
        ),
    }
    
