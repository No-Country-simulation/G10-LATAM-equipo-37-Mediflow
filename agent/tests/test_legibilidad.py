"""Pruebas de la puerta de legibilidad de la imagen (N2-08, issue #62).

Los scores se calculan con métricas determinísticas de calidad de imagen
(resolución, contraste y nitidez) en Pillow, sin llamar al modelo. Por eso se pueden correr
siempre: no necesitan red, secretos ni imágenes clínicas reales.
El criterio de aceptación (issue #62) usa tres niveles para las fotos manuscritas:
- leve   -> score >= 0.70 (pasa)
- media  -> 0.40 <= score < 0.70 (pasa)
- severa -> score < 0.40 (pasa a revisión humana)
El score de un documento con `legibilidad` ya precargada no se recalcula
(contrato del grafo).
"""
from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from agent.nodes.normalizar import (
    _PALABRAS_MIN_OCR,
    _score_de_imagen,
    normalizar,
)


def _pagina(fondo: int = 255, texto: int = 0, ancho: int = 1600, alto: int = 1200,
            blur: float = 0.0, dark: float = 1.0, paso: int = 30, tam: int = 16) -> Image.Image:
    """Página sintética: bloques oscuros sobre fondo claro, como líneas de texto."""
    img = Image.new("RGB", (ancho, alto), (fondo, fondo, fondo))
    d = ImageDraw.Draw(img)
    for y in range(0, alto - 24, paso):
        for x in range(0, ancho - 24, paso):
            d.rectangle([x, y, x + tam, y + 16], fill=(texto, texto, texto))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    if dark != 1.0:
        img = ImageEnhance.Brightness(img).enhance(dark)
    return img


def _b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_pagina_nitida_pasa():
    assert _score_de_imagen(_pagina()) >= 0.70


def test_pagina_media_800x600_pasa():
    """Una foto chica pero nítida queda penalizada por tamaño, sin llegar a ilegible."""
    score = _score_de_imagen(_pagina(ancho=800, alto=600))
    assert 0.40 <= score <= 1.0


def test_mismo_tamanio_grande_da_mismo_score():
    """Arriba de 1000 px de ancho el tamaño no debe cambiar el score: una foto de
    4096x3072 y un escaneo A4 de 1240x1754 son comparables tras normalizar."""
    chica = _score_de_imagen(_pagina(ancho=1200, alto=1600))
    grande = _score_de_imagen(_pagina(ancho=2400, alto=3200, paso=60, tam=32))
    assert grande == pytest.approx(chica, abs=0.02)


def test_pagina_borrosa_oscura_ilegible():
    assert _score_de_imagen(_pagina(blur=8, dark=0.4)) < 0.40


def test_pagina_casi_blanca_no_pasa():
    assert _score_de_imagen(_pagina(texto=255)) < 0.40


def test_pagina_borrosa_pequena_ilegible():
    assert _score_de_imagen(_pagina(ancho=600, alto=450, blur=8, dark=0.4)) < 0.40


def test_score_siempre_en_rango():
    imagenes = (
        _pagina(),
        _pagina(texto=255),
        _pagina(ancho=800, alto=600),
        _pagina(blur=8, dark=0.4),
    )
    for img in imagenes:
        assert 0.0 <= _score_de_imagen(img) <= 1.0


def test_legibilidad_precargada_no_se_recalcula():
    out = normalizar({"texto": "hola", "tipo_archivo": "TEXTO", "legibilidad": 0.9, "trace": []})
    assert out["legibilidad"] == 0.9
    assert out["trace"][-1]["detalle"]["legibilidad_provisional"] is False


def test_normalizar_con_imagen_borrosa_deriva_a_revision(monkeypatch):
    import agent.nodes.normalizar as modulo

    monkeypatch.setattr(modulo, "_confianza_ocr", lambda _img: None)
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [_b64(_pagina(blur=8, dark=0.4))],
        "trace": [],
    })
    assert out["legibilidad"] < 0.40
    assert out["trace"][-1]["detalle"]["fuente"] == "imagen"


def test_normalizar_con_varias_imagenes_usa_minimo(monkeypatch):
    """Cuando hay varias imágenes (p.ej. PDF de múltiples páginas), se usa el mínimo."""
    import agent.nodes.normalizar as modulo

    monkeypatch.setattr(modulo, "_confianza_ocr", lambda _img: None)
    # Una imagen buena (score alto) y una mala (score bajo)
    buena = _b64(_pagina())  # nitida ~1.0
    mala = _b64(_pagina(blur=8, dark=0.4))  # borrosa <0.40
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [buena, mala],
        "trace": [],
    })
    # El score debe ser el mínimo (el de la mala imagen)
    assert out["legibilidad"] < 0.40
    assert out["trace"][-1]["detalle"]["fuente"] == "imagen"


def test_imagen_no_decodificable_cuenta_cero():
    """Una página que no se puede ni decodificar es ilegible: cuenta 0.0 y queda
    anotada en la traza. Solo cuando NINGUNA decodifica se usa el proxy de texto."""
    buena = _b64(_pagina())
    out = normalizar({
        "texto": "a" * 250,
        "tipo_archivo": "IMAGEN",
        "imagenes": [buena, "esto-no-es-una-imagen"],
        "trace": [],
    })
    assert out["legibilidad"] == 0.0
    detalle = out["trace"][-1]["detalle"]
    assert detalle["imagenes_no_decodificables"] == 1


def _binario_tesseract() -> bool:
    """True si Tesseract está instalado (paquete + binario)."""
    try:
        import shutil

        import pytesseract

        pytesseract.get_tesseract_version()
        return shutil.which("tesseract") is not None
    except Exception:  # noqa: BLE001 - sin binario se salta el test OCR
        return False


_tesseract = pytest.mark.skipif(not _binario_tesseract(), reason="Tesseract no instalado")


@_tesseract
def test_sin_ocr_solo_mandan_las_metricas_de_imagen(monkeypatch):
    """Sin OCR disponible la puerta decide igual y lo deja anotado en la traza."""
    import agent.nodes.normalizar as modulo

    monkeypatch.setattr(modulo, "_confianza_ocr", lambda _img: None)
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [_b64(_pagina(blur=8, dark=0.4))],
        "trace": [],
    })
    detalle = out["trace"][-1]["detalle"]
    assert detalle["ocr_disponible"] is False
    assert detalle["confianza_ocr"] is None
    assert detalle["fuente"] == "imagen"


@_tesseract
def test_pocas_palabras_ocr_no_combinan(monkeypatch):
    """Con menos de 20 palabras (p. ej. manuscritas) manda el score óptico,
    pero la traza guarda lo que vio el OCR."""
    import agent.nodes.normalizar as modulo

    monkeypatch.setattr(modulo, "_confianza_ocr", lambda _img: (0.90, _PALABRAS_MIN_OCR - 1))
    img = _pagina()
    optico = _score_de_imagen(img)
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [_b64(img)],
        "trace": [],
    })
    assert out["legibilidad"] == optico
    detalle = out["trace"][-1]["detalle"]
    assert detalle["palabras_ocr"] == _PALABRAS_MIN_OCR - 1


@_tesseract
def test_suficientes_palabras_ocr_combinan(monkeypatch):
    """Con 20+ palabras la confianza del OCR se combina con el score óptico."""
    import agent.nodes.normalizar as modulo

    monkeypatch.setattr(modulo, "_confianza_ocr", lambda _img: (0.80, 30))
    img = _pagina(blur=8, dark=0.4)
    out = normalizar({
        "texto": "",
        "tipo_archivo": "IMAGEN",
        "imagenes": [_b64(img)],
        "trace": [],
    })
    detalle = out["trace"][-1]["detalle"]
    assert detalle["fuente"] == "imagen+ocr"
    assert detalle["palabras_ocr"] == 30
    assert detalle["confianza_ocr"] == 0.80
    assert out["legibilidad"] > _score_de_imagen(img)