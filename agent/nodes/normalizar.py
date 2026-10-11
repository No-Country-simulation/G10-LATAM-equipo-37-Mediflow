"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad.

La ingesta (`agent/ingestion.py`) ya resolvió el formato y, para texto digital, la legibilidad.
Para imagen y PDF escaneado llega en `None` a propósito: la puerta de legibilidad vive aquí y
completa el score con métricas determinísticas de calidad de imagen (resolución, contraste y
nitidez). La autoevaluación del modelo se deja para un PR siguiente (fase 2).
"""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageFilter

from agent.nodes.common import step
from agent.state import TriageState

# La legibilidad de una imagen la decide este nodo. Resolución, contraste y nitidez son
# deterministas con Pillow: no requieren modelo, claves ni red, con lo que se puede calibrar,
# testear y mantener en verde el CI. La autoevaluación del modelo queda para un PR siguiente
# (fase 2, issue #62).
_IMG_MINIMO = 40      # caracteres: se lee a medias -> revisión humana con AMB-4
_IMG_SUFICIENTE = 250  # caracteres: se lee bien -> casi automático


def _b64decode(b64: str) -> bytes:
    try:
        return base64.b64decode(b64.encode("ascii"))
    except Exception:
        return b""


def _decodable_image(imagenes: list[str] | None) -> Image.Image | None:
    for chunk in imagenes or []:
        data = _b64decode(chunk)
        try:
            return Image.open(BytesIO(data)).convert("RGB")
        except Exception:
            continue
    return None


def _score_from_text(texto: str) -> float:
    """Proxy textual. Solo aplica cuando la imagen NO se pudo decodificar, para conservar el
    comportamiento de los tests del grafo. No se ejecuta en imágenes legítimas."""
    if len(texto) >= _IMG_SUFICIENTE:
        return 0.75
    if len(texto) >= _IMG_MINIMO:
        return 0.50
    return 0.0


def _pixels(gray: Image.Image) -> list[int]:
    try:
        return list(gray.get_flattened_data())  # Pillow >= 12
    except AttributeError:  # pragma: no cover - Pillow < 12
        return list(gray.getdata())


def _media_y_var(datos: list[int]) -> tuple[float, float]:
    n = len(datos)
    if n == 0:
        return 0.0, 0.0
    media = float(sum(datos)) / n
    var = sum((v - media) ** 2 for v in datos) / n
    return media, max(0.0, var)


def _score_de_imagen(img: Image.Image) -> float:
    """Score de legibilidad de una imagen (0-1) a partir de resolución, contraste y nitidez.

    Multiplicativo: una imagen diminuta o sin contraste no puede pasar aunque el resto
    acompañe. Calibración: nítida 1600x1200 -> ~1.0; media 800x600 -> ~0.44;
    borrosa/oscura o en blanco -> <0.40 (pasa a revisión humana).
    """
    ancho, alto = img.size
    resolucion = min(1.0, (ancho * alto) / (1200.0 * 900.0))

    gray = img.convert("L")

    # Contraste: desviación estándar de los niveles de gris.
    _, var_gris = _media_y_var(_pixels(gray))
    contraste = min(1.0, (var_gris ** 0.5) / 80.0)

    # Nitidez: varianza del Laplaciano. Nítida -> alta; borrosa o plana -> baja.
    lap = gray.filter(ImageFilter.Kernel((3, 3), (0, -1, 0, -1, 4, -1, 0, -1, 0), scale=1, offset=0))
    _, var_lap = _media_y_var(_pixels(lap))
    nitidez = min(1.0, var_lap / 800.0)

    return round(resolucion * (0.75 * contraste + 0.25 * nitidez), 4)


def _legibilidad_documento(texto: str, imagenes: list[str] | None) -> float:
    """Completa la legibilidad. Devuelve el score para la puerta (<0.40: íelegible, >=0.40: legible)."""
    img = _decodable_image(imagenes)
    if img is not None:
        return _score_de_imagen(img)
    return _score_from_text(texto)


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")
    imagenes = state.get("imagenes", []) or []

    legibilidad = state.get("legibilidad")
    provisional = legibilidad is None
    img_previa = _decodable_image(imagenes)
    if provisional:
        legibilidad = _score_de_imagen(img_previa) if img_previa is not None else _score_from_text(texto)

    fuente = "imagen" if img_previa is not None else "texto-proxy"

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
                "fuente": fuente,
            },
        ),
    }
    
