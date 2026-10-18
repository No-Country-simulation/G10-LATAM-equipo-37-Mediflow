"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad.

La ingesta (`agent/ingestion.py`) ya resolvió el formato y, para texto digital, la legibilidad.
Para imagen y PDF escaneado llega en `None` a propósito: la puerta de legibilidad vive aquí y
completa el score con métricas determinísticas de calidad de imagen (resolución, contraste y
nitidez). La autoevaluación del modelo se deja para un PR siguiente (fase 2, issue #62).
"""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

from agent.nodes.common import step
from agent.state import TriageState

# Umbrales de texto usados como proxy cuando la imagen no se puede decodificar
_IMG_MINIMO = 40      # caracteres: se lee a medias -> revisión humana con AMB-4
_IMG_SUFICIENTE = 250  # caracteres: se lee bien -> casi automático


def _b64decode(b64: str) -> bytes:
    try:
        return base64.b64decode(b64.encode("ascii"))
    except Exception:
        return b""


def _decodable_image(imagenes: list[str] | None) -> Image.Image | None:
    """Devuelve la primera imagen que se pueda decodificar, o None."""
    for chunk in imagenes or []:
        data = _b64decode(chunk)
        try:
            return Image.open(BytesIO(data)).convert("RGB")
        except Exception:
            continue
    return None


def _score_from_text(texto: str) -> float:
    """Proxy textual. Solo aplica cuando la imagen NO se pudo decodificar, para
    conservar el comportamiento de los tests del grafo. No se ejecuta en imágenes
    legítimas."""
    if len(texto) >= _IMG_SUFICIENTE:
        return 0.75
    if len(texto) >= _IMG_MINIMO:
        return 0.50
    return 0.0


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
    stat = ImageStat.Stat(gray)
    contraste = min(1.0, stat.stddev[0] / 80.0)

    # Nitidez: varianza del Laplaciano. Nítida -> alta; borrosa o plana -> baja.
    lap = gray.filter(ImageFilter.Kernel((3, 3), (0, -1, 0, -1, 4, -1, 0, -1, 0), scale=1, offset=0))
    stat_lap = ImageStat.Stat(lap)
    nitidez = min(1.0, stat_lap.var[0] / 800.0)

    return round(resolucion * (0.75 * contraste + 0.25 * nitidez), 4)


def _legibilidad_de_imagenes(imagenes: list[str] | None, texto: str = "") -> float:
    """Calcula la legibilidad como el mínimo score entre todas las imágenes decodificables.
    Si ninguna imagen se puede decodificar, recurre al proxy de texto (que será 0.0 si
    no hay texto)."""
    if not imagenes:
        return _score_from_text(texto)
    scores = []
    for b64 in imagenes:
        img = _decodable_image([b64])
        if img is not None:
            scores.append(_score_de_imagen(img))
    if scores:
        return min(scores)
    # Ninguna imagen decodificable: se usa el proxy de texto (0.0 si no hay texto)
    return _score_from_text(texto)


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")
    imagenes = state.get("imagenes", []) or []

    legibilidad = state.get("legibilidad")
    provisional = legibilidad is None
    if provisional:
        # Calcular score real a partir de imágenes (mínimo entre páginas) o proxy de
        # texto si no hay páginas o ninguna se puede decodificar
        legibilidad = _legibilidad_de_imagenes(imagenes, texto)

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
                "fuente": "imagen" if imagenes else "texto-proxy",
            },
        ),
    }
    
