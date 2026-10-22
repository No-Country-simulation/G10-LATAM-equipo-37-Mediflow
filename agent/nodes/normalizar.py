"""Detecta el formato y produce texto o imágenes. Calcula la legibilidad.

La ingesta (`agent/ingestion.py`) ya resolvió el formato y, para texto digital, la legibilidad.
Para imagen y PDF escaneado llega en `None` a propósito: la puerta de legibilidad vive aquí y
combina métricas determinísticas de calidad de imagen (resolución, contraste y nitidez,
medidas a ancho normalizado) con la confianza del OCR cuando reconoce suficiente texto.
La autoevaluación del modelo se deja para un PR siguiente (fase 2, issue #62).
"""
from __future__ import annotations

import base64
import os
import platform
import shutil
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat

from agent.ingestion import OCR_LANG
from agent.nodes.common import step
from agent.state import TriageState

# Umbrales de texto usados como proxy cuando la imagen no se puede decodificar
_IMG_MINIMO = 40      # caracteres: se lee a medias -> revisión humana con AMB-4
_IMG_SUFICIENTE = 250  # caracteres: se lee bien -> casi automático
# Ancho (px) al que se normaliza cada página antes de medir contraste y nitidez:
# hace comparables una foto de 4096x3072 y un escaneo A4 de 1240x1754.
_ANCHO_NORMALIZADO = 1000
# Palabras reconocidas por Tesseract a partir de las cuales su confianza se combina
# con el score óptico. Con menos palabras (p. ej. manuscritas) mandan solo las
# métricas de imagen.
_PALABRAS_MIN_OCR = 20
# Peso de la confianza OCR en la combinación con el score óptico.
# Calibración inicial: Tesseract separa bien impresos (>=0.75 limpios, 0.35-0.42 dañados)
# así que el OCR lleva más peso que el óptico. Lo afina la fase 4 con datos reales del CI.
_PESO_OCR = 0.8


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


def _normalizar_tamanio(img: Image.Image) -> Image.Image:
    """Copia de la página a ancho fijo. Evita que la nitidez y el contraste dependan
    de los píxeles de captura en vez de la calidad real de la imagen."""
    if img.width == _ANCHO_NORMALIZADO:
        return img
    escala = _ANCHO_NORMALIZADO / img.width
    alto = max(1, int(img.height * escala))
    return img.resize((_ANCHO_NORMALIZADO, alto), Image.LANCZOS)


def _score_de_imagen(img: Image.Image) -> float:
    """Score de legibilidad de una imagen (0-1) a partir de resolución, contraste y nitidez.

    La resolución sale del ancho original (ya no penaliza arriba de
    `_ANCHO_NORMALIZADO`); contraste y nitidez se miden a ancho normalizado, así una
    foto de 4096x3072 y un escaneo A4 son comparables. Multiplicativo: una imagen
    diminuta o sin contraste no puede pasar aunque el resto acompañe.
    """
    resolucion = min(1.0, img.width / _ANCHO_NORMALIZADO)

    gray = _normalizar_tamanio(img).convert("L")
    # Contraste: desviación estándar de los niveles de gris.
    stat = ImageStat.Stat(gray)
    contraste = min(1.0, stat.stddev[0] / 80.0)

    # Nitidez: varianza del Laplaciano. Nítida -> alta; borrosa o plana -> baja.
    lap = gray.filter(ImageFilter.Kernel((3, 3), (0, -1, 0, -1, 4, -1, 0, -1, 0), scale=1, offset=0))
    stat_lap = ImageStat.Stat(lap)
    nitidez = min(1.0, stat_lap.var[0] / 800.0)

    return round(resolucion * (0.75 * contraste + 0.25 * nitidez), 4)


def _confianza_ocr(img: Image.Image) -> tuple[float, int] | None:
    """(confianza media 0-1, palabras) reconocidas por Tesseract, o None si el OCR
    no está disponible (binario ausente, idioma faltante o imagen rara).

    Usa el mismo fallback de Windows que `ingestion._ocr` (issue #123): nunca lanza,
    la puerta decide igual con las métricas de imagen.
    """
    try:
        import pytesseract
    except ImportError:
        return None
    if platform.system() == "Windows" and not shutil.which("tesseract"):
        for ruta in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.exists(ruta):
                pytesseract.pytesseract.tesseract_cmd = ruta
                break
    try:
        datos = pytesseract.image_to_data(img, lang=OCR_LANG, output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001 - como en _ocr: se sigue sin OCR
        return None
    confianzas = [
        int(conf)
        for texto, conf in zip(datos.get("text", []), datos.get("conf", []), strict=False)
        if (texto or "").strip() and int(conf) >= 0
    ]
    if not confianzas:
        return 0.0, 0
    return round(sum(confianzas) / len(confianzas) / 100.0, 4), len(confianzas)


def _score_de_pagina(img: Image.Image) -> tuple[float, float | None, int]:
    """(score, confianza OCR o None, palabras OCR) de una página decodificable.

    Regla de bloqueo (fase 4, issue #62): si el OCR se ejecutó pero no reconoció
    NINGUNA palabra (palabras == 0, confianza 0.0), no hay señal textual de
    legibilidad y se bloquea fail-closed (score 0.0). Evita que un manuscrito
    severo con bordes nítos (óptico alto) pase sin ser legible (p. ej. M7).
    Con 1.._PALABRAS_MIN_OCR-1 palabras mandan las métricas de imagen.
    """
    optico = _score_de_imagen(img)
    ocr = _confianza_ocr(img)
    if ocr is None:
        return optico, None, 0
    confianza, palabras = ocr
    if palabras == 0:
        # OCR corrió (confianza 0.0) pero reconoció cero palabras: ilegible.
        return 0.0, confianza, palabras
    if palabras < _PALABRAS_MIN_OCR:
        return optico, confianza, palabras
    return round(_PESO_OCR * confianza + (1.0 - _PESO_OCR) * optico, 4), confianza, palabras


def _legibilidad_de_imagenes(
    imagenes: list[str] | None, texto: str = ""
) -> tuple[float, dict]:
    """(score, detalle) a partir de las páginas: el mínimo score entre las decodificables.

    Una página que no se puede decodificar cuenta como 0.0 (fail-closed): si ni el
    archivo se lee, la puerta no puede darla por buena. Si ninguna imagen se puede
    decodificar, recurre al proxy de texto (que será 0.0 si no hay texto).
    """
    detalle: dict = {
        "confianza_ocr": None,
        "palabras_ocr": 0,
        "ocr_disponible": False,
        "imagenes_no_decodificables": 0,
    }
    if not imagenes:
        return _score_from_text(texto), detalle
    scores = []
    for b64 in imagenes:
        img = _decodable_image([b64])
        if img is None:
            detalle["imagenes_no_decodificables"] += 1
            scores.append(0.0)
            continue
        score, confianza, palabras = _score_de_pagina(img)
        scores.append(score)
        if confianza is not None:
            detalle["ocr_disponible"] = True
        detalle["palabras_ocr"] += palabras
        if confianza is not None and (
            detalle["confianza_ocr"] is None or confianza < detalle["confianza_ocr"]
        ):
            detalle["confianza_ocr"] = confianza
    if detalle["imagenes_no_decodificables"] == len(imagenes):
        # Ninguna imagen decodificable: se usa el proxy de texto (0.0 si no hay texto)
        return _score_from_text(texto), detalle
    return min(scores), detalle


def normalizar(state: TriageState) -> dict:
    texto = (state.get("texto") or "").strip()
    tipo = state.get("tipo_archivo", "TEXTO")
    imagenes = state.get("imagenes", []) or []

    legibilidad = state.get("legibilidad")
    provisional = legibilidad is None
    detalle_ocr: dict = {}
    if provisional:
        # Calcular score real a partir de imágenes (mínimo entre páginas) o proxy de
        # texto si no hay páginas o ninguna se puede decodificar
        legibilidad, detalle_ocr = _legibilidad_de_imagenes(imagenes, texto)

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
                "fuente": (
                    "texto-proxy"
                    if not imagenes
                    else "imagen+ocr"
                    if detalle_ocr.get("ocr_disponible")
                    else "imagen"
                ),
                "confianza_ocr": detalle_ocr.get("confianza_ocr"),
                "palabras_ocr": detalle_ocr.get("palabras_ocr", 0),
                "ocr_disponible": detalle_ocr.get("ocr_disponible", False),
                "imagenes_no_decodificables": detalle_ocr.get("imagenes_no_decodificables", 0),
            },
        ),
    }
    
